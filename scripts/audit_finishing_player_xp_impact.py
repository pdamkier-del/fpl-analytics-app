#!/usr/bin/env python3
"""Read-only, paired six-GW player-xP impact of tau=50 team finishing shrinkage.

Compare ORIGINAL live vFinal simulator inputs with a diagnostic variant using
past-only goals versus xG. No model coefficients/production input/app output
are modified; penalties, minutes, and all other components are held constant.
The FPL player-goals aggregation can omit own goals; this is a proxy, not a
certified substitute for official club scoreline outcomes.
"""
from __future__ import annotations
import json
from pathlib import Path
import sys
import numpy as np
import pandas as pd

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'src'),str(ROOT/'scripts')]
from run_live_vfinal_joint_simulation import simulate,validate

BASE=ROOT/'data_v1_1/derived/live_locked_inputs/2026-27-v1'
WORK=ROOT/'work/live-final-model'
TAU=50.0

def main():
    baseline=pd.read_csv(BASE/'vfinal_live_full_simulator_input.csv.gz',low_memory=False)
    verify=validate(baseline)
    assert len(verify['gws'])==6,verify
    cutoff=pd.to_datetime(baseline.cutoff,utc=True,errors='raise')
    assert cutoff.nunique()==1
    cut=cutoff.iloc[0]
    h=pd.read_csv(BASE/'observed_team_xg_history.csv.gz')
    h['available_at']=pd.to_datetime(h.available_at,utc=True,errors='raise')
    h=h[h.available_at<cut].copy()
    ph=pd.read_csv(BASE/'player_fixture_observations.csv.gz',low_memory=False)
    ph['available_at']=pd.to_datetime(ph.available_at,utc=True,errors='raise')
    ph=ph[ph.available_at<cut].copy()
    assert h.duplicated(['fixture_uuid','team_id']).sum()==0
    assert ph.duplicated(['fixture_uuid','player_uuid']).sum()==0
    actual=ph.groupby(['fixture_uuid','team_id'],as_index=False).goals.sum()
    history=h.merge(actual,on=['fixture_uuid','team_id'],how='left',validate='one_to_one')
    assert history.goals.notna().all() and history.xg.notna().all()
    assert len(history)>=60 and history.team_id.nunique()==20
    t=history.groupby('team_id').agg(xg=('xg','sum'),goals=('goals','sum'),games=('xg','size'))
    t['factor']=(t.goals+TAU)/(t.xg+TAU)
    assert np.isfinite(t.factor).all() and (t.factor>0).all()
    present=set(baseline.home_team_id.astype(int))|set(baseline.away_team_id.astype(int))
    assert present==set(map(int,t.index)), 'No verified team finishing history for every active team'
    factors=t.factor.to_dict()

    cand=baseline.copy()
    side_factor=cand.team_id.map(factors).astype(float)
    cand['lambda_home_goals']=cand.lambda_home_goals*cand.home_team_id.map(factors).astype(float)
    cand['lambda_away_goals']=cand.lambda_away_goals*cand.away_team_id.map(factors).astype(float)
    cand['goal_mu']=cand.goal_mu*side_factor
    cand['assist_mu']=cand.assist_mu*side_factor
    assert validate(cand)==verify

    for name,frame in [('original',baseline),('candidate',cand)]:
        g=frame.groupby(['fixture_uuid','team_id'],sort=False)
        first=g[['lambda_home_goals','lambda_away_goals','home_team_id','assist_probability_per_goal']].first()
        lambdas=np.where(first.index.get_level_values('team_id').to_numpy()==first.home_team_id.to_numpy(),
                         first.lambda_home_goals.to_numpy(),first.lambda_away_goals.to_numpy())
        goal=g.goal_mu.sum().to_numpy()
        ass=g.assist_mu.sum().to_numpy()
        apg=first.assist_probability_per_goal.to_numpy()
        if not np.allclose(goal,lambdas,rtol=0,atol=1e-7):
            raise AssertionError(name+' failed goal mass conservation')
        if not np.allclose(ass,lambdas*apg,rtol=0,atol=1e-7):
            raise AssertionError(name+' failed assist mass conservation')

    fixture_seeds={fx:i for i,fx in enumerate(sorted(baseline.fixture_uuid.unique()))}
    alt,alt_audit=simulate(cand,draws=400,fixture_seed_offsets=fixture_seeds)
    original=pd.read_csv(BASE/'live_vfinal_fixture_xp.csv.gz')
    assert not original.duplicated(['fixture_uuid','player_uuid']).any()
    scores=original[['fixture_uuid','player_uuid','gw','xpts_fixture','goal_points','assist_points','expected_bonus']].merge(
        alt[['fixture_uuid','player_uuid','xpts_fixture','goal_points','assist_points','expected_bonus']],
        on=['fixture_uuid','player_uuid'],suffixes=('_base','_tau50'),validate='one_to_one')
    assert len(scores)==len(original)==len(alt)
    names=baseline[['player_uuid','fpl_element','player','team']].drop_duplicates('player_uuid')
    ranks=scores.groupby('player_uuid',as_index=False)[['xpts_fixture_base','xpts_fixture_tau50','goal_points_base',
                  'goal_points_tau50','assist_points_base','assist_points_tau50']].sum()
    ranks=ranks.merge(names,on='player_uuid',validate='one_to_one')
    ranks['delta']=ranks.xpts_fixture_tau50-ranks.xpts_fixture_base
    ranks=ranks.sort_values('xpts_fixture_base',ascending=False)
    mids=baseline[baseline.pos.astype(str).isin(['MID'])][['player_uuid']].drop_duplicates()
    midr=ranks[ranks.player_uuid.isin(set(mids.player_uuid))]
    le=ranks[ranks.fpl_element.eq(542)]
    if len(le)!=1:raise AssertionError('Le Fee FPL id changed')
    le_rows=scores.merge(baseline[['fixture_uuid','player_uuid','fpl_element']].drop_duplicates(),
                        on=['fixture_uuid','player_uuid'],validate='one_to_one')
    le_gw=le_rows[le_rows.fpl_element.eq(542)][['gw','xpts_fixture_base','xpts_fixture_tau50']]
    report={
        'classification':'READ_ONLY_FINISHING_PROXY_AB_NOT_FROZEN_PM_PROMOTION',
        'season':'2026-27','cutoff':str(cut),'tau':TAU,
        'historic_team_fixture_sides':len(history),
        'historical_goals_source':'FPL player-credit goals, may omit own goals',
        'comparison':'same original simulator, same 400 draws, same fixture seeds, unchanged non-goal inputs',
        'simulated_fixture_count':alt_audit['fixtures'],
        'simulated_player_fixture_rows':len(alt),
        'team_goal_assist_totals_preserved':True,
        'lefee_six_gw':le[['xpts_fixture_base','xpts_fixture_tau50','delta',
                          'goal_points_base','goal_points_tau50','assist_points_base','assist_points_tau50']].iloc[0].round(5).to_dict(),
        'lefee_by_gw':le_gw.round(5).to_dict(orient='records'),
        'top_midfielders_before':midr[['player','team','xpts_fixture_base','xpts_fixture_tau50','delta']].head(12).round(5).to_dict(orient='records'),
        'most_changed_players':ranks.reindex(ranks.delta.abs().sort_values(ascending=False).index)[['player','team','xpts_fixture_base','xpts_fixture_tau50','delta']].head(12).round(5).to_dict(orient='records'),
        'sunderland':{k:(int(v) if k=='games' else round(float(v),5)) for k,v in t.loc[20].to_dict().items()},
        'promotion_allowed':False,
        'limitations':['not an independent observed-player-outcome backtest',
          'FPL credited player goals may not include own goals',
          'penalty process intentionally unchanged',
          'no TS transfer or season replay']}
    WORK.mkdir(parents=True,exist_ok=True)
    out=WORK/'experimental_finishing_player_xp_impact.json'
    out.write_text(json.dumps(report,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    for name in ['lefee_six_gw','lefee_by_gw','top_midfielders_before','most_changed_players','sunderland']:
        print('FINISH_PLAYER_'+name.upper(),json.dumps(report[name],ensure_ascii=False))
    print('FINISH_PLAYER_EXPERIMENT',json.dumps({k:report[k] for k in
          ['classification','historic_team_fixture_sides','simulated_fixture_count',
           'simulated_player_fixture_rows','team_goal_assist_totals_preserved','promotion_allowed']},ensure_ascii=False))

if __name__=='__main__':
    main()

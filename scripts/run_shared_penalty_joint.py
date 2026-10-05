#!/usr/bin/env python3
"""Joint integration test for the shared penalty model.

Adds, marginally on top of the saved DefCon finalist:
- team penalty occurrence from team awarded + opponent conceded history;
- recency-weighted penalty taker allocation;
- taker conversion shrinkage;
- explicit scored penalty goals replacing equivalent expected team-goal mass;
- taker -2 for misses;
- opposing active GK +5 for a saved penalty;
- penalty saves are also included in the keeper's save count while expected
  penalty-save mass is removed from the ordinary keeper-save Poisson.

GW22-38 is a reused diagnostic, not independent holdout.
"""
from __future__ import annotations
import json,sys
from collections import defaultdict
from dataclasses import replace
from pathlib import Path
import numpy as np
import pandas as pd

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'));sys.path.insert(0,str(ROOT/'scripts'))

from fpl_v1_1_model.paired_joint import read_frozen_table,build_pair,run_pair
from run_shared_penalty_model import load_pl_penalties
from run_v4_performance_rating_experiment import player_id_map
from run_v4rc_experiment import write_json,sha

ROLE=ROOT/'analysis/results/role-event-priors-20261005-v1'
DC=ROOT/'analysis/results/defcon-threshold-finalist-20261005-v1/calibrated_dc.csv.gz'
FROZEN=ROOT/'analysis/results/deadline-joint-inputs-v1'
PEN=ROOT/'analysis/results/shared-penalty-model-20261005-v1'
OUT=ROOT/'analysis/results/shared-penalty-joint-20261005-v1'


def score(y,p):
    e=np.asarray(p)-np.asarray(y)
    return dict(mae=float(np.mean(np.abs(e))),rmse=float(np.sqrt(np.mean(e**2))),bias=float(np.mean(e)))


def canonical_team_map():
    line=[]
    for gw in range(1,39):
        z=pd.read_csv(ROOT/f'data_v1_1/raw/all-competitions-2025-26/GW{gw}/lineups.csv',
                      usecols=['match_id','team_code','player_name','is_starting'])
        z=z[z.is_starting.astype(str).str.lower().isin(['true','1','yes'])]
        line.append(z)
    line=pd.concat(line,ignore_index=True)
    clas=pd.read_csv(ROOT/'analysis/results/reproducible-role-v1/classified_starters.csv',
                     usecols=['match_id','fixture_uuid','team_id','player']).drop_duplicates()
    m=line.merge(clas,left_on=['match_id','player_name'],right_on=['match_id','player'],how='inner')
    x=m[['match_id','team_code','fixture_uuid','team_id']].drop_duplicates()
    bad=x.groupby(['match_id','team_code']).agg({'fixture_uuid':'nunique','team_id':'nunique'})
    if ((bad.fixture_uuid>1)|(bad.team_id>1)).any():
        raise ValueError('Ambiguous team identity mapping')
    return x.drop_duplicates(['match_id','team_code'])


def player_penalty_ledger():
    sides,pen=load_pl_penalties()
    pidmap=player_id_map()
    pen['player_uuid']=pd.to_numeric(pen.player_id,errors='coerce').map(pidmap)
    pen=pen[pen.player_uuid.notna()].copy()
    tm=canonical_team_map()
    pen=pen.merge(tm,on=['match_id','team_code'],how='inner',validate='many_to_one')
    return sides,pen,tm


def build_player_states(role,pen,half,tau_conv):
    """Return per target player-fixture penalty weight + conversion, cutoff-safe by GW."""
    decay=2**(-1/half)
    attempts=defaultdict(float);scored=defaultdict(float)
    league_sc=0.;league_at=0.
    bygw={int(gw):g for gw,g in pen.groupby('gw')}
    rows=[]
    for gw in sorted(role.gw.unique()):
        # decay once per GW before forecasting current GW
        for k in list(attempts):attempts[k]*=decay;scored[k]*=decay
        cur=role[role.gw==gw]
        lg=league_sc/league_at if league_at>0 else .78
        for r in cur.itertuples(index=False):
            pid=str(r.player_uuid);a=attempts[pid];s=scored[pid]
            conv=(s+tau_conv*lg)/(a+tau_conv)
            rows.append(dict(fixture_uuid=r.fixture_uuid,player_uuid=pid,team_id=int(r.team_id),
                             gw=int(gw),pen_attempt_state=a,pen_conversion=float(conv)))
        # update after prediction using all actual penalty attempts in this GW
        g=bygw.get(int(gw))
        if g is not None:
            for r in g.itertuples(index=False):
                pid=str(r.player_uuid);att=float(r.attempts);sc=float(r.penalties_scored)
                attempts[pid]+=att;scored[pid]+=sc;league_at+=att;league_sc+=sc
    return pd.DataFrame(rows)


def build_team_penalty_targets(role,sides,tm,tau):
    # Reconstruct same sequential EB occurrence model, but attach canonical ids.
    team=defaultdict(lambda:[0.,0.]);conceded=defaultdict(lambda:[0.,0.]);league=[0.,0.]
    rec=[]
    for gw in sorted(sides.gw.unique()):
        cur=sides[sides.gw==gw]
        for r in cur.itertuples(index=False):
            lg=league[0]/league[1] if league[1]>0 else .12
            a,n=team[int(r.team_code)];c,m=conceded[int(r.opp_code)]
            own=(a+tau*lg)/(n+tau);opp=(c+tau*lg)/(m+tau)
            lam=max(1e-6,.5*own+.5*opp)
            rec.append(dict(gw=int(gw),match_id=r.match_id,team_code=int(r.team_code),lambda_pen=lam))
        for _,g in cur.groupby('match_id'):
            for r in g.itertuples(index=False):
                t=int(r.team_code);o=int(r.opp_code);att=float(r.attempts)
                team[t][0]+=att;team[t][1]+=1;conceded[o][0]+=att;conceded[o][1]+=1;league[0]+=att;league[1]+=1
    p=pd.DataFrame(rec).merge(tm,on=['match_id','team_code'],how='inner',validate='many_to_one')
    p=p[['fixture_uuid','team_id','gw','lambda_pen']].drop_duplicates(['fixture_uuid','team_id'])
    keys=role[['fixture_uuid','team_id','gw']].drop_duplicates()
    return keys.merge(p,on=['fixture_uuid','team_id','gw'],how='left',validate='one_to_one')


def main():
    if OUT.exists():raise FileExistsError(OUT)
    OUT.mkdir(parents=True)
    summ=json.loads((PEN/'model_summary.json').read_text())
    tau=float(summ['selected']['occurrence_tau'])
    half=float(summ['selected']['taker_half_life'])
    tau_conv=float(summ['selected']['conversion_tau'])
    psave=float(summ['selected']['p_keeper_save_given_miss'])

    role=read_frozen_table(ROLE,'candidate_inputs')
    dc=pd.read_csv(DC)[['fixture_uuid','player_uuid','mu_cal']]
    role=role.merge(dc,on=['fixture_uuid','player_uuid'],how='left',validate='one_to_one')
    role['mu_dc']=role.mu_cal.fillna(role.mu_dc);role=role.drop(columns=['mu_cal'])

    sides,pen,tm=player_penalty_ledger()
    pst=build_player_states(role,pen,half,tau_conv)
    teams=build_team_penalty_targets(role,sides,tm,tau)
    role=role.merge(pst,on=['fixture_uuid','player_uuid','team_id','gw'],how='left',validate='one_to_one')
    role['pen_attempt_state']=role.pen_attempt_state.fillna(0)
    role['pen_conversion']=role.pen_conversion.fillna(.78)
    role=role.merge(teams[['fixture_uuid','team_id','lambda_pen']],on=['fixture_uuid','team_id'],how='left',validate='many_to_one')
    role['lambda_pen']=role.lambda_pen.fillna(float(teams.lambda_pen.mean()))

    # Translate penalty history into roster weights. Small goal-rate fallback
    # allows a new/no-history taker but historical attempts dominate.
    role['pen_weight_raw']=role.pen_attempt_state + .02*np.maximum(role.goal_rate90,1e-6)
    denom=role.groupby(['fixture_uuid','team_id']).pen_weight_raw.transform('sum')
    role['pen_weight']=np.where(denom>0,role.pen_weight_raw/denom,0)
    role['team_pen_conversion']=(role.pen_weight*role.pen_conversion).groupby([role.fixture_uuid,role.team_id]).transform('sum')
    role[['fixture_uuid','player_uuid','team_id','gw','lambda_pen','pen_weight','pen_conversion','team_pen_conversion']].to_csv(
        OUT/'penalty_joint_inputs.csv.gz',index=False,compression='gzip')

    truth=read_frozen_table(FROZEN,'targets')
    rec=[]
    for i,(fx,g) in enumerate(role[role.gw.between(22,38)].groupby('fixture_uuid',sort=True)):
        _,base=build_pair(g)
        lookup=g.set_index('player_uuid')
        home=int(g.home_team_id.iloc[0]);away=int(g.away_team_id.iloc[0])
        hrow=g[g.team_id==home].iloc[0];arow=g[g.team_id==away].iloc[0]
        players=tuple(replace(p,
            penalty_weight=float(lookup.loc[p.player_id,'pen_weight']),
            penalty_conversion=float(lookup.loc[p.player_id,'pen_conversion'])) for p in base.players)
        treat=replace(base,players=players,
            lambda_home_penalties=float(hrow.lambda_pen),
            lambda_away_penalties=float(arow.lambda_pen),
            home_penalty_conversion=float(hrow.team_pen_conversion),
            away_penalty_conversion=float(arow.team_pen_conversion),
            p_penalty_save_given_miss=psave)
        a,b=run_pair(base,treat,n=400,seed=36092501+i)
        for r in g.itertuples():
            rec.append(dict(fixture_uuid=fx,player_uuid=r.player_uuid,gw=r.gw,
              final_dc=a[r.player_uuid]['xPts_nonbonus'],
              final_dc_penalty=b[r.player_uuid]['xPts_nonbonus'],
              penalty_miss_points=b[r.player_uuid].get('penalty_miss_points',0.0),
              penalty_save_points=b[r.player_uuid].get('penalty_save_points',0.0)))
    pred=pd.DataFrame(rec);sc=pred.merge(truth,on=['fixture_uuid','player_uuid'],validate='one_to_one')
    y=sc.total_points-sc.bonus;m0=score(y,sc.final_dc);m1=score(y,sc.final_dc_penalty)
    report=dict(classification='reused_diagnostic_not_independent_holdout',
      architecture=summ['architecture'],selected=summ['selected'],
      rows=len(sc),fixtures=int(sc.fixture_uuid.nunique()),draws_per_fixture=400,
      nonbonus={'final_dc':m0,'final_dc_plus_shared_penalty':m1},
      delta={k:m1[k]-m0[k] for k in ['mae','rmse','bias']},
      mean_penalty_miss_points=float(pred.penalty_miss_points.mean()),
      mean_penalty_save_points=float(pred.penalty_save_points.mean()),
      promoted=False)
    write_json(OUT/'joint_metrics.json',report)
    pred.to_csv(OUT/'joint_predictions.csv.gz',index=False,compression='gzip')
    write_json(OUT/'protocol.json',dict(
      note='Scored penalty mass replaces expected mass in existing team-goal lambda; misses and GK saves are one shared event',
      reused_diagnostic='GW22-38',promotion_allowed=False))
    outs=[p for p in sorted(OUT.iterdir()) if p.name!='manifest.json']
    write_json(OUT/'manifest.json',dict(sources=[
      dict(path='scripts/run_shared_penalty_joint.py',sha256=sha(Path(__file__))),
      dict(path='src/fpl_v1_1_model/joint_simulator.py',sha256=sha(ROOT/'src/fpl_v1_1_model/joint_simulator.py'))],
      outputs=[dict(path=p.name,sha256=sha(p)) for p in outs]))
    print(json.dumps(report,indent=2))

if __name__=='__main__':main()

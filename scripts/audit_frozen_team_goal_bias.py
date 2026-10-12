#!/usr/bin/env python3
"""Audit frozen PM team-goal *means* against observed goals, without promoting a model.

Tests the actual, unchanged fit_team_latent from vFinal on 2025/26 Premier League
in strict GW-ahead refits. Select a minimal global scoring calibration using only
GW6-21, then report untouched GW22-38. Also report GW3-5 2026/27 walk-forward
from the current pre-cutoff evidence and diagnose Sunderland GW7-12.
No TS, player xP or production input is altered.

Caveat: the 2025/26 backtest's xG source is FotMob team match xG; live input uses
verified sums of FPL player xG. The fit math is identical, input provider differs.
"""
from __future__ import annotations
import json,sys
from pathlib import Path
import numpy as np
import pandas as pd
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from fpl_v1_1_model.vfinal_replay_state import fit_team_latent
RAW=ROOT/'data_v1_1/raw/all-competitions-2025-26'
BASE=ROOT/'data_v1_1/derived/live_locked_inputs/2026-27-v1'
OUT=ROOT/'work/live-final-model/team_goal_bias_full_audit.json'
TAUS=(None,20.,50.,100.,200.)
RNG=np.random.default_rng(20261012)

def dev(y,p):
    y=np.asarray(y,float);p=np.clip(np.asarray(p,float),1e-9,None)
    return 2*np.where(y>0,y*np.log(np.maximum(y,1e-12)/p)-(y-p),p)

def score(df,pcol='pred'):
    v=df[pcol].to_numpy(float);y=df.actual.to_numpy(float)
    return dict(n=len(df),observed_mean=round(float(np.mean(y)),5),
      predicted_mean=round(float(np.mean(v)),5),
      observed_total=round(float(np.sum(y)),4),
      predicted_total=round(float(np.sum(v)),4),
      predicted_over_actual_pct=round(float(100*(np.sum(v)/max(1e-9,np.sum(y))-1)),3),
      mae=round(float(np.mean(np.abs(v-y))),6),
      poisson_deviance=round(float(np.mean(dev(y,v))),6))

def load_2025():
    m=[]
    for gw in range(1,39):
        x=pd.read_csv(RAW/f'GW{gw}'/'matches.csv',low_memory=False)
        x=x[x.match_id.astype(str).str.startswith('25-26-prem-')].copy()
        m.append(x)
    m=pd.concat(m,ignore_index=True).drop_duplicates('match_id')
    m=m[m.finished.astype(str).str.lower().eq('true')].copy()
    numeric=['gameweek','home_team','away_team','home_score','away_score','home_expected_goals_xg','away_expected_goals_xg']
    for col in numeric:m[col]=pd.to_numeric(m[col],errors='coerce')
    m=m.dropna(subset=numeric).copy()
    assert m.match_id.nunique()>=375,m.match_id.nunique()
    m['gw']=m.gameweek.astype(int)
    assert m.gw.between(1,38).all()
    assert m[['home_team','away_team']].notna().all().all()
    h=[]
    for v in m.itertuples(index=False):
        h.append(dict(match_id=v.match_id,gw=v.gw,team_id=int(v.home_team),
                      opponent_team_id=int(v.away_team),was_home=True,xg=float(v.home_expected_goals_xg),
                      actual=float(v.home_score)))
        h.append(dict(match_id=v.match_id,gw=v.gw,team_id=int(v.away_team),
                      opponent_team_id=int(v.home_team),was_home=False,xg=float(v.away_expected_goals_xg),
                      actual=float(v.away_score)))
    h=pd.DataFrame(h)
    assert h.duplicated(['match_id','team_id']).sum()==0
    assert h.team_id.nunique()==20
    return m,h

def compute_gws(matches,sides,min_gw):
    rows=[]
    for gw in sorted(set(sides.gw)):
        if gw<min_gw:continue
        past=sides[sides.gw<gw].copy()
        future=sides[sides.gw==gw].copy()
        if len(past)<40 or future.empty:continue
        assert not set(past.match_id)&set(future.match_id)
        target=matches[matches.gw==gw].copy()
        if target.empty:continue
        schedule=target[['match_id']].copy()
        schedule['home_team_id']=target.home_team.astype(int).to_numpy()
        schedule['away_team_id']=target.away_team.astype(int).to_numpy()
        assert set(schedule.match_id)==set(future.match_id)
        raw=fit_team_latent(past.rename(columns={'actual':'goals'}),schedule,gw)
        goals_fit=fit_team_latent(past.assign(xg=past.actual),schedule,gw)
        ratio=float(past.actual.sum()/past.xg.sum())
        league_xg=float(past.xg.mean());league_goals=float(past.actual.mean())
        for fr in schedule.itertuples(index=False):
            a,b=raw[str(fr.match_id)]
            ga,gb=goals_fit[str(fr.match_id)]
            for team,xpred,gpred,home in ((int(fr.home_team_id),a,ga,True),
                                           (int(fr.away_team_id),b,gb,False)):
                actual=future[(future.match_id==fr.match_id)&(future.team_id==team)]
                assert len(actual)==1
                obs=float(actual.iloc[0].actual)
                r=dict(gw=int(gw),match_id=str(fr.match_id),team=team,
                       home=home,actual=obs,xg_actual=float(actual.iloc[0].xg),
                       pred=float(xpred),goal_fit=float(gpred),
                       league_xg=league_xg,league_actual=league_goals,
                       past_goals=float(past.actual.sum()),past_xg=float(past.xg.sum()))
                for tau in TAUS:
                    suffix='none' if tau is None else str(int(tau))
                    fac=1. if tau is None else (r['past_goals']+tau)/(r['past_xg']+tau)
                    r['global_'+suffix]=float(xpred*fac)
                # Goal-fitted variant not promoted without independent proof.
                for alpha in (.25,.5,1.):
                    r['goalblend_'+str(alpha)]=float((1-alpha)*xpred+alpha*gpred)
                rows.append(r)
    return pd.DataFrame(rows)

def select_holdout(r):
    devset=r[r.gw.between(6,21)]
    holdset=r[r.gw.between(22,38)]
    assert len(devset)>=300 and len(holdset)>=300
    candidates=['pred']+[f'global_{int(x)}' for x in TAUS if x is not None]+[
               f'goalblend_{a}' for a in (.25,.5,1.)]
    devscores={col:score(devset,col) for col in candidates}
    selection=min(candidates,key=lambda c:(devscores[c]['poisson_deviance'],devscores[c]['mae']))
    hscores={col:score(holdset,col) for col in candidates}
    a=holdset.pred.to_numpy(float)
    b=holdset[selection].to_numpy(float)
    y=holdset.actual.to_numpy(float)
    bymatch=holdset.assign(delta=dev(y,b)-dev(y,a)).groupby('match_id').delta.agg('sum')
    md=holdset.groupby('match_id').size()
    assert md.eq(2).all()
    diff=1000 # placeholder overwritten below
    diffs=[]
    x=bymatch.to_numpy(float)
    for _ in range(2000):
        sample=RNG.integers(0,len(x),len(x))
        diffs.append(float(x[sample].sum()/(2*len(sample))))
    # Regression-to-mean bias at the upper tail of the FROZEN prediction:
    high=[]
    for lab,mask in [('below_1',a<1),('1_to_1_5',(a>=1)&(a<1.5)),
                     ('1_5_to_2',(a>=1.5)&(a<2)),('at_least_2',a>=2),
                     ('at_least_2_5',a>=2.5)]:
        q=holdset[mask]
        if len(q):high.append(dict(segment=lab,**score(q)))
    # Paired goal-share uncertainty, resample whole fixtures.
    game=holdset.groupby('match_id').agg(predicted=('pred','sum'),actual=('actual','sum'))
    arr=game[['predicted','actual']].to_numpy(float)
    over=[]
    for _ in range(2000):
        samp=arr[RNG.integers(0,len(arr),len(arr))]
        over.append(float(samp[:,0].sum()/max(1e-10,samp[:,1].sum())-1))
    return dict(train='GW6-21',holdout='GW22-38',
       chosen_on_dev=selection,dev=devscores,
       holdout_all=hscores,holdout_by_original_prediction=high,
       holdout_original_over_actual_95ci_pct=[round(float(v)*100,2) for v in np.quantile(over,[.025,.975])],
       chosen_minus_original_deviance_95ci=[round(float(v),6) for v in np.quantile(diffs,[.025,.975])],
       positive_delta_is_worse=True,
       provisional_conclusion='No promotion without holdout advantage and consistent metrics')

def live():
    h=pd.read_csv(BASE/'observed_team_xg_history.csv.gz')
    ph=pd.read_csv(BASE/'player_fixture_observations.csv.gz',low_memory=False)
    forecast=pd.read_csv(BASE/'future_team_goal_lambdas.csv.gz')
    cutoff=pd.to_datetime(ph.available_at,utc=True,errors='raise')
    h['available_at']=pd.to_datetime(h.available_at,utc=True,errors='raise')
    assert h.available_at.max()<=cutoff.max()
    h=h.drop_duplicates(['fixture_uuid','team_id']).copy()
    g=ph.groupby(['fixture_uuid','team_id'],as_index=False).goals.sum()
    h=h.merge(g,on=['fixture_uuid','team_id'],how='inner',validate='one_to_one')
    h=h.rename(columns={'goals':'actual'})
    assert len(h)>=80 and h.team_id.nunique()==20
    original_player_goals=float(h.actual.sum())
    # Verify match outcomes against official FPL fixture SCORELINES.
    # FPL player-credit goals omit own goals; scorelines do not.
    # Never fill missing scores with fabricated outcomes.
    official=json.loads((ROOT/'work/live-final-model/fixtures.json').read_text())
    by_id={int(v['id']):v for v in official}
    actual_scores=[];discrepancies=[]
    for v in h.itertuples(index=False):
        fixture_id=int(str(v.fixture_uuid).split('-')[-1])
        fx=by_id.get(fixture_id)
        if (fx is None or not fx.get('finished') or
            fx.get('team_h_score') is None or fx.get('team_a_score') is None):
            actual_scores.append(np.nan)
            continue
        expected_home=int(fx['team_h']);expected_away=int(fx['team_a'])
        if (bool(v.was_home) and expected_home!=int(v.team_id) or
            not bool(v.was_home) and expected_away!=int(v.team_id)):
            raise ValueError('Official fixture team identity mismatch')
        outcome=float(fx['team_h_score'] if bool(v.was_home) else fx['team_a_score'])
        actual_scores.append(outcome)
        if abs(outcome-float(v.actual))>1e-10:
            discrepancies.append(dict(fixture_id=fixture_id,team=int(v.team_id),
                                      scoreline=outcome,player_credited_goals=float(v.actual)))
    # Archived player-xG sides can precede final FPL fixture status. Exclude,
    # rather than fabricate results for, any still-incomplete pair.
    h['actual']=actual_scores
    unavailable=h[h.actual.isna()].fixture_uuid.astype(str).unique().tolist()
    verified=h.dropna(subset=['actual']).copy()
    sizes=verified.groupby('fixture_uuid').size()
    complete=set(sizes[sizes.eq(2)].index)
    h=verified[verified.fixture_uuid.isin(complete)].copy()
    if len(h)<100:
        raise ValueError(f'Fewer than 50 fully verified fixtures: {len(h)//2}')
    reconciliation=dict(official_fixture_sides=len(h),
                        excluded_without_final_score=len(unavailable),
                        excluded_examples=unavailable[:5],
                        player_credited_goal_total=original_player_goals,
                        official_scoreline_goal_total=float(h.actual.sum()),
                        side_mismatches=len(discrepancies),
                        examples=discrepancies[:6])
    # Only completed historical fixtures and only earlier GWs for each prediction.
    fxs=[]
    for f,grp in h.groupby('fixture_uuid'):
        if len(grp)!=2:continue
        home=grp[grp.was_home==True];away=grp[grp.was_home==False]
        if len(home)!=1 or len(away)!=1:continue
        fxs.append(dict(match_id=f,gw=int(grp.gw.iloc[0]),
                       home_team=int(home.team_id.iloc[0]),away_team=int(away.team_id.iloc[0])))
    m=pd.DataFrame(fxs)
    h=h[h.fixture_uuid.isin(m.match_id)].copy()
    h['match_id']=h.fixture_uuid
    r=compute_gws(m,h,min_gw=3)
    r=r.dropna()
    if len(r)<30:raise AssertionError(f'not enough 2026 walkforward, got {len(r)}')
    o=score(r)
    tail=score(r[r.pred>=2]) if (r.pred>=2).any() else None
    alternatives={col:score(r,col) for col in ['pred','global_50','goalblend_0.25','goalblend_0.5','goalblend_1.0']}
    rows_by_gw=[dict(gw=int(gw),**score(z)) for gw,z in r.groupby('gw')]
    league=dict(games=int(len(h)/2),xg=round(float(h.xg.sum()),4),
                official_scoreline_goals=round(float(h.actual.sum()),4),
                fpl_credited_goals=round(original_player_goals,4),
                xg_per_side=round(float(h.xg.mean()),5),
                goals_per_side=round(float(h.actual.mean()),5))
    sides=[]
    for fr in forecast.itertuples(index=False):
        sides.extend([dict(gw=int(fr.gw),fixture=int(fr.fpl_fixture_id),team=int(fr.home_team_id),
                           lam=float(fr.lambda_home_goals)),
                      dict(gw=int(fr.gw),fixture=int(fr.fpl_fixture_id),team=int(fr.away_team_id),
                           lam=float(fr.lambda_away_goals))])
    v=pd.DataFrame(sides)
    sun=v[v.team==20]
    past_sun=h[h.team_id==20]
    sunreport=dict(games=int(len(past_sun)),historical_xg_per_match=round(float(past_sun.xg.mean()),4),
                   historical_goals_per_match=round(float(past_sun.actual.mean()),4),
                   frozen_upcoming_lambdas=[dict(gw=int(rr.gw),pred=round(float(rr.lam),4)) for rr in sun.itertuples(index=False)],
                   frozen_upcoming_mean=round(float(sun.lam.mean()),5),
                   coming_matches=int(len(sun)))
    ranked=v.groupby('team').lam.agg(['mean','count']).sort_values('mean',ascending=False).head(10)
    league_factor=(float(h.actual.sum())+50.)/(float(h.xg.sum())+50.)
    return dict(classification='CURRENT_2026_27_SOURCE_LIMITED_WALKFORWARD_NOT_PM_CERTIFICATION',
                historical_league=league,scoreline_reconciliation=reconciliation,
                gw3_to_latest_walkforward=score(r),early_alternative_scores=alternatives,
                gw3_to_latest_by_gw=rows_by_gw,
                high_predicted_lambda_walkforward=tail,
                tested_gws=sorted(map(int,r.gw.unique())),
                forward_sides=len(r),
                current_six_gw_league_pred_per_team_match=round(float(v.lam.mean()),5),
                current_six_gw_league_pred_total=round(float(v.lam.sum()),4),
                current_future_lambda_ge2_count=int((v.lam>=2).sum()),
                current_future_lambda_ge2_5_count=int((v.lam>=2.5).sum()),
                strongest_forward_team_lambdas=[dict(team=int(t),mean=round(float(rr['mean']),5),
                                            matches=int(rr['count'])) for t,rr in ranked.iterrows()],
                current_global_50_goals_xg_factor=round(league_factor,6),
                global_50_diagnostic_adjusted_sunderland=round(float(sun.lam.mean()*league_factor),5),
                sunderland=sunreport,
                caution='2026/27 sample covers only 5 completed GWs and GW3-5 walkforward; official scorelines verified and reconciled to FPL credited player goals')

def main():
    m,h=load_2025()
    raw=compute_gws(m,h,min_gw=3)
    assert raw.match_id.nunique()>=300
    hold=select_holdout(raw)
    early=raw[raw.gw.between(3,5)]
    early_baseline=score(early)
    early_high=score(early[early.pred>=2]) if (early.pred>=2).any() else None
    report=dict(classification='READ_ONLY_ORIGINAL_FROZEN_TEAM_LATENT_WALKFORWARD_GOAL_BIAS_AUDIT',
                historical_early_gw3_5=dict(baseline=early_baseline,high_predicted_lambdas=early_high,
                                          lambda_ge2=int((early.pred>=2).sum())),
                historical_2025_26_coverage=dict(matches=int(m.match_id.nunique()),
                    team_sides=int(len(h)),teams=int(h.team_id.nunique())),
                historical=hold,live=live(),production_model_changed=False,
                original_fit='fpl_v1_1_model.vfinal_replay_state.fit_team_latent ridge=.25 half_life=16',
                limitation='2025/26 source FotMob match xG vs live 2026/27 FPL player summed xG; no TS or player PM scoring replay')
    OUT.parent.mkdir(parents=True,exist_ok=True)
    OUT.write_text(json.dumps(report,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    print('TEAM_GOALS_COVERAGE',json.dumps(report['historical_2025_26_coverage']))
    print('TEAM_GOALS_EARLY_2025',json.dumps(report['historical_early_gw3_5']))
    print('TEAM_GOALS_HOLDOUT',json.dumps({k:hold[k] for k in ['chosen_on_dev','holdout_all','holdout_by_original_prediction','holdout_original_over_actual_95ci_pct','chosen_minus_original_deviance_95ci']}))
    print('TEAM_GOALS_DEVELOPMENT',json.dumps({k:hold['dev'][k] for k in hold['dev']}))
    print('TEAM_GOALS_LIVE',json.dumps(report['live']))
if __name__=='__main__':main()

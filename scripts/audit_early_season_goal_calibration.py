#!/usr/bin/env python3
"""Read-only time-decaying actual-goals + xG team-lambda experiment.

Original locked fit_team_latent (xG target) is compared with the very same
model refitted to pre-deadline ACTUAL TEAM SCORELINES. Actual goals automatically
reflect past attack AND opponent defence; no target GW outcomes are used.

The proposed probability blend is:
lambda(t) = (1-alpha_t)*lambda_xg(t) + alpha_t*lambda_goals(t),
alpha_t = alpha_at_gw3 * 2**(-(gw-3)/half_life_gw).

Development GW3-12 in 2025/26 only; validation GW13-21; historical untouched
GW22-38 and independent 2026/27 completed GW3-5 as diagnostic. Uses known
actual results for labels and xG rates from source FotMob (2025/26) and
complete-player FPL xG (2026/27). No live or frozen production change.
"""
from __future__ import annotations
import json,sys
from pathlib import Path
import numpy as np
import pandas as pd

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'scripts'),str(ROOT/'src')]
from audit_frozen_team_goal_bias import load_2025,compute_gws,score,dev
from fpl_v1_1_model.vfinal_replay_state import fit_team_latent

BASE=ROOT/'data_v1_1/derived/live_locked_inputs/2026-27-v1'
WORK=ROOT/'work/live-final-model'
RNG=np.random.default_rng(20261012)
CONFIGS={
 'locked_xg':(0.,8.),
 'fade20_h6':(.2,6.),
 'fade35_h6':(.35,6.),
 'fade50_h6':(.5,6.),
 'fade35_h12':(.35,12.),
 'fade50_h12':(.5,12.),
 'fade25_h16':(.25,16.),
 'constant25':(.25,float('inf')),
 'constant50':(.5,float('inf')),
}

def weight(gws,alpha,half):
    g=np.asarray(gws,float)
    w=alpha*2**(-np.maximum(g-3.,0.)/half)
    return np.where(np.isfinite(w),w,alpha)

def variants(df):
    v=df.copy()
    for name,(alpha,half) in CONFIGS.items():
        w=weight(v.gw,alpha,half)
        v[name]=(1-w)*v.pred+w*v.goal_fit
    return v

def window_scores(frame):
    return {name:score(frame,name) for name in CONFIGS}

def paired_boot(frame,chosen,reps=2000):
    q=frame.copy()
    q['loss_delta']=dev(q.actual,q[chosen])-dev(q.actual,q.pred)
    grp=q.groupby('match_id').agg(delta=('loss_delta','sum'),pred=('pred','sum'),actual=('actual','sum'))
    assert q.groupby('match_id').size().eq(2).all()
    vals=grp[['delta','pred','actual']].to_numpy(float)
    n=len(vals)
    diffs=[];bias=[]
    for _ in range(reps):
        a=vals[RNG.integers(0,n,size=n)]
        diffs.append(float(a[:,0].sum()/(2*n)))
        bias.append(float((a[:,1].sum()-a[:,2].sum())/a[:,2].sum()*100))
    return dict(matches=n,chosen_minus_baseline_poisson_deviance_ci95=[round(float(x),6) for x in np.quantile(diffs,[.025,.975])],
        original_total_bias_ci95_pct=[round(float(x),3) for x in np.quantile(bias,[.025,.975])])

def current_rows():
    h=pd.read_csv(BASE/'observed_team_xg_history.csv.gz')
    h['available_at']=pd.to_datetime(h.available_at,utc=True,errors='raise')
    meta=json.loads((WORK/'source_manifest.json').read_text())
    cutoff=pd.Timestamp(meta['observed_at'])
    h=h[h.available_at<cutoff].copy()
    ph=pd.read_csv(BASE/'player_fixture_observations.csv.gz',low_memory=False)
    ph['available_at']=pd.to_datetime(ph.available_at,utc=True,errors='raise')
    ph=ph[ph.available_at<cutoff].copy()
    player_goals=ph.groupby(['fixture_uuid','team_id'],as_index=False).goals.sum()
    h=h.merge(player_goals,on=['fixture_uuid','team_id'],how='inner',validate='one_to_one')
    official=json.loads((WORK/'fixtures.json').read_text())
    lookup={int(f['id']):f for f in official}
    facts=[];verified=set();excluded=[]
    for f,sub in h.groupby('fixture_uuid'):
        if len(sub)!=2:
            excluded.append(str(f));continue
        fixture=lookup.get(int(str(f).split('-')[-1]))
        if (fixture is None or not fixture.get('finished') or
            fixture.get('team_h_score') is None or fixture.get('team_a_score') is None):
            excluded.append(str(f));continue
        home=sub[sub.was_home==True];away=sub[sub.was_home==False]
        if len(home)!=1 or len(away)!=1:raise ValueError('Misidentified home/away')
        assert int(home.team_id.iloc[0])==int(fixture['team_h'])
        assert int(away.team_id.iloc[0])==int(fixture['team_a'])
        facts.append(dict(match_id=f,gw=int(sub.gw.iloc[0]),
                          home_team=int(home.team_id.iloc[0]),away_team=int(away.team_id.iloc[0])))
        verified.add(str(f))
        for key,side in [('home',home),('away',away)]:
            p=float(fixture['team_h_score'] if key=='home' else fixture['team_a_score'])
            h.loc[side.index,'actual']=p
    h=h[h.fixture_uuid.isin(verified)].copy()
    m=pd.DataFrame(facts)
    assert len(h)>=100 and m.match_id.nunique()>=50,('Unexpected 2026 historical coverage',len(h),excluded[:5])
    h['match_id']=h.fixture_uuid
    r=compute_gws(m,h,min_gw=3)
    assert len(r)>=60 and r.gw.min()==3,(len(r),sorted(r.gw.unique()))
    print('EARLY_CAL_LIVE_VERIFIED_COVERAGE',json.dumps(dict(matches=len(m),scored_week_min=int(m.gw.min()),
                     scored_week_max=int(m.gw.max()),excluded_unfinished=len(excluded),
                     scored_season_2026_gws=sorted(map(int,r.gw.unique())))))
    return h,variants(r),cutoff

def prospective(h):
    forecast=pd.read_csv(BASE/'future_team_goal_lambdas.csv.gz')
    assert forecast.gw.nunique()==6
    origin=int(forecast.gw.min())
    targets=forecast[['fpl_fixture_id','home_team_id','away_team_id']].copy()
    targets['match_id']='fpl-2026-27-'+targets.fpl_fixture_id.astype(int).astype(str)
    fit_goals=fit_team_latent(h.assign(xg=h.actual),targets[['match_id','home_team_id','away_team_id']],origin)
    fit_xg=fit_team_latent(h,targets[['match_id','home_team_id','away_team_id']],origin)
    report=[]
    for fr in forecast.itertuples(index=False):
        key='fpl-2026-27-'+str(int(fr.fpl_fixture_id))
        for team,base,orig,goal_fit in [
             (int(fr.home_team_id),float(fr.lambda_home_goals),float(fit_xg[key][0]),float(fit_goals[key][0])),
             (int(fr.away_team_id),float(fr.lambda_away_goals),float(fit_xg[key][1]),float(fit_goals[key][1]))]:
            report.append(dict(gw=int(fr.gw),fixture_id=int(fr.fpl_fixture_id),team=team,
                               pred=base,refit_xg=orig,goal_fit=goal_fit))
    a=pd.DataFrame(report)
    assert len(a)==120
    diff=float(np.max(np.abs(a.pred-a.refit_xg)))
    if diff>1e-7:raise AssertionError(f'Current original PM refit does not match checkpoint: {diff}')
    a=variants(a)
    sun=a[a.team==20]
    top=a.groupby('team',as_index=False).agg(
         original=('pred','mean'),goal_fit=('goal_fit','mean'))
    return a,dict(verified_baseline_max_abs_diff=diff,
            baseline_avg_lam=round(float(a.pred.mean()),5),
            by_model={name:round(float(a[name].mean()),5) for name in CONFIGS},
            projected_at_least_2_by_model={name:int((a[name]>=2).sum()) for name in CONFIGS},
            sunderland={name:round(float(sun[name].mean()),5) for name in CONFIGS},
            sunderland_by_gw=[dict(gw=int(r.gw),original=round(float(r.pred),4),
                          goal_fitted=round(float(r.goal_fit),4),
                          **{name:round(float(getattr(r,name)),4) for name in CONFIGS if name!='locked_xg'})
                           for r in sun.itertuples(index=False)],
            top_original=top.sort_values('original',ascending=False).head(8).round(5).to_dict(orient='records'))

def main():
    m,h=load_2025()
    historical=variants(compute_gws(m,h,min_gw=3))
    assert historical.match_id.nunique()>300
    development=historical[historical.gw.between(3,12)]
    validation=historical[historical.gw.between(13,21)]
    holdout=historical[historical.gw.between(22,38)]
    assert min(len(z) for z in [development,validation,holdout])>150
    train=window_scores(development)
    # Select only on development. No glance at validation/holdout/current.
    choice=min(CONFIGS, key=lambda name:(train[name]['poisson_deviance'],train[name]['mae']))
    hold=window_scores(holdout)
    val=window_scores(validation)
    early2025=window_scores(historical[historical.gw.between(3,5)])
    h2,live,_=current_rows()
    # Independent fixed GW3-5 comparison, regardless of a newer rolling checkpoint.
    current_early=live[live.gw.between(3,5)].copy()
    assert len(current_early)==60
    live_scores=window_scores(current_early)
    live_high=window_scores(current_early[current_early.pred>=2])
    _,projection=prospective(h2)
    results=dict(classification='READ_ONLY_TIME_DECAYING_TEAM_GOALS_EXPERIMENT_NO_PRODUCTION_PROMOTION',
        original_model='unchanged fit_team_latent fitted to xG + separate refit to scored goals',
        goal_defense_handling='actual-goal refit learns opponent conceded goals and team goal scoring jointly',
        formula='(1-weight(gw))*xG_lambda + weight(gw)*goals_lambda; weight(gw)=alpha*2**(-(gw-3)/half_life)',
        configs=CONFIGS,dev_gw3_12=train,selected_on_dev_only=choice,
        validation_gw13_21=val,untouched_holdout_gw22_38=hold,
        early_gw3_5_2025=early2025,early_gw3_5_2026=live_scores,
        current_early_high_original_ge2=live_high,
        validation_bootstrap=paired_boot(validation,choice),
        holdout_bootstrap=paired_boot(holdout,choice),
        current_early_bootstrap=paired_boot(current_early,choice),
        additional_verified_2026_gws=sorted(map(int,live.gw.unique())),
        full_2026_walkforward=window_scores(live),
        future_2026_27=projection,
        data_notes=['2025 season uses same FotMob team xG for all historic models',
                    '2026 season uses FPL player-xG team sums and independently verified official team scores',
                    '2026 sample only GW3-5, so current-season evidence is short',
                    'GW22-38 2025 held out from configuration selection',
                    'Fitting to actual goals is not a new player PM, TS or chip replay'],
        promotion_allowed=False)
    out=WORK/'experimental_early_season_goal_calibration.json'
    out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps(results,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    for key in ['selected_on_dev_only','dev_gw3_12','validation_gw13_21',
                'untouched_holdout_gw22_38','early_gw3_5_2025','early_gw3_5_2026',
                'current_early_high_original_ge2','future_2026_27',
                'validation_bootstrap','holdout_bootstrap','current_early_bootstrap']:
        print('EARLY_CAL_'+key.upper(),json.dumps(results[key],ensure_ascii=False))
if __name__=='__main__':main()

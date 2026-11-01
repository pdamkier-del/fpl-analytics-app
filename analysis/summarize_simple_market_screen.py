"""Summarize fixed offline screen; never selects or activates live parameters."""
import json
from pathlib import Path
import numpy as np
import pandas as pd
from scipy.stats import poisson

OUT=Path(__file__).resolve().parents[1]/'analysis/results/simple-market-model-20261025'


def main():
    team=pd.read_csv(OUT/'team-markets.csv');metrics=[]
    for season,g in team.groupby('season'):
        y=np.r_[g.actual_home,g.actual_away]
        for arm in ['baseline','market']:
            mu=np.r_[g.baseline_home,g.baseline_away] if arm=='baseline' else np.r_[g.home,g.away]
            metrics.append(dict(season=season,arm=arm,team_rows=len(y),goal_mae=float(abs(mu-y).mean()),goal_bias=float((mu-y).mean()),poisson_log_loss=float(-poisson.logpmf(y,mu).mean()),clean_sheet_brier=float(((np.exp(-mu)-(y==0))**2).mean())))
    pd.DataFrame(metrics).to_csv(OUT/'team-metrics.csv',index=False)
    m=pd.read_csv(OUT/'metrics.csv');checks=[]
    for arm,a in m[(m.cohort=='all')&(m.arm!='archived_B')].groupby('arm'):
        per=[]
        for r in a.itertuples():
            b=m[(m.season==r.season)&(m.cohort=='all')&(m.arm=='archived_B')].iloc[0]
            per.append(dict(season=r.season,minute_mae_delta=r.minute_mae-b.minute_mae,xp_mae_delta=r.xp_mae-b.xp_mae,minute_bias_delta=r.minute_bias-b.minute_bias,xp_bias_delta=r.xp_bias-b.xp_bias))
        passes=all(r['minute_mae_delta']<=.05 and r['xp_mae_delta']<=.005 for r in per) and any(r['minute_mae_delta']<0 or r['xp_mae_delta']<0 for r in per)
        checks.append(dict(arm=arm,numerical_screen_passed=bool(passes),seasons=per,eligible_for_activation=False))
    pred=pd.read_csv(OUT/'predictions.csv.gz');incremental=[];rng=np.random.default_rng(20261025)
    for season,g in pred.groupby('season'):
        a=g[g.arm=='market_PM_frozen_MM'];b=g[g.arm=='analytic_PM_frozen_MM']
        paired=a.merge(b,on=['fixture_uuid','player_uuid'],validate='one_to_one',suffixes=('','_b'))
        paired['delta']=abs(paired.xp-paired.total_points)-abs(paired.xp_b-paired.total_points)
        agg=paired.groupby('fixture_uuid').delta.agg(['sum','count']).to_numpy()
        ix=rng.integers(0,len(agg),(1000,len(agg)));r=agg[ix].sum(axis=1)
        incremental.append(dict(season=season,comparison='market minus analytic, frozen MM',xp_mae_delta=float(paired.delta.mean()),ci95=np.quantile(r[:,0]/r[:,1],[.025,.975]).tolist()))
    decision=json.loads((OUT/'decision.json').read_text());decision['numerical_checks']=checks;decision['market_incremental_bootstrap']=incremental
    (OUT/'decision.json').write_text(json.dumps(decision,indent=2)+'\n')
    print(pd.DataFrame(metrics).to_string(index=False));print(json.dumps(checks,indent=2))

if __name__=='__main__':main()

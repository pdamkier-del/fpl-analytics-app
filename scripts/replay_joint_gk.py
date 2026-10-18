#!/usr/bin/env python3
"""Matched, past-only GK replay; reused 2025/26 period is NOT independent OOS."""
from pathlib import Path
import json
import numpy as np
import pandas as pd
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import LogisticRegression
from individual_mm_evidence import load_frame
from build_current_b_inputs import historical_B_training
from research_individual_mm_refinement import design
from run_vfinal_integrated import build_final_frame
from mm_locked_bridge import attach_mm,locked_sampler_expectation
from gk_joint_bridge import observations
from run_joint_gk_preview import run,write,ROOT


def main():
    out=ROOT/'work/joint-gk-historical';out.mkdir(exist_ok=True)
    pm=build_final_frame();pm['season']='2025-26';pm=pm[pm.gw.between(22,38)].copy()
    frozen=load_frame(ROOT/'analysis/results/individual-mm-refinement-20261016/predictions.npz')
    b=frozen[frozen.season.eq('2025-26')&frozen['mode'].eq('B')&frozen.gw.between(22,38)].copy()
    key=['fixture_uuid','player_uuid']
    b=b.merge(pm[key+(['pos']if 'pos'not in b else[])],on=key,validate='one_to_one')
    history=historical_B_training()
    clocks=pd.to_datetime(history.known_at,utc=True,format='mixed')
    raw=history.set_index(['season']+key)
    b['unprojected_p']=b.p
    for cut,ix in b.groupby('cutoff',sort=True).groups.items():
        train=history[clocks.lt(pd.Timestamp(cut))&history.p.gt(0)&history.p.lt(1)]
        target=raw.loc[pd.MultiIndex.from_frame(b.loc[ix,['season']+key])].reset_index()
        model=make_pipeline(StandardScaler(),LogisticRegression(C=.1,max_iter=3000,tol=1e-8))
        model.fit(design(train),train.y)
        if model[-1].n_iter_[0]>=3000:raise ValueError('Historical calibration did not converge')
        prob=model.predict_proba(design(target))[:,1]
        b.loc[ix,'unprojected_p']=prob
        print('Past-only GK replay origin',cut,'training rows',len(train),flush=True)
    joined=attach_mm(pm,b)
    xp,details,audit,base=run(joined,b,observations(ROOT),season='2025-26',paired=True)
    pred=[]
    truth=b.set_index(key)
    basex=base.set_index(key)
    for r in xp.itertuples():
        k=(r.fixture_uuid,r.player_uuid)
        if k not in details:continue
        actual=truth.loc[k];before=basex.loc[k];new=details[k]
        pred.append(dict(fixture_uuid=k[0],player_uuid=k[1],gw=int(actual.gw),actual_start=float(actual.y),actual_minutes=float(actual.minutes),
            before_p=float(actual.p),after_p=new['p'],before_minutes=float(locked_sampler_expectation(actual.p,actual.q,actual.s,actual.c)),before_sampled_minutes=before.minutes,after_minutes=new['x'],before_xp=before.xpts,after_xp=r.xpts_fixture))
    result=pd.DataFrame(pred)
    import sqlite3
    with sqlite3.connect(f'file:{ROOT/"work/core.sqlite3"}?mode=ro',uri=True)as db:
        points=pd.read_sql_query("SELECT fixture_uuid,player_uuid,total_points FROM player_fixture_observations WHERE season='2025-26' AND is_final=1",db)
    result=result.merge(points,on=key,validate='one_to_one')
    if len(result)!=len(details):raise ValueError('Historical GK cohort or actuals are missing')
    metrics={}
    for arm in ['before','after']:
        e=result[arm+'_xp']-result.total_points
        metrics[arm]=dict(rows=len(result),start_brier=float(((result[arm+'_p']-result.actual_start)**2).mean()),
            minute_mae=float(abs(result[arm+'_minutes']-result.actual_minutes).mean()),
            xp_mae=float(abs(e).mean()),xp_bias=float(e.mean()))
    result.to_csv(out/'paired-gk.csv.gz',index=False,compression={'method':'gzip','mtime':0})
    result.assign(error=abs(result.after_xp-result.total_points)).nlargest(20,'error').to_csv(out/'failure-cases.csv',index=False)
    write(out/'summary.json',dict(scope='past-only matched replay on reused research period; not independent certification',season='2025-26',gws=list(range(22,39)),
        fixtures=int(result.fixture_uuid.nunique()),metrics=metrics,team_fixtures=len(audit),all_team_gk_minutes_90=all(abs(a['analytic_gk_minutes']-90)<1e-8 for a in audit),
        minute_metric_basis='analytic expectation for both arms; xP uses paired400-draw budgets',baseline='same B MM through original locked PM sampler',candidate='B-GK-joint-empirical-v1 plus dependent joint XI starts',production_changed=False,
        source_clock_limitation='Historical outcomes known-at inherits kickoff+3h proxy; strict news cutoffs preserved; this period was previously used for research'))
    print(json.dumps(metrics,indent=2),flush=True)
if __name__=='__main__':main()

#!/usr/bin/env python3
"""Read-only MM error distribution and exact-XI audit of PR #9 predictions."""
from pathlib import Path
import json
import numpy as np
import pandas as pd
from individual_mm_evidence import load_frame

ROOT=Path(__file__).resolve().parents[1]
SOURCE=ROOT/'analysis/results/individual-mm-refinement-20261016/predictions.npz'
OUT=ROOT/'analysis/results/mm-error-xi-audit-20261016'
ARMS=['original','best_existing','B']
KEY=['season','fixture_uuid','player_uuid']
BINS=[-1e-9,5,15,30,60,np.inf]
LABELS=['0-5','5-15','15-30','30-60','over-60']

def main():
    if not SOURCE.exists():raise SystemExit('Missing original PR9 prediction capsule: '+str(SOURCE))
    OUT.mkdir(parents=True,exist_ok=True)
    all_rows=load_frame(SOURCE)
    needed=KEY+['team_id','gw','mode','p','x','y','minutes']
    missing=set(needed)-set(all_rows)
    if missing:raise ValueError('Missing prediction columns: '+str(sorted(missing)))
    all_rows=all_rows[all_rows['mode'].isin(ARMS)].copy()
    all_rows=all_rows[((all_rows.season=='2024-25')&(all_rows.gw>=22))|((all_rows.season=='2025-26')&(all_rows.gw>=6))]
    if all_rows.duplicated(KEY+['mode']).any():raise ValueError('Duplicate predictions per model/player/fixture')
    for mode in ARMS:
        group=all_rows[all_rows['mode']==mode]
        if group.shape[0]!=39264:raise ValueError(f'{mode} has {len(group)} rows, expected 39264')
    truth=all_rows[all_rows['mode']=='B'][KEY+['team_id','gw','y','minutes']]
    for mode in ['original','best_existing']:
        left=all_rows[all_rows['mode']==mode].merge(truth,on=KEY,suffixes=('','_B'),validate='one_to_one')
        if len(left)!=len(truth) or not (left.team_id==left.team_id_B).all() or not (left.y==left.y_B).all() or not np.allclose(left.minutes,left.minutes_B):raise ValueError('Unequal shared truth for '+mode)
    all_rows['error']=all_rows.x-all_rows.minutes
    all_rows['ae']=all_rows.error.abs()
    all_rows['error_band']=pd.cut(all_rows.ae,BINS,labels=LABELS,include_lowest=True,right=True)
    rows=[]
    for (mode,season),g in all_rows.groupby(['mode','season'],sort=True):
        for label in LABELS:
            subset=g[g.error_band==label]
            rows.append(dict(mode=mode,season=season,band=label,count=len(subset),percent=100*len(subset)/len(g),error_share_percent=100*subset.ae.sum()/g.ae.sum()))
    for mode,g in all_rows.groupby('mode'):
        for label in LABELS:
            subset=g[g.error_band==label]
            rows.append(dict(mode=mode,season='pooled',band=label,count=len(subset),percent=100*len(subset)/len(g),error_share_percent=100*subset.ae.sum()/g.ae.sum()))
    pd.DataFrame(rows).to_csv(OUT/'error_bands.csv',index=False,float_format='%.8f')
    summary=[]
    for (mode,season),g in all_rows.groupby(['mode','season']):
        a=np.sort(g.ae.to_numpy())
        n=len(a)
        summary.append(dict(mode=mode,season=season,count=n,mae=g.ae.mean(),rmse=np.sqrt((g.error**2).mean()),median=np.median(a),p90=np.quantile(a,.9),p95=np.quantile(a,.95),p99=np.quantile(a,.99),error_share_top5=100*a[int(np.floor(.95*n)):].sum()/a.sum(),error_share_top10=100*a[int(np.floor(.90*n)):].sum()/a.sum()))
    pd.DataFrame(summary).to_csv(OUT/'tail_summary.csv',index=False,float_format='%.8f')
    # Full-XI accuracy: only groups with 11 observed starters and complete, consistent team-fixture coverage.
    # Rank GK and outfield separately, but no tactical formation is asserted.
    xi=[]
    for (mode,season,fixture,team),g in all_rows.groupby(['mode','season','fixture_uuid','team_id'],sort=True):
        total_true=int(g.y.sum())
        if total_true!=11:
            xi.append(dict(mode=mode,season=season,fixture_uuid=fixture,team_id=team,gw=int(g.gw.iloc[0]),eligible=False,reason='not_11_observed_starters',correct=np.nan))
            continue
        # A separately identified goalkeeper position is not stored in the PR9 prediction capsule.
        # Therefore top-11 p is an explicitly UNCONSTRAINED XI selection diagnostic.
        if len(g)<11 or g.p.isna().any():
            xi.append(dict(mode=mode,season=season,fixture_uuid=fixture,team_id=team,gw=int(g.gw.iloc[0]),eligible=False,reason='incomplete_or_missing_probs',correct=np.nan))
            continue
        selected=g.sort_values(['p','player_uuid'],ascending=[False,True]).head(11)
        correct=int(selected.y.sum())
        xi.append(dict(mode=mode,season=season,fixture_uuid=fixture,team_id=team,gw=int(g.gw.iloc[0]),eligible=True,reason='unconstrained_top11',correct=correct))
    xi=pd.DataFrame(xi)
    # Require identical eligible fixture-team keys for fair model comparisons.
    pivot=xi.pivot_table(index=['season','fixture_uuid','team_id'],columns='mode',values='eligible',aggfunc='first')
    shared=pivot[ARMS].fillna(False).all(axis=1)
    keys=shared[shared].index.to_frame(index=False)
    filtered=xi.merge(keys,on=['season','fixture_uuid','team_id'],validate='many_to_one')
    filtered.to_csv(OUT/'xi_per_team_fixture.csv',index=False)
    xi_summary=filtered.groupby(['mode','season','correct']).size().rename('count').reset_index()
    pooled=filtered.groupby(['mode','correct']).size().rename('count').reset_index().assign(season='pooled')
    xi_summary=pd.concat([xi_summary,pooled],ignore_index=True)
    denominators=filtered.groupby(['mode','season']).size().rename('total').reset_index()
    xi_summary=xi_summary.merge(denominators,on=['mode','season'])
    xi_summary['percent']=100*xi_summary['count']/xi_summary['total']
    xi_summary.to_csv(OUT/'xi_accuracy.csv',index=False,float_format='%.8f')
    clubs=filtered.groupby(['mode','season','team_id']).agg(matches=('correct','size'),avg_correct=('correct','mean'),exact_11_rate=('correct',lambda x:100*(x==11).mean()),at_least_10_rate=('correct',lambda x:100*(x>=10).mean())).reset_index()
    clubs.to_csv(OUT/'xi_clubs.csv',index=False,float_format='%.8f')
    # Actual vs predicted start classification; diagnostic includes all players, not just XI selections.
    all_rows['start_decision']=all_rows.p.ge(.5)
    all_rows['start_correct']=all_rows.start_decision.eq(all_rows.y.eq(1))
    all_rows.groupby(['mode','season']).agg(player_starts=('start_correct','size'),threshold_start_accuracy=('start_correct','mean')).reset_index().to_csv(OUT/'start_threshold_accuracy.csv',index=False)
    # Top B errors with identical best/original predictions and no inferred medical cause.
    columns=KEY+['team_id','gw','minutes','y','x','p','error','ae']
    merged=all_rows[all_rows['mode']=='B'][columns].rename(columns={'x':'B_x','p':'B_p','error':'B_error','ae':'B_ae'})
    for mode in ['original','best_existing']:
        t=all_rows[all_rows['mode']==mode][KEY+['x','p','ae']].rename(columns={'x':mode+'_x','p':mode+'_p','ae':mode+'_ae'})
        merged=merged.merge(t,on=KEY,validate='one_to_one')
    merged['B_delta_vs_best']=merged.B_ae-merged.best_existing_ae
    merged.sort_values(['B_ae','season','fixture_uuid','player_uuid'],ascending=[False,True,True,True]).head(100).to_csv(OUT/'top_100_B_errors.csv',index=False,float_format='%.8f')
    problems=merged.assign(worse_B=merged.B_delta_vs_best>1e-9,better_B=merged.B_delta_vs_best< -1e-9)
    problems.groupby(['season','team_id']).agg(rows=('B_ae','size'),B_mae=('B_ae','mean'),best_mae=('best_existing_ae','mean'),improved_rows=('better_B','sum'),worsened_rows=('worse_B','sum')).reset_index().to_csv(OUT/'club_error_summary.csv',index=False)
    report=dict(evaluation_player_fixtures_per_arm=39264,arms=ARMS,xi_definition='11 highest individual p, UNCONSTRAINED; not legal 1 GK + 10 outfield and not tactical formation',xi_shared_eligible_team_fixtures=len(keys),xi_total_group_records=len(xi),xi_missing_reason_counts=xi[~xi.eligible].groupby(['mode','reason']).size().to_dict().__str__(),note='Read-only retrospective audit using frozen PR9 predictions; not independent holdout or prospective validated data')
    (OUT/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2))
    print('\nPOOLED ERROR DISTRIBUTION');print(pd.DataFrame(rows).query("season == 'pooled'").to_string(index=False))
    print('\nPOOLED XI DISTRIBUTION');print(xi_summary.query("season == 'pooled'").to_string(index=False))
if __name__=='__main__':main()

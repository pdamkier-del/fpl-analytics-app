#!/usr/bin/env python3
"""PR9/PR11 MM-only role-stratified error audit. Purely retrospective; no refitting."""
from pathlib import Path
import json
import numpy as np
import pandas as pd
from individual_mm_evidence import load_frame

ROOT=Path(__file__).resolve().parents[1]
SRC=ROOT/'analysis/results/individual-mm-refinement-20261016/predictions.npz'
OUT=ROOT/'analysis/results/mm-role-uncertainty-20261017'
MODES=['original','best_existing','B']
KEY=['season','fixture_uuid','player_uuid']
BINS=[-1e-9,5,15,30,60,np.inf]
NAMES=['0-5','5-15','15-30','30-60','over-60']
def run():
    OUT.mkdir(parents=True,exist_ok=True)
    f=load_frame(SRC)
    f=f[f['mode'].isin(MODES)&(((f.season=='2024-25')&(f.gw>=22))|((f.season=='2025-26')&(f.gw>=6)))].copy()
    needed=set(KEY+['team_id','mode','p','q','s','c','x','y','minutes','prior_type','news_state'])
    if needed-set(f):raise ValueError('Missing needed columns: '+str(needed-set(f)))
    if f.duplicated(KEY+['mode']).any():raise ValueError('Duplicate forecasts')
    f['role']=f.prior_type.fillna('UNKNOWN').replace({'rotation_or_short_history':'rotation_or_short_history'})
    f['absolute_error']=(f.x-f.minutes).abs()
    f['error_band']=pd.cut(f.absolute_error,BINS,labels=NAMES)
    f['wrong_high_confidence_start']=((f.p>=.8)&(f.y==0))|((f.p<=.2)&(f.y==1))
    f['start_mismatch_at_50pct']=(f.p>=.5).ne(f.y==1)
    f['large_error']=f.absolute_error>30
    f['catastrophic_error']=f.absolute_error>60
    f['actual_state']=np.select([f.y.eq(1),f.minutes.gt(0)],['started','cameo'],default='did_not_play')
    # Prior role is assigned BEFORE target; do not define groups from target outcome.
    groups=[]
    for (mode,season,role),g in f.groupby(['mode','season','role'],sort=True):
        n=len(g);total=g.absolute_error.sum()
        row=dict(mode=mode,season=season,role=role,n=n,mae=g.absolute_error.mean(),rmse=np.sqrt(np.mean((g.x-g.minutes)**2)),median=g.absolute_error.median(),p90=g.absolute_error.quantile(.9),p95=g.absolute_error.quantile(.95),p99=g.absolute_error.quantile(.99),start_brier=np.mean((g.p-g.y)**2),large_count=int(g.large_error.sum()),large_percent=100*g.large_error.mean(),catastrophic_count=int(g.catastrophic_error.sum()),catastrophic_percent=100*g.catastrophic_error.mean(),absolute_error_sum=total,large_error_share=100*g.loc[g.large_error,'absolute_error'].sum()/total if total else 0,catastrophic_error_share=100*g.loc[g.catastrophic_error,'absolute_error'].sum()/total if total else 0,wrong_high_confidence_starts=int(g.wrong_high_confidence_start.sum()),wrong_high_confidence_start_pct=100*g.wrong_high_confidence_start.mean(),start_rate=g.y.mean(),mean_p=g.p.mean())
        groups.append(row)
    pd.DataFrame(groups).to_csv(OUT/'role_error_summary.csv',index=False,float_format='%.8f')
    bands=f.groupby(['mode','season','role','error_band'],observed=False).agg(n=('absolute_error','size'),error_sum=('absolute_error','sum')).reset_index()
    bands.to_csv(OUT/'role_error_bands.csv',index=False)
    states=f.groupby(['mode','season','role','actual_state']).agg(n=('absolute_error','size'),mae=('absolute_error','mean'),error_sum=('absolute_error','sum'),mean_predicted_minutes=('x','mean'),mean_actual_minutes=('minutes','mean')).reset_index()
    states.to_csv(OUT/'role_actual_state.csv',index=False)
    # Calibration: A probabilistic model is judged across similarly predicted cohorts,
    # not by whether any specific 50/50 choice happened to start.
    f['p_bin']=pd.cut(f.p,[-1e-10,.1,.2,.3,.4,.5,.6,.7,.8,.9,1.+1e-10],include_lowest=True)
    f.groupby(['mode','role','p_bin'],observed=False).agg(n=('y','size'),forecast_start_rate=('p','mean'),observed_start_rate=('y','mean'),start_brier=('p',lambda x:np.nan)).reset_index().drop(columns='start_brier').to_csv(OUT/'role_calibration.csv',index=False)
    # Pairwise improvements with frozen common identity and identical truth.
    comparison=f.pivot(index=KEY,columns='mode',values='absolute_error')
    if len(comparison)!=39264 or comparison.isna().any().any():raise ValueError('Unmatched historical evaluation')
    facts=f[f['mode']=='B'][KEY+['team_id','gw','role','news_state','p','y','minutes','x','s','q','c']].copy()
    facts=facts.merge(comparison.reset_index(),on=KEY,validate='one_to_one')
    facts['B_minus_best']=facts.B-facts.best_existing
    facts['B_minus_original']=facts.B-facts.original
    facts['extreme_start_uncertainty']=facts.p.between(.3,.7,inclusive='both')
    facts['high_confidence']=((facts.p>=.8)|(facts.p<=.2))
    facts.sort_values(['B','season','fixture_uuid'],ascending=[False,True,True]).head(200).to_csv(OUT/'top200_B_errors_by_role.csv',index=False)
    facts.groupby(['season','role']).agg(n=('B','size'),B_mae=('B','mean'),previous_mae=('best_existing','mean'),improved_rows=('B_minus_best',lambda x:int((x<0).sum())),worsened_rows=('B_minus_best',lambda x:int((x>0).sum())),n_above_60=('B',lambda x:int((x>60).sum())),n_30_70_start_chance=('extreme_start_uncertainty','sum'),n_high_confidence=('high_confidence','sum')).reset_index().to_csv(OUT/'role_comparisons.csv',index=False)
    facts.groupby(['season','team_id','role']).agg(n=('B','size'),B_mae=('B','mean'),previous_mae=('best_existing','mean'),n_above_60=('B',lambda x:int((x>60).sum()))).reset_index().to_csv(OUT/'club_role_errors.csv',index=False)
    # Player identity counts do not establish cause; show repeat outliers.
    facts.groupby(['season','team_id','player_uuid','role']).agg(n=('B','size'),B_mae=('B','mean'),large_n=('B',lambda x:int((x>30).sum())),catastrophic_n=('B',lambda x:int((x>60).sum())),mean_start_probability=('p','mean'),actual_starts=('y','sum')).reset_index().sort_values(['catastrophic_n','large_n','B_mae'],ascending=False).to_csv(OUT/'repeat_player_outliers.csv',index=False)
    summary=dict(evaluation_player_fixtures=39264,role_definition='pre-target prior_type from frozen PR9, not final realized minutes',method='posthoc error and start-calibration diagnosis; uncertainty is quantified as conditional empirical errors, not a fitted predictive-minute interval',warning='Unknown health and lineup shocks not labelled avoidable; role uncertainty cannot excuse poor probabilistic calibration',inputs=str(SRC.relative_to(ROOT)),production_unchanged=True)
    (OUT/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
    print(pd.read_csv(OUT/'role_error_summary.csv').query("mode == 'B'").to_string(index=False))
if __name__=='__main__':run()

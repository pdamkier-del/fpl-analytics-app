#!/usr/bin/env python3
"""Posthoc error analysis; no refitting, reselection, or forecast mutation."""
import json,sys
from pathlib import Path
import numpy as np,pandas as pd
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT/'scripts'),str(ROOT/'src')]
from individual_mm_validation import save
from experiment_mm_pm import POINT_COMPONENTS,score
OUT=ROOT/'analysis/results/individual-mm-20261015'

def diagnostics(season):
    f=pd.read_csv(OUT/f'{season}_candidates.csv.gz',usecols=['mode','fixture_uuid','player_uuid','player_type','team_news_state'],low_memory=False)
    f=f[f['mode'].eq('original')].drop(columns='mode')
    p=pd.read_csv(OUT/f'{season}_pm_predictions.csv.gz',low_memory=False)
    if not {'player_type','team_news_state'}.issubset(p):
        p=p.merge(f,on=['fixture_uuid','player_uuid'],how='left',validate='many_to_one')
    p['player_type']=p.player_type.fillna('unknown_prior_group');p['team_news_state']=p.team_news_state.fillna('UNKNOWN')
    if season=='2024-25':p=p[p.gw.ge(22)]
    result={}
    for mode,g in p.groupby('mode'):
        ref=p[p['mode'].eq('control_MM__'+mode.split('__',1)[1])]
        means={k:float(g[k].mean()-ref[k].mean()) for k in POINT_COMPONENTS}
        bins=pd.cut(g.xp,[-np.inf,0,1,2,3,4,5,6,8,np.inf])
        result[mode]=dict(rows=len(g),played=score(g[g.minutes.gt(0)]),prior_roles={str(k):score(v) for k,v in g.groupby('player_type')},news_states={str(k):score(v) for k,v in g.groupby('team_news_state')},component_delta_vs_logistic=means,xp_reliability=[dict(bin=str(k),rows=len(v),mean_pred=float(v.xp.mean()),mean_actual=float(v.total_points.mean())) for k,v in g.groupby(bins,observed=True)])
    return dict(results=result,classification='POSTHOC_DIAGNOSTICS_NO_MODEL_SELECTION',verified_medical_return_group='Not Available: no verified medical labels',locked_model_active=False)

if __name__=='__main__':
    for season in ['2024-25','2025-26']:
        if (OUT/f'{season}_pm_predictions.csv.gz').exists():save(OUT/f'{season}_pm_diagnostics.json',diagnostics(season))

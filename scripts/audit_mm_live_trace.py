#!/usr/bin/env python3
"""Trace current locked P(start) stages; fit unchanged models, never publish."""
import json,sys
from pathlib import Path
import numpy as np,pandas as pd
from scipy.special import expit,logit
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import LogisticRegression
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT/'src'),str(ROOT/'scripts')]
from run_mm_unified_official_roles import BASE_FEATURES,ROLE_FEATURES,WORKLOAD_FEATURES,full_mm
from run_mm_v2_team_news_availability_experiment import policy_caps,RATING_CFG,L2
from run_locked_mm_gw6_38 import POLICY
from run_mm_v2_relative_rating_competition import add_relative_xi_features
from run_mm_v2_xi_rating_experiment import ASSIGN_FEATURES,fit_residual
from fpl_v1_1_model.availability_projection import project_exact_starters_with_caps
from build_reproducible_role_benchmark import normalize_eleven
from audit_mm_components import prefix_features,load_obs
from fpl_v1_1_model.experimental_mm_research import fit_start,survival_prediction

def main():
    base=ROOT/'data_v1_1/derived/live_locked_inputs/2026-27-v1';out=ROOT/'analysis/results/mm-research-20261014'
    history=pd.read_csv(base/'reconstructed_training_features.csv.gz',low_memory=False);target=pd.read_csv(base/'v2_baseline_feature_matrix.csv.gz',low_memory=False)
    cutoff=pd.to_datetime(target.cutoff,utc=True).min()
    if not (pd.to_datetime(history.outcome_known_at,utc=True)<cutoff).all():raise ValueError('Future training outcome')
    target['y']=0;target['minutes']=0.;target['outcome_known_at']='2100-01-01T00:00:00Z'
    future=target.target_gw.ne(target.gw);target.loc[future,'team_news_state']='UNKNOWN';target.loc[future,'team_news_scoped_chance']=np.nan
    f=pd.concat([history,target],ignore_index=True);train=np.arange(len(f))<len(history)
    columns=BASE_FEATURES+ROLE_FEATURES+WORKLOAD_FEATURES
    m=make_pipeline(StandardScaler(),LogisticRegression(C=1.,max_iter=2000,random_state=0));m.fit(f.loc[train,columns],f.loc[train,'y']);base_raw=m.predict_proba(f[columns])[:,1];p0=normalize_eleven(f,base_raw)
    p,q,c,x,_=full_mm(f.copy(),train);caps=policy_caps(f,POLICY);pre=project_exact_starters_with_caps(f,p,caps);feat=add_relative_xi_features(f,pre,RATING_CFG);residual,model=fit_residual(feat,pre,train,ASSIGN_FEATURES,L2);final=project_exact_starters_with_caps(feat,residual,caps)
    raw_x=np.clip(feat[ASSIGN_FEATURES].to_numpy(float),-50,50);z=(raw_x-np.array(model['mean']))/np.array(model['scale']);contrib=z*np.array(model['coef']);xi_raw=expit(logit(np.clip(pre,1e-8,1-1e-8))+contrib.sum(axis=1))
    original=pd.read_csv(base/'vfinal_live_full_simulator_input.csv.gz',low_memory=False);rows=[]
    for pid in [411,12]:
        indices=np.flatnonzero((f.get('fpl_element',pd.Series(index=f.index,dtype=float)).eq(pid)&f.get('target_gw',pd.Series(index=f.index,dtype=float)).eq(7)).to_numpy());i=int(indices[0]);r=original[original.fpl_element.eq(pid)&original.target_gw.eq(7)].iloc[0]
        if abs(final[i]-r.p_start)>1e-10:raise ValueError('Current stage trace differs from locked forecast')
        rows.append(dict(player=r.player,frozen_v2_normalized_prior=float(expit(f.base_logit.iloc[i])),role_workload_raw=float(base_raw[i]),role_workload_normalized=float(p0[i]),performance_normalized=float(p[i]),availability_projected=float(pre[i]),xi_residual_raw=float(xi_raw[i]),xi_residual_normalized=float(residual[i]),final=float(final[i]),xi_logit_contributions=dict(zip(ASSIGN_FEATURES,map(float,contrib[i]))),start_duration=float(r.start_minutes_mean),sub_probability=float(q[i]),sub_duration=float(c[i]),mm_xmins=float(r.xmins)))
    # Candidate focus remains diagnostic, evaluated on the same historical snapshot.
    current=original[original.target_gw.eq(7)].copy();current['new_p_start']=current.p_start;current['new_start_minutes']=current.start_minutes_mean;current['new_q_sub']=current.mm_q_sub;current['new_sub_minutes']=current.mm_sub_minutes
    hist=pd.read_csv(base/'player_fixture_observations.csv.gz');hist['known']=pd.to_datetime(hist.available_at,utc=True)
    current=prefix_features(current,hist)
    previous=pd.concat([pd.read_csv(out/f'{s}_features.csv.gz') for s in ['2024-25','2025-26']],ignore_index=True)
    sel=json.loads((out/'selection.json').read_text());name=sel['selected_start'];reg=float(name.rsplit('_',1)[1]);pp=fit_start(previous,current,C=reg,hierarchical=name.startswith('hierarchical'))
    pools=[]
    for season,hours in [('2024-25',4),('2025-26',3)]:
        ob=load_obs(ROOT/'work/core.sqlite3',season,hours).rename(columns={'fpl_position':'pos'});pools.append(ob)
    pools.append(hist.rename(columns={'fpl_position':'pos'}));pool=pd.concat(pools,ignore_index=True);pool['pos']=pool.pos.replace({'GKP':'GK'})
    duration=sel['selected_duration']
    if duration.startswith('survival_'):
        _,half,strength=duration.split('_');ss=survival_prediction(current,hist,pool[pool.started.eq(1)],half_days=float(half),strength=float(strength))
    else:ss=current['duration_h'+duration[-1]].to_numpy()
    for pid in [411,12]:
        i=int(np.flatnonzero(current.fpl_element.eq(pid))[0]);r=current.iloc[i];q=float(r.new_q_sub);c=float(r.new_sub_minutes)
        rows[[x['player'] for x in rows].index(r.player)]['candidate_focus']=dict(selected_start=name,selected_duration=duration,p_start=float(pp[i]),start_duration=float(ss[i]),combined_xmins=float(pp[i]*ss[i]+(1-pp[i])*q*c),duration_only_xmins=float(r.new_p_start*ss[i]+(1-r.new_p_start)*q*c),start_only_xmins=float(pp[i]*r.new_start_minutes+(1-pp[i])*q*c),xp='Not Available: focus candidates need full current PM component rebuild, not a substituted minute label')
    report=dict(classification='UNCHANGED_CURRENT_MM_STAGE_TRACE_AND_SHADOW_COMPONENTS',cutoff=str(cutoff),rows=rows,locked_model_active=False,promotion_allowed=False,interpretation='Sequential fitted transformations; stage differences and coefficient contributions are not causal effects')
    (out/'live_trace.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
if __name__=='__main__':main()

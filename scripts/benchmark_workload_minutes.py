#!/usr/bin/env python3
"""Frozen workload experiment: development GW6-15/16-21, reused GW22-38.

Start selection uses development log-loss. Expected-minutes candidates use
development RMSE, with MAE/calibration reported alongside it. This protocol
change is explicit: a conditional mean forecast serves expected points, rather
than targeting the zero-heavy conditional median solely for MAE.
"""
import argparse
import json
from pathlib import Path
import sys
import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression, Ridge
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from fpl_v1_1_model.workload import WORKLOAD_FEATURES
from fpl_v1_1_model.minutes_decomposition import component_inputs,compose_expected_minutes
from fpl_v1_1_model.frozen_forecast import predict_frozen
from build_reproducible_role_benchmark import BASE_FEATURES,ROLE_FEATURES,normalize_eleven,score,write_json,write_prediction_csv,sha
from benchmark_squad_minutes import serialize

VARIANTS=['role_control','workload_start','role_decomposition','workload_decomposition','pl_only_start']


def evaluate(frame,train,test):
    cutoff=pd.to_datetime(frame.loc[test,'cutoff'],utc=True).min()
    assert (pd.to_datetime(frame.loc[train,'outcome_known_at'],utc=True)<cutoff).all()
    assert not (train&test).any()
    role_columns=BASE_FEATURES+ROLE_FEATURES
    starts={};models={}
    for name,columns in [('role',role_columns),('workload',role_columns+WORKLOAD_FEATURES),
                         ('pl_only',role_columns+['pl_only_'+k for k in WORKLOAD_FEATURES])]:
        model=make_pipeline(StandardScaler(),LogisticRegression(C=1.,max_iter=2000,random_state=0))
        model.fit(frame.loc[train,columns],frame.loc[train,'y'])
        starts[name]=normalize_eleven(frame,model.predict_proba(frame[columns])[:,1])
        models[name+'_start_probability']=serialize(model,columns)
    X=component_inputs(frame);duration_predictions={}
    for name,x in [('role',X),('workload',pd.concat([X,frame[WORKLOAD_FEATURES]],axis=1))]:
        predictions={}
        masks={'start':train&(frame.y==1),'sub_probability':train&(frame.y==0),
               'sub_duration':train&(frame.y==0)&(frame.minutes>0)}
        for component,mask in masks.items():
            classifier=component=='sub_probability'
            model=make_pipeline(StandardScaler(),LogisticRegression(C=1.,max_iter=2000,random_state=0) if classifier else Ridge(alpha=20.))
            y=(frame.loc[mask,'minutes']>0).astype(int) if classifier else frame.loc[mask,'minutes']
            model.fit(x.loc[mask],y)
            predictions[component]=model.predict_proba(x)[:,1] if classifier else np.clip(model.predict(x),0,90)
            # serialize also supports one-dimensional Ridge coef_
            model_key=name+('_start_duration' if component=='start' else '_'+component)
            models[model_key]={'features':list(x.columns),'coefficients':np.ravel(model[-1].coef_).tolist(),
              'intercept':float(np.ravel(model[-1].intercept_)[0]),'scaler_mean':model[0].mean_.tolist(),'scaler_scale':model[0].scale_.tolist(),'training_rows':int(mask.sum())}
        duration_predictions[name]=predictions
    # The separate workload feature table plus immutable foundation preserves
    # all q/H and inputs; save actual model columns on these rows as well.
    idcols=['season','gw','fixture_uuid','player_uuid','team_id','team','player','pos','cutoff','expected_role','y','minutes','outcome_known_at','role_information_change','target_role_case_posthoc','work_max_history_known_at','work_all_competitions_complete']
    # Categorical inputs can be reconstructed exactly from pos/expected_role;
    # numeric component inputs are included by their explicit feature schema.
    from fpl_v1_1_model.minutes_decomposition import FEATURES
    cols=list(dict.fromkeys(idcols+role_columns+FEATURES+WORKLOAD_FEATURES+['pl_only_'+k for k in WORKLOAD_FEATURES]))
    f=frame.loc[test,cols].copy();idx=np.flatnonzero(test)
    for name in ('role','workload'):
        for comp,v in duration_predictions[name].items():f[name+'_'+comp]=v[idx]
    specifications={'role_control':('role',None),'workload_start':('workload',None),
                    'role_decomposition':('role','role'),'workload_decomposition':('workload','workload'),
                    'pl_only_start':('pl_only',None)}
    for variant,(start,duration) in specifications.items():
        p=starts[start][idx]
        terms=(f.start_minutes_mean,f.p_cameo_given_bench,f.cameo_minutes_mean) if duration is None else (f[duration+'_start'],f[duration+'_sub_probability'],f[duration+'_sub_duration'])
        f[variant+'_p_start']=p;f[variant+'_xmins']=compose_expected_minutes(p,*terms)
    metrics={name:{**score(f,name),'xmins_bias':float((f[name+'_xmins']-f.minutes).mean())} for name in VARIANTS}
    return f,metrics,models,{'training_rows':int(train.sum()),'evaluation_rows':len(f),'training_cutoff':cutoff.isoformat()}


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--features',default=str(ROOT/'analysis/results/workload-quality-v3/all_features.csv.gz'))
    ap.add_argument('--out',default=str(ROOT/'analysis/results/workload-quality-minutes-v3'))
    a=ap.parse_args();out=Path(a.out);out.mkdir(parents=True,exist_ok=True)
    # Written before any fits/evaluation, with fixed candidates/hyperparameters.
    protocol={'development_train':'GW6-15','development_validation':'GW16-21','final_train':'GW6-21',
      'final_evaluation':'GW22-38 reused diagnostic, NOT fresh independent OOS',
      'fixed_candidates':VARIANTS[:4],'diagnostic_ablation':'pl_only_start added to isolate observed cup/Europe information; excluded from selection',
      'start_objective':'development log-loss; control wins ties',
      'expected_minutes_objective':'development RMSE; control wins ties; MAE and mean bias also reported',
      'hyperparameters':{'logistic_C':1.,'Ridge_alpha':20.,'workload_half_life_days':[3,7]},
      'workload_coverage':'Observed PL + cup/Europe subset, FA Cup absent and lineup/stat gaps explicit; not full all-official-match coverage',
      'availability':'Authoritative FPL deadlines; completed-match availability remains kickoff+3h proxy',
      'deployment':'Experimental only; independent test and downstream xP validation required before app adoption'}
    write_json(out/'protocol.json',protocol)
    frame=pd.read_csv(a.features);known=pd.to_datetime(frame.outcome_known_at,utc=True)
    dev_test=frame.gw.between(16,21);dev_cutoff=pd.to_datetime(frame.loc[dev_test,'cutoff'],utc=True).min()
    dev_train=frame.gw.between(6,15)&(known<dev_cutoff)
    dev,dev_metrics,dev_models,dev_fit=evaluate(frame,dev_train,dev_test)
    start_selected=min(['role_control','workload_start'],key=lambda v:dev_metrics[v]['log_loss'])
    minutes_selected=min(VARIANTS[:4],key=lambda v:dev_metrics[v]['xmins_rmse'])
    protocol.update({'development_selected_start':start_selected,'development_selected_minutes':minutes_selected,'development_fit':dev_fit})
    test=frame.gw.between(22,38);cutoff=pd.to_datetime(frame.loc[test,'cutoff'],utc=True).min()
    train=frame.gw.between(6,21)&(known<cutoff)
    diagnostic,metrics,models,fit=evaluate(frame,train,test)
    protocol['final_fit']=fit
    clean=frame.loc[test].drop(columns=[c for c in frame if c.startswith('actual_') or c.endswith('_posthoc') or c in ('y','minutes','outcome_known_at')])
    inference=[]
    for variant in VARIANTS:
        predicted=predict_frozen(clean,models,fit['training_cutoff'],variant)
        dp=np.abs(predicted.p_start.to_numpy()-diagnostic[variant+'_p_start'].to_numpy())
        dm=np.abs(predicted.expected_minutes.to_numpy()-diagnostic[variant+'_xmins'].to_numpy())
        assert dp.max()<1e-10 and dm.max()<1e-9
        inference.append({'variant':variant,'rows':len(predicted),'max_start_error':float(dp.max()),'max_minutes_error':float(dm.max()),'outcome_columns_removed':True})
    write_json(out/'inference_verification.json',{'checks':inference,'status':'matches saved frozen predictions without outcome inputs'})
    write_prediction_csv(dev,out/'development_predictions.csv.gz');write_prediction_csv(diagnostic,out/'reused_holdout_diagnostic_predictions.csv.gz')
    for col in ['gw','team','expected_role','target_role_case_posthoc']:
        records=[]
        for label,g in diagnostic.groupby(col):
            for v in VARIANTS:records.append({col:label,'variant':v,**score(g,v)})
        pd.DataFrame(records).to_csv(out/f'metrics_by_{col}.csv',index=False)
    components={}
    for name in ('role','workload'):
        start=diagnostic.y==1;nonstart=diagnostic.y==0;sub=nonstart&(diagnostic.minutes>0)
        def duration(mask,col):
            e=diagnostic.loc[mask,col]-diagnostic.loc[mask,'minutes']
            return {'n':int(mask.sum()),'mae':float(abs(e).mean()),'rmse':float(np.sqrt((e**2).mean())),'bias':float(e.mean())}
        p=np.clip(diagnostic.loc[nonstart,name+'_sub_probability'],1e-9,1-1e-9)
        y=(diagnostic.loc[nonstart,'minutes']>0).astype(float)
        components[name]={'start_duration':duration(start,name+'_start'),'sub_duration':duration(sub,name+'_sub_duration'),
          'appearance_given_nonstart':{'n':int(nonstart.sum()),'brier':float(((p-y)**2).mean()),'log_loss':float(-(y*np.log(p)+(1-y)*np.log(1-p)).mean())}}
    write_json(out/'component_metrics.json',components)
    impact=[]
    for label,mask in [('role_change_at_least_5pp',diagnostic.role_information_change>=.05),
                       ('role_change_below_5pp',diagnostic.role_information_change<.05),
                       ('observed_nonpl_match_last_7d',diagnostic.work_team_nonpl_matches_7d>0),
                       ('no_observed_nonpl_match_last_7d',diagnostic.work_team_nonpl_matches_7d==0)]:
        for v in VARIANTS:impact.append({'group':label,'variant':v,**score(diagnostic.loc[mask],v)})
    pd.DataFrame(impact).to_csv(out/'metrics_by_cutoff_safe_groups.csv',index=False)
    write_json(out/'development_metrics.json',dev_metrics);write_json(out/'reused_holdout_metrics.json',metrics)
    write_json(out/'development_models.json',dev_models);write_json(out/'frozen_models.json',models);write_json(out/'protocol.json',protocol)
    inputs=[Path(a.features).resolve(),Path(a.features).resolve().parent/'coverage_audit.json']
    code=[Path(__file__),ROOT/'src/fpl_v1_1_model/workload.py',ROOT/'src/fpl_v1_1_model/minutes_decomposition.py',ROOT/'src/fpl_v1_1_model/frozen_forecast.py',ROOT/'scripts/predict_frozen_workload.py',ROOT/'scripts/build_reproducible_role_benchmark.py',ROOT/'scripts/benchmark_squad_minutes.py']
    write_json(out/'manifest.json',{'inputs':[{'path':str(p.relative_to(ROOT)),'sha256':sha(p)} for p in inputs],
      'code':[{'path':str(p.relative_to(ROOT)),'sha256':sha(p)} for p in code],
      'outputs':[{'path':p.name,'sha256':sha(p)} for p in sorted(out.iterdir()) if p.name!='manifest.json' and not p.name.endswith('.tmp')]})
    print(json.dumps({'development':dev_metrics,'selected_start':start_selected,'selected_minutes':minutes_selected,'reused_diagnostic':metrics},indent=2))


if __name__=='__main__':main()

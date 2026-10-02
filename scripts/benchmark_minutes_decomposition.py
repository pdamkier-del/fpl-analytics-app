#!/usr/bin/env python3
"""Isolate conditional-minutes changes with frozen role-aware P(start)."""
import argparse
import json
from pathlib import Path
import sys
import numpy as np
import pandas as pd

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from fpl_v1_1_model.minutes_decomposition import fit_components,compose_expected_minutes
from build_reproducible_role_benchmark import score,write_json,sha,write_prediction_csv


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--features',default=str(ROOT/'analysis/results/reproducible-role-v1/all_feature_predictions.csv.gz'))
    ap.add_argument('--out',default=str(ROOT/'analysis/results/minutes-decomposition-v1'))
    a=ap.parse_args();out=Path(a.out);out.mkdir(parents=True,exist_ok=True)
    frame=pd.read_csv(a.features)
    train=frame.evaluation_partition=='development_in_sample'
    test=frame.evaluation_partition=='frozen_oos'
    cutoff=pd.to_datetime(frame.loc[test,'cutoff'],utc=True).min()
    assert (pd.to_datetime(frame.loc[train,'outcome_known_at'],utc=True)<cutoff).all()
    predicted,models,counts=fit_components(frame,train)
    for name,values in predicted.items():frame[name]=values
    p=frame.role_aware_p_start
    variants={
      'new_start_duration':(frame.e_min_start,frame.p_cameo_given_bench,frame.cameo_minutes_mean),
      'new_sub_appearance':(frame.start_minutes_mean,frame.p_sub_not_start,frame.cameo_minutes_mean),
      'new_sub_duration':(frame.start_minutes_mean,frame.p_cameo_given_bench,frame.e_min_sub),
      'full_decomposition':(frame.e_min_start,frame.p_sub_not_start,frame.e_min_sub)}
    for name,terms in variants.items():
        frame[name+'_p_start']=p
        frame[name+'_xmins']=compose_expected_minutes(p,*terms)
    holdout=frame.loc[test].copy()
    holdout['actual_event_posthoc']=np.where(holdout.y==1,'start',np.where(holdout.minutes>0,'sub_appearance','no_appearance'))
    names=['baseline','role_aware',*variants]
    metrics={name:score(holdout,name) for name in names}
    for col in ['gw','team','expected_role','target_role_case_posthoc','actual_event_posthoc']:
        rows=[]
        for label,g in holdout.groupby(col,sort=True):
            for name in names:rows.append({col:label,'variant':name,**score(g,name)})
        pd.DataFrame(rows).to_csv(out/f'metrics_by_{col}.csv',index=False)
    for label,mask in [('prior_disagreement',holdout.history_disagreement_share>0),
                      ('no_prior_disagreement',holdout.history_disagreement_share==0),
                      ('role_change_at_least_5pp',holdout.role_information_change>=.05),
                      ('role_change_below_5pp',holdout.role_information_change<.05)]:
        g=holdout.loc[mask];metrics[label]={name:score(g,name) for name in names}
    def duration_score(actual,pred):
        e=np.asarray(pred)-np.asarray(actual)
        return {'n':len(e),'mae':float(abs(e).mean()),'rmse':float(np.sqrt((e**2).mean())),'bias':float(e.mean())}
    starters=holdout.y==1;nonstarts=holdout.y==0;subs=nonstarts&(holdout.minutes>0)
    components={
       'start_duration':{'baseline':duration_score(holdout.loc[starters,'minutes'],holdout.loc[starters,'start_minutes_mean']),
                         'new':duration_score(holdout.loc[starters,'minutes'],holdout.loc[starters,'e_min_start'])},
       'sub_duration':{'baseline':duration_score(holdout.loc[subs,'minutes'],holdout.loc[subs,'cameo_minutes_mean']),
                       'new':duration_score(holdout.loc[subs,'minutes'],holdout.loc[subs,'e_min_sub'])}}
    appearance=(holdout.loc[nonstarts,'minutes']>0).astype(int)
    for name,col in [('baseline','p_cameo_given_bench'),('new','p_sub_not_start')]:
        probabilities=np.clip(holdout.loc[nonstarts,col],1e-9,1-1e-9)
        components.setdefault('sub_appearance',{})[name]={'n':len(appearance),'brier':float(((probabilities-appearance)**2).mean()),
           'log_loss':float(-(appearance*np.log(probabilities)+(1-appearance)*np.log(1-probabilities)).mean())}
    write_prediction_csv(holdout,out/'conditional_minutes_holdout_predictions.csv.gz')
    write_json(out/'metrics.json',metrics);write_json(out/'component_metrics.json',components);write_json(out/'models.json',models)
    write_json(out/'protocol.json',{'fit':'frozen GW6-21; fixed Ridge alpha=20 durations, standardized logistic C=1 sub appearance',
       'training_counts':counts,'holdout_rows':len(holdout),'training_cutoff':cutoff.isoformat(),
       'p_start':'unchanged frozen role-aware-v1','tuning':'none; ablations are diagnostic, not selected on final holdout',
       'bench_definition':'all non-starting members of fixed benchmark roster; not confirmed matchday bench',
       'availability':'inherits explicit historical cutoff/completion proxies from role foundation',
       'deployment':'experimental, app unchanged; requires independent OOS before promotion'})
    code=[Path(__file__),ROOT/'src/fpl_v1_1_model/minutes_decomposition.py',ROOT/'scripts/build_reproducible_role_benchmark.py']
    write_json(out/'manifest.json',{'input':{'path':str(Path(a.features).relative_to(ROOT)) if Path(a.features).is_relative_to(ROOT) else Path(a.features).name,'sha256':sha(a.features)},
            'code':[{'path':str(p.relative_to(ROOT)),'sha256':sha(p)} for p in code],
            'outputs':[{'path':p.name,'sha256':sha(p)} for p in sorted(out.iterdir()) if p.name!='manifest.json' and not p.name.endswith('.tmp')]})
    print(json.dumps({'overall':metrics,'components':components},indent=2))


if __name__=='__main__':main()

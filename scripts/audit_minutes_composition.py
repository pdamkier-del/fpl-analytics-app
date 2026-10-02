#!/usr/bin/env python3
"""Posthoc exact Shapley decomposition of the saved minutes MAE/RMSE changes.

Diagnostic only: no candidate fitting, selection or target labels as predictors.
Six component replacement orders remove arbitrary order dependence.
"""
from itertools import permutations
from pathlib import Path
import numpy as np
import pandas as pd
from benchmark_minutes_decomposition import ROOT
from build_reproducible_role_benchmark import write_json, sha


def contributions(frame):
    old=[frame.start_minutes_mean.to_numpy(),frame.p_cameo_given_bench.to_numpy(),frame.cameo_minutes_mean.to_numpy()]
    new=[frame.e_min_start.to_numpy(),frame.p_sub_not_start.to_numpy(),frame.e_min_sub.to_numpy()]
    p=frame.role_aware_p_start.to_numpy();actual=frame.minutes.to_numpy()
    def errors(terms):
        prediction=p*terms[0]+(1-p)*terms[1]*terms[2]
        return np.abs(prediction-actual),(prediction-actual)**2
    maes=np.zeros((len(frame),3));mses=np.zeros_like(maes)
    for order in permutations(range(3)):
        terms=list(old);prev_mae,prev_mse=errors(terms)
        for index in order:
            terms[index]=new[index];next_mae,next_mse=errors(terms)
            maes[:,index]+=(next_mae-prev_mae)/6
            mses[:,index]+=(next_mse-prev_mse)/6
            prev_mae,prev_mse=next_mae,next_mse
    a,b=errors(old);c,d=errors(new)
    assert np.allclose(maes.sum(axis=1),c-a,atol=1e-10)
    assert np.allclose(mses.sum(axis=1),d-b,atol=1e-10)
    return maes,mses


def main():
    path=ROOT/'analysis/results/minutes-decomposition-v1/conditional_minutes_holdout_predictions.csv.gz'
    frame=pd.read_csv(path);out=ROOT/'analysis/results/minutes-composition-audit';out.mkdir(parents=True,exist_ok=True)
    maes,mses=contributions(frame)
    groups={'all':np.ones(len(frame),dtype=bool),
            'actual_start':frame.y==1,'actual_sub':(frame.y==0)&(frame.minutes>0),
            'no_appearance':frame.minutes==0,
            'high_role_impact':frame.role_information_change>=.05}
    rows=[];labels=['start_duration','sub_probability','sub_duration']
    for name,mask in groups.items():
        n=int(mask.sum())
        for i,label in enumerate(labels):
            rows.append({'group':name,'component':label,'n':n,
                'mean_mae_contribution':float(maes[mask,i].mean()),
                'whole_cohort_weighted_mae_contribution':float(maes[mask,i].sum()/len(frame)),
                'mean_mse_contribution':float(mses[mask,i].mean())})
    pd.DataFrame(rows).to_csv(out/'shapley_error_contributions.csv',index=False)
    # Reliability bins use predictions alone; labels are only evaluation outcomes.
    bins=[0,5,15,30,45,60,75,90.000001];records=[]
    for name,col in [('control','role_aware_xmins'),('full','full_decomposition_xmins')]:
        for band,g in frame.groupby(pd.cut(frame[col],bins=bins,include_lowest=True),observed=True):
            e=g[col]-g.minutes
            records.append({'variant':name,'prediction_bin':str(band),'n':len(g),
               'mean_prediction':float(g[col].mean()),'mean_actual':float(g.minutes.mean()),
               'median_actual':float(g.minutes.median()),'zero_share':float((g.minutes==0).mean()),
               'bias':float(e.mean()),'mae':float(abs(e).mean()),'rmse':float(np.sqrt((e**2).mean()))})
    pd.DataFrame(records).to_csv(out/'minutes_reliability.csv',index=False)
    summary={'n':len(frame),'zero_minutes_share':float((frame.minutes==0).mean()),
       'mae_delta':float(maes.sum(axis=1).mean()),'mse_delta':float(mses.sum(axis=1).mean()),
       'component_mae_contributions':dict(zip(labels,map(float,maes.mean(axis=0)))),
       'component_mse_contributions':dict(zip(labels,map(float,mses.mean(axis=0)))),
       'interpretation':'Exact attribution for saved predictions, not causal explanation. Conditional mean minimizes MSE; conditional median minimizes MAE. Do not distort E[min] toward zero just to improve MAE.',
       'holdout_status':'Previously inspected GW22-38: posthoc diagnostic, not independent OOS',
       'next_decision':'Predeclare component proper losses plus final mean-calibration/RMSE and downstream xP validation; retain MAE as a reported diagnostic, not the only acceptance metric.'}
    write_json(out/'summary.json',summary)
    write_json(out/'manifest.json',{'input':{'path':str(path.relative_to(ROOT)),'sha256':sha(path)},
      'code':[{'path':str(Path(__file__).relative_to(ROOT)),'sha256':sha(__file__)}],
      'outputs':[{'path':p.name,'sha256':sha(p)} for p in sorted(out.iterdir()) if p.name!='manifest.json']})
    print(summary)


if __name__=='__main__':main()

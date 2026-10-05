#!/usr/bin/env python3
"""v4-3S: joint starter / substitute / zero-minute state model.

This experiment replaces the two-step start + cameo-probability composition with
one mutually exclusive three-state probability model:

    S = starts
    C = substitute appearance (not start, minutes > 0)
    Z = zero minutes

The conditional duration forecasts remain frozen from v4:
    E[min] = P(S)*E[min|start] + P(C)*E[min|sub]

Protocol:
* Fit on GW6-15, select on GW16-21.
* Refit selected candidate on GW6-21.
* GW22-38 is reused diagnostic only, not fresh OOS.
* Preserve the inherited exact-11 expected starters per team/fixture by shifting
  only the S-vs-nonstart log odds; the C:Z ratio inside nonstarters is preserved.
* No point/event/transfer/chip model changes.
"""
from __future__ import annotations
import gzip, hashlib, io, json, os
from pathlib import Path
import sys
import numpy as np
import pandas as pd
from scipy.optimize import brentq
from scipy.special import expit, logit
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
sys.path.insert(0,str(ROOT/'scripts'))

from fpl_v1_1_model.workload import WORKLOAD_FEATURES
from build_reproducible_role_benchmark import BASE_FEATURES,ROLE_FEATURES
from run_v4rc_experiment import add_role_competition_features, fit_v4_start, xmins_from_p, RC_B

SOURCE=ROOT/'analysis/results/workload-recovered-v4/all_features.csv.gz'
V4_RESULTS=ROOT/'analysis/results/workload-recovered-minutes-v4'
OUT=ROOT/'analysis/results/v4-three-state-20261005-v1'

V4_FEATURES=BASE_FEATURES+ROLE_FEATURES+WORKLOAD_FEATURES
CANDIDATES={
    '3state_v4':V4_FEATURES,
    '3state_v4_rc':V4_FEATURES+RC_B,
}


def sha(path):
    h=hashlib.sha256()
    with open(path,'rb') as f:
        for chunk in iter(lambda:f.read(1024*1024),b''):h.update(chunk)
    return h.hexdigest()


def write_json(path,value):
    path.write_text(json.dumps(value,indent=2,sort_keys=True,allow_nan=False)+'\n')


def write_gzip_csv(frame,path):
    tmp=path.with_name(path.name+'.tmp')
    with open(tmp,'wb') as raw:
        with gzip.GzipFile(filename='',mode='wb',fileobj=raw,mtime=0) as gz:
            with io.TextIOWrapper(gz,encoding='utf-8',newline='') as txt:
                frame.to_csv(txt,index=False)
        raw.flush();os.fsync(raw.fileno())
    os.replace(tmp,path)


def target_state(frame):
    # 2=start, 1=substitute appearance, 0=zero minutes
    return np.where(frame.y.to_numpy(int)==1,2,
                    np.where(frame.minutes.to_numpy(float)>0,1,0)).astype(int)


def constrain_exact_eleven(frame,prob):
    """Constrain starter mass to 11 while preserving C:Z ratio per player."""
    out=np.asarray(prob,float).copy()
    for idx in frame.groupby(['fixture_uuid','team_id'],sort=True).indices.values():
        idx=np.asarray(idx,dtype=int)
        if len(idx)<=11:raise ValueError('Need full roster >11 for exact-11 constraint')
        ps=np.clip(out[idx,2],1e-9,1-1e-9)
        non=out[idx,0]+out[idx,1]
        # Shift S-vs-nonstart odds by one team-level intercept.
        z=np.log(ps)-np.log(np.clip(non,1e-12,None))
        b=brentq(lambda a:expit(z+a).sum()-11,-40,40)
        new_s=expit(z+b)
        ratio_c=np.divide(out[idx,1],non,out=np.zeros_like(non),where=non>0)
        out[idx,2]=new_s
        out[idx,1]=(1-new_s)*ratio_c
        out[idx,0]=(1-new_s)*(1-ratio_c)
    assert np.allclose(out.sum(axis=1),1,atol=1e-10)
    return out


def baseline_states(frame,p_start):
    q=np.clip(frame.p_cameo_given_bench.to_numpy(float),0,1)
    ps=np.asarray(p_start,float)
    pc=(1-ps)*q
    pz=(1-ps)*(1-q)
    return np.column_stack([pz,pc,ps])


def expected_minutes_states(frame,prob):
    s=frame.start_minutes_mean.to_numpy(float)
    c=frame.cameo_minutes_mean.to_numpy(float)
    return prob[:,2]*s+prob[:,1]*c


def metrics(frame,mask,prob,xmins):
    y=target_state(frame)[mask]
    p=np.clip(prob[mask],1e-12,1)
    mins=frame.minutes.to_numpy(float)[mask]
    xm=np.asarray(xmins,float)[mask]
    start=(y==2).astype(float);ps=p[:,2]
    err=xm-mins
    one=np.eye(3)[y]
    return {
        'n':int(mask.sum()),
        'state_log_loss':float(-np.log(p[np.arange(len(y)),y]).mean()),
        'state_brier':float(np.mean(np.sum((p-one)**2,axis=1))),
        'start_log_loss':float(-(start*np.log(ps)+(1-start)*np.log1p(-ps)).mean()),
        'start_brier':float(np.mean((ps-start)**2)),
        'xmins_mae':float(np.mean(np.abs(err))),
        'xmins_rmse':float(np.sqrt(np.mean(err**2))),
        'xmins_bias':float(np.mean(err)),
        'mean_p_start':float(ps.mean()),
        'mean_p_sub':float(p[:,1].mean()),
        'actual_start_rate':float((y==2).mean()),
        'actual_sub_rate':float((y==1).mean()),
    }


def fit_three_state(frame,train,features,C):
    model=make_pipeline(StandardScaler(),LogisticRegression(C=C,max_iter=3000,random_state=0))
    y=target_state(frame)
    model.fit(frame.loc[train,features],y[train])
    raw=model.predict_proba(frame[features])
    # sklearn class order must be Z,C,S = 0,1,2
    if list(model[-1].classes_)!=[0,1,2]:raise AssertionError(model[-1].classes_)
    prob=constrain_exact_eleven(frame,raw)
    stored={
        'features':features,'C':float(C),
        'classes':[int(x) for x in model[-1].classes_],
        'coefficients':model[-1].coef_.tolist(),
        'intercepts':model[-1].intercept_.tolist(),
        'scaler_mean':model[0].mean_.tolist(),
        'scaler_scale':model[0].scale_.tolist(),
        'training_rows':int(train.sum()),
    }
    return prob,stored


def main():
    if OUT.exists():raise FileExistsError(OUT)
    OUT.mkdir(parents=True)
    protocol={
        'name':'v4 three-state starter/substitute/zero experiment',
        'states':{'0':'zero minutes','1':'substitute appearance','2':'starter'},
        'development_train':'GW6-15',
        'development_selection':'GW16-21',
        'final_train':'GW6-21',
        'reused_diagnostic':'GW22-38; not fresh independent OOS',
        'candidate_features':{k:len(v) for k,v in CANDIDATES.items()},
        'regularization_C':[0.25,1.0,4.0],
        'selection':'lowest development xMins RMSE; must beat v4 RMSE by >=0.01 min and not worsen state log-loss versus v4 by >0.005, otherwise retain v4',
        'exact_11':'team-level S-vs-nonstart log-odds shift; C:Z ratio preserved',
        'durations':'v4 start_minutes_mean and cameo_minutes_mean frozen',
        'no_other_model_changes':True,
    }
    write_json(OUT/'protocol.json',protocol)

    frame=pd.read_csv(SOURCE).reset_index(drop=True)
    known=pd.to_datetime(frame.outcome_known_at,utc=True)
    dev_val=frame.gw.between(16,21).to_numpy()
    dev_cut=pd.to_datetime(frame.loc[dev_val,'cutoff'],utc=True).min()
    dev_train=(frame.gw.between(6,15)&(known<dev_cut)).to_numpy()

    p_v4_dev,_=fit_v4_start(frame,dev_train)
    saved_dev=pd.read_csv(V4_RESULTS/'development_predictions.csv.gz')
    keys=['fixture_uuid','player_uuid','team_id','gw']
    chk=frame.loc[dev_val,keys].copy();chk['rebuilt']=p_v4_dev[dev_val]
    chk=chk.merge(saved_dev[keys+['workload_start_p_start']],on=keys,validate='one_to_one')
    repro_dev=float(np.max(np.abs(chk.rebuilt-chk.workload_start_p_start)))
    if repro_dev>1e-10:raise AssertionError(f'v4 dev mismatch {repro_dev}')

    feat_dev=add_role_competition_features(frame,p_v4_dev)
    base_prob_dev=baseline_states(frame,p_v4_dev)
    base_xm_dev=xmins_from_p(frame,p_v4_dev)
    base_dev=metrics(frame,dev_val,base_prob_dev,base_xm_dev)

    rows=[];dev_models={}
    for name,features in CANDIDATES.items():
        for C in (0.25,1.0,4.0):
            prob,model=fit_three_state(feat_dev,dev_train,features,C)
            xm=expected_minutes_states(frame,prob)
            met=metrics(frame,dev_val,prob,xm)
            rec={'candidate':name,'C':C,**met,
                 'delta_state_log_loss':met['state_log_loss']-base_dev['state_log_loss'],
                 'delta_start_log_loss':met['start_log_loss']-base_dev['start_log_loss'],
                 'delta_xmins_mae':met['xmins_mae']-base_dev['xmins_mae'],
                 'delta_xmins_rmse':met['xmins_rmse']-base_dev['xmins_rmse']}
            rows.append(rec);dev_models[f'{name}_C_{C:g}']=model
    cand=pd.DataFrame(rows).sort_values(['xmins_rmse','state_log_loss','candidate','C'])
    acceptable=cand[(cand.xmins_rmse<=base_dev['xmins_rmse']-0.01)&
                    (cand.state_log_loss<=base_dev['state_log_loss']+0.005)]
    if len(acceptable):
        best=acceptable.iloc[0]
        selected=str(best.candidate);selected_C=float(best.C)
    else:
        selected='v4';selected_C=None
    cand.to_csv(OUT/'development_candidates.csv',index=False)
    selection={'baseline_v4':base_dev,'selected':selected,'selected_C':selected_C,
               'v4_reproduction_max_abs_error':repro_dev,'rule':protocol['selection']}
    write_json(OUT/'selection.json',selection)
    write_json(OUT/'development_models.json',dev_models)

    test=frame.gw.between(22,38).to_numpy()
    final_cut=pd.to_datetime(frame.loc[test,'cutoff'],utc=True).min()
    final_train=(frame.gw.between(6,21)&(known<final_cut)).to_numpy()
    p_v4,_=fit_v4_start(frame,final_train)
    saved_test=pd.read_csv(V4_RESULTS/'reused_holdout_diagnostic_predictions.csv.gz')
    chk2=frame.loc[test,keys].copy();chk2['rebuilt']=p_v4[test]
    chk2=chk2.merge(saved_test[keys+['workload_start_p_start']],on=keys,validate='one_to_one')
    repro_test=float(np.max(np.abs(chk2.rebuilt-chk2.workload_start_p_start)))
    if repro_test>1e-10:raise AssertionError(f'v4 test mismatch {repro_test}')

    feat_final=add_role_competition_features(frame,p_v4)
    base_prob=baseline_states(frame,p_v4);base_xm=xmins_from_p(frame,p_v4)
    if selected=='v4':
        prob=base_prob.copy();xm=base_xm.copy();final_model=None
    else:
        prob,final_model=fit_three_state(feat_final,final_train,CANDIDATES[selected],selected_C)
        xm=expected_minutes_states(frame,prob)

    base_test=metrics(frame,test,base_prob,base_xm)
    new_test=metrics(frame,test,prob,xm)

    slices=[]
    pband=(p_v4>=.20)&(p_v4<=.80)
    state=target_state(frame)
    groups=[
        ('all',test),
        ('v4_pstart_0.20_to_0.80',test&pband),
        ('POSTHOC_starter',test&(state==2)),
        ('POSTHOC_substitute',test&(state==1)),
        ('POSTHOC_zero',test&(state==0)),
    ]
    for label,mask in groups:
        slices.append({'slice':label,'arm':'v4',**metrics(frame,mask,base_prob,base_xm)})
        slices.append({'slice':label,'arm':'v4_3state',**metrics(frame,mask,prob,xm)})
    pd.DataFrame(slices).to_csv(OUT/'diagnostic_slices.csv',index=False)

    gwrows=[]
    for gw in range(22,39):
        mask=test&frame.gw.eq(gw).to_numpy()
        if not mask.any():continue
        gwrows.append({'gw':gw,'arm':'v4',**metrics(frame,mask,base_prob,base_xm)})
        gwrows.append({'gw':gw,'arm':'v4_3state',**metrics(frame,mask,prob,xm)})
    pd.DataFrame(gwrows).to_csv(OUT/'metrics_by_gw.csv',index=False)

    pred=frame.loc[test,keys+['team','player','pos','expected_role','y','minutes']].copy()
    pred['v4_p_start']=base_prob[test,2];pred['v4_p_sub']=base_prob[test,1];pred['v4_p_zero']=base_prob[test,0]
    pred['three_p_start']=prob[test,2];pred['three_p_sub']=prob[test,1];pred['three_p_zero']=prob[test,0]
    pred['v4_xmins']=base_xm[test];pred['three_xmins']=xm[test]
    write_gzip_csv(pred,OUT/'reused_diagnostic_predictions.csv.gz')

    result={
        'classification':'development-selected three-state experiment + reused diagnostic; not independent OOS',
        'development_selection':selection,
        'reused_diagnostic':{
            'v4':base_test,'v4_3state':new_test,
            'delta_3state_minus_v4':{k:new_test[k]-base_test[k] for k in
                ['state_log_loss','state_brier','start_log_loss','start_brier','xmins_mae','xmins_rmse','xmins_bias']},
            'v4_reproduction_max_abs_start_error':repro_test,
        },
        'selected_candidate_promoted':False,
        'conditional_durations_unchanged':True,
        'rows':int(test.sum()),'fixtures':int(frame.loc[test,'fixture_uuid'].nunique()),
    }
    write_json(OUT/'result.json',result)
    write_json(OUT/'frozen_model.json',{'selected':selected,'model':final_model})

    outs=[p for p in sorted(OUT.iterdir()) if p.name!='manifest.json']
    write_json(OUT/'manifest.json',{
        'sources':[
            {'path':str(SOURCE.relative_to(ROOT)),'sha256':sha(SOURCE)},
            {'path':str((V4_RESULTS/'development_predictions.csv.gz').relative_to(ROOT)),'sha256':sha(V4_RESULTS/'development_predictions.csv.gz')},
            {'path':str((V4_RESULTS/'reused_holdout_diagnostic_predictions.csv.gz').relative_to(ROOT)),'sha256':sha(V4_RESULTS/'reused_holdout_diagnostic_predictions.csv.gz')},
            {'path':'scripts/run_v4_three_state_experiment.py','sha256':sha(Path(__file__))},
        ],
        'outputs':[{'path':p.name,'sha256':sha(p)} for p in outs],
    })
    print(json.dumps(result,indent=2))


if __name__=='__main__':
    main()

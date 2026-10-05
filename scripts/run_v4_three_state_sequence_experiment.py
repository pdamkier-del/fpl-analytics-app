#!/usr/bin/env python3
"""v4-3S-v2: preserve v4 start probabilities, improve C-vs-Z with sequence history.

Motivation
----------
The first joint 3-state experiment sharply improved S/C/Z state log-loss but
worsened expected minutes because it slightly damaged the already-strong v4
P(start) and over-assigned substitute mass. This experiment keeps P(start)
exactly equal to frozen v4 and only learns the conditional branch

    q = P(substitute appearance | not start)

using cutoff-safe recent PL sequence features on top of the existing role +
workload features. Candidate q models are selected on GW16-21 by xMins RMSE.
Conditional starter/cameo durations are unchanged.

No GW22-38 result is used for candidate selection.
"""
from __future__ import annotations
import gzip, hashlib, io, json, os
from pathlib import Path
import sys
import numpy as np
import pandas as pd
from scipy.special import expit, logit
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
sys.path.insert(0,str(ROOT/'scripts'))

from fpl_v1_1_model.workload import WORKLOAD_FEATURES
from build_reproducible_role_benchmark import BASE_FEATURES,ROLE_FEATURES
from run_v4rc_experiment import fit_v4_start, xmins_from_p

SOURCE=ROOT/'analysis/results/workload-recovered-v4/all_features.csv.gz'
V4_RESULTS=ROOT/'analysis/results/workload-recovered-minutes-v4'
OUT=ROOT/'analysis/results/v4-three-state-sequence-20261005-v1'

BASE_Q_FEATURES=BASE_FEATURES+ROLE_FEATURES+WORKLOAD_FEATURES
SEQ_FEATURES=[
    'seq_hist_n',
    'seq_last_minutes','seq_prev_minutes',
    'seq_mean2_minutes','seq_mean3_minutes','seq_mean5_minutes',
    'seq_last_started','seq_start_share3','seq_start_share5',
    'seq_sub_share3','seq_sub_share5',
    'seq_zero_share3','seq_zero_share5',
    'seq_trend_2_vs_prev3',
    'seq_minutes_slope5',
    'seq_start_streak','seq_nonstart_streak',
    'seq_60plus_share3','seq_60plus_share5',
    'seq_changed_state_last',
]
C_VALUES=[0.25,1.0,4.0]
BLENDS=[0.25,0.5,0.75,1.0]


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


def state_label(started,minutes):
    if int(started)==1:return 2
    return 1 if float(minutes)>0 else 0


def add_sequence_features(frame):
    """Build prior-PL sequence features with strict outcome_known_at < cutoff."""
    f=frame.copy().reset_index(drop=True)
    cut=pd.to_datetime(f.cutoff,utc=True)
    known=pd.to_datetime(f.outcome_known_at,utc=True)
    histories={}
    # Every row is one completed/predicted PL player-fixture observation.
    by_player={}
    for i,r in f[['player_uuid','outcome_known_at','y','minutes']].iterrows():
        by_player.setdefault(str(r.player_uuid),[]).append(
            (known.iloc[i],int(r.y),float(r.minutes)))
    for pid in by_player:
        by_player[pid].sort(key=lambda z:z[0])

    rows=[]
    for i,r in f.iterrows():
        pid=str(r.player_uuid); c=cut.iloc[i]
        hist=[z for z in by_player.get(pid,[]) if z[0] < c]
        hist=hist[-8:]
        mins=[z[2] for z in hist]
        starts=[z[1] for z in hist]
        states=[state_label(z[1],z[2]) for z in hist]
        def tail_mean(x,n,default=0.):
            return float(np.mean(x[-n:])) if x else default
        def share(pred,n):
            z=hist[-n:]
            return float(np.mean([pred(v) for v in z])) if z else 0.
        def streak(value_start):
            n=0
            for v in reversed(states):
                if value_start(v):n+=1
                else:break
            return float(n)
        if len(mins)>=2:
            recent2=float(np.mean(mins[-2:]))
            prev3=mins[-5:-2]
            trend=recent2-(float(np.mean(prev3)) if prev3 else float(np.mean(mins[:-2])) if len(mins)>2 else recent2)
        else:trend=0.
        z5=np.asarray(mins[-5:],float)
        slope=float(np.polyfit(np.arange(len(z5)),z5,1)[0]) if len(z5)>=2 else 0.
        changed=float(len(states)>=2 and states[-1]!=states[-2])
        rows.append({
            'seq_hist_n':float(min(len(hist),5)),
            'seq_last_minutes':mins[-1] if mins else 0.,
            'seq_prev_minutes':mins[-2] if len(mins)>=2 else (mins[-1] if mins else 0.),
            'seq_mean2_minutes':tail_mean(mins,2),
            'seq_mean3_minutes':tail_mean(mins,3),
            'seq_mean5_minutes':tail_mean(mins,5),
            'seq_last_started':float(starts[-1]) if starts else 0.,
            'seq_start_share3':share(lambda z:z[1]==1,3),
            'seq_start_share5':share(lambda z:z[1]==1,5),
            'seq_sub_share3':share(lambda z:z[1]==0 and z[2]>0,3),
            'seq_sub_share5':share(lambda z:z[1]==0 and z[2]>0,5),
            'seq_zero_share3':share(lambda z:z[2]==0,3),
            'seq_zero_share5':share(lambda z:z[2]==0,5),
            'seq_trend_2_vs_prev3':trend,
            'seq_minutes_slope5':slope,
            'seq_start_streak':streak(lambda s:s==2),
            'seq_nonstart_streak':streak(lambda s:s!=2),
            'seq_60plus_share3':share(lambda z:z[2]>=60,3),
            'seq_60plus_share5':share(lambda z:z[2]>=60,5),
            'seq_changed_state_last':changed,
        })
    out=pd.concat([f,pd.DataFrame(rows)],axis=1)
    assert np.isfinite(out[SEQ_FEATURES].to_numpy(float)).all()
    return out


def q_target(frame):
    # Defined only for actual nonstarters.
    return ((frame.y.to_numpy(int)==0)&(frame.minutes.to_numpy(float)>0)).astype(int)


def fit_q(frame,train,features,C):
    mask=train&(frame.y.to_numpy(int)==0)
    model=make_pipeline(StandardScaler(),LogisticRegression(C=C,max_iter=3000,random_state=0))
    model.fit(frame.loc[mask,features],q_target(frame)[mask])
    q=model.predict_proba(frame[features])[:,1]
    stored={'features':features,'C':float(C),'coefficients':model[-1].coef_[0].tolist(),
            'intercept':float(model[-1].intercept_[0]),
            'scaler_mean':model[0].mean_.tolist(),'scaler_scale':model[0].scale_.tolist(),
            'training_rows':int(mask.sum())}
    return q,stored


def compose(frame,p_start,q):
    s=frame.start_minutes_mean.to_numpy(float)
    c=frame.cameo_minutes_mean.to_numpy(float)
    return p_start*s+(1-p_start)*q*c


def state_probs(p_start,q):
    ps=np.asarray(p_start,float);q=np.asarray(q,float)
    return np.column_stack([(1-ps)*(1-q),(1-ps)*q,ps])


def metrics(frame,mask,p_start,q,xm):
    ystart=frame.y.to_numpy(int)[mask]
    mins=frame.minutes.to_numpy(float)[mask]
    p=np.clip(state_probs(p_start,q)[mask],1e-12,1)
    state=np.where(ystart==1,2,np.where(mins>0,1,0))
    one=np.eye(3)[state]
    err=np.asarray(xm)[mask]-mins
    non=ystart==0
    qsub=p[non,1]/np.clip(p[non,0]+p[non,1],1e-12,None)
    zsub=(mins[non]>0).astype(float)
    return {
        'n':int(mask.sum()),
        'state_log_loss':float(-np.log(p[np.arange(len(state)),state]).mean()),
        'state_brier':float(np.mean(np.sum((p-one)**2,axis=1))),
        'sub_brier_given_nonstart':float(np.mean((qsub-zsub)**2)) if non.any() else None,
        'xmins_mae':float(np.mean(np.abs(err))),
        'xmins_rmse':float(np.sqrt(np.mean(err**2))),
        'xmins_bias':float(np.mean(err)),
        'mean_q_sub_given_nonstart':float(qsub.mean()) if non.any() else None,
        'actual_q_sub_given_nonstart':float(zsub.mean()) if non.any() else None,
    }


def sequence_audit(frame,mask,p_start,q_base):
    xm=xmins_from_p(frame,p_start)
    err=xm-frame.minutes.to_numpy(float)
    rows=[]
    bands=[
        ('state_changed_last',frame.seq_changed_state_last.to_numpy()>0.5),
        ('state_stable',frame.seq_changed_state_last.to_numpy()<=0.5),
        ('strong_uptrend',frame.seq_trend_2_vs_prev3.to_numpy()>=20),
        ('strong_downtrend',frame.seq_trend_2_vs_prev3.to_numpy()<=-20),
        ('flat_trend',np.abs(frame.seq_trend_2_vs_prev3.to_numpy())<20),
        ('nonstart_streak_2plus',frame.seq_nonstart_streak.to_numpy()>=2),
        ('start_streak_2plus',frame.seq_start_streak.to_numpy()>=2),
    ]
    for name,m in bands:
        z=mask&m
        if z.sum()==0:continue
        rows.append({'group':name,'n':int(z.sum()),'v4_mae':float(np.mean(np.abs(err[z]))),
                     'v4_rmse':float(np.sqrt(np.mean(err[z]**2))),
                     'mean_actual_minutes':float(frame.minutes.to_numpy(float)[z].mean()),
                     'mean_v4_xmins':float(xm[z].mean())})
    return pd.DataFrame(rows)


def main():
    if OUT.exists():raise FileExistsError(OUT)
    OUT.mkdir(parents=True)
    protocol={
        'name':'v4 3-state v2 sequence/substate experiment',
        'principle':'freeze v4 P(start); learn only P(sub appearance | not start)',
        'sequence_features':SEQ_FEATURES,
        'development_train':'GW6-15','development_selection':'GW16-21',
        'final_train':'GW6-21','reused_diagnostic':'GW22-38 only after selection',
        'candidate_q_models':['existing_v4_q','binary_v4_features','binary_v4_plus_sequence'],
        'blend_grid':BLENDS,'C_grid':C_VALUES,
        'selection':'lowest development xMins RMSE; v4 wins ties; require no >0.005 worsening in state log-loss',
        'durations':'unchanged v4 conditional start/cameo means',
        'start_probability':'exact frozen v4, unchanged for every candidate',
    }
    write_json(OUT/'protocol.json',protocol)

    raw=pd.read_csv(SOURCE).reset_index(drop=True)
    frame=add_sequence_features(raw)
    known=pd.to_datetime(frame.outcome_known_at,utc=True)
    dev=frame.gw.between(16,21).to_numpy()
    devcut=pd.to_datetime(frame.loc[dev,'cutoff'],utc=True).min()
    tr=(frame.gw.between(6,15)&(known<devcut)).to_numpy()
    pdev,_=fit_v4_start(frame,tr)

    # Exact v4 reproduction.
    saved=pd.read_csv(V4_RESULTS/'development_predictions.csv.gz')
    keys=['fixture_uuid','player_uuid','team_id','gw']
    chk=frame.loc[dev,keys].copy();chk['p']=pdev[dev]
    chk=chk.merge(saved[keys+['workload_start_p_start']],on=keys,validate='one_to_one')
    repro=float(np.max(np.abs(chk.p-chk.workload_start_p_start)))
    if repro>1e-10:raise AssertionError(repro)

    q0=np.clip(frame.p_cameo_given_bench.to_numpy(float),1e-6,1-1e-6)
    xm0=compose(frame,pdev,q0)
    base=metrics(frame,dev,pdev,q0,xm0)

    candidates=[];models={}
    specs=[('binary_base',BASE_Q_FEATURES),('binary_sequence',BASE_Q_FEATURES+SEQ_FEATURES)]
    for name,features in specs:
        for C in C_VALUES:
            qhat,model=fit_q(frame,tr,features,C);models[f'{name}_C_{C:g}']=model
            for alpha in BLENDS:
                # Blend on logit scale so probabilities remain coherent and
                # alpha=0 would be exact v4. We test only nonzero candidates.
                qb=expit((1-alpha)*logit(q0)+alpha*logit(np.clip(qhat,1e-6,1-1e-6)))
                xm=compose(frame,pdev,qb)
                met=metrics(frame,dev,pdev,qb,xm)
                candidates.append({'candidate':name,'C':C,'alpha':alpha,**met,
                                   'delta_xmins_rmse':met['xmins_rmse']-base['xmins_rmse'],
                                   'delta_xmins_mae':met['xmins_mae']-base['xmins_mae'],
                                   'delta_state_log_loss':met['state_log_loss']-base['state_log_loss'],
                                   'delta_sub_brier':met['sub_brier_given_nonstart']-base['sub_brier_given_nonstart']})
    cand=pd.DataFrame(candidates).sort_values(['xmins_rmse','state_log_loss','candidate','C','alpha'])
    acceptable=cand[cand.state_log_loss<=base['state_log_loss']+0.005]
    if len(acceptable) and float(acceptable.iloc[0].xmins_rmse)<base['xmins_rmse']-1e-10:
        best=acceptable.iloc[0]
        selected=str(best.candidate);selC=float(best.C);selA=float(best.alpha)
    else:
        selected='v4';selC=None;selA=None
    cand.to_csv(OUT/'development_candidates.csv',index=False)
    selection={'v4':base,'selected':selected,'selected_C':selC,'selected_alpha':selA,
               'v4_start_reproduction_max_abs_error':repro}
    write_json(OUT/'selection.json',selection)
    write_json(OUT/'development_models.json',models)
    sequence_audit(frame,dev,pdev,q0).to_csv(OUT/'development_sequence_audit.csv',index=False)

    # Final fit/evaluation.
    test=frame.gw.between(22,38).to_numpy()
    finalcut=pd.to_datetime(frame.loc[test,'cutoff'],utc=True).min()
    finaltr=(frame.gw.between(6,21)&(known<finalcut)).to_numpy()
    pfinal,_=fit_v4_start(frame,finaltr)
    saved2=pd.read_csv(V4_RESULTS/'reused_holdout_diagnostic_predictions.csv.gz')
    chk2=frame.loc[test,keys].copy();chk2['p']=pfinal[test]
    chk2=chk2.merge(saved2[keys+['workload_start_p_start']],on=keys,validate='one_to_one')
    repro2=float(np.max(np.abs(chk2.p-chk2.workload_start_p_start)))
    if repro2>1e-10:raise AssertionError(repro2)

    q0=np.clip(frame.p_cameo_given_bench.to_numpy(float),1e-6,1-1e-6)
    xm0=compose(frame,pfinal,q0)
    if selected=='v4':
        qfinal=q0.copy();xm=xm0.copy();finalmodel=None
    else:
        features=BASE_Q_FEATURES+(SEQ_FEATURES if selected=='binary_sequence' else [])
        qhat,finalmodel=fit_q(frame,finaltr,features,selC)
        qfinal=expit((1-selA)*logit(q0)+selA*logit(np.clip(qhat,1e-6,1-1e-6)))
        xm=compose(frame,pfinal,qfinal)

    btest=metrics(frame,test,pfinal,q0,xm0)
    ntest=metrics(frame,test,pfinal,qfinal,xm)
    sequence_audit(frame,test,pfinal,q0).to_csv(OUT/'reused_diagnostic_sequence_audit.csv',index=False)

    # Diagnostic slices, posthoc labels clearly marked.
    state=np.where(frame.y.to_numpy(int)==1,2,np.where(frame.minutes.to_numpy(float)>0,1,0))
    groups=[
        ('all',test),
        ('sequence_changed',test&(frame.seq_changed_state_last.to_numpy()>0.5)),
        ('strong_uptrend',test&(frame.seq_trend_2_vs_prev3.to_numpy()>=20)),
        ('strong_downtrend',test&(frame.seq_trend_2_vs_prev3.to_numpy()<=-20)),
        ('POSTHOC_substitute',test&(state==1)),
        ('POSTHOC_zero',test&(state==0)),
    ]
    sr=[]
    for label,m in groups:
        if not m.any():continue
        sr.append({'slice':label,'arm':'v4',**metrics(frame,m,pfinal,q0,xm0)})
        sr.append({'slice':label,'arm':'v4_3state_sequence',**metrics(frame,m,pfinal,qfinal,xm)})
    pd.DataFrame(sr).to_csv(OUT/'diagnostic_slices.csv',index=False)

    pred=frame.loc[test,keys+['team','player','pos','expected_role','y','minutes']+SEQ_FEATURES].copy()
    pred['v4_p_start']=pfinal[test];pred['v4_q_sub']=q0[test];pred['new_q_sub']=qfinal[test]
    pred['v4_xmins']=xm0[test];pred['new_xmins']=xm[test]
    write_gzip_csv(pred,OUT/'reused_diagnostic_predictions.csv.gz')

    result={
        'classification':'development-selected conditional substate/sequence experiment; GW22-38 reused diagnostic only',
        'development_selection':selection,
        'reused_diagnostic':{
            'v4':btest,'candidate':ntest,
            'delta_candidate_minus_v4':{k:ntest[k]-btest[k] for k in
                ['state_log_loss','state_brier','sub_brier_given_nonstart','xmins_mae','xmins_rmse','xmins_bias']},
            'v4_start_reproduction_max_abs_error':repro2,
        },
        'p_start_identical_to_v4':True,'conditional_durations_unchanged':True,
        'promoted':False,'rows':int(test.sum()),
    }
    write_json(OUT/'result.json',result)
    write_json(OUT/'frozen_model.json',{'selected':selected,'model':finalmodel,'alpha':selA})

    outs=[p for p in sorted(OUT.iterdir()) if p.name!='manifest.json']
    write_json(OUT/'manifest.json',{
        'sources':[{'path':str(SOURCE.relative_to(ROOT)),'sha256':sha(SOURCE)},
                   {'path':'scripts/run_v4_three_state_sequence_experiment.py','sha256':sha(Path(__file__))}],
        'outputs':[{'path':p.name,'sha256':sha(p)} for p in outs]})
    print(json.dumps(result,indent=2))


if __name__=='__main__':
    main()

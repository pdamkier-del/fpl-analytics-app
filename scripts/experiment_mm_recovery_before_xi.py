#!/usr/bin/env python3
"""Medical-return correction WITHIN full frozen-MM XI optimizer, compared fairly.

We retain original MM base, q_sub, substitute duration and Team News policy.
Evidence of injury -> miss -> start return is used only when archived predeadline
status and pre-target outcomes confirm it. The medical return logit increment is
applied to P(start) before XI competition and is followed by the original
residual XI optimizer, exact-11 projection and hard-out caps.
Grid selected GW16-21; refit GW6-21 and diagnose reused GW22-38.
No permanent PM, TS, or official MM modifications.
"""
import json,sys
from pathlib import Path
import numpy as np,pandas as pd
from scipy.special import expit,logit
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'scripts'),str(ROOT/'src')]
from experiment_mm_full_calendar_features import build_calendar,NEWS,RATINGS,POLICY
from run_mm_unified_official_roles import SOURCE,full_mm,compose
from run_v4_three_state_sequence_experiment import add_sequence_features,metrics
from run_v4_performance_rating_experiment import build_perf_ledger,add_features as add_perf_features
from fpl_v1_1_model.rating_history import build_rating_features
from fpl_v1_1_model.team_news_history import read_split_gzip_jsonl,build_strict_team_news_features
from run_mm_v2_team_news_availability_experiment import policy_caps,RATING_CFG,L2
from fpl_v1_1_model.availability_projection import project_exact_starters_with_caps
from run_mm_v2_relative_rating_competition import add_relative_xi_features
from run_mm_v2_xi_rating_experiment import ASSIGN_FEATURES,fit_residual
OUT=ROOT/'work/live-final-model/mm_full_medical_return_xi_ab.json'

def metric(frame,sel,p,q,sub):
    xm=compose(frame,p,q,sub)
    return metrics(frame,sel,p,q,xm)

def model(frame,train,eval_mask,base,q,sub,caps,shift):
    m=frame.cal_medical_return_starter.to_numpy(float)
    prior=project_exact_starters_with_caps(frame,base,caps)
    pred=expit(logit(np.clip(prior,1e-8,1-1e-8))+float(shift)*m)
    adjusted=project_exact_starters_with_caps(frame,pred,caps)
    feat=add_relative_xi_features(frame,adjusted,RATING_CFG)
    recalibrated,_=fit_residual(feat,adjusted,train,ASSIGN_FEATURES,L2)
    final=project_exact_starters_with_caps(feat,recalibrated,caps)
    err=(pd.DataFrame({'key':frame.fixture_uuid.astype(str)+'#'+frame.team_id.astype(str),
                       'p':final}).groupby('key').p.sum()-11).abs().max()
    assert err<1e-6,err
    xm=compose(feat,final,q,sub)
    out={}
    for label,condition in [
         ('all',np.ones(len(frame),dtype=bool)),
         ('medical_return',m>=.5),
         ('not_medical_return',m<.5),
         ('long_gap14',frame.cal_team_since_pl_days.ge(14).to_numpy())]:
        mm=eval_mask&condition
        if mm.sum()>=10:
            out[label]=metrics(feat,mm,final,q,xm)
    return out

def run():
    frame=add_sequence_features(pd.read_csv(SOURCE).reset_index(drop=True))
    frame=add_perf_features(frame,build_perf_ledger())
    frame=build_rating_features(frame,pd.read_csv(RATINGS))
    strict=read_split_gzip_jsonl(NEWS,'predeadline_strict.jsonl.gz')
    frame=build_strict_team_news_features(frame,strict)
    frame,coverage=build_calendar(frame)
    known=pd.to_datetime(frame.outcome_known_at,utc=True)
    grids=[0.,.2,.4,.6,.8,1.]
    metrics_by_fold={}
    for label,target_gws,end_train in [
        ('development',range(16,22),15),('reused_diagnostic',range(22,39),21)]:
        if label!='development' and 'choice' not in metrics_by_fold:
            raise AssertionError('Must select before looking at diagnostic')
        v=frame.gw.isin(target_gws).to_numpy()
        cut=pd.to_datetime(frame.loc[v,'cutoff'],utc=True).min()
        train=(frame.gw.le(end_train)&known.lt(cut)).to_numpy()
        base,q,sub,original_x,_=full_mm(frame.copy(),train)
        caps=policy_caps(frame,POLICY)
        tested=grids if label=='development' else sorted(set([0.,metrics_by_fold['choice']]))
        results={}
        for shift in tested:
            actual=model(frame,train,v,base,q,sub,caps,shift)
            results[str(shift)]=actual
            print('RETURN_FULL_XI_VARIANT',json.dumps(dict(fold=label,shift=shift,
                 all={k:actual['all'][k] for k in ['state_log_loss','xmins_mae','xmins_rmse']},
                 medical={k:actual.get('medical_return',{}).get(k) for k in ['n','state_log_loss','xmins_mae','xmins_rmse']})),
                 flush=True)
        metrics_by_fold[label]=results
        if label=='development':
            zero=results['0.0']
            core=zero['all'];med=zero.get('medical_return')
            eligible=[]
            for c in tested[1:]:
                res=results[str(c)]
                if med is None or med['n']<15 or 'medical_return' not in res:continue
                m=res['medical_return'];a=res['all']
                if (m['xmins_rmse']<med['xmins_rmse'] and
                    m['xmins_mae']<med['xmins_mae'] and
                    a['xmins_rmse']<=core['xmins_rmse']+.02 and
                    a['xmins_mae']<=core['xmins_mae']+.02 and
                    a['state_log_loss']<=core['state_log_loss']+.001):
                    eligible.append(c)
            metrics_by_fold['choice']=min(eligible,key=lambda c:(
                  results[str(c)]['medical_return']['xmins_rmse'],
                  results[str(c)]['all']['state_log_loss'])) if eligible else 0.
            print('RETURN_FULL_XI_SELECTED_DEV',json.dumps(dict(selected=metrics_by_fold['choice'],
                 medical_rows=int((v&(frame.cal_medical_return_starter>=.5)).sum()))),flush=True)
    rep=dict(classification='READ_ONLY_FULL_MM_INJURY_RETURN_BEFORE_XI',
             calendar_feature_provenance=coverage,folds=metrics_by_fold,
             selected_dev_only=metrics_by_fold['choice'],
             source='2025/26 PL player outcomes + strict predeadline FPL news',
             guards='exact XI expected starts=11, source hard-out caps applied before/after XI',
             baseline_math='Original MM base Pstart, conditional substitute appearance and minutes. No additive calendar regressors.',
             caveat='GW22-38 previously reused by project: not an independent holdout',
             production_changed=False)
    OUT.parent.mkdir(parents=True,exist_ok=True)
    OUT.write_text(json.dumps(rep,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print('RETURN_FULL_XI_FINAL',json.dumps({k:rep[k] for k in ['selected_dev_only','calendar_feature_provenance','caveat']}),flush=True)
if __name__=='__main__':run()

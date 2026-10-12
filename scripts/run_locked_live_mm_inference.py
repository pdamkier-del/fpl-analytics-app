#!/usr/bin/env python3
"""Execute frozen MM including XI on isolated training and unlabeled targets.

Current reconstruction quality is explicit: diagnostics are not release
certification. Never substitute base P(start) for the full upstream MM in XI.
"""
import argparse,json,sys,hashlib
from pathlib import Path
import numpy as np,pandas as pd
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'src'),str(ROOT/'scripts')]
from run_mm_unified_official_roles import full_mm,compose
from run_mm_v2_team_news_availability_experiment import policy_caps,RATING_CFG,L2
from run_locked_mm_gw6_38 import POLICY
from fpl_v1_1_model.availability_projection import project_exact_starters_with_caps
from run_mm_v2_relative_rating_competition import add_relative_xi_features
from run_mm_v2_xi_rating_experiment import ASSIGN_FEATURES,fit_residual
from audit_current_locked_inputs import csvgz,dump
BASE=ROOT/'data_v1_1/derived/live_locked_inputs/2026-27-v1'
WORK=ROOT/'work/live-final-model'


def medical_return_mask(history,target,origin):
    """Strict known-before-deadline medical return after one verified missed GW."""
    states={'OUT','DOUBT','MAJOR_DOUBT'}
    eligible={'AVAILABLE','RETURNED_AVAILABLE'}
    if not {'gw','player_uuid','y','minutes','team_news_state'}.issubset(history.columns):
        raise ValueError('Unavailable historical medical state for vNext')
    past=history[history.gw.between(origin-6,origin-1)]
    counts=past.groupby(['player_uuid','gw']).size()
    ambiguous=set(counts[counts>1].index)
    facts={(str(r.player_uuid),int(r.gw)):(int(r.y),float(r.minutes),str(r.team_news_state))
           for r in past.itertuples(index=False) if (r.player_uuid,r.gw) not in ambiguous}
    current=target[target.target_gw.eq(origin)]
    if current.player_uuid.duplicated().any():raise ValueError('Duplicate player in target')
    positives=set()
    for r in current.itertuples(index=False):
        pid=str(r.player_uuid)
        if str(r.team_news_state) not in eligible:continue
        last=facts.get((pid,origin-1))
        missed=facts.get((pid,origin-2))
        earlier=sum(facts.get((pid,k),(0,0,'UNKNOWN'))[0] for k in range(origin-6,origin-2))
        if last and missed and last[0]==1 and last[1]>0 and missed[1]==0 and missed[2] in states and earlier>=2:
            positives.add(pid)
    return target.player_uuid.astype(str).isin(positives).to_numpy(bool),positives

def infer(history,target,medical_return_logit=0.0):
    history=history.copy();target=target.copy()
    if target.empty or history.empty:raise ValueError('Missing real training or target rows')
    if any(c in target and target[c].notna().any() for c in ['y','minutes','outcome_known_at']):
        raise ValueError('Future target outcomes are forbidden')
    origin=int(target.gw.iloc[0]);cut=pd.to_datetime(target.cutoff,utc=True).min()
    if not target.gw.eq(origin).all():raise ValueError('Multiple forecast origins')
    if not history.season.eq(target.season.iloc[0]).all():raise ValueError('Previous season is not current-season training')
    if not (history.gw<origin).all():raise ValueError('Current/future GW in training')
    if not (pd.to_datetime(history.outcome_known_at,utc=True)<cut).all():
        raise ValueError('Training outcome unavailable at forecast origin')
    if set(history.fixture_uuid)&set(target.fixture_uuid):raise ValueError('Overlapping training/target fixtures')
    medical_return_logit=float(medical_return_logit)
    if medical_return_logit not in (0.0,0.4):
        raise ValueError('Only development-selected +0.4 experimental MM permitted')
    if medical_return_logit:
        selected,identified=medical_return_mask(history,target,origin)
    else:
        selected=np.zeros(len(target),dtype=bool);identified=set()
    # Target sentinels are necessary for old functions that cast the whole array.
    # Every fitting function receives the explicit immutable training-only mask.
    target['y']=0;target['minutes']=0.;target['outcome_known_at']='2100-01-01T00:00:00Z'
    future=target.target_gw.ne(origin)
    target.loc[future,'team_news_state']='UNKNOWN'
    target.loc[future,'team_news_scoped_chance']=np.nan
    target.loc[future,'team_news_availability_cap']=1.
    target.loc[future,'team_news_known']=0.
    f=pd.concat([history,target],ignore_index=True)
    train=np.arange(len(f))<len(history)
    p,q,sub,raw,models=full_mm(f.copy(),train)
    caps=policy_caps(f,POLICY)
    pre=project_exact_starters_with_caps(f,p,caps)
    if medical_return_logit:
        from scipy.special import expit,logit
        delta=np.zeros(len(f),float)
        delta[len(history):]=selected.astype(float)*medical_return_logit
        pre=project_exact_starters_with_caps(
            f,expit(logit(np.clip(pre,1e-8,1-1e-8))+delta),caps)
    feat=add_relative_xi_features(f,pre,RATING_CFG)
    residual,_=fit_residual(feat,pre,train,ASSIGN_FEATURES,L2)
    final=project_exact_starters_with_caps(feat,residual,caps)
    xm=compose(feat,final,q,sub)
    result=feat.iloc[len(history):].copy().reset_index(drop=True)
    result['p_start']=final[~train];result['mm_q_sub']=q[~train]
    if medical_return_logit:
        result['medical_return_vnext']=selected
    result['mm_sub_minutes']=sub[~train];result['xmins']=xm[~train]
    result['team_news_availability_cap']=caps[~train]
    result['p_appearance_from_bench']=(1-result.p_start)*result.mm_q_sub
    result=result.drop(columns=['y','minutes','outcome_known_at'])
    if not np.isfinite(result[ASSIGN_FEATURES+['p_start','xmins','mm_q_sub','mm_sub_minutes']].to_numpy(float)).all():
        raise ValueError('Nonfinite frozen inference output')
    counts=result.groupby(['fixture_uuid','team_id']).xi_selected_map.sum()
    if not counts.eq(11).all():raise ValueError('XI assignment failed for one or more target teams')
    err=float((result.groupby(['fixture_uuid','team_id']).p_start.sum()-11).abs().max())
    if err>1e-6:raise ValueError('Final exact-11 probability invariant failed')
    audit=dict(train_rows=len(history),target_rows=len(target),train_gws=sorted(map(int,history.gw.unique())),
               xi_features=ASSIGN_FEATURES,exact11_max_error=err,
               target_outcomes_used=0,future_news_neutralized_rows=int(future.sum()),
               model_math_changed=bool(medical_return_logit),live_certified=False,
               medical_return_logit=medical_return_logit,
               medically_documented_returner_count=len(identified),
               medically_documented_returner_fpl_ids=sorted(set(map(int,target.loc[selected,'fpl_element']))))
    return result,audit


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--one-gw',action='store_true')
    ap.add_argument('--vnext-medical-preview',action='store_true')
    a=ap.parse_args()
    if a.vnext_medical_preview and a.one_gw:raise ValueError('vNext preview requires six GW')
    history=pd.read_csv(BASE/'reconstructed_training_features.csv.gz',low_memory=False)
    target=pd.read_csv(BASE/'v2_baseline_feature_matrix.csv.gz',low_memory=False)
    if a.one_gw:target=target[target.target_gw.eq(target.gw)].reset_index(drop=True)
    result,audit=infer(history,target,medical_return_logit=.4 if a.vnext_medical_preview else 0.)
    label=('vnext_experimental_six_gw' if a.vnext_medical_preview else
           ('one_gw' if a.one_gw else 'six_gw'))
    path=(WORK/f'mm_{label}.csv.gz' if a.vnext_medical_preview else
          WORK/f'mm_frozen_diagnostic_{label}.csv.gz')
    csvgz(path,result)
    audit['classification']=('EXPERIMENTAL_MEDICAL_RETURN_MM_VNEXT_NOT_FINAL'
        if a.vnext_medical_preview else 'UNCHANGED_LOCKED_MM_ON_RECONSTRUCTED_TRAINING_NOT_LIVE_CERTIFIED')
    audit['training_quality']=json.loads((WORK/'live_training_provenance.json').read_text())
    audit['sha256']=hashlib.sha256(path.read_bytes()).hexdigest()
    dump(WORK/f'mm_inference_{label}.json',audit)
    print(json.dumps(audit),flush=True)
if __name__=='__main__':main()

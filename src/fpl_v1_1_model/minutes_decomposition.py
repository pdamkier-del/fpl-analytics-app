"""Frozen conditional-minutes experiment; not the active application engine.

Here bench means the benchmark's non-starting roster population. It includes
non-selected players: confirmed matchday-bench membership is NOT predicted.
Thus the mathematically precise probability is P(sub appearance | not start).
"""
import numpy as np
from sklearn.linear_model import LogisticRegression, Ridge
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from .role_classifier import ROLES

FEATURES=['start_minutes_mean','cameo_minutes_mean','p_cameo_given_bench',
          'role_fit_fast','role_h_fast','role_qmax_fast','role_evidence_fast',
          'role_fit_slow','role_h_slow','role_qmax_slow','role_evidence_slow',
          'role_started_last_gw']


def component_inputs(frame):
    """Only pre-cutoff fields; categorical schema is fixed, not learned on OOS."""
    out=frame[FEATURES].copy()
    for pos in ('GK','DEF','MID','FWD'):
        out['position_'+pos]=(frame.pos==pos).astype(float)
    for role in (*ROLES,'UNKNOWN'):
        out['expected_role_'+role]=(frame.expected_role==role).astype(float)
    assert np.isfinite(out.to_numpy()).all()
    return out


def compose_expected_minutes(p_start,start_minutes,p_sub,sub_minutes):
    values=[np.asarray(v,dtype=float) for v in (p_start,start_minutes,p_sub,sub_minutes)]
    if not all(np.isfinite(v).all() for v in values): raise ValueError('Non-finite minutes inputs')
    if any(((v < -1e-9)|(v > 1+1e-9)).any() for v in (values[0],values[2])): raise ValueError('Invalid probability')
    if any(((v < -1e-9)|(v > 90+1e-9)).any() for v in (values[1],values[3])): raise ValueError('Invalid conditional minutes')
    values=[np.clip(v,0,1 if i in (0,2) else 90) for i,v in enumerate(values)]
    return values[0]*values[1]+(1-values[0])*values[2]*values[3]


def fit_components(frame,training_mask):
    X=component_inputs(frame)
    starts=training_mask&(frame.y==1)
    nonstarts=training_mask&(frame.y==0)
    subs=nonstarts&(frame.minutes>0)
    models={
      'start_duration':make_pipeline(StandardScaler(),Ridge(alpha=20.)),
      'sub_appearance':make_pipeline(StandardScaler(),LogisticRegression(C=1.,max_iter=2000,random_state=0)),
      'sub_duration':make_pipeline(StandardScaler(),Ridge(alpha=20.))}
    models['start_duration'].fit(X.loc[starts],frame.loc[starts,'minutes'])
    models['sub_appearance'].fit(X.loc[nonstarts],(frame.loc[nonstarts,'minutes']>0).astype(int))
    models['sub_duration'].fit(X.loc[subs],frame.loc[subs,'minutes'])
    predictions={
      'e_min_start':np.clip(models['start_duration'].predict(X),0,90),
      'p_sub_not_start':models['sub_appearance'].predict_proba(X)[:,1],
      'e_min_sub':np.clip(models['sub_duration'].predict(X),0,90)}
    serialized={}
    for name,model in models.items():
        serialized[name]={'features':list(X.columns),'coefficients':np.ravel(model[-1].coef_).tolist(),
                          'intercept':float(np.ravel(model[-1].intercept_)[0]),
                          'scaler_mean':model[0].mean_.tolist(),'scaler_scale':model[0].scale_.tolist()}
    return predictions,serialized,{'starts':int(starts.sum()),'nonstarts':int(nonstarts.sum()),'subs':int(subs.sum())}

"""Outcome-free inference for the saved role/workload experiments.

This adapter does not supply historical features, certify source publication,
predict medical availability, or activate the app. Inputs must include the full
benchmark roster per fixture/team/cutoff for the inherited exact-eleven rule.
"""
import numpy as np
import pandas as pd
from scipy.optimize import brentq
from scipy.special import expit, logit
from .minutes_decomposition import compose_expected_minutes

VARIANTS={
    'role_control':('role',None),
    'workload_start':('workload',None),
    'role_decomposition':('role','role'),
    'workload_decomposition':('workload','workload'),
    'pl_only_start':('pl_only',None),
}


def linear_prediction(inputs, model, probability):
    columns=[]
    for name in model['features']:
        if name.startswith('position_'):
            col=(inputs.pos==name.removeprefix('position_')).astype(float)
        elif name.startswith('expected_role_'):
            col=(inputs.expected_role==name.removeprefix('expected_role_')).astype(float)
        else:
            if name not in inputs:
                raise ValueError('Missing model input: '+name)
            col=inputs[name]
        columns.append(np.asarray(col,dtype=float))
    x=np.column_stack(columns)
    mean=np.asarray(model['scaler_mean'],dtype=float)
    scale=np.asarray(model['scaler_scale'],dtype=float)
    coef=np.asarray(model['coefficients'],dtype=float)
    if not np.isfinite(x).all() or not np.isfinite(mean).all() or not np.isfinite(scale).all() or not np.isfinite(coef).all():
        raise ValueError('Non-finite model input or coefficient')
    if (scale<=0).any() or len(mean)!=x.shape[1] or len(coef)!=x.shape[1]:
        raise ValueError('Invalid stored model schema')
    result=((x-mean)/scale)@coef+float(model['intercept'])
    return expit(result) if probability else np.clip(result,0,90)


def predict_frozen(inputs, models, training_cutoff, variant='workload_start'):
    """Ignore all outcome columns; use only each saved model's input schema."""
    if variant not in VARIANTS:
        raise ValueError('Unknown experimental variant')
    keys=['cutoff','fixture_uuid','team_id','player_uuid']
    if any(k not in inputs for k in keys):
        raise ValueError('Missing forecast keys')
    if inputs.duplicated(keys).any():
        raise ValueError('Duplicate forecast key')
    cutoff=pd.to_datetime(inputs.cutoff,utc=True)
    if cutoff.isna().any() or (cutoff<pd.to_datetime(training_cutoff,utc=True)).any():
        raise ValueError('Forecast precedes frozen model training cutoff')
    for field in ('max_history_known_at','work_max_history_known_at'):
        if field not in inputs:
            raise ValueError('Missing cutoff audit field: '+field)
        raw=inputs[field]
        known=pd.to_datetime(raw,utc=True,errors='coerce')
        supplied=raw.notna() & (raw.astype(str).str.strip()!='')
        if (supplied & known.isna()).any() or (known.notna() & (known>=cutoff)).any():
            raise ValueError('Future or invalid historical availability: '+field)
    start,duration=VARIANTS[variant]
    p=linear_prediction(inputs,models[start+'_start_probability'],True)
    # Repeated forecasts of one fixture at different cutoffs are separate.
    for indexes in inputs.groupby(['cutoff','fixture_uuid','team_id'],sort=True).indices.values():
        if len(indexes)<=11:
            raise ValueError('Full roster with more than eleven candidates required')
        z=logit(np.clip(p[indexes],1e-7,1-1e-7))
        shift=brentq(lambda b:expit(z+b).sum()-11,-40,40)
        p[indexes]=expit(z+shift)
    if duration is None:
        start_minutes=inputs.start_minutes_mean.to_numpy(dtype=float)
        sub_probability=inputs.p_cameo_given_bench.to_numpy(dtype=float)
        sub_minutes=inputs.cameo_minutes_mean.to_numpy(dtype=float)
    else:
        start_minutes=linear_prediction(inputs,models[duration+'_start_duration'],False)
        sub_probability=linear_prediction(inputs,models[duration+'_sub_probability'],True)
        sub_minutes=linear_prediction(inputs,models[duration+'_sub_duration'],False)
    result=inputs[keys].reset_index(drop=True).copy()
    result['p_start']=p;result['e_min_given_start']=start_minutes
    result['p_appearance_given_not_start']=sub_probability
    result['e_min_given_sub']=sub_minutes
    result['expected_minutes']=compose_expected_minutes(p,start_minutes,sub_probability,sub_minutes)
    result['variant']=variant;result['experimental']=True
    result['all_competitions_complete']=False
    return result

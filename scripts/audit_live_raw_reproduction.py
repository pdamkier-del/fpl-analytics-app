#!/usr/bin/env python3
"""Locate upstream drift and perform a one-feature causal replay, without tuning.

Inputs are complete original-vFinal workflow ZIPs. Exact comparison is used;
an allclose check would conceal the optimizer's sensitivity to small features.
"""
import argparse, json, sys, zipfile, hashlib
from pathlib import Path
import numpy as np
import pandas as pd
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'src'),str(ROOT/'scripts')]
from run_v4_three_state_sequence_experiment import fit_q, BASE_Q_FEATURES, SEQ_FEATURES

def read(z,key):
    paths=[n for n in z.namelist() if n.endswith('/'+key+'.csv.gz')]
    if len(paths)!=1:raise ValueError('Expected one '+key)
    return pd.read_csv(z.open(paths[0]),compression='gzip',low_memory=False)

def numeric_diff(a,b):
    if list(a.columns)!=list(b.columns) or a.shape!=b.shape:raise ValueError('Schema or row count changed')
    out={}
    for c in a.select_dtypes('number'):
        x=a[c].to_numpy(float);y=b[c].to_numpy(float)
        same=(x==y)|(np.isnan(x)&np.isnan(y))
        if not same.all():
            d=np.abs(x-y);finite=d[np.isfinite(d)]
            out[c]={'rows':int((~same).sum()),'max_abs':float(finite.max()) if len(finite) else None}
    return out

def causal_q(a,b):
    features=BASE_Q_FEATURES+SEQ_FEATURES
    mask=np.ones(len(a),dtype=bool)
    qa,ma=fit_q(a,mask,features,4.)
    qb,mb=fit_q(b,mask,features,4.)
    changed=[c for c in features if not a[c].equals(b[c])]
    if changed!=['seq_minutes_slope5']:
        raise ValueError('Causal intervention is defined only for the observed single changed q feature')
    corrected=b.copy();corrected['seq_minutes_slope5']=a.seq_minutes_slope5.to_numpy()
    qc,mc=fit_q(corrected,mask,features,4.)
    if not np.array_equal(qa,qc) or ma!=mc:raise AssertionError('One-feature causal replay did not reproduce q')
    return {'changed_q_features':changed,'unadjusted_q_max_abs':float(abs(qa-qb).max()),
            'restored_one_feature_q_max_abs':float(abs(qa-qc).max()),
            'restored_fit_receipt_identical':ma==mc,
            'parameters_changed':False,'intervention_for_audit_only':True,
            'explanation':'Tiny polyfit slope differences change the unchanged standardized logistic L-BFGS fit. Restoring this sole changed q input restores every fitted coefficient and probability exactly.'}

def main():
    p=argparse.ArgumentParser();p.add_argument('--before',type=Path,required=True);p.add_argument('--after',type=Path,required=True);p.add_argument('--out',type=Path,required=True);args=p.parse_args()
    with zipfile.ZipFile(args.before) as za,zipfile.ZipFile(args.after) as zb:
        train_a=read(za,'reconstructed_training_features');train_b=read(zb,'reconstructed_training_features')
        identity=['player_uuid','fixture_uuid','gw','team_id','y','minutes']
        if not train_a[identity].equals(train_b[identity]):raise ValueError('Training identities/order/outcomes changed')
        report={'classification':'EXACT_UPSTREAM_DRIFT_AUDIT_NOT_RELEASE_CERTIFICATION',
            'archives':{k:hashlib.sha256(v.read_bytes()).hexdigest() for k,v in [('before',args.before),('after',args.after)]},
            'training_identity_and_order_identical':True,
            'training_numeric_differences':numeric_diff(train_a,train_b),
            'q_causal_replay':causal_q(train_a,train_b),
            'team_xg_history_exact':read(za,'observed_team_xg_history').equals(read(zb,'observed_team_xg_history')),
            'team_lambda_differences':numeric_diff(read(za,'future_team_goal_lambdas'),read(zb,'future_team_goal_lambdas')),
            'mm_differences':numeric_diff(read(za,'mm_frozen_diagnostic_six_gw'),read(zb,'mm_frozen_diagnostic_six_gw')),
            'locked_model_active':False,
            'remaining':'Cross-runtime team latent numerical drift and two complete canonical-runtime raw rebuilds must still be validated. No source values are overwritten with archived predictions.'}
    args.out.parent.mkdir(parents=True,exist_ok=True);args.out.write_text(json.dumps(report,indent=2,allow_nan=False)+'\n')
    print(json.dumps(report))
if __name__=='__main__':main()

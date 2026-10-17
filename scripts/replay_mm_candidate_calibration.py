#!/usr/bin/env python3
"""Re-fit the prospective B entry point at every frozen evaluation cutoff.

This proves that the preview runtime is not just a renamed saved number.
Inputs are the frozen prior-only features; no feature reconstruction shortcuts
or outcome labels are permitted in target rows.
"""
from pathlib import Path
import json
import numpy as np
import pandas as pd
from individual_mm_evidence import load_frame
from archive_role_injury_mm import restore
from mm_candidate_forecast import infer_B
from research_individual_mm_refinement import NUM

ROOT=Path(__file__).resolve().parents[1]
def main():
    cap=ROOT/'work/mm-integration-source'
    if not (cap/'results/predictions.npz').exists():restore(cap)
    base=load_frame(cap/'results/predictions.npz')
    base=base[base['mode']=='role_chance_return_duration'].copy()
    features=pd.read_csv(ROOT/'analysis/results/individual-mm-refinement-20261016/prior_only_features.csv.gz',float_precision='round_trip')
    keys=['season','fixture_uuid','player_uuid'];extra=[c for c in features if c not in base or c in keys]
    base=base.merge(features[extra],on=keys,validate='one_to_one')
    base['cutoff']=pd.to_datetime(base.cutoff,utc=True,format='mixed')
    base['known_at']=pd.to_datetime(base.kickoff_at,utc=True,format='mixed')+pd.to_timedelta(np.where(base.season.eq('2024-25'),4,3),unit='h')
    truth=load_frame(ROOT/'analysis/results/individual-mm-refinement-20261016/predictions.npz')
    truth=truth[truth['mode']=='B'];evaluation=((base.season=='2024-25')&base.gw.ge(22))|((base.season=='2025-26')&base.gw.ge(6))
    records=[];count=0;maximum=0.
    drop=['y','minutes','known_at']
    for cut,gg in base[evaluation].groupby('cutoff',sort=True):
        h=base[base.known_at.lt(cut)].copy()
        # Remove retrospective outcomes and all non-feature diagnostic labels.
        target=gg.drop(columns=drop+['outcome_known_at'],errors='ignore').reset_index(drop=True)
        pred,audit=infer_B(h,target,dict(upstream_variant='role_chance_return_duration',source_manifest_sha256='frozen-role-injury-capsule',features=NUM))
        ref=truth.merge(pred[keys+['p','q','s','c','x']],on=keys,validate='one_to_one',suffixes=('_frozen','_runtime'))
        diff=max(float((ref[k+'_frozen']-ref[k+'_runtime']).abs().max()) for k in ['p','q','s','c','x'])
        if diff>1e-6:raise ValueError('Runtime B differs from frozen reference: '+str(diff))
        count+=len(pred);maximum=max(maximum,diff)
        records.append(dict(cutoff=str(cut),rows=len(pred),training_rows=audit['training_rows'],last_label_known_at=audit['last_label_known_at'],max_abs_error=diff))
        print('Runtime B parity',cut,len(pred),diff,flush=True)
    if count!=39264:raise ValueError('Incomplete runtime parity')
    path=ROOT/'analysis/results/mm-integration-preview-20261017'
    path.mkdir(parents=True,exist_ok=True)
    (path/'runtime_parity.json').write_text(json.dumps(dict(evaluation_rows=count,max_abs_error=maximum,tolerance=1e-6,origins=records,production_unchanged=True),indent=2)+'\n')
if __name__=='__main__':main()

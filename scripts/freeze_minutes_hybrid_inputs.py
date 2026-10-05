"""Freeze development-selected minute composition for a paired joint diagnostic."""
import gzip
import hashlib
import json
from pathlib import Path
import numpy as np
import pandas as pd
from fpl_v1_1_model.paired_joint import read_frozen_table,build_pair

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'analysis/results/minutes-hybrid-inputs-20261005-v1'

def main():
    if OUT.exists():raise FileExistsError(OUT)
    experiment=ROOT/'analysis/results/minutes-components-20261005-v1'
    selection=json.loads((experiment/'selection.json').read_text())['selected']
    original=ROOT/'analysis/results/deadline-joint-inputs-v1'
    f=read_frozen_table(original,'inputs');target=read_frozen_table(original,'targets')
    p=ROOT/'analysis/results/workload-recovered-minutes-v4/reused_holdout_diagnostic_predictions.csv.gz'
    v=pd.read_csv(p)
    columns={'S':{'base':'start_minutes_mean','role':'role_start','workload':'workload_start'},
             'Q':{'base':'p_cameo_given_bench','role':'role_sub_probability','workload':'workload_sub_probability'},
             'C':{'base':'cameo_minutes_mean','role':'role_sub_duration','workload':'workload_sub_duration'}}
    keys=['fixture_uuid','player_uuid']
    selected=v[keys].copy()
    destinations={'S':'v4_start_minutes_mean','Q':'v4_p_cameo_given_bench','C':'v4_cameo_minutes_mean'}
    for k,dest in destinations.items():selected[dest]=v[columns[k][selection[k]]]
    hybrid=f.drop(columns=list(destinations.values())).merge(selected,on=keys,validate='one_to_one')
    assert len(hybrid)==len(f)==11794
    prob=hybrid.v4_workload_start_p_start
    hybrid['v4_workload_start_xmins']=prob*hybrid.v4_start_minutes_mean+(1-prob)*hybrid.v4_p_cameo_given_bench*hybrid.v4_cameo_minutes_mean
    changed=set(destinations.values())|{'v4_workload_start_xmins'}
    for col in f.columns:
        if col not in changed:pd.testing.assert_series_equal(f[col].reset_index(drop=True),hybrid[col].reset_index(drop=True))
    for _,g in hybrid.groupby('fixture_uuid'):build_pair(g)
    OUT.mkdir(parents=True)
    outputs=[]
    for name,frame in [('inputs',hybrid[f.columns]),('targets',target)]:
        raw=frame.to_csv(index=False).encode();packed=gzip.compress(raw,mtime=0);parts=[]
        for i,start in enumerate(range(0,len(packed),32768)):
            path=f'{name}.csv.gz.part-{i:04d}';chunk=packed[start:start+32768];(OUT/path).write_bytes(chunk)
            parts.append(dict(path=path,bytes=len(chunk),sha256=hashlib.sha256(chunk).hexdigest()))
        outputs.append(dict(name=name,rows=len(frame),compressed_sha256=hashlib.sha256(packed).hexdigest(),uncompressed_sha256=hashlib.sha256(raw).hexdigest(),parts=parts))
    m=dict(classification='experimental_development_selected_minutes_hybrid_reused_diagnostic',
        selected=selection,original_input_manifest_sha256=hashlib.sha256((original/'manifest.json').read_bytes()).hexdigest(),
        selected_before_joint_point_evaluation=True,unchanged_nonminute_columns_verified=True,
        original_v2_control_unchanged=True,fixtures=144,rows=11794,outputs=outputs,
        sources=[dict(path=str(x.relative_to(ROOT)),sha256=hashlib.sha256(x.read_bytes()).hexdigest()) for x in [p,experiment/'selection.json',Path(__file__)]],
        caveats=['GW22-38 reused; no independent validation','original scoring/BPS limitations retained','v4 column prefix denotes experimental hybrid in this folder only'])
    (OUT/'manifest.json').write_text(json.dumps(m,indent=2)+'\n');print('Verified paired hybrid inputs:',len(hybrid))

if __name__=='__main__':main()

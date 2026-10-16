#!/usr/bin/env python3
"""Merge completed origin shards without changing frozen input or reference identity."""
import argparse,hashlib,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
from audit_capture_io import checked_records,write_records

def merge_records(baseline,shards):
    expected={(r['origin'],r['fixture']):r for r in baseline}
    if len(expected)!=len(baseline):raise ValueError('Duplicate baseline fixture')
    merged={}
    for records in shards:
        for r in records:
            key=(r['origin'],r['fixture'])
            if key in merged:raise ValueError('Overlapping origin shards')
            if key not in expected:raise ValueError('Out-of-scope fixture')
            b=expected[key]
            if r['input']!=b['input'] or r['reference']!=b['reference'] or r['seed']!=b['seed']:raise ValueError('Frozen input/reference drift')
            merged[key]=r
    if set(merged)!=set(expected):raise ValueError('Incomplete seasonal fixture matrix')
    return [merged[(r['origin'],r['fixture'])] for r in baseline]

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--baseline',required=True);ap.add_argument('--input',action='append',required=True);ap.add_argument('--out',required=True);a=ap.parse_args()
    base=checked_records(a.baseline)
    if len(base)!=330:raise ValueError('Complete 330-fixture baseline required')
    merged=merge_records(base,[checked_records(p) for p in a.input]);write_records(a.out,merged)
    receipt=dict(fixtures=len(merged),sources={p:hashlib.sha256(Path(p).read_bytes()).hexdigest() for p in [a.baseline,*a.input]},output_sha256=hashlib.sha256(Path(a.out).read_bytes()).hexdigest(),locked_model_active=False)
    Path(a.out).with_suffix('.manifest.json').write_text(json.dumps(receipt,indent=2)+'\n');print(json.dumps(receipt,indent=2))
if __name__=='__main__':main()

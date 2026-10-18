#!/usr/bin/env python3
"""One command to assemble verified current B inputs and run existing MM -> PM.

Requires genuine upstream role/chance/return features; does not invent them.
Defaults to locked PM minute sampler and writes only to work/.
"""
import argparse
import json
import hashlib
from pathlib import Path
import pandas as pd
from assemble_current_b_roster import assemble
from run_mm_locked_preview import run_pipeline

ROOT=Path(__file__).resolve().parents[1]

def load(path): return json.loads(path.read_text())

def digest(obj):
    return hashlib.sha256(json.dumps(obj,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()

def main():
    a=argparse.ArgumentParser()
    for name in ['source','identity','features','history','roles','pm-input','bps-audit','out']:
        a.add_argument('--'+name,type=Path,required=True)
    args=a.parse_args()
    out=args.out.resolve()
    if not out.is_relative_to(ROOT/'work'):
        raise ValueError('Preview output must remain under work/')
    source=args.source
    roster=load(source/'official-roster.json')
    receipt=load(source/'receipt.json')
    bootstrap=load(source/'bootstrap.json')
    fixtures=load(source/'fixtures.json')
    features=pd.read_csv(args.features)
    mapping=pd.read_csv(args.identity)
    provenance=load(source/'B-feature-provenance.json')
    target=assemble(roster,mapping,features,provenance)
    cutoff=roster['cutoff']
    provenance.update(
        data_at=cutoff,
        origin_deadline=receipt['origin_deadline'],
        bootstrap_sha256=digest(bootstrap),
        fixtures_sha256=digest(fixtures),
        bootstrap_observed_at=receipt['observed_at'],
        fixtures_observed_at=receipt['observed_at'],
        source_workflow=receipt.get('workflow'))
    if provenance['bootstrap_sha256']!=receipt['bootstrap_sha256'] or provenance['fixtures_sha256']!=receipt['fixtures_sha256']:
        raise ValueError('Official source receipt mismatch')
    pm=pd.read_csv(args.pm_input)
    doc,forecast,plan,audit=run_pipeline(
        pd.read_csv(args.history),target,pd.read_csv(args.roles),
        provenance,pm,bootstrap,load(args.bps_audit),fixtures=fixtures,
        minute_sampler='locked')
    out.mkdir(parents=True,exist_ok=True)
    for name,obj in [('mm.json',doc),('forecast.json',forecast),('pm-audit.json',audit)]:
        (out/name).write_text(json.dumps(obj,sort_keys=True,allow_nan=False)+'\n')
    print(json.dumps(dict(status='PREVIEW_NOT_PRODUCTION',players=len(forecast['players']),
        gws=forecast['gws'],pm_sampler='locked',manager_state='NOT_AVAILABLE',
        blocked=forecast.get('blockers',[]))))
if __name__=='__main__':main()

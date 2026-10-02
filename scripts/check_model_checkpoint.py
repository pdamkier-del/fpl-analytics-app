#!/usr/bin/env python3
"""Verify saved model inputs/code/outputs, including complete gzip streams.

Does not rebuild or overwrite benchmark artifacts. Readiness is reported
separately from checksum integrity: intact experiments are not deployed models.
"""
import argparse
import gzip
import hashlib
import json
import subprocess
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
EXPERIMENTS=['reproducible-role-v1','minutes-decomposition-v1','squad-minutes-v1',
             'minutes-composition-audit','workload-v1','workload-minutes-v1',
             'independent-cl-audit','workload-quality-v2','workload-quality-minutes-v2',
             'independent-europe-audit','workload-quality-v3','workload-quality-minutes-v3']


def historical_code_version(path, expected):
    """Verify old experiment code against tracked Git bytes, never inputs/outputs."""
    relative=str(path.relative_to(ROOT))
    commits=subprocess.check_output(['git','log','--format=%H','--',relative],cwd=ROOT,text=True).splitlines()
    for commit in commits:
        content=subprocess.check_output(['git','show',f'{commit}:{relative}'],cwd=ROOT)
        if hashlib.sha256(content).hexdigest()==expected:return commit
    raise ValueError('SHA256 mismatch; no matching historical Git code')


def inspect(path):
    h=hashlib.sha256()
    with path.open('rb') as f:
        for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
    rows=None
    if path.name.endswith('.csv.gz'):
        with gzip.open(path,'rb') as f:
            rows=sum(b.count(b'\n') for b in iter(lambda:f.read(1024*1024),b''))-1
        if rows<1:raise ValueError('Empty prediction stream '+str(path))
    return h.hexdigest(),rows


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--db',default=str(ROOT/'work/core.sqlite3'))
    ap.add_argument('--report')
    a=ap.parse_args();db=Path(a.db).resolve();cache={};errors=[];checks=[]
    for name in EXPERIMENTS:
        folder=ROOT/'analysis/results'/name;manifest=json.loads((folder/'manifest.json').read_text())
        inputs=manifest.get('inputs',manifest.get('input',[]))
        if isinstance(inputs,dict):inputs=[inputs]
        for kind,items in [('input',inputs),('code',manifest.get('code',[])),('output',manifest['outputs'])]:
            for item in items:
                p=folder/item['path'] if kind=='output' else ROOT/item['path']
                if kind=='input' and str(item['path']).endswith(('.sqlite3','.sqlite')):p=db
                p=p.resolve()
                try:
                    if p not in cache:cache[p]=inspect(p)
                    digest,rows=cache[p]
                    historical=None
                    if digest!=item['sha256']:
                        if kind!='code':raise ValueError('SHA256 mismatch')
                        historical=historical_code_version(p,item['sha256']);digest=item['sha256']
                    checks.append({'experiment':name,'kind':kind,'path':str(p.relative_to(ROOT)) if p.is_relative_to(ROOT) else p.name,'sha256':digest,'csv_rows':rows,'historical_code_commit':historical})
                except (OSError,EOFError,ValueError) as e:
                    errors.append({'experiment':name,'kind':kind,'path':item['path'],'error':str(e)})
    raw=ROOT/'data_v1_1/raw/all-competitions-2025-26'
    source=json.loads((raw/'SOURCE_MANIFEST.json').read_text())
    for item in source['files']:
        p=raw/item['path'];b=p.read_bytes()
        digest=hashlib.sha1(b'blob '+str(len(b)).encode()+b'\0'+b).hexdigest()
        if digest!=item['git_blob_sha']:errors.append({'path':str(p.relative_to(ROOT)),'error':'Frozen source Git blob mismatch'})
    independent=ROOT/'data_v1_1/raw/independent-cup-inventory'
    independent_source=json.loads((independent/'SOURCE_MANIFEST.json').read_text())
    b=(independent/independent_source['local_path']).read_bytes()
    digest=hashlib.sha1(b'blob '+str(len(b)).encode()+b'\0'+b).hexdigest()
    if digest!=independent_source['git_blob_sha']:
        errors.append({'path':independent_source['local_path'],'error':'Independent inventory Git blob mismatch'})
    report={'integrity_passed':not errors,'manifest_checks':len(checks),'unique_files':len(cache),
      'source_files_verified':len(source['files']),'errors':errors,'checks':checks,
      'independent_source_files_verified':1,
      'full_season_simulation_ready':False,
      'cup_source_quality_certified':False,
      'cup_quality_audit':'analysis/results/independent-europe-audit/summary.json',
      'remaining_requirements':[
        'Complete FA Cup/player-minute ingestion and missing cup/Europe kickoff/stat data, with an independent coverage inventory',
        'Historical schedule/competition-state as-of snapshots for cutoff-safe Match Importance; no final-season elimination leakage',
        'Full squad/appearance/duration decomposition validated jointly with start forecasts and downstream xP',
        'A new independent role/workload test period or season (GW22-38 has already been repeatedly inspected)',
        'Integrate the selected standalone forecast with the existing app and replay/transfer/chip engine, then verify replay against the existing control'
      ]}
    if a.report:
        p=Path(a.report);p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(report,indent=2,sort_keys=True)+'\n')
    print(json.dumps({k:v for k,v in report.items() if k!='checks'},indent=2))
    raise SystemExit(bool(errors))


if __name__=='__main__':main()

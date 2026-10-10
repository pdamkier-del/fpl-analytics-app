#!/usr/bin/env python3
"""Package verified replay files append-only; never fit or modify the model."""
import argparse,base64,hashlib,io,json,zipfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
BASE='data_v1_1/derived/live_locked_inputs/2026-27-v1/'
WORK='work/live-final-model/'
def main():
    p=argparse.ArgumentParser();p.add_argument('--template',type=Path,required=True);p.add_argument('--out',type=Path,required=True);p.add_argument('--workflow',required=True);a=p.parse_args()
    if a.out.exists():raise ValueError('Checkpoint already exists; select a new version')
    template=json.loads(a.template.read_text());audit=json.loads((ROOT/WORK/'canonical_raw_rebuild.json').read_text())
    if not audit.get('passed') or not all(r['exact_equal'] for r in audit['comparisons'].values()):raise ValueError('Exact rebuild required')
    files=set(template['files'])
    files.update(BASE+f for f in ['player_fixture_observations.csv.gz','source_feature_matrix.csv.gz','sequence_feature_matrix.csv.gz','performance_feature_matrix.csv.gz','v2_baseline_feature_matrix.csv.gz','classified_starters.csv.gz','coverage_audit.json'])
    files.add(WORK+'historical_zero_membership_recovery.json')
    receipt=json.loads((ROOT/WORK/'publication_provenance.json').read_text())
    if receipt['cutoff']!=audit['cutoff'] or receipt['source_workflow']!=a.workflow:raise ValueError('Publication receipt mismatch')
    for f,digest in receipt['checksums'].items():
        if hashlib.sha256((ROOT/BASE/f).read_bytes()).hexdigest()!=digest:raise ValueError('Receipt checksum mismatch')
    buf=io.BytesIO();hashes={}
    with zipfile.ZipFile(buf,'w',zipfile.ZIP_DEFLATED,compresslevel=9) as z:
        for name in sorted(files):
            data=(ROOT/name).read_bytes();hashes[name]=hashlib.sha256(data).hexdigest()
            info=zipfile.ZipInfo(name,date_time=(2026,10,10,0,0,0));info.compress_type=zipfile.ZIP_DEFLATED
            z.writestr(info,data,compresslevel=9)
    data=buf.getvalue();a.out.mkdir(parents=True);parts=[]
    for index,start in enumerate(range(0,len(data),90000)):
        name=f'part-{index:03d}.b64';raw=data[start:start+90000];(a.out/name).write_text(base64.b64encode(raw).decode())
        parts.append({'file':name,'sha256':hashlib.sha256((a.out/name).read_bytes()).hexdigest()})
    manifest={'classification':'ORIGINAL_VFINAL_GW7_DIAGNOSTIC_NOT_FULL_CHAIN_CERTIFIED','cutoff':audit['cutoff'],'source_workflow':a.workflow,
        'source_checkpoint':'model/checkpoints/live_gw7_sources_20261010_v1','archive_sha256':hashlib.sha256(data).hexdigest(),'parts':parts,'files':hashes}
    (a.out/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n');print(json.dumps({'files':len(files),'parts':len(parts),'bytes':len(data),'archive_sha256':manifest['archive_sha256']}))
if __name__=='__main__':main()

#!/usr/bin/env python3
"""Restore/publish checksum-verified append-only diagnostic release snapshots."""
import argparse,hashlib,json,os,zipfile,urllib.request
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
SELECTOR=ROOT/'model/checkpoints/current-diagnostic.json'
PREFIXES=('work/live-final-model/','work/live-manager-validation/','data_v1_1/derived/live_locked_inputs/','data_v1_1/raw/','data_v1_1/derived/mm_v2_ratings/','data_v1_1/derived/team_news_audit/')
def digest(data):return hashlib.sha256(data).hexdigest()
def allowed(name):
    p=Path(name)
    return not p.is_absolute() and '..' not in p.parts and name.startswith(PREFIXES)
def restore():
    if not SELECTOR.exists():
        import sys
        sys.path.insert(0,str(ROOT/'scripts'))
        from restore_live_vfinal_checkpoint import restore as legacy
        legacy(ROOT/'model/checkpoints/live_vfinal_gw7_20261010_v2')
        legacy(ROOT/'model/checkpoints/live_tc_gw7_20261010_v1')
        return
    receipt=json.loads(SELECTOR.read_text());url=receipt['archive_url']
    expected='https://github.com/pdamkier-del/fpl-analytics-app/releases/download/'
    if not url.startswith(expected):raise ValueError('Untrusted checkpoint URL')
    data=urllib.request.urlopen(url,timeout=120).read()
    if digest(data)!=receipt['archive_sha256']:raise ValueError('Archive checksum mismatch')
    import io
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        if set(z.namelist())!=set(receipt['files']):raise ValueError('Archive file set mismatch')
        for name in z.namelist():
            if not allowed(name) or digest(z.read(name))!=receipt['files'][name]:raise ValueError('Unsafe or corrupt checkpoint member')
        for name in z.namelist():
            p=ROOT/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(z.read(name))
    print('Restored verified diagnostic snapshot',receipt['cutoff'])
def package():
    forecast=json.loads((ROOT/'app/vfinal-diagnostic.json').read_text())
    audit=json.loads((ROOT/'work/live-final-model/canonical_raw_rebuild.json').read_text())
    if not audit['passed'] or audit['cutoff']!=forecast['data_asof'] or forecast['locked_model_active'] is not False:raise ValueError('Invalid reproducibility gate')
    tag='diagnostic-'+os.environ['GITHUB_RUN_ID']+'-'+os.environ['GITHUB_RUN_ATTEMPT']
    path=ROOT/'work/diagnostic-snapshot.zip';files={}
    current_sources={s['path'] for s in json.loads((ROOT/'work/live-final-model/source_manifest.json').read_text())['sources']}
    with zipfile.ZipFile(path,'w',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
        for prefix in PREFIXES:
            for p in sorted((ROOT/prefix).rglob('*')):
                if p.is_file() and p.suffix not in ('.log',):
                    name=str(p.relative_to(ROOT))
                    if name.startswith('data_v1_1/raw/live-captures/') and name not in current_sources:continue
                    data=p.read_bytes();files[name]=digest(data);z.writestr(name,data)
    result=dict(classification='ORIGINAL_LOCKED_CHAIN_DIAGNOSTIC',locked_model_active=False,cutoff=forecast['data_asof'],origin_gw=forecast['gws'][0],source_workflow='https://github.com/'+os.environ['GITHUB_REPOSITORY']+'/actions/runs/'+os.environ['GITHUB_RUN_ID'],tag=tag,archive_url='https://github.com/pdamkier-del/fpl-analytics-app/releases/download/'+tag+'/diagnostic-snapshot.zip',archive_sha256=digest(path.read_bytes()),files=files)
    SELECTOR.parent.mkdir(parents=True,exist_ok=True);SELECTOR.write_text(json.dumps(result,indent=2)+'\n')
    out=ROOT/'model/checkpoints/releases'/tag/'manifest.json';out.parent.mkdir(parents=True,exist_ok=False);out.write_bytes(SELECTOR.read_bytes())
    print(tag)
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('operation',choices=['restore','package']);args=p.parse_args()
    restore() if args.operation=='restore' else package()

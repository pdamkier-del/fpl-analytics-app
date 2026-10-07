#!/usr/bin/env python3
"""Build the distributable FPL desktop app + data update.

Outputs:
  updates/app-<version>.zip
  updates/data-base.json.gz
  updates/manifest.json
  VERSION.txt
  DATA_VERSION.txt

The installed app already checks updates/manifest.json on main at startup.
"""
from __future__ import annotations
import argparse, gzip, hashlib, json, os, re, zipfile, subprocess, sys
from datetime import datetime, timezone
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
UPDATES=ROOT/'updates'

APP_FILES=[
    ROOT/'start_app.py',
]
APP_DIRS=[
    ROOT/'app',
]
MODEL_FILES=[
    ROOT/'model'/'engine.py',
    ROOT/'model'/'decision_optimizer.py',
]

def sha_bytes(raw:bytes)->str:
    return hashlib.sha256(raw).hexdigest()

def safe_version(value:str)->str:
    value=value.strip()
    if not re.fullmatch(r'[A-Za-z0-9._-]+',value):
        raise ValueError('Unsafe version string')
    return value

def read_json(path:Path):
    return json.loads(path.read_text(encoding='utf-8'))

def derive_data_version(base:dict,stamp:str)->str:
    meta=base.get('meta') or {}
    season=str(meta.get('season') or 'current').replace('/','-')
    gw=meta.get('next_gw')
    return f"{season}-gw{gw if gw is not None else 'x'}-{stamp}"

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--app-version')
    ap.add_argument('--data-version')
    ap.add_argument('--message',default='Published FPL model and website update')
    args=ap.parse_args()

    now=datetime.now(timezone.utc)
    stamp=now.strftime('%Y%m%dT%H%M%SZ')
    old=(ROOT/'VERSION.txt').read_text(encoding='utf-8').strip() if (ROOT/'VERSION.txt').exists() else '2.2'
    app_version=safe_version(args.app_version or f"{old}.{now.strftime('%Y%m%d%H%M')}")
    base_path=ROOT/'model'/'base_data.json'
    if not base_path.exists():
        raise FileNotFoundError(base_path)
    base_raw=base_path.read_bytes()
    base=read_json(base_path)
    data_version=safe_version(args.data_version or derive_data_version(base,stamp))

    # Capture the official FPL fixture schedule on every published update.\n    # This is the cutoff-safe source for when confirmed DGW/BGW information\n    # became visible to the model.\n    schedule_snapshot=ROOT/'scripts'/'snapshot_fpl_schedule.py'\n    if not schedule_snapshot.exists():\n        raise FileNotFoundError(schedule_snapshot)\n    subprocess.run([sys.executable,str(schedule_snapshot)],check=True,cwd=ROOT)\n\n    match_builder=ROOT/'scripts'/'build_match_centre_data.py'
    if match_builder.exists():
        subprocess.run([sys.executable,str(match_builder)],check=True,cwd=ROOT)

    UPDATES.mkdir(exist_ok=True)
    bundle=UPDATES/f'app-{app_version}.zip'
    with zipfile.ZipFile(bundle,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=9) as z:
        for p in APP_FILES+MODEL_FILES:
            if p.exists(): z.write(p,p.relative_to(ROOT).as_posix())
        for d in APP_DIRS:
            for p in sorted(d.rglob('*')):
                if p.is_file(): z.write(p,p.relative_to(ROOT).as_posix())

    compressed=gzip.compress(base_raw,compresslevel=9,mtime=0)
    data_file=UPDATES/'data-base.json.gz'
    data_file.write_bytes(compressed)
    bundle_raw=bundle.read_bytes()

    raw_base='https://raw.githubusercontent.com/pdamkier-del/fpl-analytics-app/main/updates'
    manifest={
        'app_version':app_version,
        'data_version':data_version,
        'published_utc':now.isoformat().replace('+00:00','Z'),
        'message':args.message,
        'app':{
            'url':f'{raw_base}/{bundle.name}',
            'sha256':sha_bytes(bundle_raw),
        },
        'data':{
            'url':f'{raw_base}/data-base.json.gz',
            'sha256':sha_bytes(compressed),
            'uncompressed_sha256':sha_bytes(base_raw),
        },
    }
    (UPDATES/'manifest.json').write_text(json.dumps(manifest,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    (ROOT/'VERSION.txt').write_text(app_version+'\n',encoding='utf-8')
    (ROOT/'DATA_VERSION.txt').write_text(data_version+'\n',encoding='utf-8')
    print(json.dumps(manifest,indent=2))
if __name__=='__main__':
    main()

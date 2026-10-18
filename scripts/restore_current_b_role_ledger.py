#!/usr/bin/env python3
"""Restore only checksum-verified public latent-role history; no manager data.

An absent first publication is explicit. Network errors, malformed documents,
and changed bytes fail closed rather than resetting a player's normal role.
"""
import argparse, gzip, hashlib, io, json
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import urlopen
import pandas as pd

BASE='https://pdamkier-del.github.io/fpl-analytics-app/mm-preview/current/'
ALLOWED={'season','fixture_uuid','player_uuid','team_id','gw','cutoff','pos','p','p_role','upstream_s','s','q','c','x','news_eligible','news_state','news_chance','news_medical_out','news_effective_at'}

def validate(index, packed):
    if index.get('model')!='B_locked_PM_preview' or index.get('locked_model_active') is not False:
        raise ValueError('Untrusted role ledger publication')
    if index.get('role_ledger_file')!='role-ledger.csv.gz' or hashlib.sha256(packed).hexdigest()!=index.get('role_ledger_sha256'):
        raise ValueError('Role ledger checksum mismatch')
    f=pd.read_csv(io.BytesIO(gzip.decompress(packed)))
    if set(f)!=ALLOWED or f.empty:raise ValueError('Unexpected public role ledger fields')
    cutoff=pd.to_datetime(f.cutoff,utc=True,format='mixed')
    if cutoff.isna().any() or (cutoff>pd.Timestamp(index['data_asof'])).any():raise ValueError('Role ledger contains future state')
    if f.duplicated(['season','fixture_uuid','player_uuid','cutoff']).any():raise ValueError('Duplicate role state')
    for col in ['p','p_role','q']:
        if not pd.to_numeric(f[col],errors='coerce').between(0,1).all():raise ValueError('Invalid role probability')
    for col in ['s','upstream_s','c','x']:
        if not pd.to_numeric(f[col],errors='coerce').between(-1e-10,90+1e-10).all():raise ValueError('Invalid role duration')
    return f

def restore(out,base=BASE):
    out=Path(out)
    # A stale work file must never masquerade as the response to this request.
    if out.exists():out.unlink()
    try:
        with urlopen(base+'index.json',timeout=60) as r:index=json.load(r)
    except HTTPError as e:
        if e.code!=404:raise
        print('No previous current B publication; pre-injury latent state remains unknown')
        return False
    if 'role_ledger_sha256' not in index:
        raise ValueError('Existing B publication has no verifiable role ledger')
    with urlopen(base+'role-ledger.csv.gz',timeout=60) as r:packed=r.read()
    frame=validate(index,packed)
    out.parent.mkdir(parents=True,exist_ok=True);out.write_bytes(packed)
    print(json.dumps(dict(role_ledger_rows=len(frame),sha256=hashlib.sha256(packed).hexdigest())))
    return True

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--out',type=Path,default=Path('work/previous-B-role-ledger.csv.gz'));a=p.parse_args();restore(a.out)

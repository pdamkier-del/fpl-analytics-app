#!/usr/bin/env python3
"""Publish only verified current B/locked-PM outputs to the isolated preview.

Never copies manager results or experimental interval estimates into the app.
Source inputs and p/q/s/c remain archived for later rotation-risk analysis.
"""
from pathlib import Path
from datetime import datetime,timezone
import argparse,gzip,hashlib,json
from mm_candidate_forecast import seal_document
from fpl_v1_1_model.forecast_snapshot import require_snapshot,require_official_catalog
from restore_current_b_role_ledger import validate as validate_ledger
ROOT=Path(__file__).resolve().parents[1]

def write(path,obj):
    b=json.dumps(obj,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False).encode()+b'\n'
    path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(b)
    return hashlib.sha256(b).hexdigest()

def publish(source,out,inputs=ROOT/'work/current-B-inputs'):
    source=Path(source);out=Path(out)
    f=json.loads((source/'forecast.json').read_text());m=json.loads((source/'mm.json').read_text());audit=json.loads((source/'pm-audit.json').read_text())
    require_snapshot(f)
    now=datetime.now(timezone.utc)
    if f.get('scope')!='prospective_preview' or f.get('model')!='B_locked_PM_preview' or f.get('locked_model_active') is not False:
        raise ValueError('Current B preview contract required')
    if f.get('minute_sampler_audit',{}).get('sampler')!='locked':raise ValueError('Only the locked PM sampler may be published')
    if now>=datetime.fromisoformat(f['origin_deadline'].replace('Z','+00:00')):raise ValueError('Preview deadline expired')
    if seal_document(m)['content_sha256']!=m.get('content_sha256'):raise ValueError('MM checksum mismatch')
    if not audit.get('point_components_reconciled'):raise ValueError('PM point components do not reconcile')
    mmkeys={(r['fixture_id'],r['player_id']) for r in m['players']}
    expected={(x['fixture_uuid'],p['player_uuid']) for p in f['players'] for w in p['weeks'] for x in w['fixtures']}
    if mmkeys!=expected:raise ValueError('Public MM and PM identity coverage mismatch')
    bootstrap=json.loads((Path(inputs)/'bootstrap.json').read_text())
    provenance=json.loads((Path(inputs)/'provenance.json').read_text())
    raw=json.dumps(bootstrap,sort_keys=True,separators=(',',':'),allow_nan=False).encode()
    if hashlib.sha256(raw).hexdigest()!=provenance['bootstrap_sha256']:raise ValueError('Official catalogue source changed')
    require_official_catalog(f,bootstrap['elements'])
    next_gw=next(e['id'] for e in bootstrap['events'] if e.get('is_next'))
    if next_gw!=f['gws'][0]:raise ValueError('Official catalogue GW mismatch')
    catalogue=dict(source='Official FPL snapshot used by this forecast',fetched_at=provenance['bootstrap_observed_at'],next_gw=next_gw,
        players=[dict(id=p['id'],team=p['team'],position=p['element_type'],price=p['now_cost']/10) for p in bootstrap['elements']])
    # Probabilities of start/appearance remain; unvalidated duration intervals
    # and PMF bands are not presented as quantitative live uncertainty.
    for r in m['players']:
        for key in ['minute_pmf','minute_probabilities','interval80']:r.pop(key,None)
        r['p_play']=r['p_start']+(1-r['p_start'])*r['p_sub_given_not_start']
        r['uncertainty_status']='Not Available: duration intervals are not independently calibrated and validated'
    m=seal_document(m)
    index=dict(scope='prospective_preview',model='B_locked_PM_preview',locked_model_active=False,
        data_asof=f['data_asof'],origin_deadline=f['origin_deadline'],gws=f['gws'],players=len(f['players']),fixtures=f['fixtures'],
        forecast_sha256=f['forecast_sha256'],forecast_file='forecast.json',mm_file='mm.json',
        forecast_file_sha256=write(out/'forecast.json',f),mm_file_sha256=write(out/'mm.json',m),
        uncertainty_intervals_validated=False,minute_sampler='locked',
        status='diagnostic_not_certified',risk_inputs_archived=True,TS_risk_parameters_changed=False)
    ledger=(Path(inputs)/'role-ledger.csv.gz').read_bytes()
    index['role_ledger_file']='role-ledger.csv.gz'
    index['role_ledger_sha256']=hashlib.sha256(ledger).hexdigest()
    index['role_ledger_rows']=len(validate_ledger(index,ledger))
    (out/'role-ledger.csv.gz').write_bytes(ledger)
    index['catalogue_file']='catalogue.json'
    index['catalogue_sha256']=write(out/'catalogue.json',catalogue)
    write(out/'pm-audit.json',audit)
    write(out/'index.json',index)
    packed=gzip.compress((source/'mm.json').read_bytes(),mtime=0)
    archive=out/'history'/(f['forecast_sha256']+'.mm.json.gz');archive.parent.mkdir(exist_ok=True)
    if archive.exists() and archive.read_bytes()!=packed:raise ValueError('Immutable MM evidence differs')
    archive.write_bytes(packed)
    print(json.dumps(index,indent=2));return index
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--source',type=Path,default=ROOT/'work/current-B-output');p.add_argument('--out',type=Path,default=ROOT/'app/mm-preview/current');p.add_argument('--inputs',type=Path,default=ROOT/'work/current-B-inputs');a=p.parse_args();publish(a.source,a.out,a.inputs)

"""Permanent public forecast bundles, using the existing producer and C2 freeze.

No model calls. Public-only inputs. Original JSON bytes survive in deterministic
gzip files. Strict live capture; historical inputs are never backdated.
"""
import argparse
from datetime import datetime, timezone
import fcntl
import gzip
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import re
import shutil
import tempfile

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('existing_c2_freeze', ROOT/'integration/model-interface/freeze_forecast.py')
existing = importlib.util.module_from_spec(spec)
spec.loader.exec_module(existing)
PIN = '161b67b6fb8786a38e78c245b92a03ad841575d8'
WEIGHTS = [1., .6, .36, .216, .1296, .07776]
FORBIDDEN = {'manager_state','manager_id','entry_id','bank_tenths','purchase_price_tenths',
             'free_transfers','chips_used','password','token','authorization','cookie',
             'access_token','refresh_token','api_key','private_nonce','squad'}


def canonical(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, allow_nan=False,
                      separators=(',', ':')).encode()


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def clock(value):
    result = datetime.fromisoformat(value.replace('Z','+00:00'))
    if result.tzinfo is None:
        raise ValueError('Timezone required')
    return result.astimezone(timezone.utc)


def require(condition, reason):
    if not condition:
        raise ValueError(reason)


def public_only(value):
    if isinstance(value, dict):
        require(not (set(map(str.lower,value)) & FORBIDDEN), 'Private/credential field in public input')
        for item in value.values():
            public_only(item)
    elif isinstance(value, list):
        for item in value:
            public_only(item)


def validate(current, config, *, now, model_commit, sources, computation):
    raw = {}
    docs = {}
    for name in ['index.json','forecast.json','mm.json','catalogue.json']:
        p = current/name
        require(p.is_file() and not p.is_symlink(), 'Missing or redirected public input')
        raw[name] = p.read_bytes()
        docs[name] = json.loads(raw[name])
        public_only(docs[name])
    i,f,m,c = (docs[n] for n in ['index.json','forecast.json','mm.json','catalogue.json'])
    require(model_commit == PIN, 'Unreviewed model source')
    require(f.get('model') == i.get('model') == 'B-MM-PM-TS-v1', 'Wrong chain')
    require(f.get('forecast_sha256') == sha(canonical({k:v for k,v in f.items() if k!='forecast_sha256'})), 'Forecast content changed')
    require(i.get('forecast_sha256') == f['forecast_sha256'], 'Index identity mismatch')
    for name,key in [('forecast.json','forecast_file_sha256'),('mm.json','mm_file_sha256'),('catalogue.json','catalogue_sha256')]:
        require(i.get(key) == sha(raw[name]), 'Public file checksum mismatch')
    for name,key in [('forecast.json','forecast_file'),('mm.json','mm_file'),('catalogue.json','catalogue_file')]:
        require(i.get(key) == name, 'Unexpected public input filename')
    require(m.get('model_version') == f['model'], 'MM model mismatch')
    require(clock(m['data_at']) == clock(f['data_asof']) and clock(m['origin_deadline']) == clock(f['origin_deadline']), 'MM issue mismatch')
    mm_bytes=json.dumps({k:v for k,v in m.items() if k!='content_sha256'},sort_keys=True,separators=(',',':'),allow_nan=False).encode()
    require(m.get('content_sha256') == sha(mm_bytes), 'MM content changed')
    require(clock(i['data_asof']) == clock(f['data_asof']) and clock(i['origin_deadline']) == clock(f['origin_deadline']), 'Index clock mismatch')
    require(clock(f['data_asof']) <= now < clock(f['origin_deadline']), 'Capture is not before deadline')
    require(computation.get('schema')=='fpl-computation-witness/v1' and computation.get('numerical_source')==PIN, 'Missing producer identity')
    require(clock(f['data_asof'])<=clock(computation['producer_completed_at'])<=now, 'Computation clock mismatch')
    require(clock(computation['producer_started_at'])<=clock(computation['producer_completed_at']), 'Invalid producer interval')
    gws = f.get('gws', [])
    require(gws and type(gws[0]) is int and 1<=gws[0]<=38 and gws == list(range(gws[0],min(39,gws[0]+6))), 'Incomplete six-GW horizon')
    require(i.get('gws') == gws and c.get('next_gw') == gws[0], 'Origin/horizon mismatch')
    require(f.get('code_sha256') and f.get('input_sha256'), 'Missing code/input hashes')
    require(config == json.loads((Path(__file__).parent/'frozen-ts-config.json').read_text()), 'TS configuration changed')
    require(config.get('weights') == WEIGHTS and config.get('hit_uncertainty_buffer') == 1. and config.get('discount_transfer_costs') is False, 'Not the frozen TS configuration')
    public_only(config)
    n = f.get('scenario_contract',{}).get('draws')
    require(type(n) is int and n>0 and f['scenario_contract'].get('version')=='shared-PM-match-draws-v1', 'Missing shared scenarios')
    players = f.get('players', [])
    require(players and len({p['id'] for p in players}) == len(players), 'Duplicate/missing players')
    require(len({p['player_uuid'] for p in players}) == len(players), 'Duplicate stable player identities')
    catalog = {p['id']:p for p in c['players']}
    require(len(catalog)==len(c['players']) and set(catalog)=={p['id'] for p in players}, 'Catalogue roster mismatch')
    mmkeys = [(r['player_id'],r['fixture_id']) for r in m['players']]
    require(len(mmkeys)==len(set(mmkeys)), 'Duplicate MM identities')
    keys = set()
    for p in players:
        cp = catalog[p['id']]
        require((cp['team'],cp['position'],round(cp['price']*10)) == (p['team_id'],p['position'],p['price_tenths']), 'Catalogue attributes mismatch')
        require([w['gw'] for w in p['weeks']] == gws, 'Missing/duplicated player GW')
        for w in p['weeks']:
            samples = w.get('scenarios',{})
            pts,mins = samples.get('points',[]),samples.get('minutes',[])
            require(len(pts)==len(mins)==n and all(type(x) in (float,int) and math.isfinite(x) for x in pts+mins), 'Invalid scenario arrays')
            require(abs(sum(pts)/n-w['xpts'])<1e-7, 'Scenario/xP mismatch')
            # Preserve the producer's analytic minute mean; finite draws need not equal it.
            require(abs(w['xmins']-w['pm_analytic_minutes'])<1e-7, 'MM/PM analytic mean mismatch')
            require(all(0<=v<=90*len(w['fixtures']) for v in mins), 'Invalid minutes/blank GW')
            require(all(v!=0 or pts[j]==0 for j,v in enumerate(mins)), 'Points without appearance')
            require(len({x['fixture_uuid'] for x in w['fixtures']})==len(w['fixtures']), 'Duplicate fixture in GW')
            for match in w['fixtures']:
                key = (p['player_uuid'],match['fixture_uuid'])
                require(key not in keys, 'Duplicate player fixture')
                keys.add(key)
    require(keys==set(mmkeys), 'MM/PM fixture coverage mismatch')
    mm_by_key={(r['player_id'],r['fixture_id']):r for r in m['players']}
    for p in players:
        for w in p['weeks']:
            for match in w['fixtures']:
                require(abs(mm_by_key[p['player_uuid'],match['fixture_uuid']]['xmins']-match['xmins'])<1e-7, 'MM fixture mean differs from PM input')
    for name in ['bootstrap.json','fixtures.json','provenance.json']:
        path=sources/name
        require(path.is_file() and not path.is_symlink(), 'Original official source missing')
        value=path.read_bytes();public_only(json.loads(value));raw['official-'+name]=value
    bootstrap=json.loads(raw['official-bootstrap.json'])
    provenance=json.loads(raw['official-provenance.json'])
    # Forecast input hashes cover bytes; provenance covers canonical official responses.
    require(sha(raw['official-bootstrap.json'])==f['input_sha256'].get('bootstrap.json'), 'Original bootstrap differs')
    require(sha(raw['official-provenance.json'])==f['input_sha256'].get('provenance.json'), 'Original provenance differs')
    require(sha(canonical(json.loads(raw['official-fixtures.json'])))==provenance.get('fixtures_sha256'), 'Original fixture source differs')
    events={r['id']:r for r in bootstrap['events']}
    require(clock(events[gws[0]]['deadline_time'])==clock(f['origin_deadline']), 'Deadline is not official')
    elements={r['id']:r for r in bootstrap['elements']}
    require(set(elements)==set(catalog), 'Original official roster differs')
    return raw, f, keys


def bundle(current, destination, config, *, sources, computation, model_commit=PIN, now=None):
    now = now or datetime.now(timezone.utc)
    raw,f,keys = validate(current,config,now=now,model_commit=model_commit,sources=sources,computation=computation)
    destination.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=destination) as temporary:
        temp = Path(temporary)
        reference = existing.freeze(current,temp/'reference',model_commit)
        files = {name+'.gz':gzip.compress(value,mtime=0) for name,value in raw.items()}
        files['frozen-reference.json'] = (reference/'manifest.json').read_bytes()
        files['ts-config.json'] = canonical(config)
        files['computation-receipt.json'] = canonical(computation)
        identities = dict(season=f['season'],origin_gw=f['gws'][0],gws=f['gws'],
                          forecast_sha256=f['forecast_sha256'],model_source=model_commit,
                          files={name:sha(value) for name,value in files.items()})
        revision = sha(canonical(identities))
        manifest = dict(schema='fpl-permanent-public-forecast/v1',revision_id=revision,
                        **identities, data_cutoff=f['data_asof'],official_deadline=f['origin_deadline'],
                        captured_at=now.isoformat(),publication_at=None,
                        forecast_origin_at=f['data_asof'],computation_completed_by=computation['producer_completed_at'],
                        computation_time_basis=computation['clock_basis'],
                        publication_status='pending_external_release_receipt',
                        model_versions=dict(mm=f['mm_version'],pm=f.get('parts',{}).get('pm_vfinal','PM vFinal'),ts='TS v3'),
                        code_sha256=f['code_sha256'],input_sha256=f['input_sha256'],
                        raw_sha256={name:sha(value) for name,value in raw.items()},
                        player_fixture_rows=len(keys),shared_scenarios=f['scenario_contract'],
                        eligible_only_with_verified_predeadline_publication=True)
        target = destination/revision
        stage = temp/'bundle';stage.mkdir()
        for name,value in files.items():
            with (stage/name).open('wb') as handle:
                handle.write(value);handle.flush();os.fsync(handle.fileno())
        with (stage/'manifest.json').open('wb') as handle:
            handle.write(canonical(manifest));handle.flush();os.fsync(handle.fileno())
        with (destination/'.lock').open('a') as lock:
            fcntl.flock(lock,fcntl.LOCK_EX)
            if target.exists():
                old = verify(target)
                require(all(old[k]==manifest[k] for k in identities), 'Existing revision differs')
            else:
                os.rename(stage,target)
            fd=os.open(destination,os.O_RDONLY)
            try:os.fsync(fd)
            finally:os.close(fd)
        return target


def verify(folder):
    require(not folder.is_symlink(), 'Redirected archive')
    manifest = json.loads((folder/'manifest.json').read_bytes())
    identities = {k:manifest[k] for k in ['season','origin_gw','gws','forecast_sha256','model_source','files']}
    require(sha(canonical(identities))==manifest['revision_id'], 'Revision identity changed')
    require(set(p.name for p in folder.iterdir())=={'manifest.json',*manifest['files']}, 'Unexpected/missing archive files')
    for name,h in manifest['files'].items():
        require(Path(name).name==name and not (folder/name).is_symlink(), 'Unsafe archive path')
        raw=(folder/name).read_bytes()
        require(sha(raw)==h, 'Archived bytes changed')
        if name.endswith('.gz'):
            require(sha(gzip.decompress(raw))==manifest['raw_sha256'][name[:-3]], 'Original bytes changed')
    forecast=json.loads(gzip.decompress((folder/'forecast.json.gz').read_bytes()))
    require(forecast['forecast_sha256']==sha(canonical({k:v for k,v in forecast.items() if k!='forecast_sha256'})), 'Archived forecast seal changed')
    for key,source in [('forecast_sha256','forecast_sha256'),('season','season'),('gws','gws'),('data_cutoff','data_asof'),('official_deadline','origin_deadline')]:
        require(manifest[key]==forecast[source], 'Archive metadata differs from original forecast')
    require(clock(manifest['data_cutoff'])<=clock(manifest['captured_at'])<clock(manifest['official_deadline']), 'Invalid archive clock')
    return manifest


def match_final(folder, fixtures, outcomes, events):
    """Exact fixture/element join; no latest-club/name or GW-only joins."""
    verify(folder)
    f=json.loads(gzip.decompress((folder/'forecast.json.gz').read_bytes()))
    fx={r['id']:r for r in fixtures}
    require(len(fx)==len(fixtures), 'Duplicate official fixtures')
    ev={r['id']:r for r in events}
    require(len(ev)==len(events), 'Duplicate official events')
    actual={(r['fixture'],r['element']):r for r in outcomes}
    require(len(actual)==len(outcomes), 'Duplicate official outcomes')
    matched=[]
    for p in f['players']:
        for w in p['weeks']:
            for item in w['fixtures']:
                identity=item['fixture_uuid']
                prefix='live-'+f['season']+'-fpl-'
                require(identity.startswith(prefix), 'Fixture mapping needs explicit adapter')
                fixture=int(identity[len(prefix):]);official=fx.get(fixture)
                require(official is not None and official.get('finished') is True and official.get('finished_provisional') is True, 'Official final fixture unavailable')
                event=ev.get(official.get('event'),{})
                require(event.get('finished') is True and event.get('data_checked') is True, 'Official event final/checked label unavailable')
                label=actual.get((fixture,p['id']))
                require(label is not None, 'Missing official player result')
                matched.append(dict(player_uuid=p['player_uuid'],player_id=p['id'],fixture_uuid=identity,
                                    origin_gw=f['gws'][0],forecast_target_gw=w['gw'],
                                    actual_event=official.get('event'),forecast=item,actual=label))
    return matched


if __name__=='__main__':
    p=argparse.ArgumentParser(__doc__)
    p.add_argument('current',type=Path);p.add_argument('destination',type=Path)
    p.add_argument('--config',required=True,type=Path)
    p.add_argument('--sources',required=True,type=Path)
    p.add_argument('--computation-receipt',required=True,type=Path)
    a=p.parse_args()
    print(bundle(a.current,a.destination,json.loads(a.config.read_text()),sources=a.sources,
                 computation=json.loads(a.computation_receipt.read_text())))

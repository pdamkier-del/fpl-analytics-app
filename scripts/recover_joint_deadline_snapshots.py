"""Recover immutable predeadline bootstrap bytes selected from Randdalf/fplcache.

Raw compressed bytes are verified against Git blob SHA and packed losslessly.
The official event deadline must match the frozen diagnostic cutoff exactly.
No Core tables or old forecast/results files are modified.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor
import gzip
import hashlib
import io
import json
import lzma
from pathlib import Path
import sqlite3
import urllib.request

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def download(row):
    url = 'https://raw.githubusercontent.com/Randdalf/fplcache/'+row['source_commit']+'/cache/2026/'+row['path']
    raw = urllib.request.urlopen(url, timeout=40).read()
    git_sha = hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest()
    if len(raw) != row['size'] or git_sha != row['sha']:
        raise ValueError('Source blob mismatch GW'+str(row['gw']))
    j = json.loads(lzma.decompress(raw))
    event = next(e for e in j['events'] if e['id'] == row['gw'])
    if pd.Timestamp(event['deadline_time']) != pd.Timestamp(row['cutoff']):
        raise ValueError('Official deadline differs from frozen cutoff GW'+str(row['gw']))
    if pd.Timestamp(row['published_at']) >= pd.Timestamp(event['deadline_time']):
        raise ValueError('Snapshot publication is not before deadline')
    return row, raw, j, url


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--selection', type=Path, default=ROOT/'analysis/results/joint-deadline-snapshot-selection-v1/selection.json')
    ap.add_argument('--db', type=Path, default=ROOT/'work/core.sqlite3')
    ap.add_argument('--out', type=Path, default=ROOT/'analysis/results/joint-deadline-snapshots-v1')
    a = ap.parse_args()
    if a.out.exists():
        raise FileExistsError('Use a new immutable output directory')
    selection = json.loads(a.selection.read_text())
    with ThreadPoolExecutor(max_workers=3) as pool:
        recovered = list(pool.map(download, selection['snapshots']))
    con = sqlite3.connect(a.db.resolve().as_uri()+'?mode=ro', uri=True)
    mappings = pd.read_sql_query("SELECT DISTINCT player_uuid,external_id FROM player_id_mapping WHERE id_namespace='fpl_element' AND season='2025-26'", con)
    if mappings.external_id.duplicated().any() or mappings.player_uuid.duplicated().any():
        raise ValueError('Nonunique season-specific player identity')
    mapping = dict(zip(mappings.external_id.astype(int), mappings.player_uuid))
    codes = pd.read_sql_query("SELECT DISTINCT player_uuid,external_id FROM player_id_mapping WHERE id_namespace='fpl_code'", con)
    code_map = codes.groupby('player_uuid').external_id.apply(lambda x:set(x.astype(int))).to_dict()
    con.close()
    a.out.mkdir(parents=True)
    sources = []; states = []; events = []
    for row, raw, j, url in recovered:
        parts = []
        for i, start in enumerate(range(0, len(raw), 32768)):
            data = raw[start:start+32768]; path = f"gw{row['gw']:02d}.json.xz.part-{i:04d}"
            (a.out/path).write_bytes(data)
            parts.append(dict(path=path, bytes=len(data), sha256=sha(data)))
        sources.append(dict(gw=row['gw'],source_url=url,source_commit=row['source_commit'],
            blob_sha=row['sha'],published_at=row['published_at'],cutoff=row['cutoff'],
            bytes=len(raw),sha256=sha(raw),json_sha256=sha(lzma.decompress(raw)),parts=parts,
            snapshot_age_hours=(pd.Timestamp(row['cutoff'])-pd.Timestamp(row['published_at'])).total_seconds()/3600))
        ids=set()
        for e in j['elements']:
            if e['id'] in ids:
                raise ValueError('Duplicate FPL element')
            ids.add(e['id']); pid=mapping.get(e['id'])
            if pid is not None and int(e['code']) not in code_map.get(pid, set()):
                raise ValueError('FPL element/code identity disagreement')
            states.append(dict(gw=row['gw'],cutoff=row['cutoff'],observed_at=row['published_at'],
                player_uuid=pid,fpl_element_id=e['id'],fpl_code=e['code'],team_id=e['team'],
                position={1:'GK',2:'DEF',3:'MID',4:'FWD'}.get(e['element_type'],'OTHER'),
                price_tenths=e['now_cost'],status_code=e['status'],
                chance_this_round=e.get('chance_of_playing_this_round'),
                chance_next_round=e.get('chance_of_playing_next_round'),
                web_name=e['web_name'],source_blob_sha=row['sha']))
        for e in j['events']:
            events.append(dict(snapshot_gw=row['gw'],observed_at=row['published_at'],
                event_id=e['id'],deadline_time=e['deadline_time'],source_blob_sha=row['sha']))
    outputs = []
    for name, frame in [('states',pd.DataFrame(states)),('events',pd.DataFrame(events))]:
        raw=frame.to_csv(index=False,lineterminator='\n').encode(); packed=gzip.compress(raw,mtime=0);parts=[]
        for i,start in enumerate(range(0,len(packed),32768)):
            data=packed[start:start+32768];path=f'{name}.csv.gz.part-{i:04d}'
            (a.out/path).write_bytes(data);parts.append(dict(path=path,bytes=len(data),sha256=sha(data)))
        outputs.append(dict(name=name,rows=len(frame),uncompressed_sha256=sha(raw),compressed_sha256=sha(packed),parts=parts))
    manifest=dict(season='2025-26',classification='reused_diagnostic_state_recovery',
        source_repository='Randdalf/fplcache',source_head=selection['source_head'],source_tree=selection['source_tree'],
        sources=sources,outputs=outputs,code_sha256=sha(Path(__file__).read_bytes()),
        selection_sha256=sha(a.selection.read_bytes()),mapped_state_rows=sum(x['player_uuid'] is not None for x in states),
        unmapped_state_rows=sum(x['player_uuid'] is None for x in states),
        interpretation='FPL-listing/team/position/price/status evidence, not authoritative matchday availability or legal registration',
        unchanged='Core database, frozen component forecasts, adapter, simulator, transfer/chip policy and old paired diagnostic')
    (a.out/'manifest.json').write_text(json.dumps(manifest,indent=2,sort_keys=True)+'\n')
    print(json.dumps({k:manifest[k] for k in ['mapped_state_rows','unmapped_state_rows']},indent=2))


if __name__ == '__main__':
    main()

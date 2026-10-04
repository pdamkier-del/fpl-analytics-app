"""Verify recovered original bootstrap streams and their predeadline projection."""
import argparse
import hashlib
import json
import lzma
from pathlib import Path

import pandas as pd

from fpl_v1_1_model.paired_joint import read_frozen_table

ROOT=Path(__file__).resolve().parents[1]


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--report',type=Path,default=ROOT/'work/joint-deadline-integrity.json')
    a=ap.parse_args();folder=ROOT/'analysis/results/joint-deadline-snapshots-v1'
    m=json.loads((folder/'manifest.json').read_text());checks=0
    selected=json.loads((ROOT/'analysis/results/joint-deadline-snapshot-selection-v1/selection.json').read_text())
    if sha((ROOT/'scripts/recover_joint_deadline_snapshots.py').read_bytes())!=m['code_sha256']:
        raise ValueError('Recovery code changed')
    if sha((ROOT/'analysis/results/joint-deadline-snapshot-selection-v1/selection.json').read_bytes())!=m['selection_sha256']:
        raise ValueError('Source selection changed')
    checks+=2
    states=read_frozen_table(folder,'states');events=read_frozen_table(folder,'events')
    for e in m['outputs']:
        checks+=len(e['parts'])+2
    for source in m['sources']:
        chunks=[]
        for p in source['parts']:
            path=(folder/p['path']).resolve()
            if not path.is_relative_to(folder.resolve()):
                raise ValueError('Invalid raw part path')
            raw=path.read_bytes();checks+=1
            if len(raw)!=p['bytes'] or sha(raw)!=p['sha256']:
                raise ValueError('Raw snapshot part changed')
            chunks.append(raw)
        raw=b''.join(chunks);text=lzma.decompress(raw);j=json.loads(text)
        if len(raw)!=source['bytes'] or sha(raw)!=source['sha256'] or sha(text)!=source['json_sha256']:
            raise ValueError('Original stream changed')
        if hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest()!=source['blob_sha']:
            raise ValueError('Original Git blob changed')
        checks+=2
        row=next(x for x in selected['snapshots'] if x['gw']==source['gw'])
        if row['sha']!=source['blob_sha'] or row['published_at']!=source['published_at'] or row['source_commit']!=source['source_commit']:
            raise ValueError('Source metadata differs from frozen selection')
        event=next(e for e in j['events'] if e['id']==source['gw'])
        if pd.Timestamp(event['deadline_time'])!=pd.Timestamp(source['cutoff']) or pd.Timestamp(source['published_at'])>=pd.Timestamp(source['cutoff']):
            raise ValueError('Deadline/source time mismatch')
        checks+=2
        s=states[states.gw==source['gw']].set_index('fpl_element_id')
        if len(s)!=len(j['elements']) or not s.index.is_unique or s.player_uuid.isna().any():
            raise ValueError('Incomplete/nonunique player projection')
        for e in j['elements']:
            projected=s.loc[e['id']]
            if int(projected.fpl_code)!=e['code'] or int(projected.team_id)!=e['team'] or int(projected.price_tenths)!=e['now_cost'] or projected.status_code!=e['status']:
                raise ValueError('Projected player state changed')
            checks+=1
        ev=events[events.snapshot_gw==source['gw']].set_index('event_id')
        for e in j['events']:
            if pd.Timestamp(ev.loc[e['id'],'deadline_time'])!=pd.Timestamp(e['deadline_time']):
                raise ValueError('Projected deadline changed')
            checks+=1
    report=dict(integrity_passed=True,checks=checks,snapshots=len(m['sources']),
        mapped_state_rows=len(states),official_deadlines_match_frozen_cutoffs=True,
        source_publication_before_cutoff=True,full_roster_replay_ready=False,
        limitation='Predeadline FPL snapshot recovery; does not fill component forecasts or establish a complete physical matchday roster')
    a.report.parent.mkdir(parents=True,exist_ok=True)
    a.report.write_text(json.dumps(report,indent=2,sort_keys=True)+'\n')
    print(json.dumps(report,indent=2))


if __name__=='__main__':
    main()

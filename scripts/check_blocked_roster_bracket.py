"""Check persisted source-gap evidence without changing forecast eligibility."""
import hashlib,json,lzma
from pathlib import Path
import pandas as pd
from fpl_v1_1_model.paired_joint import read_frozen_table
ROOT=Path(__file__).resolve().parents[1]
def main():
    out=ROOT/'analysis/results/blocked-roster-bracket-v1';m=json.loads((out/'manifest.json').read_text());checks=0
    for path,key in [(ROOT/'analysis/results/blocked-roster-source-index-v1/manifest.json','source_inventory_manifest_sha256'),(out/'publication.json','publication_metadata_sha256')]:
        assert hashlib.sha256(path.read_bytes()).hexdigest()==m[key];checks+=1
    for item in m['outputs']:
        assert hashlib.sha256((out/item['path']).read_bytes()).hexdigest()==item['sha256'];checks+=1
    assert hashlib.sha256((ROOT/'scripts/audit_blocked_roster_near_deadline.py').read_bytes()).hexdigest()==m['code_sha256'];checks+=1
    sources={}
    for source in m['sources']:
        chunks=[]
        for part in source['parts']:
            raw=(out/part['path']).read_bytes();assert len(raw)==part['bytes'] and hashlib.sha256(raw).hexdigest()==part['sha256'];chunks.append(raw);checks+=1
        raw=b''.join(chunks)
        assert len(raw)==source['bytes'] and hashlib.sha256(raw).hexdigest()==source['sha256']
        assert hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest()==source['blob_sha']
        elements=json.loads(lzma.decompress(raw))['elements'];assert len({e['id'] for e in elements})==len(elements)
        sources[source['blob_sha']]={e['id']:e for e in elements};checks+=3
    e=pd.read_csv(out/'blocked_rows.csv');b=read_frozen_table(ROOT/'analysis/results/deadline-player-components-v1','blocked_roster');keys=['fixture_uuid','player_uuid']
    assert not e[keys].duplicated().any() and e[keys].merge(b[keys],on=keys,how='outer',indicator=True)._merge.eq('both').all();checks+=1
    states=read_frozen_table(ROOT/'analysis/results/joint-deadline-snapshots-v1','states')
    for r in e.itertuples():
        assert pd.Timestamp(r.last_predeadline_at)<pd.Timestamp(r.cutoff)<pd.Timestamp(r.nearest_post_nominal_at)
        assert not ((states.gw==r.gw)&(states.player_uuid==r.player_uuid)).any()
        assert bool(r.present_nearest_post)==(r.fpl_element_id in sources[r.nearest_post_blob])
        if pd.notna(r.first_observed_post_blob):
            assert pd.Timestamp(r.first_observed_post_nominal_at)>pd.Timestamp(r.cutoff)
            x=sources[r.first_observed_post_blob][r.fpl_element_id]
            assert x['team']==r.observed_post_team and {1:'GK',2:'DEF',3:'MID',4:'FWD'}[x['element_type']]==r.observed_post_position
        assert r.resolution=='still_blocked_no_predeadline_listing_evidence';checks+=1
    publication=json.loads((out/'publication.json').read_text()) if (out/'publication.json').exists() else []
    for p in publication:
        source=next(s for s in m['sources'] if s['path']==p['path'])
        target=e[e.gw==source['gw']].cutoff.iloc[0]
        assert pd.Timestamp(p['published_at'])>pd.Timestamp(target);checks+=1
    prior=ROOT/'analysis/results/deadline-joint-paired-diagnostic-v1'
    old=json.loads((prior/'verification.json').read_text())
    for p in old['policy_checks']:
        assert hashlib.sha256((ROOT/p['path']).read_bytes()).hexdigest()==p['sha256'];checks+=1
    diagnostic=json.loads((prior/'manifest.json').read_text())
    for s in diagnostic['code']:
        assert hashlib.sha256((ROOT/s['path']).read_bytes()).hexdigest()==s['sha256'];checks+=1
    read_frozen_table(prior,'predictions');checks+=1
    report=dict(integrity_passed=True,checks=checks,blocked_rows=len(e),unique_players=int(e.player_uuid.nunique()),
        recovered_predeadline_rows=0,full_period_ready=False,forecast_or_policy_changes=False,
        postdeadline_sources_publication_verified=len(publication),retained_sources=len(m['sources']),
        original_paired_prediction_checksum_verified=True)
    (out/'verification.json').write_text(json.dumps(report,indent=2,sort_keys=True)+'\n');print(json.dumps(report,indent=2))
if __name__=='__main__':main()

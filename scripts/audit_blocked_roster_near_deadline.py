"""Bracket blocked FPL listings with pinned cache bytes; never promote future state."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import hashlib,json,lzma,sqlite3,urllib.request
from pathlib import Path
import pandas as pd
from fpl_v1_1_model.paired_joint import read_frozen_table
ROOT=Path(__file__).resolve().parents[1]
HEAD='17e703acd4f744931afa9d1d90a2998cfb104286'
def digest(raw):return hashlib.sha256(raw).hexdigest()
def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--trees',type=Path,default=ROOT/'work/roster-gap-source/trees.json')
    ap.add_argument('--out',type=Path,default=ROOT/'analysis/results/blocked-roster-bracket-v1')
    a=ap.parse_args()
    if a.out.exists():raise FileExistsError('Use a new immutable output directory')
    blocked=read_frozen_table(ROOT/'analysis/results/deadline-player-components-v1','blocked_roster')
    original=json.loads((ROOT/'analysis/results/joint-deadline-snapshots-v1/manifest.json').read_text())
    pre={s['gw']:s for s in original['sources']}
    con=sqlite3.connect((ROOT/'work/core.sqlite3').resolve().as_uri()+'?mode=ro',uri=True)
    identities=pd.read_sql_query("SELECT DISTINCT m.player_uuid,m.external_id AS fpl_element_id,p.canonical_name FROM player_id_mapping m JOIN players p USING(player_uuid) WHERE m.id_namespace='fpl_element' AND m.season='2025-26'",con);con.close()
    assert not identities.player_uuid.duplicated().any()
    blocked=blocked.merge(identities,on='player_uuid',validate='many_to_one')
    candidates=[]
    for month in json.loads(a.trees.read_text()):
        for x in month['tree']:
            if x['type']!='blob' or not x['path'].endswith('.json.xz'):continue
            day,time=x['path'].split('/');hhmm=time.split('.')[0]
            nominal=pd.Timestamp(f"2026-{int(month['month']):02d}-{int(day):02d}T{hhmm[:2]}:{hhmm[2:]}:00Z")
            for gw,g in blocked.groupby('gw'):
                cutoff=pd.Timestamp(g.cutoff.iloc[0])
                if cutoff<nominal<=cutoff+pd.Timedelta(days=2):
                    candidates.append(dict(gw=int(gw),path=month['month']+'/'+x['path'],blob_sha=x['sha'],bytes=x['size'],nominal_at=nominal.isoformat(),month_tree_sha=month['sha']))
    def fetch(r):
        url=f"https://raw.githubusercontent.com/Randdalf/fplcache/{HEAD}/cache/2026/{r['path']}"
        raw=urllib.request.urlopen(url,timeout=40).read()
        assert len(raw)==r['bytes'] and hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest()==r['blob_sha']
        elements={int(e['id']):e for e in json.loads(lzma.decompress(raw))['elements']}
        return r,raw,elements
    with ThreadPoolExecutor(max_workers=4) as pool: recovered=list(pool.map(fetch,candidates))
    a.out.mkdir(parents=True);rows=[];retained={}
    for r in blocked.itertuples(index=False):
        snapshots=sorted([x for x in recovered if x[0]['gw']==r.gw],key=lambda x:x[0]['nominal_at'])
        assert snapshots
        nearest=snapshots[0]
        present=[x for x in snapshots if int(r.fpl_element_id) in x[2]]
        first=present[0] if present else None
        keep=[nearest]+([first] if first and first[0]['path']!=nearest[0]['path'] else [])
        for item in keep:retained[item[0]['path']]=item
        entry=dict(fixture_uuid=r.fixture_uuid,player_uuid=r.player_uuid,gw=r.gw,canonical_name=r.canonical_name,
            fpl_element_id=int(r.fpl_element_id),forecast_team_id=r.team_id,forecast_position=r.pos,cutoff=r.cutoff,
            last_predeadline_at=pre[r.gw]['published_at'],last_predeadline_blob=pre[r.gw]['blob_sha'],
            nearest_post_nominal_at=nearest[0]['nominal_at'],nearest_post_blob=nearest[0]['blob_sha'],
            present_nearest_post=int(r.fpl_element_id) in nearest[2],
            first_observed_post_nominal_at=first[0]['nominal_at'] if first else None,
            first_observed_post_blob=first[0]['blob_sha'] if first else None,
            resolution='still_blocked_no_predeadline_listing_evidence')
        if first:
            e=first[2][int(r.fpl_element_id)];entry.update(observed_post_team=e['team'],observed_post_position={1:'GK',2:'DEF',3:'MID',4:'FWD'}[e['element_type']],observed_post_name=e['web_name'])
        rows.append(entry)
    sources=[]
    for i,(path,(r,raw,_)) in enumerate(sorted(retained.items())):
        parts=[]
        for j,start in enumerate(range(0,len(raw),32768)):
            data=raw[start:start+32768];name=f'snapshot-{i:02d}.json.xz.part-{j:04d}';(a.out/name).write_bytes(data)
            parts.append(dict(path=name,bytes=len(data),sha256=digest(data)))
        sources.append(dict(**r,sha256=digest(raw),source_head=HEAD,parts=parts,source_url=f'https://raw.githubusercontent.com/Randdalf/fplcache/{HEAD}/cache/2026/{path}'))
    evidence=pd.DataFrame(rows);evidence.to_csv(a.out/'blocked_rows.csv',index=False)
    (a.out/'candidate_index.json').write_text(json.dumps(candidates,indent=2,sort_keys=True)+'\n')
    manifest=dict(parent_checkpoint='cc682afe9777925a9adaef06ddaec5d53e66e44a',classification='source_gap_diagnostic_not_forecast_input',
        blocked_rows=len(evidence),unique_players=int(evidence.player_uuid.nunique()),blocked_fixtures=int(evidence.fixture_uuid.nunique()),
        source_candidates_checked=len(recovered),retained_snapshots=len(sources),
        present_nearest_post_rows=int(evidence.present_nearest_post.sum()),observed_within_two_days_rows=int(evidence.first_observed_post_blob.notna().sum()),
        recovered_predeadline_rows=0,full_period_ready=False,sources=sources,
        outputs=[dict(path=p,sha256=digest((a.out/p).read_bytes())) for p in ['blocked_rows.csv','candidate_index.json']],
        code_sha256=digest(Path(__file__).read_bytes()),
        limitations=['Nominal times come from cache paths; Git publication metadata must be checked separately.','Missing before and present after does not prove the exact addition time or ineligibility.','Postdeadline states are audit evidence only, never forecast inputs.'],
        unchanged='All model inputs, predictions, simulator, adapter, scoring and transfer/chip policy')
    (a.out/'manifest.json').write_text(json.dumps(manifest,indent=2,sort_keys=True)+'\n')
    print(json.dumps({k:v for k,v in manifest.items() if k not in ['sources','outputs','limitations']},indent=2))
if __name__=='__main__':main()

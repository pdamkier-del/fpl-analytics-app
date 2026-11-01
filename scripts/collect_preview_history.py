"""Copy coherent actual match history from a successful production artifact.

Never regenerate historical results or replace production. Independent of the
prospective forecast cutoff; provenance is the immutable CI artifact and hashes.
"""
import argparse,hashlib,json,subprocess,tarfile,tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
FILES=['current-players.json','live-fixtures.json','match-results.json']
def build(site,out,provenance):
    data={name:(Path(site)/name).read_bytes()for name in FILES};docs={n:json.loads(b)for n,b in data.items()}
    o,f,h=(docs[n]for n in FILES)
    if o['fetched_at']!=f['fetched_at']or h['observed_at']!=o['fetched_at']:raise ValueError('History files are not from one verified official capture')
    if not h.get('gw_rows')or not h.get('match_rows'):raise ValueError('Empty match history')
    ids={p['id']for p in o['players']};matches={x['id']for x in f['fixtures']}
    if any(r['player_id']not in ids or r['fixture_id']not in matches for r in h['match_rows']):raise ValueError('Unmatched historical player/fixture identity')
    out=Path(out);out.mkdir(parents=True,exist_ok=True)
    for n,b in data.items():(out/n).write_bytes(b)
    index=dict(schema='fpl-preview-actual-history-v1',observed_at=h['observed_at'],available_gws=h.get('available_gws',h['completed_gws']),match_rows=len(h['match_rows']),gw_rows=len(h['gw_rows']),files={n:hashlib.sha256(b).hexdigest()for n,b in data.items()},**provenance)
    (out/'index.json').write_text(json.dumps(index,sort_keys=True,separators=(',',':'))+'\n');return index

def collect(out):
    from publish_mm_preview import gh,REPO
    runs=gh('actions/runs?status=success&per_page=100')['workflow_runs'];allowed={'.github/workflows/free-pages.yml','.github/workflows/current-diagnostic-forecast.yml'}
    for r in sorted([r for r in runs if r['path']in allowed],key=lambda r:r['updated_at'],reverse=True):
        arts=gh('actions/runs/'+str(r['id'])+'/artifacts')['artifacts'];good=[a for a in arts if not a['expired']and a['name'].startswith('github-pages-')]
        if good:break
    else:raise ValueError('No successful production history artifact')
    a=good[0]
    with tempfile.TemporaryDirectory(prefix='fpl-history-')as tmp:
        subprocess.run(['gh','run','download',str(r['id']),'--repo',REPO,'--name',a['name'],'--dir',tmp],check=True)
        with tarfile.open(Path(tmp)/'artifact.tar')as tar:
            for name in FILES:
                member=next(x for x in tar.getmembers()if x.name.removeprefix('./')==name)
                (Path(tmp)/name).write_bytes(tar.extractfile(member).read())
        return build(tmp,out,dict(production_run=r['id'],production_artifact=a['id']))
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--site',type=Path);p.add_argument('--out',type=Path,default=ROOT/'app/mm-preview/history');a=p.parse_args()
    print(json.dumps(build(a.site,a.out,dict(validation_fixture=True))if a.site else collect(a.out),indent=2))

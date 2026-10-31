"""Package shared, non-personal frozen replay inputs for on-demand private reviews."""
import argparse,gzip,hashlib,json
from pathlib import Path
from historical_manager_review import HistoricalScorer
ROOT=Path(__file__).resolve().parents[1]
def sha(raw):return hashlib.sha256(raw).hexdigest()
def build(replay,markets,initial,history,out):
    replay,markets,initial,history,out=map(Path,[replay,markets,initial,history,out]);out.mkdir(parents=True,exist_ok=True);files={}
    def put(name,raw):
        target=out/name;target.parent.mkdir(parents=True,exist_ok=True);packed=gzip.compress(raw,mtime=0);target.write_bytes(packed);files[name]=sha(packed)
    raw=initial.read_bytes()
    if sha(raw)!='b0ef4493b3db92c38e403054d3e263b5cd9a529304b80eb4f684862b9dac5d61':raise ValueError('Unverified pre-GW1 price snapshot')
    put('initial-bootstrap.json.gz',raw)
    index=json.loads((history.parent/'index.json').read_text());raw=history.read_bytes()
    if sha(raw)!=index['files'][history.name]:raise ValueError('Actual history checksum mismatch')
    put('history/match-results.json.gz',raw);put('history/index.json.gz',(history.parent/'index.json').read_bytes())
    for gw in [6,7,8]:
        doc_raw=(replay/f'gw{gw}/forecast.json').read_bytes();doc=json.loads(doc_raw);samples_raw=(replay/f'gw{gw}/scenarios.json.gz').read_bytes();samples=json.loads(gzip.decompress(samples_raw));boot_raw=(markets/f'gw{gw}/inputs/bootstrap.json').read_bytes();boot=json.loads(boot_raw)
        if sha(boot_raw)!=doc['source_hashes']['bootstrap.json']:raise ValueError('Market snapshot differs from forecast source')
        frozen=json.loads(gzip.decompress((ROOT/f'analysis/results/current-season-b-backtest-20261027/gw{gw}.json.gz').read_bytes()))
        if doc['players']!=frozen['players']or doc['source_hashes']!=frozen['source_hashes']:raise ValueError('Different frozen forecast')
        HistoricalScorer(doc,samples,[dict(id=p['id'],code=p['code'])for p in boot['elements']])
        put(f'gw{gw}/forecast.json.gz',doc_raw);put(f'gw{gw}/scenarios.json.gz',gzip.decompress(samples_raw));put(f'gw{gw}/bootstrap.json.gz',boot_raw)
    manifest=dict(schema='fpl-shared-history-refresh-inputs-v1',season='2026-27',model_source='03d5c4d4777b44bc1d37884a1cf4dde106b45cab',gws=[6,7,8],files=files,scope='Shared football/model inputs only. No manager ID, picks, purchases, transfers, bank, personal forecast or private result.',initial_source='https://raw.githubusercontent.com/Randdalf/fplcache/main/cache/2026/8/21/1300.json.xz')
    (out/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n');return manifest
if __name__=='__main__':
    p=argparse.ArgumentParser()
    for key in ['replay','markets','initial','history','out']:p.add_argument('--'+key,type=Path,required=True)
    a=p.parse_args();m=build(a.replay,a.markets,a.initial,a.history,a.out);print('Packaged shared replay inputs:',len(m['files']),'files; no manager data')

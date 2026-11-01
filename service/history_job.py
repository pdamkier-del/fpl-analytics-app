"""Complete private history refresh using shared, immutable, non-personal PM draws."""
import concurrent.futures,gzip,hashlib,json,re,subprocess,sys
from pathlib import Path,PurePosixPath
import requests
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/'src'),str(ROOT/'scripts')]
from scripts.export_fpl_team_history import collect
CONFIG=ROOT/'service/history-refresh-bundle.json'
MODEL='03d5c4d4777b44bc1d37884a1cf4dde106b45cab'
def sha(raw):return hashlib.sha256(raw).hexdigest()
def ready():
    return CONFIG.is_file()and all((ROOT/f'analysis/results/current-season-b-backtest-20261027/gw{gw}.json.gz').is_file()for gw in [6,7,8])
def fingerprint():
    files=[Path(__file__),CONFIG,ROOT/'scripts/historical_manager_review.py',ROOT/'scripts/export_fpl_team_history.py']+[ROOT/f'analysis/results/current-season-b-backtest-20261027/gw{gw}.json.gz'for gw in [6,7,8]]
    return sha(b''.join(p.read_bytes()for p in files))
def progress(folder,stage,gw=None,completed=0,total=0):
    target=Path(folder)/'progress.json';tmp=target.with_suffix('.tmp');tmp.write_text(json.dumps(dict(stage=stage,gw=gw,completed_gws=completed,total_gws=total)));tmp.replace(target)
def download_bundle(folder,season):
    config=json.loads(CONFIG.read_text())
    if not re.fullmatch('[a-f0-9]{40}',config['commit'])or config['path']!='analysis/results/history-refresh-public-20261029':raise ValueError('Invalid pinned replay bundle')
    base='https://raw.githubusercontent.com/pdamkier-del/fpl-analytics-app/'+config['commit']+'/'+config['path']+'/'
    def read(name,digest):
        path=PurePosixPath(name)
        if path.is_absolute()or '..'in path.parts:raise ValueError('Invalid bundle path')
        r=requests.get(base+name,timeout=45);r.raise_for_status();raw=r.content
        if len(raw)>32*1024*1024 or sha(raw)!=digest:raise ValueError('Replay bundle checksum mismatch')
        return raw
    raw=read('manifest.json',config['manifest_sha256']);manifest=json.loads(raw)
    if manifest['schema']!='fpl-shared-history-refresh-inputs-v1'or manifest['season']!=season or manifest['model_source']!=MODEL:raise ValueError('Replay season/source mismatch')
    expected={'initial-bootstrap.json.gz','history/index.json.gz','history/match-results.json.gz'}|{f'gw{gw}/{name}.json.gz'for gw in manifest['gws']for name in ['forecast','scenarios','bootstrap']}
    if set(manifest['files'])!=expected:raise ValueError('Incomplete replay bundle')
    out=Path(folder)/'public-inputs';out.mkdir(exist_ok=True);(out/'manifest.json').write_bytes(raw)
    def save(item):
        name,digest=item;packed=read(name,digest);target=out/name;target.parent.mkdir(exist_ok=True,parents=True);target.write_bytes(packed)
    with concurrent.futures.ThreadPoolExecutor(max_workers=4)as pool:list(pool.map(save,manifest['files'].items()))
    return manifest

def refresh(folder,entry,season,get_public):
    folder=Path(folder);progress(folder,'history');history=collect(entry,season)
    (folder/'history-import.json').write_text(json.dumps(history,allow_nan=False));(folder/'transfers.json').write_text(json.dumps(history['transfers'],allow_nan=False))
    progress(folder,'model');manifest=download_bundle(folder,season);public=folder/'public-inputs'
    (folder/'initial-bootstrap.json').write_bytes(gzip.decompress((public/'initial-bootstrap.json.gz').read_bytes()))
    # Current verified outcomes may include official scoring corrections; the
    # predeadline forecasts and scenario draws remain frozen.
    index_raw=get_public('mm-preview/history/index.json');actual_raw=get_public('mm-preview/history/match-results.json');index=json.loads(index_raw)
    if sha(actual_raw)!=index['files']['match-results.json']:raise ValueError('Published actual history changed during retrieval')
    actual=folder/'actual';actual.mkdir();(actual/'index.json').write_bytes(index_raw);(actual/'match-results.json').write_bytes(actual_raw)
    for gw in manifest['gws']:
        capsule=folder/f'replay/gw{gw}';market=folder/f'markets/gw{gw}/inputs';capsule.mkdir(parents=True);market.mkdir(parents=True)
        (capsule/'forecast.json').write_bytes(gzip.decompress((public/f'gw{gw}/forecast.json.gz').read_bytes()))
        (capsule/'scenarios.json.gz').write_bytes((public/f'gw{gw}/scenarios.json.gz').read_bytes())
        (market/'bootstrap.json').write_bytes(gzip.decompress((public/f'gw{gw}/bootstrap.json.gz').read_bytes()))
    completed=subprocess.run([sys.executable,str(ROOT/'scripts/locked_numerical_runtime.py'),str(Path(__file__).resolve()),str(folder)],timeout=1800,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    if completed.returncode:raise ValueError('Private historical review did not pass validation')
    return json.loads((folder/'review.json').read_text())

def worker(folder):
    from scripts.historical_manager_review import build,states
    folder=Path(folder);history=json.loads((folder/'history-import.json').read_text());manifest=json.loads((folder/'public-inputs/manifest.json').read_text());targets=[w['gw']for w in history['weeks']if w['final']and w['gw']in manifest['gws']]
    # Late joiners or unsupported historical chips still receive all official
    # history. We never invent ownership/prices to fill an unsafe replay.
    unavailable=None
    if targets:
        try:states(dict(history,weeks=[w for w in history['weeks']if w['gw']<=max(targets)]),history['transfers'],json.loads((folder/'initial-bootstrap.json').read_text()))
        except (KeyError,ValueError):unavailable='Historiske køb, bank eller chipforløb kunne ikke genskabes sikkert.';targets=[]
    build(folder,folder/'replay',folder/'review.json',history_source=folder/'actual/match-results.json',markets=folder/'markets',review_gws=targets,progress=lambda gw,done,total:progress(folder,'model',gw,done,total))
    result=json.loads((folder/'review.json').read_text());result['analysis_status']=dict(completed_gws=targets,available_gws=manifest['gws'],unavailable_reason=unavailable)
    for w in result['weeks']:
        if not w.get('transfer_review'):w['analysis_unavailable']=unavailable or('Ingen valideret B-opvarmning før GW6.'if w['gw']<6 else'Afventer en valideret gemt prognosepakke for denne GW.')
    (folder/'review.json').write_text(json.dumps(result,allow_nan=False));progress(folder,'complete',completed=len(targets),total=len(targets))
if __name__=='__main__':worker(Path(sys.argv[1]))

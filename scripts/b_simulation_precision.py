"""B-only precision and browser transport; original PM/TS scoring is unchanged."""
import copy,hashlib,json
NORMAL_DRAWS=2000
PRECISE_DRAWS=10000
VERSION='B-simulation-precision-v1'

def fixture_offset(fixture,season):
    # Identical for a full horizon, one GW, a subset, and paired model arms.
    return int.from_bytes(hashlib.sha256((season+'|'+fixture).encode()).digest()[:4],'big')

def resolution(mode='normal',fixtures=60):
    if mode not in ['normal','validation','close']:raise ValueError('Unknown precision mode')
    n=NORMAL_DRAWS if mode=='normal'else PRECISE_DRAWS
    if not 1<=fixtures<=60 or n*fixtures>600000:raise ValueError('B precision budget exceeded: max 60 fixtures / 600000 draws')
    return n

def browser_summary(forecast):
    """Derived transport, canonical sealed ID retained for the private backend.

    Byte hash is in the public index. It is intentionally not a new model seal:
    the service fetches and verifies canonical forecast.json including all draws.
    """
    from b_chain_contract import validate_forecast
    from fpl_v1_1_model.forecast_snapshot import require_snapshot
    require_snapshot(forecast);validate_forecast(forecast);out=copy.deepcopy(forecast)
    for p in out['players']:
        for w in p['weeks']:w.pop('scenarios',None)
    for team in out.get('gk_team_fixtures',[]):team.get('physical_timeline',{}).pop('unlisted_keeper_minutes',None)
    out['transport']=dict(version='B-browser-summary-v1',canonical_forecast_sha256=forecast['forecast_sha256'],canonical_file='forecast.json',contains_TS_scenarios=False,server_retains_all_joint_draws=True)
    return out

def publish_summaries(root):
    from pathlib import Path
    root=Path(root);receipts=[]
    for directory in [root/'app/mm-preview/current',root/'app/mm-preview/gk']:
        fpath=directory/'forecast.json';index_path=directory/'index.json'
        if not fpath.exists()or not index_path.exists():continue
        raw=fpath.read_bytes();f=json.loads(raw)
        if not f.get('simulation_precision'):continue
        short=json.dumps(browser_summary(f),sort_keys=True,ensure_ascii=False,allow_nan=False,separators=(',',':')).encode()+b'\n';(directory/'browser-forecast.json').write_bytes(short)
        index=json.loads(index_path.read_text());digest=hashlib.sha256(short).hexdigest();index.update(browser_forecast_file='browser-forecast.json',browser_forecast_sha256=digest)
        if directory.name=='current':index.update(forecast_file='browser-forecast.json',forecast_file_sha256=digest)
        index_path.write_text(json.dumps(index,sort_keys=True,ensure_ascii=False,separators=(',',':'))+'\n')
        receipts.append(dict(directory=directory.name,canonical_bytes=len(raw),browser_bytes=len(short),reduction=1-len(short)/len(raw),forecast_sha256=f['forecast_sha256']))
    return receipts

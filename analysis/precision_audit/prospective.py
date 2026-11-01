"""Append-only real predeadline forecasts; never stores oracle outputs."""
import argparse,gzip,hashlib,json
from datetime import datetime,timezone
from pathlib import Path
from fpl_v1_1_model.forecast_snapshot import require_snapshot
from b_chain_contract import validate_forecast
BASE='https://pdamkier-del.github.io/fpl-analytics-app/mm-preview/'

def canonical(value):return json.dumps(value,sort_keys=True,ensure_ascii=False,allow_nan=False,separators=(',',':')).encode()

def verify(folder):
    folder=Path(folder);path=folder/'manifest.json';entries=json.loads(path.read_text())if path.exists()else[];previous=None
    for e in entries:
        body={k:v for k,v in e.items()if k!='record_sha256'}
        if hashlib.sha256(canonical(body)).hexdigest()!=e['record_sha256']or e['previous_record_sha256']!=previous:raise ValueError('Prospective ledger chain changed')
        raw=gzip.decompress((folder/e['file']).read_bytes());f=json.loads(raw);require_snapshot(f,e['forecast_sha256'])
        if hashlib.sha256(raw).hexdigest()!=e['content_sha256']:raise ValueError('Prospective content changed')
        if datetime.fromisoformat(e['acquired_at'])>=datetime.fromisoformat(f['origin_deadline'].replace('Z','+00:00')):raise ValueError('Postdeadline record cannot be admitted')
        previous=e['record_sha256']
    return entries

def append(folder,forecast,metadata,acquired_at,http_date=None):
    folder=Path(folder);folder.mkdir(parents=True,exist_ok=True);entries=verify(folder)
    require_snapshot(forecast);validate_forecast(forecast)
    if forecast.get('scope')!='prospective_preview'or any('oracle'in k.lower()for k in forecast):raise ValueError('Oracle output cannot enter real forecast ledger')
    acquired=datetime.fromisoformat(acquired_at);deadline=datetime.fromisoformat(forecast['origin_deadline'].replace('Z','+00:00'))
    if acquired>=deadline or datetime.fromisoformat(forecast['data_asof'].replace('Z','+00:00'))>acquired:raise ValueError('Invalid predeadline acquisition clock')
    if metadata['forecast_sha256']!=forecast['forecast_sha256']:raise ValueError('Publication/forecast identity differs')
    if any(e['forecast_sha256']==forecast['forecast_sha256']for e in entries):return entries
    raw=canonical(forecast);name='forecast-'+forecast['forecast_sha256']+'.json.gz';target=folder/name
    if target.exists():raise ValueError('Refuse overwrite of immutable forecast file')
    target.write_bytes(gzip.compress(raw,mtime=0));entry=dict(file=name,forecast_sha256=forecast['forecast_sha256'],content_sha256=hashlib.sha256(raw).hexdigest(),acquired_at=acquired_at,http_date=http_date,model_source=metadata['model_source'],publication_run=metadata['publication_run'],gws=forecast['gws'],origin_deadline=forecast['origin_deadline'],previous_record_sha256=entries[-1]['record_sha256']if entries else None,scope='REAL_PREDEADLINE_FORECAST_NOT_ORACLE')
    entry['record_sha256']=hashlib.sha256(canonical(entry)).hexdigest();entries.append(entry);(folder/'manifest.json').write_text(json.dumps(entries,indent=2)+'\n');verify(folder);return entries

def main():
    p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True);p.add_argument('--verify-only',action='store_true');a=p.parse_args()
    if a.verify_only:print('Verified prospective records',len(verify(a.out)));return
    import requests
    for _ in range(3):
        m=requests.get(BASE+'chain-publication-sources.json',timeout=60);m.raise_for_status();r=requests.get(BASE+'current/forecast.json',timeout=60);r.raise_for_status();f=r.json()
        if m.json()['forecast_sha256']==f['forecast_sha256']:break
    entries=append(a.out,f,m.json(),datetime.now(timezone.utc).isoformat(),r.headers.get('Date'));print('Immutable predeadline records',len(entries),'GW',f['gws'],'seal',f['forecast_sha256'])
if __name__=='__main__':main()

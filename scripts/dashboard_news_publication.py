"""Keep the freshest verified public news while overlaying a B UI/model preview."""
from datetime import datetime,timezone,timedelta
from pathlib import Path
import json
from urllib.request import urlopen
from urllib.error import HTTPError,URLError
from collect_dashboard_news import seal,URL
PUBLIC='https://pdamkier-del.github.io/fpl-analytics-app/mm-preview/news/availability.json'

def checked(raw,now=None):
    value=json.loads(raw);now=now or datetime.now(timezone.utc)
    if value.get('schema')!='fpl-dashboard-availability-v1' or value.get('source_url')!=URL or seal(value)['content_sha256']!=value.get('content_sha256'):raise ValueError('Unverified public news')
    at=datetime.fromisoformat(value['observed_at'].replace('Z','+00:00'))
    if at>now+timedelta(seconds=30):raise ValueError('Future news capture')
    if len({p['id']for p in value['players']})!=len(value['players']):raise ValueError('Duplicate news identities')
    return value,at

def retain_latest(source,previous):
    candidates=[]
    for path in [Path(source)/'news/availability.json',Path(previous)/'news/availability.json']:
        if path.exists():
            raw=path.read_bytes();value,at=checked(raw);candidates.append((at,raw))
    try:
        with urlopen(PUBLIC,timeout=15)as response:raw=response.read()
        value,at=checked(raw);candidates.append((at,raw))
    except (HTTPError,URLError,TimeoutError):pass
    if candidates:
        _,raw=max(candidates,key=lambda p:p[0]);out=Path(source)/'news/availability.json';out.parent.mkdir(parents=True,exist_ok=True);out.write_bytes(raw)

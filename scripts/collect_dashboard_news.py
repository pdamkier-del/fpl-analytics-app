"""Capture official FPL availability news, without manager or private squad data."""
from datetime import datetime,timezone
from pathlib import Path
import argparse,hashlib,json
import requests
URL='https://fantasy.premierleague.com/api/bootstrap-static/'
FIELDS=('status','news','news_added','chance_of_playing_next_round','chance_of_playing_this_round')

def seal(document):
    clean={k:v for k,v in document.items()if k!='content_sha256'}
    return dict(clean,content_sha256=hashlib.sha256(json.dumps(clean,sort_keys=True,ensure_ascii=False,separators=(',',':'),allow_nan=False).encode()).hexdigest())

def build(raw,observed_at=None):
    observed_at=observed_at or datetime.now(timezone.utc).isoformat()
    now=datetime.fromisoformat(observed_at.replace('Z','+00:00'))
    event=next((e for e in raw['events']if e.get('is_next')),None)
    if not event or datetime.fromisoformat(event['deadline_time'].replace('Z','+00:00'))<=now:raise ValueError('No current official next GW')
    teams={t['id']:t['name']for t in raw['teams']};players=[]
    for p in sorted(raw['elements'],key=lambda p:p['id']):
        if p['status']not in {'a','d','i','s','u','n'}:raise ValueError('Unknown official availability status')
        for field in ['chance_of_playing_next_round','chance_of_playing_this_round']:
            if p.get(field)is not None and p[field]not in [0,25,50,75,100]:raise ValueError('Invalid FPL availability chance')
        if p.get('news_added') and datetime.fromisoformat(p['news_added'].replace('Z','+00:00'))>now:raise ValueError('Future news timestamp')
        players.append(dict(id=p['id'],name=p['web_name'],team=p['team'],team_name=teams[p['team']],position=p['element_type'],price_tenths=p['now_cost'],**{k:p.get(k)for k in FIELDS}))
    if not players or len({p['id']for p in players})!=len(players):raise ValueError('Invalid official player catalogue')
    return seal(dict(schema='fpl-dashboard-availability-v1',observed_at=observed_at,source_url=URL,next_gw=event['id'],deadline=event['deadline_time'],players=players))

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--out',type=Path,default=Path('app/mm-preview/news/availability.json'));ap.add_argument('--bootstrap',type=Path);args=ap.parse_args()
    if args.bootstrap:raw=json.loads(args.bootstrap.read_text())
    else:
        response=requests.get(URL,timeout=45,headers={'Cache-Control':'no-cache','User-Agent':'FPLAnalyticsAvailability/1'});response.raise_for_status();raw=response.json()
    value=build(raw);args.out.parent.mkdir(parents=True,exist_ok=True);args.out.write_text(json.dumps(value,sort_keys=True,ensure_ascii=False,separators=(',',':'),allow_nan=False)+'\n')
    print(json.dumps({k:value[k]for k in ['observed_at','next_gw','content_sha256']}))
if __name__=='__main__':main()

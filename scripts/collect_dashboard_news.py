"""Capture official FPL availability news, without manager or private squad data."""
from datetime import datetime,timezone,timedelta
from pathlib import Path
import argparse,hashlib,json
import requests
URL='https://fantasy.premierleague.com/api/bootstrap-static/'
FIXTURES_URL='https://fantasy.premierleague.com/api/fixtures/'
FIELDS=('status','news','news_added','chance_of_playing_next_round','chance_of_playing_this_round')

def seal(document):
    clean={k:v for k,v in document.items()if k!='content_sha256'}
    return dict(clean,content_sha256=hashlib.sha256(json.dumps(clean,sort_keys=True,ensure_ascii=False,separators=(',',':'),allow_nan=False).encode()).hexdigest())

def recent_dismissals(fixtures,raw,now):
    """Match events are facts; no inference about ban length or future fixtures."""
    players={p['id']for p in raw['elements']};teams={t['id']:t['name']for t in raw['teams']};events={};seen=set();seen_fixtures=set()
    for f in fixtures:
        if f['id']in seen_fixtures:raise ValueError('Duplicate discipline fixture')
        seen_fixtures.add(f['id'])
        if not f.get('kickoff_time'):continue
        ko=datetime.fromisoformat(f['kickoff_time'].replace('Z','+00:00'))
        if ko.tzinfo is None:raise ValueError('Fixture timezone required')
        if not now-timedelta(days=14)<=ko<now:continue
        for stat in f.get('stats',[]):
            if stat.get('identifier')!='red_cards':continue
            for side,team,opp in [('h',f['team_h'],f['team_a']),('a',f['team_a'],f['team_h'])]:
                for item in stat.get(side,[]):
                    if item['element']not in players:raise ValueError('Unmapped red-card player')
                    if item['value']!=1:raise ValueError('Invalid red-card count')
                    key=(item['element'],f['id'])
                    if key in seen:raise ValueError('Duplicate red-card event')
                    seen.add(key);events.setdefault(item['element'],[]).append(dict(fixture_id=f['id'],gw=f.get('event'),kickoff=f['kickoff_time'],team_id=team,opponent=teams[opp],red_cards=1,provisional=not bool(f.get('finished')),source_url=FIXTURES_URL))
    return events


def reviewed_resolutions():
    path=Path(__file__).resolve().parents[1]/'research/discipline_sources/reviewed-resolutions.json'
    if not path.exists():return []
    value=json.loads(path.read_text())
    if value.get('schema')!='fpl-reviewed-discipline-resolutions-v1':raise ValueError('Unknown discipline resolution registry')
    return value['records']


def build(raw,observed_at=None,fixtures=None,resolutions=()):
    observed_at=observed_at or datetime.now(timezone.utc).isoformat()
    now=datetime.fromisoformat(observed_at.replace('Z','+00:00'))
    event=next((e for e in raw['events']if e.get('is_next')),None)
    if not event or datetime.fromisoformat(event['deadline_time'].replace('Z','+00:00'))<=now:raise ValueError('No current official next GW')
    teams={t['id']:t['name']for t in raw['teams']};players=[];discipline=recent_dismissals(fixtures,raw,now)if fixtures is not None else {}
    for p in sorted(raw['elements'],key=lambda p:p['id']):
        if p['status']not in {'a','d','i','s','u','n'}:raise ValueError('Unknown official availability status')
        for field in ['chance_of_playing_next_round','chance_of_playing_this_round']:
            if p.get(field)is not None and p[field]not in [0,25,50,75,100]:raise ValueError('Invalid FPL availability chance')
        if p.get('news_added') and datetime.fromisoformat(p['news_added'].replace('Z','+00:00'))>now:raise ValueError('Future news timestamp')
        players.append(dict(id=p['id'],name=p['web_name'],team=p['team'],team_name=teams[p['team']],position=p['element_type'],price_tenths=p['now_cost'],**{k:p.get(k)for k in FIELDS}))
    if fixtures is not None:
        for p in players:
            p['recent_red_cards']=sorted(discipline.get(p['id'],[]),key=lambda x:x['kickoff'],reverse=True)
            for e in p['recent_red_cards']:
                matches=[r for r in resolutions if r['player_id']==p['id']and r['fixture_id']==e['fixture_id']and r.get('kickoff')and datetime.fromisoformat(r['kickoff'].replace('Z','+00:00'))==datetime.fromisoformat(e['kickoff'].replace('Z','+00:00'))]
                if len(matches)>1:raise ValueError('Duplicate discipline resolution')
                if matches:
                    r=matches[0]
                    if not r.get('human_reviewed')or not r['source_url'].startswith('https://www.premierleague.com/')or datetime.fromisoformat(r['source_observed_at'].replace('Z','+00:00'))>now:raise ValueError('Unverified discipline resolution')
                    e['resolution']=r
    if not players or len({p['id']for p in players})!=len(players):raise ValueError('Invalid official player catalogue')
    return seal(dict(schema='fpl-dashboard-availability-v1',observed_at=observed_at,source_url=URL,next_gw=event['id'],deadline=event['deadline_time'],players=players,discipline_checked=fixtures is not None,discipline_source_url=FIXTURES_URL if fixtures is not None else None))

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--out',type=Path,default=Path('app/mm-preview/news/availability.json'));ap.add_argument('--bootstrap',type=Path);ap.add_argument('--fixtures',type=Path);args=ap.parse_args()
    if args.bootstrap:raw=json.loads(args.bootstrap.read_text())
    else:
        response=requests.get(URL,timeout=45,headers={'Cache-Control':'no-cache','User-Agent':'FPLAnalyticsAvailability/1'});response.raise_for_status();raw=response.json()
    if args.fixtures:fixtures=json.loads(args.fixtures.read_text())
    elif args.bootstrap:fixtures=None
    else:
        response=requests.get(FIXTURES_URL,timeout=45,headers={'Cache-Control':'no-cache','User-Agent':'FPLAnalyticsAvailability/1'});response.raise_for_status();fixtures=response.json()
    value=build(raw,fixtures=fixtures,resolutions=reviewed_resolutions());args.out.parent.mkdir(parents=True,exist_ok=True);args.out.write_text(json.dumps(value,sort_keys=True,ensure_ascii=False,separators=(',',':'),allow_nan=False)+'\n')
    print(json.dumps({k:value[k]for k in ['observed_at','next_gw','content_sha256']}))
if __name__=='__main__':main()

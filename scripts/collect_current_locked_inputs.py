"""Capture actual current-season inputs for the existing locked chain.
No model mathematics, imputed match events, fuzzy identities or ep_next forecast.
All HTTP payloads retained with capture timestamps and SHA-256; resume from cache.
"""
from pathlib import Path
from datetime import datetime, timezone, timedelta
from collections import defaultdict,Counter
import concurrent.futures as cf
import csv,gzip,hashlib,json,sqlite3,sys,time,unicodedata
from urllib.request import Request,urlopen
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))
from fpl_v1_1_model.team_news_history import normalize_team_news
WORK=ROOT/'work/live-final-model';WORK.mkdir(parents=True,exist_ok=True)
CACHE=ROOT/'.cache/current-locked-inputs';CACHE.mkdir(parents=True,exist_ok=True)
SOURCES=[];ERRORS=[]
def utc(s):return datetime.fromisoformat(str(s).replace('Z','+00:00')).astimezone(timezone.utc)
def norm(s):return ''.join(c for c in unicodedata.normalize('NFKD',str(s)).casefold() if c.isalnum())
ALIASES={'manchestercity':'mancity','manchesterunited':'manutd','nottinghamforest':'nottmforest','tottenhamhotspur':'spurs','tottenham':'spurs','brightonhovealbion':'brighton','brightonandhovealbion':'brighton','wolverhamptonwanderers':'wolves','newcastleunited':'newcastle','westhamunited':'westham','ipswichtown':'ipswich','leicestercity':'leicester','afcbournemouth':'bournemouth','leedsunited':'leeds'}
def club(s):return ALIASES.get(norm(s),norm(s))
def dump(p,v):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(v,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
def gz(p,v):p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(gzip.compress((''.join(json.dumps(r,ensure_ascii=False,allow_nan=False)+'\n' for r in v)).encode(),mtime=0))
def table(p,rs,columns):
 p.parent.mkdir(parents=True,exist_ok=True)
 with p.open('w',newline='') as f:
  w=csv.DictWriter(f,fieldnames=columns,extrasaction='ignore');w.writeheader();w.writerows(rs)
def capture(url,p,cache=False):
 c=CACHE/hashlib.sha256(url.encode()).hexdigest();at=datetime.now(timezone.utc).isoformat()
 if cache and c.exists():b=c.read_bytes();at=datetime.fromtimestamp(c.stat().st_mtime,timezone.utc).isoformat()
 else:
  for i in range(3):
   try:
    b=urlopen(Request(url,headers={'User-Agent':'Mozilla/5.0 FPLAnalytics locked data','Accept':'application/json'}),timeout=30).read();break
   except Exception:
    if i==2:raise
    time.sleep(i+1)
  c.write_bytes(b)
 p.parent.mkdir(parents=True,exist_ok=True)
 if p.exists() and p.read_bytes()!=b:raise ValueError('Immutable capture differs: '+str(p))
 p.write_bytes(b);SOURCES.append(dict(url=url,path=str(p.relative_to(ROOT)),sha256=hashlib.sha256(b).hexdigest(),observed_at=at));return json.loads(b),at

def main():
 stamp=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ');base=ROOT/'data_v1_1/raw/live-captures'/stamp
 bootstrap,asof=capture('https://fantasy.premierleague.com/api/bootstrap-static/',base/'bootstrap.json')
 fixtures,_=capture('https://fantasy.premierleague.com/api/fixtures/',base/'fixtures.json')
 year=int(bootstrap['events'][0]['deadline_time'][:4]);season=f'{year}-{str(year+1)[-2:]}';provider_season=f'{year}%2F{year+1}'
 assert season=='2026-27',('Unexpected official season',season)
 event=next(e for e in bootstrap['events'] if e.get('is_next'));gw=int(event['id']);now=utc(asof);deadline=utc(event['deadline_time']);assert now<deadline
 teams={int(t['id']):t for t in bootstrap['teams']};byclub={club(t['name']):t for t in bootstrap['teams']}
 players={int(p['code']):p for p in bootstrap['elements'] if p['element_type']!=5}
 con=sqlite3.connect((ROOT/'work/core.sqlite3').as_uri()+'?mode=ro',uri=True)
 ids=defaultdict(set)
 for code,uid in con.execute("SELECT external_id,player_uuid FROM player_id_mapping WHERE id_namespace='fpl_code'"):ids[str(code)].add(uid)
 con.close();uuid_map={c:next(iter(ids[str(c)])) for c in players if len(ids[str(c)])==1}
 unresolved=[dict(fpl_element=p['id'],fpl_code=c,name=p['web_name'],reason='No unique existing stable-code UUID') for c,p in players.items() if c not in uuid_map]
 ident=[dict(fpl_element=p['id'],fpl_code=c,player_uuid=uuid_map.get(c),team_id=p['team'],team_code=teams[p['team']]['code'],name=p['first_name']+' '+p['second_name']) for c,p in players.items()]
 dump(WORK/'current_identity.json',ident);dump(WORK/'bootstrap.json',bootstrap);dump(WORK/'fixtures.json',fixtures)
 for e in bootstrap['events']:
  if e['id']<gw and e.get('finished'):
   capture(f"https://fantasy.premierleague.com/api/event/{e['id']}/live/",base/f"fpl/gw{e['id']}.json")
 news=[]
 for code,p in players.items():
  if code not in uuid_map:continue
  scoped=p.get('chance_of_playing_next_round')
  # Chance is scoped ONLY to the official next event at this capture.
  state=normalize_team_news(p.get('status'),p.get('news'),scoped)
  news.append(dict(season=season,gw=gw,cutoff=deadline.isoformat(),player_uuid=uuid_map[code],fpl_element=p['id'],effective_at=asof,observed_at=asof,identity_status='mapped',timing_verified=True,tier='strict',normalized_availability_state=state,scoped_chance=scoped,raw_status=p.get('status'),raw_news=p.get('news'),news_added=p.get('news_added'),source='Official FPL bootstrap-static',source_id='bootstrap:'+stamp,carried_from_earlier_gw=False,unchanged_news_since_previous_gw=False))
 gz(ROOT/'data_v1_1/derived/team_news_audit/2026-27-v2/predeadline_strict.jsonl.gz',news)
 selected={};expected={'prem':'Premier League','cl':'Champions League','el':'Europa League','conf':'Conference League','conf_qual':'Conference League Qualification','fa':'FA Cup','efl':'EFL Cup'}
 for comp,lid in [('prem',47),('cl',42),('el',73),('conf',10216),('conf_qual',10615),('fa',132),('efl',133)]:
  try:
   j,_=capture(f'https://www.fotmob.com/api/data/leagues?id={lid}&season={provider_season}',base/f'fotmob/{comp}.json',False)
   assert j['details']['name']==expected[comp] and j['details']['selectedSeason']==f'{year}/{year+1}', f"Requested {year}/{year+1}, provider returned {j['details']['selectedSeason']}"
   for f in j.get('fixtures',{}).get('allMatches',[]):
    s=f.get('status') or {};ko=s.get('utcTime')
    if not ko or utc(ko)>now or not s.get('finished'):continue
    if any(club(f.get(side,{}).get('name','')) in byclub for side in ['home','away']):selected[str(f['id'])]=(comp,f)
  except Exception as e:ERRORS.append(dict(source='FotMob inventory',competition=comp,error=str(e)))
 details=[]
 def one(item):
  mid,(comp,f)=item
  try:
   j,at=capture('https://www.fotmob.com/api/data/matchDetails?matchId='+mid,base/f'fotmob/details/{mid}.json',True)
   assert str(j['general']['matchId'])==mid and j['general']['finished'];return comp,f,j,at
  except Exception as e:ERRORS.append(dict(source='FotMob detail',match_id=mid,error=str(e)));return None
 with cf.ThreadPoolExecutor(max_workers=5) as pool:details=[x for x in pool.map(one,selected.items()) if x]
 fixture_key={(int(f['team_h']),int(f['team_a']),utc(f['kickoff_time']).isoformat()):f for f in fixtures if f.get('kickoff_time')}
 games=[];lines=[];stats=[];ratings=[];unmapped=[];positions=[]
 for comp,inventory,j,at in details:
  g=j['general'];mid=str(g['matchId']);ko=utc(g['matchTimeUTCDate']);h=byclub.get(club(g['homeTeam']['name']));a=byclub.get(club(g['awayTeam']['name']));f=fixture_key.get((int(h['id']),int(a['id']),ko.isoformat())) if h and a and comp=='prem' else None
  if comp=='prem' and not f:ERRORS.append(dict(source='PL fixture identity',match_id=mid,error='No exact home-away-UTC fixture match'));continue
  match_id=f'26-27-{comp}-{mid}';known=(ko+timedelta(hours=4)).isoformat()
  if utc(known)>=now:continue
  game=dict(match_id=match_id,provider_match_id=mid,gameweek=f['event'] if f else None,tournament=comp,kickoff_time=ko.isoformat(),finished=True,home_team=h['code'] if h else None,away_team=a['code'] if a else None,home_score=j['header']['teams'][0]['score'],away_score=j['header']['teams'][1]['score'],round_name=g.get('matchRound'),available_at=known,publication_at=None,observed_at=at,availability_quality='PROXY_CUTOFF_SAFE',provider_league=g['leagueName'])
  games.append(game);playerstats=j.get('content',{}).get('playerStats') or {};lineup=j.get('content',{}).get('lineup') or {}
  for side in ['home','away']:
   block=lineup.get(side+'Team') or {};team=byclub.get(club(block.get('name','')))
   if not team:continue
   for kind in ['starters','subs']:
    for slot,p in enumerate(block.get(kind,[]),1):
     pid=str(p['id']);st=playerstats.get(pid,{});opta=st.get('optaId');code=int(opta) if str(opta).isdigit() else None
     current=players.get(code);uid=uuid_map.get(code)
     if current is None or int(current['team'])!=int(team['id']):
      unmapped.append(dict(match_id=match_id,provider_player_id=pid,opta_code=opta,player_name=p['name'],team=team['name'],reason='No exact Opta code + current team match'));continue
     vals={v.get('key',k):v.get('stat',{}).get('value') for section in st.get('stats',[]) for k,v in section.get('stats',{}).items()}
     lines.append(dict(match_id=match_id,team_side=side,team_code=team['code'],formation=block.get('formation'),player_id=current['id'],player_uuid=uid,player_name=p['name'],is_starting=kind=='starters',position='GK' if slot==1 and kind=='starters' else p.get('positionId'),lineup_status='confirmed',lineup_slot=slot,provider_player_id=pid))
     stats.append(dict(match_id=match_id,player_id=current['id'],player_uuid=uid,team_id=team['id'],team_code=team['code'],minutes_played=vals.get('minutes_played'),started=kind=='starters',available_at=known,stats=vals,provider_player_id=pid,opta_code=opta))
     rate=vals.get('rating_title')
     if rate is not None and uid:
      assert 0<=float(rate)<=10
      ratings.append(dict(provider='FotMob',player_uuid=uid,match_id=match_id,available_at=known,rating=rate,observed_at=at,publication_at=None,timing_quality='PROXY_CUTOFF_SAFE'))
  # No measured average position is fabricated from planned lineup geometry.
 columns=['match_id','gameweek','tournament','kickoff_time','finished','home_team','away_team','home_score','away_score','round_name','provider_match_id','available_at']
 table(ROOT/'data_v1_1/raw/all-competitions-2026-27/matches.csv',games,columns)
 table(ROOT/'data_v1_1/raw/all-competitions-2026-27/lineups.csv',lines,['match_id','team_side','team_code','formation','player_id','player_uuid','player_name','is_starting','position','lineup_status','lineup_slot','provider_player_id'])
 # Per-GW files are exactly the existing role bridge's expected input layout.
 for n in sorted({g['gameweek'] for g in games if g['gameweek'] is not None}):
  mids={g['match_id'] for g in games if g['gameweek']==n};folder=ROOT/f'data_v1_1/raw/fpl-core-2026-27/GW{n}'
  table(folder/'fixtures.csv',[g for g in games if g['match_id'] in mids],columns)
  table(folder/'lineups.csv',[r for r in lines if r['match_id'] in mids],['match_id','team_side','team_code','formation','player_id','player_uuid','player_name','is_starting','position','lineup_status','lineup_slot'])
  table(ROOT/f'data_v1_1/raw/all-competitions-2026-27/GW{n}/playermatchstats.csv',[r for r in stats if r['match_id'] in mids],['match_id','player_id','minutes_played'])
 gz(WORK/'player_match_events.jsonl.gz',stats);gz(WORK/'match_actuals.jsonl.gz',games)
 table(WORK/'ratings.csv',ratings,['provider','player_uuid','match_id','available_at','rating','observed_at','publication_at','timing_quality'])
 (ROOT/'data_v1_1/derived/mm_v2_ratings').mkdir(parents=True,exist_ok=True)
 (ROOT/'data_v1_1/derived/mm_v2_ratings/player_match_ratings_2026_27.csv.gz').write_bytes(gzip.compress((WORK/'ratings.csv').read_bytes(),mtime=0))
 assert len({(r['provider'],r['player_uuid'],r['match_id']) for r in ratings})==len(ratings)
 dump(WORK/'source_manifest.json',dict(season=season,observed_at=asof,target_gw=gw,deadline=deadline.isoformat(),sources=SOURCES,errors=ERRORS))
 dump(WORK/'collection_audit.json',dict(season=season,target_gw=gw,observed_at=asof,current_players=len(players),mapped_current_uuid=len(uuid_map),unresolved_current_identity=unresolved,completed_matches=dict(Counter(g['tournament'] for g in games)),lineup_rows=len(lines),player_event_rows=len(stats),ratings=len(ratings),strict_next_gw_news_rows=len(news),unmapped_provider_rows=unmapped,measured_average_position_rows=0,errors=ERRORS,publication_time_proxy='kickoff + 4h; preserve observed_at and do not relabel as exact publication',models_changed=False))
 print('CURRENT LOCKED INPUT COLLECTION',season,'GW',gw,'matches',len(games),'ratings',len(ratings),'news',len(news),'errors',len(ERRORS),flush=True)
if __name__=='__main__':main()

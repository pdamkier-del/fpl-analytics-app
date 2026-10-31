"""Independent, public all-competition match context. Never changes MM/PM/TS inputs."""
import argparse,concurrent.futures,csv,hashlib,json,re,time,unicodedata,math
from pathlib import Path
from datetime import datetime,timezone
from urllib.request import Request,urlopen
ROOT=Path(__file__).resolve().parents[1]
COMPETITIONS={'prem':(47,'Premier League'),'cl':(42,'Champions League'),'el':(73,'Europa League'),'conf':(10216,'Conference League'),'conf_qual':(10615,'Conference League Qualification'),'fa':(132,'FA Cup'),'efl':(133,'EFL Cup')}
def utc(s):return datetime.fromisoformat(str(s).replace('Z','+00:00')).astimezone(timezone.utc)
def norm(s):
 s=''.join(c for c in unicodedata.normalize('NFKD',s).lower()if c.isalnum())
 return {'manchestercity':'mancity','manchesterunited':'manutd','tottenhamhotspur':'spurs','tottenham':'spurs','nottinghamforest':'nottmforest','brightonandhovealbion':'brighton','brightonhovealbion':'brighton','wolverhamptonwanderers':'wolves','newcastleunited':'newcastle','westhamunited':'westham','ipswichtown':'ipswich','leedsunited':'leeds','afcbournemouth':'bournemouth'}.get(s,s)
def numeric(v):return v if isinstance(v,(float,int))and not isinstance(v,bool)and math.isfinite(v) else None
def values(player):return {v.get('key',k):v.get('stat',{}).get('value')for section in player.get('stats',[])for k,v in section.get('stats',{}).items()}
def build(bootstrap,fixtures,details,evidence,observed_at,coverage):
 eligible=[p for p in bootstrap['elements']if p.get('element_type')!=5];players={str(p['code']):p for p in eligible}
 if len(players)!=len(eligible):raise ValueError('Ambiguous FPL stable-code identity')
 clubs={norm(t['name']):t['id']for t in bootstrap['teams']};mapped={};conflicts=set()
 for comp,j,source in details:
  for p in (j.get('content',{}).get('playerStats')or{}).values():
   code=str(p.get('optaId','')).removeprefix('p');pid=str(p.get('id'))
   if code in players:
    if pid in mapped and mapped[pid]!=code:conflicts.add(pid)
    else:mapped[pid]=code
 for pid in conflicts:mapped.pop(pid,None)
 fpl={(f['team_h'],f['team_a'],utc(f['kickoff_time'])):f['id']for f in fixtures if f.get('kickoff_time')};curated={(str(r['fpl_code']),str(r['provider_match_id'])):r for r in evidence.get('records',[])}
 rows=[];unknown=0;missing_lineups=[]
 for comp,j,source in details:
  g=j['general'];mid=str(g['matchId']);kickoff=g['matchTimeUTCDate'];home,away=g['homeTeam'],g['awayTeam'];h,a=clubs.get(norm(home['name'])),clubs.get(norm(away['name']));line=j.get('content',{}).get('lineup')or{};stats=j.get('content',{}).get('playerStats')or{};seen=set()
  if not line.get('homeTeam',{}).get('starters')or not line.get('awayTeam',{}).get('starters'):missing_lineups.append(mid);continue
  for side in ['home','away']:
   block=line[side+'Team'];opponent=away if side=='home'else home;team=home if side=='home'else away
   for group in ['starters','subs','unavailable']:
    for p in block.get(group,[])or[]:
     pid=str(p['id']);code=mapped.get(pid)
     if code is None:unknown+=1;continue
     identity=(mid,players[code]['id'])
     if identity in seen:continue
     seen.add(identity);v=values(stats.get(pid,{ }));minutes=numeric(v.get('minutes_played'));events=p.get('performance',{}).get('substitutionEvents',[]);unavail=p.get('unavailability')or{};cause=False;reason=None;reason_source=source['url'];reason_date=None
     if group=='unavailable':reason='suspension'if unavail.get('type')=='suspension'else'unavailable';label='Suspenderet (kampkilden)'if reason=='suspension'else'Fravær ifølge kampkilden: '+str(unavail.get('type')or'årsag ikke oplyst');minutes=0
     elif group=='subs'and minutes is None and not any(e.get('type')=='subIn'for e in events)and numeric(p.get('performance',{}).get('rating'))is None and not (stats.get(pid,{})or{}).get('stats'):reason='unused_substitute';label='På bænken; ingen registreret indskiftning. Årsag ikke bekræftet.';minutes=0
     elif minutes==0 and group=='subs':reason='unused_substitute';label='Ubenyttet reserve; årsag ikke bekræftet'
     elif minutes is None:reason='minutes_unknown';label='Spilletid ikke oplyst'
     else:
      out=next((e for e in events if e.get('type')=='subOut'),None)
      reason='substituted_injury'if out and out.get('reason')=='injury'else'substituted_tactical'if out and out.get('reason')=='tactical'else'played'
      label={'substituted_injury':'Udskiftet · skade ifølge kampkilden','substituted_tactical':'Udskiftet · taktisk ifølge kampkilden','played':'Startede'if group=='starters'else'Indskiftet'}[reason]
     ev=curated.get((code,mid))
     if ev and minutes==0:
      if ev['reason_code']in ['rested','injury','suspension']and not ev.get('cause_confirmed'):raise ValueError('Unconfirmed causal absence evidence')
      reason=ev['reason_code'];label=ev['label'];cause=ev.get('cause_confirmed',False);reason_source=ev['source_url'];reason_date=ev.get('published_date')
     row=dict(player_id=players[code]['id'],fpl_code=int(code),provider_player_id=int(pid),provider_match_id=mid,competition=comp,competition_name=COMPETITIONS[comp][1],kickoff=kickoff,team=team['name'],opponent=opponent['name'],was_home=side=='home',home_score=j['header']['teams'][0].get('score'),away_score=j['header']['teams'][1].get('score'),started=group=='starters',minutes=minutes,goals=numeric(v.get('goals')),assists=numeric(v.get('assists')),xg=numeric(v.get('expected_goals')),xa=numeric(v.get('expected_assists')),shots=numeric(v.get('total_shots')),reason_code=reason,reason=label,cause_confirmed=cause,reason_source=reason_source,reason_published_date=reason_date,reason_source_sha256=ev.get('source_sha256')if ev else None,reason_source_observed_at=ev.get('observed_at')if ev else source['observed_at'],source_url=source['url'],source_observed_at=source['observed_at'],source_time_quality=source.get('capture_time_quality','HTTP_capture'))
     if comp=='prem':
      fid=fpl.get((h,a,utc(kickoff)))
      if fid is None:raise ValueError('PL fixture identity mismatch: '+mid)
      row['fpl_fixture_id']=fid
     rows.append(row)
 if len({(r['player_id'],r['provider_match_id'])for r in rows})!=len(rows):raise ValueError('Duplicate player/match context')
 return dict(schema='fpl-player-match-context-v1',observed_at=observed_at,rows=sorted(rows,key=lambda r:(r['kickoff'],r['player_id']),reverse=True),coverage=coverage,unmapped_provider_rows=unknown,ambiguous_provider_ids=sorted(conflicts),missing_lineups=missing_lineups,points_policy='Only Premier League fixtures award FPL points. Non-PL stats are context, never FPL points or a forecast update.')
def collect(out,cache):
 cache.mkdir(parents=True,exist_ok=True);sources=[];errors=[]
 prior_path=ROOT/'work/live-final-model/source_manifest.json';prior={r['url']:r for r in json.loads(prior_path.read_text()).get('sources',[])}if prior_path.exists()else{}
 def fetch(url,detail=False):
  key=hashlib.sha256(url.encode()).hexdigest();p=cache/key;meta=cache/(key+'.meta');old=ROOT/'.cache/current-locked-inputs'/key
  if detail and p.exists()and meta.exists()and (datetime.now(timezone.utc)-utc(json.loads(meta.read_text())['observed_at'])).total_seconds()<48*3600:b=p.read_bytes();at=json.loads(meta.read_text())['observed_at']
  elif detail and old.exists()and time.time()-old.stat().st_mtime<48*3600:
   b=old.read_bytes();previous=prior.get(url,{});exact=previous.get('sha256')==hashlib.sha256(b).hexdigest();at=previous['observed_at']if exact else datetime.fromtimestamp(old.stat().st_mtime,timezone.utc).isoformat();p.write_bytes(b);meta.write_text(json.dumps(dict(observed_at=at,capture_time_quality='original_source_manifest'if exact else'cached_file_timestamp')))
  else:
   b=urlopen(Request(url,headers={'User-Agent':'Mozilla/5.0 FPLAnalytics match-context'}),timeout=40).read();at=datetime.now(timezone.utc).isoformat();p.write_bytes(b);meta.write_text(json.dumps(dict(observed_at=at,capture_time_quality='HTTP_capture')))
  source=dict(url=url,observed_at=at,sha256=hashlib.sha256(b).hexdigest(),capture_time_quality=json.loads(meta.read_text()).get('capture_time_quality','unknown'));sources.append(source);return json.loads(b),source
 bootstrap,_=fetch('https://fantasy.premierleague.com/api/bootstrap-static/');fixtures,_=fetch('https://fantasy.premierleague.com/api/fixtures/');year=int(bootstrap['events'][0]['deadline_time'][:4]);season=f'{year}/{year+1}';clubs={norm(t['name'])for t in bootstrap['teams']};now=datetime.now(timezone.utc);selected={};coverage=[]
 for comp,(lid,label)in COMPETITIONS.items():
  try:
   j,source=fetch(f'https://www.fotmob.com/api/data/leagues?id={lid}&season={year}%2F{year+1}')
   if j['details']['selectedSeason']!=season or j['details']['name']!=label:raise ValueError('Provider season/competition mismatch')
   fs=[f for f in j.get('fixtures',{}).get('allMatches',[])if f.get('status',{}).get('finished')and f['status'].get('utcTime')and utc(f['status']['utcTime'])<=now and any(norm(f[s]['name'])in clubs for s in ['home','away'])]
   for f in fs:selected[str(f['id'])]=comp
   coverage.append(dict(competition=comp,status='verified_inventory',matches=len(fs)))
  except Exception as e:coverage.append(dict(competition=comp,status='unavailable',error=type(e).__name__));errors.append(dict(competition=comp,error=str(e)))
 def one(item):
  mid,comp=item
  try:
   j,source=fetch('https://www.fotmob.com/api/data/matchDetails?matchId='+mid,True);g=j['general']
   if str(g['matchId'])!=mid or not g.get('finished')or utc(g['matchTimeUTCDate'])>now:raise ValueError('Wrong/unfinished match detail')
   if str(g.get('parentLeagueId',g.get('leagueId')))!=str(COMPETITIONS[comp][0]):raise ValueError('Wrong competition in match detail')
   return comp,j,source
  except Exception as e:errors.append(dict(match_id=mid,error=str(e)));return None
 with concurrent.futures.ThreadPoolExecutor(5)as pool:details=[r for r in pool.map(one,selected.items())if r]
 if not details:raise ValueError('No verified match context')
 evidence=json.loads((ROOT/'data_v1_1/curated/player-match-absence-evidence.json').read_text());at=datetime.now(timezone.utc).isoformat();data=build(bootstrap,fixtures,details,evidence,at,coverage);data['collection_errors']=errors;data['season']=season;data['sources']=sorted(sources,key=lambda s:s['url'])
 out.mkdir(parents=True,exist_ok=True);b=(json.dumps(data,ensure_ascii=False,sort_keys=True,separators=(',',':'))+'\n').encode();(out/'player-matches.json').write_bytes(b);index=dict(schema='fpl-player-match-context-index-v1',observed_at=at,season=season,file='player-matches.json',sha256=hashlib.sha256(b).hexdigest(),matches=len(details),player_rows=len(data['rows']),coverage=coverage,collection_errors=errors);(out/'index.json').write_text(json.dumps(index,sort_keys=True)+'\n');print(json.dumps({k:v for k,v in index.items()if k!='sha256'},indent=2))
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--out',type=Path,default=ROOT/'app/mm-preview/match-context');p.add_argument('--cache',type=Path,default=ROOT/'.cache/player-match-context');a=p.parse_args();collect(a.out,a.cache)

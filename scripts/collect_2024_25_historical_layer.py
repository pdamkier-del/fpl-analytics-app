"""Append-only 2024/25 data collection, NOT a forecasting/model runner.
Pinned Git raw values; provenance separates final outcomes from as-of evidence.
Resume immutable HTTP captures from cache. Never writes 2025/26 inputs or src/.
"""
import concurrent.futures as cf
import datetime as dt
import gzip
import hashlib
import io
import json
import lzma
import os
from pathlib import Path
import re
import sqlite3
import time
import unicodedata
import urllib.parse as up
import urllib.request as ur
import pandas as pd

ROOT=Path(__file__).resolve().parents[1]
CONF=json.loads((ROOT/'research/season_2024_25_v1/config.json').read_text())
RAW=ROOT/'data_v1_1/raw/season_2024_25_v1'
OUT=ROOT/'data_v1_1/derived/season_2024_25_v1'
AUDIT=ROOT/'analysis/results/season-2024-25-data-audit-v1'
CACHE=ROOT/'.cache/season-2024-25-data-v1'
UTC=dt.timezone.utc
SOURCES=[]; ERRORS=[]

def sha(b): return hashlib.sha256(b).hexdigest()
def T(s): return pd.Timestamp(s,tz='UTC') if pd.Timestamp(s).tz is None else pd.Timestamp(s).tz_convert('UTC')
def dump(p,obj): p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(obj,indent=2,ensure_ascii=False,default=str)+'\n')
def gz(p,rows):
 p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(gzip.compress((''.join(json.dumps(r,ensure_ascii=False,default=str,sort_keys=True)+'\n' for r in rows)).encode(),mtime=0))
def fetch(url):
 CACHE.mkdir(parents=True,exist_ok=True);p=CACHE/sha(url.encode())
 if p.exists():return p.read_bytes()
 h={'User-Agent':'Mozilla/5.0 FPL-historical-audit'}
 if url.startswith('https://api.github.com/') and os.environ.get('GH_TOKEN'):h['Authorization']='Bearer '+os.environ['GH_TOKEN']
 for attempt in range(3):
  try:
   b=ur.urlopen(ur.Request(url,headers=h),timeout=35).read();p.write_bytes(b);return b
  except Exception:
   if attempt==2:raise
   time.sleep(1+attempt)
def js(url):return json.loads(fetch(url))
def capture(url,path,quality,blob=None):
 b=fetch(url)
 if blob:assert hashlib.sha1(b'blob '+str(len(b)).encode()+b'\0'+b).hexdigest()==blob,(path,'Git hash mismatch')
 p=RAW/path;p.parent.mkdir(parents=True,exist_ok=True)
 if p.exists() and p.read_bytes()!=b:raise FileExistsError('Immutable raw capture differs '+str(p))
 if not p.exists():p.write_bytes(b)
 SOURCES.append(dict(path=str(p.relative_to(ROOT)),url=url,sha256=sha(b),git_blob_sha=blob,bytes=len(b),quality=quality,retrieved_at=dt.datetime.now(UTC).isoformat()))
 return b

def github_files():
 paths=[]
 for repo,base in [('Vaastav/Fantasy-Premier-League','data/2024-25'),('olbauday/FPL-Core-Insights','data/2024-2025')]:
  pin=CONF['pins'][repo]
  top=js(f'https://api.github.com/repos/{repo}/contents/{base}?ref={pin}')
  for e in top:
   if e['type']=='file' and e['name'].endswith('.csv'):paths.append((repo,pin,base+'/'+e['name'],e['sha']))
   if e['type']=='dir' and e['name'] in {'gws','understat','matches','playermatchstats','players','teams','playerstats'}:
    # Vaastav players/ duplicates GW data; understat keeps the full per-match source.
    if repo.startswith('Vaastav') and e['name']=='players':continue
    tree=js(f"https://api.github.com/repos/{repo}/git/trees/{e['sha']}?recursive=1");assert not tree.get('truncated')
    for f in tree['tree']:
     if f['type']=='blob' and f['path'].endswith('.csv'):paths.append((repo,pin,base+'/'+e['name']+'/'+f['path'],f['sha']))
 def one(r):
  repo,pin,path,blob=r
  try:capture(f'https://raw.githubusercontent.com/{repo}/{pin}/{up.quote(path)}',repo.split('/')[0]+'/'+path,'EXACT_POSTMATCH',blob)
  except Exception as e:ERRORS.append(dict(source=repo,path=path,error=str(e)))
 with cf.ThreadPoolExecutor(max_workers=6) as ex:list(ex.map(one,paths))
 print('Git CSV sources',len(paths),'errors',len(ERRORS),flush=True)


def snapshots():
 repo='Randdalf/fplcache';pin=CONF['pins'][repo];candidates=[]
 for year,tree in CONF['cache_trees'].items():
  j=js(f'https://api.github.com/repos/{repo}/git/trees/{tree}?recursive=1');assert not j.get('truncated')
  for e in j['tree']:
   m=re.fullmatch(r'(\d+)/(\d+)/(\d{2})(\d{2})\.json\.xz',e['path'])
   if m:
    mo,day,hh,mm=map(int,m.groups());candidates.append(dict(path=f"cache/{year}/{e['path']}",blob=e['sha'],nominal=dt.datetime(int(year),mo,day,hh,mm,tzinfo=UTC)))
 candidates.sort(key=lambda e:e['nominal'])
 ref=next(e for e in candidates if e['path']=='cache/2025/5/25/1247.json.xz')
 b=capture(f"https://raw.githubusercontent.com/{repo}/{pin}/{ref['path']}",'bootstrap/deadline_reference.json.xz','EXACT_POSTMATCH',ref['blob'])
 payload=json.loads(lzma.decompress(b));deadlines=[dict(gw=e['id'],cutoff=e['deadline_time']) for e in payload['events']]
 assert len(deadlines)==38 and T(deadlines[0]['cutoff']).year==2024
 rows=[];metadata=[]
 for d in deadlines:
  cutoff=T(d['cutoff']); pre=[e for e in candidates if e['nominal']<cutoff][-1]
  url=f'https://api.github.com/repos/{repo}/commits?sha={pin}&path='+pre['path']+'&per_page=1'
  commit=js(url)[0];parent=commit['parents'][0]['sha'];clock=max(T(commit['commit']['committer']['date']),T(pre['nominal']))
  runs_url=f'https://api.github.com/repos/{repo}/actions/runs?head_sha={parent}&per_page=100'
  runs=js(runs_url);assert runs['total_count']<=100
  verified=False;effective=clock;server_job=None
  for run in runs['workflow_runs']:
   if run.get('name')!='cache' or run.get('head_sha')!=parent or run.get('conclusion')!='success':continue
   jobs=js(f"https://api.github.com/repos/{repo}/actions/runs/{run['id']}/jobs?per_page=100")
   for job in jobs['jobs']:
    if job.get('name')=='cache' and job.get('conclusion')=='success' and job.get('completed_at') and T(job['started_at'])<=T(commit['commit']['committer']['date'])<=T(job['completed_at']):
     effective=max(clock,T(job['completed_at']));verified=True;server_job=job
  rawurl=f"https://raw.githubusercontent.com/{repo}/{commit['sha']}/{pre['path']}"
  b=capture(rawurl,f"bootstrap/gw{d['gw']:02d}.json.xz",'EXACT_PREDEADLINE' if verified and effective<cutoff else 'UNAVAILABLE',pre['blob'])
  j=json.loads(lzma.decompress(b));event=next(e for e in j['events'] if e['id']==d['gw']);match=T(event['deadline_time'])==cutoff
  verified=verified and match and effective<cutoff
  metadata.append(dict(gw=d['gw'],cutoff=d['cutoff'],clock_at=str(clock),effective_at=str(effective),timing_verified=verified,deadline_matches=match,source_commit=commit['sha'],source_url=rawurl,parent_commit=parent,run_metadata_url=runs_url,commit_metadata_url=url,server_job_id=server_job['id'] if server_job else None,source_sha256=sha(b),age_hours=(cutoff-clock).total_seconds()/3600))
  teams={t['id']:t for t in j['teams']}
  for e in j['elements']:
   if e.get('element_type')==5:continue
   rows.append(dict(season='2024-25',gw=d['gw'],cutoff=d['cutoff'],fpl_element=e['id'],fpl_code=e['code'],player_name=e['first_name']+' '+e['second_name'],web_name=e['web_name'],team_id=e['team'],team_code=teams[e['team']]['code'],team=teams[e['team']]['name'],fpl_position=e['element_type'],price_tenths=e['now_cost'],status=e.get('status'),news=e.get('news'),news_added=e.get('news_added'),chance_this_round=e.get('chance_of_playing_this_round'),chance_next_round=e.get('chance_of_playing_next_round'),current_event=next((v['id'] for v in j['events'] if v.get('is_current')),None),next_event=next((v['id'] for v in j['events'] if v.get('is_next')),None),observed_at=str(pre['nominal']),effective_at=str(effective),clock_at=str(clock),timing_verified=verified,forecast_eligible=verified,quality='EXACT_PREDEADLINE' if verified else 'UNAVAILABLE',source_url=rawurl))
  print('Snapshot GW',d['gw'],'players',len(j['elements']),'verified',verified,flush=True)
 gz(OUT/'deadline_player_candidates.jsonl.gz',rows);dump(OUT/'deadlines.json',deadlines);dump(AUDIT/'snapshot_provenance.json',metadata)
 return pd.DataFrame(rows),deadlines

def core_export():
 con=sqlite3.connect((ROOT/'work/core.sqlite3').resolve().as_uri()+'?mode=ro',uri=True)
 tables={r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'")};inventory=[]
 dump(OUT/'core_schema.json',{r[0]:r[1] for r in con.execute("SELECT name,sql FROM sqlite_master WHERE type='table' AND sql IS NOT NULL")})
 for name in sorted(tables):
  columns=[r[1] for r in con.execute('PRAGMA table_info('+name+')')]
  if 'season' in columns:
   df=pd.read_sql_query('SELECT * FROM '+name+" WHERE season='2024-25'",con)
   inventory.append(dict(table=name,rows=len(df),columns=columns))
   if len(df):gz(OUT/('existing_core_'+name+'.jsonl.gz'),df.to_dict('records'))
 ids=pd.read_sql_query("SELECT * FROM player_id_mapping",con)
 players=pd.read_sql_query('SELECT * FROM players',con)
 gz(OUT/'reference_player_identity_rows.jsonl.gz',ids.to_dict('records'));gz(OUT/'reference_player_names.jsonl.gz',players.to_dict('records'))
 con.close();dump(AUDIT/'existing_core_inventory.json',inventory)
 return ids,players

def norm(name):return ''.join(c for c in unicodedata.normalize('NFKD',str(name)).casefold() if c.isalnum())
ALIAS={'manchestercity':'mancity','manchesterunited':'manutd','nottinghamforest':'nottmforest','tottenhamhotspur':'spurs','tottenham':'spurs','brightonhovealbion':'brighton','brightonandhovealbion':'brighton','wolverhamptonwanderers':'wolves','newcastleunited':'newcastle','westhamunited':'westham','ipswichtown':'ipswich','leicestercity':'leicester','afcbournemouth':'bournemouth'}
def club(name):s=norm(name);return ALIAS.get(s,s)

def external_inventories(teams):
 plnames={club(n) for n in teams['name']};events={};league_codes={'prem':'eng.1','fa':'eng.fa','efl':'eng.league_cup','cl':'uefa.champions','el':'uefa.europa','conf':'uefa.europa.conf'}
 probes=[]
 # Provider payloads are final-match evidence only; not historical future schedules.
 for comp,code in league_codes.items():
  url=f'https://site.api.espn.com/apis/site/v2/sports/soccer/{code}/scoreboard?dates=20240701-20250601&limit=1000'
  try:
   b=capture(url,f'espn/{comp}/inventory.json','EXACT_POSTMATCH');j=json.loads(b);ev=j.get('events',[])
   probes.append(dict(competition=comp,url=url,event_rows=len(ev),potential_truncation=len(ev)>=1000))
   for e in ev:
    sides=e.get('competitions',[{}])[0].get('competitors',[])
    if any(club(s.get('team',{}).get('displayName','')) in plnames for s in sides):events[(comp,e['id'])]=e
  except Exception as e:ERRORS.append(dict(source='ESPN',competition=comp,url=url,error=str(e)))
 def summary(item):
  (comp,eid),e=item;code=league_codes[comp]
  url=f'https://site.api.espn.com/apis/site/v2/sports/soccer/{code}/summary?event={eid}'
  try:
   capture(url,f'espn/{comp}/summaries/{eid}.json','EXACT_POSTMATCH')
  except Exception as ex:ERRORS.append(dict(source='ESPN',competition=comp,event=eid,error=str(ex)))
 with cf.ThreadPoolExecutor(max_workers=6) as ex:list(ex.map(summary,events.items()))
 dump(AUDIT/'external_inventory_probes.json',probes)
 # Direct provider probes: preserve failures and do not hammer denied endpoints.
 selected={}
 for comp,lid in [('prem',47),('cl',42),('el',73),('conf',10216),('conf_qual',10615),('fa',132),('efl',133)]:
  url=f'https://www.fotmob.com/api/data/leagues?id={lid}&season=2024%2F2025'
  try:
   league=json.loads(capture(url,f'fotmob/{comp}_{lid}_league.json','EXACT_POSTMATCH'))
   expected={'prem':'Premier League','cl':'Champions League','el':'Europa League','conf':'Conference League','conf_qual':'Conference League Qualification','fa':'FA Cup','efl':'EFL Cup'}
   assert league['details']['name']==expected[comp],(comp,league['details'])
   for e in (league.get('fixtures') or {}).get('allMatches',[]):
    status=e.get('status') or {};ko=pd.to_datetime(status.get('utcTime'),utc=True,errors='coerce')
    if pd.isna(ko) or not (T('2024-07-01')<=ko<T('2025-06-02')):continue
    if any(club((e.get(side) or {}).get('name','')) in plnames for side in ['home','away']):selected[str(e['id'])]=(comp,e)
  except Exception as e:ERRORS.append(dict(source='FotMob',competition=comp,url=url,error=str(e)))
 # Pin PL provider match IDs already witnessed in the archived Core source too.
 for p in sorted((RAW/'olbauday/data/2024-2025/matches').rglob('matches.csv')):
  df=pd.read_csv(p)
  for e in df.to_dict('records'):
   if pd.notna(e.get('fotmob_id')):selected.setdefault(str(int(e['fotmob_id'])),('prem',e))
 def detail(pair):
  mid,(comp,e)=pair;url=f'https://www.fotmob.com/api/data/matchDetails?matchId={mid}'
  try:capture(url,f'fotmob/details/{mid}.json','EXACT_POSTMATCH')
  except Exception as ex:ERRORS.append(dict(source='FotMob',competition=comp,match_id=mid,url=url,error=str(ex)))
 # Small probe before a full pass; preserve a denied provider as unavailable.
 pairs=list(selected.items());probe=pairs[:3]
 before=len(ERRORS)
 for pair in probe:detail(pair)
 if len(ERRORS)-before<len(probe):
  with cf.ThreadPoolExecutor(max_workers=5) as ex:list(ex.map(detail,pairs[3:]))
 dump(AUDIT/'fotmob_selected_inventory.json',[dict(provider_match_id=mid,competition=c,fixture=e) for mid,(c,e) in selected.items()])
 return events

def main():
 for d in [RAW,OUT,AUDIT]:d.mkdir(parents=True,exist_ok=True)
 github_files()
 try:capture('https://www.football-data.co.uk/mmz4281/2425/E0.csv','football_data/E0.csv','EXACT_POSTMATCH')
 except Exception as e:ERRORS.append(dict(source='football-data',error=str(e)))
 snaps,deadlines=snapshots();ids,players=core_export()
 raw=pd.read_csv(RAW/'Vaastav/data/2024-25/players_raw.csv');teams=pd.read_csv(RAW/'Vaastav/data/2024-25/teams.csv')
 byid={}
 for r in ids[(ids.id_namespace=='fpl_element') & (ids.season=='2024-25')].itertuples():byid.setdefault(str(r.external_id),set()).add(r.player_uuid)
 bycode={}
 for r in ids[ids.id_namespace=='fpl_code'].itertuples():bycode.setdefault(str(r.external_id),set()).add(r.player_uuid)
 identity=[]
 for r in raw.itertuples():
  if r.element_type==5:continue
  a=byid.get(str(r.id),set());b=bycode.get(str(r.code),set());choices=a&b if a and b else b
  identity.append(dict(season='2024-25',fpl_element=r.id,fpl_code=r.code,player_name=r.first_name+' '+r.second_name,player_uuid=next(iter(choices)) if len(choices)==1 else None,status='mapped' if len(choices)==1 else 'ambiguous' if len(choices)>1 else 'unresolved',rule='exact season element corroborated by stable code' if a and b else 'exact stable FPL code',end_season_team_not_a_feature=r.team))
 pd.DataFrame(identity).to_csv(OUT/'player_identity.csv',index=False)
 # Actuals are kept in separate postmatch files. Never use current-GW value as deadline price.
 gws=pd.concat([pd.read_csv(RAW/f'Vaastav/data/2024-25/gws/gw{gw}.csv').assign(gw=gw) for gw in range(1,39)],ignore_index=True)
 gws['available_at_proxy']=(pd.to_datetime(gws.kickoff_time,utc=True)+pd.Timedelta(hours=3)).astype(str)
 gws['quality']='EXACT_POSTMATCH';gws['timing_quality']='PROXY_CUTOFF_SAFE';gws['season']='2024-25'
 gws=gws.merge(pd.DataFrame(identity)[['fpl_element','player_uuid','status']],left_on='element',right_on='fpl_element',how='left',validate='many_to_one')
 gws.to_csv(OUT/'player_fixture_actuals.csv.gz',index=False,compression={'method':'gzip','mtime':0})
 fixtures=pd.read_csv(RAW/'Vaastav/data/2024-25/fixtures.csv');fixtures['season']='2024-25';fixtures['quality']='EXACT_POSTMATCH';fixtures['future_schedule_forecast_eligible']=False
 fixtures.to_csv(OUT/'pl_fixture_actuals.csv',index=False)
 events=external_inventories(teams)
 dump(AUDIT/'collection_errors.json',ERRORS);dump(AUDIT/'source_manifest.json',dict(config=CONF,sources=sorted(SOURCES,key=lambda r:r['path']),errors=ERRORS))
 # Raw source pack retains exact bytes and is checkpointed separately; not just Actions cache.
 import tarfile
 with tarfile.open(AUDIT/'raw_sources.tar.xz','w:xz') as tar:
  for p in sorted(RAW.rglob('*')):
   if p.is_file():tar.add(p,arcname=str(p.relative_to(RAW)))
 dump(AUDIT/'collection_summary.json',dict(raw_files=len(SOURCES),errors=len(ERRORS),player_fixture_rows=len(gws),fixtures=len(fixtures),snapshot_candidate_rows=len(snaps),certified_snapshot_gws=sorted(snaps[snaps.timing_verified].gw.unique().tolist()),identity_counts=pd.DataFrame(identity).status.value_counts().to_dict(),espn_selected_events=len(events),no_model_execution=True))
 print('COMPLETE collection',len(SOURCES),'sources',len(ERRORS),'errors',flush=True)

if __name__=='__main__':main()

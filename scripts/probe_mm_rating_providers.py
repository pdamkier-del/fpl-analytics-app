#!/usr/bin/env python3
"""Probe original provider rating schemas without altering any model."""
import json,time,urllib.parse,urllib.request
from pathlib import Path
OUT=Path('analysis/results/mm-rating-provider-probe-20261006-v1')
OUT.mkdir(parents=True,exist_ok=True)
errors=[]

def fetch(name,base,path,**params):
 url=base+'/'+path+'?'+urllib.parse.urlencode(params)
 try:
  req=urllib.request.Request(url,headers={'User-Agent':'FPL-analytics research rating ingestion','Accept':'application/json'})
  with urllib.request.urlopen(req,timeout=45) as handle:result=json.load(handle)
  (OUT/(name+'.json')).write_text(json.dumps(result,ensure_ascii=False))
  print(name,'OK',list(result) if isinstance(result,dict) else type(result).__name__,flush=True)
  return result
 except Exception as e:
  errors.append({'name':name,'url':url,'error':str(e)})
  print(name,'ERROR',str(e),flush=True);return None

fot='https://www.fotmob.com/api/data'
league=fetch('fotmob_pl_2025',fot,'leagues',id=47,season='2025/2026')
fetch('fotmob_all_leagues',fot,'allLeagues')
if league:
 matches=league.get('matches',{}).get('allMatches',[]) or league.get('fixtures',{}).get('allMatches',[])
 finished=[m for m in matches if m.get('status',{}).get('finished')]
 if finished:
  first=sorted(finished,key=lambda m:str(m.get('status',{}).get('utcTime','')))[0]
  fetch('fotmob_match',fot,'matchDetails',matchId=first['id'])
sofa='https://www.sofascore.com/api/v1'
seasons=fetch('sofascore_pl_seasons',sofa,'unique-tournament/17/seasons')
if seasons:
 season=next((s for s in seasons.get('seasons',[]) if str(s.get('year')) in ['25/26','2025/2026','2025/26']),None)
 if season:
  events=fetch('sofascore_pl_events',sofa,f'unique-tournament/17/season/{season["id"]}/events/last/0')
  finished=[e for e in (events or {}).get('events',[]) if e.get('status',{}).get('type')=='finished']
  if finished:fetch('sofascore_lineups',sofa,f'event/{finished[0]["id"]}/lineups')
(OUT/'errors.json').write_text(json.dumps(errors,indent=2))

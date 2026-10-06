#!/usr/bin/env python3
import json,requests
BASE='https://www.fotmob.com/api/data'
S=requests.Session();S.headers.update({'user-agent':'fotmob-api (+https://github.com)','accept':'application/json'})
def get(path,**params):
 r=S.get(f'{BASE}/{path}',params=params,timeout=30);r.raise_for_status();return r.json()
a=get('allLeagues')
hits=[]
for country in a.get('countries',[]):
 for l in country.get('leagues',[]):
  if 'fa cup' in str(l.get('name','')).lower():
   hits.append({'country':country.get('name'),'ccode':country.get('ccode'),**l})
print('HITS',json.dumps(hits,ensure_ascii=False))
if not hits: raise SystemExit('no FA Cup')
fa=next((x for x in hits if x.get('ccode')=='ENG' or x.get('country')=='England'),hits[0])
lid=fa['id']
league=get('leagues',id=lid,season='2025/2026')
print('LEAGUE_KEYS',list(league))
print('DETAILS',json.dumps(league.get('details'),ensure_ascii=False)[:5000])
print('FIXTURES_TYPE',type(league.get('fixtures')).__name__)
print('FIXTURES',json.dumps(league.get('fixtures'),ensure_ascii=False)[:20000])
from pathlib import Path
out=Path('analysis/results/fotmob-fa-probe-20261006')
out.mkdir(parents=True,exist_ok=True)
payload={'hits':hits,'fa':fa,'league_keys':list(league),'details':league.get('details'),'fixtures':league.get('fixtures')}
(out/'probe.json').write_text(json.dumps(payload,ensure_ascii=False,indent=2))

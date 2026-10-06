"""Capture source/schema research independently of all forecast code.
Current payload is schema evidence only, never a historical availability input.
"""
import datetime as dt
import hashlib
import json
from pathlib import Path
import re
import subprocess
import urllib.request

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'analysis/results/team-news-source-research-20261006-v1'
SOURCES=[
 ('official_bootstrap','https://fantasy.premierleague.com/api/bootstrap-static/'),
 ('injury_hub','https://www.premierleague.com/en/news/4242565'),
 ('suspension_hub','https://www.premierleague.com/en/news/4425344'),
 ('player_notes','https://www.premierleague.com/en/news/4485566/new-player-notes-feature-warns-fpl-managers-of-possible-upcoming-absences'),
 ('gw1_guide','https://www.premierleague.com/en/news/4373995/quick-fantasy-tips-your-basic-guide-to-gameweek-1'),
 ('gw12_guide','https://www.premierleague.com/en/news/4462450'),
 ('gw38_guide','https://www.premierleague.com/en/news/4664134/everything-you-need-for-gameweek-38-of-fpl-with-the-latest-tips-and-advice'),
 ('predicted_xi_example','https://www.premierleague.com/en/news/4720146/predicted-line-ups-for-premier-league-teams-in-matchweek-5'),
 ('club_team_news_example','https://www.chelseafc.com/en/news/article/enzo-maresca-delivers-chelsea-team-news-ahead-of-newcastle'),
]

def main():
 if OUT.exists(): raise FileExistsError('Append-only source research version already exists')
 OUT.mkdir(parents=True)
 rows=[]
 for name,url in SOURCES:
  observed=dt.datetime.now(dt.timezone.utc).isoformat()
  row=dict(name=name,url=url,observed_at=observed,historical_input_eligible=False)
  try:
   with urllib.request.urlopen(urllib.request.Request(url,headers={'User-Agent':'Mozilla/5.0'}),timeout=45) as r:
    raw=r.read(); row.update(bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest(),response_date=r.headers.get('Date'),last_modified=r.headers.get('Last-Modified'))
   if name=='official_bootstrap':
    j=json.loads(raw)
    keys=sorted(set().union(*(set(e) for e in j['elements'])))
    row['element_keys']=keys
    row['availability_schema']={k:dict(present=sum(k in e for e in j['elements']),nonnull=sum(e.get(k) is not None for e in j['elements']),types=sorted({type(e.get(k)).__name__ for e in j['elements']})) for k in ['status','news','news_added','chance_of_playing_this_round','chance_of_playing_next_round']}
    row['additional_news_note_keys']=[k for k in keys if re.search('news|note|availability|susp',k,re.I)]
    row['status_counts']={k:sum(e.get('status')==k for e in j['elements']) for k in sorted({e['status'] for e in j['elements']})}
    # Preserve only schema sample, not current statistics/results or model inputs.
    (OUT/'current_schema_sample.json').write_text(json.dumps({k:j['elements'][0].get(k) for k in ['id','code','status','news','news_added','chance_of_playing_this_round','chance_of_playing_next_round']},indent=2)+'\n')
   else:
    text=raw.decode('utf-8',errors='replace')
    row['date_metadata_candidates']=re.findall(r'(?:datePublished|dateModified|article:published_time|article:modified_time)[^\n]{0,160}',text)[:10]
    row['publication_interpretation']='Today retrieval of potentially mutable article; header date is insufficient to certify this body before a historical deadline.'
  except Exception as e:
   row['error']=str(e)
  rows.append(row)
 (OUT/'sources.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2)+'\n')
 paths=subprocess.check_output(['git','ls-tree','-r','--long','HEAD'],cwd=ROOT,text=True).splitlines()
 inventory=[]
 for line in paths:
  metadata,path=line.split('\t',1)
  if re.search('bootstrap|snapshot|availability|team.news|cache|blocked-roster',path,re.I):
   inventory.append(dict(path=path,git_metadata=metadata))
 (OUT/'repository_inventory.json').write_text(json.dumps(dict(head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),candidates=inventory),indent=2)+'\n')
 print(json.dumps([dict(name=r['name'],error=r.get('error'),bytes=r.get('bytes')) for r in rows],indent=2))

if __name__=='__main__': main()

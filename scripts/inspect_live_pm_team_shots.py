#!/usr/bin/env python3
"""Read-only provenance probe for FotMob team shot and xG match stats."""
from pathlib import Path
import json
ROOT=Path(__file__).resolve().parents[1]
raw=ROOT/'data_v1_1/raw/live-captures'
files=sorted(raw.glob('*/fotmob/details/*.json'))
if not files:raise FileNotFoundError('Restore 2026 source archive first')
counts={};examples=[]
for f in files:
  o=json.loads(f.read_text())
  c=o.get('content',{})
  for k in c:counts[k]=counts.get(k,0)+1
  parts=c.get('stats',{}).get('Periods',{}).get('All',[])
  if isinstance(parts,list):
    matches=[]
    for block in parts:
      for item in block.get('stats',[]):
        title=str(item.get('title',''))
        if any(term in title.lower() for term in ('target','shot','xg','expected goal','saves')):
          matches.append({k:item.get(k) for k in ('title','stats','type')})
    if matches and len(examples)<3:examples.append({'match_id':o.get('general',{}).get('matchId'),'path':str(f.relative_to(ROOT)),
        'labels':matches[:14]})
print('FOTMOB TEAM MATCH FACTS FIELD AUDIT',json.dumps({'files':len(files),'content_keys':counts,'examples':examples},ensure_ascii=False))

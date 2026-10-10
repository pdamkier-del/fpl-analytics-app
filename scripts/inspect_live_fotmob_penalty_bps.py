#!/usr/bin/env python3
"""Inventory archived FotMob PL penalty/BPS evidence, without guessing aliases.

This scans already restored official-source checkpoint JSON. Writes actionable
field coverage and example paths; never generates invented BPS / penalty CSVs.
"""
from __future__ import annotations
import argparse,collections,json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
SOURCE=ROOT/'data_v1_1/raw/live-captures'
OUT=ROOT/'work/live-final-model/provider_penalty_bps_evidence.json'
BPS_KEYS=('accurate_crosses','blocks','clearances','interceptions','recoveries',
 'tackles_won','chances_created','successful_dribbles','was_fouled',
 'shots_on_target','accurate_passes','accurate_passes_percent',
 'big_chances_missed','fouls_committed','offsides','total_shots','dispossessed')
def shotmap_evidence(section):
    """Inventory provider-declared event keys without interpreting them."""
    rows=section if isinstance(section,list) else (section.get('shots',[]) if isinstance(section,dict) else [])
    fields=collections.Counter();explicit=collections.Counter();examples={}
    for item in rows:
        if not isinstance(item,dict):continue
        for key,value in item.items():
            fields[str(key)]+=1
            if 'penalt' in str(key).lower() or (
                isinstance(value,str) and 'penalt' in value.lower()):
                tag=str(key)+'='+str(value)
                explicit[tag]+=1
                examples.setdefault(tag,{k:item.get(k) for k in ('id','playerId','teamId','eventType','shotType','situation','isPenalty') if k in item})
    return fields,explicit,examples

def inspect(root=SOURCE):
    paths=sorted(root.glob('*/fotmob/details/*.json'))
    if not paths:raise FileNotFoundError('Restore live input checkpoint first')
    appearances=collections.Counter()
    examples={}
    events=collections.Counter()
    raw_labels=collections.Counter()
    matches=0;players=0
    shot_fields=collections.Counter();penalty_markers=collections.Counter();penalty_examples={}
    for path in paths:
        d=json.loads(path.read_text())
        content=d.get('content') or {}
        matches+=1
        for player_id,player in (content.get('playerStats') or {}).items():
            players+=1
            for section in player.get('stats') or []:
                for label,value in (section.get('stats') or {}).items():
                    key=str(value.get('key') or label)
                    appearances[key]+=1
                    examples.setdefault(key,{'file':str(path.relative_to(root)),
                                             'player_id':str(player_id),'label':str(label)})
        sf,pm,pe=shotmap_evidence(content.get('shotmap'))
        shot_fields.update(sf);penalty_markers.update(pm)
        for key,val in pe.items():penalty_examples.setdefault(key,dict(val,source_path=str(path.relative_to(root))))
        for key in ('shotmap','shots','events','incidents'):
            if key in content:
                raw=content[key]
                events[key]+=1
                # Do not interpret provider-specific event codes as confirmed
                # penalties without a verified documentation mapping.
                if isinstance(raw,dict):raw_labels.update(str(x) for x in raw)
    missing=[k for k in BPS_KEYS if appearances[k]==0]
    return {
      'classification':'RAW_FOTMOB_FIELD_EVIDENCE_NOT_MODEL_FEATURES',
      'matches':matches,'player_sections':players,
      'bps_observed_keys':{k:appearances[k] for k in BPS_KEYS},
      'bps_missing_exact_fields':missing,
      'event_sections':dict(events),
      'event_section_labels':dict(raw_labels),
      'field_examples':{k:examples.get(k) for k in BPS_KEYS if k in examples},
      'shotmap_raw_fields':dict(shot_fields),
      'explicit_penalty_shot_markers':dict(penalty_markers),
      'explicit_penalty_examples':penalty_examples,
      'penalty_attempts_verified':False,
      'penalty_taker_identity_verified':False,
      'bps_complete':False if missing else None,
      'model_certified':False,
      'note':'Only exact raw field names counted. Historical BPS proxy formula needs provider semantic audits; penalty events require independently verified code and scorer mapping.'}
def main():
    p=argparse.ArgumentParser()
    p.add_argument('--raw',type=Path,default=SOURCE)
    p.add_argument('--out',type=Path,default=OUT)
    args=p.parse_args();result=inspect(args.raw)
    args.out.parent.mkdir(parents=True,exist_ok=True)
    args.out.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({k:result[k] for k in ('matches','bps_missing_exact_fields','event_sections','penalty_attempts_verified','model_certified')}))
if __name__=='__main__':main()

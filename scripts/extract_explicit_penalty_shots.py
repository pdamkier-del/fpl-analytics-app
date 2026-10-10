#!/usr/bin/env python3
"""Extract literal provider-declared penalty shot candidates, never guesses.

This is source evidence only. It cannot be promoted to penalty_attempts until
player UUID, fixture mapping, outcome and full-zero-side coverage are verified.
"""
from __future__ import annotations
import argparse,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
CAP=ROOT/'data_v1_1/raw/live-captures'
OUT=ROOT/'work/live-final-model/explicit_penalty_shot_evidence.json'
def candidates(root):
    rows=[];matches=0;shot_total=0;shootout_excluded=0;ambiguous_excluded=0
    for path in sorted(Path(root).glob('*/fotmob/details/*.json')):
        d=json.loads(path.read_text());matches+=1
        shotmap=(d.get('content') or {}).get('shotmap')
        shots=shotmap if isinstance(shotmap,list) else (shotmap.get('shots',[]) if isinstance(shotmap,dict) else [])
        for idx,shot in enumerate(shots):
            if not isinstance(shot,dict):continue
            shot_total+=1
            tags={str(k):v for k,v in shot.items() if 'penalt' in str(k).lower() or (isinstance(v,str) and 'penalt' in v.lower())}
            if not tags:continue
            # A shoot-out shot is never a Premier League match penalty.
            # Require the provider's explicit match-penalty situation.
            if str(shot.get('period','')).lower()=='penaltyshootout':
                shootout_excluded+=1;continue
            if str(shot.get('situation','')).lower()!='penalty':
                ambiguous_excluded+=1;continue
            rows.append({'source_path':str(path.relative_to(root)),'shot_index':idx,
              'match_id':(d.get('general') or {}).get('matchId'),
              'player_id':shot.get('playerId'),'team_id':shot.get('teamId'),
              'tags':tags,'raw_shot':shot})
    # Categorize the literal event types and check raw identity coverage.
    from collections import Counter
    types=Counter(str(r['raw_shot'].get('eventType')) for r in rows)
    missing={key:sum(r[key] is None for r in rows) for key in ('match_id','player_id','team_id')}
    duplicate_shots=len(rows)-len({(r['source_path'],r['shot_index']) for r in rows})
    return {'classification':'RAW_EXPLICIT_PENALTY_SHOT_CANDIDATES_NOT_VERIFIED_PENALTY_LEDGER',
      'matches_inspected':matches,'shots_inspected':shot_total,
      'candidate_count':len(rows),'event_type_counts':dict(types),
      'missing_raw_identities':missing,'duplicate_source_shots':duplicate_shots,
      'shootout_excluded':shootout_excluded,
      'ambiguous_excluded':ambiguous_excluded,'candidates':rows,
      'complete_attempt_history':False,'player_uuid_verified':False,
      'penalty_model_input_ready':False,'live_model_certified':False}
def main():
    p=argparse.ArgumentParser();p.add_argument('--raw',type=Path,default=CAP)
    p.add_argument('--out',type=Path,default=OUT)
    a=p.parse_args();r=candidates(a.raw)
    a.out.parent.mkdir(parents=True,exist_ok=True)
    a.out.write_text(json.dumps(r,indent=2,ensure_ascii=False,default=str)+'\n')
    print(json.dumps({k:r[k] for k in ('classification','matches_inspected','shots_inspected','candidate_count','shootout_excluded','ambiguous_excluded','event_type_counts','missing_raw_identities','penalty_model_input_ready')}))
if __name__=='__main__':main()

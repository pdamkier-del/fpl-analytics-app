"""Offline replay of archived witnesses only: no TS, enumeration or fitting.

Independently checks every archived chosen path/nomination, arithmetic, source/
implementation identities and the hand-derived D01 objective. Never runs TS.
"""
from pathlib import Path
import hashlib,json,sys
import numpy as np
from reference import transition,scalar_score,legal_nomination,COUNTS
from collections import Counter
S=Path(__file__).resolve().parents[1];ROOT=S.parents[1]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def verify(result_path):
 result=json.loads(result_path.read_text());manifest=json.loads((S/'inputs/implementation-manifest.json').read_text())
 for path,h in manifest['files'].items():assert sha(ROOT/path)==h,('Original implementation changed',path)
 assert result['protocol_sha256']==sha(ROOT/'research/experiments/EXP-TS-SEARCH-001.json')==manifest['protocol_sha256']
 assert result['input_sha256']==sha(S/'inputs/instances.json');assert result['implementation_sha256']==sha(S/'code/run_experiment.py')
 cases={c['id']:c for c in json.loads((S/'inputs/instances.json').read_text())['cases']};assert result['status']=='completed'and not result['not_run'];assert {r['id']for r in result['rows']}==set(cases)
 assert result['elapsed_seconds']<=result['budget_seconds']==120
 actions=0;scored=0
 for row in result['rows']:
  case=cases[row['id']];players={p['id']:p for p in case['players']};initial=tuple((p,players[p]['purchase'])for p in case['initial_ids'])
  assert row['status']=='completed'and row['certified_domain'];assert not(row['illegal_decisions']or row['scorer_disagreements']or row['menu_failures'])
  for kind in ['fixed_nomination_exact','joint_exact']:
   purchases=initial;bank=case['bank'];ft=case['free_transfers'];objective=0.
   for g,a in enumerate(row[kind]['path']):
    ids=tuple(a['ids']);positions=tuple(players[p]['position']for p in ids);nom=a['nomination'];assert legal_nomination(ids,positions,nom)
    assert Counter(positions)==COUNTS and max(Counter(players[p]['team']for p in ids).values())<=3
    move=transition(purchases,bank,ft,ids,players);assert move is not None;after,out,inc,hits,paid=move;assert len(inc)<=2
    assert list(out)==a['outgoing']and list(inc)==a['incoming'];assert bank==a['bank_before']and after[1]==a['bank_after'];assert ft==a['free_transfers_before']and after[2]==a['free_transfers_after'];assert hits==a['official_hit_points']and paid==a['uncertainty_penalty']
    if case['level']=='restricted_DNP':assert list(nom[0])in case['xi_menu']
    points=np.array([players[p]['points'][g]for p in ids]).T;minutes=np.array([players[p]['minutes'][g]for p in ids]).T;score=scalar_score(ids,positions,points,minutes,nom);assert abs(score-a['projected_manager_score'])<1e-9
    objective+=result['configuration']['weights'][g]*score-hits-paid;purchases,bank,ft=after;scored+=1
   assert abs(objective-row[kind]['objective'])<1e-9
  assert abs(row['fixed_nomination_search_gap']-(row['fixed_nomination_exact']['objective']-row['heuristic']['objective']))<1e-9
  assert abs(row['joint_gap']-(row['joint_exact']['objective']-row['heuristic']['objective']))<1e-9
  assert min(row['fixed_nomination_search_gap'],row['joint_gap'])>=-1e-9;actions+=len(row['heuristic']['path'])
 d01=next(r for r in result['rows']if r['id']=='D01');assert abs(d01['joint_exact']['objective']-247.40288)<1e-9;assert abs(d01['heuristic']['objective']-214.5024)<1e-9
 return dict(mode='Offline chosen-path replay and source/code/input identities; not a rerun of exact search or proof by replay alone',cases=len(cases),heuristic_path_actions=actions,exact_path_nominations_independently_replayed=scored,D01_hand_witness_matches=True,protocol_unchanged=True,implementation_unchanged=True)
if __name__=='__main__':print(json.dumps(verify(Path(sys.argv[1])),indent=2))

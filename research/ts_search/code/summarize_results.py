"""Render all archived case outcomes and a source-based pruning witness. No search."""
import csv,hashlib,json
from pathlib import Path
from collections import defaultdict
S=Path(__file__).resolve().parents[1];ROOT=S.parents[1];OUT=ROOT/'research/results/EXP-TS-SEARCH-001'
def summarize():
 r=json.loads((OUT/'initial-run/results.json').read_text());inputs=json.loads((S/'inputs/instances.json').read_text());cases={c['id']:c for c in inputs['cases']};groups=defaultdict(list)
 for row in r['rows']:groups[row['family']].append(row)
 summary=dict(experiment_id=r['experiment_id'],status=r['status'],initial_wall_seconds=r['elapsed_seconds'],budget_seconds=r['budget_seconds'],completed=len(r['rows']),not_run=r['not_run'],deterministic_cases=30,restricted_DNP_cases=12,heuristic_path_actions=sum(len(v['heuristic']['path'])for v in r['rows']),illegal_decisions=sum(len(v['illegal_decisions'])for v in r['rows']),scorer_disagreements=sum(len(v['scorer_disagreements'])for v in r['rows']),menu_failures=sum(len(v['menu_failures'])for v in r['rows']),score_audits=sum(v['score_audits']for v in r['rows']),positive_fixed_nomination_gaps=sum(v['fixed_nomination_search_gap']>1e-9 for v in r['rows']),positive_joint_gaps=sum(v['joint_gap']>1e-9 for v in r['rows']),maximum_joint_gap=max(v['joint_gap']for v in r['rows']),max_reachable_states_per_layer=max(max(v['joint_exact']['state_counts'])for v in r['rows']),numerical_comparison_tolerance=1e-9,families={k:dict(cases=len(v),positive_gaps=sum(x['joint_gap']>1e-9 for x in v),gap_min=min(x['joint_gap']for x in v),gap_max=max(x['joint_gap']for x in v))for k,v in groups.items()},scope='Constructed finite six-GW domains under frozen B-worker scorer. No representative failure rate, realized points, full FPL optimum or model promotion. Restricted DNP menu only; no stochastic transfer-search test.')
 with(OUT/'case-results.csv').open('w')as h:
  names=['id','level','family','heuristic_objective','fixed_nomination_exact','joint_exact','transfer_search_gap','joint_gap','nomination_gain_on_heuristic_path','illegal','scorer_disagreements','case_seconds'];w=csv.DictWriter(h,fieldnames=names,lineterminator='\n');w.writeheader()
  for x in r['rows']:w.writerow(dict(id=x['id'],level=x['level'],family=x['family'],heuristic_objective=x['heuristic']['objective'],fixed_nomination_exact=x['fixed_nomination_exact']['objective'],joint_exact=x['joint_exact']['objective'],transfer_search_gap=x['fixed_nomination_search_gap'],joint_gap=x['joint_gap'],nomination_gain_on_heuristic_path=x['nomination_gain_on_heuristic_path'],illegal=len(x['illegal_decisions']),scorer_disagreements=len(x['scorer_disagreements']),case_seconds=x['elapsed_seconds']))
 # Compute why the returned optimal opening bundle is absent from positive-leg search.
 witness=[]
 for row in r['rows']:
  if row['joint_gap']<=1e-9:continue
  c=cases[row['id']];p={v['id']:v for v in c['players']};a=row['joint_exact']['path'][0];pairs=[]
  for out in a['outgoing']:
   incoming=next(i for i in a['incoming']if p[i]['position']==p[out]['position']);before=sum(w*sum(p[out]['points'][g])/len(p[out]['points'][g])for g,w in enumerate(r['configuration']['weights']));after=sum(w*sum(p[incoming]['points'][g])/len(p[incoming]['points'][g])for g,w in enumerate(r['configuration']['weights']));pairs.append(dict(outgoing=out,incoming=incoming,weighted_individual_gain=after-before,current_out_price=p[out]['price'],purchase=p[out]['purchase'],incoming_price=p[incoming]['price']))
  witness.append(dict(id=row['id'],opening_bundle_pairs=pairs,necessary_negative_leg=any(x['weighted_individual_gain']<-1e-12 for x in pairs),interpretation='Matches the already documented _fast_local_candidate_squads gain<=-1e-12 exclusion. Mechanism not a new discovery; six-GW gap is newly measured. No proposer-ablation or alternative policy run.'))
 assert len(witness)==11 and all(x['necessary_negative_leg']for x in witness)
 (OUT/'pruning-witnesses.json').write_text(json.dumps(witness,indent=2)+'\n');(OUT/'summary.json').write_text(json.dumps(summary,indent=2)+'\n');return summary
if __name__=='__main__':print(json.dumps(summarize(),indent=2))

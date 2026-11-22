"""Render historical matrices from curated families and immutable public evidence.
This is bookkeeping; classification is evidence-limited and awaits PR review.
"""
import csv,gzip,json,re
from pathlib import Path
S=Path(__file__).resolve().parents[1];ROOT=S.parents[1]
def load(p):return json.loads(p.read_text())
def render():
 families=load(S/'family-definitions.json');bundle=json.loads(gzip.decompress((S/'primary-evidence.json.gz').read_bytes()));index=json.loads(gzip.decompress((S/'tree-index.json.gz').read_bytes()));receipts=load(S/'source-receipts.json');directory={d:f['id'] for f in families for d in f['directories']};matrix=[];variants=[]
 extras={'LEGACY-023':['minute-model-research.md'],'LEGACY-024':['individual-mm-refinement-complete.md'],'LEGACY-040':['systematic-precision-audit.md','decisions.py','historical-TS-cases.json','parameter-provenance.json'],'LEGACY-041':['controls/manifest.json'],'LEGACY-042':['assist-decision.json','high-precision-summary.json'],'LEGACY-043':['secondary-components-validation.md','repair-validation.json'],'LEGACY-044':['transfer-engine-audit-20261031/README.md'],'LEGACY-045':['ts-v4-joint-planner-built.md','test_transfer_planner_joint.py','ts-v3-targeted-diagnostic-setup.md'],'LEGACY-039':['PR21-body.md','PR22-body.md'],'LEGACY-038':['PR20-body.md'],'LEGACY-051':['team_xg_dynamics_experiment.py','team_xg_opponent_adjusted.py','team-xg-run-receipt.json']}
 def leaves(x,p=''):
  if isinstance(x,dict):
   for k,v in x.items():yield from leaves(v,(p+'.'if p else'')+k)
  elif isinstance(x,list):
   for i,v in enumerate(x):yield from leaves(v,f'{p}[{i}]')
  else:yield p,x
 for f in families:
  sources=[];design=[];metrics=[]
  for i,r in enumerate(bundle):
   parts=r['path'].split('/')
   if len(parts)<4 or parts[2] not in f['directories']:continue
   sources.append({k:v for k,v in r.items() if k!='text'}|{'archive':'research/stage0/primary-evidence.json.gz','array_index':i})
   if r['path'].endswith('.json'):
    for key,v in leaves(json.loads(r['text'])):
     if re.search(r'train|develop|test|cutoff|selection|baseline|classification|limitation|scope|population|fixtures|rows|sample|draws|cohort|season|clock',key,re.I):design.append(dict(source_index=i,field=key,value=v))
     if re.search(r'mae|rmse|brier|log.loss|crps|bias|delta|interval|ci95|bounds|mismatch|accepted|promot|fail|decision|selected|gain|regret',key,re.I) and not re.search('coef|feature|model.mean|model.scale',key,re.I):metrics.append(dict(source_index=i,field=key,value=v))
  additional=[r for r in receipts if any(r['path'].endswith(s) for s in extras.get(f['id'],[]))]
  # PR bodies are dated secondary claims; their status is not evidence a queued run completed.
  for suffix in extras.get(f['id'],[]):
   p=S/'evidence'/suffix
   if p.exists():additional.append(dict(local_path=str(p.relative_to(ROOT)),class_='public PR prose; reported only'))
  links=f.get('existing_result_links',[])
  if f['id']=='LEGACY-052':links=['analysis/audits/2026-11-22/results/evaluation.json','analysis/audits/2026-11-22/results/official-ep-next-benchmark.json']
  if f['id']=='LEGACY-053':links=['analysis/followup-41-20261122/results/pm-decomposition.json','analysis/followup-41-20261122/results/bps-identification.json']
  card=dict(**f,configuration={'description':'Original source-specific configuration; no new parameters','sources':sources,'additional_sources':additional,'existing_sources':links},train_development_test={'summary':f['validation'],'original_design_facts':design,'missing_information':'Any field absent from cited source is NOT_AVAILABLE; no inference of publication clocks, training independence or actual event times.'},population={'summary':'See original rows/fixtures/cohort facts, never sum overlapping arms as independent sample size','source_facts':'train_development_test.original_design_facts'},metrics_effect_uncertainty={'summary':f['finding'],'original_result_facts':metrics,'uncertainty_scope':'Intervals retain original clustering/selection limits. Missing original intervals are NOT_AVAILABLE; no fresh CI or efficacy test executed.'},outcomes_seen=True,verification_scope='Original bytes/provenance and selected arithmetic; full scientific replication not performed',promotion='None; preserve original decisions in exact configurations; independent review pending')
  matrix.append(card)
 for d,id in sorted(directory.items()):
  paths=[r for r in index if r['path'].startswith('analysis/results/'+d+'/')];variants.append(dict(directory=d,family=id,paths=len({r['path'] for r in paths}),path_blob_versions=len(paths),primary_artifacts=sum(1 for r in bundle if r['path'].startswith('analysis/results/'+d+'/')),classification=next(f['classification'] for f in families if f['id']==id),evidence_gap='Primary summaries indexed' if any(r['path'].startswith('analysis/results/'+d+'/') for r in bundle) else 'No standard summary indexed; see full pinned tree, family evidence and source-directory files; no independent efficacy inferred'))
 (S/'historical-matrix.json.gz').write_bytes(gzip.compress(json.dumps(matrix,ensure_ascii=False,separators=(',',':')).encode(),mtime=0))
 with(S/'directory-matrix.csv').open('w')as h:
  w=csv.DictWriter(h,fieldnames=list(variants[0]),lineterminator='\n');w.writeheader();w.writerows(variants)
 text=['# Deduplicated historical research matrix','', 'Dated 22 November 2026. **54 coverage families are not 54 independent experiments.** Directory/substudy membership is exhaustive for the pinned public result trees in `directory-matrix.csv`; arm-specific source facts, baseline, configuration, periods, population, metrics, decisions and missingness are in `historical-matrix.json.gz`. All original protocols/results remain intact in `primary-evidence.json.gz` and the cited Git objects. Source-only or queued work is not called completed.','', 'Classification is narrow: accepted = original scoped research/checkpoint decision, rejected = that exact tested configuration, exploratory = reused/diagnostic, inconclusive = incomplete/unrecovered evidence, blocked = missing prerequisites, untested = not a generalizable science result. An accepted gate never implies independent predictive validation or deployment. Existing registry states are preserved.','', '| ID | Model / question | Classification | Verified boundary / original finding |','| --- | --- | --- | --- |']
 for f in families:text.append('| '+f['id']+' | '+f['model']+': '+f['question']+' | '+f['classification']+' | '+f['finding'].replace('|','/')+' |')
 text+=['','## Copies, variants and unknowns','', 'Identical `(path, Git blob)` versions are collapsed across branches; different blobs at one path remain separate versions. Different arms/seeds/parameter values and calibrated follow-ups remain attached to their original family and directory. A changed file or repeated season is not a fresh hypothesis or untouched holdout. The 225 primary result/protocol artifacts keep every original field, including negative decisions. The 184 directory rows do not count private-manager payloads as performance trials.','', 'The original PR41 inventory has **178 directory groups / 2,471 files**; the expanded branch union has **184 result directories** plus flat result files. `verification.json` checks all 2,471 content hashes and all 236 original test-source paths. Tests are indexed, not re-executed model certification. The public tree index covers 58 branch names at 48 unique commit heads, 3,169 distinct path/blob versions; private-manager branch names and payloads are excluded.','', 'Cases without a machine-readable standard summary are explicitly marked in `directory-matrix.csv`. Detailed missing fields remain NOT_AVAILABLE rather than guessed. The team-xG Actions job succeeded, but its result/log bodies could not be downloaded (Forbidden); numerical claims remain unverified. See LEGACY-051 and its run/digest receipt.','','Independent scientific review of grouping and novelty is **pending**; deterministic checks do not replace it.']
 (S/'HISTORICAL_MATRIX.md').write_text('\n'.join(text)+'\n')
 print(json.dumps({'families':len(matrix),'directories':len(variants),'matrix_bytes':(S/'historical-matrix.json.gz').stat().st_size}))
if __name__=='__main__':render()

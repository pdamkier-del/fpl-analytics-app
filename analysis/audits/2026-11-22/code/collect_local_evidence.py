"""Collect pre-existing public research evidence. Does not execute models or read manager files."""
from pathlib import Path
import json,gzip,hashlib,shutil,subprocess,argparse
p=argparse.ArgumentParser();p.add_argument('--research-root',type=Path,required=True);p.add_argument('--archive-root',type=Path,required=True);p.add_argument('--work-root',type=Path,required=True);a=p.parse_args();R=Path(__file__).resolve().parents[1];manifest=[]
def copy(src,dst,compress=False):
 raw=src.read_bytes();out=R/dst;out.parent.mkdir(parents=True,exist_ok=True)
 if compress:out.write_bytes(gzip.compress(raw,mtime=0))
 else:out.write_bytes(raw)
 manifest.append({'path':str(out.relative_to(R)),'source_sha256':hashlib.sha256(raw).hexdigest(),'stored_sha256':hashlib.sha256(out.read_bytes()).hexdigest(),'uncompressed_bytes':len(raw)})
inv=[]
for d in sorted(a.research_root.iterdir()):
 if not d.is_dir():continue
 files=[]
 for f in sorted(d.rglob('*')):
  if f.is_file():files.append({'path':str(f.relative_to(a.research_root)),'bytes':f.stat().st_size,'sha256':hashlib.sha256(f.read_bytes()).hexdigest()})
 inv.append({'experiment':d.name,'files':files})
(R/'research-inventory.json').write_text(json.dumps(inv,indent=2))
selected={
'mm-final-20261006-v1':['result.json'],
'vfinal-integrated-20261005-v1':['result.json','protocol.json'],
'full-model-audit-20261012':['historical_ts_reproduction_report.json','regular_starter_calibration_report.json','sampler_subgroup_report.json'],
'transfer-strategy-v3-replay-20261005-v2':['summary.json','verification.json','comparison.csv'],
'attack-budget-ablation-20261031':['decision.json','protocol.json','bootstrap.json','high-forecast-bootstrap.json','metrics.csv','README.md'],
'hierarchical-goal-assist-allocation-20261005-v1':['joint_metrics.json','protocol.json'],
'europe-rotation-20261022':['decision.json','protocol.json'],
'role-injury-mm-20261016':['summary.json','reproduction.json'],
'gk-shot-quality-efficiency-20261005-v1':['keeper_metrics.json','protocol.json','selection.json'],
'current-season-b-backtest-20261027':['README.md','score-proof.json','release.json'],
'code-wiring-audit-20261031':['README.md'],
}
for d,names in selected.items():
 for n in names:
  src=a.research_root/d/n
  if src.exists():copy(src,'evidence/'+d+'/'+n)
for gw in (8,9,10):
 for kind in ('forecast','mm','existing-app-data','live','index'):
  src=a.archive_root/f'gw{gw}-{kind}.json';copy(src,'inputs/archive/'+src.name+'.gz',True)
for n in ('report.json','bootstrap.json','fixtures.json','results.json','raw-keeper-results.json'):
 copy(a.archive_root/n,'inputs/archive/'+n+'.gz',True)
for d,names in {
'fpl-recent-evaluation':['benchmarks.json','benchmark-protocol.json','benchmark-uncertainty.json'],
'fpl-p90-integration':['conclusion.json','feasibility.json'],
'fpl-dynamic-model/extended':['residual-results.json'],
'fpl-keeper-quality/analysis/results/keeper-quality-rates-20261115':['results.json','CONCLUSION.md'],
'fpl-joint-substitution/review/analysis/results/joint-substitution-research-20261108':['results.json','conclusion.json','checks.json','prospective-plan.json','team-count-results.json'],
}.items():
 for n in names:copy(a.work_root/d/n,'evidence/'+d.split('/')[0]+'/'+n)
(R/'evidence-manifest.json').write_text(json.dumps(manifest,indent=2));print(json.dumps({'experiment_directories':len(inv),'indexed_files':sum(len(i['files'])for i in inv),'copied_files':len(manifest),'stored_bytes':sum((R/m['path']).stat().st_size for m in manifest)}))

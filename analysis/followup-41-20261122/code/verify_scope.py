"""Review guard: evidence-only diff and no accidentally tracked private ledger artifacts."""
from pathlib import Path
import subprocess,json,hashlib
BASE='d28bfe3c1b596e1806009e830b2a603e09677b02';root=Path(__file__).resolve().parents[3]
paths=subprocess.check_output(['git','-C',str(root),'diff','--name-only',BASE],text=True).splitlines()
allowed=['analysis/audits/2026-11-22/code/','analysis/audits/2026-11-22/tests/','analysis/audits/2026-11-22/result-integrity.json','analysis/audits/2026-11-22/results/evaluation.json','analysis/followup-41-20261122/']
assert all(any(p.startswith(a)for a in allowed)for p in paths),paths
tracked=subprocess.check_output(['git','-C',str(root),'ls-files'],text=True).splitlines()
assert not any(Path(p).name=='ledger.jsonl'or Path(p).name.startswith('record-')for p in tracked)
R=Path(__file__).resolve().parents[1]
for e in json.loads((R/'result-integrity.json').read_text()):assert hashlib.sha256((R/e['path']).read_bytes()).hexdigest()==e['sha256']
print(json.dumps({'changed_paths':len(paths),'audit_only':True,'private_ledger_artifacts_tracked':False,'followup_result_hashes_verified':True}))

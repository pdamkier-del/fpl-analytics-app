"""Compose existing frozen NP coefficients with the separately tested B repairs.

Never changes the old selected policy, fitted model, decision, or benchmark.
"""
from pathlib import Path
import hashlib,json
ROOT=Path(__file__).resolve().parents[1]
def build():
    original=ROOT/'analysis/results/nonpenalty-goal-head-20261023/policy.json';policy=json.loads(original.read_text());policy['scope']='B integrated source/event repair; original NP coefficients and selection retained; not production activation'
    policy['composition_baseline_sha256']=hashlib.sha256(original.read_bytes()).hexdigest()
    added=['scripts/b_horizon_eligibility.py','scripts/b_physical_workload.py','scripts/b_medical_return.py','src/fpl_v1_1_model/b_event_simulator.py','scripts/mm_candidate_forecast.py']
    for name in set(policy['sha256'])|set(added):policy['sha256'][name]=hashlib.sha256((ROOT/name).read_bytes()).hexdigest()
    # The selected head and its original evidence MUST remain byte-identical.
    frozen=json.loads(original.read_text())
    for name in [frozen['model'],frozen['decision'],frozen['protocol'],'src/fpl_v1_1_model/experimental_nonpenalty_allocation.py','src/fpl_v1_1_model/experimental_penalty_neutral.py','src/fpl_v1_1_model/joint_simulator.py']:
        if policy['sha256'][name]!=frozen['sha256'][name]:raise ValueError('Frozen NP/production benchmark changed: '+name)
    out=ROOT/'analysis/results/integrated-repair-20261031/nonpenalty-policy.json';out.parent.mkdir(parents=True,exist_ok=True);out.write_text(json.dumps(policy,indent=2)+'\n')
    return out
if __name__=='__main__':print(build())

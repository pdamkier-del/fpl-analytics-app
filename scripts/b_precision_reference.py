"""Reuse only the immutable upstream-head benchmark, never new B calibration."""
import hashlib,subprocess
from pathlib import Path
BASELINE='161b67b6fb8786a38e78c245b92a03ad841575d8'
HEADS=['src','model','scripts/gk_joint_bridge.py','scripts/gk_solo_role.py','scripts/mm_candidate_forecast.py','scripts/mm_locked_bridge.py','scripts/b_chain_contract.py','scripts/b_preview_ts.py','scripts/run_live_locked_ts.py','scripts/build_current_b_inputs.py','scripts/b_physical_workload.py','scripts/b_medical_return.py','scripts/b_horizon_eligibility.py','scripts/run_vfinal_integrated.py','scripts/nonpenalty_goal_bridge.py','scripts/joint_role_bridge.py','analysis/results/integrated-repair-20261031','analysis/results/nonpenalty-goal-head-20261023/final-v2']
def require_reference(root,reference):
    root=Path(root)
    if reference!=BASELINE:raise ValueError('Unapproved B precision reference')
    subprocess.run(['git','diff','--exit-code',BASELINE,'--',*HEADS],cwd=root,check=True)
    subprocess.run(['python','scripts/check_snapshot_adapter.py'],cwd=root,check=True)
    return dict(reference_source=BASELINE,scope='Unchanged original upstream heads and historical baseline only; new precision/calibration requires separate gates',upstream_head_paths=HEADS,precision_recorder_default_reference_tests='tests/test_preview_distributions.py and tests/test_b_simulation_precision.py',new_B_forecast_reused=False)

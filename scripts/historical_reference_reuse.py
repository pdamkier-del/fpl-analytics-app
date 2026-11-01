"""Bounded reuse of original-head validation after reviewed exact refactors.

This does not validate the new normal-match forecast. That computation, its
physical constraints, source linkage, scope replay and TS checks still run.
"""
import hashlib,json,subprocess,sys
from pathlib import Path


def require_compatible(root,reference,current,*,manifest=None):
    root=Path(root)
    manifest=manifest or json.loads((root/'analysis/results/normal-match-correctness-20261025/historical-reference-reuse.json').read_text())
    if reference!=manifest['reference_source']:
        raise ValueError('Historical reference source is not approved for reuse')
    pins=manifest['reviewed_file_sha256']
    added=manifest['reviewed_additions_sha256']
    for name,digest in {**pins,**added}.items():
        path=(root/name).resolve()
        if not path.is_relative_to(root.resolve()) or hashlib.sha256(path.read_bytes()).hexdigest()!=digest:
            raise ValueError('Historical reference dependency changed: '+name)
    changed=subprocess.check_output(['git','diff','--name-status',reference,current,'--','src','model','scripts','analysis','data','data_v1_1','service'],cwd=root,text=True).splitlines()
    # Original datasets, coefficients and all unreviewed existing source files
    # must remain byte identical. New isolated research files are not inputs to
    # the fixed historical jobs; their original importers are pinned above.
    for row in changed:
        status,name=row.split('\t',1)
        if name.startswith(('model/','data/','data_v1_1/','service/')):
            raise ValueError('Original fitted model/data dependency changed: '+name)
        if status=='A':
            if name=='analysis/results/normal-match-correctness-20261025/historical-reference-reuse.json' or name in added:continue
            raise ValueError('Unreviewed historical reference addition: '+name)
        if status!='M' or name not in pins:
            raise ValueError('Unreviewed historical reference change: '+row)
    proofs=manifest['exact_refactor_receipts']
    for name,requirements in proofs.items():
        proof=json.loads((root/name).read_text())
        if any(proof.get(k)!=v for k,v in requirements.items()):
            raise ValueError('Missing exact historical refactor proof: '+name)
    # The cleanup replay starts at f4e0944. Its numerical entry paths must be
    # exactly the same as the successful original-head reference being reused.
    subprocess.run(['git','diff','--exit-code',reference,'f4e0944','--',
        'src/fpl_v1_1_model/joint_simulator.py','scripts/run_joint_gk_preview.py',
        'scripts/b_chain_contract.py','scripts/pm_preview_distributions.py',
        'scripts/run_vfinal_integrated.py'],cwd=root,check=True)
    # Execute the retained original PM, rather than trusting a source-text
    # exception or a changed model's statistical score.
    subprocess.run([sys.executable,str(root/'scripts/check_locked_gk_default.py')],cwd=root,check=True)
    return dict(reference_source=reference,current_source=current,
        scope='Original unchanged upstream heads only; new normal-match forecast not reused',
        reviewed_dependency_sha256=pins,exact_refactor_receipts=list(proofs),
        reviewed_additions_sha256=added,
        original_PM_event_rng_aggregate_replay_passed=True,
        reference_matches_exact_refactor_baseline=True,
        fresh_current_forecast_required=True,new_normal_constraints_required=True)

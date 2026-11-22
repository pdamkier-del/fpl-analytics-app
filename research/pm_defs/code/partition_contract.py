"""Metadata gate for future residual replacement, never a model correction.

Conservation of one observed BPS target is a partition identity. Transporting
2025BPS into2026BPS is a different target and cannot be certified by that identity.
"""
from contracts import ContractError,Unidentified,retarget_background

def replace_same_target_residual(*,old_known,old_residual,explicit_value,term,
                                explicit_before,residual_excludes_before,
                                old_rulebook,new_rulebook,unit):
 if unit!='bps_units':raise ContractError('Residual replacement requires BPSunits')
 if not old_rulebook or old_rulebook!=new_rulebook:raise Unidentified('Across-rule-year target transport requires independently identified new target; partition conservation is insufficient')
 if not term or term in explicit_before or term in residual_excludes_before:raise ContractError('Explicit term already accounted for or excluded; duplicate replacement')
 known,residual=retarget_background(old_known,old_residual,explicit_value,residual_excludes_new=False)
 return dict(known=known,residual=residual,rulebook=new_rulebook,explicit_after=sorted(set(explicit_before)|{term}),residual_excludes_after=sorted(set(residual_excludes_before)|{term}))

# Deadline snapshots recovered; component timing blocks decision replay

Continues `33f99cf4205e4853f9e8a31af91651310d95476b`. The existing original
adapter/simulator and unchanged-control/v4 paired diagnostic remain runnable.
No old source, frozen forecast, target, metric, transfer or chip strategy changed.

## What is now recovered

All 17 predeadline FPL bootstrap snapshots for reused diagnostic GW22–38 are
preserved with original Git blob SHA, source commit/publication time, original
XZ bytes and checksums. All official event deadlines match the frozen v4
cutoffs. All 13,956 snapshot states map uniquely by season element ID and stable
FPL code; 13,955 of the 13,987 control rows match snapshot team/position.

15 of the 46 first-entry rows now have confirmed predeadline FPL evidence.
31 are not observed in the selected snapshots; a further roster row outside
the missing-component inventory is also unverified. Snapshot age can be 5.2542
hours. Absence is not proof of ineligibility, and FPL listing is not a complete
physical football roster. None of these rows was removed or assigned zero.
The 46 component forecasts themselves remain absent: source recovery and
forecast generation are distinct steps.

## New timing finding

The original Phase 3C/3D/3E experiments freeze contexts before each target
fixture and update their historical states in kickoff/fixture-ID order.
They do not batch all forecasts at one common GW deadline. The structural
audit finds earlier-in-order fixtures with kickoff after the frozen cutoff in
153 of 170 fixture contexts. 409 player rows across five fixtures also have
player-specific history from after that cutoff, relevant for DGWs.

Attack position/assist priors and discipline population priors are directly
fixture-sequential. DC population/opponent and team-goal contexts have similar
ordering. Simultaneous fixtures earlier in UUID order can also expose results.
These counts show structural exposure, not a numerical impact estimate or an
exact reconstruction of archived forecast values. They conservatively exclude
additional possible problems from unfinished predeadline games.

The prior paired comparison remains useful as a reused mechanistic sensitivity
diagnostic. It cannot certify a deadline-safe decision replay. Do not silently
patch its archived inputs or reinterpret GW22–38 as a new holdout.

## Validation and next step

107 tests pass. The expanded joint checker passes 14,905 checks, including the
14,780 snapshot checks; original policy hashes still match. The timing audit
was reproduced byte-for-byte from its tracked original experiment sources,
without requiring the external recovery ZIPs.

Next: build a separately versioned common component input at each deadline
from declared frozen parameters and completed predeadline observations. Give
first-entry rows an explicit tested position-prior contract. Resolve the
remaining 31 first-entry roster/position evidence cases plus the additional
roster row before declaring a full common roster ready. Preserve the original
control checkpoint; run a new paired comparison on the new common input with
only minutes differing between arms. Transfer/chip strategy stays fixed.

The unresolved roster evidence is a concrete data gap. Full-roster/full-season
replay has not passed preflight and has not started. The separate season-rule
audit must also be resolved before full season replay. Competition-state and
fresh validation requirements remain separate promotion work.

Reproduce checks/audit:

```bash
PYTHONPATH=src python scripts/check_joint_checkpoint.py
PYTHONPATH=src python scripts/audit_joint_component_timing.py --out work/timing-audit-reproduced
PYTHONPATH=src python -m pytest -q tests
```

Exact inventory/results: `analysis/results/joint-deadline-roster-audit-v1/`
and `analysis/results/joint-component-timing-audit-v1/`. Latest machine status:
the latter folder's `readiness.json`.

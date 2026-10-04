# Original deadline snapshots recovered; evidence gap narrowed

Continues `7ac64e366d0790449ec12849f4a9e524b7351789`.
Recovered all 17 selected predeadline bootstrap streams for diagnostic GW22–38.
The exact original XZ bytes, Git blob SHA, raw/decompressed SHA256 and historical
source commit/publication timestamp are preserved in lossless parts. Official
event deadlines match the existing frozen v4 cutoffs in every snapshot.
Snapshot ages range from minutes to 5.2542 hours. All 13,956 element rows map
uniquely to stable Core identities, with season-specific element/code checks.

The new audit compares the control's 13,987 player-fixture rows with these
snapshots. 13,955 have matching team and position; 32 are not observed in the
selected predeadline snapshot. There are no team/position disagreements.
Of the original 46 missing-component rows, 15 have matching predeadline FPL
evidence and 31 are not observed. One additional unverified roster row lies
outside the missing-component inventory.

Do not equate snapshot absence with confirmed ineligibility: players may be
added between snapshots. Do not equate FPL listing with a complete physical
football roster. Removing these players from simulator event allocation or
assigning missing components zero would silently change the control contract.
Their status remains unknown; the original diagnostic and Core are untouched.

The 15 verified entrants can now be considered for an explicit first-entry
component path from frozen position priors, without fitting to target outcomes.
Before doing so, audit the archived predictors' kickoff-vs-deadline timing:
their sequential fixture updates may have consumed games after a GW deadline.
Full-roster replay remains blocked; this checkpoint recovers source evidence,
not new forecasts or new validation results. Transfer/chip policy is unchanged.

Reproduce source/roster checks:

```bash
PYTHONPATH=src python scripts/check_joint_deadline_snapshots.py
PYTHONPATH=src python scripts/audit_joint_deadline_roster.py --out work/deadline-roster-audit-reproduced
```

The authoritative next step is component-timing audit, then a separately
versioned deadline-safe first-entry contract. Resolve the 31 first entrants
and additional roster row before declaring complete-roster replay ready.

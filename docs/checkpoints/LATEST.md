# Latest continuation checkpoint

Read [verified paired deadline-input diagnostic](2026-10-04-deadline-joint-paired.md).
Continues d450116d2779e533ab2c6d84431d86e23b8d3f38; all older evidence is preserved.

117 tests and 12,896 common-input checks pass. A controlled paired run is
complete on 144 whole fixtures / 11,794 rows with the original adapter and
simulator. Transfer/chip policy hashes are unchanged. Control and v4 differ
only in their original minute fields within this new common-input experiment.
Bonus-neutral MAE is 0.857057 control versus 0.831744 v4; this is reused
GW22–38 diagnostic sensitivity, never a new holdout or independent validation.

Technical readiness is true for the bounded complete-fixture paired cohort.
Full-period/full-season readiness is false: 32 roster rows across 26 fixtures
still lack verified predeadline team/position evidence. Next resume at that
concrete source gap; do not rerun reconstruction or tune on GW22–38. History
availability uses an explicit kickoff+3h guard rather than verified publication
timestamps. Apply the existing season scoring/chip audit before full-season
replay; retain original transfer/chip policy during any controlled comparison.

# Frozen paired inputs and explicit cohort gap

Continues the original dependency checkpoint `705fb19a66577c75ff2f3d6f2dd43ffdb85d4f84`.
The paired-input manifest records original archive/member checksums and source
identities, unchanged V2/v4 input hashes and deterministic packed CSV hashes.
The same complete fixture roster, event inputs, team goals and original scoring
are used in both arms. Evaluation targets are a separate packed table.

All 13,987 V2 and v4 roster rows align. Original goal, assist and discipline
files lack **46** rows; DC additionally lacks the same 40 non-GK rows. These
are mostly newly entering players. GK DC is zero by the scoring rule, not a
filled missing forecast. The missing observations affect **33 of 170** fixtures.
Whole affected fixtures are excluded from both arms: **137 fixtures / 11,226
player-fixture rows** remain, with no missing-component zero fill and no
control/candidate-specific filtering. The inherited control's 0.05-minute
filter excludes zero additional rows in this complete cohort.

This gap prevents the full-roster diagnostic and controlled whole-period replay.
The limited complete-fixture diagnostic is executable. It is not an independent
holdout; no GW22–38 model selection, fitting or policy tuning occurs.

The original Phase4B adapter builds the unchanged V2 control. v4 is created
from its simulator inputs by replacing only the selected minutes fields.
On-pitch goal/assist/DC rates stay fixed, avoiding a changed xMins denominator
silently changing the event model. Original simulator and transfer/chip modules
are untouched. Same deterministic seed and 80-simulation inherited budget in
each fixture/arm; random branching is not event-aligned CRN sampling.

Reproduce from published packed inputs:

```sh
PYTHONPATH=src python -m pytest -q tests
python scripts/run_paired_joint_diagnostic.py --out work/paired-reproduction
python scripts/check_joint_checkpoint.py
```

Do not overwrite frozen folders. Original packages can reconstruct a new input
folder via `freeze_joint_diagnostic_inputs.py --archive-directory PATH --out NEW`.
Recover or generate the missing frozen components with declared cutoff-safe
inputs before extending the cohort; no invented first-appearance zeros.

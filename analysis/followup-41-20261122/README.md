# Opfølgning på PR #41

Start med [den korte beslutningsrapport](DECISION_REPORT.md). Se også [privat TS-logning](PRIVATE_TS_LOGGING.md) og [protokollen for ekstern xP](EXTERNAL_XP_PROTOCOL.md).

Denne branch bygger på PR #41 og gentager ikke dens modelaudit. Den retter audit-serialisering, tilføjer nye PM-dekomponeringer, leverer en selvstændig privat TS-logger og fastlægger adgangs-/evalueringskrav til eksterne modeller. Ingen model eller app publiceres.

## Genberegning

Brug PR #41's `analysis/audits/2026-11-22/requirements-audit.txt`. Fra repositoryroden:

```sh
OPENBLAS_NUM_THREADS=1 python analysis/audits/2026-11-22/code/run_audit.py
OPENBLAS_NUM_THREADS=1 python analysis/followup-41-20261122/code/pm_decomposition.py
OPENBLAS_NUM_THREADS=1 python analysis/followup-41-20261122/code/bps_rule_transport.py
OPENBLAS_NUM_THREADS=1 python -m pytest -q analysis/audits/2026-11-22/tests analysis/followup-41-20261122/tests
```

Ingen kommando her kører en model-/TS-søgning eller publicerer noget. PM-resultaterne bruger PR #41's frosne arkiver. Reproducerbarhedskvitteringen dokumenterer den oprindelige hashseed-fejl og det numerisk uændrede resultat efter rettelsen. Data fra en faktisk privat TS-capture ligger uden for repoet og følger aldrig med disse resultater.

De to substitutionskvitteringer er read-only observationer pr. 22. november. De ændrer ikke forsøget. Rigtige fremtidige managerbeslutninger kan ikke genskabes ud fra tests, tidligere resultater eller en ny forecastberegning.

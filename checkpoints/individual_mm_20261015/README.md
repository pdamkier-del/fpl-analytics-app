# Individual MM research evidence

Public numerical evidence for PR #4, **not production weights, an independent
holdout, or certification of a six-GW transfer-strategy replay**.

Restore and verify every part, archive and member checksum:

```bash
PYTHONPATH=src:scripts python scripts/individual_mm_evidence.py restore --out work/individual-mm-evidence
```

The capsule contains the full chronological MM metrics and group reports,
development selection, lineup/source audit, both completed six-arm PM reports,
PM group/component diagnostics, frozen-origin horizon results, failed legacy
six-GW input contract, source manifest and validation receipt. All scored MM,
PM and horizon player rows are included as compressed, factorized NumPy arrays.

Read a prediction table without pickle:

```python
from scripts.individual_mm_evidence import load_frame
frame = load_frame('work/individual-mm-evidence/2025-26_pm_predictions.npz')
```

Numeric arrays preserve parsed CSV values exactly. Factorization reduces
repeated identifiers without dropping zero-minute players. PM arrays include
all ten point components; MM arrays include original, previous start/survival,
control and role arms. Reports retain all calibration bins and bootstrap
intervals. Original 2024 PM predictions include GW6–38 captures; its reported
chronological evaluation is GW22–38. Selection is not repeated on evaluation.

The companion audit at `docs/audits/2026-10-15-individual-mm-validation.md`
explains reproduction from archived source inputs and all temporal limitations.
`manifest.json` records exact byte counts and SHA-256 hashes. Source archive
identifiers and hashes are recorded inside `source_manifest.json`.

Decision: keep the original MM; `locked_model_active=false`; preserve the
2,125-point legacy benchmark. These research files contain no manager state.

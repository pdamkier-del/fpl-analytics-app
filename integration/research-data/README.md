# C2 — permanent original forecast and private decision capture

Integration based on PR46 `876e61b0`, informed by PR50. MM B, PM vFinal,
TS v3 and the substitution experiment are unchanged. No research results from
PR47–50 are edited. This is storage/orchestration, not another producer or app.

## Reused and new code

| Existing system | Integration |
| --- | --- |
| Pinned B producer `161b67b6`, existing hourly publication workflow and source artifacts | New sibling archive job consumes exactly those outputs. It does not depend on UI/publication success. |
| PR46 `freeze_forecast.py` | Reused for original byte identity and frozen reference metadata; archive adds MM, source receipts, full config and permanent persistence. |
| PR42 `private_ts_ledger.py` | Reused append-only private ledger and original validators; accept original worker bench aliases without rewriting output, preserve canonical original input/output and snapshot selling prices, add runtime provenance and filesystem protections. |
| PR43 `evaluation_ops.ts_capture/private_routes` and original completion hook | Reused fail-closed mount/permission/CI checks and capability-protected observations; require verified runtime identity. Installation is an overlay on a disposable pinned service build, not a model patch. |
| Existing official completed-GW ingestion and weekly review | No replacement collector or scorer. New exact fixture/element join verifies final fixtures plus official event `finished && data_checked`; stores origin target separately from rearranged actual event. |

New files live under this directory, `evaluation_ops`, the reused PR42 logger
path and `tests/research_data`. The only existing workflow changed is
`mm-current-preview-publication.yml`. Existing C2 UI, protected substitution
workflow, numerical code/config and research records are not changed.

## Public archive: no artifact-retention dependency

Each issue is a content-addressed directory and GitHub Release tagged
`fpl-forecast-<season>-gw<origin>-<revision_sha256>`. Original forecast, MM, index,
catalogue and original official bootstrap/fixtures/provenance bytes are retained
in deterministic gzip, including all shared point/minute scenarios. The bundle
also includes the full unchanged TS configuration, PR46 frozen-reference
manifest, producer-job clock receipt and checksums for compressed and raw bytes.
Forecast model/code/input identities, season, IDs, all six GW (season end only
truncated), official source deadline, capture clock and model versions remain
explicit. Original bootstrap preserves stable player codes and `ep_next`.

Forecast origin/cutoff is `data_asof`. Exact numerical finish time is not emitted
by the frozen producer: record GitHub's successful producer-job completion as
an **upper bound**, never invent a more precise timestamp. Publication time is
recorded separately from actual GitHub release/asset metadata in immutable
`publication.json`. Both complete data and receipt must be available before
the original official deadline. Later archival of stale inputs is rejected,
not backdated. A pending/incomplete release is not eligible research data.

Revisions include all original file/config/producer-receipt hashes. The same
revision is idempotent; later forecasts receive distinct identities. Recovery
checks every byte against manifest, revision and original publication receipt.
The tool never uses upload `--clobber`, moves a tag or overwrites differing data.
Partial uploads are recoverable only with missing identical assets before deadline.

Release assets have no Actions artifact-retention TTL. This reuses the existing
repository and GitHub authentication, without a new paid service or database.
See [GitHub releases](https://docs.github.com/en/repositories/releasing-projects-on-github/about-releases).
This is indefinite retention while the repository/releases are retained, **not
provider-guaranteed eternity or administrator-proof WORM**. Repository admins can
delete assets; checksums detect modification but cannot recover deletion. Restrict
writers/deletion, consider GitHub immutable-release policy where supported, and
retain an independent verified backup for disaster recovery. No billing change
or retention-policy setting was made here. Monitor growing release count/storage.

### Capture and recovery

The existing workflow runs these commands using original computation artifacts:

```sh
python integration/research-data/computation_receipt.py --repository "$GITHUB_REPOSITORY" --run "$SOURCE_RUN" > computation.json
python integration/research-data/archive.py CAPTURE/current BUNDLES \
  --sources ORIGIN/work/current-B-inputs \
  --config integration/research-data/frozen-ts-config.json \
  --computation-receipt computation.json
python integration/research-data/releases.py BUNDLES/REVISION \
  --repository "$GITHUB_REPOSITORY" --target "$GITHUB_SHA"
```

For independent recovery, with no Actions artifact or model computation:

```python
from pathlib import Path
from releases import Github, recover
folder, publication = recover(TAG, Path('recovered'), Github('pdamkier-del/fpl-analytics-app'))
```

Use `PYTHONPATH=integration/research-data`. `archive.match_final` accepts the
recovered folder, official fixtures, normalized fixture/element outcomes and
official events; missing/ambiguous/nonfinal labels fail closed. It does not
write outcomes into a forecast or substitute latest names/clubs.

Manual workflow input `research_archive_only=true` skips Pages entirely and may
reuse `validated_run`; it neither recomputes TS nor deploys the app. Normal
scheduled operation still uses the existing producer. Do not activate ordinary
production deployment to bypass PR46 release gates.

## Private TS: preserved input/output, private storage only

Install the minimal completion hook on a **disposable** original service build:

```sh
python integration/research-data/install_private_hook.py DISPOSABLE_FROZEN_RUNTIME
```

The installer verifies all532 original Python files, permits only the known HTTP
orchestration hook, and records537 file hashes including logger/config. Numerical
sources and worker entrypoint remain unchanged. Every capture rechecks this receipt.
Keep this overlay separately reviewed; do not point the live service at it yet.

Provision `FPL_TS_PRIVATE_VOLUME` as a real private persistent mount and
`FPL_TS_PRIVATE_ROOT` as its owned0700 subdirectory outside every Git checkout.
An owned0600 `storage-attestation.json` must declare the exact mount, persistent
and private storage, `public_export:false`, private backups and an operator
reference. This operator attestation is a prerequisite, not independent proof
of durability; verify restart and backup/restore on the actual host.

Capture rejects public CI, ephemeral/unconfigured storage, insecure permissions,
missing identity/config, altered inputs, incomplete/late calculations and
validation-only observations. Status contains a fixed reason, not private paths
or payload values. Manager input/output, purchase/current/selling prices,
bank, FT, chips, all sixGW, recommended XI/bench/C/VC, transfer path and keep-squad
control remain private. The original JSON semantics are preserved; raw HTTP
whitespace is not retained. Foreach player, selling price is derived using the
original forecast price and unchanged official purchase-price rule, not a later
live price. No extra optimization is run to construct a control.

Recommendation, user intention and execution are separate records. Existing
capability/origin/TTL gates protect intent/reported-execution routes. Browser
reports are explicitly **not verified official execution**, and never become
realized-policy evidence. Existing job capabilities last1hour and do not survive
service restart; durable ledger recovery does not create a durable browser login.
A trusted authenticated execution ingestion/recovery path is still required for
long-lived realized-policy research; this PR does not invent one.

Private records never go to this repository, releases, Pages or CI artifacts.
Only the original public producer inputs are permitted in release bundles.

## Readiness and verification

See [VERIFICATION.md](VERIFICATION.md), [C1 data contract](C1_DATA_AVAILABILITY.md)
and [C2 handoff](../C2_HANDOFF.md). Local success is not a live capture certificate.
Private operational readiness remains blocked until real storage/authentication
and restart/recovery release gates are verified. No private service or app deploy
is performed by this PR.

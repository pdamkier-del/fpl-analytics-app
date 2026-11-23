# Public forecast archiving — minimal main integration

This branch starts at main `e515658e`. It does **not** merge PR44,46or51.
It extracts only PR51's tested public archive, configuration and producer-clock
helpers, plus PR46's pure `freeze_forecast.py` dependency. Numerical source
remains `161b67b6`; no model, scorer, private service, PWA or app code is installed.

## Automatic operation

`.github/workflows/public-forecast-archive.yml` consumes the existing main
producer `mm-current-preview-publication.yml`:

- `workflow_run` after its completion, including UI failures where computation succeeded;
- hourly `43 * * * *` catch-up over the last24hours of main producer runs;
- manual recovery of a specific existing main producer run, with no computation.

There is no producer/deploy job in this workflow. The original producer's
schedule and Pages workflow are byte-identical to main. No merge of unrelated
UI/private integration is needed. The new workflow must exist on the default
branch before GitHub delivers scheduled/workflow_run events; a feature-branch
manual test alone does not establish that main activation has occurred.

Only same-repository, main-branch, approved producer runs are accepted. Original
workflow/source pins and successful numerical-job clocks are checked using
PR51's helper. Original artifacts are downloaded as data, never executed. No
later input, score or parameter update is used to regenerate a forecast.

The existing content-addressed Release format and no-clobber behavior are kept.
Original six-GW MM/PM/shared scenarios, official source snapshots, identities,
full TSconfiguration, byte hashes and original publication receipts survive
artifact expiry. A fresh-runner retry preserves the first manifest and every
existing asset. Every new write is recovered into a separate directory from
Releases only before being reported successful. The consumer skips producer
runs whose original receipt and provider IDs/digests already verify.

The strict before-deadline rule is unchanged: late/incomplete/corrupt inputs
cannot become eligible original forecasts. Season-end truncation remains the
existing explicit exception to sixGW. Private-manager keys are rejected by the
public validator; only the pinned public producer's two named artifacts are read.
Private TSlogging/storage remains untouched and fail-closed.

## Failure and missing-origin visibility

Each execution emits a GitHub job summary, fixed nonprivate reason codes and
`work/public-archive-status/status.json`; failure produces a failed Actions check
and error annotation. The status-only artifact is retained90days. **Forecast
storage is Releases, not this operational artifact.** No payloads, paths, private
states or signed error URLs enter the report.

Monitoring compares the official deadline calendar with verified release receipts.
It reports the next origin and missing completed origins since23November2026.
Unknown API/calendar coverage is a failure, never a claimed successful zero.
There is no retrospective claim that monitoring was active before main activation.
The official event's current deadline is also checked against original publication.

GitHub schedules are best effort; there is no guaranteed execution-time SLA.
The independent completion event plus catch-up reduce missed-event risk. Missing
producer artifacts after their24hourTTL cannot be fabricated or recomputed as
original; they remain a visible gap. Investigate failed checks before the next
deadline and retain an independent backup against administrator deletion.

Releases have no Actions retention TTL, but are not administrator-proof WORM.
Checksums/IDs/timestamps detect changes; they cannot recover deletion. This uses
the existing repository, token and producer, without adding a paid service.

## Verification and recovery

```sh
OPENBLAS_NUM_THREADS=1 python -m pytest -q tests/research_data
python integration/research-data/automatic.py --repository pdamkier-del/fpl-analytics-app \
  --target FULL_ARCHIVER_COMMIT --out work/public-archive-status --source-run ORIGINAL_MAIN_RUN
```

Omit `--source-run` for discovery/catch-up. To recover independently, use
`PYTHONPATH=integration/research-data` and
`releases.recover(TAG, destination, releases.Github(REPOSITORY))`.
See [MAIN_READINESS.md](MAIN_READINESS.md) for actual test/drift receipts and
[C1_DATA_AVAILABILITY.md](C1_DATA_AVAILABILITY.md) for scientific eligibility.

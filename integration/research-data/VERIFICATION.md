# Verification — C2 original data retention

22 November 2026. Base PR46 `876e61b0`; frozen numerical runtime `161b67b6`.

## Reproduction

Prepare a disposable full checkout at the frozen source, then:

```sh
python integration/research-data/install_private_hook.py /path/to/disposable-runtime
FPL_CAPTURE_RUNTIME=/path/to/disposable-runtime OPENBLAS_NUM_THREADS=1 \
  python -m pytest -q tests/research_data analysis/followup-41-20261122/tests
node --test integration/model-interface/*.test.js
```

In the installed disposable runtime:

```sh
OPENBLAS_NUM_THREADS=1 PYTHONPATH=src:scripts:. python -m pytest -q \
  tests/test_private_manager_service.py tests/test_mm_preview_service.py \
  tests/test_b_snapshot_policy.py tests/test_unified_b_chain.py
```

Python3.12.14, existing `/workspace/fpl-venv`; no new numerical dependencies.

## Actual local results

| Test domain | Result / boundary |
| --- | --- |
| New integration plus reused logger tests |47 pass, no skips with installed runtime. |
| Existing pinned service, B-chain and snapshot-policy tests |47 pass on the installed runtime. |
| Existing C2 model-interface/store/window JS tests |13 pass. |
| Full-chain test |Synthetic public forecast→permanent-backend test double→independent recovery→actual frozen TS calculation→private capture→new-process ledger recovery→90 exact fixture/element outcome joins. No match model refit or synthetic efficacy claim. |
| Persistence and revisions |New interpreter recovers private ledger; public recovery succeeds after deleting local archives. Later revision leaves old bytes unchanged. Release test double has persistent files, not actual GitHub durability. |
| Late/missing/changed data |Deadline boundary, absent MM/source, changed forecast/seal/config/archive bytes and modified permanent assets rejected. |
| Blank/DGW/rearranged results |Explicit blank retained with no phantom fixture; double yields two fixture rows; moved actual event kept separately from original target. Finality/data_checked and missing result gates reject. |
| Privacy/authentication |CI, unconfigured/unmounted/insecure/unattested storage rejected; capability/origin checks deny unauthorized observations; errors omit private bodies; model output/input unchanged; intention/execution not fabricated. |
| Frozen runtime |All532 original source hashes verified before install; only known service HTTP hook permitted.537 installed-file hashes checked before capture; repeat install idempotent. |

Mocks are explicit: persistent-mount detection is mocked locally, public GitHub
release storage uses a filesystem-backed test double in tests, official outcomes
are synthetic API-shaped labels. Actual TS worker and source checks run without
optimizer/scorer mocks. Separate HTTP tests stub only worker transport/computation
to verify hook order and private authorization. None of these is live private
capture, paid-disk verification or proof of FPL model accuracy.

Development failures were fixed openly: the installer's first preflight found
two generic result-write boundaries and refused installation; it now identifies
the unique original-plan boundary. An initial JSON round-trip comparison confused
Python tuples with JSON arrays; canonical equality fixed the test. The combined
fixture initially lacked required player names; the fixture was corrected. No
numerical model, weights, result or scientific protocol changed to pass a test.

## Read-only operational observations

[operational-readiness.json](evidence/operational-readiness.json) records the
actual observation. Public Pages still serves original GW11–16 with deadline
21 November11:00UTC, already expired at observation. The existing private service
health request timed out; that does not prove the service is permanently down.
PR46's public GW12artifact body could not be downloaded here (no HTTPstatus
received on redirect); no access-control bypass or signed URL was recorded.

The existing successful numerical job45061627661was independently verified via
GitHubmetadata and original workflow pin checks; its receipt is in
[computation-witness-observed.json](evidence/computation-witness-observed.json).
This is verified source/job-clock metadata, not verification of its artifact bytes.

No local private mount is configured. The connected Render tool rejected resource
inspection because no user-confirmed workspace is selected. No workspace was
guessed, resource provisioned, storage permissions changed or deployment triggered.

## Verified live public archive, with no app deployment

Archive-only [run 45076646704](https://github.com/pdamkier-del/fpl-analytics-app/actions/runs/45076646704)
SUCCEEDED using the already-computed public producer run 45061627661. Both the
`current` model computation and `preview` Pages job were SKIPPED. The source
verification and permanent archive job succeeded. No private service was deployed.

[Permanent original GW12–17 release](https://github.com/pdamkier-del/fpl-analytics-app/releases/tag/fpl-forecast-2026-27-gw12-90229f06fead26e48ae05f9b1b308245f8b196c79d476ab7c08028915d2ef10d):
release 454789206, revision90229f06…, forecast179ad0e4…,4,044 player-fixture rows.
Original cutoff22Nov19:53:22UTC; producer completed by20:10:25UTC; archive capture
22:15:29UTC; all data assets published by22:15:45UTC and completion receipt
22:15:51 UTC, **before official27Nov18:30UTCdeadline**. This issue occupies about
2.5MiB of release assets; future storage grows with original revisions.

Independent recovery on this execution host fetched all11data/manifest assets
**from Releases only**, verified every byte and original publication receipt,
and needed neither an Actions artifact nor a model run. Exact manifest,
publication and recovery receipts are retained in [evidence/](evidence/).
The earlier artifact download limitation remains an initial observation; it no
longer prevents accessing this archived issue via the permanent release.

A new-runner retry preserves the first capture manifest instead of trying
to replace its timestamp; the regression test verifies identical public receipts.
Cold-runner retry [45076965409](https://github.com/pdamkier-del/fpl-analytics-app/actions/runs/45076965409)
also SUCCEEDED: all 12 release asset IDs, digests, sizes and creation timestamps
remained unchanged. No asset or first-capture clock was overwritten. Source
computation and Pages were skipped again. Exact observations are in
[live-workflow-verification.json](evidence/live-workflow-verification.json). Main's automatic archive job is not activated by an
unmerged feature-branch test. This proves one valid retained issue and recovery,
not a record of every future GW or final-result scientific accuracy. Private
operational readiness remains blocked by the separately stated storage/auth gates.

**Delivery:** [integration PR #51](https://github.com/pdamkier-del/fpl-analytics-app/pull/51), stacked on #46. 107 tests pass; [test receipt](evidence/test-receipt.json) pins tested code and commands. Public live verification succeeded; private operational gates remain blocked. No merge or service/app deploy.

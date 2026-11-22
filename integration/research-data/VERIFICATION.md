# Verification — C2 original data retention

22 November2026. Base PR46 `876e61b0`; frozen numerical runtime `161b67b6`.

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

Archive-only live workflow probe and release outcome will be recorded separately;
until that succeeds, public end-to-end operational readiness remains unverified.
Private readiness remains blocked regardless of the public probe.

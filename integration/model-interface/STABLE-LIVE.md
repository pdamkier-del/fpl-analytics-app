# Stable live app integration

This branch extends PR #44 from `84c41932fbb90ef680cb9ce7f606307750d18e13`. Apply the overlay after the B-preview generator to `app/mm-preview/app` in an isolated build directory. The overlay uses the actually published UI source `27bf5e1e1a17360bdbbfb41fbce7fe55679c6870` as its verified reference. The Pages workflow on main specifies `b6ecb068394dc9e9f5f2c493e1f0ee0a4cbf7d96`. The published B forecast lists source `161b67b6fb8786a38e78c245b92a03ad841575d8` and the chain version `B-MM-PM-TS-v1`.

```sh
node --test integration/model-interface/*.test.js
python integration/model-interface/preview-overlay.py /path/to/generated/mm-preview/app
FPL_PREVIEW_URL=http://localhost:18097/mm-preview/app/ BROWSER_PATH=/usr/bin/chromium \
  node integration/model-interface/preview-smoke.cjs
```

The default smoke test uses a sealed expired B capture. Set `FPL_EXPECT_LIVE_GW` for a current capture and fresh checksummed official availability feed. Set `FPL_TEST_WORKER_FILE` to the served, disposable generated worker to verify activation of a new revision. Set `FPL_TEST_PLAN_FIXTURE` to a local synthetic fixture from `analysis/prepare_dashboard_news_test.py --snapshot` to check that changing the saved bank invalidates the TS result. The browser starts with an empty profile and the test intercepts any plan submission. A live private computation needs a backend configured for the same exact public forecast identity.

## Existing systems

| System | Existing behavior | Integration |
| --- | --- | --- |
| Production Pages | Legacy app; its current forecast and frontend ship separately from B. | Use a separate build and host or a separate Pages subdirectory. |
| B Pages | Reusable computation workflow, checksum-indexed forecasts and generated UI, independent availability feed. | Inject after the pinned UI build. GitHub Pages deployment is outside this overlay. |
| Private Python service | Capability-keyed TS jobs, idempotent submission, official deadline recheck and explicit B path. The B route resolves the production Pages B forecast URL. | The generated clients verify the stored team digest and the latest snapshot before accepting a response. A future isolated backend needs the matching preview forecast URL and allowed origin. |
| Official manager import | The public FPL picks endpoint provides the 15 selections, captain, vice, bench and bank at a past deadline. History provides used chips. The public picks omit individual purchase prices, selling prices and remaining FT. Predeadline changes may be hidden. | Keep the existing import-to-draft and confirmation flows. The shared store reads the existing key and preserves supplied state fields. Exact current prices and FT require user-verified or separately authenticated data. |
| PWA | Legacy mobile launcher owns a worker with its own cache. | Generated preview owns a worker scoped to its app URL. Only the offline document is cached. Forecasts and private requests bypass the worker cache. |
| Research | Published captures and model evidence exist as separate artifacts. | Export a reviewed public snapshot through the read-only format below. |

## Model interface

The existing normalized app payload is checked by `contract-v1.js`. The module metadata validator in `modules-v1.js` is a separate producer-facing interface. It checks the configured version, input identity and upstream receipts. The caller verifies bytes against a trusted manifest before calling the validator. Existing B numerical code and service request formats retain their current entry points. Individual MM/PM/TS runtime adapters have yet to adopt the producer-facing metadata contract.

All result envelopes use schema `fpl-model-module/v1` and fields `kind`, `version`, `data_cutoff`, `input_sha256`, `output_sha256`, `dependencies` and `payload`. Each dependency receipt names a module kind, version and output SHA-256. Input identities and the official deadline come from orchestration. The cutoff includes a timezone and precedes the official deadline. The downstream cutoff can equal or follow each upstream cutoff.

| Module | Preserved implementation | Input | Output and compatibility |
| --- | --- | --- | --- |
| MM | B | Official player catalogue, schedule, versioned observed inputs frozen at cutoff. | Per player and fixture minutes and playing probabilities with official player and fixture IDs. Consumers require explicit blank GW rows and retain all fixtures in doubles. |
| PM | vFinal | Frozen official inputs and an MM output receipt. | Sealed per-GW points and minutes, fixture distributions and any advertised scenario capabilities. The app contract requires one row per player per GW and an exact catalogue match. |
| TS | v3 | Exact confirmed squad snapshot and sealed forecast. MM and PM receipts identify the forecast inputs. | GW path and lineup tied to forecast identity, cutoff, origin GW and manager-state SHA-256. TS options depend on the required distribution and chip capabilities. |

`modules-v1.test.js` tests configured version switches and rejection of mismatched dependencies, input identity and cutoff. `contract-v1.test.js` tests UI forecast and plan identity, and `forecast-gate.test.js` covers rollover, stale feeds, deadlines, doubles and blanks at the display boundary. The existing B and backend test suites remain required for promotion.

## Frozen public capture

```sh
python integration/model-interface/freeze_forecast.py /path/to/mm-preview/current /path/to/frozen \
  --model-commit 161b67b6fb8786a38e78c245b92a03ad841575d8
```

Read `<payload_sha256>/manifest.json` with schema `fpl-frozen-forecast/v1`. Verify the exact `forecast.json` bytes against `payload_sha256` before evaluating. The manifest records model source commit, chain name, season, origin deadline, GW sequence, cutoff and application forecast identity. Use a model source commit verified against the associated publication receipt. Keep frozen directories separate from live publication. A candidate promotion requires its own integration PR, pinned artifacts and a regression comparison against the frozen incumbent.

## Release gate

Run the full pinned Python and browser regression suites, current official GW import with all required inputs confirmed, a privately bound TS computation, real navigation on mobile and desktop and a service-worker version transition with existing storage. Confirm that stale or incompatible projections appear as historical and a newer saved squad invalidates an in-flight result. Publish only to the isolated preview after those checks. Record the deployed URL, UI commit, model commit, forecast identity and model versions in the release receipt.

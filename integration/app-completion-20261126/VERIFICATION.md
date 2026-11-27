# Verification and delivery — 2026-11-26

**27 November update:** The owner resolved the environment-policy restriction. Production has since advanced; `BASELINE_REVIEW_20261127.md` supersedes the old baseline/release-blocker status below and records the complete new artifact review. The earlier actual-team test scope remains unchanged. See `PUBLIC_PREVIEW_20261127.md` for the successful publication and fresh public manager/browser checks.

## Scope

Integration branch based on the actual deployed stable integration, `140e3f88`, not the generated publication mirror. Only the workflow and this integration package change. No model, scorer, sampling, six-GW weights, backend, protected research experiment or production app changes. The builder preserves every pre-existing publication file byte-for-byte and adds an isolated preview directory. Original overview remains available as `advanced-overview.html`.

## Implemented

- Shared official XV, legal XI/bench, captain/vice-captain, shirts and six individual GW plus total controls on Mit hold and Transfers.
- Real official history is reused via the existing importer and private browser cache. Draft transfers are isolated from confirmed state, with search/filter/sort, reset, budget/hits only when verified, and explicitly marginal player xP rather than an invented TS recommendation.
- Original TS client, forecast/state validation, catalogue, player/club details and historical periods reused. Original planner bootstrap no longer duplicates the shared team bootstrap.
- Read-only CI verification is separated from protected Pages publication. Both publication flags are required; production baseline is checked again before deployment. No forecast recomputation.

## Actual-data browser checks

See `evidence/actual-browser.json` and `evidence/catalogue-browser.json`. Chromium used the locally staged frontend on the approved Pages origin, with frontend files routed locally. Public catalogue/model data and backend were unchanged. The private cache was populated from a genuinely completed existing Render history request, not a synthetic squad. This is not proof of a deployed preview or a fresh clean-browser import.

Verified 15 actual unique players, identical team on both pages, 11 starters and four substitutes, draft change/reset without modifying actual state, seven period controls, mobile layout without horizontal overflow and no page exceptions. Catalogue: 674 players, 20 clubs, search/sort, history and forecast periods and detail navigation. Screenshots remain private local deliverables, not repository/Pages/CI artifacts.

## Automated checks

`node integration/app-completion-20261126/test_team_model.cjs`

`node --test integration/model-interface/*.test.js` — 15 passed.

`python -m pytest -q integration/model-interface/test_preview_server.py integration/model-interface/test_archive_preview.py` — 5 passed.

The existing registered publication workflow supports `app_completion_preview=true`, with publication false by default. Its read-only job builds from the existing Pages artifact, verifies original-file hashes, tests helpers and loads the new pages in Chromium with the manager backend deliberately unavailable. It requires the real public forecast catalogue to load, rather than accepting an empty error shell. No private manager data enters CI. See the PR checks for the final commit's result.

## Explicit incomplete acceptance criteria / blockers

1. Public preview deployment was rejected by the existing github-pages environment branch policy before job steps. See `PREVIEW_BLOCKER.md`. No permissions were weakened, no alternate deployment bypass attempted and no production merge performed. The proposed preview URL is not advertised as working.
2. A real TS recommendation was not obtained: the official status observed at 2026-11-26 09:37:51 UTC was older than the original two-hour gate during testing. The exact original freshness rule remains in force; the preview now explains this cause. The existing status producer must publish fresh status before a genuine six-GW TS run can be verified. No synthetic plan is shown as actual.
3. The deployed full-history import can take minutes and its job receipts are ephemeral after backend restart. Cached actual data display immediately, but this does not eliminate that first-import dependency. A fast official-only backend is not deployed by this PR.
4. The existing original economics reconciler is limited to season 2026-27, through GW12, complete history and no prior wildcard/Free Hit. Current real history meets those constraints. Beyond its supported domain, purchase/sale prices, bank, FT and chip economics must remain unavailable; this PR does not invent them or claim unrestricted future finance support. The visual forecast horizon itself is data-driven.

## Release decision

Keep as integration PR. Public preview and a fresh real TS calculation still require verification before production approval. Owner's smallest next action is allowing this integration branch in the existing github-pages environment; then run both preview flags and review the isolated preview. Refresh the existing official status feed before TS acceptance. No production model replacement or FPL transfer is authorized or performed.

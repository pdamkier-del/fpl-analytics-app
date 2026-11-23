# FPL Analytics — model/TS plug-in boundary (draft v1)

This is a **non-production engineering integration PR**, separate from the Codex scientific Research Lab work. The current live B preview is pinned to a separate UI commit by `.github/workflows/mm-current-preview-publication.yml`; editing this branch does **not** update or certify that preview.

## Goal

Keep **one stable web app and one canonical real FPL squad**, while allowing independently versioned MM, PM and TS engines to supply verified results. No model should be installed simply by editing a dashboard URL or replacing a raw JSON file.

```
FPL official & verified match data ─┐
                                    ├─ versioned, sealed forecast ─> stable dashboard
MM adapter -> PM adapter ────────────┘                               │
                                                                      ├─ private manager state
TS adapter <── sealed forecast + exact manager-state hash ─────────────┘
      │
      └─ versioned plan ──> compatibility gate ──> Transfers / Chips
```

## What the existing app actually does

- The B-preview UI reads `vfinal-diagnostic.json`, `current-players.json`, `live-fixtures.json`, `fixture-expectations.json` and `manager-service.json` from relative paths.
- `app/classic-manager.js` explicitly accepts only `model === 'original_locked_vFinal_diagnostic'` and the private health response `runtime === 'original_locked_python'`.
- Dashboard and Transfers have overlapping implementations of manager state handling. Local keys include `fpl-manager-state-v1` (the real squad) and `fpl-manager-plan-v1` (disposable derived TS result).
- The private TS plan is already tied to `forecast_sha256`, `forecast_cutoff`, `manager_state_sha256` and `gw`. Those bindings must survive any adapter.
- A cached plan must be invalidated **as a plan**, never by deleting the user's actual squad, when forecast, model, cutoff, lineup or manager input changes.
- The production `main/app` tree is legacy; the currently published B-preview uses a separately pinned UI SHA. A merge into `main` does not, by itself, deploy a UI rewrite.

## This PR's concrete first step

`contract-v1.js` is a pure side-effect-free validator for a normalized forecast envelope and a TS identity check. `contract-v1.test.js` covers model-independent acceptance, outdated forecast, wrong squad, mismatched official catalogue, invalid GW sequence, and missing projections.

**Not yet wired into the live page.** No new model has been activated, and no stored team has been modified. It must not be described as a completed plug-in system.

## Required next integration steps (separate reviewed PRs)

1. **Canonical manager store:** one read/write implementation for import, persistence, versioning and migration; Dashboard and Transfers read the same in-memory snapshot. Keep migration reversible and never wipe local storage for a model change.
2. **Forecast loader:** verify a signed/hashed immutable publication manifest, stable GW/players/fixtures schema, freshness, source cutoffs, exact official player catalogue and advertised capabilities. Do not guess unknown model fields. Show explicit `Not Available` on invalid data.
3. **Adapters, not raw swaps:** each external MM/PM outputs the normalized sealed forecast needed by existing screens. A point mean alone cannot be assumed to provide minutes, `P(start)`, `P60`, correlated draws or a valid TS horizon. Capability gates determine which screens/features are available.
4. **TS interface:** inputs are sealed forecast plus explicit manager state; outputs include exact forecast/state hash, six-GW path, legal transfers, bench/captain/chips, and keep-squad control. TS's numerical code stays independent of UI and can be swapped only when contract tests pass.
5. **Fail-closed rollout:** isolated preview branch, automated contract/regression tests (including DGWs, blanks, deadlines, offline/cache, stale plans, recovery), end-to-end real manager ID validation and pinned UI/engine pair. Promote only after live release receipts agree.
6. **Research Lab integration:** lab reads frozen public forecast and score snapshots and produces reproducible evaluations; it cannot mutate or automatically promote the production MM/PM/TS.

## Release checks before advertising plug-and-play

- A valid synthetic second model renders all supported public views without modifying app code.
- The user's exact actual 15-player squad, purchase prices, FT, chips and bank are preserved through model switching and install/update.
- An old TS plan never appears under a new forecast; TS recommendations always declare engine ID/version and manager-state identity.
- Missing service, expired data, corrupted JSON, cache mismatch and incompatible models show actionable errors, not invented live forecasts.
- Mobile + desktop PWA both use the same release and clear caches safely without deleting manager data.
- Research and all frozen historical/prespective evidence remain untouched.

No locked MM B, PM vFinal or TS v3 numerical parameters change in this PR.

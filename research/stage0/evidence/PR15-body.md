## PREVIEW READY – NOT YET CERTIFIED

**Delivered and verified:** https://pdamkier-del.github.io/fpl-analytics-app/mm-preview/

Historical MM preview, **not a current B forecast or production activation**. Keep draft. Production MM/PM/TS/chips and benchmark remain unchanged; `locked_model_active=false`. No official transfers or private manager-state writes.

### Implemented

Reuses #4 and #8–14: PR9 B calibrator with original source caps/return protection; prior-only detailed roles and formations for XI selection only; PR13 mean-consistent minute PMF as a separately labelled experiment. One versioned `fpl.mm/1.0` contract and prospective fail-closed fitting/immutable registration interface.

Hard XI constraints forbid incompatible goalkeepers and unavailable players. **No formation nudge** to B's marginal probabilities. Verified canonical identities now cover reserves/2024 players absent from the starter-role ledger; no probability/minute changes or manual player boosts.

### Actual historical results

39,264 matched player-fixtures; all40 club-seasons; six requested arms;50 historical B refits.

| MM | MAE | RMSE | Start Brier | Errors >60min |
| --- | ---: | ---: | ---: | ---: |
| Original | 11.240711 | 21.115962 | .073445 |1559|
| B /common candidate |10.408358|20.172026|.068827|1278|

Runtime B maximum difference2.03748e-7 against frozen p/q/s/c/x, within absolute tolerance1e-6. Common contract retains frozen B exactly. PMF expectation residual<=2.85e-14 minutes. 660 covered2025/26 team-fixtures:101 exact XIs (15.303%),43.939% >=10, average9.148485. Equivalent2024 formation evidence remains Not Available.

Uncertainty **does not pass promotion**: central80 coverage90.56%; shortest80 coverage87.67%; CRPS+5.91e-6 /logloss+.0009373 versus PR13 after exact-mean repair. Intervals/distributions stay experimental.

### Completed verification

- [Validation39013829273](https://github.com/pdamkier-del/fpl-analytics-app/actions/runs/39013829273): **89 tests**, actual full refit/replay, source/identity/leakage checks, unchanged production/frozen inputs.
- [Protected Pages deployment39013859364](https://github.com/pdamkier-del/fpl-analytics-app/actions/runs/39013859364): **success** via existing main-only environment rule, unchanged. All88 other production files byte-identical to the verified original publication. All53 refreshed public paths are under `app/mm-preview/`.
- Public browser tests: Pitch/List, player popup, name/start/xM sorting both ways, all20 clubs/GW/season selectors, unavailable0-minute profile,2024 missing formations, SHA-verified payloads and reload. New canonical names verified after publication.
- Mobile-width test: same published app in390px iframe,375px client/scroll width with no document overflow; popup/sorting work. Not a claim of physical iPhone/Safari testing. No app-origin JS console errors observed.
- Existing scheduled original forecast run39011647304 also succeeded; it is not a candidate downstream validation.
- Model code `d8e5337`; numerical results `79c65d4`; public preview `2ab6558`; completion docs `7d74508`.

### Explicit stop gates

No untouched later evaluation; historical actual publication-time proxies;35 source-hard-zero conflicts; three prior B club-risk flags; incomplete2024 formation ledger; failed probabilistic calibration/non-inferiority gate; no verified current-season PR8→B feature bridge. Current B forecasts therefore remain **Not Available**. No unapproved B-derived xP/TS outputs produced.

[Full mathematics, errors, all clubs and paired intervals](https://github.com/pdamkier-del/fpl-analytics-app/blob/integration-mm-preview-20261017/docs/research/2026-10-17-mm-integrated-preview.md)

[Completion evidence, tests, source coverage, publication and rollback](https://github.com/pdamkier-del/fpl-analytics-app/blob/integration-mm-preview-20261017/docs/checkpoints/2026-10-17-mm-integrated-preview-complete.md)

Do not merge the entire research stack into production. Activation requires the documented gates and selective reviewed integration.

Follow-up PR #16: https://github.com/pdamkier-del/fpl-analytics-app/pull/16 adds the isolated locked-PM/TS bridge, historical point replay and prospective source capture. It also confirms a PM duration-clipping mean mismatch, so live activation remains blocked. The MM-only historical preview in this PR is not a certified current MM → PM → TS release.

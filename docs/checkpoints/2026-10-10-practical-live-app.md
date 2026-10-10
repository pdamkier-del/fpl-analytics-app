# Practical original-model app recovery, 2026-10-10

Continue from newest branch HEAD, not a recorded forecast. Default branch `main` now contains the online manager workflow and scheduled current diagnostic workflow. Both explicitly check out `free-github-static-20261010`. Main's original application files and all branch history are preserved.

## Practical integration

- `live-manager-plan.yml`: authenticated browser dispatch or normal GitHub Run workflow, original Python TS v3 and FH/WC/BB/TC adapters, cutoff-bound input, encrypted browser result. The optional RSA public key and UUID are data, never shell code. Token remains in the browser tab only. The browser rejects a plan with another manager hash, cutoff or GW. TC remains manual.
- `current-diagnostic-forecast.yml`: every six hours and on demand, fresh official FPL + verified provider capture, unchanged MM/vFinal adapters, two exact raw rebuilds, two original TC replays, original manager validation and repository tests before release/commit/Pages publication. Failures retain the last verified forecast and publish attempt status separately.
- Immutable GitHub release snapshots retain raw sources, derived inputs, outputs, per-file checksums and workflow provenance. The selector and append-only release manifest live under `model/checkpoints`. Restore rejects wrong archive hashes, member sets, unsafe paths and wrong file hashes. Initial immutable checkpoints remain available.
- Fresh forecast requests are available in My Team. Actual manager observation must precede the new forecast cutoff; invalid observation times are never rewritten. Incomplete drafts are preserved locally. FT and purchase prices remain required and are never inferred from squad value/current prices.
- Current recommendations are unavailable after the origin deadline, an official-next-GW mismatch or 24-hour forecast expiry. Source freshness is a publication/input guard, not a transfer decision parameter. The original six-GW strategy is not shortened near season end; GW34+ remains blocked until an already locked valid end-of-season contract is available.
- My Team uses original computed XI/C/VC/bench on a responsive pitch, and displays existing player xP/minutes/per-fixture start probabilities beside the selected roster. Alternative transfer/chip inspection does not apply official transfers or rewrite owned squad state. `my-team-live.html` routes to the original manager integration; its earlier source remains for existing rule regression tests.
- The existing 46-topic interactive mathematics tree is retained. Its original formulas/source links are unchanged. Live diagnostic status and manual TC are explicitly distinguished from historical replay performance.

## Snapshot-specific integration defects corrected

The TC extension previously restored the fixed GW7 snapshot in `finally`; it now backs up/restores the actual ordinary data for the current run and verifies the original input/output hashes. Only current-half ordinary rows enter TC if a six-GW horizon crosses GW19. Original draws/seeds/float32 aggregation/top-20 selection are unchanged.

Keeper coverage no longer assumes exactly 50 games. Penalty source coverage no longer assumes exactly 100 sides. Player component coverage no longer assumes exactly 4,002 rows/60 fixtures. All require actual fixture/player identities and cutoff-safe source coverage. Original model mathematics and minimum keeper history remain unchanged.

Fresh source captures showed five GW6 fixtures (51, 52, 53, 57, 60) with official `finished=false`, `finished_provisional=true`, `started=true`, 90 minutes, and scores exactly equal to the completed provider match. This is explicit provisional evidence, not an invented final result. Keeper SOT accepts those independently observed, score-reconciled matches diagnostically and records their IDs. Unresolved scores or coverage gaps block publication. Official GW-level historical player data keeps its original closure requirement.

The provider's FA inventory still returns 2025/26 when 2026/27 is requested. That precise pre-existing diagnostic limitation remains excluded/disclosed. Every other collection error blocks publication.

## Newly recovered historical GW6 roster

The original immutable input archive contains the official predeadline GW6 bootstrap. It has 667 registered players, observed `2026-10-10T07:34:58.649875+00:00`, before official deadline `2026-10-10T10:00:00Z`.

Raw source: `data_v1_1/raw/live-captures/20261010T073458Z/bootstrap.json`.

SHA-256: `0d483cb9d0962156f8df8aef5031fb4de151bb166bad512979e9645e01bd949e`.

Source checkpoint: `model/checkpoints/live_inputs_20261010_v1`, archive SHA-256 `61123e5c6fb8446ec3836c3ac1dbc902132cc371683b88310f2722b1934d428f`. Capture timestamp is independently retained in the checksummed `live_vfinal_20261010_v1` source manifest. The recovered `gw6.json` must match that raw roster/news exactly; the regression restores and hashes the original archive. This supplies genuine GW6 eligibility/news when completed official outcomes become available. It does not claim exact deadline completeness or fill unavailable outcomes. Historical GWs without such a roster are explicitly excluded. New predeadline roster versions are retained append-only for later historical use.

## Alternative source research and certification blockers

No repeat crawl of the 223 previously inspected provider repository versions was performed. Fresh source versions are captured by the actual update pipeline and individually re-audited. The original 334 missing BPS rows were not recovered. With five newly completed provisional matches, the diagnostic audit found 1,204 verified and 492 quarantined rows: chances_created 106, dispossessed 110, was_fouled 265, accurate_passes_percent 16, tackles_won 159 (overlapping fields). Missing values remain missing; raw Tackles is not relabelled as tackles_won.

New primary documentation checked:

- FootyStats individual-player endpoint: https://footystats.org/api/documentations/player-individual. Its documented statistics are by season/league. Season totals, averages and percentiles cannot identify missing player-match actions. Access also requires a provider API key. No current-season per-match payload with the required identities/definitions was obtained.
- FootyStats match endpoint: https://footystats.org/api/documentations/match-details. Documented team statistics and lineups do not establish every required player BPS action. `date_unix` is documented as kickoff, not publication time; it cannot replace the historical availability proxy.
- Hudl Statsbomb live API examples: https://live-data-api-guide.statsbomb.com/scripts-services/javascript.html. The documentation describes Premier League queries, but does not itself supply verifiable 2026/27 historical match payloads or prove exact publication times. No such licensed/current-season source payload was available in this task. Previously checked free open data is not reclassified as current-season coverage.

No new source above justified inventing a BPS value or converting a match/capture/update timestamp into exact historical publication time. Kickoff + 4h remains an explicitly unverified historical proxy. Historical cohort/registration and provider semantic gaps, the excluded FA inventory, missing BPS actions and publication-time evidence continue to block full certification. `locked_model_active=false` is preserved.

## Verification so far

- Main online original manager runtime: https://github.com/pdamkier-del/fpl-analytics-app/actions/runs/38081406102 — passed, synthetic validation only.
- Original full integration: https://github.com/pdamkier-del/fpl-analytics-app/actions/runs/38081514243 — 389 repository tests + seven forecast deadline/GW/freshness checks passed, original TC exact replay passed.
- Python-to-browser WebCrypto response round trip and malformed/tampered encryption checks passed locally; recovered GW6 archive verification passed locally. Local broad test restoration is partial; CI is authoritative for the full historical fixture suite.
- Fresh forecast publication is being exercised at https://github.com/pdamkier-del/fpl-analytics-app/actions/runs/38081916486. Earlier attempts correctly rejected incomplete source coverage; read the newest attempt, not the first failure.
- Responsive review uses the actual manager page at 390 and 1080 pixels: `app/ui-review.html`.

Personal optimization remains Not Available until actual FT, all purchase prices and a verified observation timestamp are provided. A saved future FH/WC/BB calendar is not fabricated: original policies replan at each deadline; TC exposes concrete/anonymous future options as manual provisional support.

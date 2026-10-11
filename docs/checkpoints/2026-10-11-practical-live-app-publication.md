# Practical live app publication — 2026-10-11

Continue from newest HEAD on `free-github-static-20261010`. Read this checkpoint and `2026-10-10-practical-live-app.md`. Default `main` contains both dispatch/schedule workflows; main's application and the working branch/history are preserved.

## Verified deployed snapshot

- Official capture cutoff: `2026-10-11T07:08:34.014305+00:00`; GW7–12, 60 fixtures, 667 players / 4,002 player-fixture forecasts.
- Fresh original data → MM → vFinal → TS v3 → FH/WC/BB/TC workflow: https://github.com/pdamkier-del/fpl-analytics-app/actions/runs/38116328855, **attempt 2 passed and deployed**. Attempt 1 correctly refused publication.
- Five watched raw-rebuild artifacts were exactly identical in two complete rebuilds; historical training 3,179 rows. One-match and one-GW seed parity passed. 104,000 original TC samples replayed exactly. Current TC rows use approved six-GW inputs verbatim.
- **397 Python regressions and seven forecast/deadline/GW checks passed** in that fresh run.
- Independent original-manager integration: https://github.com/pdamkier-del/fpl-analytics-app/actions/runs/38120333104, 397 + seven checks passed on the immutable historical regression snapshot.
- Main online Python runtime and fresh official FPL deadline verification: https://github.com/pdamkier-del/fpl-analytics-app/actions/runs/38120904078, **13 relevant tests passed**, synthetic validation only. Official GW/deadline is checked before and after a personal calculation; changed/expired deadlines block its return.
- Latest separately verified Pages restore/deploy: https://github.com/pdamkier-del/fpl-analytics-app/actions/runs/38120901489. The fresh forecast workflow also passed Pages deployment.
- Immutable release: https://github.com/pdamkier-del/fpl-analytics-app/releases/tag/diagnostic-38116328855-2; 622 checksummed members. Archive SHA-256 `6c86688c28d5f3743b24c65a066f6646808b757a71d7880a5015d4e681a6666f`.
- Source/math protection: comparison to task starting HEAD `528005a8e349571b2631127604983ab189af8f07` changes no `src/`, `config/` or frozen `analysis/` files. No model formula, trained-procedure definition, coefficient setting, TS/chip strategy, seed, 400-draw count or top-20 TC rule changed. `locked_model_active=false`.

## Online and update operation

My Team runs original Python through GitHub Actions on main, checks manager hash/cutoff/GW, and decrypts an ephemeral RSA-OAEP/AES-GCM reply. Token is tab-memory only. Manager input is sent to Actions; plan can also be downloaded as a 30-day Actions artifact. No personal manager state is committed as plaintext. A user-authorized Actions token and complete real state are still needed to exercise an actual personal browser request; that authenticated end-to-end request has not been claimed tested.

Automatic forecasts run every six hours and on demand. They capture sources, retain predeadline roster versions, reproduce original outputs and TC scenarios, validate, append an immutable release and publish. Failure status is recorded without replacing the last verified release. Forecasts expire at their official deadline, official-next-GW mismatch or 24-hour cutoff age. The original maximum six-GW horizon is retained. At GW34–38 the original planner already uses available season GWs and the original weight prefix; adapter/frontend guards follow that existing source behavior. Missing mid-season horizon rows still block publication.

TC overlap comparison guards numerical batch-size drift using eight float64 epsilons on a symmetric unit-or-value scale. It rejects material changes and all changed identities/NaNs. This is an adapter comparison guard; current values are not rounded/replaced. Exact raw-rebuild and exact TC-replay claims refer to their two same-input rebuilds, not raw long-horizon batch overlap.

Responsive My Team, alternative transfer/chip inspection and the 46-topic interactive original mathematics tree were inspected in the actual browser. 390px and 1080px views use the same page/state. Proof: [model tree](assets/2026-10-11-model-tree.jpg).

## Current synthetic example — NOT the user's team

Cutoff 2026-10-11T07:08:34.014305+00:00; explicit cheap legal test squad with two FT:

- GW7 five transfers; in Saka, Thiago, Groß, Haaland, E.Le Fée. Original projected XI/captain score 37.882586; gain before hits 31.952968; official hit 12; original uncertainty buffer 3. FT 2 → 1; bank 370 → 145 tenths. Weighted six-GW improvement over hold 73.887347.
- FH current-GW gain 25.330000; WC weighted-horizon gain 61.722208; BB current-GW gain 0.006375. Their original different horizons must not be treated as interchangeable one-GW gains.
- Manual TC support: SAVE_TC; use-now 6.377500, concrete future option 7.290935 (Mbeumo, provisional GW10), latent DGW option 10.419375. This unused-TC test does not apply to a state whose TC was already used. Such a state is explicitly shown as already used.

The public example's cutoff/GW must match the current forecast or release packaging fails. Personal output remains **Not Available** until actual FT, all 15 purchase prices and an authentic UTC observation time are supplied. The documented roster/bank/chip facts may remain a browser draft; they are not a completed manager state.

## Unresolved source/certification limits

- Original 334 incomplete BPS rows remain unresolved. Latest fresh capture: **1,204 verified, 524 quarantined**, with 56 observed matches / 112 team sides. Missing overlapping fields: chances_created 108, dispossessed 112, was_fouled 265, accurate_passes_percent 16, tackles_won 191. Additional observed GW6 rows increase quarantine; they do not repair the original 334.
- Authentic 667-player predeadline GW6 roster was recovered and verified against original archive hashes. Historical cohort completeness, provider mappings/semantics and source-news completeness remain limited; GW6 outcomes are not invented.
- Exact historical publication times remain unverified. Kickoff + four hours is an explicitly uncertified proxy.
- Provider FA inventory remains wrong-season and excluded/disclosed. Every other capture error blocks publication.
- New alternative primary source documentation did not supply verifiable current-season missing BPS actions/publication times. No repeat scan of the same 223 provider revisions.
- Original policies replan FH/WC/BB at each deadline; there is no invented fixed future four-chip calendar. TC options are provisional and remain manual.
- Full live certification remains blocked; `locked_model_active=false` is preserved.

Season-end compatibility is verified with explicit synthetic GW34 and GW38 regressions: the original source chooses five and one remaining GW respectively with its unchanged weight prefix. A missing GW in the middle of the season is rejected. No season-end strategy or coefficient was invented. Current GW7 inputs/calculations are unchanged by these adapter bounds.


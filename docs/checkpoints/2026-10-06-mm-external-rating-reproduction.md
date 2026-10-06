# Original external ratings: reproducible MM experiment

Scope: MM only. PM, TS, rating_history.py, xi_assignment.py, the existing MM v2 experiment and all minute-duration mathematics remain unchanged. This is an experiment on reused GW22–38; it is not a promotion or an independent OOS claim.

## Sources and mapping

FotMob's original 0–10 `playerStats.FotMob rating` is preferred; the original lineup performance rating is used only when that precise stat is absent. No normalisation, rescaling, rounding, inferred ratings or replacement zeros are introduced. SofaScore's official www API returned HTTP 403 in the provider probe; no SofaScore rows are invented. Multiple provider rows are supported and retained separately by the importer.

The frozen FPL identity source is `olbauday/FPL-Core-Insights` at `1c9191ab6b0c191378ea27f257fdab2bae63caba`. Its files are identity and fixture registries, not the model repository. FPL season player IDs are connected to existing UUIDs using the existing exact all-competitions/core joins. FotMob Opta IDs equal the stable FPL player codes and bootstrap the provider player-ID map. Conflicting anchors remain ambiguous. There is no fresh fuzzy, surname-only or abbreviation guessing. Exact name fallback requires team and match. New 2026/27 player UUIDs are not manufactured; promoted clubs do not inherit another season's team ID.

Match IDs must exist in the source registries. Provider match-ID anchors must also agree with season, competition, date and PL club. Date-free repeated European fixture keys quarantined by the earlier independent audit are excluded. Existing dated recovered IDs are retained. Unresolved raw provider facts and ambiguity reasons are saved rather than forced into the model ledger.

Competition inventories cover PL, Champions League, Europa League, Conference League (including its qualification), FA Cup and EFL Cup. Only completed, non-cancelled/non-awarded matches with a PL club from the corresponding season's club roster are requested. July-to-June kickoff bounds reject season-selector fallbacks; a future-season endpoint is not assumed to honour its selector. Known club aliases/provider IDs carry forward only via permanent club codes. Coverage counts describe the returned provider inventories and frozen internal registry; failures and unmapped fixtures are explicitly reported. They do not establish that a failed competition endpoint had no matches.

## Time availability

The provider response does not expose a certified historical rating-publication timestamp. For provider-confirmed finished matches, `available_at = kickoff + 6 hours` is a conservative proxy beyond normal 90/120-minute play. It is not represented as an observed publication timestamp, and later rating revisions cannot be certified from a current historical response. Existing rating_history.py strictly filters `available_at < cutoff`. The collection separately checks the target fixture/player against every feature-table cutoff, plus postmatch proxy, duplicate and 0–10 bounds checks. The raw response manifest includes retrieval time and payload SHA256; retrieval time is not substituted for historical availability.

## Run and resume

```bash
PYTHONPATH=src python scripts/collect_mm_external_ratings.py --as-of 2026-10-06T23:59:59Z
PYTHONPATH=src python scripts/rebuild_mm_rating_ledger.py
PYTHONPATH=src python scripts/run_mm_v2_xi_rating_experiment.py --ratings data_v1_1/derived/mm_v2_ratings/player_match_ratings.csv.gz --out analysis/results/mm-v2-xi-rating-with-external-ratings-20261006-v1
PYTHONPATH=src python scripts/analyze_mm_external_rating_experiment.py
```

Successful provider responses are cached by URL, with response hashes and retrieval time. GitHub Actions restores and saves this cache even if later steps fail. It uploads outputs as artifacts; repository publication is through the authenticated GitHub connector, without local HTTPS push credentials. The captured-run season-scope audit removed only unmapped past-season fallback rows and verified byte-identical model inputs; no model refit is needed for that cleanup. `scripts/audit_mm_rating_season_scope.py` documents this one-time audit. The offline rebuild uses `raw_provider_ratings.csv.gz` and `exact_mapping_inputs.json.gz` and requires no provider network access. It asserts equivalence with the published mapped CSV.

The data directory holds the mapped ratings, every raw rated player, row-level mapping audit, fixture inventory, exact mapping inputs, frozen identity sources, identity/coverage audits and SHA256 data manifest. It preserves unresolved provider data for future certified mapping without redownloading matches. A manifest retains HTTP provenance; the full HTTP cache is a resume aid rather than a required offline ledger-rebuild input.

## Fixed diagnostic slices

The companion analysis replays the unchanged locked MM and asserts agreement with the experiment's baseline. It then compares the same prediction rows for locked MM, XI-only and XI with original external ratings, including three-state log-loss/Brier and minute MAE/RMSE. It saves all cutoffs, q/H inputs, conditional bench-appearance probabilities and unchanged duration expectations in an augmented prediction ledger.

Definitions fixed before reading results: uncertain starters have base P(start) in [.20,.80]; multi-role players have at least two q_role_slow values >= .20; close role competition means at least two competitors and absolute XI margin <= .25; rating trends require at least two past matches and +/- .25 on the original scale. Lineup shocks use base P(start)>=.80 with an actual nonstart or <=.20 with an actual start. Incumbent/competitor cases require the same team, fixture and expected role, an incumbent nonstart with base P(start)>=.80 and a starting competitor with a higher prior recent rating.

Those outcome-based case slices are descriptive only. They do not show why a coach changed the lineup, or establish a causal effect of ratings. Empty slices are not reported as zero-error successes. All GW and team/role slices are retained, including requested GWs 30,22,31,36,32,38,37,29. No thresholds or model hyperparameters are tuned to the old reported gains or to this reused diagnostic.

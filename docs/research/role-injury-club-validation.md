# Role / injury history and club-level MM validation — research contract

This is an MM-only research extension of the existing individual-role MM. No PM, points, TS or chips are simulated in this task. The production MM/PM/TS, chips and 2,125-point benchmark are untouched.

## Source data, not invented injury labels
The archived Core has no independently verified medical clearance/training-return dates. The completed research replay now integrates timestamp-bounded historical FPL news for both seasons; see [the full results](2026-10-16-role-injury-mm-results.md). Official selection flags must not be confused with medical clearance. Reconstructed past squad sheets can confirm a *past* available player, not an injury diagnosis or a future starting XI. FPL `news`, `status`, availability percentages and timestamped official club/PL news may supply prospective observations, but an unverified or missing state must remain UNKNOWN. Team news should be collected as snapshots **before every relevant deadline**; a current web page cannot safely be retroactively used in earlier gameweeks.

An append-only UTF-8 CSV can contain:
`player_uuid,club_id,effective_at,published_at,captured_at,source_url,source_kind,state,return_earliest,return_latest,injury_type,training_state,confidence`.
All timestamps are ISO 8601 with timezone. States: OUT, SUSPENDED, DOUBTFUL, RETURNING, AVAILABLE, UNKNOWN. A verified report does not automatically justify a medically accurate return prediction; return windows only when explicitly sourced. Retain original text and provenance outside the CSV for audit. Do not infer training or return from a match gap. Player identities must be canonical, club identities season-scoped and transfers carefully reconciled.

`scripts/research_role_injury_club_audit.py` implements an as-of selector that uses only captured/published facts strictly before cutoff and fails closed on same-time contradictory statuses. UNKNOWN never becomes AVAILABLE. These states are **not yet calibrated to probabilities** and must not be injected as automatic p_start=1 or 0 without a certified rule and expiry checks. Returned-available does not imply full-match fitness.

## Per-club, paired simulator evaluation
Once historical research candidate MM outputs are exported as:
`season,club,player_uuid,fixture_uuid,actual_minutes,baseline_minutes,candidate_minutes`
with no duplicate identity/fixture rows and identical eligible sample sets, run:
```sh
PYTHONPATH=src:. python scripts/research_role_injury_club_audit.py --paired-csv work/paired_mm_minutes.csv --output-json analysis/results/club_mm_errors.json
```
The script outputs club+season sample size, original/candidate MAE, change and signed bias, sorted worst regression first. Do not fit candidates on this evaluation set. Also evaluate start Brier/log-loss and position/role and confirmed-news subgroups in the existing MM evaluator; clubs with small samples require uncertainty intervals. Squad and on-pitch minute-sampler outcomes differ from raw analytic MM labels. Do not invent a 6GW TS replay until 183 origin/target pairs are source-certified.

## Next development gate
1. Backfill only verifiably time-stamped historic news/squad/role records with source references; report coverage (including UNKNOWN) per club. Never silently reclassify past OUT cases from future actual appearances.
2. Join evidence to the existing MM candidate's **cutoff** (not target kickoff), isolating baseline forecast vs new status-based forecast and comparing against the existing no-role logistic arm. Role must be learned from verified-available starts; medical absence must not erase a long-term first-choice prior.
3. Freeze role/status and injury-feature definitions on development GW; evaluate on later periods. Report all 20 club deltas plus aggregate, high-xG key players, confidence intervals, lead time, and RETURNING subgroup with true labels only when available.
4. Obtain independent prospective MM validation, calibrated availability inputs and verified return evidence before integration. PM, TS, chips and points are explicitly outside this task.

**Current status**: 13 MM-only arms completed on identical historical cohorts, all 20 clubs per season reported, source manifests and checksum-verified permanent capsule preserved. See [results and limitations](2026-10-16-role-injury-mm-results.md). No production promotion; `locked_model_active=false`.

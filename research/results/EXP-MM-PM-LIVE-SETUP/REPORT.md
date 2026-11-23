# Phase 4 — prospective MM/PM validation setup

23 November 2026. **Infrastructure verified; prospective accuracy evidence pending. No model promotion.**

## Decision and actual evidence

Reuse EXP-MM-LIVE-001 and EXP-OPS-EVAL-001; register only the missing frozen PM study, EXP-PM-LIVE-001. All 64 prior protocol JSONs and old append-only events are preserved. PR41/42/49 definitions and historical findings inform endpoints; no historical efficacy study or protected substitution experiment was rerun.

The shared protocol was committed as `7c4df96f` before eligible future issues/outcomes. Registration boundary: **23 November 2026 11:04:39.640399 UTC**. Both forecast data timestamp and complete publication must follow it. v1 code/command registered before its real preflight; v2 code/command registered before a second preflight. Their manifests and actual receipts are retained. v2 only bounds repeated archive metadata I/O; exact transformation test protects selection/scoring logic.

**Real archive link:** original GW12 release revision `f54f651ea03ee099ef5be35c9cb36eddc3a8472470ead2aaac786b097c281633`, forecast `4d1a2e3925d5da64bfdfa2f7f98a9b7a04ade220f3546f655e4bc4a7ca1051dd`, six-GW horizon 12–17, 400 shared scenarios. Existing pinned C2 Release recovery, byte checksums and full archive validation succeeded on original compressed files. This issue predates registration: **infrastructure example only, no prospective score**. See archive-link-proof.json and both preflight status files. Redundant recovered asset copies are not committed; they remain independently recoverable from the original public Release.

**Actual automatic archive operation:** main workflow_run `45150316270` succeeded on 23 November at 09:48–09:49 UTC, recorded in automatic-archive-observation.json. That proves a natural C2 archive trigger, not execution of this new research evaluation workflow.

**Official result status observed:** GW12 `finished=false`, `data_checked=false`; deadline **27 November 2026 18:30 UTC**. The current preflights scored **zero prospective origins**, found no eligible new original issues, and did not request future event-live outcomes. A newly issued complete original before **27 November 17:30 UTC** can qualify GW12. Otherwise the study begins at the next eligible future origin; do not backfill the already inspected older issue.

## Fixed scientific design

- Latest complete eligible original at deadline minus 60 minutes, selected without labels and retained immutably; original MM/PM source, IDs, hashes and full six-GW payload verified. Score origin GW only.
- First eligible origin fixes 16 consecutive scheduled origins (season end cap). Final lock is 30 days after the last origin's deadline, taken from the first selected original calendar. No extension or efficacy stopping.
- Formal final review needs at least 12 complete GW and 120 distinct fixtures. Missing support gives an inconclusive result. Interim numbers are descriptive.
- MM: start/play/P60/P90 Brier, log loss and calibration, minute MAE/RMSE/bias, empirical minute CRPS/PIT/intervals. Preserve native probabilities separately from scenario marginals. Prior-only smoothed start-frequency and minutes-per-completed-club-fixture baselines use original bootstrap; insufficient or in-progress history remains unknown.
- PM: empirical point CRPS, MAE/RMSE/bias, haul probabilities, PIT/interval calibration; goal/assist count means, qualified CS/DC award probabilities, save-bucket and bonus-mean errors. Official original `ep_next` is a mean comparator only, with origin-is-next and identity gates. Never invent its predictive distribution.
- Two primary comparison endpoints: start log-loss difference and point MSE difference versus the prespecified baselines. Whole-GW equal weights, fixed circular moving-block bootstrap lengths 3 and 6, 2,000 replicates, 95% descriptive and 97.5% family-adjusted intervals. No inference before lock/minimum gates; sample floors do not prove power.
- Fixed position/club/original role/availability/probability groups and original top-50 xP cohort; no outcome-selected cohorts. Full protocol contains target, missingness, multiplicity and stop rules.

## Data contracts, limitations and attribution

Official final `finished` AND `data_checked`, finished fixture identities and stable player codes are required. Closed-world component ledgers and counts must reconcile. DGW starts require per-fixture history; no inferred starts from minutes. Explicit official DNP is distinct from missing rows and card-only zero-minute events. Blank/double GW, missing/changed identities and label revisions are tested. Raw label vintages remain separate from forecasts.

CS award probability combines eligibility and no-concession: it is not unconditional club CS probability. DC has no 60-minute rule. Save point means are not save-count laws; bonus means are not joint BPS distributions. Injury-return episodes are not identifiable from current role/availability metadata. Point/minute residual association does not causally isolate PM error. MM and PM are scored separately on identical fixtures and descriptive actual-minute strata; no oracle correction or model change is performed.

## Verification and operational readiness

v1: 88 tests passed before its recorded preflight. v2: 91 tests passed, including 26 new MM/PM infrastructure/metric/contract tests and prior research contract/regression checks. The v2 test receipt records the exact command and revision. Fixtures include synthetic final/nonfinal/DNP/DGW/blank/corruption cases and two already-known GW10 official ledgers for contract regression only. No reused data become independent evidence. These tests do not claim real future accuracy or full season operational reliability.

The CLI's connection to an actual original public archive is verified twice. Immutable report writes/restart recovery and final-lock behavior are tested with an in-memory public backend. No real prospective research report/selection has been published because none qualifies. Live final-label matching/scoring for this study awaits an eligible original and finished outcomes. The proposed daily/archive-triggered report workflow is on the research branch, **not activated on main**. Its eventual Release writes require separately reviewed integration; it does not deploy the app or change the producer.

## Prioritized next actions and costs

1. **Now:** review/register this frozen evaluator and integrate only its report consumer after review. Existing public GitHub APIs/Release storage, no new service or paid data; one short daily job plus archive events. Actual production API throughput has not been benchmarked.
2. **Next valid origin:** capture an issue after registration and before its cutoff, then wait for official finality. Report true coverage and proper scores without tuning. Calendar cost: first outcomes after GW12 completion at earliest; formal assessment only after the fixed multi-GW window and lock.
3. **After supported fresh residuals:** prioritize MM exposure/start/P60 errors and point-unit goal/assist/CS/DC residuals in the prespecified decision-relevant cohort. Preserve sparse/negative findings. Saves/bonus mechanisms and injury-return cohorts have explicit identification gaps. See NEXT_IMPROVEMENTS.md for component-specific prerequisites/costs.
4. **Next model experiment:** preregister one supported mechanism on later untouched outcomes; do not fit or select a correction on this validation window. No defensible new failure ranking or claimed FPL point gain exists yet.

Frozen MM B, PM vFinal, TS v3, app, prior research outputs and protected substitution trial remain unchanged. Independent scientific/code review remains pending.

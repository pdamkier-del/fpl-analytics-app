# Frozen MM/PM prospective validation — locked implementation protocol

23 November 2026. Implements existing EXP-MM-LIVE-001 without changing its JSON,
primary start-log-loss endpoint or12GW/120 match review floor. Registers the
missing frozen-PM observation study as EXP-PM-LIVE-001. Existing OPS-EVAL-001
is the infrastructure parent. No candidates, fits, substitutions trial changes,
model/app changes or repeated historical efficacy study.

## Novelty, scope and issue eligibility

PR41/42 and LEGACY-016–027/031/033/035/036/038/041/043/053 already contain MM,
PMcomponent and oracle diagnostics on seen/reused data. PR49supplies the component
dictionary and identifiability gates. Reuse those definitions; new evidence here
must come from **new original issues and future final outcomes**, not new plots
of GW8–10. PR52/53 supplies verified public originals and recovery. No private
manager data or commercial model is needed.

Common registration boundary is the UTC event registering EXP-PM-LIVE-001.
Only model source161b67b6, unchanged TSconfig and original forecast **data_asof
AND complete publication after that boundary** are eligible. Entire six-GW
data must recover/hash-match via the pinned PR53archive implementation. Current
already-issued GW12archives are infrastructure examples only for this study.

For each origin select the latest complete original issue available at
**T=official origin deadline minus60minutes**; include publication.json's actual
provider asset creation clock. Ties: data_asof, completed publication, revision ID.
Selection uses timestamps/identity only, before accessing any outcomes. BeforeT,
report provisional/pending; afterT, write an immutable origin-selection receipt.
No later revision replaces it. Invalid/late/missing originals remain explicit gaps.

GW12is possible if a new eligible issue reaches its27Nov18:30UTCdeadline's
T-cutoff after registration; otherwise start at the first qualifying future
origin≥12. Earliest start is not backfilled from an inspected earlier issue.

## Population, period and stopping

Use only **origin-GW targets** from each issue. Later fiveGWare retained, never
pooled as independent observations. First eligible origin g0fixes16consecutive
scheduled origins g0…min(g0+15,38). Final data lock is30days after the last
origin's official deadline. No extending the window, early efficacy stopping,
parameter/model tuning, outcome-selected baseline or exclusion after viewing scores.

Formal final comparison requires≥12 complete valid GWs AND≥120 distinct matched
fixtures, preserving the existing MMminimum. Fewer means inconclusive, not a
relaxed threshold. Primary all-roster fixture/point coverage must be complete;
partial/schedule-changed cohorts are descriptive and cannot satisfy that gate.
Interim per-GW reports are descriptive only; no rolling significance decisions.

All original eligible catalogue players form the primary cohort. Prespecified
secondary cohorts: p_play≥.20 per fixture; p_start<.20/.20–.80/≥.80; each FPLposition,
club, original MMnormal_role (regular/reserve/rotation_or_short_history or raw
unknown), original availability flag, and top50origin-xP players (ID tie-break).
Sparse groups retain counts and missingness, not an efficacy claim. Top50is a
public decision-relevance proxy, not a private manager or realized FPLgain.
No verified injury-return episode field is archived: do not relabel availability
caution or short history as actual injury return.

## Outcomes and correctness gates

Use official event finished&&data_checked, every actual fixture final, exact
season/fixture/element and stable player code. Reuse the existing official completed-
GWpayload schema. Optional official element-summary history is required for DGW
starts; never infer starting from minutes. Single-fixture starts use explicit
official GWstarts. Per-fixture minutes/component points come from official explain
lists; full point ledgers and event totals must reconcile.

An omitted entry is zero ONLY within a complete finalized official point-award
ledger. An explicitly present zero-stat/no-explain player can support DNPzero;
missing players or identities cannot. Card-only participation at0minutes is
separate from positive-minute appearance. DGWstarts missing without fixture history
stay unknown; no distribution is invented. Preserve explicit blanks, all double
fixtures and postponed identities. Schedule changes exclude affected primary
targets with reasons; never join by names/current clubs or move a prediction.

Retain original raw label checksums and observed_at; corrections create new
label/report hashes, never rewrite forecasts/selections or silently replace reports.
Pending events are not fetched/scored as final. At final lock, no later correction
changes the registered primary analysis; subsequent corrections are sensitivity.

## Metrics and baselines fixed before new outcomes

**MM primary:** start log loss (natural log, fixed probability clamp1e-6).
Brier/start reliability also reported. Appearance means positive reported minutes;
evaluate original p_play, bench-appearance probability and q_sub on actual nonstarts.
Report minute MAE/RMSE/bias, start/cameo conditional duration diagnostics, P60andP90
Brier/log loss, fixed decile calibration and four-category minute-bin Brier.
P90means reported90, not a team-clock conservation constraint. Full minute CRPS
uses original **GW-total** minute samples; no per-fixture PMF is fabricated in DGW.

MMbaselines from that issue's original bootstrap and source-completed fixture count
Nfor the player's original club: Beta(1,1)smoothed start frequency (starts+1)/(N+2),
and mean minutes/N. Only records with N>0, valid prior counts and no impossible
count>N qualify; report paired coverage. They are simple current-club-denominator
season references, not certified transfer-adjusted histories. Appearance/P60/P90
reference probabilities are not identified by aggregate minutes; do not invent them.

**PM primary absolute metric:** CRPS of the original empirical origin-GW point
law. Report xP MAE/RMSE/MSE/bias, haul≥2/5/10 Brier, randomized empirical PIT,
50/80/95%central empirical intervals, their actual discrete forecast mass, width
and realized coverage. Finite400draw forecasts and uncertainty intervals do not
include parameter uncertainty. Original `distribution.p_zero` is **zero minutes**,
not zero points. No reinterpretation is allowed.

PMmean comparator: same-origin official ep_next if archived finite and original
bootstrap is_next matches origin; secondary total_points/N prior season mean
scaled by that player's original origin-fixture count. Missing ep_next never gets
today's value or0. Official point forecast has no published probability law:
no official CRPS/interval/Brier is invented. Probabilistic calibration is absolute
for our law, while comparator claims use matched mean errors.

Per-fixture component means use PR49's canonical additive partition once:
appearance, goals, assists, CS, DC, saves, penalty saves, bonus, GC, negatives.
Goal/assist count means may be derived only with registered season point weights;
count mean errors are valid, occurrence probabilities are not inferred via Poisson.
Qualified-CS award probability=CSpoints/(4GK/DEF,1MID), FWDnotapplicable.
Outfield DCaward probability=meanDCpoints/2; no60minute requirement. Score their
binary official awards. Saves bucket means and bonus means allow point-mean errors,
not full save-count/BPS/bonus probability laws. Missing background BPS, big-chance
save subtypes and event coupling remain NOT_IDENTIFIED; no fabricated scores.

## Uncertainty and claims

Fixed primary comparison family: (1)paired start-log-loss difference versus the
smoothed-start baseline; (2)paired point-MSE difference versus ep_next. Model-minus-
baseline, negative is better. Aggregate rows withinGWthen weight GWs equally.
One final analysis only: paired circular moving-GW-block bootstrap, length3,
seed2026112304,2,000 replicates; report95%CIs and simultaneous97.5%CIs for two
comparisons (Bonferroni family control). Length6is a prespecified sensitivity.
With<12GWs or<120 fixtures no inferential interval or superiority conclusion.
Twelve/16GWs are review floors, not proven power; variance/power is not established.
Small correlated blocks can yield wide/unstable intervals; no player-iid claims.

Practical descriptive reference margins: start log loss .01 nats and point MSE
.10 points²/player-GW; do not promote even if margins/intervals pass. The MMprotocol
and final statistical plan's assumptions and sparse subgroup safeguards still apply.
All other subgroup/calibration/component tests are descriptive/hypothesis-generating,
not multiplicity-free discoveries. No model acceptance or actual FPLpoint claim.

## Separating MM and PM; priority rule

Report minute/participation residuals alongside point/component errors by the
same **predeadline** rotation/availability groups. Rank component hypotheses by
absolute point bias and mean absolute error in the top50/active public cohorts,
with event/support counts. Keep minute-error ranking in minute units separately.
Realized-minute-stratified profiles and residual correlations are exploratory,
not causal attribution: the current archive lacks aligned per-draw component/
minute/goal/BPS ledgers. Do not “correct PM” from an MMexposure correlation.

Before new labels there is no new error ranking. Existing documented risks are
start/duration/P90exposure, team/player goal-allocation, qualifiedCS and DC/bonus
definitions/calibration. Injury-return/specific-save/BPSdependency explanations
remain hypotheses or data-gated. Any later change needs a new isolated protocol.

## Automation and reproducibility

Research-only workflow recovers existing public Release assets using pinned
main d4d6e804archive helpers. It never calls a model/TSworker, app deploy, private
endpoint or substitution pipeline. Reuse official finished-GWingestion snapshots;
only supplement required per-fixture DGWlabels from official history. Report outputs
are content-addressed research reports; no forecast or old result is overwritten.
Workflow remains proposed until this research PR is reviewed/integrated; no claim
of automatic scientific reporting on main merely from a branch test.

Register immutable harness/command hashes before the first capture/scoring run.
Known GW8–10 and synthetic fixtures test infrastructure only; do not rerun their
old audits or describe them as independent validation. Live initial run may verify
archive access, record pending selection/results and publish no score.

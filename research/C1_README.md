# C1 — Scientific Model Research | README & progress checklist

**Owner:** C1 (Codex model research) · **Programme:** FPL Analytics + FPL Research Lab
**Last prepared:** 2026-11-22 · **State:** Stage 0 reconciliation implemented; independent scientific PR review pending; **no new model experiment executed**
**Canonical scientific plan:** [MASTER_PLAN.md](MASTER_PLAN.md) · **Registry:** [experiments/](experiments/) · **Current snapshot:** [STATUS.md](STATUS.md) · **Session handoff:** [SESSION_HANDOFF.md](SESSION_HANDOFF.md)

> **Mission:** Improve *validated* predictive quality and FPL decision value—not apparent historical fit or model complexity. Research is separate from the stable Analytics app. This README is the human-readable checklist, **not** a replacement for the experiment registry, immutable evidence, or append-only decision log.

## A. Start-of-session checklist (every time)

- [x] Read the [root entry point](../MASTER_PLAN.md), [programme plan](MASTER_PLAN.md), [methodology](METHODOLOGY.md), [data catalog](DATA_CATALOG.md), [decision log](DECISION_LOG.md) and [handoff](SESSION_HANDOFF.md).
- [x] Check the *live* GitHub status of PRs **#41 (audit), #42 (follow-up), #45 (programme)**, and separate WIP **#43 (private capture)** / **#44 (app interface)**. **#45 is stacked on #42, which is stacked on #41** as of this document; never assume all have merged into main.
- [x] Run `python research/tools/registry.py validate`, `status`, `next` from a checkout that includes PR #45. Stop and repair registry consistency on failure.
- [x] Locate the exact experiment ID and inspect its JSON, original outcome/score evidence, source SHA, cutoff, prior branch/PR and declared sample. Search the historical inventory **before** creating a new ID.
- [x] Classify the intended task: **inventory / infrastructure / deterministic correctness / retrospective diagnostic / prospective forecast evaluation / stateful TS policy evaluation**.
- [x] Check study prerequisites and whether any proposed new efficacy test has *genuinely untouched* outcomes. Previously seen GW8–10 and reconstructed/reused seasons are not independent confirmation.
- [x] Confirm exact scope, tests, compute budget, write locations and independent branch. Never mix model research with app-interface/C2 work.

Commands to run, once the research branch is available:

```sh
python research/tools/registry.py validate
python research/tools/registry.py status
python research/tools/registry.py next
# Read the individual experiment registration and its source evidence before acting.
```

## B. Permanent rules — non-negotiable

- Never alter frozen **MM B**, **PM vFinal**, **TS v3**, the production app, or the existing preregistered substitution experiment while doing exploratory research.
- **No leakage:** model inputs/estimates must be available by the original FPL deadline and preserved as original issue/publication vintages. Don't rewrite forecasts with observed labels.
- **No duplicate science:** an old test, new chart of the same results, or a rerun on seen outcomes is not new prospective evidence.
- **No false certainty:** thousands of correlated player rows do not equal thousands of independent matches/GWs; account for fixture, GW, temporal and overlapping-horizon dependence.
- Separate **forecast quality** (proper scores and calibration), **mathematical search correctness**, **expected decision utility**, and **realized policy value**.
- Report negative results, missing data, excluded observations, uncertainty and limitations. Never cherry-pick winning subgroups or promote on one p-value.
- Preserve private manager state, user intentions, executions, bank, purchase prices and chips outside public Git, GitHub Pages and public CI; recommendations are not proof of execution.
- Do **not** change the production model pointer or deploy from Research Lab. A new model needs a separate reviewed integration PR with rollback.
- Do not spend substantial compute, introduce new model families, change primary metrics, or tune hyperparameters unless a specific preregistered protocol and its gates permit it.
- If a prerequisite fails, **record 'blocked' with the exact failure and preserve unfinished work**; never manufacture input or call a partial test release-ready.

## C. Programme scoreboard — tick only after objective completion

**Legend:** `[ ]` outstanding; `[x]` verified completed with source link; an experiment can be *ready* scientifically while its harness is not implemented.

### Stage 0 — Historical reconciliation **implemented; independent review pending**

Original programme registration: **25 unchanged entries**; Stage 0 appends **38 missing historical entries**, for **63 total**. This is coverage, not independent trial count. Audit inventory references approximately **178 study directories / 2,471 files** and **236 test files**; these are not counts of independent experiments.

- [x] Scientific master plan, registry and programme architecture **authored** in PR #45 (11 registry tests reported passing; this is planning, not full model certification).
- [x] Reconcile *distinct* historical hypotheses against **all relevant prior PRs, branches, audit result directories, evidence inventory and tests**. Group copies/parameter variants without double counting.
- [x] For each substantive previous study record: original question; tested MM/PM/TS configuration; baseline; original vs reconstructed cutoff; train/dev/test periods; population; metric; numerical effect and uncertainty if available; whether outcomes were already seen; decision; original evidence path/SHA.
- [x] Produce a **deduplicated historical matrix**: accepted / rejected **in that exact configuration** / inconclusive / exploratory / untested / blocked.
- [x] Flag missing historical registrations and append new *evidence-linked* records when necessary. Do not change original decisions or count variants as independent holdouts.
- [x] Create a **gap/dependency matrix**: what can be measured now; what needs valid captures; what requires new GW; what cannot currently be identified.
- [x] Review and justify research priority across **TS search**, **prospective MM**, **PM data definitions**, **TS stateful policy**, model limits and external benchmark.
- [ ] Update `research/SESSION_HANDOFF.md`, status and append-only event/decision history with the actual inventory outcome. Submit a **separate research PR**; do not begin new model tuning.
- [ ] Independent review confirms no high-impact prior test is incorrectly labelled a new discovery.

**Stage-0 definition of done:** every proposed new model experiment can be matched to prior evidence, or explicitly marked genuinely novel, before execution.

**Evidence:** [decision report](stage0/REPORT.md), [historical matrix](stage0/HISTORICAL_MATRIX.md), [184-directory matrix](stage0/directory-matrix.csv), [gap/novelty matrix](stage0/GAP_MATRIX.md), [verification](stage0/verification.json). All 2,471 original source hashes match; 236 test paths exist (model tests not rerun); 225 primary artifacts retained. No model/app/protected-trial changes. Deterministic self-checks do not satisfy independent scientific review.

### Stage 1 — TS v3 **search correctness** (registry: `EXP-TS-SEARCH-001`)

- [ ] Read the registered fixed experimental domain and exact frozen scorer; do **not** change horizon discount, buffer, search parameters or chips policy.
- [ ] Implement independent exact finite-domain oracle; include manually checkable witness cases.
- [ ] Respect registered bounds: **30 deterministic legal instances**, **12 restricted DNP/nomination instances**, **player pool ≤17**, **≤2 transfers**, **≤8 scenarios**, **120-second initial budget**.
- [ ] Measure legal-action violations, scoring disagreement and *all* heuristic utility gaps. A restricted nomination optimum is not a global FPL optimum.
- [ ] Record reproduction command, source/input/output hashes, runtime, failed instances and clear limitations.
- [ ] Update registry and handoff; choose a *new* follow-up hypothesis only if evidence warrants one.

**Exit gate:** zero illegal/scoring mismatches on the declared witnesses and an honest quantified search gap. This does **not** certify TS's real-season gain.

### Stage 2 — MM **independent predictive quality**

- [ ] Maintain old substitution trial `EXP-MM-SUB-20261108` **unchanged**: **8 new completed GW / 80 matches**, original cohort/cutoffs/metrics; do not count the old 20 matches.
- [ ] Complete original-vintage collection gates before `EXP-MM-LIVE-001`; earliest newly registered holdout origin **GW12 or later**, with **12 new GW / 120 matches** review floor.
- [ ] Score starting probabilities, bench appearance, minutes conditional on start/bench, expected minutes, P60, P90 and full minute distribution with each target defined exactly.
- [ ] Use proper Brier/log loss/distribution scores for predictive claims; MAE, RMSE and bias as applicable diagnostics; reliability by prespecified subgroups.
- [ ] Compare identical players, fixtures, time cutoffs and same-outcome vintages; report paired GW/block uncertainty and a practical minimum effect.
- [ ] Only then preregister *new* conditional MM ablations that demonstrably differ from previously tested role, workload, return, Europe or P90 adjustments.
- [ ] Verify downstream PM/TS safeguards before recommending any promotion.

**Exit gate:** reproducible independent evidence, not attractive old GW8–10 fits.

### Stage 3 — PM **target definitions before changes** (`EXP-PM-DEFS-001`)

- [ ] Define a versioned event dictionary for team goals, goals credited to players, FPL assists, actual reported minutes, CS eligibility, DC, saves, background/action BPS, bonus allocation and missingness.
- [ ] Reconcile rules/targets and quantify coverage using PR #42; **no double counting** and no post-outcome data for deployable forecasts.
- [ ] Distinguish team-level CS from on-pitch qualified CS; mark unobserved save/BPS subtypes unknown rather than zero.
- [ ] Preserve original MM forecasts for end-to-end PM evaluation; observed-minute and observed-goal studies are **oracle diagnostics only**.
- [ ] Register any later PM candidate separately with a held-out evaluation plan and downstream safeguards.

**Exit gate:** known event identities reconcile, unknown data are explicit, and a new PM experiment is statistically identifiable.

### Stage 4 — TS **decision value** (`EXP-TS-POLICY-001`)

- [ ] First obtain lawful, timestamp-valid full six-GW forecasts and genuine private manager snapshots, recommendations, intentions and **verified actual executions**.
- [ ] Check per-origin prices, bank, purchase/sale prices, FT carry, chips, captain, vice, legal XI and substitutes; never equate predicted decisions with executed ones.
- [ ] Compare no-transfer, simple one-GW/greedy and frozen TS v3 in **stateful** counterfactual trajectories using the same original information.
- [ ] Separate search gaps, forecast error, decision utility and realized net points; use nonoverlapping origins or valid blocks for overlapping horizons.
- [ ] Only after baseline validity, preregister horizon/discount/hit-buffer/risk/chip sensitivity in development sets, with untouched prospective confirmation.

**Exit gate:** documented net FPL value with realistic uncertainty; missing six-GW or private execution data means 'Not Available'.

### Stage 5 — Model limits and competitors

- [ ] Pursue `EXP-LIMITS-001` with explicit information sets, conditional uncertainty, learning curves and carefully labelled oracle diagnostics. **Never claim a percentage of theoretical optimum** without an identified denominator.
- [ ] Pursue `EXP-EXT-XP-001` only with provider rights, original timestamps, matched player IDs/definitions and comparable GW cuts. No invented LazyFPL/FPL Review ranking.
- [ ] Distinguish a small statistically detectable improvement from meaningful impact on FPL choices; report limitations and computing cost.

### Stage 6 — Release qualification and permanent GW learning

- [ ] Record model-specific primary metrics, subgroups, calibration, uncertainty, source/code hashes and a locked rollback candidate.
- [ ] Obtain new independent evidence and verify PM/TS downstream impact before proposing a production change.
- [ ] Hand model candidate + exact adapter/forecast contract to C2 via **separate integration PR**, never modifying app code from C1.
- [ ] Once operations are verified, consume each *new* final GW as an immutable evaluation, update results and negative findings without retuning to that GW.
- [ ] Maintain a readable status/dashboard that makes blocked or low-power research visible rather than hiding it.

## D. Existing research — **do not rediscover as new results**

| Prior evidence | Takeaway and boundary |
| --- | --- |
| PR #41 and #42 GW8–10 | 2,007 player observations / 30 matches; first historical MM/PM audit; **already seen** outcomes. |
| `LEGACY-001` | MM checkpoint designation, **not** independent evidence of live superiority. |
| `LEGACY-003` | Hierarchical goal/assist allocation not promoted after worse nonbonus RMSE in tested configuration. |
| `LEGACY-004` | High-xP budget change helps a subgroup but harms aggregate RMSE. |
| `LEGACY-005`, `LEGACY-015` | Keeper-quality gains small/uncertain and not active production proof. |
| `LEGACY-006` | Europe-rotation candidate rejected for its evaluated configuration; time provenance partly incomplete. |
| `LEGACY-007` | Injury/news caps can violate XI unless coherently reprojected; oracle not deployable. |
| `LEGACY-008`, `LEGACY-009` | Historical TS proxy and 2,125-point reproduction **do not** certify present full 6-GW/chip TS; only 33/183 needed origin/target pairs in old coverage. |
| `LEGACY-010` | GW6–8 retrospective replay with later-selected policy; not prospective. |
| `LEGACY-012` | Starter-duration integration benefit small/mixed; old reconstructed cohort. |
| `LEGACY-013` | Blind P90 rescaling rejected; physical 5-subs support must hold. |
| `EXP-MM-SUB-20261108` | Protected, still awaiting new complete observations in last recorded status. |

This table is **an index, not proof of exhaustive coverage**. Stage 0 must verify the source inventory and append missing distinct studies without overwriting these conclusions.

## E. Exact end-of-session checklist

- [x] Run registry validation and relevant deterministic/regression tests; include actual commands, pass/fail counts and any unrun suites.
- [x] Save original scripts/code SHA, input hashes, forecast vintages, fixture rules, coverage and result file hashes.
- [x] Report effect size in natural units with valid uncertainty where inferential; report deterministic search witnesses without inappropriate p-values.
- [x] Record all attempted experiments (including failed, null and blocked); don't cherry-pick.
- [x] Append dated registry events and decision log; explicitly regenerate status and handoff. A GitHub checkbox is **not** the official experiment state.
- [ ] Open a *single bounded* research PR with evidence, remaining blocker and next valid action.
- [x] Leave production models and C2 integration branches untouched.

## F. Ownership and handoff to C2

**C1:** research inventory, statistical studies, reproducible MM/PM/TS evidence, controlled candidate recommendations.
**C2:** stable live app, canonical manager data, deploy, model adapters and PWA experience.
**Boundary:** C1 may produce a validated candidate and a versioned contract, but **C2 alone integrates it via reviewed PR**. Neither C1 nor public GW reports can automatically promote a model.

### First prompt at next C1 availability

> Read the latest Stage-0 PR review and `research/stage0/REPORT.md`, `GAP_MATRIX.md`, `SESSION_HANDOFF.md`; verify registry/source receipts. Resolve independent novelty review before the next model experiment. Do not repeat the six old one-GW TS enumeration cases or the TSv4 MILP/enabler tests as new. The remaining `EXP-TS-SEARCH-001` gap is the unchanged current scorer in its registered finite domain; preserve all original bounds and register the harness before execution. A new session needs scope authorization for Stage 1; this Stage-0 session executed no model experiment.

**Important:** This checklist reflects the 2026-11-22 programme state. When resuming, verify *current* source branches, test status and new original-vintage GW receipts before ticking any box.

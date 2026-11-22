# EXP-TS-SEARCH-001 — implementation fixed before execution

22 November 2026; separate branch from PR47 at089bc44c. This supplements, **never edits**, the original registration. No outcomes, manager records, forecasts, model fits or new model parameters are acquired. All42 inputs are synthetic and written before calling any planner/oracle. No candidate selection or result-driven instance editing.

## Novelty and review

The scoped methodological review6013306012 in PR47 confirms a narrow residual question. LEGACY-040 already did six one-GW ≤2-transfer enumerations using heuristic nominations per alternative squad and buffer1.5. LEGACY-044 audited accounting and warned of negative enabler pruning. LEGACY-045 built a different joint MILP with only GW1 smoke and enabler/FT unit tests. None proves an exact current shared-PM six-GW optimum. This study does not rename those findings as new. The overall Stage0 scientific review remains pending; only the TS-overlap question was reviewed. Current user explicitly authorizes this study.

## Frozen target identity

Pin:`161b67b6fb8786a38e78c245b92a03ad841575d8`.
Target:`transfer_planner.plan_transfer_path` inside the exact `b_preview_ts.preview_scoring` context used by `service/preview_manager_job.py`. It replaces scalar scoring aliases with the unchanged `ScenarioScorer.decision`, as in that worker. This is the B-chain scorer, **not** the separate unpatched locked-manager mean/p_play approximation. Inputs contain aligned finite points/minutes arrays; no PM simulation occurs.

Load the actual frozen `run_joint_fh_wc_stopping_replay.cfg()`; all its fields must match the source manifest. The numerical objective is

`sum_g weight[g] * E[ordinary XI + legal autosubs + captain fallback] - 4*paid[g] - 1*paid[g]`.

Weights are exactly`(1,.60,.36,.216,.1296,.07776)`. Deterministic hits and the original buffer are **undiscounted**. Keep beam20, local beam60, target18, return12, backend fast_local and the original max5 transfers/GW unchanged. The finite pool≤17 means two15-player squads necessarily differ by≤2incoming players, so the original parameter need not be altered. No chip/free-hit bridge; original chip-free planner domain only.

`source-manifest.json` checks all532 Python source files in src/scripts/service before use. Imported entry points must resolve to the pinned checkout. Original sources and all experiment protocols remain immutable. Synthetic contract fields establish only internal consistency of these artificial arrays, never a claim that an MM/PM forecast was validated.

## Exact feasible domains

All cases cover six hypothetical GWs with frozen prices, club/position eligibility and a15-player initial squad. Every candidate XV has2GK/5DEF/5MID/3FWD,≤3per club, nonnegative bank and≤2incoming players per step. An action is a simultaneous net bundle (any negative-value enabling leg allowed). Bought players cost current integer-tenths price; old holdings retain purchase price until sold. Profit halves by floor; price falls realize the current price. FT evolves as`min(5,max(0,FT-transfers)+1)`; paid transfers=`max(0,transfers-FT)`. No terminal FT salvage, matching TS. All future states are hypothetical and only first action would be executed in real operation.

- **30 deterministic cases:** pool17, one all-play scenario,5fixed families×6FT/bank variations. Exhaustive legal XV and XI, both keepers, all formations, C/VC and bench orders. Since every player plays, captain is the maximal starting payoff and vice/order do not affect points. Vectorized enumeration over every legal XI evaluates`sum(XI)+max(XI)`; it does not greedily restrict formations or transfer candidates. Fixed families: negative-value funding legs; time-varying future gains/FT carry; historical purchase-price profit; club-limit restrictions; zero/negative individual legs.
- **12 DNP cases:** pool15,8aligned scenarios;4dependence families×3variations. Exactly3predeclared legal XI per case, all6outfield bench orders, all110distinct starting C/VC pairs =1,980nomination choices/GW. No transfers possible because pool=15. Captains separate additively from bench points, so every pair is evaluated once/XI and every bench permutation once/XI without enumerating their product repeatedly. Verify the frozen heuristic choice is inside the declared menu; otherwise mark invalid comparison, do not expand the menu. There is no claim of a global nomination optimum outside these menus or stochastic transfer optimality.

Inputs are interleaved5deterministic +2DNP per block so a timeout remains visible across both levels. FT0–5 and initial bank variations are synthetic boundary probes, not private manager states or representative frequencies. Current cap5 is retained on rollover.

## Independent exact method and scorer separation

Enumerate every legal XV from the finite pool. Dynamic programming retains **every** reachable `(owned IDs + purchase prices, bank, FT)` at each GW, keeping the best accumulated value for identical states. No beam, candidate-value pruning, MILP, heuristic shortlist, observed scores or learned fit. For this finite Markov state, future rewards/feasible actions depend only on that state and GW, so dominance elimination is exact. Enumerate all legal net bundles between squads; transitions/FT/hits/sale prices are implemented independently, not imported from TS.

Compute two references with the same six-GW state law and frozen utility:

1. Exact transfer paths **with unchanged heuristic nomination scores**. Its gap isolates transfer/path search within this domain.
2. Exact paths **with exact domain-specific nomination scores**. Its gap is the total joint search gap. Also report extra nomination opportunity and nomination gains along the heuristic path; do not confuse those decompositions.

Arbitrary nominated lineups are valued by the **original imported `autosub_points`** and the same per-scenario captain/vice bonus as ScenarioScorer. The separate independent scalar rule calculation enumerates matching absent nominated slots to eligible substitutes and checks legal formations. It audits those scores but never replaces them in either objective. If a mismatch occurs, report a scorer disagreement separately; do not certify correctness or replace the objective with the independent law. Captain fallback and path objectives are independently recalculated. Cached scores are deterministic integration over the input arrays, not new Monte Carlo draws.

## Hand-derived witnesses fixed before run

- Original D01 squad: optimal all-play XI base78, captain12, total90/GW. The cheap DEF16 (2points instead of outgoing DEF3's6) releases30tenths to fund MID17 (20points). MID inclusion adds14XI points, captain adds8, defence loses4: optimal daily score108. Initial FT0 means2paid transfers cost10. Immediate two-transfer joint path scores`108*2.38336-10 =247.40288`. Delaying any gain oneGW saves at most5 but loses at least18in the first GW; prices are fixed. This is a predeclared check of the exact full path, not a newly discovered enabler mechanism.
- Primitive two-scenario captain/autosub test: nominated base13 + reserve1 + vice4 =18when captain is absent; nominated23 + captain10 =33when present, mean25.5. Independent scalar test must match.
- Exactly3DEF nominated, one absent: a MID reserve cannot replace the third DEF; next eligible DEF fills it. Half-profit examples:`sale(50,61)=55`, `sale(50,62)=56`; price fall:`sale(60,49)=49`. FT5kept remains5; two transfers fromFT0 mean8official hit points+2buffer regardless of future GW weight.

## Budget, registration and failure handling

Run one fixed42-case suite with an initial **120-second total process wall budget**, including numerical imports, source checking, heuristic calls, exact references and checkpoints. A SIGALRM interrupts the remaining budget; partial results are saved, unfinished/current cases identified. No automatic budget expansion or selective rerun. The initial implementation and exact reproduction command must be recorded in the append-only registry before execution. The original protocol JSON is not changed. Preparation, primitive unit tests and offline artifact verification are reported separately; they do not run extra TS-suite instances.

Preserve all case outputs, including failures, positive gaps, menu/support failures and blocked/timeout results. Output runtime/environment, protocol/input/source/implementation hashes, state/nomination counts, complete selected paths, illegal-action counts, scorer mismatches, both gaps and all limitations. Deterministic finite-domain study: no p-values, confidence interval or realized-FPL-gain claim. A successful test cannot certify the whole app, chips, unbounded squads, real-data representativeness or a season policy.

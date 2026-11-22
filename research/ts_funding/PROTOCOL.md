# EXP-TS-FUNDING-001 — locked prospective synthetic comparison

Registered 22 November 2026, before new-instance generation or evaluation.

## Novelty and fixed candidate

LEGACY-040 enumerated six one-GW historical cases with another configuration;
LEGACY-044/045 already documented negative funding legs and MILP enablers.
PR48 measured the current six-GW loss, not a repair. This study tests the
isolated `candidate.py` supplementary-pair proposer against new finite domains.
It retains every original proposal, adding at most the existing per-depth return
cap (12) of affordable, position/club-legal simultaneous two-transfer bundles.
One leg must have negative weighted individual value and release cash; the
positive leg must be unaffordable alone; their total weighted gain must be positive.
Sort by gain, then bank, then IDs. No baseline-versus-candidate fallback, beam
change, new target pool, scorer, weights, hit buffer or production integration.
Union proposals do NOT guarantee end-to-end non-regression under beam truncation.

## Data separation and finite reference

The known 42 PR48 cases are development/regression only. Run the candidate on
them against archived baseline/exact values; do not count these as confirmation.
Freeze candidate, generator and harness before generation of the holdout.
No adjustment after holdout inspection; any future revision needs another study.

New holdout: 48 cases, six families × eight seeds, pool17, two extra players
in distinct randomly selected positions, six GW, FT0–5, bank0/5/10/20.
`generate.py` fixes seed202611220317 and independent, fixture-window,
club-exchange, sale-rounding, correlated-absence and near-tie families.
It never reads the old fixtures. Each uses independently generated integer
payoffs/prices, not modified old witnesses. These broad random domains need not
contain a funding opportunity: lack of coverage is a reportable limitation.
One aligned scenario except eight in correlated-absence. Synthetic point values
are accepted scorer inputs, not certified physically realizable FPL event laws.

Use frozen source161b67b6 and the complete original worker configuration/hash
manifest from PR48. Independent exhaustive DP reuses PR48 `reference.exact_path`,
enumerating all legal XV and purchase/bank/FT states over six GW, ≤2 net transfers
per week, with **frozen ScenarioScorer nominations** on each XV/GW. This is exact
only for transfer paths conditional on that nomination policy and finite pool.
It is NOT globally optimal XI/captain/bench, FPL or full stochastic optimization.
The same nomination policy/scorer applies to both arms and reference. Independently
audit all finite-domain nominations and all returned paths with existing scalar
scoring, sale/FT/hit transition and legality checks, including C/VC and bench.

## Endpoints, gates and budget

Primary: paired `baseline_gap - candidate_gap`, where gap=exact minus arm utility;
report every case, mean, median, range, family totals and regressions. No p-value
or population confidence claim for deliberately finite synthetic witnesses.
Secondary: runtime per arm, illegal decisions, scorer disagreements, complete
six-GW paths, gap remaining, reachable reference states and transition counts.

Practical research gate (not production acceptance): zero illegal/scorer errors,
all48 complete, no worsening beyond1e-9, positive mean improvement >1e-9 in at
least two families, candidate total planner time ≤2× baseline and mean candidate
planner time ≤2seconds. A failed gate is a result, never grounds to tune/retry.

Budgets: development120seconds; holdout240seconds including reference,10seconds
per case, first attempt only; no extension. Each phase checkpoints all failures
and not-run cases. Timers start before loading numerical source and computing.
No production-scale runtime claim; no extra scalability experiment in this study.

## Practical relevance and capture audit

Synthetic improvement is search evidence only. Realistic frozen-forecast gains
require genuine original forecasts plus legally available relevant private
states; realized-point gain requires a separate prospective/stateful protocol.
Do not fabricate state evidence or infer realized gains from these payoffs.
TaskB is read-only inspection of existing public artifacts, source and workflows,
with timestamp/hash/identity/horizon field coverage and specific C2 requirements.
No new collector, private payload access, model change, trial change or deployment.

## Reproduction

`OPENBLAS_NUM_THREADS=1 /workspace/fpl-venv/bin/python research/ts_funding/run.py --frozen-root /workspace/work/fpl-ts-frozen-161 --phase development --out research/results/EXP-TS-FUNDING-001/development`

Then identical command with `--phase holdout --out research/results/EXP-TS-FUNDING-001/holdout`.
Both require immutable implementation registration and running state before the
first execution. Offline tests verify archived results without rerunning models.

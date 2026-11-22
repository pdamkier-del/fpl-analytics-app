# TS funding pairs — finite-domain research decision

**22 November 2026 · EXP-TS-FUNDING-001 · completed; practical gate FAILED.**

The isolated candidate improves search on two of48new synthetic cases and
closes all11known development failures. It is **not ready for production**:
new improvements occur in only one family, failing the preregistered two-family
gate, and four new cases still have a positive gap to the finite reference.
No production source, app, substitution experiment, weights or scorer changed.

## Locked comparison and novelty

Candidate, generator, reference adapter, endpoints and budgets were committed
at`f5fd8975` **before either run or holdout generation**. Registry events85–87
record registration/implementation/running; original63protocols are unchanged.
See [protocol](../../ts_funding/PROTOCOL.md), [manifest](implementation-manifest.json),
[new raw cases/results](holdout/) and [development results](development/).
No tuning, second attempt, case exclusions or budget extension followed results.

LEGACY-040/044/045 already contain enumeration, funding/enabler and MILP work;
PR48already measures original TS search loss. This study's new evidence is the
separately locked candidate-versus-baseline comparison on new generated domains.
The old42cases are explicitly development/regression, with their archived
baseline/reference reused rather than rerun or counted as independent evidence.

Candidate adds at most12 legal affordable simultaneous funding pairs to the
original proposal list: a cash-releasing individually negative leg finances an
otherwise unaffordable positive leg; their joint weighted individual gain must
be positive. Existing target pool, outer beam, return cap value, weights,
undiscounted hits/buffer and shared-PM scorer are unchanged. It can still prune
useful bundles; retaining original proposals is not a theorem of beam non-regression.

## All outcomes

| New family | Cases | Improved / worsened | Baseline gap sum | Candidate gap sum |
| --- | ---: | ---: | ---: | ---: |
| Independent random profiles |8|0 /0|0|0|
| Nonmonotone fixture windows |8|2 /0|8.95744|4.25184|
| Simultaneous club exchange |8|0 /0|0|0|
| Purchase/sale rounding |8|0 /0|0|0|
| Correlated absence, eight scenarios |8|0 /0|0|0|
| Near ties / controls |8|0 /0|0|0|
| **Total new holdout** |**48**|**2 /0**|**8.95744**|**4.25184**|

Mean paired gap improvement **0.0980333 weighted synthetic utility**, median0,
range0–3.576. H2-04 improves1.1296 (remaining gap0.61344); H2-05improves3.576
(remaining0.72). H2-01andH2-06remain unchanged with gaps0.7296and2.1888.
The other44match the reference within1e-9. These are finite illustrative counts,
not a representative FPL error rate, uncertainty interval or real-point gain.
All cases, including unchanged and residual failures, are in
[holdout-cases.csv](holdout-cases.csv) and [summary](holdout-summary.json).

Development: candidate closes all11archived deterministic misses;42/42complete,
zero worsening, mean gap reduction11.80946, all final gaps0within tolerance.
This confirms the known mechanism only; it is not new confirmation of efficacy.

**Safety/accounting:** no illegal transfer/state/nominations or scoring
disagreements found; both holdout arms return all sixGW,576actions checked.
5,802finite-domain nomination/independent-scalar checks in holdout and5,328in
development cover XI/C/VC/bench/autosubs. Independent path replay checks club/
position eligibility, budget, purchase/sale rounding, buyback purchase prices,
FTcarry/cap, hits, buffer and total utility. This is tested coverage, not a proof
against all FPL rule/event edge cases. No active chips are studied.

## Compute and the failed acceptance gate

| Measurement | Result |
| --- | ---: |
| Development wall time / cap |6.0121s /120s|
| New holdout wall time / cap |12.4075s /240s|
| Slowest complete holdout case / cap |2.5348s /10s|
| Baseline planner total / mean |1.90562s /0.03970s|
| Candidate planner total / mean |1.98970s /0.04145s|
| Candidate/baseline planner time |1.04412×|

Completion, zero-errors, no-regression and runtime gates pass. **Positive mean
improvement in at least two families fails (one)**. Do not dilute that gate after
seeing results. Baseline runs first on the same scorer cache, so timing is a
single-run operational diagnostic, not a randomized speed benchmark. Small-pool
speed does not establish runtime at a real600+player pool; pair enumeration and
extra outer-beam pressure require a separately registered production-scale probe.

## Exactness and remaining identification

Independent reused DP enumerates all legal XV and every reachable purchase-price/
bank/FTstate over sixGW in each17player pool; net incoming≤2perweek,≤8scenarios.
It uses the **same frozen scorer's nomination policy** as both arms, with independent
scalar score/transition cross-checks. Thus exactness is conditional on that policy,
the pool and no chips: no claim of global joint nomination/FPL optimality.
Original six weights and source161b67b6are hash-verified in both runs.
Synthetic integer payoffs are scorer inputs, not certified football-event laws.
The reference retained at most7,340 states in a layer and evaluated602,190
transitions across the48new cases, without the TS beam or candidate proposer.

Remaining fixture-window gaps show the minimal funding rule does not solve
general time-dependent search. They may involve the original positive-value
filters, target proposal ranking or beam/path truncation; **no ablation here
identifies their separate causal contributions**. No new scorer bug was found
in the declared checks. Five families have zero baseline gap, limiting evidence
of cross-family benefit; do not add hand-picked winners to this holdout.

## Practical evidence and next decision

1. **Constructed search:** a small measured improvement on new instances; broad
   preregistered practical gate failed. Keep candidate isolated, not promoted.
2. **Realistic forecasts/states:** not evaluated. Public forecast exists, but
   genuine relevant private states and durable original-vintage gates are not
   demonstrated. [Capture audit](../../ts_funding/CAPTURE_AUDIT.md) gives verified
   field coverage, failed jobs, artifact-witness limitation and exact C2deliveries.
3. **Realized FPL:** no estimate. Requires separately registered prospective or
   valid stateful comparison, complete prices/FT/chips/executions and overlapping-
   horizon uncertainty; synthetic utility cannot supply it.

**Next research recommendation:** preregister an independent, broader finite-domain
confirmation of this unchanged candidate, with prespecified time-varying transfer
opportunities and production-size runtime probes. Treat all90cases here as seen;
do not tune on the two winners or relabel development as test. First characterize
residual search gates independently; no new optimizer/model family is required.
That can start without private data, at a separately fixed compute budget.
In parallel C2should certify existing original-vintage/private capture; only then
can a distinct frozen-real-input decision-utility study start. PM's prospective
DCrecommendation from PR49remains valid and unchanged, awaiting its own protocol.

Expected next cost:1–2engineering days for new finite-domain/probe design (estimate);
real-state efficacy is calendar/data gated. This completed study is not accepted
model evidence; independent code/result review and production integration remain
separate. Offline verification command:

`OPENBLAS_NUM_THREADS=1 /workspace/fpl-venv/bin/python -m pytest -q research/ts_funding/test_funding.py research/tests research/stage0/tests research/pm_defs/tests research/ts_search/tests`

**Verification:**65tests pass. Existing registry-count and Stage0historical-import
tests were generalized only to allow the new64thnon-legacy protocol; historical
evidence, original registered harnesses and all63existing protocol bytes remain
unchanged. The research diff contains only`research/`paths. No optimizer was
rerun by the offline tests. Test/code/source hashes are in`test-receipt.json`.

# EXP-TS-FUNDING-REALPOOL-001 — preregistration-ready protocol v1

23 November 2026. **DRAFT FOR NEXT TASK: no execution harness registered, no cases generated, no numerical evaluation authorized by this planning delivery.** One study only. Reserve this ID; append a new formal experiment registration once the implementation/source manifest is frozen and before generating any evaluation state. Do not reopen or change EXP-TS-FUNDING-001. Record implementation/command before running. Review any unresolved adapter issue before that freeze; do not silently change the design after results.

## 1. Question, estimand, novelty

Does the **unchanged PR50 funding-pair candidate** deliver practically useful improvements in the existing six-GW TS utility, at feasible runtime, when given an original real full player-pool forecast and new synthetic legal manager states?

For each fixed state s and fixed issue F, Δ(s)=U_F(candidate(s))−U_F(TSv3(s)). Primary endpoint: equal-state arithmetic mean Δ across all12 prespecified states, in **original weighted utility units**. Secondary: per-state/stratum Δ, negative/zero/positive counts, keep deltas, legality/replay differences, timeout/coverage, runtime and peak RSS. No primary optimum gap: no certified full-pool optimum exists.

PR48's42 and PR50's48 cases are seen development/regression only. LEGACY-040 one-GW enumeration, LEGACY-044 accounting, LEGACY-045 MILP and PR50 finite-pool reference are reused knowledge, not this study's contribution. New information is the original400-draw/full-pool computational and conditional utility behavior on previously ungenerated states. Same issue means12 states are **not12 independent future GWs or representative manager samples**. Do not compute a population p-value/CI from those states or draws. No claims of calibrated football forecasts, optimality, actual manager value or realized FPL-point gain.

## 2. Fixed input; firewall against PR54 validation

Use exactly the original public Release:

`fpl-forecast-2026-27-gw12-f54f651ea03ee099ef5be35c9cb36eddc3a8472470ead2aaac786b097c281633`

Canonical forecast identity `4d1a2e3925d5da64bfdfa2f7f98a9b7a04ade220f3546f655e4bc4a7ca1051dd`; original forecast.json raw-byte SHA256 `8f80f07829f3dff4dd5eeff70cde5d5ee1065fb7610aa108a14da83744f4eab7`; gzip SHA256 `0f3bc1aa31d183d6a0dcb96e5b4b3a0d306e89342a2654460a26bfbb9d59de94`. Pinned C2 runtime `d4d6e8046ad5d965cf41f5a8fce2b32a49fca16c`, source161b67b6, horizon12–17,400 original aligned shared scenarios. Remaining asset hashes are already fixed in `research/results/EXP-MM-PM-LIVE-SETUP/archive-link-proof.json`.

This issue was already inspected for infrastructure and is explicitly **ineligible for PR54's new prospective cohort**. Its football-input values are known development context; only the newly frozen state generator and its ungenerated cases form this study's test set. Conditional search/runtime testing does not require unseen football outcomes. Use no GW12+ actual results, PR54 eligible issues/scores, later prices, live injuries or current bootstrap. Never evaluate realized points in this study. All prices/IDs/availability come from this same original issue/bootstrap. No network outcome endpoints in the harness.

Full-pool gate: retain every forecast player with valid six-GW original scenario/price/club/position data; require at least500 unique IDs. No top-K truncation of input, reduced draws, horizon changes, imputed missing scenarios or newly simulated payoffs. Existing TS internal target/beam pruning stays exactly frozen; full input is not exhaustive full-pool search. Validate IDs, six-GW alignment,400 samples and pinned C2 original checksum contracts. If a gate fails, BLOCK; do not substitute a later issue.

## 3. Arms and source/configuration freeze

A: original frozen TSv3 at `161b67b6fb8786a38e78c245b92a03ad841575d8` and exact original archived TSconfig.

B: same worker/planner with **only** `research/ts_funding/candidate.py` from PR50 head `c896d16e6f07c975f434c45b49a0649ad8af25d3` enabled by its existing context manager. Pin candidate bytes in the implementation manifest. Do not add a fallback to baseline, change supplementary-pair caps, target pool, beam, weights, hit buffer, scorer, risk law or max-transfers. Reuse existing legality, state replay, scalar nomination audits and objective accounting. C: keep-squad control over the same six GWs with the same frozen nominations/scorer, no voluntary transfers; diagnostic only.

An archive-to-worker adapter may rename/restructure original data only if a non-evaluation contract fixture proves unchanged numerical arrays, draw identities, model fields and scorer agreement. If original worker inputs cannot be recovered losslessly, BLOCK. No new model, event simulation or surrogate scorer. Freeze adapter, generator, dependency versions, source hashes, execution command and deterministic non-evaluation test fixtures before generating the12 states. Do not modify the candidate in response to this study.

## 4. New test states — deterministic construction, no winner selection

Four fixed strata: (FT,bank in £0.1m)=(1,0),(1,10),(2,0),(2,10), three states each. Stratum j=0…3 in that order; replicate k=0…2. RNG `numpy.random.Generator(PCG64(202611230501+3*j+k))`; record NumPy version, generated cases and their checksums. IDs sorted ascending before sampling; positions GK,DEF,MID,FWD, sample2/5/5/3 without replacement uniformly within each position. Sort sampled IDs for canonical roster. Reject if >3 per club, duplicate previously accepted roster, or sum market purchase prices+bank>1000 (£100m). Purchase price=current original market price for all owned players, so no invented profit ledger. Club/position/current prices must be fully identified.

Eligible *owned* sampling frame additionally requires original origin-GW P(play)≥0.20. If multiple fixture marginals, use P(any play) directly from original aligned GW minute draws (>0), never independent-product approximation; for one fixture use that fixture's archived native P(play). Blank-origin players cannot be owned in this stress population. This ownership frame uses forecasts only and does not restrict the planner's full incoming-player pool. No original xP ranking or inserted premium/funding winner is used. This is an ex-ante active synthetic population, not observed managers.

At most10,000 draws per state; failure is reported, with no replacement case/stratum/seed. Fix all chips unavailable/inactive, because this study tests ordinary transfers only. Six-GW bank/purchase/sale/FT/hit transitions use original rules/config. Generate and commit all12 state files in one batch before any arm runs; no inspection of gain opportunities or post-generation exclusions. Family labels are resource strata, not independent replications. Three replicates per stratum are finite stress coverage, not a power calculation.

Development may inspect the90 already-seen finite cases and original schemas offline. No new family designed around the two PR50 winners, no rerunning those cases as independent evidence, no numerical evaluation on the12 planned states during implementation development.

## 5. Execution, replay and fixed compute budget

Single CPU, one numerical thread, no parallel arms; record host/CPU/RAM/Python/dependencies.12 pairs in increasing case ID. Odd case IDs run A then B; even run B then A; each arm fresh process/cache. Both see identical original bytes/states/scenarios. Time from process start (including imports/preparation) to retained output; report planner-only time separately. Preparation and fixed scorer cache cannot leak from the first arm to the second. Record peak process RSS.

Cap **120 wall seconds per arm** and **3,600 wall seconds total**, including archive load, state construction, control, audits and all arm subprocesses. No numerical retry or budget extension. Kill a timed-out arm; retain checkpoint/error and continue only within total remaining budget. Report all12 cases, including not-run/missing/failed. Incomplete primary mean is unknown, not zero or a successful complete-case estimate. No interim efficacy stopping. A transport/contract failure before numerical execution is BLOCKED, not a candidate failure or permission to switch input.

Replay each returned six-GW path independently using the existing verified transition audit: positions, club cap, unique XV, formation, C/VC/bench, buy/sell price rounding, cash, FTcarry/cap, hits and original objective. Audit nomination sample scores with the existing scalar law. Recompute final path utility with the **same frozen scorer**, in declared order; differences >1e-8 are discrepancies. Positive Δ can result from path search, negative Δ from changed beam pressure; legality/scorer disagreements must be separated from search outcomes. A future adapter discovery does not authorize a model fix here. No active chip claim.

## 6. All-of practical feasibility gate; not promotion

Pass only if:

1. All12 paired arms, controls and replay audits complete within budget; zero invalid decisions, input mutations, score/utility disagreements >1e-8 or missing six-GW paths.
2. Mean Δ≥**0.25 original weighted utility**, at least3/12 states improve by >1e-8, with positive improvements in at least2 of4 fixed resource strata.
3. **No state worsens by more than1e-8.** Retaining proposals is not a mathematical non-regression guarantee.
4. Nearest-rank90th percentile candidate end-to-end runtime≤**30 seconds**, median paired candidate/baseline runtime ratio≤**2.0**, each arm≤120 seconds; any timeout fails feasibility.

These are prespecified engineering/information-value thresholds, not statistically powered thresholds or estimated real FPL benefits. They are **new-study** gates and do not replace/rescue PR50's failed old gate. No multiplicity-selected secondary success or relaxed threshold. No support for positive opportunities is itself informative; do not inject winners and rerun.

Report every state, mean/median/range, all4 stratum totals, utility/hits/FT/transfer counts, keep deltas, legality/score counters, runtime/RSS and missingness. If pass, only recommend considering a separate real-state study once private capture is verified. If fail/inconclusive, preserve the unchanged candidate and stop enlargement/tuning under this protocol. Any changed candidate or state distribution needs another rationale and untouched test, not repeated searching until positive.

## 7. Registration and delivery checklist for the next session

- This task: protocol/priority evidence only, registry reconciliation, no execution registration or numerical run.
- Next commissioned task: implement isolated adapter/harness contracts, review novelty/identity, pin all bytes/commands, append formal EXP-TS-FUNDING-REALPOOL-001 registration and implementation before generating test states. Pre-execution freeze required; do not alter PR54 files/manifests or original registry JSONs.
- Then one bounded run, append results/state including failed gates, independent review before any additional experiment. Private TS/stateful/realized evaluation remains separately blocked; no automatic production integration/deploy.

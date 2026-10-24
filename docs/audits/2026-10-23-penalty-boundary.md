# B penalty audit and fixed candidate replay — 23 October 2026

## Scope and existing mechanics

Production/default mathematics is unchanged. All candidates are explicit opt-ins. The existing sealed B reference is `eef055ef9aa0bd3d8a013b05e3e309b326ff98298171bc9a2cccd361c6d2a134` (data 2026-10-23 07:42:37 UTC). The reference's numerical source is `2b8393a932c7ed5de0f3334cc024915b909e6442`.

The model already simulates team penalty attempts as Poisson(lambda), blending own awarded and opponent conceded histories with league shrinkage (20 match exposure). The probability of at least one award is `1-exp(-lambda)`, not lambda itself. It permits multiple penalties. Player conversion is shrunk to the league with 20 attempt exposure, and historical taker weights decay with six GW half-life. Current B uses official FPL penalty ranks among players actually on the pitch; missing ranks retain historical weights. A roster rank or the historical normalized weight is not an unconditional chance of taking a penalty.

For Sunderland's next fixture in the reference, lambda=0.0952380952, hence P(at least one penalty)=9.0844%. Le Fée's historical weight of 94.22% is not his actual taker probability: official first-ranked Diarra takes precedence while on the pitch. Both are governed by the same MM lineup/minute distribution.

A miss gives the taker -2; a saved penalty gives the opposing active goalkeeper +5 and one save, from the same event. Those events feed the season-specific BPS calculation. The miss diagnostic component is already contained in negative points and is not added twice to xP. Ordinary assists are not assigned to a scored penalty. **A complete separate FPL penalty-winner assist process remains unimplemented**; do not claim this audit fixes special-assist identities without complete sources.

## Two distinct boundaries

1. Ordinary scorer allocation currently uses inclusive historical xG, while scored penalties also have a separate event channel. Team goals are not simply added twice; expected penalty goal mass is subtracted at team level. Nevertheless, inclusive penalty xG biases the relative allocation of ordinary goals.
2. That subtraction uses an all-roster stored conversion, whereas the realized penalty channel selects from the actual active players (and current official ranks). The new opt-in `experimental_conditional_penalties` integrates the event sampler's identical taker/conversion law over the actual lineup intervals. It subtracts precisely that conditional expectation. An impossible penalty budget fails closed. The same conversion feeds the ordinary-save expectation subtraction.

No occurrence parameters, taker history, conversion fit, team goal intensities, MM probabilities or TS scoring rules are refitted in these experiments.

## Verified event sources and candidate definition

All 380 2024/25 PL shotmaps are checked for explicit penalty flags, finished status and canonical match/player mapping. The complete 380-match 2025/26 player-stat source uses scored+missed counts; played rows have no missing penalty fields, and total attempts are reconciled before/after canonical identity mapping. Counts are 83 and 92 attempts, respectively; no unmapped identity or materially negative xG residual occurs. Both scored and missed penalties are removed. Source hashes and the positive-count ledger are archived in `analysis/results/penalty-neutral-sources-20261023`.

The nonpenalty candidate uses a **count-based FPL-scale estimate**, `max(0, inclusive FPL xG - 0.79*verified attempts)`. This is a declared convention and not native per-shot npxG. Provider-native FotMob xG is not substituted into FPL xG. A residual below -0.0051 fails instead of silently clipping incompatible data. Both individual recency histories and broad/soft-role priors are rebuilt on that boundary; new players also receive the corresponding population prior. Only ordinary scorer weights receive the resulting NP/inclusive rate ratio. Existing learned performance covariates and coefficients stay frozen; this is not a full retraining on NP goals.

The 2024 predeadline q states were reconstructed using the original `run_2024_25_conditional_mm.build_baseline`, `build_histories` and `add_role_work` functions, then reduced to q/identity/clock fields. Original role states are used; no target observed position is introduced. Earlier seasons' missing DefCon values are not imputed: the exact existing goal pooling equation is projected onto xG/minutes only and tested against the original complete-data function.

## Fixed historical tests

All variants use the existing joint-role B baseline: 171 fixtures in 2024/25 GW22–38 and 330 in 2025/26 GW6–38, 400 draws per arm, the same archived seeds. Each baseline must reproduce the published research PM baseline with **zero** maximum xP error. These are reused research periods, not independent certification.

Three isolated protocols were registered before their corresponding results were read: NP allocation only, NP plus conditional conversion, and conditional conversion only. There is no named-player override or tuning. Promotion requires, separately in each season, overall xP MAE delta <=0.005, played-player MAE delta <=0.02, absolute bias increase <=0.02; the penalty-taker subgroup must not worsen absolute bias or MAE by more than 0.02. The taker subgroup identifies players with a recorded season penalty for evaluation only; future attempts never enter prediction state.

The NP-only candidate **fails** its promotion gate. Overall MAE is 0.887523→0.887763 (2024/25) and 0.903209→0.903938 (2025/26). Taker MAE improves 2.380330→2.336434 and 2.286469→2.250461, but taker bias worsens -0.032318→-0.167195 and -0.082884→-0.201463. Lowering Le Fée's xP alone is not sufficient justification for deployment. No general predictive improvement is established. The fixture-cluster uncertainty report is archived beside the scored rows.

The current NP research bridge also rejected an exact-rate parity check for newly expanded roster entrants: their existing fallback component rates are not identical to freshly recomputed population priors. That unfinished bridge has been removed, rather than silently publishing a mixture of rates. This does not affect the conditional-only candidate, which retains every existing scorer weight.

## Reproduction

Use `PYTHONPATH=src:scripts:.:analysis OPENBLAS_NUM_THREADS=1` and the repository's locked numerical runner. Restore the existing historical checkpoints/raw sources first.

```
python analysis/build_penalty_neutral_sources.py --out analysis/results/penalty-neutral-sources-20261023
python scripts/locked_numerical_runtime.py analysis/test_penalty_neutral_candidate.py --out OUT --workers 2
python scripts/locked_numerical_runtime.py analysis/test_penalty_neutral_candidate.py --conditional-penalties --out OUT_COMBINED --workers 2
python scripts/locked_numerical_runtime.py analysis/test_penalty_neutral_candidate.py --conditional-penalties --conditional-only --out OUT_CONDITIONAL --workers 2
python analysis/summarize_penalty_candidate.py --out OUT
python -m pytest -q tests
python scripts/check_locked_gk_default.py
```

Each output contains protocol, scored rows, cohort MAE/bias and an explicit gate decision. MM input distributions are identical in both arms; consequently analytical start-Brier and minute predictions are unchanged by construction. Monte Carlo sampled minutes can differ when event RNG consumption changes, and are not claimed to be identical per draw.

## Final decision and served app

**No candidate is promoted.** The combined candidate also fails the subgroup-bias gate (2024/25 taker bias -0.167585; 2025/26 -0.201532). Conditional conversion alone is nearly neutral: overall xP MAE 0.887523→0.887623 and 0.903209→0.903066. Its taker bias changes -0.032318→-0.032898 and -0.082884→-0.083789. Those small increases fail the preregistered non-worsening subgroup-bias rule. They may include Monte Carlo noise; no predictive deterioration of practical size is asserted, but the rule is not relaxed after seeing the results.

Additional scope limitation: when both published ranks and historical taker weights are absent, the original simulator falls back to ordinary goal weights. Consequently changing those goal weights in the NP arms can also change fallback taker choices. These arms are **not** claimed as pure isolation of the ordinary scorer mechanism; their scope notes explicitly record this additional reason not to promote. The conditional-only arm changes no weights and has no such ambiguity.

The active-lineup conditional calculation remains an opt-in, unapproved implementation. The explicit promotion loader rejects failed evidence and any attempt to enable an unvalidated NP correction. No workflow, production configuration, public forecast, private manager state or publication pin is changed. A future NP release needs separate immutable penalty-fallback weights, consistent new-roster population priors, and a recalibrated ordinary-goal allocation validated before promotion. Merely subtracting penalty xG from frozen previously inclusive rates does not establish that release.

The current conditional-only comparison covers **60 fixtures, GW8–13, 4,008 player-fixture rows**. After restoring the exact archived squad evidence and the verified current goalkeeper observations (rather than the local older 68-match cache), the baseline reproduces every published xP exactly, maximum error **0**. All analytical minute/start distributions remain identical. GW8 Le Fée is 5.52 before and 5.52 under conditional conversion alone; this does **not** correct the diagnosed inclusive-xG allocation issue. Saka, Chelsea Palmer and Haaland are also unchanged in that seeded first-GW comparison. The previous single-player 4.62 diagnostic is not a released new Le Fée forecast.

**859 pytest tests**, the existing JS contract suites, and exact original locked-PM seeded parity (100 fixtures plus the aggregate replay) pass. The existing public transfer and Le Fée pages load in a real Chromium browser with normal TLS verification; the snapshot is usable and no private POST is sent. The existing release seal is unchanged. The browser receipt and full current paired comparisons are in `analysis/results/penalty-current-conditional-20261023`.

App retained: https://pdamkier-del.github.io/fpl-analytics-app/mm-preview/app/transfers-classic.html . No new preview deployment is claimed: the best documented existing release is deliberately retained because every proposed candidate failed its predeclared gate.

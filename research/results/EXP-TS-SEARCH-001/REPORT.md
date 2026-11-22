# TS v3 exact-small validation — decision report

**22 November 2026 · EXP-TS-SEARCH-001 · original protocol unchanged · no production changes.**

The frozen B-worker TS v3 returned legal, consistently scored decisions in this suite, but **did not maximize its own objective in 11 of30 deterministic cases**. Its heuristic search can exclude a necessary negative-value funding leg. The mechanism was already documented in LEGACY-044/045; this study adds an exact, six-GW, current-scorer gap measurement. It is not a first discovery of enablers or a measured real-season gain.

## All results

| Domain | Cases | Strictly positive joint gap | Illegal path actions | Scorer disagreements |
| --- | ---: | ---: | ---: | ---: |
| Deterministic, all legal XV/XI/C/VC/bench |30|11|0|0|
| DNP, three fixed XI and complete C/VC/bench menu |12|0|0|0|
| Total |42|11|0 of252 actions|0 in11,880 checks|

All 42 cases completed in **16.095455 seconds**, below the original 120-second total process budget. No cases were omitted or selectively rerun. At most180reachable states were retained in a DP layer. Both references used the unchanged six weights`(1,.60,.36,.216,.1296,.07776)` and **undiscounted** official hits plus buffer 1 per paid transfer. No scorer/config/protocol parameter was changed.

Every case is in [case-results.csv](case-results.csv); full heuristic and exact paths, input/code hashes, nomination/state counts, scoring checks and runtimes are in [initial-run/results.json](initial-run/results.json). Raw signed rounding differences are preserved; numerical agreement tolerance is1e-9. DNP gaps have magnitude below 9e-14, so these are arithmetic roundoff, not effects.

| Deterministic family | Cases with gap | Weighted synthetic utility gap |
| --- | ---: | --- |
| Cheap enabling DEF funds superior MID |6/6|32.90048–66.73408|
| Historic purchase/sale-price funding |5/6|31.34624–38.13376 among positive cases|
| Time-varying gains / FT timing |0/6|0|
| Club-limit constraints |0/6|0|
| Zero/negative isolated leg without needed funding |0/6|0|

The other 19 deterministic cases matched their finite-domain optimum. All 12 DNP cases matched **only within their predeclared restricted menu**. Their pool contains 15 players, so they do not test transfers under stochastic nominations. There was no extra nomination opportunity in these menus beyond rounding. These deliberately constructed counts are neither an estimate of real-world error frequency nor a representative performance benchmark.

## Concrete hand-checkable failure: D01

The original squad scores 90 per week: base XI78 plus captain 12. TS keeps it throughout and obtains`90*2.38336 =214.5024`.

The exact opening bundle sells DEF 3 and MID 11, buys DEF 16 and MID 17. DEF 3costs70 tenths; the replacement costs40, releasing30. This finances the MID upgrade from 50to80. The DEF alone reduces6 points to 2 and is therefore forbidden by the source proposer's negative-leg check. The MID improves the nominated XI by 14 and captain bonus by 8; losing 4 in defence leaves a joint18-point weekly improvement, to 108. With FT 0, the opening bundle pays8 official hit points and 2 buffer:

`108*2.38336 -8 -2 =247.40288`.

The exact utility gap is therefore **32.90048**. This matches the witness fixed in DESIGN.md before execution. Some optimal archived later actions swap equally useful reserves: the original objective gives free transfers no standalone charge and no terminal salvage. Those ties are preserved, not a recommendation to churn reserves.

## Search limitation versus scoring error

The source `_fast_local_candidate_squads` rejects a single leg with`weighted_gain <= -1e-12` before scoring joint bundles. [pruning-witnesses.json](pruning-witnesses.json) records the optimal opening bundles and negative individual legs in all 11positive-gap cases. In these funding constructions the superior bundle requires that rejected leg; no search-beam widening result is inferred, and no proposer ablation was run.

Two independent finite-state references make the distinction explicit:

1. Exact transfer paths valued with TS's own unchanged heuristic nominations.
2. Exact joint transfer/nomination paths valued with the **same frozen arbitrary-nomination point law**.

Both gaps coincide in all material cases. Therefore these witnesses demonstrate transfer/path search loss, not a nomination gain or point-accounting error. Independent scalar matching of absent slots to legal reserves, captain fallback, sale-price/FT/bank transitions and path-objective replay found no disagreement in the declared checks. Zero discrepancies here is not a proof that the scorer has no bugs on untested inputs.

## Scientific and reproducibility boundaries

- The target is pinned source`161b67b6`, specifically the unchanged shared-PM scorer inside the B-worker context. It is not the separate unpatched locked-manager p_play approximation. The complete source/config identity is recorded in`research/ts_search/inputs/source-manifest.json`; all 532 Python files still match after execution.
- Independent DP enumerates every feasible XV transition and retains every reachable purchase-price/bank/FT state. It uses no TS beam/proposer, MILP, new fit or observed match outcomes. Every deterministic legal XI is enumerated. The DNP domain has exactly 3 XI×6bench orders×110C/VC pairs/GW; additive factorization evaluates the same finite product exactly.
- Initial code/inputs/design were committed at`9f9ae6e3`; implementation event 75 and running event 76were committed at`759ccf51` **before execution**. The unchanged original protocol SHA256 is`ce70ee48c2555b8f658c0c16ff730f6f084baccfce2fad5d2ee51eec52bf752b`.
- The arbitrary nominee score uses the original imported autosub function and the same aligned captain law. Independent scalar rules are a cross-check, never a substituted objective. A source/code/input hash mismatch fails closed.
- Synthetic payoffs include fractional values. A generator comment calls them integer; that comment is inaccurate, and the frozen code/inputs are retained rather than edited after results. They are finite artificial payoffs accepted by the original scorer, not a certified physically realizable PM/FPL event law. These cases measure optimization correctness, not forecast calibration or football realism.
- No confidence intervals or p-values apply to these finite deterministic witnesses. No claim of global FPL, full stochastic nomination, chips, real rotation accuracy, representative utility loss or realized point gain follows. All original protocols, MM B, PM vFinal, TS v3, app/C2 work and substitutions trial remain unchanged. No private manager data is used.
- PR 47's scoped review supports TS novelty only; the overall Stage0 inventory-review box remains pending. This experiment's independent result/code review also remains pending. Completed study is not model acceptance or deployment.

Offline verification independently replays504archived exact-path nominations and all associated transitions; it matches the hand-derived D01 result. This verifies chosen witnesses, **not optimality merely from replay**; finite-domain exactness additionally follows from exhaustive domain construction and DP dominance. No full model or optimizer rerun was needed for this check.

## Next scientific work

**Next existing ready registration: EXP-PM-DEFS-001.** Consolidate the event/coverage dictionary using the already completed PR 32 and PR 42 work. No repeat audit or blanket CS/BPS correction. Frozen-MM prospective collection continues only through its data gates; the protected8 GW/80match trial is unchanged.

The TS-specific follow-up should be a **separately preregistered isolated candidate** that allows jointly beneficial funding bundles without the forbidden-leg pruning, tested against this frozen baseline for legality, exact-domain gap and runtime. The current42 cases become regression/development witnesses, never independent validation of a repair. Use a separately locked, broader unseen instance set for new search-quality claims and valid prospective stateful data for realized FPL value. Do not develop or activate that candidate in this PR. A new TS, parameter tuning or production integration is not justified automatically.

# Preserve model behavior while simplifying implementation

The user's objective is maintainable code with all existing features retained. This differs from the analytic PM research experiment: no analytic replacement, odds integration, feature removal, reweighting or model retuning is authorized by this cleanup alone.

## Ownership and order

1. **Point accounting:** one pure nonbonus scoring function, reused by sampled player results and exported aggregate components. Keep BPS and joint bonus assignment separate. Preserve public names and outputs.
2. **Input preparation:** document source, observation clock, missing-data policy and owner for each feature. Centralize duplicate transformations only after exact input replay exists.
3. **MM contract:** one authoritative duration/start distribution feeds PM. Retain roles, injuries/availability, hierarchy, workload and existing competition inputs. Explicitly document coverage gaps; cleanup does not turn missing features into implemented ones.
4. **PM orchestration:** separate minutes, ordinary goals, penalties, assists, defensive outcomes, negatives, BPS and shared bonus into clearly named stages without changing random draw order or event dependencies.
5. **TS boundary:** consume the sealed PM result/scenario contract; never rebuild independent player estimates. Preserve existing transfer rules, budgets and original desktop UI.
6. **Retire duplication:** migrate callers gradually after before/after replay. Remove old paths only when no supported caller depends on them. Keep deliberate historical/experimental reference implementations distinct.

## Acceptance for each cleanup

Same fixture inputs and seeds must reproduce all player events, FPL points, BPS/bonus, sampled intervals, final random-generator state, and downstream aggregate outputs exactly. Existing component, MM/PM, goalkeeper, role and penalty regressions must pass. A changed prediction is a separate model change, investigated and tested separately. No new complexity is justified merely by adding a layer or class.

The known substitution-process limitations and partial CL/workload/coach-quote coverage remain tracked separately. Keeping all current features does not mean those missing capabilities already exist. This cleanup cannot be presented as fixing the minute model.

## First bounded implementation

Extract pure point accounting from `joint_simulator.py`; reuse it for individual match scoring and aggregate component export. Preserve the public goal/clean-sheet constant imports for experimental callers. Keep historical BPS rules, keeper goals, save buckets, penalty saves/misses, defensive contributions and discipline unchanged. No random number calls enter the extracted function.

The analytic PM/market screen remains an offline experiment. Neither the B app nor production is deployed by this code cleanup.

## Verified first-step result

All 942 tests pass. The fixed replay has exact equality for 100 fixtures / 2,000 individual match draws plus 2,000 aggregate draws, including random state and all exported components. Evidence: `analysis/results/point-accounting-cleanup-20261025/`. No live deployment was made. The NP source-integrity guard now pins both the simulator and the extracted scorer plus the parity receipt; fitted model and historical acceptance thresholds remain unchanged. Steps 2–6 above are the remaining cleanup plan, not claims of completed implementation.

## Second bounded implementation

The maintained ownership/field map is now `docs/model/data-to-player-points.md`, linked from the root README. `scripts/trace_player_points.py` verifies exact input files and exports source context, selected NP weights, analytic MM values, sampled PM values/components and the TS seal for each player/fixture. It was checked on all 669 players / 4,014 rows of the saved 24 October reviewed release; this is not a new live forecast.

Preview means, probabilities and TS scenarios now come from one simulation pass. Exact fingerprints match the prior two-pass version on 100 historical fixtures, including every preview field and raw TS scenario. Existing full regression suite: 948 passed; subsequent targeted suite including one new joint-role integration test: 9 passed. No source feature, coefficient, probability estimate or public app output was changed or deployed. Old reference/research implementations remain deliberately separate.

## Shared fixture input implemented

The PM compatibility entry now delegates to `src/fpl_v1_1_model/fixture_input.py`: separate player/team/match tables, one exact ownership/identity/cutoff join, and one existing mathematical adapter. All source features and original player ordering are retained. Exact mathematical inputs and forecast outputs match on 98 real historical/current fixtures; all 60 current fixtures / 4,014 rows / 669 players round-trip every original value/dtype unchanged. All 974 tests pass. Details: `docs/model/shared-fixture-input.md`; receipts: `analysis/results/fixture-input-contract-20261025/`. This does not rewrite raw collectors or retrain MM/PM, and no public release is initiated.

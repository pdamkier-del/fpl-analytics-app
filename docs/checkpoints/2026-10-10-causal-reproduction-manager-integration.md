# Causal reproduction audit and original manager integration

Continues HEAD `3e857fbeccfcb455e0d679fc6142f25d8e39b42f`, branch `free-github-static-20261010`. No locked mathematical source, coefficients, thresholds, search configuration or model seed is changed.

## Reproduction evidence

The permanent `analysis/results/live-raw-reproduction-20261010-v2/causal-audit.json` records both complete workflow archive checksums. Training identities, outcomes and row order are identical. The sole changed input of the original conditional-sub logistic fit is `seq_minutes_slope5`: 473 rows, maximum 4.263256414560601e-14. The unchanged standardized L-BFGS fit then changes q by up to 0.0038346693529844322. Restoring ONLY that feature in an audit intervention restores ALL fitted coefficients and probabilities exactly, zero difference. No production observation is replaced with old predictions. The slope uses original `np.polyfit`; differing numerical kernels are being controlled rather than changing its formula. Tiny probability changes can change the conditional simulator's RNG consumption. Exact immutable-input replay is already proven, unlike the earlier raw rebuild.

Team-xG history is exactly equal, while fitted team lambdas drift by up to 3.015595619970668e-05. Cross-runtime root-cause certification requires complete raw rebuild evidence, not only the q intervention. The canonical launcher fixes hash seed, numerical threads and NumPy/OpenBLAS CPU dispatch before imports. Original tolerances, objective and model seeds remain unchanged. `verify_canonical_raw_rebuild.py` rebuilds all numerical adapters twice and checks exact training, MM, team lambda, full simulator-input and xP DataFrames. Its independent workflow retains audit artifacts even on failure. Runtime determinism does not certify missing source coverage.

Source materialization now uses the recorded manifest cutoff instead of wall-clock time. Fresh collection records its common inference cutoff AFTER all source HTTP captures, preserving each original timestamp. Repeated identical append-only keeper captures are deduplicated, while conflicting revisions remain blocking.

## Actual state, original TS and chips

The desktop's new `manager-state.html` accepts/imports legal 15-player squads, bank, FT, actual purchase prices, observed-at timestamp and all four chip histories. No current price is silently used as purchase price. Input remains local until exported. Free `live-manager-plan.yml` Actions calls the original TS planner and returns importable output; no browser PAT/token or FPL-account write is used.

The explicitly authorized diagnostic TS path now calls original `plan_transfer_path`, exact configuration from `run_joint_fh_wc_stopping_replay.cfg`, first-action execution on a COPY and original XI/captain optimizer. Later path actions are hypothetical and require replanning. The existing original FH/WC SIMPLE_FH_WC branch, WC-as-TS, FH optimizer, BB incremental autosub value and final coordinator produce diagnostic current-GW assessments. Missing TC future scenarios and future chip timing remain Not Available. No replacement stopping policy is invented and full four-chip certification remains false.

## Remaining source gaps and next GW

BPS remains 1,204 verified rows and 334 quarantined rows. Missing fields overlap: chances_created 96, dispossessed 100, was_fouled 244, accurate_passes_percent 16, tackles_won 1. This checkpoint introduces no evidence licensing invented zeros or substitution of total FPL BPS for the original background-event definition. MM historical cohorts still lack every unused registered player's observed match history and have provider-semantic limitations.

`fresh-current-source-audit.yml` restores verified stable-code identities, captures fresh official FPL/FotMob evidence in timestamped raw folders and materializes cutoff-fixed input features. It does not claim a completed fresh GW7 simulation before its artifact is audited and replayed. Outcomes unavailable at the new cutoff are excluded, not fabricated.

The permanent old 4,002-row original-vFinal diagnostic remains published and clearly labelled. The existing desktop Pages deployment is retained, with links to manager-state entry. `locked_model_active=false` until raw rebuild, source completeness and full TS/chip release requirements actually pass.

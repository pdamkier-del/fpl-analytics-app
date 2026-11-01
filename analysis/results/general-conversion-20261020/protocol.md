# General finishing and on-pitch receiver conversion: fixed protocol

Written before the new replay results are read. Offline only; no production, B-preview or private state changes.

Question: does a tightly isolated finishing correction improve the unchanged PM when applied to individual goal allocation and/or the actual on-pitch finishers' chance-weighted conversion? Unlike the earlier player-PM-v2 experiment, this does not rebuild xG/xA profiles, opponent effects or team strength.

Reference: archived original 400-draw PM, unchanged MM, original per-fixture seed. Reproduce every original player xP exactly. Historical original inputs from verified run 38565961308; Core is read-only.

Factor: existing Gamma-Poisson mean (historical goals + 20)/(historical xG + 20), all available pre-cutoff history; same setting selected previously on 2024/25 GW6–21. No new tuning, named-player correction or selection using these outcomes. Exclude known early-2022/23 placeholder expected stats. This is an all-xG effective conversion factor, not identified non-penalty skill. Current penalty probabilities/weights/conversion are held unchanged; no penalty-role repair is included.

Four arms:
1. Original, no changes.
2. Individual allocation only: multiply active scorer weights by own factor, normalize within unchanged ordinary team goal budget. Original conditional assist law retained.
3. Receiver/lineup conversion only: keep scorer/creator weights unchanged; multiply ordinary goal intensity at each minute by sum(active original goal weight × finishing factor)/sum(active original goal weight). This is a chance-share proxy for receiver exposure, not observed creator→shot links. It changes goals and assists jointly; a standalone assist increase without corresponding scored goals would be incoherent.
4. Combined: both changes; relative finishing allocation and absolute conversion applied once. The combined individual ordinary goal intensity is old ordinary intensity × old scorer share × own factor. Assistgiver is selected only for a scored ordinary goal, from active teammates excluding the scorer.

Use the existing offline shadow-intensity adapter with an isolated rate function. Do not change original simulator, PM/BPS/bonus rules or team strength. If no active scorer mass exists the multiplier is neutral, preserving original zero-scorer behavior. Missing historical player evidence gives neutral factor.

Evaluate all 171 fixtures in 2024/25 GW22–38 and all 330 in 2025/26 GW6–38, 400 draws per arm. Periods were used in previous model research: temporal pre-match checks do not make them independent whole-model holdouts. Report xP MAE/RMSE/bias, goal/assist Brier/log loss/MAE/bias, bonus errors, played-player metrics and position groups, and fixture-paired 95% bootstrap intervals. Baseline/candidate source-input hashes and caches retained. Binary-event Monte Carlo smoothing and count-Poisson approximation are labelled. Bootstrap does not cover all simulation noise.

Require consistent gains across seasons, reasonable calibration and no material point regression before considering any promotion. No new full-horizon TS total or production certification is claimed. Mixed/uncertain results mean retain current PM. A promising candidate still requires higher-precision independent validation and interaction with actual B MM/joint GK before deployment.

Capture inventory correction before examining replay metrics: the frozen 2024/25 archive contains 171 records in GW22–38, rather than the initial planning estimate of 170. All records are retained; the full run therefore has 501 fixtures. No outcome-dependent inclusion changes.

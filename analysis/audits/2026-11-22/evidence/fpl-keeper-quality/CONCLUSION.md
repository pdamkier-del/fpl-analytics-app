# Keeper rate feature diagnostic — 2026-11-15

Decision: retain as an exploratory candidate; do not promote or retune on GW8–10.

The fixed feature bundle (prior inside-box save fraction and prior xGOT faced per90) reduced save-count MAE from 1.5659 to 1.5384 and RMSE from 1.9992 to 1.9714. Poisson NLL fell from 2.05394 to 2.03434. Evaluation contains 60 full90 keeper observations across 30 matches. Paired match bootstrap delta NLL CI95 is [-0.05496, +0.01378], including no improvement. GW8 and GW9 improve; GW10 worsens.

Training targets are GW3–7 with historical features from earlier rounds; GW1–7 raw files were archived before GW8 deadline. Training feature histories are retrospective reconstructions, not contemporary historical captures. Evaluation uses the single GW1–7 fit without updating on GW8–10. This is exploratory because those outcomes were previously inspected.

The comparator is a regularized save-history Poisson regression, not the active production keeper distribution. Full90 participation is conditioned on. This result cannot establish a gain in bonus or total FPL points.

Next gate: compare against original archived keeper forecasts on matched fixtures, then test save-quality BPS with recalibrated background to avoid double counting. Until then keep production and the frozen substitution experiment unchanged. Do not search extra penalties on this evaluation set.

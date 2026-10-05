# BPS background experiment — promising candidate

Historical validation now uses explicit 2025/26 BPS rules, kept separate from
the live 2026/27 rules.

Architecture:
1. Joint simulator generates high-confidence event BPS from simulated minutes,
   goals, assists, clean sheets, saves, goals conceded, cards, own goals and
   shared penalty events.
2. Missing Opta/background BPS is forecast as a minutes-scaled per-90 rate.
3. Background candidates use FPL position, overlapping soft tactical-role axes,
   and cutoff-safe recent BPS-style underlying action rates.
4. Bonus is never forecast directly. The simulator ranks all players by BPS and
   applies official tie-aware 3/2/1 allocation.

2025/26 reconstruction differences from 2026/27 are encoded separately:
- penalty-save base +8 in 2025/26;
- saves from inside box +3 / outside box +2;
- CBI gives 1 BPS per 2 in 2025/26;
- being-tackled existed in 2025/26 (approximated in background because the
  exact Opta field is unavailable).

Development GW16-21 LOOGW:
selected background = role_recent_detail, recent half-life 3, L2=200.
Approximate background-BPS MAE = 2.8951, RMSE = 3.8988.
Role-only MAE = 2.9541, RMSE = 4.0066.

Reused GW22-38 joint diagnostic (144 fixtures / 11,794 rows, 260 draws):
Bonus:
- event-only expected-bonus MAE 0.14515
- soft-role 0.13891
- selected role+recent-detail 0.13604
- selected delta vs event-only = -0.00910
- bonus Brier 0.07257 -> 0.07180
- bonus log loss 0.19543 -> 0.19721 (slightly worse)
- mean actual bonus 0.07792
- selected mean predicted bonus 0.08051
- actual P(any bonus) 0.03900
- selected P(any bonus) 0.03993

Total xP:
- event-only MAE 0.92790, RMSE 1.84656, bias +0.03718
- selected MAE 0.92240, RMSE 1.84682, bias +0.02561
- delta MAE -0.00551
- delta RMSE +0.00025
- delta bias -0.01157

Interpretation:
- background BPS is clearly useful for expected bonus and xP MAE;
- soft roles matter, and recent detailed action rates add further signal;
- probability calibration is not finished because log loss/RMSE are not both
  improved;
- next BPS test should calibrate background uncertainty / residual variance
  rather than only the conditional mean;
- after variance calibration, translate known 2025/26 background-rule changes
  to 2026/27 before freezing the live model.

Artifacts:
analysis/results/bps-background-20251005-v1/

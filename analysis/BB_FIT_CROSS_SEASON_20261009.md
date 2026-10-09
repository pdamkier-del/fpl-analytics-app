# Bench Boost 2025/26 fit and 2024/25 conditional holdout — 2026-10-09

## Implementation
- BB code: `src/fpl_xpts/bench_boost_policy.py`; optional competition in `scripts/run_joint_fh_wc_stopping_replay.py` when `bb_lambda` supplied. With BB absent, legacy FH/WC policy stays unchanged.
- BB value: unconditional four-player bench xP MINUS expected regular autosub bench points, given the locked TS post-transfer lineup and independent appearance probabilities. Actual chip scoring is by `actual_team_points(...,'bench_boost',hit)`.
- BB threshold tapers linearly to zero at GW19 and GW38; at most once per half and never stacked with FH/WC. BB can compete with FH/WC for a deadline; their **policy weights** remain locked, but selected weeks can change.
- BB makes no permanent transfer by itself. The TS planner is unchanged. TC is NOT included in these replays; future joint-chip integration must respect locked TC and the one-chip-per-week rule.

## Results
2025/26 baseline FH/WC 2209 actual points (GW1–38):
| BB λ | BB GWs | Total |
|---:|:---:|---:|
| 0 | 1,20 | 2216 |
| 5 | 1,20 | 2216 |
| 10 | 7,20 | 2223 |
| 15 | 7,24 | 2228 |
| 20 | 11,29 | 2242 |
| 25 | 15,29 | 2245 |

2024/25 conditional FH/WC baseline 2026 actual points (GW6–38 only):
| BB λ | BB GWs | Total | FH GWs | WC GWs |
|---:|:---:|---:|:---:|:---:|
| 0 | 6,20 | 2042 | 11,29 | 8,24 |
| 10 | 6,23 | 2033 | 11,29 | 8,24 |
| 15 | 11,27 | 2058 | 12,29 | 8,31 |
| 20 | 12,31 | 2060 | 11,29 | 8,24 |
| 25 | 14,31 | 2044 | 11,29 | 8,24 |

λ=20 is best across the cross-season sums (2242 + 2060 = 4302), compared with λ=25 (2245 + 2044 = 4289). Recommendation: provisional λ_BB=20, **do not lock or claim unbiased cutoff-certified calibration**. Note that λ=15 modified the chosen FH/WC GW in 2024/25 because BB competed for deadlines even though FH/WC parameters were untouched.

BB=20 in 2025/26: BB GW11 expected +10.623 xP / actual +9; BB GW29 expected +12.627 xP / actual +24. Full total 2242 versus 2209 without BB. Bench players:
- GW11: Lacroix, Krejčí, Foster, Sels
- GW29: João Pedro, Mosquera, H. Bueno, José Sá

BB=20 in 2024/25: BB GW12 expected +8.402 xP / actual +22; BB GW31 expected +11.359 xP / actual +12. GW6–38 total 2060 versus 2026 without BB. Bench players:
- GW12: Souček, Romero, Van den Berg, Fabiański
- GW31: Mateta, Cucurella, Mykolenko, Pickford

## WC → BB study
On 2025/26 frozen FH/WC trajectory, BB directly after WC1 at GW7: expected +10.53 xP, realized +7; delay to GW15: expected +7.00 xP, realized +12. WC2 at GW26: GW27 expected +9.46 xP, actual +12; GW29 expected +12.63 xP, actual +24. Thus test WC-to-BB opportunities but never force next-GW BB.

## Reproducibility and limitations
Full 2025/26 Actions: https://github.com/pdamkier-del/fpl-analytics-app/actions/runs/37931948335
Conditional 2024/25 Actions: https://github.com/pdamkier-del/fpl-analytics-app/actions/runs/37932130768
An independent fixed-trajectory BB sweep (no competing decisions): https://github.com/pdamkier-del/fpl-analytics-app/actions/runs/37931330212

2024/25 lacks GW1–5 and has conditional roster metadata. 2025/26 WC horizon uses forecast proxy for some future weeks. 2025/26 fit is in-sample. BB xP has an independence approximation for appearances and expected future autosubs, not a fully joint sample of minutes. Future DGWs/BGWs may be incompletely observed as of prior deadlines. Historical total points are observed and not prospective forecasts.

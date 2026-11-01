# Goalkeeper hierarchy review, PR22 follow-up (18 October 2026)

## Decision

Retain `B-GK-joint-empirical-v1`. One general hierarchy alternative was implemented and tested; it failed the prespecified comparative gate. **No improvement in Penders' start calibration is claimed.** The preview now publishes the official hierarchy review, the rejected experiment and an explicit warning about the interpretation of the unlisted pool. Production MM, PM and TS remain unchanged.

The 40.29% pool in v1 is the complement of original MM probability before available-roster projection. It is **not** a fitted probability that Sharman-Lowe and Slonina collectively start. The previous interpretation was too strong. Official evidence supports Penders as the immediate deputy, but does not establish a numerical probability. Restoring 100% without calibration would also be unjustified.

## Official evidence

All sources were retrieved directly with TLS verification on 18 October 2026, initially at 20:07 UTC. Each refreshed capture records retrieval UTC, SHA-256 and the source's `content_publish_date` field in public `gk/evidence.json` and the forecast. Profile/squad publication fields are old page creation dates; they are **not** reliable last-update timestamps.

| Source | Publication field (UTC) | Finding |
| --- | --- | --- |
| [Chelsea confirmed XI vs Everton](https://www.chelseafc.com/en/news/article/confirmed-chelsea-line-up-vs-everton-171026) | 17 Oct 2026 10:15 | Martinez started; Penders was the only goalkeeper substitute. Sharman-Lowe and Slonina were absent from the match squad. |
| [Chelsea match report](https://www.chelseafc.com/en/news/article/match-report-everton-0-2-chelsea) | 17 Oct 2026 13:40 | Penders replaced injured Martinez. Next league match is Tottenham on 24 October. |
| [Alonso's update](https://www.chelseafc.com/en/news/article/alonso-issues-emiliano-martinez-update) | 17 Oct 2026 14:45 | “Mike has personality, he's brave, and we have full trust with him.” Alonso mentions his cup games. This supports hierarchy, not a guaranteed future selection. |
| [Chelsea injury update](https://www.chelseafc.com/en/news/article/injury-update-emiliano-martinez) | 18 Oct 2026 09:10 | Martinez underwent surgery for a fractured jaw. No return date given. |
| [Chelsea first-team/loan list](https://www.chelseafc.com/en/teams/mens-profiles) | Page creation 15 Jun 2022 | First-team category: Martinez, Penders, Sharman-Lowe, Slonina. Loan category: Sanchez, Jorgensen, Curd, Merrick, Sands. Registration is not proof of match fitness, Premier League eligibility or selection. |
| [Penders profile](https://www.chelseafc.com/en/teams/profile/mike-penders) | Page creation 11 Jun 2025 | Strasbourg loan described for 2025/26; Chelsea debut/cup start in August 2026. It does not say he is currently on loan. |
| [Sharman-Lowe profile](https://www.chelseafc.com/en/teams/profile/teddy-sharman-lowe) | Page creation 9 Jun 2022 | Returned from loan in January 2026 and subsequently made benches. No current injury/next-match availability confirmation found in these official sources. |
| [Slonina profile](https://www.chelseafc.com/en/teams/profile/gabriel-slonina) | Page creation 2 Aug 2022 | Earlier league/cup benches and U21 involvement. No current injury/next-match availability confirmation found in these official sources. An old loan article linked from the page is not evidence of a current loan. |
| [Official FPL bootstrap](https://fantasy.premierleague.com/api/bootstrap-static/) | Retrieval timestamp; per-player `news_added` retained | Martinez injured, next-round chance 0; Penders available; Sanchez/Jorgensen unavailable with season-long loan news. Sharman-Lowe and Slonina are not in FPL's Chelsea GK catalogue. |

Cross-check: the existing collected all-competition lineups have Penders on all seven league benches and starting both collected cup matches (27 August and 9 September). This is secondary provider evidence, not a replacement for club sources. No source establishes that Sharman-Lowe or Slonina is injured, suspended or definitely available for 24 October. They remain potential competitors with unconfirmed next-match status.

## Fixed experiment

`scripts/evaluate_gk_hierarchy.py` fits four anonymous role weights on 660 team-fixtures from 2024/25: last starter, last used reserve, last unused goalkeeper bench, other/unlisted. Only squads known before each cutoff are used. Training excludes ambiguous/missing single-starter labels and labels contradicting a hard zero availability cap; all matched validation rows are retained. Unknown roster size cannot increase the aggregate other-role mass. Explicit zero availability caps remain zero. Four log weights are fitted by conditional likelihood with unit L2 regularization; no identities, Chelsea rules, hyperparameter search or tuning to the validation outcomes are used.

The alternative is evaluated on the existing 2025/26 GW22–38 cohort: 1,361 GK rows in 144 fixtures. Missing prior role history falls back to v1. Existing empirical duration PMFs, joint exclusive GK/11-starter selection, scoring/event model, 400-draw budgets and fixture seeds are retained. Point draws are not event-aligned after starter selection changes. Minute metrics use analytical expectations for both arms. Training and evaluation use different seasons, but the evaluation period was previously used for project research and is **not independent certification**. Historical outcome clocks inherit the existing kickoff-delay proxies.

Acceptance requires lower start-Brier and minute-MAE and no higher xP-MAE. The candidate fails all three aggregate checks:

| Metric (lower error is better) | Published v1 | Hierarchy candidate |
| --- | ---: | ---: |
| Start Brier | 0.02970301 | 0.03270555 |
| Minute MAE | 5.59276308 | 6.34442144 |
| xP MAE | 0.56352314 | 0.56799596 |
| xP bias | -0.02416605 | -0.04043167 |

In the **recent regular unavailable** cohort (38 player rows, 8 fixtures), the most frequent starter in the prior five starts has a predeadline zero availability cap:

| Metric | Published v1 | Hierarchy candidate |
| --- | ---: | ---: |
| Start Brier | 0.00196804 | 0.00282640 |
| Minute MAE | 3.76086169 | 4.15730295 |
| xP MAE | 0.73157895 | 0.72565789 |
| xP bias | -0.35157895 | -0.37947368 |

For the two rows where the keeper was an actual substitute in the previous match, start-Brier improves 0.17490 → 0.16630 and minute-MAE 38.50 → 37.83, but xP-MAE worsens 1.375 → 1.5725. Two cases cannot establish takeover calibration. The unavailable-regular cohort also misses injuries that do not result in an explicit predeadline zero cap. These are limitations of this test, not evidence that deputy takeovers are intrinsically unpredictable.

All 288 candidate team-fixtures still conserve exactly 90 analytical goalkeeper minutes. Existing sampled exclusivity/coverage tests remain in place. The failed alternative is never called by the live forecast path; its publication guard refuses to treat it as activated.

## What changed, and what did not

Added a reproducible rejected experiment, cutoff/roster-size regression tests, timestamped official sources and a visible warning in the public app. The evidence file is now SHA-256 checked by the browser along with forecast/MM/baseline files. The live start model and Penders' point/minute forecasts have **not** been replaced by the failed candidate.

The fresh six-GW chain still inherits B's future-GW conditional availability assumptions: it is not a forecast of Martinez's medical recovery or future loan recalls. The current next-round exclusions are authoritative; do not read later conditional forecasts as confirmed availability. Proper numerical calibration of the deputy-vs-unlisted pool, and future availability transitions, remain unresolved model limitations.

Local validation: 702 Python tests passed; all four original B JavaScript suites (36 assertions), joint GK contracts and exact original-PM seeded parity passed. The exact-source CI, refreshed six-GW chain, publication receipt and browser verification are recorded below after completion.

## Exact-source refreshed validation

[Full CI run 39161944940](https://github.com/pdamkier-del/fpl-analytics-app/actions/runs/39161944940) passed for source `e024a8fdd881bf8266b4617cd129ff896cd5c0b1`. [Separate 702-test/JS/parity run 39161944910](https://github.com/pdamkier-del/fpl-analytics-app/actions/runs/39161944910) also passed. The CI hierarchy results reproduce the local metrics above; all 288 team-fixtures used the candidate (no fallback), and it remains rejected.

The fresh six-GW chain contains 668 players, 60 fixtures and 120 team-fixtures. GK forecast/MM/audit repeat is byte-identical. The one-match (66 player rows) and GW8 (10 fixtures, 668 rows) runs exactly match the full-horizon outputs with shared fixture seed offsets. The unchanged TS completed its six-GW regression on the actual forecast with an explicitly synthetic legal state; the state was unchanged, no actual user plan was generated, and chips were not exercised in that stage.

### Penders: previous publication versus refreshed publication

These are **different source snapshots with the same retained v1 methodology**, not a same-input effect of the rejected candidate. The original B/PM source cutoff advanced from `2026-10-18T19:28:20.734940Z` to `2026-10-18T20:14:21.884901Z`; official GK evidence was captured at `20:21:02.016105Z`. Original MM now provides raw P(start) 0.5842321056 rather than 0.5971370004, and the past-only duration history includes outcomes known at 19:30 UTC, after the previous forecast cutoff. The role-memory source also advanced. No hierarchy coefficients were activated.

| Penders GW8 | Previous published v1 | Refreshed v1 |
| --- | ---: | ---: |
| P(start) | 59.713700% | 58.423211% |
| xM | 53.680630 | 52.527614 |
| PM analytical E[min] | 53.680630 | 52.527614 |
| P(60+) | 59.447397% | 58.164979% |
| P(90) | 59.116899% | 57.841786% |
| xP (400 draws) | 2.2700 | 2.0800 |

The refreshed unlisted pool has P(start) 41.576789% and E[min] 37.472386, so team coverage is exactly 90. The larger residual is **not evidence that the named deputies became more likely to start**. This exposes the remaining upstream MM/pool-calibration limitation rather than disguising it as a successful hierarchy improvement.

Refreshed sealed snapshot: `1c37fcc66736cf73e24e2e088a9d2efabbe1afbf2ee9d5dadd5454a8d6d4584d`. Main publication configuration commit `764fa2c5d0d4aa9a561e337370c9c99decf5f35c` changes only the two preview source pins; it does not merge model/application changes into production.

## Published and verified

[Updated B preview](https://pdamkier-del.github.io/fpl-analytics-app/mm-preview/gk/) was deployed by [Pages run 39163826383](https://github.com/pdamkier-del/fpl-analytics-app/actions/runs/39163826383). The public `index.json`, forecast, GK MM, before-comparison, evidence and app JavaScript bytes were downloaded and matched the exact validated artifact.

Real Chromium navigation with TLS verification passed at desktop 1440×1000 and mobile 390×844: 668 players/60 fixtures, SHA-256 checks, Penders row and comparison, GW8→13→8, nine official source links, no JavaScript page errors and no localStorage writes. Existing B/live app and evidence navigation returned HTTP200. Screenshots were inspected. The app's comparison still describes original B/locked-PM versus joint v1 on one fresh input snapshot; the historical 40.29% warning refers to the earlier reviewed snapshot, while the refreshed pool is 41.58% as documented above.

The [public receipt](https://pdamkier-del.github.io/fpl-analytics-app/mm-preview/publication.json) identifies source `e024a8fdd881bf8266b4617cd129ff896cd5c0b1`, production run `39149160869`, production artifact `12145425207`, `production_files=88`, `production_files_identical=true`, and `locked_model_active=false` for the experiment. No production forecast/model file changed.

Result: a working refreshed preview with stronger evidence and explicit negative experimental results. A demonstrably better deputy-start calibration was **not** delivered; the best measured existing version is retained, as requested when an alternative fails. No external permission or input blocker remains.

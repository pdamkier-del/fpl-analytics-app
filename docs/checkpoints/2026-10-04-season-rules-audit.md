# 2025/26 scoring and chip audit — no policy changes

Audited 2026-10-04 against Premier League's season-specific announcements and
the recovered source bytes. The paired diagnostic deliberately retains the
same archived scoring in both arms. This audit does not activate new rules or
claim a rules-correct full-season forecast.

| Item | Official 2025/26 rule | Recovered implementation / result |
|---|---|---|
| Defensive contribution | DEF: 10 CBIT; MID/FWD: 12 CBIRT; two points per match | Threshold implementation agrees; GK has no DC points. |
| Chips | WC/FH/BB/TC once in each half, GW1–19 and GW20–38; no Assistant Manager | `choose_chip` uses these halves and tracks each chip separately. Strategic timing is preserved. |
| Free Hit boundary | Cannot use FH in both GW19 and GW20 | `choose_chip` excludes FH after the prior GW used FH. |
| AFCON transfers | Top up free-transfer balance to five for GW16, rather than add five | The archived `run_phase5s_season_replay.py` only has ordinary capped carry logic; no GW16 top-up is implemented. Season orchestration must resolve this separately. |
| Save BPS | Inside-box saves 3, outside-box saves 2; saved penalty adds 8, for 11 combined | Archived BPS is 2026/27: base penalty-save reward 7; simulator supplies no save subtypes. Historical exact BPS is unavailable. |
| Penalty-goal BPS | 12 irrespective of position; other goals retain positional BPS | Simulator allocates all goals as non-penalty; explicit penalty layer is off. Thus penalty BPS is approximated even when total xG contains penalties. |
| CBI BPS | One point per two CBI in 2025/26 | Restored 2026/27 module uses one per three. Do not silently use it as the 2025/26 rules engine. |
| Bonus ties | Official tied ranks receive 3/2/1 under the documented tie cases | Archived tie allocation tests pass. Background Opta actions remain absent. |
| Assist definitions | Simplified in 2025/26 | The inherited joint model uses an aggregate assist probability from earlier development seasons; this is a model approximation, not a rules-complete attribution engine. |

Sources (official, retrieved 2026-10-04):

- [2025/26 changes](https://www.premierleague.com/en/news/4373187/whats-new-for-202526-changes-in-fantasy-premier-league)
- [2025/26 two chip sets](https://www.premierleague.com/en/news/4362027)
- [GW16 AFCON top-up](https://www.premierleague.com/en/news/4362102/whats-new-in-202526-fantasy-extra-transfers-for-afcon)
- [2025/26 BPS changes and ties](https://www.premierleague.com/en/news/4362127/whats-new-in-202526-fantasy-changes-to-bonus-points-system)
- [2026/27 BPS change, explicitly referring to prior-season CBI](https://www.premierleague.com/en/news/4679946/)

This is a blocking differences audit, not complete season-rule certification.
Banked-transfer behavior around WC/FH, selling-price/price histories, deadlines,
first-GW chip eligibility, early-season forecasts and as-of BGW/DGW schedules
still need an integration-level season check. No transfer/chip-policy code was
changed in this continuation. Preserve a paired control when resolving scoring
or orchestration separately. The 46 missing frozen forecast rows and lack of
full-deadline v4 forecast horizons prevent a full-season replay now.

# PM component dictionary 1.0.0

Executable schema: `ledger.schema.v1.json`; canonical catalog: `catalog.v1.json`. This is a research data contract, not a production scorer or release.

| Definition | Unit / role | Required target distinction | Identity / limit |
| --- | --- | --- | --- |
| team_goals | goals / event_target | All goals credited to the scoring team, including opponent own-goals | team_goals = credited_player_goals + opponent_own_goals + explicitly_unattributed_goals; Cannot equate summed player goals or shot xG to inclusive score; unknown omissions are not zero |
| player_goals | goals / event_target | Credited player goals, with mutually exclusive penalty/nonpenalty partition | player_goals = nonpenalty_goals + scored_penalty_goals; Goals and expected xG are different targets; no inference of penalty origin from goal count |
| fpl_assists | assists / event_target | Final official FPL awards under matching rule vintage | assist_points =3*fpl_assists; category partition is mutually exclusive; Includes eligible own-goal/rebound/penalty-winner awards; no self-assist; Opta assists/xA not interchangeable |
| team_clean_sheet | probability_or_indicator / event_target | Team conceded no goal over full fixture | team_CS =1[opponent_team_goals==0]; Not identified by player qualified-CS probability; bounds are identification intervals, notCI |
| qualified_player_clean_sheet | probability_or_indicator / event_target | FPL-minute60+ and zero applicable player concession liability | E[CS_points] = position_award*E[Q60*Z_liability]; Do not multiply marginals; on-pitch-only GC cannot establish post-dismissal liability; FWDCSpoints0 |
| dc_count | actions / event_target | DEF:CBI+tackles; MID/FWD:CBI+tackles+recoveries | DC_points =2*1[count>=threshold], capped once per fixture; DEF10,MID/FWD12,GKnot applicable; never threshold a mean; never sum DGW counts before threshold |
| saves_total | saves / event_target | Inclusive official saves, including saved penalties | save_points =floor(inclusive_saves/3); Cannot invert point bucket to unique count; mean bucket differs from bucket at mean; keeper role may differ from FPL position |
| save_subtypes | saves / overlapping_subtypes | Inside-box and big-chance subsets, overlapping and including relevant penalties | 0<=inside<=total;0<=big<=total; inside+big need not<=total; Unknown big-chance is null; xGOTthreshold is not an official big-chance label; no ordinary-save double counting |
| bps_score | bps_units / intermediate_not_FPL_points | Season-specific action score before joint bonus rank | BPS_total = known_event_BPS + residual_BPS; Do not add BPS to FPLpoints. Partial residual is not pure noise; old2025target cannot be transported by blind event addition |
| background_bps | bps_units / residual | Observed BPS minus explicitly documented known-event subset | R_new =R_old -(K_new-K_old); K_new+R_new =K_old+R_old; If a new explicit save/CBI/action term replaces a residual term, refit/retarget before research use; no parameter change here |
| bonus | fpl_points / observed_point_award | Joint3/2/1fixture rank allocation including ties | bonus =rank_ties(all_fixture_BPS); E[rank(BPS)] !=rank(E[BPS]); Tie totals need not sum6; include zero-minute card participants; do not rank only selected fantasy squad |
| appearance_points | fpl_points / additive_points | Canonical fixture contribution to total FPLpoint expectation | total_points =sum(canonical_additive_partition); No zero imputation; do not add count/subset/BPS fields to this sum |
| goal_points | fpl_points / additive_points | Canonical fixture contribution to total FPLpoint expectation | total_points =sum(canonical_additive_partition); No zero imputation; do not add count/subset/BPS fields to this sum |
| assist_points | fpl_points / additive_points | Canonical fixture contribution to total FPLpoint expectation | total_points =sum(canonical_additive_partition); No zero imputation; do not add count/subset/BPS fields to this sum |
| cs_points | fpl_points / additive_points | Canonical fixture contribution to total FPLpoint expectation | total_points =sum(canonical_additive_partition); No zero imputation; do not add count/subset/BPS fields to this sum |
| save_points | fpl_points / additive_points | Canonical fixture contribution to total FPLpoint expectation | total_points =sum(canonical_additive_partition); No zero imputation; do not add count/subset/BPS fields to this sum |
| penalty_save_points | fpl_points / additive_points | Canonical fixture contribution to total FPLpoint expectation | total_points =sum(canonical_additive_partition); No zero imputation; do not add count/subset/BPS fields to this sum |
| dc_points | fpl_points / additive_points | Canonical fixture contribution to total FPLpoint expectation | total_points =sum(canonical_additive_partition); No zero imputation; do not add count/subset/BPS fields to this sum |
| negative_points | fpl_points / additive_points | Canonical fixture contribution to total FPLpoint expectation | total_points =sum(canonical_additive_partition); No zero imputation; do not add count/subset/BPS fields to this sum |
| gc_points | fpl_points / additive_points | Canonical fixture contribution to total FPLpoint expectation | total_points =sum(canonical_additive_partition); No zero imputation; do not add count/subset/BPS fields to this sum |
| penalty_miss_points | fpl_points / diagnostic_subset | Subset already included in negative_points | negative_points = cards + own_goal + penalty_miss_points; Never add this diagnostic again to the canonical sum |
| goal_penalty_split | fpl_points / diagnostic_partition | Penalty-goal and nonpenalty-goal portions of goal_points | goal_points =penalty_goal_points+nonpenalty_goal_points; Never add split children alongside parent goal_points; own-goal costs remain negative_points |
| expected_bonus | fpl_points / legacy_mean_alias | Expectation of the joint official bonus award, not BPS itself | expected_bonus=E[bonus]; count exactly once in total xP; Legacy field alias for canonical bonus_points; not a second component. |
| bonus_points | fpl_points / additive_points | Observed bonus award in actual mode, expectation in forecast mode | Count exactly once in total points/xP; BPS is not another additive term; Rank allocation requires full fixture participants; aliases cannot be added together |

## Canonical point partition

`appearance_points + goal_points + assist_points + cs_points + save_points + penalty_save_points + dc_points + negative_points + gc_points + bonus_points`

Legacy forecast `expected_bonus` maps to `bonus_points` once. Counts, BPS and diagnostic partitions are not extra FPL point terms. Missing components are not silently zero. Actual official complete/final explain lists have a separate explicit closed-world adapter; provider missing events do not.

## Rulebooks and sources

- 2026-27: `fpl-2026-27-v1`. Definitions verified; not activated in production
- 2025-26: `fpl-2025-26-archive-v1`. Official selected changes verified; archived helper omits being-tackled field, so its default-zero reconstruction is partial. Missing non-shot-save category is not automatically outside-shot.
- 2024-25: `fpl-2024-25-archive-v1`. Historical adapter retained as inherited evidence, not complete fresh rule certification; DCpoint zero is structural by absent rule, DCaction count missing.
- [RULES26](https://www.premierleague.com/en/news/4661029): primary_current_rules_read; observed 2026-11-22.
- [POINTS26](https://www.premierleague.com/en/news/2174909/): primary_current_point_table_read; observed 2026-11-22.
- [BPS26](https://www.premierleague.com/en/news/4679946/): primary_rule_change_read; observed 2026-11-22.
- [BPS25](https://www.premierleague.com/en/news/106533): primary_2025_26_BPS_table_read; observed 2026-11-22.
- [DC25](https://www.premierleague.com/en/news/4373187/): primary_historical_change_read; observed 2026-11-22.
- [FAQ](https://www.premierleague.com/en/news/4661030): primary_FAQ_edge_case_read; observed 2026-11-22.
- [SPA](https://fantasy.premierleague.com/help/rules): no_readable_lines_in_browser_extractor; observed 2026-11-22.

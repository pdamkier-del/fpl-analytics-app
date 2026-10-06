from fpl_v1_1_model.relative_match_importance import (
    normalized_competition_shares_v2,premier_race_multiplier
)

def test_fixed_budget_sum_is_one():
    s=normalized_competition_shares_v2([
        ("prem","prem_late"),("champions-league","semi_final"),("fa-cup","quarter_final")
    ],premier_race_mult=1.0)
    assert abs(sum(s.values())-1.0)<1e-12

def test_elimination_redistributes_remaining_budget():
    a=normalized_competition_shares_v2([
        ("prem","prem_late"),("champions-league","semi_final"),("fa-cup","quarter_final")
    ])
    b=normalized_competition_shares_v2([
        ("prem","prem_late"),("champions-league","semi_final")
    ])
    assert b["prem"]>a["prem"]
    assert b["champions-league"]>a["champions-league"]
    assert abs(sum(b.values())-1.0)<1e-12

def test_direct_race_increases_pl_share_not_total_budget():
    active=[("prem","prem_run_in"),("champions-league","quarter_final")]
    neutral=normalized_competition_shares_v2(active,premier_race_mult=1.0)
    race=normalized_competition_shares_v2(active,premier_race_mult=1.8)
    assert race["prem"]>neutral["prem"]
    assert race["champions-league"]<neutral["champions-league"]
    assert abs(sum(race.values())-1.0)<1e-12

def test_direct_rival_race_multiplier_exceeds_non_rival():
    table={1:80.0,5:64.0,7:58.0,17:33.0}
    direct=premier_race_multiplier(
        position=5,points=63,opponent_position=6,opponent_points=62,
        table_points_by_position=table,games_remaining=5)
    distant=premier_race_multiplier(
        position=5,points=63,opponent_position=12,opponent_points=44,
        table_points_by_position=table,games_remaining=5)
    assert direct>distant>=1.0

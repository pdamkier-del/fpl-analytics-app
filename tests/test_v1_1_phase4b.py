from fpl_v1_1_model.phase4b import FrozenPlayerForecast, player_to_sim_input, build_match_input

def test_fixture_mu_becomes_per_minute_propensity():
    p=FrozenPlayerForecast('p',1,'MID',.8,60,75,15,.3,.4,.2)
    x=player_to_sim_input(p)
    assert abs(x.goal_weight-.6)<1e-12

def test_dc_fixture_mean_converts_to_per90():
    p=FrozenPlayerForecast('p',1,'DEF',.8,45,75,15,.3,0,0,dc_mu=5,dc_alpha=1)
    assert abs(player_to_sim_input(p).dc_mu_90-10)<1e-12

def test_cards_remain_competing():
    p=FrozenPlayerForecast('p',1,'MID',.8,60,75,15,.3,0,0,p_yellow=.1,p_red=.01)
    d=player_to_sim_input(p).discipline
    assert abs(d.none+d.yellow+d.red-1)<1e-12

def test_match_builder():
    p=FrozenPlayerForecast('p',1,'MID',.8,60,75,15,.3,.2,.1)
    m=build_match_input(home_team_id=1,away_team_id=2,lambda_home_goals=1.5,lambda_away_goals=1.0,players=[p])
    assert m.home_team=='1' and m.assist_probability_per_goal==.90

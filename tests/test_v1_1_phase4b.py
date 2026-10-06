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


def test_modern_player_fields_are_forwarded():
    p=FrozenPlayerForecast(
        'p',1,'GKP',.8,60,75,15,.3,.2,.1,
        p_own_goal=.02,bps_background_rate90=4.5,bps_background_sd90=2.0,
        save_bucket_tilts=(0.,.1,.2,.3,.4),penalty_weight=.7,penalty_conversion=.81,
        lambda_saves=3.2,
    )
    x=player_to_sim_input(p)
    assert x.p_own_goal==.02
    assert x.bps_background_rate90==4.5
    assert x.bps_background_sd90==2.0
    assert x.save_bucket_tilts==(0.,.1,.2,.3,.4)
    assert x.penalty_weight==.7
    assert x.penalty_conversion==.81

def test_match_builder_modern_shared_fields():
    p=FrozenPlayerForecast('p',1,'MID',.8,60,75,15,.3,.2,.1)
    m=build_match_input(
        home_team_id=1,away_team_id=2,lambda_home_goals=1.5,lambda_away_goals=1.0,
        players=[p],lambda_home_penalties=.2,lambda_away_penalties=.1,
        home_penalty_conversion=.8,away_penalty_conversion=.75,
        p_penalty_save_given_miss=.7,bps_rules='2025-26')
    assert m.lambda_home_penalties==.2
    assert m.lambda_away_penalties==.1
    assert m.p_penalty_save_given_miss==.7
    assert m.bps_rules=='2025-26'

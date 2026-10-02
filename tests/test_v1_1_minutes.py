from fpl_v1_1_model.minutes import project_minutes

def test_recent_fixture_gets_more_weight():
    hist=[{"started":1,"minutes":90},{"started":0,"minutes":0}]
    p=project_minutes(hist,role_half_life=1.0,duration_half_life=1.5)
    assert p.p_start < 0.5
    assert p.expected_minutes < 45

def test_all_recent_starts_projects_regular():
    hist=[{"started":1,"minutes":90} for _ in range(5)]
    p=project_minutes(hist)
    assert p.p_start == 1.0
    assert p.expected_minutes == 90.0
    assert p.p_60 == 1.0

def test_cameo_is_conditional_on_bench():
    hist=[{"started":0,"minutes":20},{"started":0,"minutes":0}]
    p=project_minutes(hist,role_half_life=1.0)
    assert 0 < p.p_cameo_given_bench < 1
    assert 0 < p.expected_minutes < 20

def test_availability_scales_play_and_minutes_not_role_duration():
    hist=[{"started":1,"minutes":80} for _ in range(3)]
    p=project_minutes(hist,availability=0.5)
    assert p.p_start == 0.5
    assert p.expected_minutes == 40.0
    assert p.expected_minutes_given_start == 80.0

def test_no_previous_season_input_required():
    p=project_minutes([])
    assert p.n_prior_fixtures == 0
    assert 0 <= p.expected_minutes <= 90

def test_optional_start_regularization_softens_extreme_role_probability():
    hist=[{"started":1,"minutes":90} for _ in range(5)]
    raw=project_minutes(hist)
    reg=project_minutes(hist,start_logit_intercept=0.03,start_logit_slope=0.66)
    assert raw.p_start == 1.0
    assert 0.5 < reg.p_start < 1.0
    assert reg.expected_minutes < raw.expected_minutes

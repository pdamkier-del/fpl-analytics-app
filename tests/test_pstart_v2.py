from fpl_v1_1_model.pstart_v2 import *

def test_dynamic_comp_value_rises_when_competitions_disappear():
    b={'PL':1.0,'CL':1.2,'FA':0.6,'LC':0.4}
    a=dynamic_competition_value('LC',['PL','CL','FA','LC'],b)
    c=dynamic_competition_value('LC',['PL','LC'],b)
    assert c>a

def test_importance_increases_with_round_and_opponent():
    b={'PL':1.0,'LC':0.4}
    lo=match_importance(competition='LC',active_competitions=['PL','LC'],round_strength=.1,opponent_strength=.1,base_values=b)
    hi=match_importance(competition='LC',active_competitions=['PL','LC'],round_strength=.9,opponent_strength=.9,base_values=b)
    assert hi>lo

def test_hierarchy_absence_does_not_count_as_bench_loss():
    h=HierarchyState(9,1); before=h.value
    h.update(started=False,minutes=0,importance=.9,in_matchday_squad=False,half_life=10)
    # only gentle neutral decay of evidence strength; ratio unchanged
    assert abs(h.value-before)<1e-12

def test_exact_team_mass_with_unique_roles():
    mf=MinutesFeatures(.8,.75,.8,.1)
    inp=[]
    # 2 roles, two slots each; enough players
    for n in range(6):
        for role,q in [('A',.6),('B',.4)]:
            inp.append(PlayerRoleInput(str(n),role,q,.6+0.02*n,mf))
    p,a=constrained_start_probabilities(inp,importance=.8,role_capacity={'A':2,'B':2})
    assert abs(sum(p.values())-4)<1e-6
    assert max(p.values())<=1+1e-8

def test_injured_player_keeps_hierarchy_but_gets_zero_current_start_mass():
    mf=MinutesFeatures(.9,.9,.9,.0)
    xs=[
        PlayerRoleInput('first','RW',.9,.95,mf),
        PlayerRoleInput('backup','RW',.7,.70,mf),
        PlayerRoleInput('third','RW',.4,.50,mf),
    ]
    availability={'first':AvailabilityState('injured',0.0),'backup':1.0,'third':1.0}
    p,a=constrained_start_probabilities_deadline(xs,importance=.8,role_capacity={'RW':1.0},availability=availability)
    assert p['first']==0.0
    assert abs(sum(p.values())-1.0)<1e-7
    assert p['backup']>p['third']
    assert xs[0].hierarchy==.95  # injury did not mutate H


def test_doubtful_player_start_probability_cannot_exceed_availability_cap():
    mf=MinutesFeatures(.9,.9,.9,.0)
    xs=[PlayerRoleInput('a','ST',.9,.95,mf),PlayerRoleInput('b','ST',.8,.8,mf)]
    p,_=constrained_start_probabilities_deadline(xs,importance=.7,role_capacity={'ST':1.0},availability={'a':.35,'b':1.0})
    assert p['a']<=.35+1e-8
    assert abs(sum(p.values())-1.0)<1e-7


def test_deadline_state_never_looks_forward():
    rows=[{'observed_at':'2026-09-01T10:00:00+00:00','status':'available'},
          {'observed_at':'2026-09-03T10:00:00+00:00','status':'injured'}]
    r=deadline_state_before(rows,'2026-09-02T12:00:00+00:00')
    assert r['status']=='available'


def test_expected_minutes_respects_availability_mass():
    # 30% available player cannot receive minutes from the unavailable 70% state.
    xm=expected_minutes_from_start_probability(.20,expected_minutes_if_start=80,
        p_cameo_if_bench=.5,expected_minutes_if_cameo=20,availability_cap=.30)
    assert abs(xm-(.20*80+.10*.5*20))<1e-9

def test_cold_start_prior_fades_with_new_team_evidence():
    prior=ColdStartPrior(q_role=.80,hierarchy_role=.90,prior_equivalent_matches=4.0)
    # Before debut, prior is the state.
    q0,h0=blend_role_state_with_cold_prior(q_observed=0.0,q_evidence=0.0,
        hierarchy_observed=0.0,hierarchy_evidence=0.0,prior=prior)
    assert abs(q0-.80)<1e-12 and abs(h0-.90)<1e-12
    # With eight matches of contradictory new-team evidence, observed data dominates.
    q1,h1=blend_role_state_with_cold_prior(q_observed=.20,q_evidence=8.0,
        hierarchy_observed=.30,hierarchy_evidence=8.0,prior=prior)
    assert q1 < .50
    assert h1 < .55
    assert q1 > .20 and h1 > .30


def test_transfer_context_has_no_effect_without_fitted_coefficients():
    # Zero coefficients mean fee/expectation cannot silently affect hierarchy.
    a=transfer_context_hierarchy_prior(previous_start_share=.9,previous_minutes_share=.9,
        fee_percentile_within_club=1.0,expectation_signal=1.0,age=22,
        coefficients=TransferContextCoefficients())
    b=transfer_context_hierarchy_prior(previous_start_share=.1,previous_minutes_share=.1,
        fee_percentile_within_club=0.0,expectation_signal=0.0,age=31,
        coefficients=TransferContextCoefficients())
    assert abs(a-.5)<1e-12 and abs(b-.5)<1e-12

def test_available_status_ignores_stale_chance_cap():
    a=availability_from_status('available',0)
    assert abs(a.cap-1.0)<1e-12
    d=availability_from_status('doubtful',25)
    assert abs(d.cap-0.25)<1e-12
    i=availability_from_status('injured',100)
    assert abs(i.cap-0.0)<1e-12

import math
import pandas as pd
import pytest
from fpl_v1_1_model.experimental_penalty_neutral import remove_penalty_xg,occurrence_probability


def test_occurrence_is_poisson_at_least_one_not_rate():
    assert occurrence_probability(0)==0
    assert occurrence_probability(.2)==pytest.approx(1-math.exp(-.2))
    assert 0<occurrence_probability(3)<1
    for bad in [-1,float('nan'),float('inf')]:
        with pytest.raises(ValueError):occurrence_probability(bad)


def test_misses_and_goals_both_leave_the_ordinary_xg_channel():
    h=pd.DataFrame([dict(season='s',fixture_uuid=f,player_uuid='p',xg=x)for f,x in [('scored',.84),('missed',.85),('none',.37)]])
    a=pd.DataFrame([dict(season='s',fixture_uuid=f,player_uuid='p',attempts=1)for f in ['scored','missed']])
    out=remove_penalty_xg(h,a)
    assert list(out.xg)==pytest.approx([.05,.06,.37])
    assert list(h.xg)==[.84,.85,.37]
    assert list(out.inclusive_xg)==[.84,.85,.37]


def test_multiple_penalties_and_source_errors_are_not_silently_imputed():
    h=pd.DataFrame([dict(season='s',fixture_uuid='f',player_uuid='p',xg=1.7)])
    a=pd.DataFrame([dict(season='s',fixture_uuid='f',player_uuid='p',attempts=2)])
    assert remove_penalty_xg(h,a).xg.iloc[0]==pytest.approx(.12)
    for data in [a.assign(player_uuid='unknown'),pd.concat([a,a]),a.assign(attempts=-1),a.assign(attempts=.5)]:
        with pytest.raises(ValueError):remove_penalty_xg(h,data)
    with pytest.raises(ValueError):remove_penalty_xg(h.assign(xg=.5),a)
    with pytest.raises(ValueError):remove_penalty_xg(h.assign(xg=None),a)


def role_fixture():
    from fpl_v1_1_model.role_event_priors import QCOLS
    common=dict(season='s',fixture_uuid='old',team_id=1,gw=1,kickoff_at='2025-01-01T12:00:00Z',available_at='2025-01-01T15:00:00Z',fpl_position='MID',minutes=90,xa=.1,defcon_count=2)
    history=pd.DataFrame([dict(common,player_uuid='taker',xg=.79),dict(common,player_uuid='other',xg=.5)])
    q={c:float(c=='q_CM_slow')for c in QCOLS}
    roles=pd.DataFrame([dict(fixture_uuid='old',player_uuid=p,team_id=1,cutoff='2025-01-01T09:00:00Z',max_history_known_at='2024-12-30T15:00:00Z',**q)for p in ['taker','other']])
    target=pd.DataFrame([dict(fixture_uuid='new',player_uuid=p,team_id=1,pos='MID',cutoff='2025-01-03T09:00:00Z',max_history_known_at='2025-01-01T15:00:00Z',**q)for p in ['taker','other','new-player']])
    return history,roles,target


def test_goal_only_projection_reproduces_existing_role_pool_without_dc_imputation():
    from fpl_v1_1_model.role_event_priors import role_priors_at_deadline
    from fpl_v1_1_model.experimental_penalty_neutral import goal_role_priors
    h,r,t=role_fixture();cut=pd.Timestamp(t.cutoff.iloc[0])
    original=role_priors_at_deadline(h,r,t[['fixture_uuid','player_uuid','team_id','pos']],t,cut,900)
    got=goal_role_priors(h.drop(columns=['xa','defcon_count']),r,t,cut)
    for p in original.itertuples():assert got[p.fixture_uuid,p.player_uuid]==pytest.approx(p.goal_role_prior90,abs=1e-12)


def test_penalty_free_population_prior_also_applies_to_new_players_and_respects_cutoff():
    from fpl_v1_1_model.experimental_penalty_neutral import PenaltyNeutralState
    h,r,t=role_fixture();a=pd.DataFrame([dict(season='s',fixture_uuid='old',player_uuid='taker',attempts=1)])
    attack={'goal':{'recency_half_life':14.3,'current_season_position_prior_minutes_tau':340.}}
    baseline=PenaltyNeutralState(h,a,r,attack);factors,audit=baseline.factors(t,t.cutoff.iloc[0],'s')
    assert 0<=factors['new','taker']<factors['new','other']<=1
    assert 0<factors['new','new-player']<1
    future=h.copy().assign(fixture_uuid='future',kickoff_at='2025-01-04T12:00:00Z',available_at='2025-01-04T15:00:00Z',xg=10.)
    after=PenaltyNeutralState(pd.concat([h,future],ignore_index=True),a,r,attack).factors(t,t.cutoff.iloc[0],'s')[0]
    assert after==factors
    with pytest.raises(ValueError):baseline.factors(t.assign(max_history_known_at='2025-01-05T00:00:00Z'),t.cutoff.iloc[0],'s')


def test_penalty_goal_budget_uses_ranked_active_takers_and_substitution_times():
    from dataclasses import replace
    from fpl_v1_1_model.joint_simulator import MatchSimInput,PlayerSimInput
    from fpl_v1_1_model.experimental_penalty_neutral import conditional_penalty_conversion
    first=PlayerSimInput('one','H','MID',1.,0.,30.,0.,penalty_order=1,penalty_weight=1.,penalty_conversion=1.)
    second=replace(first,player_id='two',penalty_order=2,penalty_weight=100.,penalty_conversion=0.)
    off=replace(first,player_id='off',penalty_order=1)
    inp=MatchSimInput('H','A',2.,1.,(first,second,off),experimental_penalty_hierarchy=True)
    intervals={'one':(0,30),'two':(0,90),'off':(90,90)}
    assert conditional_penalty_conversion(inp,intervals,'H')==pytest.approx(1/3)
    assert conditional_penalty_conversion(replace(inp,experimental_penalty_hierarchy=False),intervals,'H')==pytest.approx(1/(3*101))
    assert conditional_penalty_conversion(inp,intervals,'A')==0


def test_conditional_penalty_mode_rejects_impossible_team_goal_budget():
    import numpy as np
    from fpl_v1_1_model.joint_simulator import MatchSimInput,PlayerSimInput,simulate_match
    first=PlayerSimInput('one','H','MID',1.,0.,90.,0.,goal_weight=1.,penalty_weight=1.,penalty_conversion=1.)
    inp=MatchSimInput('H','A',0.,0.,(first,),lambda_home_penalties=.1,experimental_conditional_penalties=True)
    with pytest.raises(ValueError,match='budget'):simulate_match(inp,np.random.default_rng(1))


def test_conditional_subtraction_preserves_team_goal_mean_and_penalty_consequences(monkeypatch):
    from dataclasses import replace
    import numpy as np
    import fpl_v1_1_model.joint_simulator as joint
    # Fixed whole-match players isolate event arithmetic from minutes.
    monkeypatch.setattr(joint,'_sample_minutes',lambda rng,p:(90,0,90))
    shooter=joint.PlayerSimInput('s','H','MID',1.,0.,90.,0.,goal_weight=1.,penalty_weight=1.,penalty_conversion=0.)
    keeper=joint.PlayerSimInput('k','A','GK',1.,0.,90.,0.,is_keeper=True)
    inp=joint.MatchSimInput('H','A',1.,0.,(shooter,keeper),lambda_home_penalties=.5,home_penalty_conversion=1.,p_penalty_save_given_miss=1.,experimental_conditional_penalties=True)
    rng=np.random.default_rng(83927);goals=[];misses=[]
    for _ in range(3000):
        r=joint.simulate_match(inp,rng);goals.append(r['s'].goals);misses.append(r['s'].penalty_miss)
        assert r['s'].penalty_miss==r['k'].penalty_saves==r['k'].saves
        assert r['s'].penalty_goals==0
    assert np.mean(goals)==pytest.approx(1.,abs=.065)
    assert np.mean(misses)==pytest.approx(.5,abs=.045)
    # The all-successful taker uses the same inclusive goal budget.
    inp=replace(inp,players=(replace(shooter,penalty_conversion=1.),keeper))
    goals=[];pens=[]
    for _ in range(3000):
        r=joint.simulate_match(inp,rng);goals.append(r['s'].goals);pens.append(r['s'].penalty_goals)
        assert r['s'].penalty_miss==r['k'].penalty_saves==0
    assert np.mean(goals)==pytest.approx(1.,abs=.065)
    assert np.mean(pens)==pytest.approx(.5,abs=.045)


def test_promotion_cannot_enable_failed_candidate_or_unvalidated_np_correction(tmp_path):
    import json,hashlib
    from penalty_policy import load
    d=tmp_path/'decision.json';p=tmp_path/'protocol.json';policy=tmp_path/'policy.json'
    d.write_text(json.dumps(dict(passed=True,fixtures=501,baseline_max_xp_error=0)))
    p.write_text(json.dumps(dict(conditional_only=True,conditional_penalties=True)))
    def write(**changes):
        v=dict(version='conditional-penalties-v1',approved=True,nonpenalty_scorer_correction=False,decision='decision.json',protocol='protocol.json',sha256={n:hashlib.sha256((tmp_path/n).read_bytes()).hexdigest()for n in ['decision.json','protocol.json']});v.update(changes);policy.write_text(json.dumps(v))
    write();assert load(tmp_path,policy)['approved']is True
    for changes in [dict(approved=False),dict(nonpenalty_scorer_correction=True)]:
        write(**changes)
        with pytest.raises(ValueError):load(tmp_path,policy)
    write();d.write_text(json.dumps(dict(passed=False,fixtures=501,baseline_max_xp_error=0)))
    with pytest.raises(ValueError):load(tmp_path,policy)
    write()
    with pytest.raises(ValueError,match='historical gate'):load(tmp_path,policy)


def test_np_head_is_invariant_to_adding_a_penalty_to_inclusive_history():
    from fpl_v1_1_model.experimental_penalty_neutral import PenaltyNeutralState
    from fpl_v1_1_model.experimental_nonpenalty_allocation import allocate,FEATURES
    import numpy as np
    h,roles,target=role_fixture();h['xg']=[.2,.5]
    no_events=pd.DataFrame(columns=['season','fixture_uuid','player_uuid','attempts']).astype({'attempts':float})
    event=pd.DataFrame([dict(season='s',fixture_uuid='old',player_uuid='taker',attempts=1.)])
    changed=h.copy();changed.loc[changed.player_uuid.eq('taker'),'xg']+=.79
    attack={'goal':{'recency_half_life':11.,'current_season_position_prior_minutes_tau':590.}}
    model=dict(columns=FEATURES,coef=[.1,.2],mean=[0.,0.],scale=[1.,1.])
    a=allocate(PenaltyNeutralState(h,no_events,roles,attack),target,target.cutoff.iloc[0],'s',model)
    b=allocate(PenaltyNeutralState(changed,event,roles,attack),target,target.cutoff.iloc[0],'s',model)
    assert np.allclose(a.ordinary_goal_weight,b.ordinary_goal_weight,atol=1e-12,rtol=0)
    assert np.allclose(a.nonpenalty_role_prior90,b.nonpenalty_role_prior90,atol=1e-12,rtol=0)
    assert np.allclose(a[FEATURES],b[FEATURES],atol=1e-12,rtol=0)


def test_independent_penalty_fallback_does_not_change_with_ordinary_scorer_weights(monkeypatch):
    import numpy as np
    from dataclasses import replace
    import fpl_v1_1_model.joint_simulator as joint
    from fpl_v1_1_model.experimental_penalty_neutral import conditional_penalty_conversion
    monkeypatch.setattr(joint,'_sample_minutes',lambda rng,p:(90,0,90))
    a=joint.PlayerSimInput('a','H','MID',1.,0.,90.,0.,goal_weight=10.,penalty_fallback_weight=1.,penalty_conversion=.9)
    b=replace(a,player_id='b',goal_weight=1.,penalty_fallback_weight=2.,penalty_conversion=.5)
    inp=joint.MatchSimInput('H','A',2.,0.,(a,b),lambda_home_penalties=.5,experimental_conditional_penalties=True)
    changed=replace(inp,players=(replace(a,goal_weight=.01),replace(b,goal_weight=100.)))
    intervals={'a':(0,90),'b':(0,90)}
    assert conditional_penalty_conversion(inp,intervals,'H')==conditional_penalty_conversion(changed,intervals,'H')
    for seed in range(100):
        left=joint.simulate_match(inp,np.random.default_rng(seed));right=joint.simulate_match(changed,np.random.default_rng(seed))
        for pid in ['a','b']:
            assert (left[pid].penalty_goals,left[pid].penalty_miss)==(right[pid].penalty_goals,right[pid].penalty_miss)


def test_np_short_form_does_not_treat_a_rest_or_future_match_as_bad_performance():
    from fpl_v1_1_model.experimental_nonpenalty_allocation import recent_features
    h,_,t=role_fixture();cut=t.cutoff.iloc[0]
    baseline=recent_features(h,t,cut)
    rested=h.assign(fixture_uuid='rest',kickoff_at='2025-01-02T12:00:00Z',available_at='2025-01-02T15:00:00Z',minutes=0,xg=0.)
    future=h.assign(fixture_uuid='future',kickoff_at='2025-01-04T12:00:00Z',available_at='2025-01-04T15:00:00Z',xg=5.)
    pd.testing.assert_frame_equal(baseline,recent_features(pd.concat([h,rested,future],ignore_index=True),t,cut))


def test_np_publication_gate_rejects_inclusive_performance_coefficients(tmp_path):
    import json,hashlib
    from nonpenalty_goal_bridge import load
    model=tmp_path/'model.json';decision=tmp_path/'decision.json';policy=tmp_path/'policy.json'
    m=dict(version='nonpenalty-goal-head-v1',training_min_gw=16,training_max_gw=21,allocation=dict(columns=['np_last_xg','np_recent3_xg']))
    model.write_text(json.dumps(m));decision.write_text(json.dumps(dict(passed=True,fixtures=341,baseline_max_xp_error=0)))
    def write():
        policy.write_text(json.dumps(dict(version='nonpenalty-goal-head-v1',approved=True,model='model.json',decision='decision.json',sha256={n:hashlib.sha256((tmp_path/n).read_bytes()).hexdigest()for n in ['model.json','decision.json']})))
    write();assert load(tmp_path,policy)[0]['version']=='nonpenalty-goal-head-v1'
    m['allocation']['columns']=['perf_last_xgi','np_recent3_xg'];model.write_text(json.dumps(m));write()
    with pytest.raises(ValueError,match='Blended'):load(tmp_path,policy)


def test_full_snapshot_accepts_coherent_np_penalty_summary_and_rejects_impossible_player_chance():
    from test_unified_b_chain import unified_fixture
    from b_chain_contract import validate_forecast
    f,_=unified_fixture();f['nonpenalty_goal_head']={'version':'nonpenalty-goal-head-v1'}
    # This legal synthetic snapshot has no per-fixture scoring fields; add an
    # explicit zero-scoring fixture to exercise the real snapshot validator.
    fixture={'fixture_uuid':'f','xmins':0.,'pm_analytic_minutes':0.,'components':{'goal_points':0.},'penalty_miss_points_subset_of_negative':0.,'penalty':dict(expected_nonpenalty_goals=0.,expected_penalty_goals=0.,expected_missed_penalties=0.,p_takes_penalty=0.,p_scores_penalty=0.,team_p_at_least_one=.09,team_simulated_p_at_least_one=.1)}
    # Preserve the fixture factory's existing analytic minute totals.
    for p in f['players']:
        for w in p['weeks']:
            for x in w['fixtures']:
                x.update(components={'goal_points':0.},penalty_miss_points_subset_of_negative=0.,penalty=dict(fixture['penalty']))
    assert validate_forecast(f)
    first=f['players'][0]['weeks'][0]['fixtures'][0];first['penalty']['p_takes_penalty']=.2
    with pytest.raises(ValueError,match='penalty probabilities'):validate_forecast(f)

from dataclasses import replace
import numpy as np
import pytest
from fpl_v1_1_model.experimental_pm_conversion import gamma_mean,event_weights,marginal_pair_probabilities,independent_pair_probabilities,shadow_joint_assists
from fpl_v1_1_model.joint_simulator import MatchSimInput,PlayerSimInput,simulate_many


def example():
    return MatchSimInput('h','a',2.,1.,tuple(PlayerSimInput(str(i),'h' if i<3 else 'a','MID',1.,0.,90.,10.,goal_weight=1.,assist_weight=1.) for i in range(6)),lambda_home_penalties=.2,home_penalty_conversion=.8)


def test_small_finishing_sample_shrinks_and_cold_start_is_prior():
    assert gamma_mean(8,5,50)==pytest.approx(58/55)
    assert gamma_mean(0,0,50,1.2)==pytest.approx(1.2)
    with pytest.raises(ValueError):gamma_mean(1,-1,5)


def test_fixed_total_and_penalty_parameters_are_unchanged():
    inp=example();out=event_weights(inp,{'0':2.},{'1':.5})
    assert out.lambda_home_goals==inp.lambda_home_goals and out.lambda_away_goals==inp.lambda_away_goals
    assert out.players[0].goal_weight==2 and out.players[1].assist_weight==.5
    assert inp.players[0].goal_weight==1 and out.lambda_home_penalties==.2


def test_total_mode_applies_finishing_once_to_ordinary_goal_budget():
    inp=example();out=event_weights(inp,{str(i):2. for i in range(6)},change_total=True)
    assert out.lambda_home_goals==pytest.approx((2-.16)*2+.16)
    assert out.home_penalty_conversion==inp.home_penalty_conversion


def test_joint_has_legal_and_exact_marginals_without_self_assist():
    g=np.array([.4,.3,.3]);a=np.array([.25,.35,.4]);q=marginal_pair_probabilities(g,a)
    np.testing.assert_allclose(q.sum(0),g,atol=1e-9);np.testing.assert_allclose(q.sum(1),a,atol=1e-9)
    assert not np.diag(q).any()
    assert not np.allclose(independent_pair_probabilities(g,a).sum(1),a)
    with pytest.raises(ValueError):marginal_pair_probabilities([.9,.1],[.8,.2])


def test_disabled_candidates_are_draw_for_draw_identical_and_context_restores():
    from fpl_v1_1_model import joint_simulator as sim
    inp=example();base=simulate_many(inp,n=30,seed=42)
    with shadow_joint_assists(False):assert simulate_many(event_weights(inp),n=30,seed=42)==base
    original=sim._weighted_choice
    with pytest.raises(RuntimeError):
        with shadow_joint_assists():raise RuntimeError('test')
    assert sim._weighted_choice is original


def test_shared_assist_candidate_preserves_team_scoring_and_no_unscored_assists():
    from fpl_v1_1_model import joint_simulator as sim
    inp=example();rng=np.random.default_rng(17)
    with shadow_joint_assists() as d:
        for _ in range(50):
            r=sim.simulate_match(inp,rng)
            for team in ['h','a']:
                ids=[p.player_id for p in inp.players if p.team==team]
                assert sum(r[i].assists for i in ids)<=sum(r[i].goals for i in ids)
    assert d['applied']>0


def test_event_observer_is_draw_identical_and_restores_simulator():
    from replay_pm_conversion import simulate_observed
    from fpl_v1_1_model import joint_simulator as sim
    inp=example();expected=sim.simulate_many(inp,n=40,seed=77);original=sim.simulate_match
    observed=simulate_observed(inp,77,draws=40)
    for pid,row in expected.items():
        for k,v in row.items():assert observed[pid][k]==v
        assert 0<observed[pid]['p_goal']<1
        assert 0<observed[pid]['p_assist']<1
    assert sim.simulate_match is original


def test_history_excludes_future_and_team_ids_do_not_cross_seasons():
    import pandas as pd
    from research_pm_conversion import weighted_states
    rows=[dict(player_uuid='a',team_id=6,fpl_position='FWD',season='2023-24',known=pd.Timestamp('2024-01-01',tz='UTC'),goals=3.,xg=1.,fpl_assists=1.,xa=1.,minutes=90.),dict(player_uuid='b',team_id=6,fpl_position='FWD',season='2024-25',known=pd.Timestamp('2024-09-01',tz='UTC'),goals=1.,xg=2.,fpl_assists=1.,xa=1.,minutes=90.),dict(player_uuid='b',team_id=6,fpl_position='FWD',season='2024-25',known=pd.Timestamp('2024-09-04',tz='UTC'),goals=100.,xg=1.,fpl_assists=1.,xa=1.,minutes=90.)]
    state=weighted_states(pd.DataFrame(rows),pd.Timestamp('2024-09-02',tz='UTC'),'2024-25',None)
    assert state[0].loc['a','goals']==3.
    assert state[1].loc[6,'goals']==1.
    assert state[0].loc['b','goals']==1.


def test_postprocess_groups_do_not_use_target_role_or_future_team_goals():
    import pandas as pd
    from postprocess_pm_conversion import labels
    past=[dict(player_uuid='a',season='2024-25',team_id=6,fixture_uuid=str(i),known=pd.Timestamp('2024-09-01',tz='UTC')+pd.Timedelta(days=i),started=1,minutes=90,goals=1.,fpl_assists=0.,xg=1.) for i in range(6)]
    future=dict(past[-1],fixture_uuid='future',known=pd.Timestamp('2024-10-01',tz='UTC'),started=0,goals=100.)
    record=dict(cutoff='2024-09-20T00:00:00Z',origin=7,core_fixture='target',input={'players':[dict(player_id='a',team='6')]})
    out=labels([record],pd.DataFrame(past+[future]),'2024-25').iloc[0]
    assert out.role=='regular'
    assert out.team_type=='credited_goals_at_or_below_xg'

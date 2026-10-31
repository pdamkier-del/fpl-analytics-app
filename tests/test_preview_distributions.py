"""Preview summaries use the actual PM draws without changing locked results."""
import numpy as np
import fpl_v1_1_model.joint_simulator as sim
from pm_preview_distributions import simulate_with_distributions


def test_preview_probabilities_reconcile_with_actual_draws_and_locked_output(monkeypatch):
    player=sim.PlayerSimInput('rotation','H','MID',.45,.65,72,18,goal_weight=1,assist_weight=1)
    away=sim.PlayerSimInput('away','A','FWD',1,0,90,15,goal_weight=1)
    inp=sim.MatchSimInput('H','A',1.5,1.2,(player,away))
    locked=sim.simulate_many(inp,n=300,seed=19)
    actual=[]
    original=sim.simulate_match
    def capture(*args,**kwargs):
        result=original(*args,**kwargs)
        actual.append(result['rotation'])
        return result
    monkeypatch.setattr(sim,'simulate_match',capture)
    preview=simulate_with_distributions(inp,n=300,seed=19)
    for pid,row in preview.items():
        assert {k:v for k,v in row.items() if k!='distribution'}==locked[pid]
    assert len(actual)==300
    actual=actual[-300:]
    d=preview['rotation']['distribution']
    assert np.isclose(d['p_cameo'],np.mean([r.minutes>0 and not r.started for r in actual]))
    assert np.isclose(d['p_zero']+d['p_cameo']+d['p_start'],1)
    assert np.isclose(sum(d['minute_bins']),1)
    assert 0<=d['p_90']<=d['p_60_plus']<=1-d['p_zero']<=1
    assert d['p_2_plus']==np.mean([r.points>=2 for r in actual])
    assert d['p_5_plus']==np.mean([r.points>=5 for r in actual])
    assert d['p_10_plus']==np.mean([r.points>=10 for r in actual])
    assert d['points_interval80']==list(np.quantile([r.points for r in actual],[.1,.9]))
    assert 0<d['p_start']<1 and 0<d['p_cameo']<1 and 0<d['p_zero']<1


def test_np_penalty_decomposition_reconciles_without_extra_rng():
    player=sim.PlayerSimInput('p','H','MID',1.,0.,90.,0.,goal_weight=1.,penalty_weight=1.,penalty_conversion=.7,penalty_fallback_weight=1.)
    inp=sim.MatchSimInput('H','A',1.5,0.,(player,),lambda_home_penalties=.25,experimental_conditional_penalties=True)
    original=sim.simulate_many(inp,n=200,seed=827)
    result=simulate_with_distributions(inp,n=200,seed=827,include_samples=True)['p'];split=result['penalty_components']
    assert result['xPts']==original['p']['xPts']
    assert split['expected_nonpenalty_goals']+split['expected_penalty_goals']==result['goal_points']/5
    assert -2*split['expected_missed_penalties']==result['penalty_miss_points']
    assert 0<=split['p_scores_penalty']<=split['p_takes_penalty']<=split['team_simulated_p_at_least_one']<=1
    assert np.mean(result['scenarios']['points'])==result['xPts']


def test_single_pass_preserves_joint_role_samples_and_aggregate():
    from fpl_v1_1_model.experimental_joint_role_assignment import RoleLineup,role_lineup_sampler
    players=[];distributions={}
    roles=('RB','RCB','LCB','LB','DM','RCM','LCM','RW','LW','ST')
    for team in ('H','A'):
        ids=tuple(f'{team}{i}'for i in range(11))
        distributions[team]=[RoleLineup(.5,'4-3-3',ids[:10],roles),RoleLineup(.5,'4-3-3',ids[1:],roles)]
        players.extend(sim.PlayerSimInput(pid,team,'MID',.5 if i in (0,10)else 1.,.3,78,15,goal_weight=1,assist_weight=1)for i,pid in enumerate(ids))
    inp=sim.MatchSimInput('H','A',1.4,1.2,tuple(players),experimental_joint_starters=True)
    with role_lineup_sampler(distributions):
        reference=sim.simulate_many(inp,n=50,seed=918)
        rng=np.random.default_rng(918);raw=[sim.simulate_match(inp,rng)for _ in range(50)]
        preview=simulate_with_distributions(inp,n=50,seed=918,include_samples=True)
    for pid,row in preview.items():
        assert {k:v for k,v in row.items()if k not in ('distribution','scenarios')}==reference[pid]
        assert row['scenarios']=={'minutes':[r[pid].minutes for r in raw],'points':[r[pid].points for r in raw]}

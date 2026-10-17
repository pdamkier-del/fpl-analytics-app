from dataclasses import replace
import numpy as np
import pytest
from fpl_v1_1_model.joint_simulator import PlayerSimInput,MatchSimInput,simulate_many
from fpl_v1_1_model.experimental_correctness_simulator import simulate_match,start_marginals,sample_starters,shadow_simulator


def fixture(soft=False):
    players=[]
    for team in ('H','A'):
        specs=[('GK',2,.5),('DEF',6,.65),('MID',8,.55),('FWD',3,1.7/3)] if soft else [('GK',1,1),('DEF',4,1),('MID',4,1),('FWD',2,1)]
        for pos,count,p in specs:
            players.extend(PlayerSimInput(f'{team}-{pos}-{i}',team,pos,p,0 if not soft else .5,80,20,goal_weight=1,assist_weight=1,is_keeper=pos=='GK') for i in range(count))
    return MatchSimInput('H','A',1.5,1.3,tuple(players))


def test_thousands_of_joint_xis_and_calibrated_marginals():
    inp=fixture(True);marginal,diag=start_marginals(inp);rng=np.random.default_rng(713)
    counts={p.player_id:0 for p in inp.players}
    for _ in range(5000):
        chosen=sample_starters(inp,rng)
        assert len(chosen)==22
        for team in ['H','A']:
            selected=[p for p in inp.players if p.team==team and p.player_id in chosen]
            assert len(selected)==11 and sum(p.is_keeper for p in selected)==1
        for pid in chosen:counts[pid]+=1
    assert max(abs(counts[k]/5000-v) for k,v in marginal.items())<.035
    assert max(d['max_abs_marginal_change'] for d in diag.values())<1e-10


def test_joint_intervals_have_no_keeper_or_position_slot_overlap():
    inp=fixture(True);rng=np.random.default_rng(714)
    for _ in range(150):
        trace={};res=simulate_match(inp,rng,trace=trace)
        for team in ['H','A']:
            assert sum(r.started for p in inp.players if p.team==team for r in [res[p.player_id]])==11
            bench_intervals=[trace['intervals'][p.player_id] for p in inp.players if p.team==team and not res[p.player_id].started and res[p.player_id].minutes>0]
            assert len(bench_intervals)<=5
            assert len({a for a,b in bench_intervals if a!=45})<=3
            for t in np.arange(0,90,.5):
                active=[p for p in inp.players if p.team==team and trace['intervals'][p.player_id][0]<=t<trace['intervals'][p.player_id][1]]
                assert len(active)<=11 and sum(p.is_keeper for p in active)<=1
                slots=[trace['slot_assignments'][p.player_id] for p in active]
                assert len(slots)==len(set(slots))


def test_own_goal_denies_clean_sheet_and_credits_no_scorer_or_assist():
    inp=fixture();players=tuple(replace(p,p_own_goal=1 if p.player_id=='H-DEF-0' else 0) for p in inp.players)
    inp=replace(inp,players=players,lambda_home_goals=0,lambda_away_goals=1)
    trace={};res=simulate_match(inp,np.random.default_rng(715),trace=trace)
    t,team,committer=trace['own_goal_events'][0]
    assert team=='A' and committer=='H-DEF-0'
    assert res[committer].own_goal==1 and res[committer].clean_sheet==0 and res[committer].goals_conceded_while_on_pitch==1
    assert not sum(r.goals+r.assists for r in res.values())
    assert trace['ordinary_intensity']=={'H':0,'A':0}
    assert all(r.clean_sheet==0 for p in players if p.team=='H' for r in [res[p.player_id]] if trace['intervals'][p.player_id][0]<=t<trace['intervals'][p.player_id][1])


def test_two_own_goals_apply_conceded_and_negative_points():
    inp=fixture();players=tuple(replace(p,start_minutes_mean=90,p_own_goal=int(p.player_id in ['H-DEF-0','H-DEF-1'])) for p in inp.players)
    res=simulate_match(replace(inp,players=players,lambda_home_goals=0,lambda_away_goals=2),np.random.default_rng(716))
    assert res['H-GK-0'].goals_conceded_while_on_pitch==2
    assert res['H-GK-0'].clean_sheet==0
    assert res['H-DEF-0'].own_goal==1 and res['H-DEF-1'].own_goal==1
    assert res['H-DEF-0'].points-res['H-DEF-0'].bonus==-1 # appearance 2, conceded -1, own goal -2


def test_own_goal_only_concedes_to_overlapping_players_and_penalties_share_total():
    a=PlayerSimInput('og','H','DEF',1,0,30,10,p_own_goal=1)
    b=PlayerSimInput('bench','H','DEF',0,1,0,15)
    c=PlayerSimInput('pen','A','FWD',1,0,90,0,goal_weight=1,penalty_weight=1,penalty_conversion=1)
    inp=MatchSimInput('H','A',0,2,(a,b,c),lambda_away_penalties=.5,away_penalty_conversion=1)
    trace={};res=simulate_match(inp,np.random.default_rng(717),joint_xi=False,trace=trace)
    t=trace['own_goal_events'][0][0]
    assert trace['intervals']['og'][0]<=t<trace['intervals']['og'][1]
    expected=sum(trace['intervals']['bench'][0]<=time<trace['intervals']['bench'][1] for time,team,_,_ in trace['goal_events'] if team=='A')
    assert res['bench'].goals_conceded_while_on_pitch==expected
    assert trace['ordinary_intensity']['A']==pytest.approx(2-1-.5*res['pen'].minutes/90)


def test_total_goal_expectation_is_not_inflated_by_own_goals_or_penalties():
    a=PlayerSimInput('h','H','DEF',1,0,90,0,goal_weight=1,penalty_weight=1,penalty_conversion=.8,p_own_goal=.2)
    b=replace(a,player_id='a',team='A',p_own_goal=.1)
    inp=MatchSimInput('H','A',1.4,1.1,(a,b),lambda_home_penalties=.2,lambda_away_penalties=.3)
    rng=np.random.default_rng(718);counts=[]
    for _ in range(6000):
        trace={};simulate_match(inp,rng,joint_xi=False,trace=trace)
        counts.append([sum(team==side for _,team,_,_ in trace['goal_events']) for side in ['H','A']])
    assert np.allclose(np.mean(counts,axis=0),[1.4,1.1],atol=.06)


def test_infeasible_intensity_and_hard_caps_are_rejected():
    inp=fixture()
    with pytest.raises(ValueError,match='exceed total'):
        simulate_match(replace(inp,lambda_home_goals=0,lambda_away_goals=0,players=tuple(replace(p,p_own_goal=.9) for p in inp.players)),np.random.default_rng(719))
    with pytest.raises(ValueError,match='No legal XI'):
        start_marginals(replace(inp,players=tuple(replace(p,p_start=0) if p.is_keeper else p for p in inp.players)))
    out=PlayerSimInput('out','H','MID',0,0,0,0)
    inp=replace(inp,players=inp.players+(out,))
    res=simulate_match(inp,np.random.default_rng(720));assert res['out'].minutes==0


def test_shadow_is_restored_after_failure_and_baseline_is_unchanged():
    from fpl_v1_1_model import joint_simulator as locked
    original=locked.simulate_match
    with pytest.raises(RuntimeError):
        with shadow_simulator():
            assert locked.simulate_match is not original
            raise RuntimeError('test')
    assert locked.simulate_match is original
    inp=fixture();a=simulate_many(inp,n=20,seed=721)
    with shadow_simulator():simulate_many(inp,n=20,seed=721)
    assert a==simulate_many(inp,n=20,seed=721)


def test_false_nine_does_not_force_lone_fpl_striker_to_start():
    inp=fixture(True)
    # Exactly ten outfield expected starters but only 0.8 FWD expected starters.
    # A club false nine is valid; no FPL manager formation rule is imposed.
    players=[]
    for team in ['H','A']:
        players.extend(PlayerSimInput(f'{team}-{pos}-{i}',team,pos,p,0,80,20,is_keeper=pos=='GK') for pos,n,p in [('GK',2,.5),('DEF',6,.7),('MID',8,.625),('FWD',1,.8)] for i in range(n))
    marginal,diag=start_marginals(replace(inp,players=tuple(players)))
    assert marginal['H-FWD-0']==pytest.approx(.8)
    assert diag['H']['max_abs_marginal_change']<1e-10


@pytest.mark.parametrize('season',['2024-25','2025-26','2026-27'])
def test_disabled_candidate_is_draw_for_draw_identical_to_locked_scoring(season):
    from fpl_v1_1_model import joint_simulator as locked
    inp=replace(fixture(True),bps_rules=season,lambda_home_penalties=.2,lambda_away_penalties=.3,players=tuple(replace(p,p_own_goal=.01,dc_mu_90=8,bps_background_rate90=3,bps_background_sd90=2,penalty_weight=1,penalty_conversion=.7) for p in fixture(True).players))
    for seed in range(30):
        a=locked.simulate_match(inp,np.random.default_rng(seed))
        b=simulate_match(inp,np.random.default_rng(seed),own_goals=False,joint_xi=False)
        assert a==b


@pytest.mark.parametrize('field,value',[('p_start',float('nan')),('p_cameo_given_bench',1.1),('p_own_goal',-.1)])
def test_invalid_probabilities_do_not_enter_candidate(field,value):
    inp=fixture();players=(replace(inp.players[0],**{field:value}),)+inp.players[1:]
    with pytest.raises(ValueError,match='Invalid player probability'):
        simulate_match(replace(inp,players=players),np.random.default_rng(722))


def test_own_goal_timestamp_is_inside_half_open_interval_even_at_float_boundary():
    class BoundaryRng:
        def __init__(self):self.base=np.random.default_rng(723)
        def __getattr__(self,name):return getattr(self.base,name)
        def normal(self,mean,sd):return mean
        def uniform(self,low,high):return high
    inp=fixture();inp=replace(inp,lambda_home_goals=0,lambda_away_goals=1,players=tuple(replace(p,p_own_goal=int(p.player_id=='H-DEF-0')) for p in inp.players))
    trace={};res=simulate_match(inp,BoundaryRng(),trace=trace)
    t,_,pid=trace['own_goal_events'][0];a,b=trace['intervals'][pid]
    assert a<=t<b
    assert res[pid].own_goal==1 and res[pid].goals_conceded_while_on_pitch==1 and res[pid].clean_sheet==0

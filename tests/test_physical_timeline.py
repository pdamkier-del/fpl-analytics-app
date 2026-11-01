from dataclasses import replace
from types import SimpleNamespace
import numpy as np
import pytest

from fpl_v1_1_model import joint_simulator as sim
from fpl_v1_1_model.experimental_physical_timeline import (
    PhysicalKernel,decompose_starts,physical_sampler,validate_timeline)


def fixture():
    ps=[]
    for team in ['H','A']:
        ps.extend([
            sim.PlayerSimInput(team+'GK',team,'GKP',1,0,88,10,is_keeper=True),
            sim.PlayerSimInput(team+'reserveGK',team,'GKP',0,1,90,10,is_keeper=True)])
        ps.extend(sim.PlayerSimInput(team+str(j).zfill(2),team,['DEF','MID','FWD'][j%3],.5,.4,72,20,
                   goal_weight=1,assist_weight=1)for j in range(20))
        ps.append(sim.PlayerSimInput(team+'unavailable',team,'MID',0,0,70,15))
    return sim.MatchSimInput('H','A',1.5,1.2,tuple(ps),experimental_joint_goalkeepers=True,
             verified_goalkeeper_roster_teams=('H','A'),experimental_joint_starters=True,
             experimental_mean_preserving_minutes=True)


def test_exact_start_decomposition_and_endpoint_preservation():
    p=np.array([1]*3+[.5]*14+[0]*3,float)
    rows=decompose_starts([str(i)for i in range(20)],p)
    observed=[sum(w for ids,w in rows if str(i)in ids)for i in range(20)]
    assert observed==pytest.approx(p,abs=1e-10)
    assert sum(w for _,w in rows)==pytest.approx(1)
    assert all(len(ids)==10 and len(set(ids))==10 for ids,_ in rows)


@pytest.mark.parametrize('epsilon',[1e-14,1e-12,1e-10,1e-8,-1e-10])
def test_sub_micro_projection_residual_does_not_break_physical_decomposition(epsilon):
    p=np.array([1.]*9+[.6,.4+epsilon,0.]);ids=list(map(str,range(len(p))))
    rows=decompose_starts(ids,p)
    reconstructed=np.array([sum(w for selected,w in rows if uid in selected)for uid in ids])
    assert reconstructed==pytest.approx(p,abs=1e-6)
    assert sum(w for _,w in rows)==pytest.approx(1,abs=1e-12)
    assert reconstructed[:9]==pytest.approx(np.ones(9),abs=1e-12)
    assert reconstructed[-1]==0


def test_every_draw_has_normal_physical_coverage_and_unavailable_never_plays():
    inp=fixture();kernel=PhysicalKernel(inp);rng=np.random.default_rng(9)
    for _ in range(500):
        timeline=kernel.sample(rng)
        assert validate_timeline(inp,timeline)
        assert timeline['Hunavailable'][0]==timeline['Aunavailable'][0]==0
    for team in ['H','A']:
        moments=[kernel.moments[p.player_id]for p in inp.players if p.team==team and not p.is_keeper]
        assert sum(q['x']for q in moments)==pytest.approx(900,abs=1e-7)
        assert sum(q['p']for q in moments)==pytest.approx(10)
        for q in moments:
            assert q['p']*q['s']+(1-q['p'])*q['q']*q['c']==pytest.approx(q['x'],abs=1e-8)
            assert 0<=q['p90']<=q['p60']<=q['p_play']<=1


def test_same_role_mixture_is_retained_and_input_order_is_irrelevant():
    inp=fixture();dist={}
    for t in ['H','A']:
        ids=sorted(p.player_id for p in inp.players if p.team==t and not p.is_keeper and p.p_start>0)
        dist[t]=[SimpleNamespace(players=tuple(ids[:10]),weight=.5),SimpleNamespace(players=tuple(ids[10:]),weight=.5)]
    a=PhysicalKernel(inp,dist);b=PhysicalKernel(replace(inp,players=tuple(reversed(inp.players))),dist)
    assert a.moments==b.moments
    assert all(q['p']==pytest.approx(.5) for uid,q in a.moments.items()if 'unavailable'not in uid)
    dist['H'][0].weight=.6
    with pytest.raises(ValueError,match='weights'):PhysicalKernel(inp,dist)


def test_analytical_moments_match_same_timeline_sampling_law():
    inp=fixture();kernel=PhysicalKernel(inp);rng=np.random.default_rng(123)
    draws=np.array([[v[0]for _,v in sorted(kernel.sample(rng).items())]for _ in range(6000)])
    uids=sorted(p.player_id for p in inp.players)
    for j,uid in enumerate(uids):
        if uid not in kernel.moments:continue
        expected=kernel.moments[uid]['x'];observed=draws[:,j]
        assert abs(observed.mean()-expected)<=6*observed.std(ddof=1)/np.sqrt(len(observed))+1e-8


def test_simulator_consumes_same_timeline_and_scope_restores_on_error():
    inp=fixture();kernel=PhysicalKernel(inp);original=sim.simulate_match
    with physical_sampler(kernel):
        a=sim.simulate_many(inp,n=20,seed=7)
        b=sim.simulate_many(inp,n=20,seed=7)
        assert a==b
        for team in ['H','A']:
            assert sum(a[p.player_id]['expected_minutes']for p in inp.players if p.team==team and not p.is_keeper)==pytest.approx(900)
    assert sim.simulate_match is original
    with pytest.raises(RuntimeError):
        with physical_sampler(kernel):raise RuntimeError('interrupt')
    assert sim.simulate_match is original


def test_independent_intervals_with_correct_total_still_fail_active_coverage():
    inp=fixture();kernel=PhysicalKernel(inp);t=kernel.sample(np.random.default_rng(2))
    # Shift a positive interval without changing its length or the 900 sum.
    uid=next(p.player_id for p in inp.players if not p.is_keeper and t[p.player_id][0]<89 and t[p.player_id][0]>0 and t[p.player_id][1]==0)
    m,a,b=t[uid];t[uid]=(m,a+1,b+1)
    with pytest.raises(ValueError):validate_timeline(inp,t)


def planned_swaps(times):
    inp=fixture();timeline={p.player_id:(0,90,90)for p in inp.players}
    for team in ['H','A']:
        timeline[team+'GK']=(90,0,90)
        for j in range(10):timeline[team+str(j).zfill(2)]=(90,0,90)
        for j,t in enumerate(times):
            timeline[team+str(j).zfill(2)]=(t,0,t)
            timeline[team+str(j+10).zfill(2)]=(90-t,t,90)
    return inp,timeline


def test_six_swaps_fail_even_with_exact_900_plus_90_coverage():
    inp,timeline=planned_swaps([60]*6)
    with pytest.raises(ValueError,match='five substitutions'):validate_timeline(inp,timeline)


def test_four_live_windows_fail_but_half_time_is_not_a_live_window():
    inp,timeline=planned_swaps([50,60,70,80])
    with pytest.raises(ValueError,match='three substitution windows'):validate_timeline(inp,timeline)
    inp,timeline=planned_swaps([45,60,70,80])
    assert validate_timeline(inp,timeline)


def test_goalkeeper_swap_uses_one_of_the_same_five_slots():
    inp,timeline=planned_swaps([60]*5)
    for team in ['H','A']:
        timeline[team+'GK']=(60,0,60)
        timeline[team+'reserveGK']=(30,60,90)
    with pytest.raises(ValueError,match='five substitutions'):validate_timeline(inp,timeline)


def test_normal_timeline_contract_checks_all_scenarios_not_only_means():
    import copy
    from b_chain_contract import VERSION,SCENARIOS,validate_forecast
    from pm_preview_distributions import simulate_with_distributions
    inp=fixture();kernel=PhysicalKernel(inp)
    with physical_sampler(kernel):result=simulate_with_distributions(inp,n=20,seed=7,include_samples=True)
    f=dict(model=VERSION,scope='prospective_preview',locked_model_active=False,gws=[1],
        minute_sampler_audit=dict(sampler=VERSION,all_MM_to_PM_means_consistent=True),
        scenario_contract=dict(version=SCENARIOS,draws=20),normal_match_timeline=dict(version='B-normal-timeline-v1'),
        gk_team_fixtures=[dict(team=t,fixture_uuid='match',physical_timeline={**kernel.audit,'unlisted_keeper_minutes':[0]*20})for t in ['H','A']],players=[])
    for p in inp.players:
        r=result[p.player_id];mean=kernel.moments[p.player_id]['x']if not p.is_keeper else r['expected_minutes']
        f['players'].append(dict(team_id=p.team,position=1 if p.is_keeper else 3,weeks=[dict(gw=1,
            xpts=r['xPts'],xmins=mean,pm_analytic_minutes=mean,scenarios=r['scenarios'],
            fixtures=[dict(fixture_uuid='match',xmins=mean,pm_analytic_minutes=mean)])]))
    assert validate_forecast(f)
    bad=copy.deepcopy(f)
    row=next(p for p in bad['players']if p['position']!=1)
    row['weeks'][0]['scenarios']['minutes'][0]+=1
    with pytest.raises(ValueError,match='scenario minute coverage'):validate_forecast(bad)
    bad=copy.deepcopy(f);bad['gk_team_fixtures'][0]['physical_timeline']['max_substitutions']=6
    with pytest.raises(ValueError,match='substitution process'):validate_forecast(bad)
    bad=copy.deepcopy(f);bad['gk_team_fixtures'][0]['physical_timeline']['reported_FPL_minutes_required_to_sum_990']=True
    with pytest.raises(ValueError,match='substitution process'):validate_forecast(bad)

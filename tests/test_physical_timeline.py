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

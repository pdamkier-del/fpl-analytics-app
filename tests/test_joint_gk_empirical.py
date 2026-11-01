from dataclasses import replace
import numpy as np
import pandas as pd
import pytest
from fpl_v1_1_model.joint_simulator import MatchSimInput,PlayerSimInput,simulate_match
from gk_joint_bridge import DurationHistory,prepare,marginals,UNKNOWN


def history():
    # Test-only league history, with an explicit short-start tail.
    return pd.DataFrame([dict(player_uuid='known',team_id=1,started=1,minutes=90 if i%20 else 60,
        known_at='2025-01-01T00:00:00Z')for i in range(120)])


def fixture(count=2):
    players=[];rows=[]
    for team in ['1','2']:
        for i in range(count):
            pid=f'{team}k{i}';p=1/count
            players.append(PlayerSimInput(pid,team,'GK',p,.02,78.,15.,is_keeper=True))
            rows.append(dict(player_uuid=pid,p=p,unprojected_p=.7 if count==1 else p,availability_cap=1.))
        for i in range(15):
            players.append(PlayerSimInput(f'{team}f{i}',team,'MID',2/3,.15,75.,20.))
    return MatchSimInput('1','2',1.,1.,tuple(players)),pd.DataFrame(rows)


@pytest.mark.parametrize('count',[1,2,3])
def test_realized_joint_coverage_starts_and_marginals(count):
    inp,rows=fixture(count);duration=DurationHistory(history(),'2025-02-01T00:00:00Z')
    joint,exact,audit=prepare(inp,rows,duration)
    rng=np.random.default_rng(31)
    sums={p.player_id:0 for p in joint.players if p.is_keeper}
    for draw in range(1200):
        trace={} if draw<10 else None
        out=simulate_match(joint,rng,trace=trace)
        for team in ['1','2']:
            keepers=[p for p in joint.players if p.team==team and p.is_keeper]
            assert sum(out[p.player_id].minutes for p in keepers)==90
            if trace is not None:
                for minute in range(90):
                    assert sum(trace['intervals'][p.player_id][0]<=minute<trace['intervals'][p.player_id][1] for p in keepers)==1
            assert sum(out[p.player_id].started for p in keepers)==1
            assert sum(out[p.player_id].started for p in joint.players if p.team==team)==11
        for pid in sums:sums[pid]+=out[pid].minutes/1200
    for pid,v in sums.items():assert v==pytest.approx(exact[pid]['x'],abs=4.)
    assert simulate_match(joint,np.random.default_rng(7))==simulate_match(joint,np.random.default_rng(7))
    assert all(abs(a['analytic_gk_minutes']-90)<1e-9 for a in audit)
    if count==1:
        assert exact['1k0']['p']==.7
        assert exact[UNKNOWN+'1']['p']==pytest.approx(.3)
        assert 0<exact['1k0']['p90']<exact['1k0']['p60']<1


def test_past_only_duration_does_not_use_future_or_nonstarter_minutes():
    obs=history()
    d=DurationHistory(obs,'2025-02-01T00:00:00Z')
    future=pd.DataFrame([dict(player_uuid='new',team_id=1,started=1,minutes=1,known_at='2025-03-01T00:00:00Z'),
                         dict(player_uuid='new',team_id=1,started=0,minutes=15,known_at='2025-01-01T00:00:00Z')])
    z=DurationHistory(pd.concat([obs,future]),'2025-02-01T00:00:00Z')
    assert d.pmf('new',1)==z.pmf('new',1)
    assert d.pmf('new',1)[90]>.9


def test_hard_absence_never_receives_start_or_reserve_minutes():
    inp,rows=fixture(2)
    players=tuple(replace(p,p_start=0.,p_cameo_given_bench=0.)if p.player_id=='1k1'else p for p in inp.players)
    joint,exact,_=prepare(replace(inp,players=players),rows,DurationHistory(history(),'2025-02-01T00:00:00Z'))
    assert exact['1k1']['x']==0
    for seed in range(100):assert simulate_match(joint,np.random.default_rng(seed))['1k1'].minutes==0


def test_incomplete_roster_uses_upstream_probability_not_a_collapsed_calibrator():
    inp,rows=fixture(1)
    rows['new_p_start']=.65
    rows['unprojected_p']=.9999
    joint,exact,_=prepare(inp,rows,DurationHistory(history(),'2025-02-01T00:00:00Z'))
    assert exact['1k0']['p']==.65
    assert exact[UNKNOWN+'1']['p']==pytest.approx(.35)

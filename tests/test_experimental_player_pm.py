import copy
from dataclasses import replace
import numpy as np
import pandas as pd
import pytest
from fpl_v1_1_model import joint_simulator as sim
from fpl_v1_1_model.experimental_player_pm import posterior,ProfileFit,prepare,lineup_rates,shadow_player_intensity,historical_opponent_offsets


def fixture():
    ps=tuple(sim.PlayerSimInput(str(i),str(i//2),'FWD',1.,0.,90.,0.,goal_weight=.2,assist_weight=.1) for i in range(4))
    return sim.MatchSimInput('0','1',1.,1.,ps)


def spec(inp,h=0.):
    return dict(profiles={p.player_id:dict(xg90={'mean':.5},xa90={'mean':.2},finishing={'mean':1.}) for p in inp.players},contexts={str(t):dict(opponent=1.,venue=1.,xa_anchor=.4) for t in ['0','1']},anchor_weight=h,creativity=0.,finishing=True)


def test_profile_shrinkage_uncertainty():
    a=posterior(8,5,1,50);assert a['mean']==pytest.approx(58/55);assert a['interval95'][0]<a['mean']<a['interval95'][1]
    assert posterior(0,0,.2,10)['mean']==.2
    with pytest.raises(ValueError):posterior(1,-1,1,20)


def test_lineup_changes_total_not_only_shares():
    x=fixture();s=spec(x);e={p.player_id:1. for p in x.players};a,ind=lineup_rates(x,s,e)
    assert a['0']['total']==pytest.approx(1);assert sum(ind[p.player_id] for p in x.players if p.team=='0')==pytest.approx(1)
    e['0']=0;b,_=lineup_rates(x,s,e);assert b['0']['total']==pytest.approx(.5)
    c,_=lineup_rates(x,spec(x,1.),e);assert c['0']['total']==pytest.approx(1)


def test_finishing_applied_once_penalty_budget_preserved():
    x=replace(fixture(),lambda_home_penalties=.2,home_penalty_conversion=.8);s=spec(x)
    for p in s['profiles'].values():p['finishing']['mean']=2
    a,_=lineup_rates(x,s,{p.player_id:1 for p in x.players})
    assert a['0']['total']==pytest.approx((1-.16)*2+.16)


def test_creativity_and_opposition_are_not_independent_goals():
    x=fixture();s=spec(x);s['creativity']=.5;e={p.player_id:1 for p in x.players};a,_=lineup_rates(x,s,e)
    s['profiles']['0']['xa90']['mean']=0.;b,_=lineup_rates(x,s,e);assert b['0']['total']<a['0']['total']
    s['creativity']=0.;s['contexts']['0']['opponent']=2;c,_=lineup_rates(x,s,e);assert c['0']['total']==pytest.approx(2)


def test_shared_events_and_context_restore():
    x=fixture();s=spec(x);saved=sim.simulate_match;minute=sim._sample_minutes;d={}
    expected=0.
    with shadow_player_intensity(s,d):
        for seed in range(50):
            r=sim.simulate_match(x,np.random.default_rng(seed));assert sum(v.assists for v in r.values())<=sum(v.goals for v in r.values())
            expected+=(r['0'].minutes+r['1'].minutes)/180
    assert sim.simulate_match is saved and sim._sample_minutes is minute
    assert d['0']['draws']==50 and d['0']['goal_mean_sum']==pytest.approx(expected)
    with pytest.raises(RuntimeError):
        with shadow_player_intensity(s):raise RuntimeError()
    assert sim.simulate_match is saved and sim._sample_minutes is minute


def test_original_unmodified_when_context_disabled():
    x=fixture();a=sim.simulate_many(x,n=20,seed=14)
    with shadow_player_intensity(spec(x)):sim.simulate_many(x,n=20,seed=14)
    assert a==sim.simulate_many(x,n=20,seed=14)


def history():
    rows=[]
    for gw in range(1,4):
        for i in range(4):
            rows.append(dict(player_uuid=str(i),fixture_uuid=str(gw),season='a',team_id=i//2,opponent_team_id=1-i//2,was_home=int(i//2==0),fpl_position='FWD',kickoff_at=f'2024-01-{gw:02d}T12:00Z',known=pd.Timestamp(f'2024-01-{gw:02d}T16:00Z'),xg=.2,xa=.1,goals=0.,fpl_assists=0.,minutes=90.,started=1,opponent_offset=1.,bps=10.))
    return pd.DataFrame(rows)


def test_future_outcome_cannot_change_profile_or_offsets():
    h=history();cut=pd.Timestamp('2024-01-03T10:00Z');p=fixture().players[0];f=ProfileFit(h,cut,'a');a=f.profile(p)
    altered=h.copy();altered.loc[altered.known>=cut,['xg','xa','goals']]=1000
    assert a==ProfileFit(altered,cut,'a').profile(p)
    o1=historical_opponent_offsets(h);o2=historical_opponent_offsets(altered)
    assert np.allclose(o1.opponent_offset,o2.opponent_offset)


def test_role_and_club_changes_and_missing_defense_are_explicit():
    h=history();p=replace(fixture().players[0],team='9',position='MID');h.loc[h.player_uuid.eq('1'),'fpl_position']='MID'
    a=ProfileFit(h,pd.Timestamp('2024-01-04T10:00Z'),'a').profile(p)
    assert a['club_change'] and a['role_change'] and a['weighted_minutes']==0
    assert a['defcon_count90'] is None and a['set_piece'].startswith('Not Available')


def test_sampled_substitutions_change_goal_time_distribution():
    x=fixture();s=spec(x);e={p.player_id:np.ones(90) for p in x.players};e['0']=np.r_[np.ones(45),np.zeros(45)]
    r,individual=lineup_rates(x,s,e);assert r['0']['bins'][0]==1 and r['0']['bins'][80]==.5
    assert individual['0']==pytest.approx(.25)

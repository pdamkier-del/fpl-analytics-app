"""Research-only gates must never see a target's outcome or break joint XI."""
from dataclasses import replace
import numpy as np
import pandas as pd
import pytest
from fpl_v1_1_model import joint_simulator as sim
from fpl_v1_1_model import experimental_player_pm as player
from fpl_v1_1_model.experimental_dynamic_pm import FEATURES,fit_gate,moment_weight,shadow_legal_minutes,shadow_team_weights
from test_experimental_correctness_simulator import fixture


def gate_data():
    rng=np.random.default_rng(911);n=100
    f=pd.DataFrame({k:rng.uniform(0,1,n) for k in FEATURES})
    f['player_xg']=rng.uniform(.5,3,n);f['team_xg']=rng.uniform(.5,3,n)
    f['xg']=.8*f.player_xg+.2*f.team_xg+rng.normal(0,.1,n)
    f['profile_variance']=rng.uniform(.01,.3,n);f['team_key']=['24:1','24:2']*(n//2)
    f['known']=pd.date_range('2024-01-01',periods=n,tz='UTC');f['cutoff']=pd.Timestamp('2024-06-01',tz='UTC')
    for k in [5,20,80]:f['amount_'+str(k)]=.6;f['detail_'+str(k)]=.7
    return f,f.iloc[-1].copy()


@pytest.mark.parametrize('config',[dict(family='fixed'),dict(family='minutes',k=20),dict(family='detailed',k=20),dict(family='uncertainty',k=4),dict(family='covariance',k=1),dict(family='learned',k=1,hierarchical=False),dict(family='learned',k=1,hierarchical=True)])
def test_gate_is_bounded_and_cannot_learn_target_or_future_results(config):
    f,t=gate_data();w,info=fit_gate(f,t,config)
    assert np.isfinite(w) and 0<=w<=1
    future=f.copy();future['known']=t.cutoff;future['xg']=1e6
    t['xg']=-1e8
    after,_=fit_gate(pd.concat([f,future]),t,config)
    assert after==pytest.approx(w,abs=1e-12)
    if 'max_known' in info:assert pd.Timestamp(info['max_known'])<t.cutoff


def test_covariance_weight_includes_bias_and_cross_moment():
    assert moment_weight(4,1,0)==.2
    assert moment_weight(4,1,1)==0
    assert moment_weight(1,1,1)==.75
    assert moment_weight(1,4,0)==.8
    with pytest.raises(ValueError):moment_weight(-1,1,0)


def test_warm_start_is_explicit_and_unseen_team_is_supported():
    f,t=gate_data();t.team_key='25:new';cfg=dict(family='learned',k=1,hierarchical=True)
    assert fit_gate(f.head(10),t,cfg)[0]==.75
    assert 0<fit_gate(f,t,cfg)[0]<1


def test_legal_bridge_reuses_existing_sampler_and_restores_on_exception():
    inp=fixture(True);p=inp.players[-1];inp=replace(inp,players=inp.players+(replace(p,player_id='unavailable',p_start=0,p_cameo_given_bench=0),))
    original_match=sim.simulate_match;original_minutes=sim._sample_minutes;diag={}
    with pytest.raises(RuntimeError):
        with shadow_legal_minutes(diagnostics=diag):
            rng=np.random.default_rng(123)
            for _ in range(60):
                result=sim.simulate_match(inp,rng)
                for team in ['H','A']:
                    assert sum(result[p.player_id].started for p in inp.players if p.team==team)==11
                assert result['unavailable'].minutes==0
            raise RuntimeError('test restoration')
    assert diag['legal_draws']==60
    assert sim.simulate_match is original_match and sim._sample_minutes is original_minutes


def test_survival_hazards_are_used_by_legal_bridge():
    inp=fixture();hazards={p.player_id:[1.]+[0.]*89 for p in inp.players};diag={}
    with shadow_legal_minutes(hazards,diag):result=sim.simulate_match(inp,np.random.default_rng(125))
    assert all(p.minutes==1 for p in result.values())
    assert diag['zero_duration_clamped']==22


def test_fixed_gate_dispatches_unchanged_formula_and_restores(monkeypatch):
    inp=fixture();calls=[]
    def fake(i,s,e):calls.append(s['anchor_weight']);return {'H':{'xg':s['anchor_weight']},'A':{'xg':s['anchor_weight']}},{p.player_id:s['anchor_weight'] for p in i.players}
    monkeypatch.setattr(player,'lineup_rates',fake)
    with shadow_team_weights({'H':.75,'A':.75}):assert player.lineup_rates(inp,{},{} )[0]['H']['xg']==.25
    assert calls==[.25] and player.lineup_rates is fake
    with shadow_team_weights({'H':.2,'A':.9}):r,_=player.lineup_rates(inp,{},{})
    assert r['H']['xg']==.8 and r['A']['xg']==pytest.approx(.1)
    with pytest.raises(ValueError):
        with shadow_team_weights({'H':float('nan')}):pass

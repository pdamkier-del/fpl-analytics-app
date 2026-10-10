import importlib.util
from pathlib import Path
import pandas as pd
import pytest
spec=importlib.util.spec_from_file_location('livepen',Path(__file__).resolve().parents[1]/'scripts/run_live_vfinal_penalty_state.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
def data():
    roster=pd.DataFrame([
      {'fixture_uuid':'fx','player_uuid':'a','team_id':1,'opponent_team_id':2,'goal_rate90':.4},
      {'fixture_uuid':'fx','player_uuid':'b','team_id':1,'opponent_team_id':2,'goal_rate90':.1},
      {'fixture_uuid':'fx','player_uuid':'c','team_id':2,'opponent_team_id':1,'goal_rate90':.2}])
    hist=pd.DataFrame([{'player_uuid':'a','gw':1,'attempts':1,'penalties_scored':1,'available_at':'2026-08-10T00:00:00Z'}])
    sides=pd.DataFrame([{'gw':1,'team_code':10,'opp_code':20,'attempts':1,'available_at':'2026-08-10T00:00:00Z'},
                        {'gw':1,'team_code':20,'opp_code':10,'attempts':0,'available_at':'2026-08-10T00:00:00Z'}])
    teams=pd.DataFrame([{'team_code':10,'team_id':1},{'team_code':20,'team_id':2}])
    summary={'selected':{'taker_half_life':6.,'occurrence_tau':10.,'conversion_tau':8.}}
    return roster,hist,sides,teams,summary
def test_penalty_weights_sum_to_one_per_team():
    result=m.apply(*data(),origin=2)
    assert (result.groupby(['fixture_uuid','team_id']).pen_weight.sum()-1).abs().max()<1e-10
    assert result.pen_conversion.between(0,1).all()
def test_future_penalties_rejected():
    r,a,s,t,m0=data();a.loc[0,'gw']=2
    with pytest.raises(ValueError,match='Future'):m.apply(r,a,s,t,m0,2)
def test_duplicate_targets_rejected():
    r,a,s,t,m0=data();r=pd.concat([r,r.iloc[[0]]])
    with pytest.raises(ValueError,match='Duplicate'):m.apply(r,a,s,t,m0,2)

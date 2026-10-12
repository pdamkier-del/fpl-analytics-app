import sys
from pathlib import Path
import pytest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from build_match_display import build

def inputs():
    official={'fetched_at':'now','players':[{'id':1},{'id':2}]}
    fixtures={'fetched_at':'now','fixtures':[{'id':10,'gw':1,'home':1,'away':2,'finished':True},{'id':11,'gw':2,'home':1,'away':3,'finished':True},{'id':12,'gw':2,'home':1,'away':4,'finished':False}]}
    events={1:{'elements':[{'id':1,'stats':{'total_points':0,'minutes':0,'expected_goals':'0.00'},'explain':[{'fixture':10,'stats':[]}]}]},2:{'elements':[{'id':1,'stats':{'total_points':7,'minutes':90,'expected_goals':'0.5'},'explain':[{'fixture':11,'stats':[{'identifier':'goals_scored','value':1,'points':5},{'identifier':'minutes','value':90,'points':2}]},{'fixture':12,'stats':[]}]},{'id':2,'stats':{'total_points':0},'explain':[{'fixture':12,'stats':[]}]}]}}
    return official,fixtures,events

def test_finished_matches_true_zero_and_partial_gw():
    output=build(*inputs())
    assert output['available_gws']==[1,2] and output['completed_gws']==[1]
    assert len(output['match_rows'])==2
    assert output['match_rows'][0]['total_points']==0
    assert output['match_rows'][0]['stats']['minutes']==0
    assert output['match_rows'][1]['total_points']==7
    assert output['match_rows'][1]['stats']=={},'Never distribute GW-level xG/minutes across DGW fixtures'
    assert [(r['player_id'],r['gw']) for r in output['gw_rows']]==[(1,1)],'Unfinished/ambiguous player GW totals cannot be presented as final'

def test_snapshot_and_identity_gates():
    official,fixtures,events=inputs();fixtures['fetched_at']='old'
    with pytest.raises(ValueError):build(official,fixtures,events)
    fixtures['fetched_at']='now';events[1]['elements'][0]['explain'][0]['fixture']=999
    with pytest.raises(ValueError):build(official,fixtures,events)

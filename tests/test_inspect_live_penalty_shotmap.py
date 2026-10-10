import importlib.util
from pathlib import Path
spec=importlib.util.spec_from_file_location('probe',Path(__file__).resolve().parents[1]/'scripts/inspect_live_fotmob_penalty_bps.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
def test_explicit_penalty_marker_keeps_source_player_ids():
    fields,markers,examples=m.shotmap_evidence({'shots':[{'playerId':7,'teamId':3,'situation':'Penalty','eventType':'Goal'},{'playerId':8,'situation':'RegularPlay'}]})
    assert fields['playerId']==2
    assert markers['situation=Penalty']==1
    assert examples['situation=Penalty']['playerId']==7
def test_no_penalty_inferred_from_ordinary_shot():
    _,markers,_=m.shotmap_evidence([{'playerId':1,'eventType':'Goal','shotType':'RightFoot'}])
    assert not markers

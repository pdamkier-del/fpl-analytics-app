import importlib.util,json
from pathlib import Path
spec=importlib.util.spec_from_file_location('e',Path(__file__).resolve().parents[1]/'scripts/extract_explicit_penalty_shots.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
def test_only_literal_penalty_events_are_kept(tmp_path):
    p=tmp_path/'GW1/fotmob/details/a.json';p.parent.mkdir(parents=True)
    p.write_text(json.dumps({'general':{'matchId':123},'content':{'shotmap':{'shots':[
      {'playerId':4,'teamId':7,'situation':'Penalty','eventType':'Goal'},
      {'playerId':5,'teamId':7,'situation':'RegularPlay','eventType':'Goal'}]}}}))
    r=m.candidates(tmp_path)
    assert r['candidate_count']==1
    assert r['candidates'][0]['player_id']==4
    assert r['candidates'][0]['source_path']=='GW1/fotmob/details/a.json'
    assert r['penalty_model_input_ready'] is False

def test_shootout_and_ambiguous_penalty_markers_excluded(tmp_path):
    p=tmp_path/'GW2/fotmob/details/f.json';p.parent.mkdir(parents=True)
    p.write_text(json.dumps({'general':{'matchId':456},'content':{'shotmap':{'shots':[
      {'playerId':11,'situation':'Penalty','period':'PenaltyShootout'},
      {'playerId':12,'situation':'RegularPlay','period':'PenaltyShootout'},
      {'playerId':13,'situation':'Penalty','period':'SecondHalf'}]}}}))
    r=m.candidates(tmp_path)
    assert r['candidate_count']==1
    assert r['shootout_excluded']==2
    assert r['candidates'][0]['player_id']==13

def test_raw_penalty_outcome_and_identity_coverage(tmp_path):
    p=tmp_path/'GW3/fotmob/details/f.json';p.parent.mkdir(parents=True)
    p.write_text(json.dumps({'general':{'matchId':900},'content':{'shotmap':{'shots':[
      {'playerId':42,'teamId':7,'situation':'Penalty','period':'FirstHalf','eventType':'Goal'},
      {'playerId':43,'teamId':7,'situation':'Penalty','period':'SecondHalf','eventType':'Miss'}]}}}))
    r=m.candidates(tmp_path)
    assert r['event_type_counts']=={'Goal':1,'Miss':1}
    assert r['missing_raw_identities']=={'match_id':0,'player_id':0,'team_id':0}
    assert r['duplicate_source_shots']==0

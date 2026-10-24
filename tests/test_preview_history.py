import json
import pytest
from collect_preview_history import build

def site(tmp_path):
    source=tmp_path/'site';source.mkdir();at='2026-10-19T19:28:44+00:00'
    docs={'current-players.json':{'fetched_at':at,'players':[{'id':1}]},'live-fixtures.json':{'fetched_at':at,'fixtures':[{'id':10}]},'match-results.json':{'observed_at':at,'available_gws':[1,7],'completed_gws':[1],'gw_rows':[{'player_id':1,'gw':7}],'match_rows':[{'player_id':1,'fixture_id':10}]}}
    for name,doc in docs.items():(source/name).write_text(json.dumps(doc))
    return source

def test_history_preserves_actual_bytes_and_independent_capture(tmp_path):
    source=site(tmp_path);out=tmp_path/'out';r=build(source,out,{'production_run':123,'production_artifact':456})
    assert r['available_gws']==[1,7] and r['match_rows']==1
    assert r['observed_at']=='2026-10-19T19:28:44+00:00'
    assert all((out/n).read_bytes()==(source/n).read_bytes() for n in r['files'])

def test_history_rejects_mixed_capture(tmp_path):
    source=site(tmp_path);p=source/'match-results.json';j=json.loads(p.read_text());j['observed_at']='2026-10-19T19:09:00Z';p.write_text(json.dumps(j))
    with pytest.raises(ValueError,match='one verified'):build(source,tmp_path/'out',{})

def test_history_rejects_unknown_fixture(tmp_path):
    source=site(tmp_path);p=source/'match-results.json';j=json.loads(p.read_text());j['match_rows'][0]['fixture_id']=99;p.write_text(json.dumps(j))
    with pytest.raises(ValueError,match='identity'):build(source,tmp_path/'out',{})

def test_history_rejects_empty_data(tmp_path):
    source=site(tmp_path);p=source/'match-results.json';j=json.loads(p.read_text());j['match_rows']=[];p.write_text(json.dumps(j))
    with pytest.raises(ValueError,match='Empty'):build(source,tmp_path/'out',{})

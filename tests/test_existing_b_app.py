from pathlib import Path
from build_existing_b_app import build, source_data


def test_preview_copies_existing_ui_without_changing_production(tmp_path):
    app = tmp_path/'app'
    app.mkdir()
    html = '<head></head><script src="classic-manager.js"></script>'
    js = "forecast.model!=='original_locked_vFinal_diagnostic';localStorage.getItem('fpl-manager-state-v1');localStorage.getItem('fpl-manager-plan-v1');fetch(service.url+'/plans',{method:'POST'});"
    (app/'my-team-classic.html').write_text(html)
    (app/'classic-manager.js').write_text(js)
    out = build(tmp_path)
    assert (app/'my-team-classic.html').read_text() == html
    assert (app/'classic-manager.js').read_text() == js
    assert '../existing-app-adapter.js' in (out/'my-team-classic.html').read_text()
    result = (out/'classic-manager.js').read_text()
    assert 'B_locked_PM_preview' in result
    assert 'fpl-manager-state-v1' in result
    assert 'fpl-manager-plan-B-preview-v1' in result
    assert "service.url+'/preview/plans'" in result


def test_official_snapshot_and_existing_xi_are_translated_without_inference():
    players = [dict(id=i, team=1, element_type=1 if i == 1 else 2, now_cost=50) for i in range(1,12)]
    slots = ['GK','CB','CB','CB','LWB','CM','CM','RWB','LW','RW','CF']
    mm = dict(teams=[dict(club_id=1,fixture_id='f1',formation='3-4-2-1')], players=[dict(
        club_id=1,fixture_id='f1',expected_xi=True,slot_index=i,slot=slot,gw=8,
        fpl_element=i+1,availability='UNKNOWN',xmins=80,primary_role=slot,role_probabilities={slot:1})
        for i,slot in enumerate(slots)])
    f = dict(gws=[8],season='2026-27',data_asof='2026-10-18T07:00:00Z',checksums={},
             players=[dict(weeks=[dict(fixtures=[dict(fixture_uuid='f1',kickoff='2026-10-24T12:00:00Z')])])])
    d = source_data(dict(elements=players,teams=[dict(id=1,name='Club')]),[],dict(bootstrap_observed_at='2026-10-18T06:59:00Z'),f,mm)
    assert d['current-players.json']['players'][0]['price'] == 5
    xi = d['club-lineups.json']['fixtures'][0]
    assert [len(x) for x in xi['layers']] == [1,3,4,2,1]
    assert sum(p['selected'] for p in xi['players']) == 11
    assert d['club-lineups.json']['source'] == 'B_MM_assignment'


def test_live_adapter_never_writes_private_storage_or_calls_model():
    src = (Path(__file__).resolve().parents[1]/'app/mm-preview/existing-app-adapter.js').read_text()
    assert 'localStorage.setItem' not in src
    assert 'sessionStorage.setItem' not in src
    assert 'existing_app_data_sha256' in src
    assert 'nativeFetch(input,options)' in src

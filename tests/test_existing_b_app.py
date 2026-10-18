from pathlib import Path
import json
import subprocess
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


def test_official_snapshot_and_existing_xi_are_translated_without_inference(tmp_path):
    players = [dict(id=i, team=1, element_type=1 if i == 1 else 2, now_cost=50) for i in range(1,12)]
    slots = ['GK','CB','CB','CB','LWB','CM','CM','RWB','LW','RW','CF']
    mm = dict(teams=[dict(club_id=1,fixture_id='f1',formation='3-4-2-1')], players=[dict(
        club_id=1,fixture_id='f1',expected_xi=True,slot_index=i,slot=slot,gw=8,
        fpl_element=i+1,availability='UNKNOWN',xmins=80,primary_role=slot,role_probabilities={slot:1})
        for i,slot in enumerate(slots)])
    f = dict(gws=[8],season='2026-27',data_asof='2026-10-18T07:00:00Z',forecast_sha256='same',
             players=[dict(id=p['id'],team_id=1,position=p['element_type'],price_tenths=50,
                weeks=[dict(gw=8,xpts=3,xmins=80,fixtures=[dict(p_start=.9,xpts=3,xmins=80,fixture_uuid='f1',kickoff='2026-10-24T12:00:00Z')])]) for p in players])
    d = source_data(dict(elements=players,teams=[dict(id=1,name='Club')]),[],dict(bootstrap_observed_at='2026-10-18T06:59:00Z',fixtures_observed_at='2026-10-18T06:58:00Z'),f,mm)
    assert d['current-players.json']['players'][0]['price'] == 5
    xi = d['club-lineups.json']['fixtures'][0]
    assert [len(x) for x in xi['layers']] == [1,3,4,2,1]
    assert sum(p['selected'] for p in xi['players']) == 11
    assert d['club-lineups.json']['source'] == 'B_MM_assignment'
    assert xi['players'][0]['observed_roles'][0] == {'role':'GK','matches':None,'share':1}
    assert d['live-fixtures.json']['fetched_at'] == '2026-10-18T06:58:00Z'
    assert d['current-players.json']['snapshot_sha256'] == d['live-fixtures.json']['snapshot_sha256']
    assert d['club-lineups.json']['forecast_sha256'] == f['forecast_sha256']
    # Exercise the actual existing renderer: B uses a sealed content identity,
    # not the old desktop exporter's absent raw-file checksums.
    app=tmp_path/'app'
    app.mkdir()
    root=Path(__file__).resolve().parents[1]
    (app/'catalog-data.js').write_text((root/'app/catalog-data.js').read_text())
    out=build(tmp_path)
    script="const fs=require('fs'),assert=require('assert'),D=require(process.argv[1]),x=JSON.parse(fs.readFileSync(0,'utf8'));const xi=D.clubLineup(x.o,x.f,x.s,true,1);assert.equal(xi.layers.flat().length,11);assert.equal(xi.layers.flat().filter(p=>p.role==='GK').length,1);x.s.forecast_sha256='wrong';assert.equal(D.clubLineup(x.o,x.f,x.s,true,1),null);"
    subprocess.run(['node','-e',script,str(out/'catalog-data.js')],input=json.dumps(dict(o=d['current-players.json'],f=f,s=d['club-lineups.json'])),text=True,check=True)


def test_live_adapter_never_writes_private_storage_or_calls_model():
    src = (Path(__file__).resolve().parents[1]/'app/mm-preview/existing-app-adapter.js').read_text()
    assert 'localStorage.setItem' not in src
    assert 'sessionStorage.setItem' not in src
    assert 'existing_app_data_sha256' in src
    assert 'nativeFetch(input,options)' in src

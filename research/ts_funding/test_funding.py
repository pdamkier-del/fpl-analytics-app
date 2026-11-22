"""Offline archive, contract and accounting checks; no new model evaluation."""
from dataclasses import asdict
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import pytest

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
sys.path[:0]=[str(HERE),str(ROOT/'research/ts_search/code')]
from reference import transition, legal_squads, exact_path
from candidate import funding_pairs, propose
from generate import cases


def load(path):
    return json.loads((ROOT/path).read_text())


def test_locked_implementation_and_all_original_protocols_unchanged():
    manifest=load('research/ts_funding/implementation-manifest.json')
    for p,h in manifest['files'].items():
        assert hashlib.sha256((ROOT/p).read_bytes()).hexdigest()==h
    base='caf6401fca8bbf7128358641ace9cfd7336e17eb'
    paths=subprocess.check_output(['git','-C',str(ROOT),'ls-tree','-r','--name-only',base,'research/experiments'],text=True).splitlines()
    assert len(paths)==63
    for p in paths:
        assert (ROOT/p).read_bytes()==subprocess.check_output(['git','-C',str(ROOT),'show',base+':'+p])


def test_new_holdout_matches_locked_generator_and_domains():
    archived=load('research/results/EXP-TS-FUNDING-001/holdout/instances.json')['cases']
    assert archived==cases() and len(archived)==48
    assert len({r['id']for r in archived})==48
    assert len({r['family']for r in archived})==6
    assert {r['free_transfers']for r in archived}==set(range(6))
    for case in archived:
        players={p['id']:p for p in case['players']}
        assert len(players)==17 and tuple(case['initial_ids'])in legal_squads(players)
        assert all(len(p['points'])==len(p['minutes'])==6 for p in players.values())
        assert max(len(w)for p in players.values()for w in p['points'])<=8


@pytest.mark.parametrize('phase,count',[('development',42),('holdout',48)])
def test_archived_paths_replay_all_prices_hits_ft_and_objectives(phase,count):
    raw=load(f'research/results/EXP-TS-FUNDING-001/{phase}/results.json')
    source='research/ts_search/inputs/instances.json' if phase=='development'else'research/results/EXP-TS-FUNDING-001/holdout/instances.json'
    inputs={c['id']:c for c in load(source)['cases']}
    assert raw['status']=='completed' and not raw['not_run'] and len(raw['rows'])==count
    for row in raw['rows']:
        assert row['status']=='completed' and not row['errors']
        case=inputs[row['id']];players={p['id']:p for p in case['players']}
        for arm,data in row['arms'].items():
            if 'path'not in data:continue # PR48 baseline never rerun.
            state=(tuple(sorted((p,players[p]['purchase'])for p in case['initial_ids'])),case['bank'],case['free_transfers'])
            value=0.
            assert len(data['path'])==6
            for g,a in enumerate(data['path']):
                selected=tuple(sorted((set(dict(state[0]))-set(a['outgoing']))|set(a['incoming'])))
                assert selected in legal_squads(players) and len(a['incoming'])<=2
                after,out,inc,hits,paid=transition(*state,selected,players)
                assert list(out)==a['outgoing'] and list(inc)==a['incoming']
                assert after[1]==a['bank_after'] and after[2]==a['free_transfers_after']
                assert hits==a['official_hit_points'] and paid==a['uncertainty_penalty']
                value+=raw['configuration']['weights'][g]*a['projected_manager_score']-hits-paid
                state=after
            assert value==pytest.approx(data['objective'],abs=1e-9)
            assert row['exact']['objective']>=data['objective']-1e-9


def test_failed_family_gate_is_preserved_not_relabelled_acceptance():
    s=load('research/results/EXP-TS-FUNDING-001/holdout-summary.json')
    assert not s['practical_gate_pass']
    assert not s['gates']['improvement_in_two_families']
    assert s['overall']['improved']==2 and s['overall']['worsened']==0
    assert s['overall']['mean_improvement']==pytest.approx(0.09803333333333224)


def test_research_patch_restores_frozen_callable_on_exception():
    class Fake:
        _fast_local_candidate_squads=object()
    planner=Fake();original=planner._fast_local_candidate_squads
    with pytest.raises(RuntimeError):
        with funding_pairs(planner):
            assert planner._fast_local_candidate_squads is not original
            raise RuntimeError('synthetic failure')
    assert planner._fast_local_candidate_squads is original


@pytest.mark.parametrize('bank,club_legal,expected',[(0,True,2),(0,False,1),(30,True,1)])
def test_only_needed_affordable_legal_funding_is_appended(bank,club_legal,expected):
    from types import SimpleNamespace
    state=SimpleNamespace(squad={1:SimpleNamespace(purchase_price=70),
                                 2:SimpleNamespace(purchase_price=50)},bank=bank)
    rows={1:('DEF',1,70),2:('MID',2,50),3:('DEF',3,40),4:('MID',4,80)}
    prepared=(rows,{1:6.,2:5.,3:2.,4:15.},{'DEF':[1,3],'MID':[2,4]})
    class Fake:
        selling_price=staticmethod(lambda purchase,current: min(purchase,current))
        valid_squad=staticmethod(lambda meta,selected: club_legal)
        _apply_selected_squad=staticmethod(lambda state,selected,meta:(SimpleNamespace(bank=state.bank),(),()))
    baseline=[{1,2}]
    result=propose(Fake(),lambda *a,**k:baseline,state,None,None,[1],[1],2,18,60,12,prepared)
    assert result[:1]==baseline and len(result)==expected
    if expected==2:assert result[-1]=={3,4}


def test_independent_dp_hand_derived_hit_and_six_week_identity():
    case=cases()[0];players={p['id']:p for p in case['players'][:15]}
    for p in players.values():p.update(price=50,purchase=50)
    players[16]=dict(players[3],id=16)
    squads=legal_squads(players);initial=tuple(range(1,16))
    scores=[{s:100.+(10. if 16 in s else 0.)for s in squads}for _ in range(6)]
    weights=(1.,.6,.36,.216,.1296,.07776)
    case.update(bank=0,free_transfers=0)
    result=exact_path(case,players,squads,scores,weights,1.)
    assert result['objective']==pytest.approx(110*sum(weights)-5.)
    assert len(result['path'])==6 and result['path'][0]['official_hit_points']==4


def test_only_research_files_changed():
    paths=subprocess.check_output(['git','-C',str(ROOT),'diff','--name-only','caf6401fca8bbf7128358641ace9cfd7336e17eb'],text=True).splitlines()
    assert paths and all(p.startswith('research/')for p in paths)


def test_public_capture_hashes_horizon_and_missing_witness_are_explicit():
    folder=HERE/'capture_evidence'
    receipt=json.loads((folder/'receipt.json').read_text())
    for name,info in receipt['public'].items():
        assert hashlib.sha256((folder/name.replace('/','--')).read_bytes()).hexdigest()==info['sha256']
    index=json.loads((folder/'current--index.json').read_text())
    fields=json.loads((folder/'forecast-field-audit.json').read_text())['documents']
    assert fields['current/forecast.json']['byte_sha256']==index['forecast_file_sha256']
    assert fields['current/mm.json']['byte_sha256']==index['mm_file_sha256']
    assert fields['current/forecast.json']['gws']==list(range(11,17))
    assert fields['current/forecast.json']['all_player_horizons_match']
    ledger=json.loads((folder/'ledger-and-job-verification.json').read_text())['ledger']
    assert ledger['matches_manifest'] and ledger['rows']==ledger['unique_player_fixture_keys']==4032
    witness=json.loads((folder/'artifact-witness.json').read_text())
    assert witness['ledger_artifact_download']['status']=='blocked'
    assert 'signed' in witness['ledger_artifact_download']['error']

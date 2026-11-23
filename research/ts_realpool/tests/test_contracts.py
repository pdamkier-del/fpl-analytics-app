from pathlib import Path
import copy
import importlib.util
import json
import sys
import pytest
ROOT=Path(__file__).resolve().parents[3]
sys.path[:0]=[str(ROOT/'research/ts_realpool'),str(ROOT/'research/ts_search/code')]
from adapter import adapt
from run_experiment import load_frozen


def fixture():
    # Unrelated contract fixture; no protocol test states generated.
    f=dict(model='B-MM-PM-TS-v1',scope='prospective_preview',locked_model_active=False,
        minute_sampler_audit=dict(sampler='B-MM-PM-TS-v1',all_MM_to_PM_means_consistent=True),
        scenario_contract=dict(version='shared-PM-match-draws-v1',draws=2),gws=[1],players=[])
    mm=dict(players=[])
    for pid in range(1,16):
        position=1 if pid<3 else 2 if pid<8 else 3 if pid<13 else 4
        f['players'].append(dict(id=pid,player_uuid=str(pid),position=position,team_id=(pid-1)//3+1,price_tenths=50,name=str(pid),weeks=[dict(gw=1,xpts=2.,p_play=1.,xmins=90.,pm_analytic_minutes=90.,fixtures=[dict(fixture_uuid='fixture-1',xmins=90.,pm_analytic_minutes=90.)],scenarios=dict(points=[1,3],minutes=[90,90]))]))
        mm['players'].append(dict(player_id=str(pid),fixture_id='fixture-1',p_play=1.))
    return f,mm


def test_identity_retains_every_model_field_draw_and_score():
    f,mm=fixture();original=copy.deepcopy(f);modules=load_frozen(Path('/workspace/work/fpl-ts-frozen-161'))
    result,eligible=adapt(f,mm,modules[2].validate_forecast,original=False)
    assert result is f and result==original and len(eligible)==15
    native=modules[2].ScenarioScorer(original);adapted=modules[2].ScenarioScorer(result)
    ids=tuple(range(1,16));assert native.decision(1,ids)==adapted.decision(1,ids)
    meta,origin=modules[3].project(result);assert len(meta)==15 and len(origin)==15


def test_rejects_missing_or_changed_scenarios_without_imputation():
    f,mm=fixture();modules=load_frozen(Path('/workspace/work/fpl-ts-frozen-161'))
    f['players'][0]['weeks'][0]['scenarios']['points'].pop()
    with pytest.raises(ValueError,match='scenarios'):adapt(f,mm,modules[2].validate_forecast,original=False)


def test_rejects_wrong_original_and_duplicate_ids():
    f,mm=fixture()
    with pytest.raises(KeyError):adapt(f,mm,lambda f:None)
    f['players'].append(copy.deepcopy(f['players'][0]))
    with pytest.raises(ValueError,match='Duplicate'):adapt(f,mm,lambda f:None,original=False)

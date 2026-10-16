import math
import sys
from pathlib import Path
import pytest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
from rolling_future_minutes import project_fixture_minutes


def test_neutral_reproduces_origin_composition():
    z=project_fixture_minutes(.82,80,.4,15,days_rest=2.5)
    assert z["p_start"]==.82
    assert z["xmins"]==pytest.approx(.82*80+.18*.4*15)


def test_known_short_rest_scenario_not_future_information():
    base=project_fixture_minutes(.8,85,.5,15,days_rest=6,short_rest_start_penalty=.2)
    short=project_fixture_minutes(.8,85,.5,15,days_rest=2,short_rest_start_penalty=.2)
    assert base["p_start"]==.8
    assert short["p_start"]==pytest.approx(.72)
    assert short["xmins"]<base["xmins"]


def test_no_recovery_without_verified_information():
    for d in (None,2,12,20):
        assert project_fixture_minutes(0,80,0,15,days_rest=d,short_rest_start_penalty=.5)["xmins"]==0


def test_reject_bad_inputs():
    with pytest.raises(ValueError):
        project_fixture_minutes(float("nan"),80,.5,15)
    with pytest.raises(ValueError):
        project_fixture_minutes(.8,80,.5,15,days_rest=-2)

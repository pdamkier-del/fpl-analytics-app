import importlib.util
from pathlib import Path
import pandas as pd
import pytest
spec=importlib.util.spec_from_file_location('joint',Path(__file__).resolve().parents[1]/'scripts/run_live_vfinal_joint_simulation.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
def test_incomplete_pm_does_not_produce_xp():
    frame=pd.DataFrame([{'fixture_uuid':'f','player_uuid':'p','team_id':1}])
    with pytest.raises(ValueError,match='Missing frozen simulator fields'):
        m.simulate(frame)
def test_duplicate_players_rejected_after_field_coverage():
    data={key:1.0 for key in m.REQUIRED}
    data.update(fixture_uuid='f',player_uuid='p',pos='MID',cutoff='2026-10-10T10:00:00Z')
    frame=pd.DataFrame([data,data])
    with pytest.raises(ValueError,match='duplicate fixture players'):
        m.validate(frame)


def test_first_match_is_earliest_in_current_gw_not_lexical_gw10():
    frame=pd.DataFrame([{'fixture_uuid':'gw10-a','target_gw':10,'target_kickoff':'2026-11-01T10:00:00Z'},
                        {'fixture_uuid':'gw6-z','target_gw':6,'target_kickoff':'2026-10-10T10:00:00Z'},
                        {'fixture_uuid':'gw6-a','target_gw':6,'target_kickoff':'2026-10-11T10:00:00Z'}])
    assert m.select_scope(frame,'one-match').fixture_uuid.tolist()==['gw6-z']
    assert len(m.select_scope(frame,'one-gw'))==2

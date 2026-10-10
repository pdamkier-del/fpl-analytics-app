import importlib.util
from pathlib import Path
import pytest
spec=importlib.util.spec_from_file_location('teams',Path(__file__).resolve().parents[1]/'scripts/build_live_penalty_fpl_team_ids.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
def test_official_fpl_team_namespace():
    b={'teams':[{'id':i} for i in range(1,21)]}
    fx=[{'team_h':i,'team_a':i+1} for i in range(1,20)]
    df=m.build(b,fx)
    assert len(df)==20
    assert (df.team_code==df.team_id).all()
def test_incomplete_fixture_namespace_rejected():
    b={'teams':[{'id':i} for i in range(1,21)]}
    with pytest.raises(ValueError,match='Fixture teams'):m.build(b,[{'team_h':1,'team_a':2}])

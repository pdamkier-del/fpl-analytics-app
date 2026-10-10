import importlib.util
from pathlib import Path
import pandas as pd
import pytest
spec=importlib.util.spec_from_file_location("gate",Path(__file__).resolve().parents[1]/"scripts/audit_live_model_integration.py")
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
def make(tmp):
    mm=pd.DataFrame([dict(fixture_uuid="f",player_uuid="p",team_id=1,gw=6,target_gw=6,p_start=.9,xmins=81.)])
    pm=pd.DataFrame([dict(fixture_uuid="f",player_uuid="p",goal_rate90=.1)])
    paths={"mm":tmp/"mm.csv","player_events":tmp/"pm.csv","team_goals":tmp/"goals.csv","keeper_saves":tmp/"keeper.csv"}
    mm.to_csv(paths["mm"],index=False);pm.to_csv(paths["player_events"],index=False)
    return paths
def test_never_certifies_partial_chain(tmp_path):
    result=m.inspect(make(tmp_path))
    assert not result["xpts_calculated"] and not result["locked_model_active"]
    assert "Missing team_goals" in result["blockers"]
def test_rejects_identity_mismatch(tmp_path):
    paths=make(tmp_path);pd.DataFrame([dict(fixture_uuid="f",player_uuid="different")]).to_csv(paths["player_events"],index=False)
    with pytest.raises(ValueError,match="identity mismatch"):m.inspect(paths)

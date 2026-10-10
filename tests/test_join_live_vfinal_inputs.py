import importlib.util
from pathlib import Path
import pandas as pd
import pytest
spec=importlib.util.spec_from_file_location("join",Path(__file__).resolve().parents[1]/"scripts/join_live_vfinal_inputs.py")
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
def sample():
    fx="live-2026-27-fpl-123"
    mm=pd.DataFrame([dict(fixture_uuid=fx,player_uuid="p1",team_id=1,target_gw=6,xmins=80,p_start=.9,pos="MID"),
                     dict(fixture_uuid=fx,player_uuid="p2",team_id=2,target_gw=6,xmins=75,p_start=.8,pos="GK")])
    events=mm[["fixture_uuid","player_uuid"]].assign(goal_rate90=.1,assist_rate90=.12,mu_dc=.6)
    teams=pd.DataFrame([dict(fpl_fixture_id=123,home_team_id=1,away_team_id=2,lambda_home_goals=1.4,lambda_away_goals=1.2)])
    saves=pd.DataFrame([dict(fixture_uuid=fx,team_id=i,lambda_saves=2.5) for i in [1,2]])
    return mm,events,teams,saves
def test_join_preserves_every_identity():
    joined=m.combine(*sample())
    assert len(joined)==2 and joined.lambda_saves.notna().all()
def test_fixture_id_error_is_detected():
    mm,e,t,s=sample();t.loc[0,"fpl_fixture_id"]=999
    with pytest.raises(ValueError,match="different fixture IDs"):m.combine(mm,e,t,s)
def test_missing_keeper_side_is_blocked():
    mm,e,t,s=sample()
    with pytest.raises(ValueError,match="team sides"):m.combine(mm,e,t,s.iloc[:1])
def test_missing_event_is_blocked():
    mm,e,t,s=sample()
    with pytest.raises(ValueError,match="fixture identities"):m.combine(mm,e.iloc[:1],t,s)

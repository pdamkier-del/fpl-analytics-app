import pandas as pd
import pytest
from fpl_v1_1_model.mm_release import normalize_mm_release,validate_mm_release

def base():
    rows=[]
    for i in range(11):
        rows.append({
          "season":"2025-26","gw":10,"fixture_uuid":"f","team_id":1,"player_uuid":f"p{i}",
          "player":f"P{i}","team":"X","pos":"MID","cutoff":"2025-10-01T10:00:00Z",
          "p_start":1.0,"xmins":80.0,"expected_role":"CM","xi_assigned_role":"CM",
          "xi_formation":"4-3-3","team_news_state":"AVAILABLE","team_news_availability_cap":1.0,
        })
    return pd.DataFrame(rows)

def test_valid_release_passes():
    s=validate_mm_release(base())
    assert s["rows"]==11
    assert s["exact11_max_abs_error"]<1e-9

def test_exact11_violation_fails():
    x=base();x.loc[0,"p_start"]=.8
    with pytest.raises(ValueError):
        validate_mm_release(x)

def test_hard_out_must_be_zero():
    x=base();x.loc[0,"team_news_state"]="OUT";x.loc[0,"team_news_availability_cap"]=0.0
    with pytest.raises(ValueError):
        validate_mm_release(x)

def test_alias_normalization():
    x=base().rename(columns={"p_start":"team_news_p_start","xmins":"team_news_xmins"})
    y=normalize_mm_release(x,p_start_col="team_news_p_start",xmins_col="team_news_xmins")
    assert "p_start" in y and "xmins" in y

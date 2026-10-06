import pandas as pd
import pytest

from fpl_v1_1_model.team_news_history import (
    normalize_team_news,default_availability_cap,
    latest_team_news_before,build_team_news_features,validate_team_news_ledger,
)

def ledger():
    return pd.DataFrame([
        {"player_uuid":"p1","observed_at":"2026-01-01T10:00:00Z","source":"fpl","source_id":"1",
         "raw_status":"d","raw_news":"Late fitness test","chance_this_round":50},
        {"player_uuid":"p1","observed_at":"2026-01-05T10:00:00Z","source":"fpl","source_id":"2",
         "raw_status":"i","raw_news":"Ruled out","chance_this_round":0},
        {"player_uuid":"p2","observed_at":"2026-01-02T10:00:00Z","source":"fpl","source_id":"3",
         "raw_status":"a","raw_news":"","chance_this_round":100},
    ])

def test_cutoff_excludes_future_news():
    st=latest_team_news_before(ledger(),"p1","2026-01-03T12:00:00Z")
    assert st is not None
    assert st.normalized_state=="DOUBT"
    assert st.chance_this_round==pytest.approx(.5)

def test_latest_predeadline_status_is_used():
    st=latest_team_news_before(ledger(),"p1","2026-01-06T12:00:00Z")
    assert st.normalized_state=="OUT"
    assert st.hard_out

def test_carry_forward_when_no_new_update():
    targets=pd.DataFrame([{"player_uuid":"p2","cutoff":"2026-01-10T12:00:00Z"}])
    out=build_team_news_features(targets,ledger())
    assert out.loc[0,"team_news_state"]=="AVAILABLE"
    assert out.loc[0,"team_news_carried_forward"]==1.0
    assert out.loc[0,"team_news_availability_cap"]==pytest.approx(1.0)

def test_unknown_is_neutral():
    targets=pd.DataFrame([{"player_uuid":"new","cutoff":"2026-01-10T12:00:00Z"}])
    out=build_team_news_features(targets,ledger())
    assert out.loc[0,"team_news_state"]=="UNKNOWN"
    assert out.loc[0,"team_news_availability_cap"]==pytest.approx(1.0)

def test_normalization_and_caps():
    assert normalize_team_news("s","Suspended for one match",None)=="SUSPENDED"
    assert normalize_team_news("d","",25)=="MAJOR_DOUBT"
    assert default_availability_cap("OUT",100)==0.0
    assert default_availability_cap("DOUBT",50)==pytest.approx(.5)

def test_future_effective_time_rejected():
    x=ledger().iloc[[0]].copy()
    x["effective_at"]="2026-01-02T10:00:00Z"
    with pytest.raises(ValueError):
        validate_team_news_ledger(x)

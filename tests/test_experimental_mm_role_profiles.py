from datetime import datetime, timedelta, timezone
import sys
from pathlib import Path
import pytest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
from experimental_mm_role_profiles import infer_player_roles

NOW=datetime(2025,10,15,tzinfo=timezone.utc)

def game(days,started,minutes,available=True):
    return {"known_at":NOW-timedelta(days=days),"started":started,
            "minutes":minutes,"available":available}

def test_regular_starter_and_short_stint_are_separate():
    p=infer_player_roles([game(i,True,65) for i in range(1,21)],NOW)
    assert p["p_start_given_available"]>.75
    assert p["starter_minutes_mean"]<77
    assert p["starter_duration_roles"]["early_substitution_starter"]>0

def test_rotation_and_long_stint_not_conflated():
    p=infer_player_roles([game(i,i%2==0,88 if i%2==0 else 0) for i in range(1,31)],NOW)
    assert p["p_start_given_available"]<.7
    assert p["starter_minutes_mean"]>77

def test_returning_from_absence_keeps_role_history():
    games=[game(i,True,88) for i in range(2,15)]
    p=infer_player_roles(games,NOW)
    q=infer_player_roles(games+[game(1,False,0,available=False)],NOW)
    assert p==q

def test_future_events_never_enter_roles():
    events=[game(1,True,88)]
    after={"known_at":NOW+timedelta(days=1),"started":False,
           "minutes":0,"available":True}
    assert infer_player_roles(events,NOW)==infer_player_roles(events+[after],NOW)

def test_cameo_profile_varies_independently():
    a=infer_player_roles([game(i,False,20) for i in range(1,11)],NOW)
    b=infer_player_roles([game(i,False,0) for i in range(1,11)],NOW)
    assert a["p_cameo_given_bench"]>b["p_cameo_given_bench"]

def test_invalid_data_rejected():
    with pytest.raises(ValueError):
        infer_player_roles([game(1,True,120)],NOW)

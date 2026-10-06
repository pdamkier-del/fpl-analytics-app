import pandas as pd
from fpl_v1_1_model.future_match_importance import add_forward_match_importance

def test_only_target_gw_snapshot_is_used():
    frame=pd.DataFrame([{
        "gw":10,"team_id":1,"fixture_uuid":"x","cutoff":"2025-11-01T10:00:00Z",
        "target_kickoff":"2025-11-01T15:00:00Z","role_h_fast":.9,"role_h_slow":.8,
        "work_minutes_7d":180.,"work_starts_7d":2.
    }])
    snap10=pd.DataFrame([
        {"match_id":"pl","team_id":1,"competition":"prem","kickoff":pd.Timestamp("2025-11-01T15:00:00Z"),"opponent_elo":1800.,"gameweek":10},
        {"match_id":"ucl","team_id":1,"competition":"champions-league","kickoff":pd.Timestamp("2025-11-04T20:00:00Z"),"opponent_elo":1950.,"gameweek":10},
    ])
    out=add_forward_match_importance(frame,{10:snap10})
    assert out.loc[0,"future_days_to_next"]>3
    assert out.loc[0,"future_next_competition"]=="champions-league"
    assert out.loc[0,"future_rotation_pressure"]>0

def test_later_snapshot_cannot_leak():
    frame=pd.DataFrame([{
        "gw":10,"team_id":1,"fixture_uuid":"x","cutoff":"2025-11-01T10:00:00Z",
        "target_kickoff":"2025-11-01T15:00:00Z","role_h_fast":.9,"role_h_slow":.8,
        "work_minutes_7d":0.,"work_starts_7d":0.
    }])
    snap10=pd.DataFrame([
        {"match_id":"pl","team_id":1,"competition":"prem","kickoff":pd.Timestamp("2025-11-01T15:00:00Z"),"opponent_elo":1800.,"gameweek":10},
    ])
    snap11=pd.DataFrame([
        {"match_id":"pl2","team_id":1,"competition":"prem","kickoff":pd.Timestamp("2025-11-08T15:00:00Z"),"opponent_elo":1800.,"gameweek":11},
        {"match_id":"futurecup","team_id":1,"competition":"fa-cup","kickoff":pd.Timestamp("2026-01-10T15:00:00Z"),"opponent_elo":1700.,"gameweek":11},
    ])
    out=add_forward_match_importance(frame,{10:snap10,11:snap11})
    assert pd.isna(out.loc[0,"future_days_to_next"])
    assert out.loc[0,"future_rotation_pressure"]==0.0

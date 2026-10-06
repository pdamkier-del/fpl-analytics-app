import pandas as pd
from fpl_v1_1_model.structural_context import StructuralHistory,add_structural_context

def classified():
    rows=[]
    for k,(ko,form,players) in enumerate([
        ("2025-08-10T12:00:00Z","4-3-3",[("p1","RW"),("g1","GK"),("x1","ST")]),
        ("2025-08-17T12:00:00Z","4-2-3-1",[("p1","CAM"),("g2","GK"),("x1","ST")]),
        ("2025-08-24T12:00:00Z","4-2-3-1",[("p1","CAM"),("g2","GK"),("x1","ST")]),
    ]):
        for p,r in players:
            rows.append({"team_id":1,"fixture_uuid":f"f{k}","kickoff":ko,
                         "formation":form,"player_uuid":p,"final_role":r})
    return pd.DataFrame(rows)

def test_formation_conditioned_history_prefers_recent_shape():
    h=StructuralHistory(classified())
    z=h.formation_features(1,"p1","2025-08-30T12:00:00Z")
    assert z["form_cond_start_prior"]>0.9
    assert z["form_role_concentration"]>0.5

def test_gk_streak_uses_pl_starts_only():
    h=StructuralHistory(classified())
    assert h.gk_streak(1,"g2","2025-08-30T12:00:00Z")==2
    assert h.gk_streak(1,"g1","2025-08-30T12:00:00Z")==0

def test_conditional_gk_signal_suppressed_when_other_keeper_out():
    h=StructuralHistory(classified())
    frame=pd.DataFrame([
      {"gw":4,"team_id":1,"fixture_uuid":"t","cutoff":"2025-08-30T12:00:00Z",
       "player_uuid":"g2","pos":"GK","role_h_fast":.8,"role_h_slow":.8,
       "team_news_hard_out":0.,"future_rotation_pressure":0.,
       "work_starts_14d":2.,"work_minutes_14d":180.},
      {"gw":4,"team_id":1,"fixture_uuid":"t","cutoff":"2025-08-30T12:00:00Z",
       "player_uuid":"g1","pos":"GK","role_h_fast":.2,"role_h_slow":.4,
       "team_news_hard_out":1.,"future_rotation_pressure":0.,
       "work_starts_14d":0.,"work_minutes_14d":0.},
    ])
    out=add_structural_context(frame,h)
    assert out.loc[0,"gk_other_keeper_hard_out"]==1.0
    assert out.loc[0,"gk_unexplained_change_signal"]==0.0

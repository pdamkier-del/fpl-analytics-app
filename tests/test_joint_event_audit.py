from audit_joint_event_semantics import own_goal_probe

def test_forensic_probe_reproduces_locked_own_goal_scoreline_inconsistency():
    # Documents a defect in the unchanged baseline, not desired scoring behavior.
    r=own_goal_probe()
    assert r['own_goals']==1
    assert r['goals_conceded']==0 and r['clean_sheet']==1
    assert r['contradiction'] is True

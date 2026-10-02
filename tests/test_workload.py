from datetime import datetime, timedelta, timezone
from pathlib import Path
import json
import numpy as np
import pandas as pd
from fpl_v1_1_model.workload import WorkloadHistory, WORKLOAD_FEATURES

ROOT=Path(__file__).resolve().parents[1]


def test_workload_cutoff_uses_completion_and_future_invariance():
    ko=datetime(2026,1,1,20,tzinfo=timezone.utc);h=WorkloadHistory()
    h.add_game(1,'past',ko,ko+timedelta(hours=3),'efl-cup',{'p':{'minutes':120,'started':True}},True)
    assert h.state(1,ko+timedelta(hours=3))[2] is None
    state,default,known=h.state(1,ko+timedelta(days=2))
    assert state['p']['work_minutes_7d']==120 and state['p']['work_team_nonpl_matches_7d']==1
    h.add_game(1,'future',ko+timedelta(days=3),ko+timedelta(days=3,hours=3),'prem',{'p':{'minutes':90,'started':True}},True)
    after=h.state(1,ko+timedelta(days=2))
    assert after==(state,default,known)


def test_workload_unknown_player_minutes_remain_unknown():
    ko=datetime(2026,1,1,20,tzinfo=timezone.utc);h=WorkloadHistory()
    h.add_game(1,'cup',ko,ko+timedelta(hours=3),'conference-league',{},False)
    state,default,_=h.state(1,ko+timedelta(days=1))
    assert state=={} and default['work_player_history_missing']==1
    assert default['work_missing_player_stats_14d']==1 and default['work_team_matches_7d']==1


def test_workload_rejects_duplicate_and_invalid_minutes():
    ko=datetime(2026,1,1,20,tzinfo=timezone.utc);h=WorkloadHistory()
    for minutes in (121,-1,float('nan')):
        try:h.add_game(1,'bad',ko,ko+timedelta(hours=3),'prem',{'p':{'minutes':minutes,'started':True}},True)
        except ValueError:pass
        else:raise AssertionError('Invalid minutes accepted')
    h.add_game(1,'good',ko,ko+timedelta(hours=3),'prem',{},False)
    try:h.add_game(1,'good',ko,ko+timedelta(hours=3),'prem',{},False)
    except ValueError:pass
    else:raise AssertionError('Duplicate match accepted')


def test_saved_workload_features_and_diagnostics_are_cutoff_safe():
    f=pd.read_csv(ROOT/'analysis/results/workload-v1/all_features.csv.gz')
    assert len(f)==26159 and np.isfinite(f[WORKLOAD_FEATURES].to_numpy()).all()
    assert not f.work_all_competitions_complete.any()
    assert (pd.to_datetime(f.work_max_history_known_at,utc=True)<pd.to_datetime(f.cutoff,utc=True)).all()
    assert (f.work_minutes_7d<=f.work_minutes_14d).all()
    assert (f.work_minutes_14d<=f.work_minutes_28d).all()
    p=pd.read_csv(ROOT/'analysis/results/workload-minutes-v1/reused_holdout_diagnostic_predictions.csv.gz')
    assert len(p)==13987 and p.gw.between(22,38).all()
    for v in ('role_control','workload_start','role_decomposition','workload_decomposition'):
        assert p[v+'_p_start'].between(0,1).all() and p[v+'_xmins'].between(0,90+1e-9).all()
        assert np.allclose(p.groupby(['fixture_uuid','team_id'])[v+'_p_start'].sum(),11,atol=1e-8)
    protocol=json.load(open(ROOT/'analysis/results/workload-minutes-v1/protocol.json'))
    assert 'NOT fresh independent OOS' in protocol['final_evaluation']
    assert protocol['final_fit']['training_rows']==12172
    assert protocol['development_fit']['training_rows']==7502


def test_minutes_error_shapley_identity():
    import importlib.util
    import sys
    sys.path.insert(0,str(ROOT/'scripts'))
    spec=importlib.util.spec_from_file_location('composition_audit',ROOT/'scripts/audit_minutes_composition.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    f=pd.read_csv(ROOT/'analysis/results/minutes-decomposition-v1/conditional_minutes_holdout_predictions.csv.gz',nrows=50)
    a,b=module.contributions(f)
    assert np.allclose(a.sum(axis=1),abs(f.full_decomposition_xmins-f.minutes)-abs(f.role_aware_xmins-f.minutes))
    assert np.allclose(b.sum(axis=1),(f.full_decomposition_xmins-f.minutes)**2-(f.role_aware_xmins-f.minutes)**2)

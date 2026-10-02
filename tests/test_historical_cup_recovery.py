import sys
from pathlib import Path
import pandas as pd

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from recover_historical_cup_workload import match_archive_fixture,start_labels
from fpl_v1_1_model.workload import WorkloadHistory


def test_old_all_zero_intervals_are_unknown_starts():
    stats=pd.DataFrame({'start_min':[0]*15,'finish_min':[90]*11+[0]*4,'minutes_played':[90]*11+[10]*4})
    labels,complete=start_labels(stats)
    assert not complete and labels==[None]*15


def test_old_valid_intervals_recover_eleven_starters():
    stats=pd.DataFrame({'start_min':[0]*11+[70,75],'finish_min':[90]*13,'minutes_played':[90]*11+[20,15]})
    labels,complete=start_labels(stats)
    assert complete and labels==[True]*11+[False]*2


def test_invalid_sub_interval_does_not_fabricate_starts():
    stats=pd.DataFrame({'start_min':[0]*11+[70],'finish_min':[90]*11+[50],'minutes_played':[90]*11+[20]})
    labels,complete=start_labels(stats)
    assert not complete and labels==[None]*12


def test_archive_cannot_precede_game_or_match_future_fixture():
    from types import SimpleNamespace
    r=SimpleNamespace(match_id='25-26-europa-league-bologna-vs-aston-villa',tournament='europa-league',
      kickoff_time='2025-09-25T19:00:00Z',home_score=0,away_score=1)
    inventory=pd.DataFrame([{'competition':'europa-league','date':'2025-09-25','home':'astonvilla','away':'bologna','home_score':1,'away_score':0}])
    hit,ko,known=match_archive_fixture(r,inventory,'2025-09-26T22:00:00Z')
    assert known.isoformat()=='2025-09-26T22:00:00+00:00'
    try:match_archive_fixture(r,inventory,'2025-09-25T18:00:00Z')
    except ValueError:pass
    else:raise AssertionError('Pre-kickoff source accepted')
    inventory.loc[0,'date']='2026-04-09'
    try:match_archive_fixture(r,inventory,'2025-09-26T22:00:00Z')
    except ValueError:pass
    else:raise AssertionError('Later fixture joined to original payload')


def test_recovered_source_version_is_a_strict_history_boundary():
    h=WorkloadHistory();h.add_game(1,'restored','2025-10-02T19:00:00Z','2025-10-04T08:24:38Z',
      'europa-league',{'player':{'minutes':90,'started':None}},False)
    state,default,known=h.state(1,'2025-10-03T17:30:00Z')
    assert not state and known is None and default['work_team_matches_7d']==0
    state,default,known=h.state(1,'2025-10-04T08:24:38Z')
    assert not state and known is None
    state,default,known=h.state(1,'2025-10-04T10:00:00Z')
    assert state['player']['work_minutes_7d']==90 and state['player']['work_starts_7d']==0
    assert default['work_missing_player_stats_14d']==1


def test_saved_recovery_keeps_quarantine_and_unknowns():
    q=pd.read_csv(ROOT/'analysis/results/independent-europe-audit/workload_quarantine.csv')
    games=pd.read_csv(ROOT/'analysis/results/historical-cup-recovery-v1/restored_team_games.csv')
    players=pd.read_csv(ROOT/'analysis/results/historical-cup-recovery-v1/restored_player_minutes.csv')
    assert len(games)==7 and len(players)==104 and players.started.isna().sum()==15
    assert games.source_match_id.isin(q.match_id).all()
    v4=pd.read_csv(ROOT/'analysis/results/workload-recovered-v4/official_player_minutes.csv')
    assert not v4.match_id.isin(q.match_id).any()
    assert v4.match_id.str.startswith('restored-').sum()==104
    known=pd.to_datetime(games.available_at,utc=True);version=pd.to_datetime(games.source_version_at,utc=True)
    assert (known>=version).all()


def test_recovery_preserves_pl_only_and_role_control():
    file='reused_holdout_diagnostic_predictions.csv.gz'
    old=pd.read_csv(ROOT/'analysis/results/workload-quality-minutes-v3'/file)
    new=pd.read_csv(ROOT/'analysis/results/workload-recovered-minutes-v4'/file)
    cols=[c for c in old if 'pl_only' in c or 'role_control' in c]
    pd.testing.assert_frame_equal(old[cols],new[cols],check_exact=True)

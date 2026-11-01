import pandas as pd
import pytest
from score_prospective_player_forecast import score


def fixture():
    m=dict(schema='B-prospective-player-ledger-v1',season='s',records=1,recorded_at='2026-10-20T10:00:00Z',data_asof='2026-10-20T09:00:00Z',origin_deadline='2026-10-20T12:00:00Z',forecast_sha256='saved')
    p=[dict(fixture_uuid='f',player_uuid='p',team_id=1,position=3,fpl_code=123,eligible_for_pre_match_validation=True,kickoff='2026-10-21T18:00:00Z',p_start=.8,p_play=.9,p60=.7,p90=.5,expected_minutes=72.,xp=3.)]
    actual=pd.DataFrame([dict(season='s',fixture_uuid='f',player_uuid='p',team_id=1,is_final=True,known_at='2026-10-21T22:00:00Z',kickoff='2026-10-21T18:00:00Z',started=1,minutes=90,total_points=4)])
    return m,p,actual


def test_known_final_result_scores_archived_probabilities():
    m,p,a=fixture();r=score(m,p,a,asof='2026-10-22T12:00:00Z')
    assert r['scored_rows']==1 and r['minute_mae']==18 and r['xp_mae']==1
    assert r['metrics'][0]['brier']==pytest.approx(.04)
    assert r['model_recalibrated']is False


def test_in_progress_or_unknown_result_stays_pending():
    m,p,a=fixture();a['is_final']=False
    r=score(m,p,a,asof='2026-10-22T12:00:00Z')
    assert r['scored_rows']==0 and r['pending_rows']==1 and r['xp_mae']is None
    a['is_final']=True
    assert score(m,p,a,asof='2026-10-21T20:00:00Z')['pending_rows']==1


def test_late_capture_cannot_become_pre_deadline_by_flag():
    m,p,a=fixture();m['recorded_at']='2026-10-22T10:00:00Z'
    r=score(m,p,a,asof='2026-10-22T12:00:00Z')
    assert r['excluded_rows']==1 and r['scored_rows']==0


def test_wrong_club_and_duplicate_labels_rejected():
    m,p,a=fixture();a['team_id']=2
    with pytest.raises(ValueError,match='identity'):score(m,p,a,asof='2026-10-22T12:00:00Z')
    with pytest.raises(ValueError,match='Duplicate'):score(m,p,pd.concat([a,a]),asof='2026-10-22T12:00:00Z')


def test_missing_stable_code_is_excluded():
    m,p,a=fixture();p[0]['fpl_code']=None
    assert score(m,p,a,asof='2026-10-22T12:00:00Z')['excluded_rows']==1

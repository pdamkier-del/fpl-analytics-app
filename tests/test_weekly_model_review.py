from copy import deepcopy
import pandas as pd
import pytest
from weekly_model_review import select, report, COLS

NOW='2026-10-22T12:00:00Z'
def fixture():
    m=dict(schema='B-prospective-player-ledger-v1',season='s',records=2,recorded_at='2026-10-20T10:00:00Z',data_asof='2026-10-20T09:00:00Z',origin_deadline='2026-10-20T12:00:00Z',forecast_sha256='saved')
    row=dict(gw=2,fixture_uuid='f',player_uuid='p',team_id=1,position=3,fpl_code=123,eligible_for_pre_match_validation=True,kickoff='2026-10-21T18:00:00Z',p_start=.8,p_play=.9,p60=.7,p90=.5,expected_minutes=72.,xp=3.)
    later=dict(row,gw=3,fixture_uuid='future')
    receipt=dict(manifest=m,records=[row,later],published_at='2026-10-20T11:00:00Z',commit='source')
    actual=pd.DataFrame([dict(season='s',fixture_uuid='f',player_uuid='p',team_id=1,is_final=True,known_at='2026-10-21T22:00:00Z',kickoff='2026-10-21T18:00:00Z',started=1,minutes=90,total_points=4)],columns=COLS)
    boot=dict(season='s',events=[dict(id=1,finished=True,data_checked=True),dict(id=2,finished=True,data_checked=True)])
    return receipt,actual,boot

def test_scores_first_gw_once_and_season_matches():
    r,a,b=fixture();old=deepcopy(r);old['published_at']='2026-10-20T10:30:00Z';old['manifest']['forecast_sha256']='old'
    out=report([r,old],b,[],a,now=NOW)
    assert out['season_summary']['scored_rows']==1
    assert out['season_summary']['minute_mae']==18
    assert out['season_summary']['xp_mae']==1
    assert out['season_summary']['metrics'][0]['brier']==pytest.approx(.04)
    assert out['missing_gws']==[1]
    assert out['weeks'][1]['forecast_sha256']=='saved'
    assert out['completed_scored_gws']==1 and out['ts']['status']=='not_measured'

def test_capture_or_publication_after_deadline_excluded():
    r,a,b=fixture();r['published_at']='2026-10-20T12:00:00Z'
    out=report([r],b,[],a,now=NOW)
    assert out['excluded_late_captures']==1
    assert out['season_summary']['xp_mae']is None
    assert out['missing_gws']==[1,2]

def test_unchecked_or_unfinished_gw_never_scores():
    r,a,b=fixture();b['events'][1]['data_checked']=False
    out=report([r],b,[],a,now=NOW)
    assert out['weeks'][1]['status']=='pending_results'
    assert out['season_summary']['scored_rows']==0
    b['events'][1]['data_checked']=True;b['events'][1]['finished']=False
    assert report([r],b,[],a,now=NOW)['season_summary']['scored_rows']==0

def test_no_final_labels_remain_pending_not_zero_error():
    r,a,b=fixture();out=report([r],b,[],a.iloc[:0],now=NOW)
    assert out['weeks'][1]['pending_rows']==1
    assert out['season_summary']['minute_mae']is None

def test_future_publication_or_wrong_season_cannot_score():
    r,a,b=fixture();r['published_at']='2026-10-23T12:00:00Z'
    assert select([r],'s',NOW)[0]=={}
    assert select([r],'another-season',NOW)[0]=={}

def test_duplicate_actual_labels_or_wrong_team_fail_closed():
    r,a,b=fixture()
    with pytest.raises(ValueError,match='Duplicate'):report([r],b,[],pd.concat([a,a]),now=NOW)
    a['team_id']=2
    with pytest.raises(ValueError,match='identity'):report([r],b,[],a,now=NOW)

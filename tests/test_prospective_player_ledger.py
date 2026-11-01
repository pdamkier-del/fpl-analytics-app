import copy
import pytest
from analysis.archive_prospective_player_forecast import build_records


def source():
    q=dict(fixture_uuid='fixture',kickoff='2026-10-24T11:30:00Z',p_start=.6,
           p_60_plus=.55,p_90=.2,xmins=55,xpts=3,components={'appearance_points':1.5,'goal_points':1.5})
    f=dict(season='2026-27',forecast_sha256='sealed-source',data_asof='2026-10-23T12:00:00Z',
           origin_deadline='2026-10-23T17:30:00Z',players=[dict(id=399,player_uuid='stable',team_id=15,position=3,weeks=[dict(gw=8,fixtures=[q])])])
    return f,{'players':[dict(player_id='stable',fixture_id='fixture',p_play=.8)]}


def test_late_capture_cannot_be_backdated_using_early_data_asof():
    f,m=source()
    meta,rows=build_records(f,m,recorded_at='2026-10-24T14:00:00+02:00')
    assert meta['data_asof']=='2026-10-23T12:00:00Z'
    assert meta['eligible_records']==0
    assert rows[0]['eligible_for_pre_match_validation'] is False
    assert meta['whole_model_certification'] is False


def test_pre_deadline_export_keeps_exact_forecast_and_identity():
    f,m=source();before=copy.deepcopy(f)
    meta,rows=build_records(f,m,recorded_at='2026-10-23T15:00:00Z',catalogue=[{'id':399,'code':466052}])
    assert meta['eligible_records']==1 and rows[0]['fpl_code']==466052
    assert rows[0]['xp']==f['players'][0]['weeks'][0]['fixtures'][0]['xpts']
    assert rows[0]['expected_minutes']==55 and f==before


def test_timezone_and_duplicate_forecast_are_not_guessed():
    f,m=source()
    with pytest.raises(ValueError,match='timezone'):build_records(f,m,recorded_at='2026-10-23T15:00:00')
    f['players'][0]['weeks'][0]['fixtures']*=2
    with pytest.raises(ValueError,match='Duplicate'):build_records(f,m,recorded_at='2026-10-23T15:00:00Z')

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


def test_player_trace_does_not_score_pending_or_future_lead_weeks():
    from weekly_model_review import player_traces
    r,a,b=fixture();b['elements']=[dict(id=1,web_name='Test',element_type=3)]
    for p in r['records']:p['player_id']=1
    selected,_=select([r],'s',NOW)
    data=player_traces(selected,b,a);p=data['players'][0]
    assert len(p['weeks'])==1 and p['weeks'][0]['gw']==2
    assert p['summary']['xp_mae']==1 and p['summary']['minute_mae']==18
    pending=player_traces(selected,b,a.iloc[:0])['players'][0]
    assert pending['summary']['scored_gws']==0
    assert pending['summary']['xp_mae']is None


def test_old_publication_receipt_uses_real_public_clock_not_today():
    from weekly_model_review import receipt_from_original_publication
    from test_prospective_player_ledger import source
    f,mm=source();docs={'forecast_sha256':f['forecast_sha256'],'documents':{'current-players.json':{'players':[{'id':399,'code':466052}]}}}
    receipt=receipt_from_original_publication(f,mm,docs,published_at='2026-10-23T16:29:56Z',recovered_at='2026-10-26T12:00:00Z',commit='original-public-commit')
    assert receipt['manifest']['recorded_at']=='2026-10-23T16:29:56+00:00'
    assert receipt['manifest']['recovered_at']=='2026-10-26T12:00:00Z'
    assert receipt['records'][0]['eligible_for_pre_match_validation']is True
    with pytest.raises(ValueError,match='before deadline'):receipt_from_original_publication(f,mm,docs,published_at='2026-10-23T18:00:00Z',recovered_at='2026-10-26T12:00:00Z',commit='late-public-commit')


def test_only_official_zero_stats_create_zero_minute_labels(monkeypatch):
    from weekly_model_review import collect_outcomes
    r,_,b=fixture();p=r['records'][0];p.update(player_id=1,fixture_uuid='live-s-fpl-1')
    b['elements']=[dict(id=1,code=123)]
    fixtures=[dict(id=1,event=2,finished=True,team_h=1,team_a=2,kickoff_time=p['kickoff'])]
    calls=[]
    class Response:
        def __init__(self,data):self.data=data
        def raise_for_status(self):pass
        def json(self):return self.data
    def zero(url,**kwargs):
        calls.append(url)
        assert 'event/2/live/'in url
        return Response({'elements':[{'id':1,'stats':{'minutes':0,'starts':0,'total_points':0}}]})
    monkeypatch.setattr('weekly_model_review.requests.get',zero)
    out=collect_outcomes({2:r},b,fixtures,NOW)
    assert len(out)==1 and out.iloc[0].minutes==0 and out.iloc[0].total_points==0
    assert len(calls)==1
    def absent(url,**kwargs):return Response({'elements':[]}if 'event/'in url else{'history':[]})
    monkeypatch.setattr('weekly_model_review.requests.get',absent)
    assert len(collect_outcomes({2:r},b,fixtures,NOW))==0


def test_actual_player_history_without_predictions_never_enters_error_metrics():
    from weekly_model_review import player_traces,attach_actual_history
    r,a,b=fixture();b['elements']=[dict(id=1,code=123,web_name='Test',element_type=3)]
    for p in r['records']:p['player_id']=1
    selected,_=select([r],'s',NOW);traces=player_traces(selected,b,a)
    h=dict(observed_at=NOW,gw_rows=[dict(player_id=1,gw=1,gw_complete=True,stats=dict(minutes=90,starts=1,total_points=6))])
    cat=dict(season='s',players=[dict(id=1,code=123)])
    attach_actual_history(traces,h,cat,b)
    p=traces['players'][0]
    assert p['actual_history'][0]['points']==6
    assert p['summary']['scored_gws']==1 and p['summary']['xp_mae']==1
    cat['season']='another-season';attach_actual_history(traces,h,cat,b)
    assert p['actual_history']==[]


def test_actual_history_season_comes_from_fixture_start_year_not_catalogue():
    from weekly_model_review import attach_actual_history
    traces={'players':[{'id':1}]}
    history={'season':2026,'observed_at':NOW,'gw_rows':[dict(player_id=1,gw=1,gw_complete=True,stats=dict(minutes=90,total_points=6,starts=1))]}
    catalogue={'players':[{'id':1,'code':123}]}
    bootstrap={'season':'2026-27','elements':[{'id':1,'code':123}]}
    attach_actual_history(traces,history,catalogue,bootstrap)
    assert traces['players'][0]['actual_history'][0]['points']==6
    history['season']='2026';attach_actual_history(traces,history,catalogue,bootstrap)
    assert traces['players'][0]['actual_history'][0]['points']==6
    history['season']=2025;attach_actual_history(traces,history,catalogue,bootstrap)
    assert traces['players'][0]['actual_history']==[]

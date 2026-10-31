from copy import deepcopy
import json
import pytest
import recover_season_model_history as module

def fixture():
    p=dict(id=1,player_uuid='stable',team_id=10,weeks=[dict(gw=7,fixtures=[dict(fixture_uuid='live-2026-27-fpl-70',kickoff='2026-10-18T12:00:00Z',p_start=.8,xmins=80,simulated_minutes=72,xpts=4)])])
    doc=dict(players=[p],published_at='2026-10-17T09:00:00Z',data_asof='2026-10-17T08:00:00Z',publication_commit='original',archive_sha256='hash',model='original_locked_vFinal_diagnostic')
    stats=dict(minutes=90,starts=1,total_points=6)
    history=dict(match_rows=[dict(player_id=1,fixture_id=70,team_id=10,stats=stats,provisional=False)],gw_rows=[dict(player_id=1,gw=7,stats=stats,gw_complete=True)])
    cat=dict(players=[dict(id=1,code=99)])
    fixtures=dict(fixtures=[dict(id=70,gw=7,home=10,away=20,kickoff='2026-10-18T12:00:00Z',finished=True)])
    current=dict(players=[dict(id=1,player_uuid='stable')])
    return {7:doc},history,cat,fixtures,current

def test_actual_original_forecasts_keep_mm_and_pm_distinct():
    result,players,summaries,labels=module.evaluate(*fixture());w=result['weeks'][0]
    assert w['minute_mae']==18 and w['mm_minute_mae']==10
    assert w['xp_mae']==2 and w['xp_bias']==-2
    assert w['start_brier']==pytest.approx(.04)
    assert players[1][0]['expected_minutes']==72
    assert players[1][0]['mm_expected_minutes']==80
    assert 'p60'not in players[1][0] and summaries[1]['scored_gws']==1
    assert labels[0]['label_basis']=='official_fixture_history'

def test_absent_label_is_pending_not_zero():
    args=fixture();args[1]['match_rows']=[]
    result,players,summaries,_=module.evaluate(*args)
    assert result['weeks'][0]['pending_rows']==1 and summaries[1]['scored_gws']==0
    assert players[1][0]['actual_points']is None

def test_final_gw_all_zero_is_verifiable_zero():
    args=fixture();args[1]['match_rows']=[];args[1]['gw_rows'][0]['stats']={k:0 for k in ['minutes','starts','total_points']}
    result,_,_,labels=module.evaluate(*args)
    assert result['weeks'][0]['scored_rows']==1
    assert labels[0]['label_basis']=='official_final_GW_all_zero'

@pytest.mark.parametrize('change',['uuid','code','team','kickoff','gw','late_kickoff'])
def test_identity_and_kickoff_mismatches_never_score(change):
    args=fixture();doc=args[0][7];person=doc['players'][0]
    if change=='uuid':person['player_uuid']='other'
    elif change=='code':args[2]['players'][0]['code']=None
    elif change=='team':person['team_id']=99
    elif change=='kickoff':person['weeks'][0]['fixtures'][0]['kickoff']='2026-10-18T13:00:00Z'
    elif change=='gw':args[3]['fixtures'][0]['gw']=8
    else:doc['published_at']='2026-10-18T12:00:00Z'
    result,*_=module.evaluate(*args)
    assert result['weeks'][0]['scored_rows']==0

def test_unfinished_event_never_scores():
    args=fixture();args[1]['gw_rows'][0]['gw_complete']=False
    assert module.evaluate(*args)[0]['weeks'][0]['scored_rows']==0

def test_duplicate_outcomes_fail_closed():
    args=fixture();args[1]['match_rows']*=2
    with pytest.raises(ValueError,match='Duplicate'):module.evaluate(*args)

def test_origin_gw_only_no_six_horizon_double_counting():
    args=fixture();p=args[0][7]['players'][0];p['weeks'].append(dict(p['weeks'][0],gw=8))
    result,players,*_=module.evaluate(*args)
    assert result['weeks'][0]['scored_rows']==1 and len(players[1])==1

def test_recovery_uses_publication_clock_not_recovery_time(monkeypatch):
    base=dict(model='original_locked_vFinal_diagnostic',season='2026-27',gws=[7,8],origin_deadline='2026-10-17T10:00:00Z',data_asof='2026-10-17T08:00:00Z',players=[])
    def git(*args):
        if args[0]=='log':return b'late 2026-10-17T10:00:00Z\nnew 2026-10-17T09:30:00Z\nold 2026-10-17T09:00:00Z\n'
        return json.dumps(base).encode()
    monkeypatch.setattr(module,'git',git)
    selected,audit=module.recover('ref','2026-27','2026-10-27T00:00:00Z')
    assert selected[7]['publication_commit']=='new' and audit['late_documents']==1

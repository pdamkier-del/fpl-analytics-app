import copy
import pandas as pd
import pytest
from historical_manager_review import hindsight,states,actual_score
from fpl_xpts.season_replay import ReplayState,OwnedPlayer

def market():
    positions=[1]*2+[2]*5+[3]*5+[4]*3
    people=[dict(id=i+1,name=str(i+1),position=p,team_id=i//3+1,price_tenths=50,status='a')for i,p in enumerate(positions)]
    people.append(dict(id=16,name='Target',position=3,team_id=8,price_tenths=50,status='a'))
    state=ReplayState({p['id']:OwnedPlayer(p['id'],50)for p in people[:15]},0,1)
    actual={p['id']:dict(points=10 if p['id']==16 else 1,played=True)for p in people}
    return people,state,actual

def test_full_market_budget_hits_and_global_fpl_rescoring():
    people,state,actual=market();r=hindsight(state,people,actual,seconds=10)
    assert r['globally_optimal']and r['minimum_transfers_proven']
    assert r['incoming']==[16]and r['hits']==0 and r['points']==30 and r['bank_after']==0
    state.free_transfers=0;r=hindsight(state,people,actual,seconds=10)
    assert r['points']==26 and r['hits']==4
    actual[16]['points']=2;r=hindsight(state,people,actual,seconds=10)
    assert r['points']==12 and r['incoming']==[]

def test_cannot_afford_or_buy_unselectable_new_player():
    people,state,actual=market();people[-1]['price_tenths']=60
    assert hindsight(state,people,actual,seconds=10)['incoming']==[]
    state.bank=10;assert hindsight(state,people,actual,seconds=10)['incoming']==[16]
    people[-1]['status']='u';assert hindsight(state,people,actual,seconds=10)['incoming']==[]

def test_sale_value_uses_actual_purchase_price_not_current_market():
    people,state,actual=market();people[-1]['price_tenths']=51
    # A £0.1m increase on retained players does not create £0.1m sale profit.
    for p in people[:-1]:p['price_tenths']=51
    assert hindsight(state,people,actual,seconds=10)['incoming']==[]
    for p in people[:-1]:p['price_tenths']=52
    assert hindsight(state,people,actual,seconds=10)['incoming']==[16]

def test_historical_state_is_before_target_transfers_and_cash_checked():
    people,_,_=market();picks=[dict(element=p['id'])for p in people[:15]]
    history={'weeks':[dict(gw=1,picks=picks,active_chip=None,entry_history=dict(bank=250)),dict(gw=2,picks=[dict(element=16 if p['element']==8 else p['element'])for p in picks],active_chip='3xc',entry_history=dict(bank=240,event_transfers=1,event_transfers_cost=0))]}
    moves=[dict(event=2,time='2026-01-02T10:00:00Z',element_out=8,element_out_cost=50,element_in=16,element_in_cost=60)]
    initial={'elements':[dict(id=p['id'],now_cost=50)for p in people]};r=states(history,moves,initial)[2]
    assert r.bank==250 and r.free_transfers==1 and 8 in r.squad and 16 not in r.squad and r.chips_used['triple_captain']==[]
    history['weeks'][1]['entry_history']['bank']=999
    with pytest.raises(ValueError,match='cash'):states(history,moves,initial)


def test_chip_costs_and_scoring_are_separate():
    people,state,actual=market();state.free_transfers=0
    ordinary=hindsight(state,people,actual,seconds=10)
    wc=hindsight(state,people,actual,seconds=10,chip='wildcard')
    fh=hindsight(state,people,actual,seconds=10,chip='free_hit')
    tc=hindsight(state,people,actual,seconds=10,chip='triple_captain')
    bb=hindsight(state,people,actual,seconds=10,chip='bench_boost')
    assert ordinary['points']==26 and wc['points']==fh['points']==30
    assert wc['hits']==fh['hits']==0 and tc['points']==36 and bb['points']==30
    assert all(r['globally_optimal']for r in [ordinary,wc,fh,tc,bb])


def test_historical_draws_must_match_model_source_identity_and_means():
    from historical_manager_review import HistoricalScorer
    doc=dict(schema='B-current-season-backtest-v1',scope='retrospective_fixed_B_policy_not_original_forecast_not_independent_holdout',model_source='03d5c4d4777b44bc1d37884a1cf4dde106b45cab',gw=6,cutoff='2026-10-01T10:00:00Z',origin_deadline='2026-10-02T10:00:00Z',draws=2,players=[dict(fixture_uuid='f',player_uuid='p',player_id=1,fpl_code=10,gw=6,xp=1)])
    samples=dict(gw=6,cutoff=doc['cutoff'],draws=2,records=[dict(fixture_uuid='f',player_uuid='p',scenarios=dict(points=[0,2],minutes=[0,90]))]);people=[dict(id=1,code=10,position=1)]
    assert HistoricalScorer(doc,samples,people).weeks[1,6]['xpts']==1
    bad=copy.deepcopy(doc);bad['players'][0]['xp']=2
    with pytest.raises(ValueError,match='means'):HistoricalScorer(bad,samples,people)
    bad=copy.deepcopy(doc);bad['model_source']='0'*40
    with pytest.raises(ValueError,match='model source'):HistoricalScorer(bad,samples,people)
    bad=copy.deepcopy(doc);bad['players'][0]['fpl_code']=11
    with pytest.raises(ValueError,match='identity'):HistoricalScorer(bad,samples,people)

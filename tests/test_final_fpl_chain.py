import pandas as pd
import pytest
from fpl_xpts.final_chip_coordinator import choose_final_chip
from fpl_xpts.simple_chip_thresholds import choose_locked_fh_wc
from fpl_xpts.tc_chip_bridge import tc_candidate_eligible,tc_captain_lineup,tc_v2_opportunity
from fpl_xpts.bench_boost_policy import LOCKED_LAMBDA_BB

def test_locked_parameters():
    assert LOCKED_LAMBDA_BB==20
    assert choose_locked_fh_wc(6,3,10,20).choice in ('normal','fh','wc')

def test_no_optional_chips_matches_frozen_fh_wc():
    for gw in (1,6,19,20,26,38):
        for fh,wc in ((0,0),(15,1),(0,28),(50,100)):
            orig=choose_locked_fh_wc(gw,3,fh,wc)
            dec=choose_final_chip(gw=gw,fh_available=True,wc_available=True,
                bb_available=False,tc_available=False,fh_gain=fh,wc_gain=wc)
            assert dec.chip==orig.choice

def test_exactly_one_chip_highest_edge():
    dec=choose_final_chip(gw=10,fh_available=True,wc_available=True,bb_available=True,
        tc_available=True,fh_gain=8,wc_gain=11,bb_gain=12,
        tc_action='USE_TC',tc_use_edge=4.,tc_candidate_is_eligible=True)
    assert dec.chip=='tc'
    assert dec.q_tc==4.0
    dec=choose_final_chip(gw=10,fh_available=True,wc_available=True,bb_available=True,
        tc_available=True,fh_gain=8,wc_gain=11,bb_gain=12,
        tc_action='USE_TC',tc_use_edge=4.,tc_candidate_is_eligible=False)
    assert dec.chip=='fh'

def test_tc_use_request_not_eligible_cannot_be_executed():
    d=choose_final_chip(gw=19,fh_available=False,wc_available=False,
        bb_available=False,tc_available=True,tc_action='USE_TC',
        tc_use_edge=20,tc_candidate_is_eligible=False)
    assert d.chip=='normal'

def test_legal_tc_captain_change_without_changing_xi():
    f=pd.DataFrame([
        dict(id=i,role='C' if i==1 else 'VC' if i==2 else 'XI' if i<=11 else 'Bench 1')
        for i in range(1,16)
    ])
    decision={'action':'USE_TC','candidate_id':3}
    assert tc_candidate_eligible(decision,f)
    adjusted=tc_captain_lineup(f,3)
    assert adjusted.loc[adjusted.role.eq('C'),'id'].tolist()==[3]
    assert adjusted.loc[adjusted.role.eq('VC'),'id'].tolist()==[2]
    assert sorted(adjusted[adjusted.role.isin(('XI','C','VC'))].id)==list(range(1,12))
    with pytest.raises(ValueError):tc_captain_lineup(f,15)

def test_tc_v2_only_offers_current_owned_candidates():
    f=pd.DataFrame([
        dict(gw=19,candidate_id=1,candidate_name='Not owned',points=12.0),
        dict(gw=19,candidate_id=2,candidate_name='Owned',points=7.0)])
    d=tc_v2_opportunity(f,19,eligible_current_ids={2})
    assert d['action']=='USE_TC'
    assert int(d['candidate_id'])==2

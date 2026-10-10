import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from live_historical_membership import recover_zero_club

def test_verified_zero_uses_registered_club_not_later_transfer_club():
    assert recover_zero_club({'code':12,'team':2},{'fpl_code':12,'team_id':9},
        {'minutes':0,'starts':0},{'team_h':2,'team_a':5})==2

def test_absent_or_uncertain_outcome_never_becomes_zero():
    for stats in [{},{'minutes':None,'starts':0},{'minutes':1,'starts':0},{'minutes':0,'starts':1}]:
        assert recover_zero_club({'code':12,'team':2},{'fpl_code':12},stats,{'team_h':2,'team_a':5}) is None

def test_inexact_identity_or_fixture_is_not_forced():
    assert recover_zero_club({'code':12,'team':2},{'fpl_code':13},{'minutes':0,'starts':0},{'team_h':2,'team_a':5}) is None
    assert recover_zero_club({'code':12,'team':9},{'fpl_code':12},{'minutes':0,'starts':0},{'team_h':2,'team_a':5}) is None

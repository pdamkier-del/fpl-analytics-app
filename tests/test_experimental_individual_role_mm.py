from datetime import datetime,timezone,timedelta
import sys
from pathlib import Path
import pytest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
from experimental_individual_role_mm import role_start_probability

T=datetime(2025,10,15,tzinfo=timezone.utc)
def obs(days,started,available=True):
    return {"known_at":T-timedelta(days=days),"started":started,"available":available}

def test_injury_absence_does_not_erase_starter_role():
    base=[obs(i,True) for i in range(1,10)]
    p=role_start_probability(base,cutoff=T)["role_start_prior"]
    injured=role_start_probability(base+[obs(0,False,False)],cutoff=T)["role_start_prior"]
    assert injured==p

def test_single_bench_does_not_collapse_regular_starter():
    z=role_start_probability([obs(i,True) for i in range(2,12)]+[obs(1,False)],cutoff=T)
    assert z["role_start_prior"]>.65

def test_persistent_benching_changes_role():
    regular=[obs(i,True) for i in range(11,21)]
    recent=[obs(i,False) for i in range(1,11)]
    a=role_start_probability(regular,cutoff=T)["role_start_prior"]
    b=role_start_probability(regular+recent,cutoff=T)["role_start_prior"]
    assert b<a

def test_future_result_cannot_leak():
    base=[obs(1,True)]
    after={"known_at":T+timedelta(days=1),"started":False,"available":True}
    assert role_start_probability(base,cutoff=T)==role_start_probability(base+[after],cutoff=T)

def test_unknown_availability_is_not_negative_role_evidence():
    base=[obs(1,True)]
    unknown={"known_at":T,"started":False,"available":None}
    assert role_start_probability(base,cutoff=T)==role_start_probability(base+[unknown],cutoff=T)

def test_cutoff_required():
    with pytest.raises(ValueError):
        role_start_probability([],cutoff=None)

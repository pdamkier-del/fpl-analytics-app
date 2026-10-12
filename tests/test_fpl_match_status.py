import sys
from pathlib import Path
import pytest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from fpl_match_status import played,cutoff_safe

def test_verified_provisional_full_time_is_cutoff_safe_only_after_existing_proxy():
    f={'finished':False,'finished_provisional':True,'started':True,'minutes':90,'kickoff_time':'2026-10-11T15:30:00Z'}
    assert played(f)
    assert cutoff_safe(f,'2026-10-12T09:00:00Z')
    assert not cutoff_safe(f,'2026-10-11T19:30:00Z')
    assert not cutoff_safe(f,'2026-10-11T18:00:00Z')
    for field,value in [('finished_provisional',False),('started',False),('minutes',89)]:
        assert not played({**f,field:value})
    assert not cutoff_safe({**f,'kickoff_time':None},'2026-10-12T09:00:00Z')
    with pytest.raises(ValueError):cutoff_safe(f,'2026-10-12T09:00:00')

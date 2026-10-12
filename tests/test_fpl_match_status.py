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

def test_mixed_archive_formats_preserve_exact_instants_for_locked_validator():
    import pandas as pd
    from fpl_match_status import canonical_timestamp
    from fpl_v1_1_model.team_news_history import validate_strict_projection
    times=['2026-10-01T09:00:00Z','2026-10-10T09:00:00.123456+00:00']
    normalized=[canonical_timestamp(s) for s in times]
    assert [pd.Timestamp(s) for s in normalized]==[pd.Timestamp(s) for s in times]
    rows=[dict(gw=n,cutoff=canonical_timestamp('2026-10-10T10:00:00Z'),player_uuid=str(n),effective_at=t,identity_status='mapped',timing_verified=True,normalized_availability_state='AVAILABLE',scoped_chance=100,tier='strict') for n,t in enumerate(normalized,1)]
    assert len(validate_strict_projection(pd.DataFrame(rows)))==2

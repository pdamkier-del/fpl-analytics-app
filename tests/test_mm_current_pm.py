import pandas as pd
import pytest
from experiment_mm_current_pm import current_minute_fields


def test_current_assembly_aliases_share_the_candidate_minute_identity():
    base=pd.DataFrame({'player_uuid':['a','b'],'p_start':[.9,.1],'xmins':[80.,3.],'mm_q_sub':[.2,.3]})
    state=pd.DataFrame({'player_uuid':['b','a'],'p':[.1,.8],'s':[70.,85.],'q':[.4,.2],'c':[20.,10.],'x':[14.2,68.4]})
    out=current_minute_fields(base,state)
    assert out.player_uuid.tolist()==['a','b']
    assert out.p_start.tolist()==[.8,.1]
    assert out.xmins.tolist()==[68.4,14.2]
    assert out.mm_q_sub.tolist()==[.2,.4]
    assert out.mm_sub_minutes.tolist()==[10.,20.]
    assert out.expected_minutes.tolist()==[68.4,14.2]
    assert base.p_start.tolist()==[.9,.1]
    assert (out.p_start*out.start_minutes_mean+(1-out.p_start)*out.mm_q_sub*out.mm_sub_minutes).tolist()==pytest.approx(out.xmins.tolist())


def test_current_state_requires_every_player_identity():
    with pytest.raises(ValueError):current_minute_fields(pd.DataFrame({'player_uuid':['a','b']}),pd.DataFrame({'player_uuid':['a']}))


def test_dataclass_tuple_component_guard_respects_numeric_serialization_tolerance():
    from experiment_mm_current_pm import component_differences
    assert component_differences({'players':({'mu':1.0},)},{'players':({'mu':1.+1e-12},)})==[]
    diff=component_differences({'players':({'mu':1.0},)},{'players':({'mu':1.01},)})
    assert diff[0]['path']=='input.players.0.mu'


def test_component_guard_rejects_different_roster_or_fields():
    from experiment_mm_current_pm import component_differences
    assert component_differences({'players':()},{'players':({},)})
    assert component_differences({'players':()},{'other':()})

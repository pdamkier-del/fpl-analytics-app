import pandas as pd
import pytest
from experiment_mm_current_pm import overlay_components


def test_component_rebuild_retains_identity_and_original_order():
    base=pd.DataFrame({'player_uuid':['a','b'],'minutes':[90,79],'untouched':[1,2]},index=[5,9])
    built=pd.DataFrame({'player_uuid':['b','a'],'minutes':[20,80]})
    out=overlay_components(base,built)
    assert out.to_dict('list')=={'player_uuid':['a','b'],'minutes':[80,20],'untouched':[1,2]}
    assert out.index.tolist()==[5,9]
    assert base.minutes.tolist()==[90,79]


def test_component_rebuild_rejects_missing_or_duplicate_identity():
    base=pd.DataFrame({'player_uuid':['a','b']})
    for ids in [['a'],['a','a'],['a','c']]:
        with pytest.raises(ValueError):overlay_components(base,pd.DataFrame({'player_uuid':ids}))

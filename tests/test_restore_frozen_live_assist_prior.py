import importlib.util
from pathlib import Path
import pandas as pd
import pytest
spec=importlib.util.spec_from_file_location('assist',Path(__file__).resolve().parents[1]/'scripts/restore_frozen_live_assist_prior.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
def sample():
    base=pd.DataFrame([{'fixture_uuid':'f','player_uuid':'p','cutoff':'2026-10-10T10:00:00Z'}])
    past=pd.DataFrame([{'goals':2,'fpl_assists':1,'available_at':'2026-10-01T10:00:00Z'},
                       {'goals':2,'fpl_assists':2,'available_at':'2026-10-02T10:00:00Z'}])
    return base,past
def test_exact_frozen_historic_formula():
    base,past=sample();r,a=m.derive(base,past)
    assert r.assist_probability_per_goal.iloc[0]==.75
    assert a['locked_model_math_unchanged']
def test_postcutoff_evidence_rejected():
    base,past=sample();past.loc[0,'available_at']='2026-10-11T10:00:00Z'
    with pytest.raises(ValueError,match='target-future'):m.derive(base,past)
def test_missing_source_assists_rejected():
    base,past=sample()
    with pytest.raises(ValueError,match='fpl_assists'):m.derive(base,past.drop(columns='fpl_assists'))

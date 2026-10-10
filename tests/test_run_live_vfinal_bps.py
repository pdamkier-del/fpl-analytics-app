import importlib.util
from pathlib import Path
import numpy as np
import pandas as pd
import pytest
spec=importlib.util.spec_from_file_location('bps',Path(__file__).resolve().parents[1]/'scripts/run_live_vfinal_bps.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)

def sample():
    t=pd.DataFrame([{'fixture_uuid':'f1','player_uuid':'p1','target_gw':6,
                     'cutoff':'2026-10-09T12:00:00Z','pos':'MID'}])
    l=pd.DataFrame([{k:0.0 for k in m.LEDGER_FIELDS if k not in ('player_uuid','available_at')}])
    l['player_uuid']='p1';l['available_at']='2026-10-08T12:00:00Z';l['minutes_played']=90.
    return t,l

def test_missing_real_provider_action_is_rejected():
    t,l=sample()
    l=l.drop(columns=['tackle_rate90'])
    with pytest.raises(ValueError,match='Missing verified'):m.calculate(t,l,{},{})

def test_future_provider_event_is_rejected():
    t,l=sample();l['available_at']='2026-10-10T13:00:00Z'
    with pytest.raises(ValueError,match='pre-cutoff'):m.calculate(t,l,{},{})

def test_frozen_regression_used_without_refit(monkeypatch):
    t,l=sample()
    monkeypatch.setattr(m,'feature_frame',lambda target,half,ledger:target.assign(x=2.))
    monkeypatch.setattr(m,'apply_model',lambda frame,model:np.array([4.25]))
    out=m.calculate(t,l,{'cols':['x']},{'position_sd90':{'MID':2.5},'global_sd90':3.})
    assert out.bg_mean_rate90.iloc[0]==4.25
    assert out.bg_sd90.iloc[0]==2.5

def test_frozen_bps_history_uses_utc_timestamps(monkeypatch):
    t,l=sample()
    def verify(target,half,ledger):
        assert pd.api.types.is_datetime64_any_dtype(target.cutoff)
        assert pd.api.types.is_datetime64_any_dtype(ledger.available_at)
        assert ledger.available_at.iloc[0] < target.cutoff.iloc[0]
        return target.assign(x=1.)
    monkeypatch.setattr(m,'feature_frame',verify)
    monkeypatch.setattr(m,'apply_model',lambda frame,model:np.array([3.]))
    out=m.calculate(t,l,{'cols':['x']},{'position_sd90':{'MID':2.},'global_sd90':3.})
    assert out.bg_mean_rate90.iloc[0]==3.

import importlib.util
from pathlib import Path
import pandas as pd
import pytest
p=Path(__file__).resolve().parents[1]/"scripts/audit_completed_gw_history.py"
spec=importlib.util.spec_from_file_location("gate",p)
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
def fixtures():
    h=pd.DataFrame([
       dict(gw=i,available_at=f"2026-08-{14+i:02d}T23:00:00Z",
            fixture_uuid=f"f{i}",player_uuid="p1",started=1,minutes=90)
       for i in range(1,6)])
    f=pd.DataFrame([dict(gw=6,target_gw=6,cutoff="2026-09-01T10:00:00Z",
                         fixture_uuid="f6",player_uuid="p1")])
    return h,f
def test_all_completed_gws_are_used():
    h,f=fixtures();assert m.audit(h,f)["completed_gws"]==[1,2,3,4,5]
def test_missing_week_rejected():
    h,f=fixtures()
    with pytest.raises(ValueError,match="Missing/extra"):m.audit(h[h.gw!=3],f)
def test_future_results_rejected():
    h,f=fixtures();h.loc[0,"available_at"]="2026-09-02T00:00:00Z"
    with pytest.raises(ValueError,match="Future"):m.audit(h,f)
def test_duplicate_player_fixture_rejected():
    h,f=fixtures();h=pd.concat([h,h.iloc[[0]]])
    with pytest.raises(ValueError,match="Duplicate"):m.audit(h,f)
def test_unknown_starters_rejected():
    h,f=fixtures();h.loc[0,"started"]=None
    with pytest.raises(ValueError,match="started"):m.audit(h,f)

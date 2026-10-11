import importlib.util
from datetime import datetime,timezone
from pathlib import Path
import pytest

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('official_window',ROOT/'scripts/verify_official_forecast_window.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)

def data():
    return {'gws':list(range(7,13)),'origin_deadline':'2026-10-17T10:00:00Z'}, {'events':[{'id':7,'is_next':True,'deadline_time':'2026-10-17T10:00:00Z'}]}

def test_matching_official_deadline():
    f,b=data();assert m.verify(f,b,datetime(2026,10,11,tzinfo=timezone.utc))==7

def test_a_later_official_gw_rejects_old_forecast():
    f,b=data();b['events'][0]['id']=8
    with pytest.raises(ValueError,match='changed'):m.verify(f,b,datetime(2026,10,11,tzinfo=timezone.utc))

def test_moved_or_elapsed_deadline_rejected():
    f,b=data();b['events'][0]['deadline_time']='2026-10-17T09:00:00Z'
    with pytest.raises(ValueError,match='differs'):m.verify(f,b,datetime(2026,10,11,tzinfo=timezone.utc))
    f,b=data()
    with pytest.raises(ValueError,match='changed'):m.verify(f,b,datetime(2026,10,17,10,tzinfo=timezone.utc))

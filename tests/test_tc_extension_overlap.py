import importlib.util
from pathlib import Path
import numpy as np
import pandas as pd
import pytest

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('tc_extension',ROOT/'scripts/run_live_tc_scenarios.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)

def test_observed_near_zero_roundoff_is_checked_without_mutating_inputs():
    a=pd.DataFrame({'fixture_uuid':['f'],'xi_score_margin':[.125],'xmins':[75.]})
    b=a.copy();b.loc[0,'xi_score_margin']+=15*np.spacing(.125);b.loc[0,'xmins']+=2.1316282072803006e-14
    before=a.copy();drift=m.verify_extension_overlap(a,b)
    assert a.equals(before) and drift['xi_score_margin']['max_ulp']==15

def test_material_numeric_difference_is_rejected():
    a=pd.DataFrame({'fixture_uuid':['f'],'p_start':[.5]});b=a.copy();b.loc[0,'p_start']+=1e-10
    with pytest.raises(ValueError,match='differs materially'):m.verify_extension_overlap(a,b)

def test_identity_or_missing_value_change_is_rejected():
    a=pd.DataFrame({'fixture_uuid':['f'],'p_start':[.5]});b=a.copy();b.loc[0,'fixture_uuid']='other'
    with pytest.raises(ValueError,match='nonfloating'):m.verify_extension_overlap(a,b)
    b=a.copy();b.loc[0,'p_start']=np.nan
    with pytest.raises(ValueError,match='differs materially'):m.verify_extension_overlap(a,b)

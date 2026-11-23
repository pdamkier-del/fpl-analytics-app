from pathlib import Path
import sys
import copy
import pytest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from adapter_v2 import adapt
from test_contracts import fixture

def test_roundoff_guard_preserves_values_and_sampling_threshold():
    f,mm=fixture();mm['players'][0]['p_play']=-4.440892098500626e-16
    mm['players'][1]['p_play']=.2
    before=copy.deepcopy(mm);original=copy.deepcopy(f)
    result,eligible=adapt(f,mm,lambda f:None,original=False)
    assert mm==before and result is f and f==original
    assert 1 not in eligible and 2 in eligible

def test_substantive_probability_error_still_blocks():
    f,mm=fixture();mm['players'][0]['p_play']=-.01
    with pytest.raises(ValueError,match='Invalid native'):adapt(f,mm,lambda f:None,original=False)

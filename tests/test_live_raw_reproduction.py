import sys
from pathlib import Path
import numpy as np
import pandas as pd
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from audit_live_raw_reproduction import numeric_diff
from locked_numerical_runtime import ENV

def test_exact_audit_does_not_hide_small_optimizer_input_drift():
    a=pd.DataFrame({'slope':[0.,1.],'id':['a','b']});b=a.copy()
    b.loc[0,'slope']=1e-14
    assert np.allclose(a.slope,b.slope)
    assert numeric_diff(a,b)['slope']=={'rows':1,'max_abs':1e-14}

def test_runtime_does_not_tune_original_model():
    assert ENV['PYTHONHASHSEED']=='0' and ENV['OPENBLAS_NUM_THREADS']=='1'
    assert ENV['OPENBLAS_CORETYPE']=='NEHALEM'
    assert not any('SEED' in k for k in ENV if k!='PYTHONHASHSEED')

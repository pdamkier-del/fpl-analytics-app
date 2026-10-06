import numpy as np
import pandas as pd
import pytest
from fpl_v1_1_model.availability_projection import project_exact_starters_with_caps

def frame(n=15):
    return pd.DataFrame({
        "fixture_uuid":["f"]*n,
        "team_id":[1]*n,
    })

def test_hard_out_is_zero_and_mass_redistributes():
    f=frame()
    p=np.array([.9]*11+[.1]*4)
    caps=np.ones(15);caps[0]=0.0
    out=project_exact_starters_with_caps(f,p,caps)
    assert out[0]==pytest.approx(0.0,abs=1e-10)
    assert out.sum()==pytest.approx(11.0,abs=1e-8)
    assert np.all(out<=caps+1e-9)

def test_soft_doubt_caps_probability():
    f=frame()
    p=np.array([.9]*11+[.1]*4)
    caps=np.ones(15);caps[0]=.5
    out=project_exact_starters_with_caps(f,p,caps)
    assert out[0]<=.5+1e-9
    assert out.sum()==pytest.approx(11.0,abs=1e-8)

def test_infeasible_caps_raise():
    f=frame(11)
    p=np.array([.8]*11)
    caps=np.array([.5]*11)
    with pytest.raises(ValueError):
        project_exact_starters_with_caps(f,p,caps)

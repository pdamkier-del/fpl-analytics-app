"""Protect the experiment from postponed-match and cold-start leakage."""
import numpy as np,pandas as pd
from audit_duration_walkforward import predictions,H,GRID

def test_postponed_prior_gw_and_target_outcome_are_not_features():
    f=pd.DataFrame([
        dict(fixture='past-1',player='x',gw=1,kickoff='2024-07-01T12:00:00Z',available=pd.Timestamp('2024-07-01T16:00:00Z'),started=1,minutes=90),
        dict(fixture='past-2',player='x',gw=2,kickoff='2024-07-05T12:00:00Z',available=pd.Timestamp('2024-07-05T16:00:00Z'),started=1,minutes=60),
        dict(fixture='postponed',player='x',gw=3,kickoff='2024-07-30T12:00:00Z',available=pd.Timestamp('2024-07-30T16:00:00Z'),started=1,minutes=1),
        dict(fixture='target',player='x',gw=6,kickoff='2024-07-15T12:00:00Z',available=pd.Timestamp('2024-07-15T16:00:00Z'),started=1,minutes=88),
    ])
    d={6:pd.Timestamp('2024-07-10T12:00:00Z')}
    p=predictions(f,d);assert len(p)==len(GRID)
    weight=2**(-1/H)
    assert np.isclose(p.loc[np.isclose(p.half,H),'pred'].iloc[0],(90*weight+60)/(weight+1))
    changed=f.copy();changed.loc[changed.fixture.isin(['postponed','target']),'minutes']=20
    assert np.allclose(p.pred,predictions(changed,d).pred)

def test_no_history_is_not_invented_for_new_player():
    f=pd.DataFrame([dict(fixture='first',player='new',gw=6,kickoff='2024-07-15T12:00:00Z',available=pd.Timestamp('2024-07-15T16:00:00Z'),started=1,minutes=90)])
    assert predictions(f,{6:pd.Timestamp('2024-07-10T12:00:00Z')}).empty

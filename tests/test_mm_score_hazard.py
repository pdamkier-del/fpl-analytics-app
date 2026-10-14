import numpy as np
import pandas as pd
from experiment_mm_score_hazard import expected,score_features

class ConstantHazard:
    def __init__(self,p):self.p=p
    def predict_proba(self,x):return np.tile([1-self.p,self.p],(len(x),1))

def frame():
    return pd.DataFrame(dict(gw=[7],pos=['FWD'],team_id=[1],duration_h6=[88.],start_share6=[1.],team_rest_days=[7.],minutes_14d=[180.]))

def record():return dict(origin=7,fixture='f',home=1,input=dict(lambda_home_goals=2.,lambda_away_goals=1.),reference={'p':9999})

def test_zero_hazard_preserves_complete_match_and_no_target_outcome_use():
    r=record();a=expected(ConstantHazard(0),frame(),r)
    r['reference']={'p':-9999};r['actual_goals']=[20,0]
    assert np.array_equal(expected(ConstantHazard(0),frame(),r),a)
    assert a[0]==90

def test_half_open_context_features_and_midpoint_integration():
    f=pd.concat([frame()]*2,ignore_index=True)
    x=score_features(f,np.array([3.,-2.]),np.array([55,60]))
    assert list(x.lead_late)==[0,0]
    assert list(x.trail)==[0,2]
    assert expected(ConstantHazard(1),frame(),record())[0]==2.5

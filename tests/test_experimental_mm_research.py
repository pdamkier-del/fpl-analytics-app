import numpy as np
import pandas as pd
import pytest
from fpl_v1_1_model.experimental_mm_research import empirical_hazard,hazard_mean,project_partition,fit_start,survival_prediction

def test_survival_mean_matches_complete_censored_observations():
    # Completion at 90 remains mass at the horizon, not an exit event.
    t=np.array([40,60,79,90,90])
    h,r,e=empirical_hazard(t)
    assert e.sum()==3 and r[89]==2
    assert np.isclose(hazard_mean(h),t.mean())
    assert hazard_mean(np.zeros(90))==90

def test_weighted_survival_and_invalid_inputs():
    t=np.array([20,60,90]);w=np.array([1,2,3])
    assert np.isclose(hazard_mean(empirical_hazard(t,w)[0]),np.average(t,weights=w))
    with pytest.raises(ValueError):empirical_hazard([79.5])
    with pytest.raises(ValueError):hazard_mean(np.ones(89))

def roster():
    return pd.DataFrame(dict(fixture_uuid=['f']*16,team_id=[1]*16,pos=['GK']*2+['MID']*14))

def test_partition_keeps_hard_endpoints_and_exact_counts():
    f=roster();p=np.array([0,.4]+[.6]*13+[1.])
    q=project_partition(f,p)
    assert q[0]==0 and q[1]==1 and q[-1]==1
    assert np.isclose(q[2:].sum(),10)
    with pytest.raises(ValueError):project_partition(f,np.zeros(16))

def test_survival_rejects_future_pool_and_preserves_no_history_fallback():
    target=pd.DataFrame([dict(cutoff='2025-01-01T00:00:00Z',player_uuid='new',pos='FWD',new_start_minutes=78)])
    obs=pd.DataFrame(dict(player_uuid=['p'],started=[1],minutes=[90],known=[pd.Timestamp('2024-12-01',tz='UTC')]))
    pool=obs.assign(pos='MID')
    assert survival_prediction(target,obs,pool)[0]==78
    pool['known']=pd.Timestamp('2025-02-01',tz='UTC')
    with pytest.raises(ValueError):survival_prediction(target,obs,pool)

def test_small_training_retains_archived_start_probability():
    target=pd.DataFrame(dict(new_p_start=[.2,.8]))
    train=pd.DataFrame(dict(y=[0,1]))
    assert np.array_equal(fit_start(train,target),[.2,.8])

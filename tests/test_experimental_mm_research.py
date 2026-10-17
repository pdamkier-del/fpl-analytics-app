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

def test_partition_respects_soft_availability_caps():
    f=roster();f['team_news_availability_cap']=1.
    f.loc[0,'team_news_availability_cap']=.1
    p=np.array([.8,.2]+[.6]*14)
    q=project_partition(f,p)
    assert q[0]<=.1 and np.isclose(q[:2].sum(),1)

def test_mm_change_reaches_both_original_pm_alias_sets():
    from capture_mm_pm_inputs import minute_fields
    f=pd.DataFrame(dict(player_uuid=['p','q']))
    state=pd.DataFrame(dict(player_uuid=['q','p'],p=[.5,.8],s=[80.,85.],q=[.2,.3],c=[10.,15.]))
    state['x']=state.p*state.s+(1-state.p)*state.q*state.c
    x=minute_fields(f,state)
    assert np.allclose(x.control_xmins,x.v4_workload_start_xmins)
    assert np.allclose(x.expected_minutes,[68.9,41.])
    assert np.allclose(x.control_xmins,x.control_p_start*x.start_minutes_mean+(1-x.control_p_start)*x.p_cameo_given_bench*x.cameo_minutes_mean)

def test_start_fit_rejects_future_outcomes_with_mixed_timestamp_styles():
    train=pd.DataFrame(dict(y=[0,1],outcome_known_at=['2024-12-01 00:00:00+00:00','2025-02-01T00:00:00Z']))
    target=pd.DataFrame(dict(new_p_start=[.5],cutoff=['2025-01-01T00:00:00Z']))
    with pytest.raises(ValueError):fit_start(train,target)

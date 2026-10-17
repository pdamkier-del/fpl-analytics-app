import numpy as np
import pandas as pd
from postprocess_dynamic_pm_v2 import compare_teams,point_losses,reliability_groups


def test_paired_team_ci_is_zero_for_identical_forecasts():
    f=pd.DataFrame([dict(fixture_uuid=str(i//2),team_id=i%2,mode=m,xg=1.+i/10,goals=i%3,xg_pred=1.2,goal_pred=1.1)for m in ['fixed','candidate']for i in range(8)])
    r=compare_teams(f)
    for target in ['xg','goals']:
        for metric in ['mae','rmse','poisson_deviance']:
            assert r['candidate'][target][metric]['delta']==0
            assert r['candidate'][target][metric]['fixture_bootstrap_95_ci']==[0.,0.]


def test_point_losses_use_observed_events_and_do_not_mutate_inputs():
    f=pd.DataFrame(dict(xp=[2.,4.],total_points=[1,6],expected_bonus=[.3,.8],bonus=[0,1],goal_mu=[.1,.5],goals=[0,2],assist_mu=[.2,.4],fpl_assists=[1,0]))
    p=point_losses(f)
    assert 'point_abs_error' not in f
    assert np.array_equal(p.point_squared_error,[1,4])
    assert np.allclose(p.assist_abs_error,[.8,.4])


def test_reliability_cohorts_do_not_saturate_on_tiny_positive_mass_or_fit_test_cutoffs():
    cols=['log_minutes','relative_variance','lineup_change','stability','disagreement','new_fraction','club_fraction','role_fraction','return_proxy']
    dev=pd.DataFrame({k:[.0001,.01,.2]for k in cols});target=pd.DataFrame({k:[.001,.3]for k in cols})
    grouped,cuts=reliability_groups(target,dev)
    assert grouped.new_players.tolist()==['low','high']
    assert grouped.absence_return_proxy.tolist()==['low','high']
    assert cuts['new_fraction']==.01
    target.loc[1,:]=1000
    assert reliability_groups(target,dev)[1]==cuts
    assert np.issubdtype(dev.lineup_change.dtype,np.number)

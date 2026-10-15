import numpy as np
import pandas as pd
from postprocess_dynamic_pm_v2 import compare_teams,point_losses


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

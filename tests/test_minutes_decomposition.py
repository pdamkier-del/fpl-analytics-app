from pathlib import Path
import numpy as np
import pandas as pd
from fpl_v1_1_model.minutes_decomposition import compose_expected_minutes,component_inputs

ROOT=Path(__file__).resolve().parents[1]


def test_conditional_minutes_identity_and_bounds():
    result=compose_expected_minutes(np.array([1,0,.5]),np.array([80,90,80]),np.array([0,.4,.2]),np.array([10,20,10]))
    assert np.allclose(result,[80,8,41])
    assert np.allclose(compose_expected_minutes([0,.5,1],[90,90,90],[1,1,1],[90,90,90]),90)
    failed=False
    try:compose_expected_minutes(1.2,90,.5,10)
    except ValueError:failed=True
    assert failed


def test_minutes_inputs_do_not_use_actuals_or_target_roles():
    frame=pd.read_csv(ROOT/'analysis/results/reproducible-role-v1/all_feature_predictions.csv.gz',nrows=20)
    before=component_inputs(frame)
    frame['minutes']=90-frame.minutes;frame['y']=1-frame.y
    frame['actual_role_posthoc']='ST';frame['target_role_case_posthoc']='disagreement'
    frame['role_aware_p_start']=1-frame.role_aware_p_start
    assert before.equals(component_inputs(frame))


def test_minutes_saved_holdout_keeps_start_model_and_identity():
    frame=pd.read_csv(ROOT/'analysis/results/minutes-decomposition-v1/conditional_minutes_holdout_predictions.csv.gz',
       usecols=['gw','role_aware_p_start','full_decomposition_p_start','full_decomposition_xmins',
                'e_min_start','p_sub_not_start','e_min_sub'])
    assert len(frame)==13987 and set(frame.gw)==set(range(22,39))
    assert np.allclose(frame.role_aware_p_start,frame.full_decomposition_p_start,atol=1e-12)
    expected=compose_expected_minutes(frame.role_aware_p_start,frame.e_min_start,frame.p_sub_not_start,frame.e_min_sub)
    assert np.allclose(expected,frame.full_decomposition_xmins,atol=1e-9)

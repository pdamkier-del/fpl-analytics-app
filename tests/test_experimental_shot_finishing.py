import numpy as np
import pandas as pd
import pytest
from fpl_v1_1_model.experimental_shot_finishing import fit_shots


def sample():
    # Same chance quality, different observed conversion rates.
    return pd.DataFrame(dict(player_uuid=['a']*100+['b']*100,
                             xg=[.2]*200,goal=[1]*40+[0]*60+[1]*10+[0]*90,
                             known=pd.to_datetime(['2024-01-01T12:00:00Z']*200)))


def test_player_effect_learns_conversion_and_unknown_player_is_neutral():
    f=fit_shots(sample(),'2024-02-01T00:00:00Z',ridge=5.)
    p=f.predict([.2,.2,.2],['a','new','b'])
    assert 0 < p[2] < p[1] < p[0] < 1
    assert f.offsets.get('new',0.)==0.


def test_strong_prior_shrinks_player_difference():
    weak=fit_shots(sample(),'2024-02-01T00:00:00Z',ridge=1.)
    strong=fit_shots(sample(),'2024-02-01T00:00:00Z',ridge=80.)
    assert abs(strong.offsets['a']-strong.offsets['b']) < abs(weak.offsets['a']-weak.offsets['b'])


def test_future_and_missing_shots_are_rejected():
    with pytest.raises(ValueError):fit_shots(sample(),'2023-12-01T00:00:00Z',ridge=5.)
    bad=sample();bad.loc[0,'xg']=np.nan
    with pytest.raises(ValueError):fit_shots(bad,'2024-02-01T00:00:00Z',ridge=5.)


def test_postshot_outcome_predictors_are_unused():
    a=sample();b=a.copy()
    b['expectedGoalsOnTarget']=b.goal
    b['isOnTarget']=b.goal
    b['goalCrossedY']=b.goal*999
    first=fit_shots(a,'2024-02-01T00:00:00Z',ridge=5.)
    second=fit_shots(b,'2024-02-01T00:00:00Z',ridge=5.)
    np.testing.assert_array_equal(first.predict([.1,.4],['a','b']),second.predict([.1,.4],['a','b']))


def test_conversion_prediction_increases_with_chance_quality():
    f=fit_shots(sample(),'2024-02-01T00:00:00Z',ridge=5.)
    assert np.all(np.diff(f.predict([.01,.1,.5,.9],['a']*4)) > 0)
    with pytest.raises(ValueError):f.predict([1.1],['a'])

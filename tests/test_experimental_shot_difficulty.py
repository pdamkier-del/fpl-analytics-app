import numpy as np
import pandas as pd
import pytest
from fpl_v1_1_model.experimental_shot_finishing import fit_shots
from fpl_v1_1_model.experimental_shot_difficulty import DifficultyFit,fit_difficulty


def history():
    rows=[]
    for p,x,goals in [('a',.05,10),('a',.6,50),('b',.05,2),('b',.6,70)]:
        rows.extend(dict(player_uuid=p,xg=x,goal=int(i<goals),known=pd.Timestamp('2024-01-01',tz='UTC')) for i in range(100))
    return pd.DataFrame(rows)


def test_neutral_setting_reproduces_existing_fit():
    f=history();cut='2024-02-01T00:00:00Z'
    a=fit_shots(f,cut,ridge=5.)
    b=fit_difficulty(f,cut,ridge=5.)
    np.testing.assert_array_equal(a.predict([.05,.8],['a','b']),b.predict([.05,.8],['a','b']))


def test_individual_shape_changes_relative_hard_vs_easy_conversion():
    f=DifficultyFit(0.,1.,{}, {'hard':.5})
    hard=f.predict([.05,.8],['hard','hard'])
    assert hard[0]>.05 and hard[1]<.8
    assert np.all(np.diff(f.predict(np.linspace(.001,.999,100),['hard']*100))>0)


def test_shape_is_regularized_and_predicted_probabilities_are_valid():
    f=history();cut='2024-02-01T00:00:00Z'
    weak=fit_difficulty(f,cut,ridge=5.,shape_ridge=5.)
    strong=fit_difficulty(f,cut,ridge=5.,shape_ridge=1000.)
    assert sum(abs(v)for v in strong.shapes.values()) < sum(abs(v)for v in weak.shapes.values())
    assert abs(weak.shapes['a'])>1e-3
    p=weak.predict([.05,.8],['new','a'])
    assert np.all((p>0)&(p<1))


def test_future_data_and_invalid_weighting_are_rejected():
    with pytest.raises(ValueError):fit_difficulty(history(),'2023-01-01T00:00:00Z')
    with pytest.raises(ValueError):fit_difficulty(history(),'2024-02-01T00:00:00Z',power=-1.)

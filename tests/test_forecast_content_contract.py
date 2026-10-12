import pandas as pd
import pytest
from fpl_v1_1_model.forecast_snapshot import seal_forecast,require_snapshot
from fpl_v1_1_model.forecast_horizon_contract import require_horizon,horizon_report

def test_same_cutoff_changed_points_rejected():
    old=seal_forecast({'data_asof':'fixed','players':[{'xp':5.}]})
    new=seal_forecast({'data_asof':'fixed','players':[{'xp':6.}]})
    assert old['forecast_sha256']!=new['forecast_sha256']
    with pytest.raises(ValueError):require_snapshot(new,old['forecast_sha256'])
    with pytest.raises(ValueError):require_snapshot({**old,'players':[{'xp':6.}]})
    assert require_snapshot(old)==old['forecast_sha256']

def test_order_does_not_change_identity():
    a=seal_forecast({'a':1,'b':{'c':2,'d':3}})
    b=seal_forecast({'b':{'d':3,'c':2},'a':1})
    assert a['forecast_sha256']==b['forecast_sha256']

def test_single_week_benchmark_is_not_six_week():
    frame=pd.DataFrame({'decision_gw':range(6,39),'gw':range(6,39)})
    report=horizon_report(frame)
    assert report['actual_origin_target_pairs']==33
    assert report['required_origin_target_pairs']==183
    with pytest.raises(ValueError,match='missing'):require_horizon(frame,6)
    assert require_horizon(frame,38)==[38]

def test_gap_is_rejected_not_weight_compressed():
    frame=pd.DataFrame({'decision_gw':[7]*5,'gw':[7,9,10,11,12]})
    with pytest.raises(ValueError,match='8'):require_horizon(frame,7)

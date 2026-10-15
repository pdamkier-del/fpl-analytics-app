from datetime import datetime,timezone,timedelta
import sys
from pathlib import Path
import pandas as pd
import pytest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
from evaluate_individual_dc import score_history
T=datetime(2025,10,15,tzinfo=timezone.utc)
def tables():
    history=pd.DataFrame([
        {"player_uuid":"a","known_at":T-timedelta(days=8),"minutes":90,"dc_count":8},
        {"player_uuid":"a","known_at":T+timedelta(days=1),"minutes":90,"dc_count":100},
    ])
    forecasts=pd.DataFrame([{"player_uuid":"a","cutoff":T,
       "position":"DEF","role_rate90":5.,"expected_minutes":90,
       "actual_dc_count":9}])
    return history,forecasts
def test_future_dc_cannot_enter_player_propensity():
    h,f=tables()
    p,s=score_history(h,f)
    q,_=score_history(h.iloc[:1],f)
    assert p.expected_dc_count.iloc[0]==q.expected_dc_count.iloc[0]
    assert p.history_rows.iloc[0]==1
    assert s["requires_original_dc_baseline_for_comparative_result"]
def test_missing_action_is_not_zero():
    h,f=tables()
    h.loc[0,"dc_count"]=float("nan")
    with pytest.raises(ValueError):
        score_history(h,f)
def test_no_automatic_actual_label_fill():
    h,f=tables()
    f.loc[0,"actual_dc_count"]=float("nan")
    with pytest.raises(ValueError):
        score_history(h,f)
def test_duplicate_forecast_is_rejected():
    h,f=tables()
    with pytest.raises(ValueError):
        score_history(h,pd.concat([f,f],ignore_index=True))
def test_distinct_players_get_distinct_profiles():
    h,f=tables()
    h=pd.concat([h,pd.DataFrame([{"player_uuid":"b","known_at":T-timedelta(days=8),"minutes":90,"dc_count":2}])])
    f=pd.concat([f,pd.DataFrame([{"player_uuid":"b","cutoff":T,"position":"DEF","role_rate90":5.,
                 "expected_minutes":90,"actual_dc_count":2}])])
    p,_=score_history(h,f)
    assert p.set_index("player_uuid").loc["a","expected_dc_count"]>p.set_index("player_uuid").loc["b","expected_dc_count"]

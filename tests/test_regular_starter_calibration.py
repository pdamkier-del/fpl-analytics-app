import pandas as pd
from audit_regular_starter_calibration import cohort

def test_future_prior_gw_outcome_is_not_available_history():
    rows=[]
    for i in range(6):rows.append(dict(player_uuid='fixture',cutoff=f'2025-01-{i+1:02d}T09:00:00Z',outcome_known_at=f'2025-01-{i+1:02d}T17:00:00Z',y=1,new_p_start=.8,new_xmins=70.,minutes=90.,gw=i+1,pos='FWD'))
    rows.append(dict(player_uuid='fixture',cutoff='2025-01-07T09:00:00Z',outcome_known_at='2025-01-07T17:00:00Z',y=0,new_p_start=.8,new_xmins=70.,minutes=0.,gw=7,pos='FWD'))
    full,_=cohort(pd.DataFrame(rows));assert len(full)==1 and full.iloc[0].started==0
    rows[5]['outcome_known_at']='2025-01-08T17:00:00Z'
    unavailable,_=cohort(pd.DataFrame(rows));assert unavailable.empty

def test_already_known_target_not_used_as_backtest():
    m=pd.DataFrame([dict(player_uuid='fixture',cutoff='2025-01-02T09:00:00Z',outcome_known_at='2025-01-01T17:00:00Z',y=1,new_p_start=.8,new_xmins=70.,minutes=90.,gw=1,pos='FWD')])
    rows,excluded=cohort(m);assert rows.empty and excluded==1

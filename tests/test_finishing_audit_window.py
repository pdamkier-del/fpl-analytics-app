import pandas as pd
import pytest
from audit_finishing_walkforward import validate_history

def fixture():
    h=pd.DataFrame({'fixture_uuid':['test-'+str(i) for i in range(20)],'gw':[7]*20,'available_at':['2026-10-17T18:00:00Z']*20})
    return h,{'gws':[8,9,10,11,12,13],'data_asof':'2026-10-18T06:00:00Z'}

def test_new_completed_GW_is_not_rejected_by_obsolete_GW7_guard():
    h,f=fixture();assert validate_history(h,f)

@pytest.mark.parametrize('case',['future_gw','future_availability','unknown_availability','naive_cutoff','missing_GW','coverage'])
def test_audit_still_rejects_unverifiable_or_future_observations(case):
    h,f=fixture()
    if case=='future_gw':h.loc[0,'gw']=8
    elif case=='future_availability':h.loc[0,'available_at']='2026-10-19T00:00:00Z'
    elif case=='unknown_availability':h.loc[0,'available_at']=None
    elif case=='naive_cutoff':f['data_asof']='2026-10-18T06:00:00'
    elif case=='missing_GW':f['gws']=[]
    else:h=h.iloc[:19]
    with pytest.raises(ValueError):validate_history(h,f)

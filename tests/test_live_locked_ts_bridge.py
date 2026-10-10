import importlib.util
from pathlib import Path
import pandas as pd
import pytest
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('live_ts',ROOT/'scripts/run_live_locked_ts.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
def state():
    pos=['GKP']*2+['DEF']*5+['MID']*5+['FWD']*3
    meta=pd.DataFrame([{'id':i+1,'position':p,'team':i//3+1,'price_tenths':50} for i,p in enumerate(pos)])
    raw={'season':'2026-27','gw':6,'source':'official manager export','observed_at':'2026-10-10T07:00:00Z','bank_tenths':15,'free_transfers':5,
         'squad':[{'id':i+1,'purchase_price_tenths':48} for i in range(15)],'chips_used':{k:[] for k in m.CHIPS}}
    return raw,meta

def test_actual_purchase_prices_are_preserved():
    r,meta=state();s=m.parse_state(r,meta,6,'2026-10-10T07:35:11Z')
    assert s.bank==15 and s.free_transfers==5 and s.squad[1].purchase_price==48

def test_missing_purchase_prices_are_not_guessed():
    r,meta=state();del r['squad'][0]['purchase_price_tenths']
    with pytest.raises(ValueError,match='purchase price'):m.parse_state(r,meta,6,'2026-10-10T07:35:11Z')

def test_post_cutoff_manager_state_rejected():
    r,meta=state();r['observed_at']='2026-10-10T08:00:00Z'
    with pytest.raises(ValueError,match='after forecast cutoff'):m.parse_state(r,meta,6,'2026-10-10T07:35:11Z')

def test_frozen_ts_parameters_reused():
    c=m.cfg();assert c.weights==(1.,.6,.36,.216,.1296,.07776)
    assert c.hit_uncertainty_buffer==1 and c.beam_width==20 and c.max_transfers_per_week==5

def test_diagnostic_bridge_runs_original_planner_without_promoting_or_mutating_manager():
    # Explicit synthetic REGRESSION fixture, never a fabricated user squad.
    import copy
    raw,meta=state();before=copy.deepcopy(raw)
    position={'GKP':1,'DEF':2,'MID':3,'FWD':4}
    payload={'season':'2026-27','gws':list(range(6,12)),'data_asof':'2026-10-10T07:35:11Z',
        'locked_model_active':False,'blockers':['Regression-only synthetic input'],
        'players':[{'id':int(r.id),'name':str(r.id),'team_id':int(r.team),'position':position[r.position],
            'price_tenths':int(r.price_tenths),
            'weeks':[{'gw':g,'xpts':4.,'p_play':1.,'fixtures':[{}]} for g in range(6,12)]} for r in meta.itertuples()]}
    result=m.run(payload,raw,include_chips=True)
    assert raw==before
    assert result['locked_model_active'] is False and result['ts_status']=='diagnostic'
    assert result['plan']['weights']==(1.,.6,.36,.216,.1296,.07776)
    assert len(result['plan']['path'])==6 and len(result['lineup'])==15
    assert sum(r['role'] in ('C','VC','XI') for r in result['lineup'])==11
    assert result['chips_status']=='diagnostic_partial'
    assert result['chip_assessment']['tc_status']=='Not Available'
    assert result['chip_assessment']['future_chip_gw'] is None

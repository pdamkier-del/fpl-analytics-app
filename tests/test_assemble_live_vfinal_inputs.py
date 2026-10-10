import importlib.util
from pathlib import Path
import pandas as pd
import pytest
spec=importlib.util.spec_from_file_location('assemble',Path(__file__).resolve().parents[1]/'scripts/assemble_live_vfinal_inputs.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)

def test_missing_assist_probability_blocks_xp():
    b=pd.DataFrame([{'fixture_uuid':'f','player_uuid':'p','p_start':.9,'xmins':80,
                     'mm_q_sub':.2,'mm_sub_minutes':17,'start_minutes_mean':88,
                     'goal_rate90':.1,'assist_rate90':.2,'dc_alpha':.2,
                     'p_yellow':.1,'p_red':.01,'cutoff':'2026-10-10T10:00:00Z',
                     'target_gw':6,'pos':'MID','team_id':1,'lambda_saves':0}])
    p=pd.DataFrame([{'fixture_uuid':'f','player_uuid':'p'}])
    with pytest.raises(ValueError,match='assist_probability_per_goal'):
        m.assemble(b,p,p)

def test_rejects_missing_penalty_player():
    b=pd.DataFrame([{'fixture_uuid':'f','player_uuid':'p','p_start':.9,'xmins':80,
                     'mm_q_sub':.2,'mm_sub_minutes':17,'start_minutes_mean':88,
                     'assist_probability_per_goal':.7,'goal_rate90':.1,'assist_rate90':.2,
                     'dc_alpha':.2,'p_yellow':.1,'p_red':.01,'cutoff':'2026-10-10T10:00:00Z',
                     'target_gw':6,'pos':'MID','team_id':1,'lambda_saves':0}])
    p=pd.DataFrame([{'fixture_uuid':'f','player_uuid':'other'}])
    with pytest.raises(ValueError,match='player-fixture identities'):
        m.assemble(b,p,p)

def test_frozen_goal_assist_normalizer_receives_numeric_rates(monkeypatch):
    import numpy as np
    seen=[]
    def record(frame,rates,assist=False):
        assert isinstance(rates,np.ndarray)
        assert rates.dtype.kind == 'f'
        seen.append((assist,rates.tolist()))
        return np.ones(len(frame),dtype=float)
    monkeypatch.setattr(m,'normalized_mu',record)
    monkeypatch.setattr(m,'validate',lambda frame:None)
    base=pd.DataFrame([{'fixture_uuid':'f','player_uuid':'p','p_start':.9,'xmins':80.,
      'mm_q_sub':.2,'mm_sub_minutes':17.,'start_minutes_mean':88.,
      'assist_probability_per_goal':.7,'goal_rate90':.12,'assist_rate90':.24,
      'dc_alpha':.2,'p_yellow':.1,'p_red':.01,'cutoff':'2026-10-10T10:00:00Z',
      'target_gw':6,'pos':'MID','team_id':1,'lambda_saves':0}])
    pen=pd.DataFrame([{'fixture_uuid':'f','player_uuid':'p','lambda_pen':.1,
      'pen_weight':1.,'pen_conversion':.8,'team_pen_conversion':.8}])
    bps=pd.DataFrame([{'fixture_uuid':'f','player_uuid':'p','bg_mean_rate90':2.,'bg_sd90':1.}])
    m.assemble(base,pen,bps)
    assert seen==[(False,[.12]),(True,[.24])]

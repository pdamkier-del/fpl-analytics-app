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

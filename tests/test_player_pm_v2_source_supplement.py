import numpy as np
import pandas as pd
import pytest
from fpl_v1_1_model import joint_simulator as sim
from fpl_v1_1_model.experimental_player_pm import shadow_player_intensity
from audit_player_pm_v2_profiles import action_profile
from test_experimental_player_pm import fixture,spec,history


def test_neutral_anchored_case_preserves_original_draws(monkeypatch):
    x=fixture();s=spec(x,1.)
    monkeypatch.setattr(sim,'_sample_minutes',lambda rng,p:(90,0,90))
    before=sim.simulate_many(x,n=50,seed=91)
    with shadow_player_intensity(s):after=sim.simulate_many(x,n=50,seed=91)
    assert before==after


def test_verified_action_profile_excludes_future_and_retains_missing():
    fields=['keypass_rate90','dribble_rate90','sot_rate90','cbi_rate90','recovery_rate90','tackle_rate90','cross_rate90','foulwon_rate90']
    rows=[dict(player_uuid='a',available_at='2024-01-01T10:00Z',minutes_played=90,**{k:1. for k in fields}),dict(player_uuid='a',available_at='2024-03-01T10:00Z',minutes_played=90,**{k:1000. for k in fields})]
    f=pd.DataFrame(rows);f['tackle_rate90']=np.nan;identity=pd.DataFrame([dict(player_uuid='a',pos='MID')]);cut=pd.Timestamp('2024-02-01T10:00Z')
    p=action_profile(f,identity,'a',cut)
    assert p['keypass_rate90']['mean']==pytest.approx(1.) and p['tackle_rate90'] is None
    assert not p['keypass_rate90']['used_in_candidate']


def test_season_local_numeric_team_ids_do_not_invent_summer_transfer():
    from fpl_v1_1_model.experimental_player_pm import ProfileFit
    from dataclasses import replace
    h=history();p=replace(fixture().players[0],team='9')
    result=ProfileFit(h,pd.Timestamp('2024-01-04T10:00Z'),'next-season').profile(p)
    assert result['club_change'] is False

import json
from pathlib import Path

import pandas as pd
import pytest

from fpl_v1_1_model.deadline_components import player_components_at_deadline

ROOT=Path(__file__).resolve().parents[1]
P=ROOT/'analysis/results/joint-component-recovery-v1'
PARAMS=dict(attack=json.loads((P/'player_attack_fit.json').read_text()),
    dc=json.loads((P/'defcon_fit.json').read_text())['selected'],
    discipline=json.loads((P/'negative_events_fit.json').read_text())['recommended_for_joint_model'])
CUTOFF='2026-01-17T11:00:00Z'


def history():
    return pd.DataFrame([dict(season='2025-26',fixture_uuid='past',player_uuid='old',team_id=1,opponent_team_id=2,
        fpl_position='MID',minutes=90.,xg=.3,xa=.2,defcon_count=12.,yellow_cards=1.,fpl_red_cards=0.,
        kickoff_at='2026-01-10T15:00:00Z',available_at='2026-01-10T18:00:00Z')])


def roster():
    return pd.DataFrame([dict(fixture_uuid='target',player_uuid='new',team_id=1,
        opponent_team_id=2,pos='MID',expected_minutes=45.,evidence_at='2026-01-17T06:40:00Z')])


def run(h=None,r=None):
    return player_components_at_deadline(history() if h is None else h,roster() if r is None else r,CUTOFF,**PARAMS)


def test_postdeadline_outcomes_cannot_change_any_component():
    future=history();future.fixture_uuid='target';future.kickoff_at='2026-01-17T15:00:00Z';future.available_at='2026-01-17T18:00:00Z'
    future[['xg','xa','defcon_count','yellow_cards','fpl_red_cards']]=1e8
    pd.testing.assert_frame_equal(run(),run(pd.concat([history(),future],ignore_index=True)))


def test_first_entry_uses_observed_position_prior_without_target_history():
    x=run().iloc[0]
    assert x.cold_start and x.history_rows==0
    assert x.goal_rate90==pytest.approx(.3)
    assert x.assist_rate90==pytest.approx(.2)
    assert x.mu_dc>0 and x.p_yellow>0
    changed=history();changed.xg=.6
    assert run(changed).goal_rate90.iloc[0]==pytest.approx(.6)


def test_unverified_roster_is_rejected_instead_of_getting_a_forecast():
    r=roster();r.evidence_at=None
    with pytest.raises(ValueError,match='roster evidence'):run(r=r)


def test_a_completed_target_cannot_be_smuggled_into_history():
    h=history();h.fixture_uuid='target'
    with pytest.raises(ValueError,match='Target fixture'):run(h)


def test_dgw_targets_share_the_same_deadline_rates():
    r=roster();second=r.copy();second.fixture_uuid='target2';second.expected_minutes=70
    x=run(r=pd.concat([r,second],ignore_index=True))
    assert x.goal_rate90.nunique()==1 and x.dc_rate90.nunique()==1
    assert x.mu_dc.iloc[1]/x.mu_dc.iloc[0]==pytest.approx(70/45)


def test_missing_past_observation_is_not_imputed_to_zero():
    h=history();h.xa=None
    with pytest.raises(ValueError,match='historical events'):run(h)


def test_previous_season_events_cannot_supply_the_current_season_prior():
    old=history();old.season='2024-25';old.fixture_uuid='previous';old.xg=1e8
    pd.testing.assert_frame_equal(run(),run(pd.concat([old,history()],ignore_index=True)))

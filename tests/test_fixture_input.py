"""Boundary tests: actual input values survive; ambiguous joins never predict."""
from dataclasses import replace
from pathlib import Path
import numpy as np
import pandas as pd
import pytest
from fpl_v1_1_model.fixture_input import FixtureTables,split_fixture_frame,join_fixture_tables,prepare_fixture

ROOT=Path(__file__).resolve().parents[1]


@pytest.fixture
def frame():
    # Real archived current inputs are not required to run unit tests.
    from fpl_v1_1_model.paired_joint import read_frozen_table
    f=read_frozen_table(ROOT/'analysis/results/joint-paired-inputs-v1','inputs')
    f=f[f.fixture_uuid.eq(f.fixture_uuid.iloc[0])].copy()
    f['lambda_pen']=.1;f['team_pen_conversion']=.8
    f['pen_weight']=.2;f['pen_conversion']=.8
    f['bg_mean_rate90']=5.;f['bg_sd90']=2.
    return f


def test_roundtrip_preserves_every_source_feature_and_player_order(frame):
    frame['extra_role_evidence']=np.arange(len(frame))
    original=frame.copy(deep=True);tables=split_fixture_frame(frame);joined=join_fixture_tables(tables)
    pd.testing.assert_frame_equal(original.reset_index(drop=True),joined[frame.columns],check_exact=True)
    pd.testing.assert_frame_equal(frame,original,check_exact=True)
    assert len(tables.teams)==2 and len(tables.match)==1


def test_only_supported_math_inputs_reach_the_existing_adapter(frame):
    p=prepare_fixture(frame,p_keeper_save_given_miss=.5,bps_rules='2026-27')
    assert p.model_input.bps_rules=='2026-27'
    assert p.model_input.p_penalty_save_given_miss==.5
    assert len(p.model_input.players)==len(frame)
    assert not p.own_goal_input_present
    assert p.fixture_uuid==str(frame.fixture_uuid.iloc[0])


def test_conflicting_team_values_are_not_taken_from_first_player(frame):
    frame.loc[frame.index[0],'lambda_pen']=.2
    with pytest.raises(ValueError,match='team context'):prepare_fixture(frame,p_keeper_save_given_miss=.5)


def test_mismatched_source_cutoff_rejected(frame):
    t=split_fixture_frame(frame);teams=t.teams.copy();teams['cutoff']='2030-01-01T12:00:00Z'
    with pytest.raises(ValueError,match='cutoff mismatch'):join_fixture_tables(replace(t,teams=teams))


def test_other_fixture_or_missing_team_rejected(frame):
    t=split_fixture_frame(frame);match=t.match.copy();match['fixture_uuid']='other'
    with pytest.raises(ValueError,match='identity mismatch'):join_fixture_tables(replace(t,match=match))
    with pytest.raises(ValueError,match='exact match clubs'):join_fixture_tables(replace(t,teams=t.teams.iloc[:1]))


def test_duplicate_players_and_unknown_match_values_rejected(frame):
    t=split_fixture_frame(frame)
    with pytest.raises(ValueError,match='player identity'):join_fixture_tables(replace(t,players=pd.concat([t.players,t.players.iloc[:1]])))
    match=t.match.copy();match['lambda_home_goals']=np.nan
    with pytest.raises(ValueError,match='Unknown/nonfinite'):join_fixture_tables(replace(t,match=match))


def test_team_feature_cannot_have_two_owners(frame):
    t=split_fixture_frame(frame);players=t.players.assign(lambda_pen=.2)
    with pytest.raises(ValueError,match='ownership'):join_fixture_tables(replace(t,players=players))


def test_naive_time_is_not_silently_assumed_utc(frame):
    t=split_fixture_frame(frame);players=t.players.assign(cutoff='2026-10-25T12:00:00')
    with pytest.raises(ValueError,match='timezone'):join_fixture_tables(replace(t,players=players))


def test_missing_player_rates_do_not_silently_become_zero(frame):
    frame.loc[frame.index[0],'goal_mu']=np.nan
    with pytest.raises(ValueError,match='Unknown/nonfinite player'):prepare_fixture(frame,p_keeper_save_given_miss=.5)


def test_unconsumed_context_and_target_labels_cannot_change_math(frame):
    from dataclasses import asdict
    reference=prepare_fixture(frame,p_keeper_save_given_miss=.5).model_input
    extra=frame.assign(actual_start=1,actual_minutes=90,observed_goal_outcome=9)
    prepared=prepare_fixture(extra,p_keeper_save_given_miss=.5)
    assert asdict(reference)==asdict(prepared.model_input)
    assert 'observed_goal_outcome'in prepared.tables.players

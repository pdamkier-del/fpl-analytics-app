"""Parity and failure-mode tests for the canonical fixture adapter."""
from dataclasses import asdict
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from fpl_v1_1_model.canonical_fixture_input import (
    expand_canonical_fixture, prepare_canonical_fixture, LEGACY_ALIASES,
)
from fpl_v1_1_model.fixture_input import prepare_fixture
from fpl_v1_1_model.paired_joint import read_frozen_table

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def legacy_frame():
    frame = read_frozen_table(
        ROOT / "analysis/results/joint-paired-inputs-v1", "inputs"
    )
    frame = frame[frame.fixture_uuid.eq(frame.fixture_uuid.iloc[0])].copy()
    frame["lambda_pen"] = .1
    frame["team_pen_conversion"] = .8
    frame["pen_weight"] = .2
    frame["pen_conversion"] = .8
    frame["bg_mean_rate90"] = 5.
    frame["bg_sd90"] = 2.
    return frame


def canonicalize(frame):
    result = frame.copy(deep=True)
    # Existing historical control minute fields define the canonical owner.
    result["p_start"] = result["control_p_start"]
    result["xmins"] = result["control_xmins"]
    return result.drop(columns=list(LEGACY_ALIASES))


def test_canonical_reconstructs_existing_sim_input(legacy_frame):
    canonical = canonicalize(legacy_frame)
    expanded = expand_canonical_fixture(canonical)
    for legacy, source in LEGACY_ALIASES.items():
        np.testing.assert_array_equal(expanded[legacy], expanded[source])
    reference = prepare_fixture(legacy_frame, p_keeper_save_given_miss=.5)
    candidate = prepare_canonical_fixture(canonical, p_keeper_save_given_miss=.5)
    assert asdict(candidate.model_input) == asdict(reference.model_input)


def test_conflicting_legacy_variant_fails_closed(legacy_frame):
    canonical = canonicalize(legacy_frame)
    canonical["v4_workload_start_p_start"] = canonical.p_start + .01
    with pytest.raises(ValueError, match="Conflicting legacy"):
        expand_canonical_fixture(canonical)


def test_minutes_identity_fails_closed(legacy_frame):
    canonical = canonicalize(legacy_frame)
    canonical["xmins"] = 0.
    with pytest.raises(ValueError, match="identity mismatch"):
        expand_canonical_fixture(canonical)


def test_missing_source_fails_closed(legacy_frame):
    canonical = canonicalize(legacy_frame).drop(columns=["bg_sd90"])
    with pytest.raises(ValueError, match="Missing canonical"):
        expand_canonical_fixture(canonical)


def test_does_not_mutate_input(legacy_frame):
    canonical = canonicalize(legacy_frame)
    before = canonical.copy(deep=True)
    expand_canonical_fixture(canonical)
    pd.testing.assert_frame_equal(canonical, before)

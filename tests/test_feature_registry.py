"""Static contract tests; no simulation parameter changes."""
from fpl_v1_1_model.feature_registry import FEATURES, feature_catalogue, owner_map
from fpl_v1_1_model.fixture_input import (
    MATCH_FIELDS, TEAM_FIELDS, PLAYER_NUMBERS,
)

def test_feature_names_are_unique_and_have_provenance():
    owners = owner_map()
    assert len(owners) == len(FEATURES)
    for item in feature_catalogue():
        assert item["name"] and item["source"] and item["consumed_by"]
        assert item["scope"] in {"fixture","team","player","role","derived"}

def test_fixture_and_team_fields_have_single_owner():
    owners = owner_map()
    for key in MATCH_FIELDS:
        assert owners[key] == "fixture"
    for key in TEAM_FIELDS:
        assert owners[key] == "team"

def test_core_frozen_player_features_are_accounted_for():
    owners = owner_map()
    for key in ("goal_mu","assist_mu","mu_dc","dc_alpha",
                "p_yellow","p_red","pen_weight","pen_conversion",
                "bg_mean_rate90","bg_sd90","lambda_saves"):
        assert owners[key] == "derived"
    for key in ("start_minutes_mean","cameo_minutes_mean",
                "p_cameo_given_bench"):
        assert owners[key] == "player"
    # Legacy aliases are not canonical source fields.
    assert not any(key.startswith(("control_","v4_")) for key in owners)

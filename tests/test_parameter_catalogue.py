"""Keep human-readable catalogue honest and read-only."""
from fpl_v1_1_model.parameter_catalogue import (
    CATALOGUE, grouped_catalogue, feature_and_parameter_catalogue,
)

def test_catalogue_has_unique_names_and_provenance():
    assert len({p.name for p in CATALOGUE}) == len(CATALOGUE)
    assert all(p.defined_in and p.module and p.kind and p.unit for p in CATALOGUE)

def test_runtime_values_are_not_mistaken_for_locked_constants():
    assert all(p.value is None for p in CATALOGUE if p.kind == "runtime feature")

def test_catalogue_exposes_grouped_and_feature_views():
    assert sum(len(v) for v in grouped_catalogue().values()) == len(CATALOGUE)
    combined = feature_and_parameter_catalogue()
    assert combined["features"] and combined["parameters"]

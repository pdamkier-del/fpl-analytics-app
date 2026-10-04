import pytest
from fpl_v1_1_model.defcon import threshold,dc_points_from_count,threshold_probability,expected_points


def test_2026_27_dc_thresholds():
    assert threshold('DEF')==10
    assert threshold('MID')==12
    assert threshold('FWD')==12
    assert threshold('GK') is None


def test_dc_points_are_capped_at_two():
    assert dc_points_from_count('DEF',9)==0
    assert dc_points_from_count('DEF',10)==2
    assert dc_points_from_count('DEF',25)==2


def test_nb_threshold_probability_is_valid():
    p=threshold_probability(8,'DEF',.15)
    assert 0 < p < 1
    assert expected_points(8,'DEF',.15)==pytest.approx(2*p)

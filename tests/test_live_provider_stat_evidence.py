import sys
from pathlib import Path
import pytest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from live_provider_stat_evidence import passing_percentage


def test_raw_fraction_is_percentage_not_completed_pass_count():
    assert passing_percentage({'type':'fractionWithPercentage','value':4,'total':5})==80.


def test_no_attempts_or_missing_denominator_remains_unknown():
    assert passing_percentage({'type':'fractionWithPercentage','value':0,'total':0}) is None
    assert passing_percentage({'type':'fractionWithPercentage','value':4}) is None
    assert passing_percentage({'type':'integer','value':4}) is None


def test_inconsistent_fraction_cannot_be_certified():
    with pytest.raises(ValueError):passing_percentage({'type':'fractionWithPercentage','value':6,'total':5})

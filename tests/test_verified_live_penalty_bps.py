import sys
from pathlib import Path
import pytest
sys.path[:0]=[str(Path(__file__).resolve().parents[1]/'src'),str(Path(__file__).resolve().parents[1]/'scripts')]
from build_verified_live_penalty_bps import verified_sparse_zeros


def test_zero_requires_conservation_of_observed_team_total():
    assert verified_sparse_zeros([2,None,3,None],5)==[2.,0.,3.,0.]
    assert verified_sparse_zeros([2,None,3],6) is None
    assert verified_sparse_zeros([2,None,3],None) is None


def test_missing_team_total_never_invents_zero():
    assert verified_sparse_zeros([None,None],None) is None
    assert verified_sparse_zeros([None,None],0)==[0.,0.]


def test_invalid_player_counts_are_rejected():
    with pytest.raises(ValueError):verified_sparse_zeros([float('nan'),None],2)
    with pytest.raises(ValueError):verified_sparse_zeros([-1,None],0)

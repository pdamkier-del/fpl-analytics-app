import copy,sys
from pathlib import Path
import pytest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from merge_individual_mm_captures import merge_records
BASE=[dict(origin=6,fixture='a',input={'x':1},reference={'p':1.2},seed=1),dict(origin=7,fixture='b',input={'x':2},reference={'p':1.3},seed=2)]
def test_fixture_identity_controls_order_and_seed():
 assert merge_records(BASE,[[BASE[1]],[BASE[0]]])==BASE
@pytest.mark.parametrize('shards',[[[BASE[0]]],[[BASE[0]],[BASE[0],BASE[1]]]])
def test_incomplete_or_overlapping_shards_are_rejected(shards):
 with pytest.raises(ValueError):merge_records(BASE,shards)
def test_reference_drift_is_not_hidden_by_merge():
 bad=copy.deepcopy(BASE);bad[0]['seed']=9
 with pytest.raises(ValueError):merge_records(BASE,[bad])

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


def test_manifest_ignores_unselected_revision_and_rejects_tampering(tmp_path):
    import hashlib,json
    from live_provider_stat_evidence import manifest_details
    rel='data/fotmob/details/123.json';path=tmp_path/rel;path.parent.mkdir(parents=True)
    path.write_text(json.dumps({'general':{'matchId':123}}))
    source={'path':rel,'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'observed_at':'2026-10-10T12:00:00Z'}
    manifest={'observed_at':'2026-10-10T13:00:00Z','sources':[source]}
    assert list(manifest_details(tmp_path,manifest))==['123']
    path.write_text('{}')
    with pytest.raises(ValueError,match='checksum'):manifest_details(tmp_path,manifest)

from scripts.verify_pages_publication import identity,verify
import pytest

def test_pages_cannot_replace_newer_forecast_or_changed_checksums():
    current=dict(model='original_locked_vFinal_diagnostic',locked_model_active=False,data_asof='new',gws=[7,8],checksums={'input':'a'})
    snapshot=identity(current);verify(snapshot,current)
    with pytest.raises(ValueError,match='older Pages'):verify({**snapshot,'data_asof':'old'},current)
    with pytest.raises(ValueError,match='older Pages'):verify({**snapshot,'checksums':{'input':'b'}},current)
    with pytest.raises(ValueError,match='contract'):identity({**current,'locked_model_active':True})

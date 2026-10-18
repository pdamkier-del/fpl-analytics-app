from scripts.verify_pages_publication import identity,verify,preview_identity
import pytest

def test_pages_cannot_replace_newer_forecast_or_changed_checksums():
    current=dict(model='original_locked_vFinal_diagnostic',locked_model_active=False,data_asof='new',gws=[7,8],checksums={'input':'a'})
    snapshot=identity(current);verify(snapshot,current)
    with pytest.raises(ValueError,match='older Pages'):verify({**snapshot,'data_asof':'old'},current)
    with pytest.raises(ValueError,match='older Pages'):verify({**snapshot,'checksums':{'input':'b'}},current)
    with pytest.raises(ValueError,match='contract'):identity({**current,'locked_model_active':True})

def test_same_production_forecast_cannot_roll_back_a_newer_MM_preview():
    current=dict(model='original_locked_vFinal_diagnostic',locked_model_active=False,data_asof='same',gws=[8],checksums={'input':'a'})
    before=preview_identity({'forecast_sha256':'old'},{'preview_source_commit':'code-a'})
    after=preview_identity({'forecast_sha256':'new'},{'preview_source_commit':'code-a'})
    snapshot={**identity(current),'mm_preview':before}
    verify(snapshot,current,before)
    with pytest.raises(ValueError,match='MM preview'):verify(snapshot,current,after)
    with pytest.raises(ValueError,match='MM preview'):verify(identity(current),current,after)

def test_new_preview_UI_is_also_protected_when_forecast_is_unchanged():
    assert preview_identity({'forecast_sha256':'same'},{'preview_source_commit':'old'})!=preview_identity({'forecast_sha256':'same'},{'preview_source_commit':'new'})

def test_incomplete_preview_cannot_be_used_as_missing_preview():
    assert preview_identity(None,None) is None
    with pytest.raises(ValueError,match='Incomplete'):preview_identity({},None)
    with pytest.raises(ValueError,match='Incomplete'):preview_identity(None,{})

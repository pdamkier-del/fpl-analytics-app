import pytest
from capture_mm_prospective import capture


def test_source_capture_is_not_misreported_as_B_forecast():
    b=dict(events=[dict(id=7,is_next=True,deadline_time='2026-10-20T10:00:00Z')],elements=[dict(id=1)])
    r=capture(b,[],observed_at='2026-10-19T10:00:00+00:00',workflow='test')
    assert r['forecasts_registered']==0 and r['scope']=='source_capture_not_forecast'
    assert r['status']=='BLOCKED_CURRENT_B_FEATURES' and not r['locked_model_active']
    with pytest.raises(ValueError,match='after official deadline'):
        capture(b,[],observed_at='2026-10-20T10:00:00+00:00',workflow='test')

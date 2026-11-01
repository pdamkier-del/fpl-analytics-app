import json
import pytest
from fpl_v1_1_model.forecast_snapshot import seal_forecast
from precision_audit import prospective

def fixture(monkeypatch):
    monkeypatch.setattr(prospective,'validate_forecast',lambda f:None)
    f=seal_forecast(dict(scope='prospective_preview',data_asof='2026-11-01T06:00:00+00:00',origin_deadline='2026-11-07T12:00:00Z',gws=[10]))
    return f,dict(forecast_sha256=f['forecast_sha256'],model_source='a'*40,publication_run='1')

def test_immutable_record_and_duplicate_do_not_rewrite_acquisition(tmp_path,monkeypatch):
    f,m=fixture(monkeypatch);a=prospective.append(tmp_path,f,m,'2026-11-01T07:00:00+00:00');b=prospective.append(tmp_path,f,m,'2026-11-02T07:00:00+00:00')
    assert a==b and len(prospective.verify(tmp_path))==1
    path=tmp_path/a[0]['file'];path.write_bytes(b'corrupt')
    with pytest.raises(Exception):prospective.verify(tmp_path)

def test_postdeadline_and_oracle_forecasts_are_never_admitted(tmp_path,monkeypatch):
    f,m=fixture(monkeypatch)
    with pytest.raises(ValueError,match='clock'):prospective.append(tmp_path,f,m,'2026-11-08T07:00:00+00:00')
    f=seal_forecast({**f,'oracle':True});m['forecast_sha256']=f['forecast_sha256']
    with pytest.raises(ValueError,match='Oracle'):prospective.append(tmp_path,f,m,'2026-11-01T07:00:00+00:00')

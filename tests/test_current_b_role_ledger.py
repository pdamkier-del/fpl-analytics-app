import gzip,hashlib
import pandas as pd
import pytest
from restore_current_b_role_ledger import validate,ALLOWED

def fixture():
    row=dict.fromkeys(ALLOWED,0)
    row.update(season='2026-27',fixture_uuid='f',player_uuid='p',team_id=1,gw=8,cutoff='2026-10-17T16:00:00Z',pos='FWD',p=.8,p_role=.8,q=.2,s=85,upstream_s=85,c=15,x=68.6,news_eligible=True,news_state='AVAILABLE',news_chance=100,news_medical_out=False,news_effective_at='2026-10-17T15:59:00Z')
    return pd.DataFrame([row])

def pack(f):
    b=gzip.compress(f.to_csv(index=False).encode(),mtime=0)
    return dict(model='B_locked_PM_preview',locked_model_active=False,role_ledger_file='role-ledger.csv.gz',role_ledger_sha256=hashlib.sha256(b).hexdigest(),data_asof='2026-10-17T16:00:00Z'),b

def test_source_only_role_memory_has_verified_bytes_and_clock():
    index,b=pack(fixture());assert len(validate(index,b))==1
    with pytest.raises(ValueError,match='checksum'):validate(index,b+b'changed')
    index,b=pack(fixture().assign(cutoff='2026-10-18T16:00:00Z'))
    with pytest.raises(ValueError,match='future'):validate(index,b)

def test_private_fields_and_invalid_probabilities_never_publish():
    for f in [fixture().assign(manager_id=123),fixture().assign(p=1.1),pd.concat([fixture(),fixture()])]:
        index,b=pack(f)
        with pytest.raises(ValueError):validate(index,b)

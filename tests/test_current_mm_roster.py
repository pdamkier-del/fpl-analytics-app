"""Official current MM skeleton: immutable source and cutoff safety."""
import copy, hashlib, json
import pytest
from build_current_mm_roster import build, canonical


def inputs():
    bootstrap=dict(
        events=[dict(id=7,is_next=True,deadline_time='2026-10-17T11:00:00Z')],
        teams=[dict(id=1),dict(id=2)],
        elements=[dict(id=1,team=1,element_type=1),
                  dict(id=2,team=1,element_type=3),
                  dict(id=3,team=2,element_type=2)])
    fixtures=[dict(id=71,event=7,started=False,team_h=1,team_a=2,
                   kickoff_time='2026-10-18T12:00:00Z')]
    receipt=dict(scope='source_capture_not_forecast',origin_gw=7,
        origin_deadline='2026-10-17T11:00:00Z',
        observed_at='2026-10-17T08:00:00Z',workflow='https://example.test/run',
        bootstrap_sha256=hashlib.sha256(canonical(bootstrap)).hexdigest(),
        fixtures_sha256=hashlib.sha256(canonical(fixtures)).hexdigest())
    return bootstrap,fixtures,receipt


def test_real_official_identity_fixture_skeleton_is_explicitly_not_model_ready():
    b,f,r=inputs()
    result=build(b,f,r,cutoff='2026-10-17T09:00:00Z')
    assert result['fixture_count']==1 and result['roster_rows']==3
    assert result['gws']==[7,8,9,10,11,12]
    assert result['model_ready'] is False
    assert {p['fpl_element'] for p in result['rows']}=={1,2,3}
    assert {p['fixture_uuid'] for p in result['rows']}=={'live-2026-27-fpl-71'}
    assert all(p['role_feature_status']=='NOT_AVAILABLE' for p in result['rows'])


def test_roster_rejects_tampering_and_future_source():
    b,f,r=inputs()
    bad=copy.deepcopy(b);bad['elements'][0]['team']=2
    with pytest.raises(ValueError,match='Bootstrap bytes'):
        build(bad,f,r,cutoff='2026-10-17T09:00:00Z')
    with pytest.raises(ValueError,match='source capture'):
        build(b,f,r,cutoff='2026-10-17T07:00:00Z')


def test_roster_rejects_started_match_even_when_signed():
    b,f,r=inputs()
    f[0]['started']=True
    r['fixtures_sha256']=hashlib.sha256(canonical(f)).hexdigest()
    with pytest.raises(ValueError,match='Started'):
        build(b,f,r,cutoff='2026-10-17T09:00:00Z')

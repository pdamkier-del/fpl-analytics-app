import pandas as pd
import pytest
from role_transition_evidence import build_evidence,available


def fixture():
    t=pd.DataFrame([dict(season='s',fixture_uuid='target',player_uuid=p,team_id=1,cutoff='2025-02-01T12:00Z',pos='MID',role=1.,news_eligible=True,news_effective_at='2025-01-31T12:00Z',news_state='AVAILABLE')for p in ['a','b']])
    obs=[];news=[]
    for i in range(9):
        for p in ['a','b']:
            started=int((p=='b')==(i<6));fx=str(i)
            obs.append(dict(season='s',fixture_uuid=fx,player_uuid=p,team_id=1,started=started,minutes=started*90,kickoff_at=f'2025-01-{i+1:02}T15:00Z',known_at=f'2025-01-{i+1:02}T19:00Z'))
            news.append(dict(season='s',fixture_uuid=fx,player_uuid=p,cutoff=f'2025-01-{i+1:02}T12:00Z',news_effective_at='2024-12-31T12:00Z',news_eligible=True,news_state='OUT'if p=='b'and i>=6 else 'AVAILABLE'))
    return t,pd.DataFrame(obs),pd.DataFrame(news)


def test_injury_opportunity_and_return_are_separate():
    t,o,n=fixture();r=build_evidence(t,o,n,['role']).set_index('player_uuid').loc['a']
    assert r.rival_uuid=='b' and r.transition_opportunity3==1 and r.transition_return_pressure==1
    assert r.transition_contested3==0 and r.transition_streak3==1
    assert r.confirmed_injury_opportunities3==3 and not r.availability_reason_inferred


def test_unknown_is_not_injury_or_rest():
    t,o,n=fixture();n.news_eligible=False;t.news_eligible=False
    r=build_evidence(t,o,n,['role']).set_index('player_uuid').loc['a']
    assert pd.isna(r.transition_opportunity3) and pd.isna(r.transition_return_pressure)
    assert r.confirmed_injury_opportunities3==0
    assert available(dict(news_eligible=float('nan'),news_effective_at=pd.NaT))is None


def test_future_and_former_club_do_not_change_features():
    t,o,n=fixture();expected=build_evidence(t,o,n,['role'])
    future=o.copy();future.fixture_uuid='future'+future.fixture_uuid;future.known_at='2025-03-01T12:00Z';future.kickoff_at='2025-03-01T10:00Z'
    former=o.copy();former.fixture_uuid='former'+former.fixture_uuid;former.team_id=2
    actual=build_evidence(t,pd.concat([o,future,former]),n,['role'])
    pd.testing.assert_frame_equal(expected,actual)


def test_co_starters_are_not_exclusive_rivals():
    t,o,n=fixture();o.started=1;o.minutes=90
    r=build_evidence(t,o,n,['role'])
    assert r.rival_uuid.isna().all()


def test_labels_duplicates_and_naive_clocks_rejected():
    t,o,n=fixture()
    with pytest.raises(ValueError,match='outcomes'):build_evidence(t.assign(y=1),o,n,['role'])
    with pytest.raises(ValueError,match='Duplicate'):build_evidence(t,pd.concat([o,o.iloc[:1]]),n,['role'])
    t.cutoff='2025-02-01'
    with pytest.raises(ValueError,match='Timezone'):build_evidence(t,o,n,['role'])


def test_double_gameweek_targets_are_separate():
    t,o,n=fixture();second=t.copy();second.fixture_uuid='target2'
    result=build_evidence(pd.concat([t,second]),o,n,['role'])
    assert len(result)==4 and result.groupby('fixture_uuid').size().eq(2).all()


def test_unknown_flag_and_future_news_not_trusted():
    assert available(dict(news_eligible=float('nan'),news_effective_at='2025-01-01T12:00Z',cutoff='2025-01-02T12:00Z',news_state='OUT'))is None
    with pytest.raises(ValueError,match='clock'):
        available(dict(news_eligible=True,news_effective_at='2025-01-03T12:00Z',cutoff='2025-01-02T12:00Z',news_state='OUT'))

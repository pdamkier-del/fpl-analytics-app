import pandas as pd
import numpy as np
import pytest
from competition_context import context_features,apply_physical_context


def rows():
    t=pd.DataFrame([dict(season='s',fixture_uuid='target',player_uuid='p',club='New',cutoff='2026-10-20T12:00:00Z')])
    e=pd.DataFrame([dict(season='s',match_id='cup',player_uuid='p',club='Old',competition='Champions League',kickoff='2026-10-18T20:00:00Z',known_at='2026-10-18T23:00:00Z',minutes=120.,started=True)])
    return t,e


def test_workload_follows_identity_but_role_stays_at_current_club():
    t,e=rows();f=context_features(t,e).iloc[0]
    assert f.context_minutes_7d==120 and f.context_nonpl_minutes_7d==120
    assert f.context_role_games==0 and np.isnan(f.context_last_started)
    assert not f.context_coverage_complete


def test_future_and_exact_cutoff_outcomes_cannot_change_context():
    t,e=rows();reference=context_features(t,e)
    future=e.copy();future['match_id']='later';future['kickoff']='2026-10-19T20:00:00Z';future['known_at']=t.cutoff.iloc[0];future['minutes']=90
    pd.testing.assert_frame_equal(reference,context_features(t,pd.concat([e,future])))


def test_unknown_minutes_are_explicit_and_not_proof_of_rest():
    t,e=rows();e['minutes']=np.nan;f=context_features(t,e).iloc[0]
    assert f.context_missing_minutes_14d==1 and np.isnan(f.context_rest_days)
    assert not f.context_coverage_complete


def test_duplicate_and_naive_clock_rejected():
    t,e=rows()
    with pytest.raises(ValueError,match='Duplicate'):context_features(t,pd.concat([e,e]))
    e['known_at']='2026-10-18T23:00:00'
    with pytest.raises(ValueError,match='Timezone'):context_features(t,e)


def test_target_labels_forbidden_and_adapter_preserves_other_inputs():
    t,e=rows()
    with pytest.raises(ValueError,match='Target outcomes'):context_features(t.assign(minutes=90),e)
    c=context_features(t,e);f=t.assign(rest_days=10.,minutes_7d=0.,minutes_14d=0.,physical_last_known_at=pd.NaT,normal_p=.8,starter_mean=85.)
    a=apply_physical_context(f,c)
    assert a.minutes_7d.iloc[0]==120 and a.normal_p.iloc[0]==.8 and a.starter_mean.iloc[0]==85.
    assert isinstance(a.physical_last_known_at.dtype,pd.DatetimeTZDtype)


def test_current_adapter_uses_canonical_club_and_real_capture_clock():
    from build_competition_context import canonical_events
    games=[dict(match_id='cl',finished=True,tournament='cl',kickoff_time='2026-10-18T20:00:00Z',observed_at='2026-10-20T08:00:00Z')]
    players=[dict(match_id='cl',player_uuid='p',team_id=2,team_code=7,minutes_played=90,started=True,available_at='2026-10-18T23:00:00Z')]
    clubs=pd.DataFrame([dict(team_id=2,team='Canonical Club'),dict(team_id=7,team='Different Club')])
    e=canonical_events(games,players,clubs,'s')
    assert e.club.iloc[0]=='Canonical Club'
    assert pd.Timestamp(e.known_at.iloc[0])==pd.Timestamp('2026-10-20T08:00:00Z')
    t,_=rows();t['club']='Canonical Club';t['cutoff']='2026-10-20T08:00:00Z'
    assert context_features(t,e).context_history_missing.iloc[0]


def test_unknown_load_uses_existing_missingness_channels_not_zero():
    t,e=rows();e['minutes']=np.nan;c=context_features(t,e)
    f=t.assign(rest_days=10.,minutes_7d=0.,minutes_14d=0.,physical_last_known_at=pd.NaT,normal_p=.8)
    a=apply_physical_context(f,c)
    assert a[['rest_days','minutes_7d','minutes_14d']].isna().all().all()
    assert a.normal_p.iloc[0]==.8


def test_adapter_accepts_equivalent_mixed_iso_clock_formats():
    t,e=rows();c=context_features(t,e);f=t.assign(rest_days=10.,minutes_7d=0.,minutes_14d=0.,physical_last_known_at=pd.NaT)
    f2=f.copy();f2['fixture_uuid']='second';f2['cutoff']='2026-10-20 12:00:00+00:00';c2=c.copy();c2['fixture_uuid']='second'
    assert len(apply_physical_context(pd.concat([f,f2],ignore_index=True),pd.concat([c,c2],ignore_index=True)))==2


def test_context_from_another_cutoff_cannot_silently_replace_inputs():
    t,e=rows();c=context_features(t,e);c['cutoff']='2026-10-21T12:00:00Z'
    f=t.assign(rest_days=10.,minutes_7d=0.,minutes_14d=0.,physical_last_known_at=pd.NaT)
    with pytest.raises(ValueError,match='cutoff mismatch'):apply_physical_context(f,c)


def test_current_context_preserves_fresh_pl_load_and_adds_only_cup_load():
    from build_competition_context import combine_current_load
    t,e=rows();c=context_features(t,e)
    # The raw descriptive archive is older and misses a recent PL match.
    authoritative=t.assign(minutes_7d=180.,minutes_14d=270.,rest_days=.5,physical_last_known_at='2026-10-20T10:00:00Z')
    result=combine_current_load(authoritative,c,c)
    assert result.context_minutes_7d.iloc[0]==300
    assert result.context_minutes_14d.iloc[0]==390
    assert result.context_rest_days.iloc[0]==.5
    assert result.context_max_known_at.iloc[0]==pd.Timestamp('2026-10-20T10:00:00Z')

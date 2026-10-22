"""Chronology/identity checks for the offline European role-signal test."""
import numpy as np
import pandas as pd
import pytest
from research_europe_rotation import features,COLS


def sample():
 target=pd.DataFrame([dict(season='s',fixture_uuid='target',player_uuid='p',team_id=1,club='A',pos='MID',cutoff='2025-01-12T10:00:00Z',y=0,minutes=0)])
 core=pd.DataFrame([dict(season='s',fixture_uuid='pl1',player_uuid='p',team_id=1,club='A',started=1,minutes=90,kickoff_at='2025-01-01T12:00:00Z',known_at='2025-01-01T16:00:00Z'),dict(season='s',fixture_uuid='pl2',player_uuid='p',team_id=1,club='A',started=0,minutes=0,kickoff_at='2025-01-07T12:00:00Z',known_at='2025-01-07T16:00:00Z')])
 ev=pd.DataFrame([dict(season='s',player_uuid='p',match_id='cl',club='A',competition='Champions League',kickoff='2025-01-09T20:00:00Z',known_at='2025-01-10T00:00:00Z',started=True,minutes=90)])
 return target,core,ev


def test_prior_cl_start_supports_role_after_pl_bench():
 t,c,e=sample();r=features(t,c,e).iloc[0]
 assert r.role_recovery==1 and r.role_recovery_case
 assert r.euro_minutes7==1 and r.euro_latest_start==1
 assert pd.Timestamp(r.europe_max_known_at)<pd.Timestamp(t.cutoff.iloc[0])


def test_future_observation_cannot_change_features():
 t,c,e=sample();base=features(t,c,e)[COLS]
 future=e.assign(match_id='later',kickoff='2025-01-14T20:00:00Z',known_at='2025-01-15T00:00:00Z',minutes=120)
 pd.testing.assert_frame_equal(base,features(t,c,pd.concat([e,future]))[COLS])


def test_late_publication_does_not_become_known_at_kickoff():
 t,c,e=sample();e['known_at']='2025-01-13T00:00:00Z';r=features(t,c,e).iloc[0]
 assert not r.europe_context and r[COLS].eq(0).all()


def test_target_outcomes_and_future_calendar_are_not_features():
 t,c,e=sample();a=features(t,c,e)[COLS]
 t['y']=1;t['minutes']=90;t['future_champions_league']='2025-01-14';t['next_recorded_competition']='fake'
 pd.testing.assert_frame_equal(a,features(t,c,e)[COLS])


def test_unknown_minutes_are_not_confirmed_unused_bench():
 t,c,e=sample();e['started']=False;e['minutes']=np.nan;r=features(t,c,e).iloc[0]
 assert r.missing_euro_minutes==1 and r.euro_latest_unused==0 and r.role_recovery==0


def test_previous_club_does_not_establish_new_club_role():
 t,c,e=sample();e['club']='B';r=features(t,c,e).iloc[0]
 assert not r.europe_context and r[COLS].eq(0).all()


def test_duplicate_player_match_fails_closed():
 t,c,e=sample()
 with pytest.raises(ValueError,match='Duplicate'):features(t,c,pd.concat([e,e]))

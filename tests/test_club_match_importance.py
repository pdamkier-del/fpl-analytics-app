import numpy as np
import pandas as pd
import pytest
from experimental_club_match_importance import build_samples,feature_dicts,pooled_history,Model,known_before,require_deadline_features,select_normal
from analyze_mm_competition_rotation import team_games


def sample():
    rows=[];core=[]
    for match in range(4):
        clock=pd.Timestamp('2024-09-01',tz='UTC')+pd.Timedelta(days=7*match)
        core.append(dict(fixture_uuid=str(match),kickoff_at=clock,team_id=1,cutoff=clock-pd.Timedelta(hours=1)))
        for player in range(13):
            rows.append(dict(season='2024-25',club='Club',match_id=str(match),competition='Premier League',stage=str(match+1),kickoff=clock,player_id=str(player),player_uuid=str(player),minutes=90 if player<11 else np.nan,started=player<11,start_min=np.nan,finish_min=np.nan,source_url='fixture-source'))
    snapshots=pd.DataFrame([dict(club='Club',team_id=1,player_uuid=str(p),cutoff=pd.Timestamp('2024-08-01',tz='UTC'),normal_role_asof=pd.Timestamp('2024-07-01',tz='UTC'),normal_role_p=.8 if p<11 else .2,normal_role_s=80.)for p in range(13)])
    news=pd.DataFrame(columns=['fixture_uuid','player_uuid','cutoff','news_effective_at'])
    return pd.DataFrame(rows),snapshots,pd.DataFrame(core),news


def build(p,s,c,n):return build_samples(p,team_games(p),s,c,n)


def test_current_lineup_and_minutes_do_not_change_own_features_or_prior_hierarchy():
    p,s,c,n=sample();a,ia=build(p,s,c,n)
    changed=p.copy();mask=changed.match_id.eq('3')
    changed.loc[mask&changed.player_id.eq('0'),['started','minutes']]=[False,20]
    changed.loc[mask&changed.player_id.eq('11'),['started','minutes']]=[True,70]
    b,ib=build(changed,s,c,n)
    labels=['normal_share','xi_changes','normal_minute_share','normal_nonselection_unknown','verified_available_not_started','available_normal_starter_share']
    pd.testing.assert_frame_equal(a.drop(columns=labels),b.drop(columns=labels))
    pd.testing.assert_frame_equal(ia.drop(columns=['started','recorded_minutes']),ib.drop(columns=['started','recorded_minutes']))
    assert a.normal_share.ne(b.normal_share).any()


def test_unknown_absence_is_not_a_verified_rest_event():
    p,s,c,n=sample();f,ip=build(p,s,c,n)
    assert f.verified_available_not_started.sum()==0
    assert ip.availability_state.eq('UNKNOWN').all()
    assert not f.deadline_correct.any()


def test_current_and_future_games_never_enter_own_pooled_history():
    f=pd.DataFrame([dict(role_definition='objective',competition='PL',kickoff=pd.Timestamp(t,tz='UTC'),cutoff=pd.Timestamp(t,tz='UTC')-pd.Timedelta(hours=1),normal_share=y)for t,y in [('2024-01-01',.4),('2024-01-08',.8),('2024-01-15',.1)]])
    a=pooled_history(f);f.loc[1:,'normal_share']=1.;b=pooled_history(f)
    assert a.iloc[0].global_usage==b.iloc[0].global_usage
    assert a.iloc[1].global_usage==b.iloc[1].global_usage==.4
    assert a.iloc[1].global_usage_n==1


def test_strict_before_clocks_and_consumer_fail_closed():
    t=pd.Timestamp('2025-01-01',tz='UTC')
    assert not known_before(t,t)
    with pytest.raises(ValueError):require_deadline_features(pd.DataFrame([dict(deadline_correct=False)]))
    with pytest.raises(ValueError):require_deadline_features(pd.DataFrame([dict(deadline_correct=True,cutoff=t,history_last_known=t-pd.Timedelta(hours=1))]))
    with pytest.raises(ValueError):require_deadline_features(pd.DataFrame([dict(deadline_correct=True,source_publication_at=t,cutoff=t,history_last_known=t-pd.Timedelta(hours=1))]))


def test_normal_roles_are_ranked_without_named_star_boosts():
    a={str(i):dict(p=.9 if i<11 else .2,duration=80)for i in range(15)}
    assert set(select_normal(a))=={str(i)for i in range(11)}
    a['14']['p']=.99;a['14']['duration']=90
    assert '14'in select_normal(a)


def test_sparse_club_interaction_shrinks_and_unseen_categories_work():
    m=Model(alpha=100).fit([{'club':'a','competition':'PL','club_comp':'a::PL'}]*10+[{'club':'a','competition':'FA','club_comp':'a::FA'}],[.8]*10+[.1])
    pred=m.predict([{'club':'new','competition':'FA','club_comp':'new::FA'}])[0]
    assert np.isfinite(pred)
    assert abs(m.predict([{'club':'a','competition':'FA','club_comp':'a::FA'}])[0]-.1)>.3


def test_feature_allowlist_excludes_current_outcomes_and_is_pl_anchored():
    row=dict(club='Club',competition='Premier League',phase='league',prior_usage=.8,prior_usage_n=3,prior_recent_usage=.7,prior_pl_usage=.8,prior_pl_n=3,prior_pl_recent_usage=.7,global_usage=.8,global_usage_n=100,global_pl_usage=.8,global_pl_n=100,season_days=100,normal_share=1.,xi_changes=0)
    f=pd.DataFrame([row]);a=feature_dicts(f,'D_dynamic');ref=feature_dicts(f,'D_dynamic',counter_pl=True)
    assert a==ref
    assert 'normal_share'not in a[0]and 'xi_changes'not in a[0]
    f['normal_share']=0;f['xi_changes']=11
    assert feature_dicts(f,'D_dynamic')==a


def test_unknown_bench_minutes_do_not_become_duration_evidence():
    from experimental_club_match_importance import prior_role
    t=pd.Timestamp('2025-01-01',tz='UTC')
    a=[dict(known_at=t-pd.Timedelta(days=2),started=False,minutes=None)]
    b=[dict(known_at=t-pd.Timedelta(days=2),started=False,minutes=30)]
    assert prior_role(a,t)==prior_role(b,t)


def test_current_result_never_enters_sporting_context():
    from experimental_club_match_importance import sporting_context
    f=pd.DataFrame([dict(club='Club',match_id='now',cutoff=pd.Timestamp('2025-01-08',tz='UTC'))])
    ledger=[dict(match_id='old',competition='prem',kickoff='2025-01-01T15:00Z',home_team='Club',away_team='Other',result='1 - 0'),dict(match_id='now',competition='prem',kickoff='2025-01-08T15:00Z',home_team='Club',away_team='Other',result='0 - 8')]
    clubs={'Club':'Club','Other':'Other','Third':'Third'}
    a=sporting_context(f,ledger,clubs)
    ledger[1]['result']='9 - 0'
    pd.testing.assert_frame_equal(a,sporting_context(f,ledger,clubs))

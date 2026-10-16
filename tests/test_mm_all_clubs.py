import numpy as np
import pandas as pd
import pytest

from validate_mm_all_clubs import temporal_ci, combined_ci, return_trajectories, descriptive_history, component_problem, metrics


def rows():
    return pd.DataFrame([dict(season='2024-25', fixture_uuid=f'f{i}', player_uuid='p',
        gw=22+i, team_id=1, cutoff=f'2025-02-{i+1:02d}T10:00Z',
        kickoff_at=f'2025-02-{i+1:02d}T14:00Z', y=i%2, minutes=90*(i%2),
        p=.5, q=.2, s=80., c=20., x=42., news_medical_return=i==0,
        news_medical_out=False)for i in range(10)])


def test_temporal_intervals_keep_blank_calendar_gameweeks():
    f=rows();f=f[f.gw.ne(25)]
    r=temporal_ci(f,f,range(22,32),draws=50)
    assert r['calendar_gws']==10 and r['populated_gws']==9
    assert all(v['delta']==0 and v['interval95']==[0.,0.]for v in r['metrics'].values())


def test_sparse_return_groups_do_not_invent_confidence_intervals():
    f=rows().iloc[:3]
    r=temporal_ci(f,f,range(22,32),draws=50)
    assert r['status'].startswith('Not Available')
    assert all(v['interval95']is None for v in r['metrics'].values())
    assert temporal_ci(f.iloc[:0],f.iloc[:0],range(22,32))['metrics']=={}


def test_return_cohorts_distinguish_scheduled_and_played_matches():
    f=rows();r=return_trajectories(f)
    assert r.scheduled_return_match.tolist()[:4]==[1,2,3,0]
    assert r.played_return_match.tolist()[:6]==[0,1,0,2,0,3]
    # Target outcomes change only retrospective played cohorts, not scheduled ones.
    bad=f.copy();bad['minutes']=90
    assert return_trajectories(bad).scheduled_return_match.equals(r.scheduled_return_match)


def test_return_cohort_handles_double_gameweeks_without_duplicate_reset():
    f=rows().iloc[:3].copy();f.loc[1,'gw']=22;f.loc[1,'cutoff']=f.loc[0,'cutoff'];f.loc[1,'news_medical_return']=True
    assert return_trajectories(f).scheduled_return_match.tolist()==[1,2,3]


def test_new_medical_absence_or_club_move_ends_return_cohort():
    f=rows().iloc[:3].copy();f.loc[1,'news_medical_out']=True
    assert return_trajectories(f).scheduled_return_match.tolist()==[1,0,0]
    f=rows().iloc[:3].copy();f.loc[1:,'team_id']=2
    assert return_trajectories(f).scheduled_return_match.tolist()==[1,0,0]


def test_component_identity_and_false_zero_counts():
    f=rows();f['x']=f.p*f.s+(1-f.p)*f.q*f.c
    assert component_problem(f)['largest_component']=='start_selection'
    f.loc[1,['p','q','x']]=0.
    r=metrics(f)
    assert r['false_zero_minutes']==r['false_zero_appearance']==r['false_zero_start']==1
    with pytest.raises(ValueError):component_problem(f.assign(x=f.x+1))


def test_combined_intervals_resample_seasons_without_mixing_identity():
    f=rows();both=pd.concat([f,f.assign(season='2025-26')],ignore_index=True)
    r=combined_ci(both,both,draws=50)
    assert r['season_stratified']
    assert all(v['delta']==0 and v['interval95']==[0.,0.]for v in r['metrics'].values())


def test_full_stint_groups_use_only_prior_verified_available_starts():
    b=rows().assign(news_eligible=True,news_state='AVAILABLE')
    core=b[['season','fixture_uuid','player_uuid','team_id','kickoff_at','minutes']].copy()
    core['started']=1;core['minutes']=90
    prior=descriptive_history(b,core)
    assert not prior.iloc[2].prior_three_full_starts
    assert prior.iloc[3].prior_three_full_starts
    changed=core.copy();changed.loc[8,'minutes']=20
    pd.testing.assert_frame_equal(prior.iloc[:8],descriptive_history(b,changed).iloc[:8])
    # Missing availability is not silently treated as a fit normal-role game.
    b.loc[:2,'news_eligible']=False
    assert not descriptive_history(b,core).iloc[3].prior_three_full_starts

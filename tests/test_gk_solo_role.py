from dataclasses import replace
import numpy as np
import pandas as pd
import pytest
from gk_solo_role import SoloRolePolicy,mark_horizon_absences
from gk_joint_bridge import DurationHistory,prepare,UNKNOWN
from fpl_v1_1_model.joint_simulator import MatchSimInput,PlayerSimInput,simulate_match


def policy(extra=(),count=5):
    obs=[]
    for i in range(count):
        for pid in ['first','backup']:
            at=pd.Timestamp('2025-08-01T12:00:00Z')+pd.Timedelta(days=i*7)
            obs.append(dict(season='2025-26',team_id=1,player_uuid=pid,kickoff_at=at,known_at=at+pd.Timedelta(hours=4),started=int(pid=='first'),confirmed_squad=True))
    p=object.__new__(SoloRolePolicy);p.squads=pd.DataFrame(obs+list(extra));p.squads['kick']=pd.to_datetime(p.squads.kickoff_at,utc=True);p.squads['clock']=pd.to_datetime(p.squads.known_at,utc=True)
    p.teams={('2025-26','1'):p.squads};p.context_cache={};p.risk=.02;p.last_training_label=pd.Timestamp('2025-05-01T00:00:00Z')
    return p


def rows():return pd.DataFrame([dict(player_uuid=p,availability_cap=cap,news_state='AVAILABLE'if cap else'OUT')for p,cap in [('first',0.),('backup',1.),('fringe',1.)]])
WEIGHTS={'first':0.,'backup':.6,'fringe':.1}
CUT='2025-09-10T00:00:00Z'


def test_residual_mass_cannot_give_unproven_reserves_large_start_chances():
    w,pool,a=policy().allocate('2025-26',1,rows(),CUT,WEIGHTS,.3)
    assert a['applied']and w['backup']==pytest.approx(.98)
    assert w['fringe']+pool==pytest.approx(.02)
    assert sum(w.values())+pool==pytest.approx(1)
    assert w['first']==0


def test_missing_squads_and_returning_starter_prevent_false_certainty():
    w,pool,a=policy(count=2).allocate('2025-26',1,rows(),CUT,WEIGHTS,.3)
    assert not a['applied']and w==WEIGHTS and pool==.3
    r=rows();r.loc[r.player_uuid.eq('first'),'availability_cap']=1.
    w,pool,a=policy().allocate('2025-26',1,r,CUT,WEIGHTS,.3)
    assert not a['applied']and w==WEIGHTS


def test_former_starter_outside_recent_five_squads_remains_competitor():
    older=dict(season='2025-26',team_id=1,player_uuid='returning',kickoff_at='2025-07-01T12:00:00Z',known_at='2025-07-01T16:00:00Z',started=1,confirmed_squad=True)
    r=pd.concat([rows(),pd.DataFrame([dict(player_uuid='returning',availability_cap=1.)])])
    _,_,a=policy([older]).allocate('2025-26',1,r,CUT,WEIGHTS,.3)
    assert not a['applied']and'returning'in a['available_known']


def test_recent_unlisted_keeper_is_not_assumed_unavailable():
    extra=dict(season='2025-26',team_id=1,player_uuid='unlisted-provider:9',kickoff_at='2025-08-29T12:00:00Z',known_at='2025-08-29T16:00:00Z',started=0,confirmed_squad=True)
    _,_,a=policy([extra]).allocate('2025-26',1,rows(),CUT,WEIGHTS,.3)
    assert not a['applied']


def test_future_squad_and_target_outcomes_cannot_change_prediction():
    future=dict(season='2025-26',team_id=1,player_uuid='fringe',kickoff_at='2025-09-20T12:00:00Z',known_at='2025-09-20T16:00:00Z',started=1,confirmed_squad=True)
    r=rows();r['y']=[1,0,0];r['minutes']=[90,0,0]
    assert policy([future]).allocate('2025-26',1,r,CUT,WEIGHTS,.3)[:2]==policy().allocate('2025-26',1,rows(),CUT,WEIGHTS,.3)[:2]
    with pytest.raises(ValueError,match='Future'):
        policy().allocate('2025-26',1,r,'2025-01-01T00:00:00Z',WEIGHTS,.3)


def test_doubtful_sole_backup_is_not_promoted_to_near_certain_starter():
    r=rows();r.loc[r.player_uuid.eq('backup'),'availability_cap']=.5
    _,_,a=policy().allocate('2025-26',1,r,CUT,WEIGHTS,.3)
    assert not a['applied']


def test_explicit_season_loan_applies_to_every_future_week_without_guessing_injury_return():
    pred=pd.DataFrame([dict(fpl_element=p,pos='GK',gw=w)for p in [1,2,3]for w in range(8,14)])
    b=dict(elements=[dict(id=1,element_type=1,status='u',news='On loan at X for rest of season'),dict(id=2,element_type=1,status='i',news='Head injury - Unknown return date'),dict(id=3,element_type=1,status='u',news='Unavailable')])
    f=mark_horizon_absences(pred,b)
    assert f.loc[f.fpl_element.eq(1),'role_horizon_absence'].all()
    assert not f.loc[f.fpl_element.ne(1),'role_horizon_absence'].any()
    assert'role_horizon_absence'not in pred


def test_role_adjustment_preserves_exact_joint_gk_coverage_and_mm_pm_moments():
    p=policy();d=DurationHistory(pd.DataFrame([dict(player_uuid='x',team_id=1,started=1,minutes=90 if i%20 else 60,known_at='2025-01-01T00:00:00Z')for i in range(120)]),CUT)
    players=[];r=[]
    for team in ['1','2']:
        for pid,prob,cap in [('first',0.,0.),('backup',.6,1.),('fringe',.1,1.)]:
            player=pid if team=='1'else team+pid
            players.append(PlayerSimInput(player,team,'GK',prob,.01 if cap else 0.,78.,15.,is_keeper=True));r.append(dict(player_uuid=player,availability_cap=cap,new_p_start=prob,news_state='AVAILABLE'if cap else'OUT',role_horizon_absence=pid=='fringe'))
        for i in range(15):players.append(PlayerSimInput(team+'out'+str(i),team,'MID',2/3,.1,75.,15.))
    inp=MatchSimInput('1','2',1.,1.,tuple(players));joint,m,a=prepare(inp,pd.DataFrame(r),d,incomplete_teams=('1','2'),role_policy=p,season='2025-26')
    assert m['backup']['p']==pytest.approx(.98)
    assert 86<m['backup']['x']<90 and m['first']['x']==0 and m['fringe']['x']==0
    for seed in range(200):
        out=simulate_match(joint,np.random.default_rng(seed))
        for team in ['1','2']:
            keepers=[x for x in joint.players if x.is_keeper and x.team==team]
            assert sum(out[x.player_id].minutes for x in keepers)==90
            assert sum(out[x.player_id].started for x in keepers)==1
    assert all(x['analytic_gk_minutes']==pytest.approx(90)for x in a)


def test_missing_availability_does_not_make_returning_competitor_disappear():
    r=rows();r.loc[r.player_uuid.eq('first'),'availability_cap']=np.nan
    _,_,a=policy().allocate('2025-26',1,r,CUT,WEIGHTS,.3)
    assert not a['applied']and'first'in a['available_known']


def test_unknown_news_is_not_confirmation_of_backup_fitness():
    r=rows();r.loc[r.player_uuid.eq('backup'),'news_state']='UNKNOWN'
    _,_,a=policy().allocate('2025-26',1,r,CUT,WEIGHTS,.3)
    assert not a['applied']

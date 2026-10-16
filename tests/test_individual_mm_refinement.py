import numpy as np
import pandas as pd
import pytest
from research_individual_mm_refinement import build_features,duration_distribution,change,project,design,NUM


def roster():
    pos=['GK']*2+['DEF']*5+['MID']*5+['FWD']*3
    return pd.DataFrame([dict(season='2024-25',fixture_uuid='m',team_id=1,player_uuid=str(i),pos=p,p=.5 if p=='GK'else 10/13,q=.3,s=80.,c=15.,x=0.,news_eligible=True,news_state='AVAILABLE',news_chance=100.,return_active=False,return_prior_games=np.nan,return_prior_p=np.nan,return_prior_s=np.nan,history_n=10.,stable_p=.7)for i,p in enumerate(pos)])


def source_rows(states=('AVAILABLE','AVAILABLE'),mins=(90,90)):
    rows=[];actual=[]
    for i,(state,m)in enumerate(zip(states,mins)):
        cut=pd.Timestamp('2025-01-01',tz='UTC')+pd.Timedelta(days=7*i)
        rows.append(dict(season='2024-25',fixture_uuid=str(i),player_uuid='p',team_id=1,gw=20+i,cutoff=cut,p=.7,q=.2,s=80.,c=15.,x=56.9,y=int(m>30),minutes=float(m),normal_role_p=.8,normal_role_s=85.,news_eligible=True,news_state=state,news_medical_out=state=='OUT',news_medical_return=False,pos='MID'))
        actual.append(dict(season='2024-25',fixture_uuid=str(i),player_uuid='p',team_id=1,gw=20+i,kickoff_at=cut+pd.Timedelta(hours=2),started=int(m>30),minutes=float(m)))
    base=pd.DataFrame(rows);role=base[['season','fixture_uuid','player_uuid','p']].copy()
    return base,role,pd.DataFrame(actual)


def test_current_outcomes_do_not_change_own_features():
    b,r,c=source_rows();a,hs,hc=build_features(b,r,c)
    b.loc[1,['y','minutes']]=[0,10.];c.loc[1,['started','minutes']]=[0,10.]
    z,hs2,hc2=build_features(b,r,c)
    columns=NUM+['return_active','return_prior_p','return_prior_s','return_prior_games','max_history_known_at']
    pd.testing.assert_frame_equal(a[columns],z[columns]);assert np.array_equal(hs,hs2);assert np.array_equal(hc,hc2)


def test_unverified_absence_never_updates_normal_role():
    b,r,c=source_rows(('OUT','AVAILABLE'),(0,90));f,hs,hc=build_features(b,r,c)
    assert f.iloc[1].history_n==0
    assert f.iloc[1].stable_p==.8
    assert hs[1].sum()==hc[1].sum()==0


def test_known_past_participation_is_role_evidence_without_inventing_health():
    b,r,c=source_rows(('UNKNOWN','AVAILABLE'),(90,90));f,hs,hc=build_features(b,r,c)
    assert f.iloc[1].history_n>0
    assert f.iloc[1].stable_p>.8
    assert hs[1,90]>0


def test_hard_source_outcome_conflict_is_not_normal_role_training_evidence():
    b,r,c=source_rows(('OUT','AVAILABLE'),(90,90));f,hs,hc=build_features(b,r,c)
    assert f.iloc[1].history_n==0
    assert hs[1].sum()==0


def test_return_requires_explicit_available_not_actual_appearance():
    b,r,c=source_rows(('AVAILABLE','OUT','UNKNOWN'),(90,0,90));f,*_=build_features(b,r,c)
    assert not f.iloc[-1].return_active
    b.loc[2,'news_state']='AVAILABLE';g,*_=build_features(b,r,c)
    assert g.iloc[-1].return_active
    assert g.iloc[-1].return_prior_p==.7
    assert g.iloc[-1].return_prior_games==0


def test_projection_preserves_hard_zero_and_legal_marginals():
    f=roster();f.loc[0,['p','q','news_state','news_chance']]=[0.,0.,'OUT',0.]
    g=project(f)
    assert g.loc[0,'p']==g.loc[0,'q']==g.loc[0,'x']==0
    assert abs(g.p.sum()-11)<1e-6
    assert abs(g[g.pos.eq('GK')].p.sum()-1)<1e-6


def test_duration_pmf_has_bounded_support_and_no_manual_star_boost():
    residual=np.zeros(181);residual[90]=1
    personal=np.zeros(91);personal[90]=10
    mean,sd,lo,hi,p90,p15=duration_distribution(90,residual,personal)
    assert mean==90 and sd==0 and lo==hi==90 and p90==1 and p15==0
    mean,*_=duration_distribution(-100,residual,np.zeros(91),cameo=True)
    assert mean==1


def test_duration_ablation_does_not_change_start_or_cameo_probabilities():
    f=roster();raw={'C_s:10.0':np.full(len(f),88.),'C_c:10.0':np.full(len(f),12.)}
    g=change(f,'C',(10.,1.),raw=raw)
    assert np.array_equal(g.p,f.p)and np.array_equal(g.q,f.q)
    assert g.s.eq(88).all()and g.c.eq(12).all()
    assert np.allclose(g.x,g.p*g.s+(1-g.p)*g.q*g.c)


def test_design_excludes_current_truth():
    f=pd.DataFrame([{**{n:1. for n in NUM},'pos':'MID','minutes':90,'y':1}]);a=design(f)
    f['minutes']=0;f['y']=0
    assert np.array_equal(a,design(f))


def test_history_at_cutoff_is_not_known():
    b,r,c=source_rows();c.loc[0,'kickoff_at']=b.loc[1,'cutoff']-pd.Timedelta(hours=4)
    f,*_=build_features(b,r,c)
    assert f.iloc[1].history_n==0
    assert pd.isna(f.iloc[1].max_history_known_at)

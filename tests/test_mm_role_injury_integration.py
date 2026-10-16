import copy
import numpy as np
import pandas as pd
import pytest
from experimental_role_injury_mm import medical_fields,eligible_news,bounded_news,carry_normal_role
from validate_role_injury_mm import paired,scores
from verify_mm_archive_push_times import event_matches
from research_role_injury_club_audit import Evidence,asof_status

def news():
    return dict(player_uuid='p',team_id=1,identity_status='mapped',timing_verified=True,deadline_matches=True,effective_at='2025-09-26T10:00Z',news_added='2025-09-26T09:00Z',gw=6,payload_current_event=5,payload_next_event=6)

def test_clock_and_club_rejection_and_unknown():
    n=news();assert eligible_news(n,'2025-09-26T11:00Z',1)
    assert not eligible_news(n,'2025-09-26T10:00Z',1)
    assert not eligible_news(n,'2025-09-26T11:00Z',2)
    n['timing_verified']=False;assert not eligible_news(n,'2025-09-26T11:00Z',1)
    n=news();n['news_added']='2025-09-26T12:00Z';assert not eligible_news(n,'2025-09-26T11:00Z',1)
    assert not eligible_news(None,'2025-09-26T11:00Z',1)

def test_unknown_publication_stays_unknown_and_old_club_does_not_override():
    e=Evidence('p','2025-26:1','2025-09-26T10:00Z','','2025-09-26T10:00Z','https://example.org/snapshot','archived','OUT',confidence='official')
    assert e.validate().published_at==''
    assert asof_status([e],'2025-09-26T11:00Z','p','2025-26:1')['state']=='OUT'
    assert asof_status([e],'2025-09-26T11:00Z','p','2025-26:2')['state']=='UNKNOWN'

def test_expected_back_is_not_a_back_injury_or_an_invented_date():
    a=medical_fields(dict(raw_news='Injury - Expected back 14 Sep',raw_status='i'))
    assert a['injury_type']is None and a['confirmed_medical_out']
    assert a['return_earliest']is None and a['expected_absence_text']=='Expected back 14 Sep'
    assert medical_fields(dict(raw_news='Back injury - Unknown return date',raw_status='i'))['injury_type']=='back'
    assert not medical_fields(dict(raw_news='Suspended - Expected back 14 Sep',raw_status='s'))['medical_flag']

def frame():
    return pd.DataFrame([dict(season='2025-26',player_uuid='p',fixture_uuid=str(i),cutoff=f'2025-09-{day}T10:00Z',team_id=1,pos='MID',p=p,s=s,q=.2,c=20.,news_eligible=True,news_state=state,news_chance=None,news_medical_out=medical)for i,(day,p,s,state,medical)in enumerate([('01',.85,82.,'AVAILABLE',False),('08',0.,40.,'OUT',True),('15',.2,50.,'AVAILABLE',False),('22',.7,78.,'AVAILABLE',False)])])

def test_injury_does_not_erase_role_but_return_is_not_automatic_90_minutes():
    f=frame();r=carry_normal_role(f)
    assert r.loc[2,'p']==.85 and r.loc[2,'s']==82
    assert r.loc[1,'p']==r.loc[1,'q']==0
    assert r.loc[3,'p']==.7
    assert not r.loc[3,'carried_normal_role']
    assert f.loc[2,'p']==.2

def test_unknown_or_club_move_cannot_establish_return_role():
    f=frame();f.loc[0,'news_eligible']=False
    assert not carry_normal_role(f).carried_normal_role.any()
    f=frame();f.loc[2:,'team_id']=2
    assert not carry_normal_role(f).carried_normal_role.any()

def test_training_return_does_not_override_official_out():
    assert medical_fields(dict(raw_news='Back in training',raw_status='i'))['training_state']=='RETURNED_TO_TRAINING'
    f=frame();f.loc[:,'news_state']='OUT';g=bounded_news(f)
    assert g.p.eq(0).all()and g.q.eq(0).all()

def test_source_appearance_cap_is_not_multiplied_twice():
    f=frame().iloc[:1].copy();f['p']=.6;f['q']=.5;f['news_chance']=75
    g=bounded_news(f,chance=True)
    assert g.p.iloc[0]==.6
    assert g.p.iloc[0]+(1-g.p.iloc[0])*g.q.iloc[0]==pytest.approx(.75)

def test_projection_respects_keeper_partition_and_hard_news():
    f=pd.concat([frame().iloc[:1].assign(player_uuid=str(i),pos='GK'if i<2 else'MID',p=.5 if i<2 else 10/18,news_state='OUT'if i==2 else'AVAILABLE')for i in range(20)],ignore_index=True)
    f['fixture_uuid']='fx';g=bounded_news(f,project=True)
    assert g.p.sum()==pytest.approx(11)and g[g.pos.eq('GK')].p.sum()==pytest.approx(1)
    assert g.iloc[2].p==g.iloc[2].q==0
    assert not g.projection_infeasible.any()

def test_push_event_requires_exact_repository_commit_parent_and_branch():
    s=dict(source_commit='c',parent_commit='b');e=dict(type='PushEvent',public=True,repo=dict(id=359131220,name='Randdalf/fplcache'),payload=dict(ref='refs/heads/main',head='c',before='b'))
    assert event_matches(e,s)
    for key in ['head','before','ref']:
        bad=copy.deepcopy(e);bad['payload'][key]='wrong';assert not event_matches(bad,s)

def test_minute_component_attribution_reconciles_and_cohort_mismatch_fails():
    f=frame();f['y']=[1,0,1,0];f['minutes']=[90,0,60,20];f['x']=f.p*f.s+(1-f.p)*f.q*f.c
    r=scores(f);assert sum(r['component_mae_attribution'].values())==pytest.approx(r['mae'])
    assert paired(f,f)['metrics']['mae']['delta']==0
    with pytest.raises(ValueError):paired(f.iloc[:2],f)

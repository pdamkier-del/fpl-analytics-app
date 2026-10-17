import json
from datetime import datetime,timezone
import numpy as np
import pandas as pd
import pytest
from mm_candidate import FormationSelector,minute_masses,intervals,validate_frame,build_contract
from mm_candidate_forecast import infer_B,register


def roster():
    return pd.DataFrame([dict(season='test',fixture_uuid='target',player_uuid=str(i),team_id=1,gw=7,cutoff='2026-10-20T10:00:00+00:00',pos='GK' if i<2 else 'MID',p=.5,q=.2,s=80.,c=15.,x=41.5,news_eligible=False,news_state='UNKNOWN',news_effective_at=None) for i in range(16)])


def ledger():
    slots=['GK','RB','RCB','LCB','LB','DM','RCM','LCM','RW','ST','LW']
    return pd.DataFrame([dict(season='test',fixture_uuid='past'+str(k),team_id=1,player_uuid=str(i+1),final_role=slot,formation='4-3-3',kickoff=f'2026-09-{k+1:02}T12:00:00+00:00') for k in range(3) for i,slot in enumerate(slots)])


def test_contract_mean_normalization_and_probability_mass():
    f=roster();mass=minute_masses(f)
    assert np.allclose(mass.sum(axis=1),1,atol=1e-12)
    assert np.allclose(mass@np.arange(91),f.x,atol=1e-6,rtol=0)
    doc=build_contract(f,FormationSelector(ledger()),scope='test',source_hash='test',model_data_at=f.cutoff.iloc[0])
    assert len(doc['players'])==16 and not doc['locked_model_active']
    assert all(abs(sum(r['minute_probabilities'])-1)<1e-10 for r in doc['players'])


@pytest.mark.parametrize('mean',[0.,.0001,1.,45.,89.9999,90.])
def test_starter_duration_endpoints_and_near_boundaries(mean):
    f=roster().iloc[:1].copy();f['p']=1.;f['q']=0.;f['s']=mean;f['x']=mean
    mass=minute_masses(f)
    assert abs((mass@np.arange(91)).item()-mean)<1e-6
    assert (mass>=0).all()


def test_one_gk_ten_outfield_hard_constraints_even_when_two_gk_likely():
    f=roster();f.loc[:1,'p']=.99;f['x']=f.p*f.s+(1-f.p)*f.q*f.c
    selected=FormationSelector(ledger()).choose(f)
    assert len(selected['assignments'])==11
    assert sum(r['slot']=='GK' for r in selected['assignments'].values())==1
    assert sum(int(pid)<2 for pid in selected['assignments'])==1


def test_zero_probability_is_never_selected_and_infeasible_is_explicit():
    f=roster();f.loc[:1,['p','q','x']]=0
    result=FormationSelector(ledger()).choose(f)
    assert not result['assignments'] and 'Not Available' in result['status']


def test_target_formation_and_post_cutoff_roles_do_not_enter_selection():
    f=roster();h=ledger();a=FormationSelector(h).choose(f)
    future=h.copy();future['fixture_uuid']='target';future['kickoff']='2026-10-21T10:00:00Z';future['formation']='4-4-2'
    b=FormationSelector(pd.concat([h,future])).choose(f)
    assert a==b


def test_history_is_season_scoped_and_no_invented_2024_formation():
    f=roster();f['season']='other'
    result=FormationSelector(ledger()).choose(f)
    assert result['formation'] is None and not result['assignments']


def test_hard_unavailable_requires_zero_p_q_x_and_valid_clock():
    f=roster();f.loc[0,['news_eligible','news_state','news_effective_at']]=[True,'OUT','2026-10-19T12:00:00Z']
    with pytest.raises(ValueError,match='unavailable'):validate_frame(f)
    f.loc[0,['p','q','x']]=0;validate_frame(f)
    f.loc[0,'news_effective_at']=f.cutoff.iloc[0]
    with pytest.raises(ValueError,match='News'):validate_frame(f)


def test_shortest_interval_uses_only_mass_and_contains_nominal_mass():
    mass=minute_masses(roster())
    for level in [.5,.8,.9]:
        l,u=intervals(mass,level,'shortest')
        for i,(a,b) in enumerate(zip(l,u)):
            assert 0<=a<=b<=90 and mass[i,a:b+1].sum()>=level-1e-10
            for lo in range(91):
                hi=lo+(b-a)-1
                if hi>=lo and hi<91:assert mass[i,lo:hi+1].sum()<level+1e-10


def test_target_labels_rejected_before_training():
    t=roster();t['minutes']=90
    with pytest.raises(ValueError,match='outcomes'):infer_B(pd.DataFrame(),t,{})


def test_register_refuses_late_forecast_or_overwrite(tmp_path):
    doc={'scope':'prospective_preview','players':[{'forecast_at':'2026-10-20T10:00:00Z'}]}
    early=datetime(2026,10,19,tzinfo=timezone.utc)
    result=register(doc,tmp_path,early)
    assert json.loads(open(result['path']).read())==doc
    with pytest.raises(FileExistsError):register(doc,tmp_path,early)
    with pytest.raises(ValueError,match='after deadline'):register(doc,tmp_path,datetime(2026,10,21,tzinfo=timezone.utc))


def test_missing_and_malformed_input_fail_closed():
    f=roster();f.loc[0,'p']=float('nan')
    with pytest.raises(ValueError):validate_frame(f)
    f=roster();f.loc[0,'x']+=1
    with pytest.raises(ValueError,match='expectation'):validate_frame(f)


def test_canonical_identity_names_include_reserves_and_prefer_registry(tmp_path):
    import sqlite3
    from build_mm_integration_preview import canonical_names
    path=tmp_path/'identity-test.sqlite3'
    with sqlite3.connect(path) as db:
        db.execute('CREATE TABLE players(player_uuid TEXT,canonical_name TEXT)')
        db.executemany('INSERT INTO players VALUES (?,?)',[('test-reserve','Test Reserve'),('test-starter','Test Starter')])
    history=pd.DataFrame([dict(player_uuid='test-starter',player='Short name')])
    names=canonical_names(path,history)
    assert names['test-reserve']=='Test Reserve'
    assert names['test-starter']=='Test Starter'

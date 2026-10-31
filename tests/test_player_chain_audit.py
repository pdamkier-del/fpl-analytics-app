import copy
import hashlib
import json
import gzip
from pathlib import Path

import pandas as pd
import pytest

from analysis.audit_player_chain import audit
from scripts.export_joint_gk_preview import selected_nonpenalty_evidence


def goalkeeper_bundle(tmp_path,f):
    inputs=tmp_path/'work/current-B-inputs';inputs.mkdir(parents=True)
    input_bundle(inputs,f)
    role=tmp_path/'work/joint-gk-current/role-squad-evidence.csv.gz'
    role.parent.mkdir(parents=True);raw=b'player_uuid,confirmed_squad\nkeeper,True\n'
    role.write_bytes(gzip.compress(raw,mtime=0))
    f['model']='B-MM-PM-TS-v1'
    f['goalkeeper_role_fit']={'squad_evidence_sha256':hashlib.sha256(raw).hexdigest()}
    official=tmp_path/'work/gk-official-evidence';official.mkdir()
    sources={}
    bootstrap={'elements':[dict(id=p['id'],element_type=p['position'],status='a',news='',chance_of_playing_next_round=None)for p in f['players']]}
    for key,data in [('chelsea_squad',b'official squad'),('fpl_bootstrap',json.dumps(bootstrap).encode())]:
        (official/(key+('.json'if key=='fpl_bootstrap'else'.html'))).write_bytes(data)
        sources[key]={'sha256':hashlib.sha256(data).hexdigest()}
    f['official_gk_evidence']={'sources':sources,'observed_at':f['data_asof']}
    f['official_gk_status']={str(p['id']):{k:p[k]for k in ['status','news','chance_of_playing_next_round']}
                             for p in bootstrap['elements']if p['element_type']==1}
    (official/'evidence.json').write_text(json.dumps(f['official_gk_evidence']))
    return inputs,role,official


def test_complete_source_checks_include_actual_goalkeeper_role_and_official_inputs(coherent,tmp_path):
    f,m,c=coherent;inputs,_,_=goalkeeper_bundle(tmp_path,f)
    r=audit(f,m,catalogue=c,inputs=inputs)
    assert r['goalkeeper_role_source_evidence_verified']
    assert r['official_goalkeeper_source_evidence_verified']
    assert r['source_linkage_passed']and r['all_model_source_evidence_verified']
    assert r['full_model_certification']is False


@pytest.mark.parametrize('change',['missing_role','corrupt_role','wrong_role','raw_squad','saved_receipt','status_snapshot'])
def test_missing_or_tampered_goalkeeper_input_cannot_appear_complete(coherent,tmp_path,change):
    f,m,c=coherent;inputs,role,official=goalkeeper_bundle(tmp_path,f)
    if change=='missing_role':role.unlink()
    elif change=='corrupt_role':role.write_bytes(b'not gzip')
    elif change=='wrong_role':role.write_bytes(gzip.compress(b'different valid input',mtime=0))
    elif change=='raw_squad':(official/'chelsea_squad.html').write_bytes(b'changed')
    elif change=='saved_receipt':(official/'evidence.json').write_text('{}')
    else:f['official_gk_status']['100']['status']='i'
    r=audit(f,m,catalogue=c,inputs=inputs)
    assert not r['all_model_source_evidence_verified']
    assert not r['source_linkage_passed']
    assert all(not p['input_evidence_verified']for p in r['players'])


def test_unified_model_without_goalkeeper_receipts_is_not_source_complete(coherent,tmp_path):
    f,m,c=coherent;input_bundle(tmp_path,f);f['model']='B-MM-PM-TS-v1'
    r=audit(f,m,catalogue=c,inputs=tmp_path)
    assert not r['goalkeeper_role_source_evidence_verified']
    assert not r['official_goalkeeper_source_evidence_verified']
    assert not r['source_linkage_passed']


@pytest.fixture
def coherent():
    f=dict(players=[],gws=[9],player_fixture_rows=22,
           forecast_sha256='test-origin',data_asof='2026-10-23T12:00:00Z',
           gk_team_fixtures=[])
    mm={'players':[]};catalogue=[]
    for team in [1,2]:
        for i in range(11):
            pid=team*100+i;uid=str(pid);position=1 if i==0 else 3
            q=dict(fixture_uuid='fixture',xmins=90.,pm_analytic_minutes=90.,
                   p_start=1.,p_60_plus=1.,p_90=1.,xpts=2.,
                   components={'appearance_points':2.})
            w=dict(gw=9,xmins=90.,xpts=2.,fixtures=[q],
                   scenarios={'minutes':[90]*4,'points':[2]*4})
            f['players'].append(dict(id=pid,player_uuid=uid,name=uid,
                                     team_id=team,team=str(team),position=position,weeks=[w]))
            mm['players'].append(dict(player_id=uid,fixture_id='fixture',xmins=90.,
                p_start=1.,p_sub_given_not_start=0.,start_minutes=90.,sub_minutes=20.,
                p_60_plus=1.,p_90=1.,p_play=1.))
            catalogue.append(dict(id=pid,team=team,element_type=position))
        f['gk_team_fixtures'].append(dict(team=team,fixture_uuid='fixture',
                                         unlisted_start_probability=0.,unlisted_expected_minutes=0.))
    return f,mm,catalogue


def test_coherence_is_not_calibration(coherent):
    f,m,c=coherent;r=audit(f,m,catalogue=c)
    assert r['technical_moment_contract_passed']
    assert all(g['expected_outfield_minutes']==900 for g in r['team_fixtures'])
    assert all(p['physical_team_minutes_verified']is None for p in r['players'])
    assert r['full_model_certification'] is False
    assert not r['source_input_evidence_verified']
    assert all(p['calibration_independently_certified'] is False for p in r['players'])


@pytest.mark.parametrize('error,passed',[(1e-16,True),(1e-6,False)])
def test_probability_roundoff_is_tolerated_but_real_ordering_error_is_not(coherent,error,passed):
    f,m,c=coherent;m['players'][-1]['p_play']=1-error
    r=audit(f,m,catalogue=c)
    assert r['technical_moment_contract_passed'] is passed


def test_reported_total_alone_does_not_establish_a_physical_timeline(coherent):
    f,m,c=coherent;p=copy.deepcopy(f['players'][1]);p.update(id=999,player_uuid='999',name='Reserve')
    w=p['weeks'][0];w.update(xmins=20.,xpts=1.,scenarios={'minutes':[20]*4,'points':[1]*4})
    w['fixtures'][0].update(xmins=20.,pm_analytic_minutes=20.,p_start=0.,p_60_plus=0.,p_90=0.,xpts=1.,components={'appearance_points':1.})
    f['players'].append(p);f['player_fixture_rows']+=1
    m['players'].append(dict(player_id='999',fixture_id='fixture',xmins=20.,p_start=0.,
        p_sub_given_not_start=1.,start_minutes=90.,sub_minutes=20.,p_60_plus=0.,p_90=0.,p_play=1.))
    c.append(dict(id=999,team=1,element_type=3))
    r=audit(f,m,catalogue=c)
    assert r['technical_moment_contract_passed']
    assert 'normal_substitution_limit_exceeded'not in r['finding_counts']
    g=next(g for g in r['team_fixtures']if g['team_id']==1)
    assert g['expected_outfield_minutes']==920
    assert 'draws_over_900'not in g
    assert all(p['physical_team_minutes_verified']is None for p in r['players'] if p['team_id']==1)


@pytest.mark.parametrize('mutation,code',[
    ('duplicate_identity','duplicate_player_identity'),
    ('duplicate_fixture','duplicate_player_fixture'),
    ('missing_mm','MM_PM_identity_coverage'),
    ('point_sum','point_components_mismatch'),
    ('week_sum','fixture_week_aggregation'),
    ('minute_moment','MM_PM_moment_mismatch'),
    ('wrong_club','catalogue_identity_mismatch'),
])
def test_corrupt_boundary_is_detected_for_any_player(coherent,mutation,code):
    f,m,c=coherent;p=f['players'][-1]
    if mutation=='duplicate_identity':p['id']=f['players'][0]['id']
    elif mutation=='duplicate_fixture':p['weeks'][0]['fixtures']*=2
    elif mutation=='missing_mm':m['players'].pop()
    elif mutation=='point_sum':p['weeks'][0]['fixtures'][0]['components']['appearance_points']=3
    elif mutation=='week_sum':p['weeks'][0]['xpts']=3
    elif mutation=='minute_moment':m['players'][-1]['sub_minutes']=120;m['players'][-1]['p_sub_given_not_start']=1;m['players'][-1]['p_start']=.5
    elif mutation=='wrong_club':c[-1]['team']=99
    r=audit(f,m,catalogue=c)
    assert code in r['finding_counts']
    assert r['technical_moment_contract_passed'] is False


def test_double_gameweek_samples_are_not_mislabeled_as_fixture_samples(coherent):
    f,m,c=coherent
    for p in f['players']:
        w=p['weeks'][0];q=copy.deepcopy(w['fixtures'][0]);q['fixture_uuid']='second';w['fixtures'].append(q)
        w.update(xmins=180.,xpts=4.,scenarios={'minutes':[180]*4,'points':[4]*4})
    for row in list(m['players']):m['players'].append(dict(row,fixture_id='second'))
    f['player_fixture_rows']*=2
    for row in list(f['gk_team_fixtures']):f['gk_team_fixtures'].append(dict(row,fixture_uuid='second'))
    r=audit(f,m,catalogue=c)
    assert r['technical_moment_contract_passed']
    assert len(r['team_fixtures'])==4
    assert all('draws_over_900' not in g for g in r['team_fixtures'])
    assert all(p['physical_team_minutes_verified'] is None for p in r['players'])


def test_average_900_does_not_hide_invalid_individual_timelines(coherent):
    f,m,c=coherent
    for index in [1,2]:
        p=f['players'][index];w=p['weeks'][0]
        w['xmins']=70;w['scenarios']['minutes']=[70]*4
        w['fixtures'][0].update(xmins=70,pm_analytic_minutes=70,p_90=0)
        m['players'][index].update(xmins=70,start_minutes=70,p_90=0)
    for i,minutes in enumerate([[10,20,30,20],[20,20,20,20]]):
        p=copy.deepcopy(f['players'][1]);p.update(id=998+i,player_uuid=str(998+i),name='Reserve')
        w=p['weeks'][0];w.update(xmins=20,xpts=1,scenarios={'minutes':minutes,'points':[1]*4})
        w['fixtures'][0].update(xmins=20,pm_analytic_minutes=20,p_start=0,p_60_plus=0,p_90=0,xpts=1,components={'appearance_points':1})
        f['players'].append(p);f['player_fixture_rows']+=1
        m['players'].append(dict(player_id=p['player_uuid'],fixture_id='fixture',xmins=20,p_start=0,p_sub_given_not_start=1,start_minutes=90,sub_minutes=20,p_60_plus=0,p_90=0,p_play=1))
        c.append(dict(id=p['id'],team=1,element_type=3))
    r=audit(f,m,catalogue=c);g=next(g for g in r['team_fixtures']if g['team_id']==1)
    assert r['technical_moment_contract_passed']
    assert g['expected_outfield_minutes']==900
    assert 'draws_not_900'not in g
    assert all(p['physical_team_minutes_verified'] is None for p in r['players']if p['team_id']==1)


def add_substitution(f,m,c,index,starter_minutes,sub_minutes,identity):
    p=f['players'][index];w=p['weeks'][0];q=w['fixtures'][0]
    xp=2 if starter_minutes>=60 else 1
    w.update(xmins=starter_minutes,xpts=xp,scenarios={'minutes':[starter_minutes]*4,'points':[xp]*4})
    q.update(xmins=starter_minutes,pm_analytic_minutes=starter_minutes,p_60_plus=float(starter_minutes>=60),p_90=0,xpts=xp,components={'appearance_points':xp})
    m['players'][index].update(xmins=starter_minutes,start_minutes=starter_minutes,p_60_plus=float(starter_minutes>=60),p_90=0)
    sub=copy.deepcopy(p);sub.update(id=identity,player_uuid=str(identity),name='Sub')
    w=sub['weeks'][0];q=w['fixtures'][0]
    w.update(xmins=sub_minutes,xpts=1,scenarios={'minutes':[sub_minutes]*4,'points':[1]*4})
    q.update(xmins=sub_minutes,pm_analytic_minutes=sub_minutes,p_start=0,p_60_plus=0,p_90=0,xpts=1,components={'appearance_points':1})
    f['players'].append(sub);f['player_fixture_rows']+=1
    m['players'].append(dict(player_id=str(identity),fixture_id='fixture',xmins=sub_minutes,p_start=0,p_sub_given_not_start=1,start_minutes=90,sub_minutes=sub_minutes,p_60_plus=0,p_90=0,p_play=1))
    c.append(dict(id=identity,team=p['team_id'],element_type=p['position']))


def test_three_valid_reported_minute_pairs_sum_897_without_false_900_violation(coherent):
    f,m,c=coherent
    for i,(a,b)in enumerate([(55,34),(68,21),(72,17)],1):add_substitution(f,m,c,i,a,b,1000+i)
    r=audit(f,m,catalogue=c);g=next(g for g in r['team_fixtures']if g['team_id']==1)
    assert g['expected_outfield_minutes']==897
    assert g['maximum_known_substitutions_lower_bound']==3
    assert 'normal_substitution_limit_exceeded'not in r['finding_counts']
    assert r['technical_moment_contract_passed']
    assert all(p['physical_team_minutes_verified']is None for p in r['players'])


@pytest.mark.parametrize('include_GK',[False,True])
def test_six_substitutions_are_detected_even_with_exact_900_model_minutes(coherent,include_GK):
    f,m,c=coherent
    indices=[0,1,2,3,4,5]if include_GK else[1,2,3,4,5,6]
    for index in indices:add_substitution(f,m,c,index,70,20,1000+index)
    r=audit(f,m,catalogue=c);g=next(g for g in r['team_fixtures']if g['team_id']==1)
    assert g['expected_outfield_minutes']==900
    assert g['maximum_known_substitutions_lower_bound']==6
    assert g['draws_over_standard_five_sub_limit']==4
    assert r['finding_counts']['normal_substitution_limit_exceeded']==1
    assert all(p['physical_team_minutes_verified']is False for p in r['players']if p['team_id']==1)


def input_bundle(tmp_path,f):
    rows=[dict(player_uuid=p['player_uuid'],fixture_uuid=q['fixture_uuid'],
               cutoff=f['data_asof'],minutes_7d=0,minutes_14d=0,rest_days=20,
               last_started=0,history_n=1)for p in f['players']for w in p['weeks']for q in w['fixtures']]
    pd.DataFrame(rows).to_csv(tmp_path/'target.csv.gz',index=False)
    (tmp_path/'pm.csv.gz').write_bytes(b'fixed-public-input')
    (tmp_path/'provenance.json').write_text('{}')
    pd.DataFrame([{'known_at':'2026-10-01T12:00:00Z'}]).to_csv(tmp_path/'history.csv.gz',index=False)
    f['input_sha256']={p.name:hashlib.sha256(p.read_bytes()).hexdigest()for p in tmp_path.iterdir()}


def test_late_context_is_diagnostic_not_pre_cutoff_source(coherent,tmp_path):
    f,m,c=coherent;input_bundle(tmp_path,f)
    context={'rows':[dict(player_id=101,competition='cl',minutes=90,
        kickoff='2026-10-20T19:00:00Z',source_observed_at='2026-10-24T12:00:00Z')]}
    r=audit(f,m,catalogue=c,inputs=tmp_path,context=context)
    assert r['source_input_evidence_verified']
    p=next(p for p in r['players']if p['id']==101);q=p['fixtures'][0]
    assert q['PL_workload']['minutes_7d']==0
    assert q['non_PL_minutes_14d_in_context']==90
    assert q['context_records_first_captured_after_cutoff']==1
    assert q['later_context_is_not_proof_of_model_consumption']


def test_different_origin_input_bundle_is_never_substituted(coherent,tmp_path):
    f,m,c=coherent;input_bundle(tmp_path,f)
    (tmp_path/'provenance.json').write_bytes(b'different origin')
    r=audit(f,m,catalogue=c,inputs=tmp_path)
    assert not r['source_input_evidence_verified']
    assert all('PL_workload' not in q for p in r['players']for q in p['fixtures'])


def test_verified_MM_input_is_not_complete_NP_derivation_evidence(coherent,tmp_path):
    f,m,c=coherent;input_bundle(tmp_path,f)
    f['nonpenalty_goal_head']={'source_sha256':{'player_fixture_observations':'missing'}}
    r=audit(f,m,catalogue=c,inputs=tmp_path)
    assert r['source_input_evidence_verified']
    assert r['all_model_source_evidence_verified'] is False
    assert r['source_linkage_passed'] is False
    assert all(p['input_evidence_verified'] is False for p in r['players'])
    assert 'ordinary_goal_source_evidence_unavailable' in r['finding_counts']


@pytest.mark.parametrize('source,code',[('history','training_history_after_origin'),
                                       ('features','feature_history_after_origin'),
                                       ('target','target_outcome_leakage'),
                                       ('cap','availability_cap_exceeded')])
def test_verified_files_can_still_contain_semantic_leakage_or_bad_caps(coherent,tmp_path,source,code):
    f,m,c=coherent;input_bundle(tmp_path,f)
    t=pd.read_csv(tmp_path/'target.csv.gz')
    if source=='history':pd.DataFrame([{'known_at':'2026-10-24T12:00:00Z'}]).to_csv(tmp_path/'history.csv.gz',index=False)
    elif source=='features':t['max_history_known_at']='2026-10-24T12:00:00Z'
    elif source=='target':t['observed_minutes']=90
    elif source=='cap':t['news_eligible']=True;t['news_chance']=25
    t.to_csv(tmp_path/'target.csv.gz',index=False)
    f['input_sha256']={p.name:hashlib.sha256(p.read_bytes()).hexdigest()for p in tmp_path.iterdir()}
    r=audit(f,m,catalogue=c,inputs=tmp_path)
    assert r['source_input_evidence_verified']
    assert code in r['finding_counts']
    assert not r['technical_moment_contract_passed']


def selected_policy(tmp_path):
    new=tmp_path/'new.json';new.write_text(json.dumps(dict(passed=True,fixtures=341,marker='selected')))
    (tmp_path/'old.json').write_text(json.dumps(dict(passed=True,fixtures=341,marker='superseded')))
    return dict(approved=True,decision='new.json',sha256={'new.json':hashlib.sha256(new.read_bytes()).hexdigest()})


def test_export_uses_exact_selected_decision_not_older_experiment(tmp_path):
    policy=selected_policy(tmp_path);e=selected_nonpenalty_evidence(tmp_path,policy)
    assert e['historical']['marker']=='selected'
    assert e['historical_decision_file']=='new.json'
    (tmp_path/'new.json').write_text(json.dumps(dict(passed=True,marker='changed after approval')))
    with pytest.raises(ValueError,match='checksum'):selected_nonpenalty_evidence(tmp_path,policy)


def test_old_public_evidence_is_reported_not_green(coherent,tmp_path):
    f,m,c=coherent;policy=selected_policy(tmp_path);f['nonpenalty_goal_head']={'policy':policy}
    r=audit(f,m,catalogue=c,penalty_evidence=dict(policy=policy,historical=json.loads((tmp_path/'old.json').read_text())),policy_root=tmp_path)
    assert r['published_selected_historical_evidence_matches'] is False
    assert r['finding_counts']['published_validation_policy_mismatch']==1


def test_selected_policy_cannot_escape_repository(tmp_path):
    parent=tmp_path/'inner';parent.mkdir();p=selected_policy(tmp_path);p['decision']='../new.json';p['sha256'][p['decision']]=p['sha256']['new.json']
    with pytest.raises(ValueError,match='receipt'):selected_nonpenalty_evidence(parent,p)

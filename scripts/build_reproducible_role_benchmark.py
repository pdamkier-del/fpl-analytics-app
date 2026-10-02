#!/usr/bin/env python3
"""Rebuild historical roles, pre-cutoff q/H, and a frozen chronological holdout.

No target lineup/position/role or outcome is a prediction input. GW deadlines are
explicit reconstruction proxies unless --cutoffs supplies gw,cutoff timestamps.
The unchanged V2 predictions are a comparator, not a newly cutoff-certified model.
"""
import argparse
import hashlib
import gzip
import io
import importlib.util
from importlib.metadata import version
import json
import os
from pathlib import Path
import sqlite3
import sys

import numpy as np
import pandas as pd
from scipy.special import expit, logit
from scipy.optimize import brentq
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from fpl_v1_1_model.role_classifier import classify_lineup, canonical, ROLES
from fpl_v1_1_model.role_history import RoleHistory, summarize_state

BASE_FEATURES = ['base_logit']
ROLE_FEATURES = [f'role_{f}_{speed}' for speed in ('fast','slow')
                 for f in ('fit','h','qmax','evidence')]+['role_started_last_gw']


def write_json(path, value):
    path.write_text(json.dumps(value, indent=2, sort_keys=True, allow_nan=False)+'\n')


def sha(path):
    h=hashlib.sha256()
    with open(path,'rb') as f:
        for chunk in iter(lambda:f.read(1024*1024),b''): h.update(chunk)
    return h.hexdigest()


def write_prediction_csv(frame,path):
    """Atomic, deterministic gzip with an explicit completeness check.

    Do not leave a partially written benchmark at its final path if interrupted.
    Empty gzip filename prevents destination-dependent header bytes.
    """
    temporary=path.with_name(path.name+'.tmp')
    with open(temporary,'wb') as raw:
        with gzip.GzipFile(filename='',mode='wb',fileobj=raw,mtime=0) as compressed:
            with io.TextIOWrapper(compressed,encoding='utf-8',newline='') as stream:
                frame.to_csv(stream,index=False)
        raw.flush();os.fsync(raw.fileno())
    with gzip.open(temporary,'rb') as stream:
        rows=sum(chunk.count(b'\n') for chunk in iter(lambda:stream.read(1024*1024),b''))
    assert rows==len(frame)+1, 'Incomplete prediction artifact'
    os.replace(temporary,path)


def normalize_eleven(df, raw):
    result=np.asarray(raw).copy()
    for indexes in df.groupby(['fixture_uuid','team_id'],sort=True).indices.values():
        z=logit(np.clip(result[indexes],1e-7,1-1e-7))
        if len(indexes)<=11: raise ValueError('Insufficient cohort for exact-11 constraint')
        shift=brentq(lambda b:expit(z+b).sum()-11,-40,40)
        result[indexes]=expit(z+shift)
    return result


def metrics(y, minutes, p, xm):
    p=np.clip(np.asarray(p),1e-9,1-1e-9);y=np.asarray(y);err=np.asarray(xm)-np.asarray(minutes)
    return {'n':len(y),'brier':float(np.mean((p-y)**2)),
            'log_loss':float(-np.mean(y*np.log(p)+(1-y)*np.log(1-p))),
            'xmins_mae':float(np.mean(np.abs(err))), 'xmins_rmse':float(np.sqrt(np.mean(err**2)))}


def score(frame, variant):
    return metrics(frame.y,frame.minutes,frame[f'{variant}_p_start'],frame[f'{variant}_xmins'])


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--db',required=True)
    ap.add_argument('--raw-root',default=str(ROOT/'data_v1_1/raw/fpl-core-2025-26'))
    ap.add_argument('--baseline',default=str(ROOT/'analysis/results/v2-reproduced/pstart_v2_fixture_holdout_2025_26.csv'))
    ap.add_argument('--out',default=str(ROOT/'analysis/results/reproducible-role-v1'))
    ap.add_argument('--cutoffs',help='Optional authoritative gw,cutoff CSV; must contain every predicted GW')
    a=ap.parse_args();out=Path(a.out);out.mkdir(parents=True,exist_ok=True)
    con=sqlite3.connect(f'file:{Path(a.db).resolve()}?mode=ro',uri=True)
    obs=pd.read_sql_query("SELECT player_uuid,gw,team_id,opponent_team_id,was_home,fixture_uuid,kickoff_at,started,minutes FROM player_fixture_observations WHERE season='2025-26' AND is_final=1",con)
    assert not obs.duplicated(['fixture_uuid','player_uuid']).any()
    mapping=dict(con.execute("SELECT external_id,player_uuid FROM player_id_mapping WHERE season='2025-26' AND id_namespace='fpl_element'"))
    mapping={str(k):str(v) for k,v in mapping.items()}
    player_names=dict(con.execute('SELECT player_uuid,canonical_name FROM players'))
    spec=importlib.util.spec_from_file_location('geometry',ROOT/'scripts/v1_1_ingest_fpl_core_detailed_roles.py')
    geometry=importlib.util.module_from_spec(spec);spec.loader.exec_module(geometry)
    lines=[];averages=[];fixtures=[];input_paths=[]
    for gw in range(1,39):
        folder=Path(a.raw_root)/f'GW{gw}'
        for name,container in [('lineups',lines),('average_positions',averages),('fixtures',fixtures)]:
            path=folder/f'{name}.csv';input_paths.append(path)
            frame=pd.read_csv(path);frame['gw']=gw;container.append(frame)
    line=pd.concat(lines,ignore_index=True);avg=pd.concat(averages,ignore_index=True);fix=pd.concat(fixtures,ignore_index=True)
    line['player_id']=line.player_id.astype(str);avg['player_id']=avg.player_id.astype(str)
    assert not avg.duplicated(['match_id','player_id']).any()
    line['player_uuid']=line.player_id.map(mapping)
    assert line.player_uuid.notna().all()
    line=line.merge(avg[['match_id','player_id','x','y']],on=['match_id','player_id'],how='left',validate='many_to_one',sort=False)
    line['starting']=line.is_starting.astype(str).str.lower().isin(['true','1','yes'])
    observations={(str(r.fixture_uuid),str(r.player_uuid)):r for r in obs.itertuples()}
    source_groups={(int(gw),mid):g for (gw,mid),g in line.groupby(['gw','match_id'],sort=False)}
    jobs=[];teams={};fixture_lookup={}
    for f in fix.sort_values(['kickoff_time','match_id']).itertuples():
        mg=source_groups[(int(f.gw),f.match_id)]
        home=geometry.mode_team(obs,f.gw,set(mg.loc[mg.team_side=='home','player_uuid']))
        away=geometry.mode_team(obs,f.gw,set(mg.loc[mg.team_side=='away','player_uuid']))
        fixture=geometry.fixture_for(obs,f.gw,home,away,f.kickoff_time)
        assert fixture is not None
        ko=pd.to_datetime(f.kickoff_time,utc=True)
        hname,aname=f.match_id.split('-prem-',1)[1].split('-vs-',1)
        fixture_lookup[fixture]={'kickoff':ko,'gw':int(f.gw),'match_id':f.match_id}
        for side,team,name in [('home',home,hname),('away',away,aname)]:
            teams[int(team)]=name
            sg=mg[(mg.team_side==side)&mg.starting].copy()
            assert len(sg)==11
            sg['slot']=range(1,12)
            formation=str(sg.formation.iloc[0])
            # Replay the legacy numeric-ID tie-break, not lexicographic strings.
            # Equal average y otherwise swaps two Brentford roles in GW37.
            geometric_input=sg.copy();geometric_input['player_id']=geometric_input.player_id.astype(int)
            roles=geometry.add_goalkeeper_roles(geometric_input,geometry.assign_starter_roles(geometric_input,formation))
            roles={mapping[pid]:canonical(role) for pid,role in roles.items()}
            jobs.append((ko,fixture,int(team),int(f.gw),f.match_id,name,formation,sg,roles))
    history=RoleHistory();audit=[];label_differences=[]
    for ko,fixture,team,gw,mid,name,formation,sg,geom in sorted(jobs,key=lambda j:(j[0],j[1],j[2])):
        prior,_,_=history.state(team,ko,10)
        classified=classify_lineup(formation,sg.to_dict('records'),geom,prior)
        layers=geometry.parse_formation(formation)
        counts=sg[sg.position!='G'].position.value_counts()
        protected=counts.get('D',0)==layers[0] and counts.get('F',0)==layers[-1]
        players=[]
        for r in sg.to_dict('records'):
            pid=r['player_uuid'];z=classified[pid];actual=observations.get((fixture,pid))
            if actual is None or not actual.started: label_differences.append({'fixture':fixture,'player':pid,'source_started':True,'core_started':None if actual is None else actual.started})
            minutes=0 if actual is None else float(actual.minutes)
            row={'fixture_uuid':fixture,'match_id':mid,'team_id':team,'team':name,'player_uuid':pid,
                 'player':r['player_name'],'gw':gw,'kickoff':ko.isoformat(),'formation':formation,
                 'lineup_slot':r['slot'],'average_x':r['x'],'average_y':r['y'],**z}
            row['geometry_path']='coarse_position_protected' if protected else 'global_average_x_fallback'
            patterns=geometry.role_pattern
            same_line=z['position_role'] in patterns(layers,z['formation_layer']) if z['formation_layer'] is not None and z['formation_layer']>=0 else z['position_role']=='GK'
            row['geometry_same_formation_line']=same_line
            row['average_position_quality_note']='no touch-count, variance or in-match formation-change timestamps available'
            row['prior_q']=json.dumps(row['prior_q'],sort_keys=True,separators=(',',':'))
            # Diagnostic, not a verified error label.
            if z['disagreement']:
                aa=z['slot_role'];bb=z['position_role']
                if aa[0] in 'RL' and bb[0] in 'RL' and aa[1:]==bb[1:]: cause='left_right_permutation'
                elif {aa,bb}<={'RB','RWB','LB','LWB'}: cause='fullback_wingback'
                elif same_line: cause='within_line_ordering_conflict'
                else: cause='cross_line_assignment_conflict'
                row['diagnostic_type']=cause
            else: row['diagnostic_type']='agreement'
            audit.append(row)
            # The source describes confirmed lineup slots; Core supplies the
            # benchmark's actual start label. Do not promote a lineup discrepancy
            # to actual start evidence in H.
            players.append({'player_uuid':pid,'role':z['final_role'],
                            'started':bool(actual.started) if actual else False,
                            'minutes':minutes,'disagreement':z['disagreement']})
        # Historic effective availability, NOT the source's actual ingestion time.
        history.add_game(team,ko+pd.Timedelta(hours=3),fixture,players)
    audit=pd.DataFrame(audit)
    audit.to_csv(out/'classified_starters.csv',index=False)
    disagreements=audit[(audit.slot_role!='GK')&audit.disagreement].copy()
    disagreements.to_csv(out/'role_disagreements.csv',index=False)
    non_gk=audit[audit.slot_role!='GK']
    for column in ['disagreement_type','diagnostic_type','geometry_path','team','formation']:
        grouped=disagreements.groupby(column).size().rename('count').reset_index()
        grouped['percent_of_disagreements']=grouped['count']/len(disagreements)*100
        if column in ['team','formation']:
            grouped['all_outfield_starters']=grouped[column].map(non_gk.groupby(column).size())
            grouped['disagreement_rate_percent']=100*grouped['count']/grouped.all_outfield_starters
        grouped.sort_values(['count',column],ascending=[False,True]).to_csv(out/f'disagreements_by_{column}.csv',index=False)
    disagreements.groupby(['team','formation','disagreement_type']).size().rename('count').reset_index().to_csv(out/'disagreements_cross_tab.csv',index=False)
    old_slots=pd.read_csv(ROOT/'analysis/recovered/FPL_MANAGER_XI_ROLE_TEST_2025_26/starter_roles_2025_26.csv')
    check=audit.merge(old_slots[['fixture_uuid','team_id','player_uuid','role']],on=['fixture_uuid','team_id','player_uuid'],validate='one_to_one')
    assert len(check)==8360
    assert (check.slot_role==check.role.map(canonical)).all(), 'Structural template differs from recovered slots'
    assert len(disagreements)==1052, 'Recovered disagreement population changed'
    baseline=pd.read_csv(a.baseline).reset_index(drop=True)
    assert not baseline.duplicated(['fixture_uuid','player_uuid']).any()
    if a.cutoffs:
        cutoff_map={int(r.gw):pd.to_datetime(r.cutoff,utc=True) for r in pd.read_csv(a.cutoffs).itertuples()}
        cutoff_source='supplied_deadlines'
    else:
        # Use all GW fixtures, not just the selected cohort; do not infer from outcomes.
        cutoff_map={gw:min(v['kickoff'] for v in fixture_lookup.values() if v['gw']==gw)-pd.Timedelta(minutes=90) for gw in range(1,39)}
        cutoff_source='first_fixture_minus_90_minutes_proxy'
    # Identify exactly where the legacy GW-only history rule differs from strict
    # historical effective availability; do not silently rewrite its predictions.
    legacy_history_audit=[]
    past=obs[['fixture_uuid','gw','team_id','kickoff_at']].drop_duplicates().copy()
    past['known_at']=pd.to_datetime(past.kickoff_at,utc=True)+pd.Timedelta(hours=3)
    for (gw,team),g in baseline.groupby(['gw','team_id']):
        prior=past[past.team_id==team];cutoff=cutoff_map[int(gw)]
        late=prior[(prior.gw<gw)&(prior.known_at>=cutoff)]
        omitted=prior[(prior.gw>=gw)&(prior.known_at<cutoff)]
        if len(late) or len(omitted):
            legacy_history_audit.append({'gw':int(gw),'team_id':int(team),'not_yet_known_but_lower_gw':late.fixture_uuid.tolist(),
                                         'already_known_but_equal_or_higher_gw':omitted.fixture_uuid.tolist()})
    write_json(out/'legacy_gw_cutoff_audit.json',legacy_history_audit)
    cache={};features=[]
    actual_roles={(r.fixture_uuid,r.player_uuid):r for r in audit.itertuples()}
    for r in baseline.itertuples():
        cutoff=cutoff_map[int(r.gw)];key=(int(r.team_id),int(r.gw))
        if key not in cache:
            cache[key]={speed:history.state(r.team_id,cutoff,half) for speed,half in [('fast',3),('slow',10)]}
        states=cache[key];record={'cutoff':cutoff.isoformat(),'cutoff_source':cutoff_source,'team':teams[int(r.team_id)],
                               'player':player_names.get(str(r.player_uuid),str(r.player_uuid)),
                               'base_logit':float(logit(np.clip(r.p_start_v2,1e-6,1-1e-6)))}
        for speed in ('fast','slow'):
            allstates,capacities,games=states[speed];state=allstates.get(str(r.player_uuid),{})
            summary=summarize_state(state,capacities)
            for f,v in summary.items():
                name=f'{f}_{speed}' if f.startswith('role_') else f
                record[name]=v
            for field in ('q','H'):
                values=state.get(field,{})
                for role in ROLES: record[f'{field}_{role}_{speed}']=values.get(role,0.)
            record[f'capacities_{speed}']=json.dumps(capacities,sort_keys=True,separators=(',',':'))
            if speed=='slow':
                q=state.get('q',{})
                record['expected_role']=max(sorted(q),key=q.get) if q else 'UNKNOWN'
                record['role_started_last_gw']=float(bool(games and any(p['player_uuid']==str(r.player_uuid) and p['started'] for p in games[-1]['players'])))
                record['max_history_known_at']=games[-1]['known_at'].isoformat() if games else ''
                assert not games or games[-1]['known_at']<cutoff
        actual=actual_roles.get((r.fixture_uuid,str(r.player_uuid)))
        record['actual_role_posthoc']=actual.final_role if actual else 'UNOBSERVED_BENCH'
        record['target_role_case_posthoc']=('disagreement' if actual.disagreement else 'agreement') if actual else 'unobserved_bench'
        record['outcome_known_at']=(fixture_lookup[r.fixture_uuid]['kickoff']+pd.Timedelta(hours=3)).isoformat()
        features.append(record)
    frame=pd.concat([baseline,pd.DataFrame(features)],axis=1)
    frame['baseline_p_start']=frame.p_start_v2;frame['baseline_xmins']=frame.expected_minutes_v2
    frame['actual_start']=frame.y;frame['actual_minutes']=frame.minutes
    test=frame.gw.between(22,38)
    training_cutoff=min(cutoff_map[g] for g in range(22,39))
    train=frame.gw.between(6,21)&(pd.to_datetime(frame.outcome_known_at,utc=True)<training_cutoff)
    frame['evaluation_partition']=np.where(test,'frozen_oos',np.where(train,'development_in_sample','excluded_from_fit'))
    assert not (train&test).any()
    assert not any('posthoc' in x for x in BASE_FEATURES+ROLE_FEATURES)
    model_specs={'calibration':BASE_FEATURES,'role_aware':BASE_FEATURES+ROLE_FEATURES,
                 'q_only':BASE_FEATURES+[x for x in ROLE_FEATURES if '_h_' not in x],
                 'h_only':BASE_FEATURES+[x for x in ROLE_FEATURES if '_h_' in x]}
    models={}
    for name,columns in model_specs.items():
        model=make_pipeline(StandardScaler(),LogisticRegression(C=1.,max_iter=2000,solver='lbfgs',random_state=0))
        model.fit(frame.loc[train,columns],frame.loc[train,'y'])
        p=normalize_eleven(frame,model.predict_proba(frame[columns])[:,1])
        frame[f'{name}_p_start']=p
        frame[f'{name}_xmins']=p*frame.start_minutes_mean+(1-p)*frame.p_cameo_given_bench*frame.cameo_minutes_mean
        models[name]={'features':columns,'coefficients':model[-1].coef_[0].tolist(),'intercept':float(model[-1].intercept_[0]),
                      'scaler_mean':model[0].mean_.tolist(),'scaler_scale':model[0].scale_.tolist()}
    frame['role_information_change']=np.abs(frame.role_aware_p_start-frame.calibration_p_start)
    holdout=frame.loc[test].copy()
    write_prediction_csv(frame,out/'all_feature_predictions.csv.gz')
    write_prediction_csv(holdout,out/'role_augmented_holdout_predictions.csv.gz')
    variants=['baseline',*model_specs]
    overall={v:score(holdout,v) for v in variants}
    for col in ['gw','team','expected_role','actual_role_posthoc','target_role_case_posthoc']:
        rows=[]
        for value,g in holdout.groupby(col,sort=True):
            for v in variants: rows.append({col:value,'variant':v,**score(g,v)})
        pd.DataFrame(rows).to_csv(out/f'metrics_by_{col}.csv',index=False)
    for label,selector in [('prior_disagreement',holdout.history_disagreement_share>0),
                           ('no_prior_disagreement',holdout.history_disagreement_share==0),
                           ('role_change_at_least_5pp',holdout.role_information_change>=.05),
                           ('role_change_below_5pp',holdout.role_information_change<.05)]:
        g=holdout.loc[selector]
        overall[label]={v:score(g,v) for v in variants} if len(g) else {}
    # Paired block bootstrap at GW level (17 blocks), preserving within-GW
    # dependence. Exploratory uncertainty, not a multi-comparison significance test.
    loss=lambda p,x:np.column_stack(((p-holdout.y)**2,
             -holdout.y*np.log(np.clip(p,1e-9,1-1e-9))-(1-holdout.y)*np.log(np.clip(1-p,1e-9,1)),
             abs(x-holdout.minutes),(x-holdout.minutes)**2))
    base_loss=loss(holdout.baseline_p_start,holdout.baseline_xmins)
    role_loss=loss(holdout.role_aware_p_start,holdout.role_aware_xmins)
    blocks=[]
    for _,idx in holdout.reset_index(drop=True).groupby('gw').indices.items():
        blocks.append((base_loss[idx].sum(axis=0),role_loss[idx].sum(axis=0),len(idx)))
    rng=np.random.default_rng(20261002);draws=[]
    for _ in range(2000):
        sampled=[blocks[i] for i in rng.integers(0,len(blocks),len(blocks))]
        denominator=sum(b[2] for b in sampled)
        b=sum(v[0] for v in sampled)/denominator;r=sum(v[1] for v in sampled)/denominator
        b[3]=np.sqrt(b[3]);r[3]=np.sqrt(r[3]);draws.append(r-b)
    write_json(out/'paired_gw_bootstrap.json',{'seed':20261002,'draws':2000,'blocks':len(blocks),
              'delta_role_minus_baseline_95_percentile_intervals':{metric:np.quantile(np.array(draws)[:,i],[.025,.975]).tolist() for i,metric in enumerate(['brier','log_loss','xmins_mae','xmins_rmse'])}})
    reference=json.loads((ROOT/'analysis/recovered/FPL_MANAGER_XI_ROLE_TEST_2025_26/manager_xi_holdout_metrics.json').read_text())
    write_json(out/'models.json',models)
    write_json(out/'metrics.json',overall)
    write_json(out/'audit_summary.json',{'starters':len(audit),'outfield_disagreements':len(disagreements),
               'outfield_disagreement_percent':100*len(disagreements)/len(non_gk),
               'missing_starter_coordinates':int(audit.average_position_missing.sum()),
               'final_overrides':int((audit.final_role!=audit.slot_role).sum()),
               'source_core_start_discrepancies':label_differences,'old_reference_unreproduced':reference,
               'training_rows':int(train.sum()),'holdout_rows':int(test.sum()),'training_cutoff':training_cutoff.isoformat(),
               'cutoff_source':cutoff_source,'availability':'kickoff + 3h historical effective-availability proxy, not observed publication time',
               'scope':'2025/26 PL roles only; baseline remains legacy GW-filtered comparator',
               'fit_protocol':'fixed logistic C=1, standardized; GW6-21 labels known before earliest holdout cutoff; frozen GW22-38; no tuning',
               'minute_protocol':'baseline conditional duration/cameo terms unchanged; replace only P(start)',
               'classifier_version':'formation-first-v1'})
    input_paths += [Path(a.db),Path(a.baseline)]
    if a.cutoffs: input_paths.append(Path(a.cutoffs))
    code_paths=[Path(__file__),ROOT/'src/fpl_v1_1_model/role_classifier.py',ROOT/'src/fpl_v1_1_model/role_history.py',ROOT/'scripts/v1_1_ingest_fpl_core_detailed_roles.py',
                ROOT/'scripts/reproduce_pstart_v2_fixture_minutes.py',ROOT/'src/fpl_v1_1_model/minutes.py']
    write_json(out/'manifest.json',{'inputs':[{ 'path':str(p.relative_to(ROOT)) if p.is_relative_to(ROOT) else p.name,'sha256':sha(p)} for p in input_paths],
                                  'code':[{ 'path':str(p.relative_to(ROOT)),'sha256':sha(p)} for p in code_paths],
                                  'outputs':[{ 'path':p.name,'sha256':sha(p)} for p in sorted(out.iterdir()) if p.name!='manifest.json'],
                                  'python':sys.version,'numpy':np.__version__,'pandas':pd.__version__,
                                  'scipy':version('scipy'),'scikit_learn':version('scikit-learn'),
                                  'cutoffs':{str(k):v.isoformat() for k,v in cutoff_map.items()}})
    print(json.dumps({'audit':len(disagreements),'overall':{v:overall[v] for v in variants}},indent=2))


if __name__=='__main__': main()

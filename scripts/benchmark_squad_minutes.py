#!/usr/bin/env python3
"""Train/choose on GW6-15/16-21; reused GW22-38 is diagnostic, not fresh OOS.

Factorize P(sub|not start)=P(squad|not start)*P(sub|confirmed bench).
Absence from complete lineups is not an injury diagnosis. No target roster is
ever a prediction feature. Existing role/minutes artifacts remain immutable.
"""
import argparse
from pathlib import Path
import sqlite3
import sys
import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import make_pipeline

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from fpl_v1_1_model.squad_history import SquadHistory,squad_label,unknown_state,SQUAD_FEATURES
from fpl_v1_1_model.minutes_decomposition import component_inputs,fit_components,compose_expected_minutes
from build_reproducible_role_benchmark import BASE_FEATURES,ROLE_FEATURES,normalize_eleven,score,write_json,write_prediction_csv,sha


def serialize(model,columns):
    return {'features':list(columns),'coefficients':model[-1].coef_[0].tolist(),'intercept':float(model[-1].intercept_[0]),
            'scaler_mean':model[0].mean_.tolist(),'scaler_scale':model[0].scale_.tolist()}


def build_history(con,raw,classified):
    obs=pd.read_sql_query("SELECT player_uuid,fixture_uuid,team_id,started,minutes,kickoff_at FROM player_fixture_observations WHERE season='2025-26' AND is_final=1",con)
    assert not obs.duplicated(['fixture_uuid','player_uuid']).any()
    mapping={str(k):str(v) for k,v in con.execute("SELECT external_id,player_uuid FROM player_id_mapping WHERE season='2025-26' AND id_namespace='fpl_element'")}
    lines=pd.concat([pd.read_csv(raw/f'GW{g}/lineups.csv') for g in range(1,39)],ignore_index=True)
    lines['player_uuid']=lines.player_id.astype(str).map(mapping)
    assert lines.player_uuid.notna().all()
    fixture_map=classified[['match_id','player_uuid','team_id','fixture_uuid']].drop_duplicates()
    group_map={}
    for key,g in lines.groupby(['match_id','team_side']):
        hit=g[['match_id','player_uuid']].merge(fixture_map,on=['match_id','player_uuid'])
        assert hit.team_id.nunique()==1 and hit.fixture_uuid.nunique()==1
        group_map[key]=(int(hit.team_id.iloc[0]),hit.fixture_uuid.iloc[0])
    obs_groups={(str(f),int(t)):g for (f,t),g in obs.groupby(['fixture_uuid','team_id'])}
    labels={};coverage=[];history=SquadHistory()
    for key,g in sorted(lines.groupby(['match_id','team_side']),key=lambda x:x[0]):
        team,fixture=group_map[key];actual=obs_groups[(fixture,team)]
        listed=set(g.player_uuid);planned=set(g.loc[g.is_starting.astype(str).str.lower()=='true','player_uuid'])
        core={r.player_uuid:r for r in actual.itertuples()}
        missing_appearances=[r.player_uuid for r in actual.itertuples() if r.minutes>0 and r.player_uuid not in listed]
        withdrawn=[p for p in planned if p in core and not core[p].started and core[p].minutes==0]
        complete=len(g)==20 and not missing_appearances and not withdrawn
        coverage.append({'match_id':key[0],'team_side':key[1],'team_id':team,'fixture_uuid':fixture,
                         'listed_count':len(g),'complete_for_negative_labels':complete,
                         'withdrawn_or_start_discrepancy_count':len(withdrawn),'appearances_missing_from_source':len(missing_appearances)})
        players={}
        for r in actual.itertuples():
            label=squad_label(r.player_uuid in listed,bool(r.started),float(r.minutes),complete,r.player_uuid in withdrawn)
            p={'squad':label,'started':bool(r.started),'minutes':float(r.minutes)}
            players[r.player_uuid]=p;labels[(fixture,r.player_uuid)]=p
        ko=pd.to_datetime(actual.kickoff_at.iloc[0],utc=True)
        history.add_game(team,ko+pd.Timedelta(hours=3),fixture,players)
    return history,labels,pd.DataFrame(coverage)


def evaluate_fit(frame,train,test,refit_start):
    cutoff=pd.to_datetime(frame.loc[test,'cutoff'],utc=True).min()
    assert (pd.to_datetime(frame.loc[train,'outcome_known_at'],utc=True)<cutoff).all()
    assert not (train&test).any()
    X=component_inputs(frame)
    X=pd.concat([X,frame[SQUAD_FEATURES]],axis=1)
    known=frame.squad_label_posthoc.notna()
    nonstarts=train&(frame.y==0)&known
    bench=nonstarts&(frame.squad_label_posthoc==1)
    squad=make_pipeline(StandardScaler(),LogisticRegression(C=.3,max_iter=2000,random_state=0))
    sub=make_pipeline(StandardScaler(),LogisticRegression(C=.3,max_iter=2000,random_state=0))
    squad.fit(X.loc[nonstarts],frame.loc[nonstarts,'squad_label_posthoc'].astype(int))
    sub.fit(X.loc[bench],(frame.loc[bench,'minutes']>0).astype(int))
    p_squad=squad.predict_proba(X)[:,1];p_sub_bench=sub.predict_proba(X)[:,1]
    durations,duration_models,counts=fit_components(frame,train)
    if refit_start:
        columns=BASE_FEATURES+ROLE_FEATURES
        start=make_pipeline(StandardScaler(),LogisticRegression(C=1.,max_iter=2000,random_state=0))
        start.fit(frame.loc[train,columns],frame.loc[train,'y'])
        p=normalize_eleven(frame,start.predict_proba(frame[columns])[:,1])
        start_model=serialize(start,columns)
    else:p=frame.role_aware_p_start.to_numpy();start_model={'reference':'unchanged role-aware-v1 frozen GW6-21'}
    f=frame.loc[test].copy();idx=np.flatnonzero(test)
    p=p[idx];s=p_squad[idx];b=p_sub_bench[idx]
    f['p_squad_given_not_start']=s;f['p_sub_given_bench']=b
    f['p_sub_given_not_start_factorized']=s*b
    f['p_squad_unconditional']=p+(1-p)*s
    f['e_min_start_new']=durations['e_min_start'][idx];f['e_min_sub_new']=durations['e_min_sub'][idx]
    specs={'control':(f.start_minutes_mean,f.p_cameo_given_bench,f.cameo_minutes_mean),
           'factorized_sub':(f.start_minutes_mean,s*b,f.cameo_minutes_mean),
           'factorized_full':(f.e_min_start_new,s*b,f.e_min_sub_new)}
    for name,terms in specs.items():
        f[name+'_p_start']=p;f[name+'_xmins']=compose_expected_minutes(p,*terms)
    result={name:score(f,name) for name in specs}
    serialized={'squad_given_nonstart':serialize(squad,X.columns),'sub_given_bench':serialize(sub,X.columns),
                'durations':duration_models,'start':start_model}
    protocol={'train_rows':int(train.sum()),'validation_rows':len(f),'training_cutoff':cutoff.isoformat(),
              'known_nonstart_training_labels':int(nonstarts.sum()),'confirmed_bench_training_labels':int(bench.sum()),'duration_counts':counts}
    return f,result,serialized,protocol


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--db',required=True)
    ap.add_argument('--raw-root',default=str(ROOT/'data_v1_1/raw/fpl-core-2025-26'))
    ap.add_argument('--features',default=str(ROOT/'analysis/results/reproducible-role-v1/all_feature_predictions.csv.gz'))
    ap.add_argument('--out',default=str(ROOT/'analysis/results/squad-minutes-v1'))
    a=ap.parse_args();out=Path(a.out);out.mkdir(parents=True,exist_ok=True)
    con=sqlite3.connect(f'file:{Path(a.db).resolve()}?mode=ro',uri=True)
    classified_path=ROOT/'analysis/results/reproducible-role-v1/classified_starters.csv'
    history,labels,coverage=build_history(con,Path(a.raw_root),pd.read_csv(classified_path))
    coverage.to_csv(out/'source_squad_coverage.csv',index=False)
    frame=pd.read_csv(a.features);cache={};rows=[]
    for r in frame.itertuples():
        cutoff=pd.to_datetime(r.cutoff,utc=True);key=(int(r.team_id),r.cutoff)
        if key not in cache:cache[key]=history.state(r.team_id,cutoff)
        state,known_at=cache[key]
        record=state.get(r.player_uuid,unknown_state()).copy()
        record['max_squad_history_known_at']=known_at.isoformat() if known_at else ''
        assert known_at is None or known_at<cutoff
        record['squad_label_posthoc']=labels[(r.fixture_uuid,r.player_uuid)]['squad']
        rows.append(record)
    frame=pd.concat([frame,pd.DataFrame(rows)],axis=1)
    dev_test=frame.gw.between(16,21)
    dev_cutoff=pd.to_datetime(frame.loc[dev_test,'cutoff'],utc=True).min()
    dev_train=frame.gw.between(6,15)&(pd.to_datetime(frame.outcome_known_at,utc=True)<dev_cutoff)
    dev,dev_metrics,dev_models,dev_protocol=evaluate_fit(frame,dev_train,dev_test,True)
    # Predeclared objective: minutes MAE; stable control wins exact ties. No
    # candidate is selected using the already seen GW22-38 diagnostics.
    chosen=min(['control','factorized_sub','factorized_full'],key=lambda name:dev_metrics[name]['xmins_mae'])
    final_test=frame.gw.between(22,38)
    final_cutoff=pd.to_datetime(frame.loc[final_test,'cutoff'],utc=True).min()
    final_train=frame.gw.between(6,21)&(pd.to_datetime(frame.outcome_known_at,utc=True)<final_cutoff)
    diagnostic,metrics,models,protocol=evaluate_fit(frame,final_train,final_test,False)
    write_prediction_csv(dev,out/'development_validation_predictions.csv.gz')
    write_prediction_csv(diagnostic,out/'reused_holdout_diagnostic_predictions.csv.gz')
    for col in ['gw','team','target_role_case_posthoc','expected_role']:
        records=[]
        for label,g in diagnostic.groupby(col):
            for name in ['control','factorized_sub','factorized_full']:records.append({col:label,'variant':name,**score(g,name)})
        pd.DataFrame(records).to_csv(out/f'metrics_by_{col}.csv',index=False)
    write_json(out/'development_metrics.json',dev_metrics);write_json(out/'reused_holdout_metrics.json',metrics)
    write_json(out/'development_models.json',dev_models);write_json(out/'frozen_models.json',models)
    write_json(out/'protocol.json',{'development':dev_protocol,'frozen_fit':protocol,'selected_on_development_mae':chosen,
                'fixed_candidates':['control','factorized_sub','factorized_full'],'C_squad_and_bench':.3,'duration_alpha':20.,
                'negative_squad_labels':'only 20-player source lists without detected discrepancies',
                'labels':'not selected into observed matchday squad; never injury/medical unavailability',
                'holdout_status':'reused, previously inspected; diagnostic only, NOT fresh independent OOS',
                'availability':'historical cutoff/completion proxies inherited; no real ingestion timestamp certification',
                'deployment':'experimental; no app/UI switch or Match Importance changes'})
    write_json(out/'source_audit.json',{'team_fixtures':len(coverage),'complete_negative_label_fixtures':int(coverage.complete_for_negative_labels.sum()),
               'starter_only_fixtures':int((coverage.listed_count==11).sum()),'feature_rows':len(frame),
               'known_squad_labels':int(frame.squad_label_posthoc.notna().sum()),'unknown_squad_labels':int(frame.squad_label_posthoc.isna().sum())})
    inputs=[Path(a.db),Path(a.features),classified_path,*sorted(Path(a.raw_root).glob('GW*/lineups.csv'))]
    code=[Path(__file__),ROOT/'src/fpl_v1_1_model/squad_history.py',ROOT/'src/fpl_v1_1_model/minutes_decomposition.py',ROOT/'scripts/build_reproducible_role_benchmark.py']
    write_json(out/'manifest.json',{'inputs':[{'path':str(p.relative_to(ROOT)) if p.is_relative_to(ROOT) else p.name,'sha256':sha(p)} for p in inputs],
               'code':[{'path':str(p.relative_to(ROOT)),'sha256':sha(p)} for p in code],
               'outputs':[{'path':p.name,'sha256':sha(p)} for p in sorted(out.iterdir()) if p.name!='manifest.json' and not p.name.endswith('.tmp')]})
    print({'development':dev_metrics,'chosen':chosen,'reused_holdout_diagnostic':metrics})


if __name__=='__main__':main()

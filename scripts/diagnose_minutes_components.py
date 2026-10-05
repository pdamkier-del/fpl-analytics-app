"""Frozen component diagnostic and development-only composition selection.

No estimator refits. Compare all 27 fixed combinations of existing base/role/
workload conditional forecasts with v4 start probabilities held fixed.
"""
import hashlib
import itertools
import json
from pathlib import Path
import numpy as np
import pandas as pd
from fpl_v1_1_model.paired_joint import read_frozen_table

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'analysis/results/minutes-components-20261005-v1'
SOURCE=ROOT/'analysis/results/workload-recovered-minutes-v4'
CHOICES={
    'S':{'base':'start_minutes_mean','role':'role_start','workload':'workload_start'},
    'Q':{'base':'p_cameo_given_bench','role':'role_sub_probability','workload':'workload_sub_probability'},
    'C':{'base':'cameo_minutes_mean','role':'role_sub_duration','workload':'workload_sub_duration'}}

def predict(f,combo):
    p=f.workload_start_p_start.to_numpy()
    s,q,c=[f[CHOICES[k][v]].to_numpy() for k,v in zip(['S','Q','C'],combo)]
    return p*s+(1-p)*q*c

def score(y,p):
    e=p-np.asarray(y)
    return dict(mae=float(np.abs(e).mean()),rmse=float(np.sqrt(np.mean(e**2))),bias=float(e.mean()))

def main():
    if OUT.exists():raise FileExistsError(OUT)
    OUT.mkdir(parents=True)
    protocol=dict(start='frozen selected v4 workload_start P(start)',candidates=27,
        choices=CHOICES,selection='lowest development GW16-21 RMSE; prefer baseline on ties within 1e-10',
        fitting='none; existing development models trained GW6-15; final models trained GW6-21',
        final_evaluation='same 144 fixtures as point diagnostic; reused GW22-38 only',
        deployment='experimental composition screen; no automatic model promotion',
        diagnostic='actual-substitute signed error decomposition is descriptive, not causal attribution')
    (OUT/'protocol.json').write_text(json.dumps(protocol,indent=2)+'\n')
    devpath=SOURCE/'development_predictions.csv.gz'
    testpath=SOURCE/'reused_holdout_diagnostic_predictions.csv.gz'
    dev=pd.read_csv(devpath)
    assert dev.gw.between(16,21).all()
    combos=list(itertools.product(['base','role','workload'],repeat=3))
    records=[]
    for combo in combos:
        records.append(dict(S=combo[0],Q=combo[1],C=combo[2],**score(dev.minutes,predict(dev,combo))))
    ranked=sorted(records,key=lambda x:x['rmse'])
    base=records[0]
    chosen=base if base['rmse']<=ranked[0]['rmse']+1e-10 else ranked[0]
    combo=tuple(chosen[k] for k in ['S','Q','C'])
    selection=dict(selected=chosen,baseline=base,selection_period='GW16-21',no_test_metrics_used=True)
    # Selection is saved before evaluation data is read.
    (OUT/'selection.json').write_text(json.dumps(selection,indent=2)+'\n')
    pd.DataFrame(records).to_csv(OUT/'development_combinations.csv',index=False)
    test=pd.read_csv(testpath)
    inputs=read_frozen_table(ROOT/'analysis/results/deadline-joint-inputs-v1','inputs')
    keys=['fixture_uuid','player_uuid','gw','team_id']
    test=test.merge(inputs[keys],on=keys,validate='one_to_one')
    assert len(test)==11794 and test.fixture_uuid.nunique()==144
    assert np.allclose(predict(test,('base','base','base')),test.workload_start_xmins,rtol=0,atol=1e-10)
    slices=[];conditional=[]
    for label,f in [('development',dev),('reused_diagnostic',test)]:
        p=f.workload_start_p_start.to_numpy();s=f.start_minutes_mean.to_numpy()
        q=f.p_cameo_given_bench.to_numpy();c=f.cameo_minutes_mean.to_numpy()
        y=f.y.to_numpy();m=f.minutes.to_numpy();z=((y==0)&(m>0)).astype(int)
        terms=dict(start_selection=(p-y)*(s-q*c),starter_duration=y*(s-m),
                   sub_appearance=(1-y)*(q-z)*c,sub_duration=(1-y)*z*(c-m))
        assert np.allclose(sum(terms.values()),f.workload_start_xmins-m,rtol=0,atol=1e-10)
        for case,mask in [('all',np.ones(len(f),dtype=bool)),('starter',y==1),('substitute',z==1),('did_not_play',m==0)]:
            slices.append(dict(period=label,case=case,n=int(mask.sum()),
                **{'signed_'+k:float(v[mask].mean()) for k,v in terms.items()},
                **score(m[mask],f.workload_start_xmins.to_numpy()[mask])))
        for family in ['base','role','workload']:
            sm=f[CHOICES['S'][family]];qm=f[CHOICES['Q'][family]];cm=f[CHOICES['C'][family]]
            conditional.append(dict(period=label,family=family,
                starter_duration_mae=float(abs(sm[y==1]-m[y==1]).mean()),
                substitute_duration_mae=float(abs(cm[z==1]-m[z==1]).mean()),
                sub_appearance_brier=float(((qm[y==0]-z[y==0])**2).mean())))
    pd.DataFrame(slices).to_csv(OUT/'signed_error_components.csv',index=False)
    pd.DataFrame(conditional).to_csv(OUT/'conditional_component_metrics.csv',index=False)
    selected=predict(test,combo)
    group=[]
    for col in ['pos','expected_role']:
        for name,g in test.groupby(col):
            group.append(dict(dimension=col,group=name,n=len(g),baseline_mae=score(g.minutes,g.workload_start_xmins)['mae'],
                candidate_mae=score(g.minutes,predict(g,combo))['mae']))
    pd.DataFrame(group).to_csv(OUT/'selected_candidate_groups.csv',index=False)
    policy=json.loads((ROOT/'analysis/results/season-2025-26-mechanics-v1/verification.json').read_text())['policy_checks']
    for item in policy:assert hashlib.sha256((ROOT/item['path']).read_bytes()).hexdigest()==item['sha256']
    result=dict(development=selection,reused_diagnostic=dict(rows=len(test),fixtures=144,
        baseline=score(test.minutes,test.workload_start_xmins),candidate=score(test.minutes,selected)),
        role_coverage=dict(development_unknown=int(dev.expected_role.eq('UNKNOWN').sum()),development_rows=len(dev),
                           diagnostic_unknown=int(test.expected_role.eq('UNKNOWN').sum()),diagnostic_rows=len(test)),
        no_estimators_refit=True,model_promoted=False,policy_unchanged=True,
        checks=dict(signed_error_reconstruction=True,frozen_v4_composition_match=True,exact_paired_cohort=True),
        classification='development_composition_screen_plus_reused_diagnostic',
        sources=[dict(path=str(p.relative_to(ROOT)),sha256=hashlib.sha256(p.read_bytes()).hexdigest()) for p in [devpath,testpath,Path(__file__)]],
        outputs=[dict(path=p.name,sha256=hashlib.sha256(p.read_bytes()).hexdigest()) for p in sorted(OUT.iterdir())])
    (OUT/'manifest.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result,indent=2))

if __name__=='__main__':main()

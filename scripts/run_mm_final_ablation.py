#!/usr/bin/env python3
"""Final MM ablation: isolate workload/official-role/MI contributions."""
from __future__ import annotations
import json,sys
from pathlib import Path
import numpy as np
import pandas as pd
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'));sys.path.insert(0,str(ROOT/'scripts'))

from run_mm_unified_official_roles import SOURCE,build_role_games,add_importance,role_features,full_mm
from run_v4_performance_rating_experiment import build_perf_ledger,add_features as add_perf_features
from run_v4_three_state_sequence_experiment import add_sequence_features,metrics,write_json

OUT=ROOT/'analysis/results/mm-final-ablation-20261006-v1'

def prep(frame):
    frame=add_sequence_features(frame.reset_index(drop=True))
    return add_perf_features(frame,build_perf_ledger())

def run_arm(frame,games,qs,hs,train,mask):
    f=role_features(frame.copy(),games,qs,hs)
    p,q,sub,xm,_=full_mm(f,train)
    return metrics(f,mask,p,q,xm)

def main():
    OUT.mkdir(parents=True,exist_ok=True)
    raw=prep(pd.read_csv(SOURCE))
    games,_,_=build_role_games();games=add_importance(games)
    known=pd.to_datetime(raw.outcome_known_at,utc=True)
    dev=raw.gw.between(16,21).to_numpy();dcut=pd.to_datetime(raw.loc[dev,'cutoff'],utc=True).min()
    dtr=(raw.gw.between(6,15)&(known<dcut)).to_numpy()
    test=raw.gw.between(22,38).to_numpy();tcut=pd.to_datetime(raw.loc[test,'cutoff'],utc=True).min()
    ttr=(raw.gw.between(6,21)&(known<tcut)).to_numpy()

    variants={
      'source_pl_roles_fa_workload':None,
      'rebuilt_pl_only':{'comps':{'prem'},'q':0.0,'h':0.0},
      'pl_plus_europe':{'comps':{'prem','champions-league','europa-league','conference-league'},'q':0.0,'h':0.0},
      'pl_plus_domestic_cups':{'comps':{'prem','fa-cup','efl-cup'},'q':0.0,'h':0.0},
      'all_official_no_mi':{'comps':None,'q':0.0,'h':0.0},
      'all_official_mi':{'comps':None,'q':0.1,'h':0.4},
    }
    rows=[];detail={}
    for name,spec in variants.items():
        if spec is None:
            fd=raw.copy();pdv,qd,sd,xd,_=full_mm(fd,dtr);dmet=metrics(fd,dev,pdv,qd,xd)
            ft=raw.copy();pt,qt,st,xt,_=full_mm(ft,ttr);tmet=metrics(ft,test,pt,qt,xt)
            n_games=None
        else:
            gg=games if spec['comps'] is None else [g for g in games if g['competition'] in spec['comps']]
            fd=role_features(raw.copy(),gg,spec['q'],spec['h']);pdv,qd,sd,xd,_=full_mm(fd,dtr);dmet=metrics(fd,dev,pdv,qd,xd)
            ft=role_features(raw.copy(),gg,spec['q'],spec['h']);pt,qt,st,xt,_=full_mm(ft,ttr);tmet=metrics(ft,test,pt,qt,xt)
            n_games=len(gg)
        rows.append({'arm':name,'role_team_games':n_games,
          'dev_state_log_loss':dmet['state_log_loss'],'dev_xmins_mae':dmet['xmins_mae'],'dev_xmins_rmse':dmet['xmins_rmse'],
          'test_state_log_loss':tmet['state_log_loss'],'test_xmins_mae':tmet['xmins_mae'],'test_xmins_rmse':tmet['xmins_rmse'],
          'test_xmins_bias':tmet['xmins_bias']})
        detail[name]={'development':dmet,'reused_diagnostic':tmet}
    out=pd.DataFrame(rows)
    base=out[out.arm=='source_pl_roles_fa_workload'].iloc[0]
    for col in ['dev_state_log_loss','dev_xmins_mae','dev_xmins_rmse','test_state_log_loss','test_xmins_mae','test_xmins_rmse']:
        out['delta_'+col]=out[col]-float(base[col])
    out.to_csv(OUT/'ablation.csv',index=False)

    # Architecture choice is development-first with explicit structural requirement:
    # among official-role variants, choose lowest dev RMSE, then dev MAE.
    official=out[out.arm.isin(['pl_plus_europe','pl_plus_domestic_cups','all_official_no_mi','all_official_mi'])].copy()
    choice=official.sort_values(['dev_xmins_rmse','dev_xmins_mae','dev_state_log_loss']).iloc[0]
    result={'classification':'final MM structural ablation; GW22-38 reused diagnostic only',
      'arms':out.to_dict(orient='records'),'details':detail,
      'development_selected_official_role_arm':str(choice.arm),
      'note':'Selection does not use GW22-38. Source PL-role arm is comparator, not structurally eligible final MM because official non-PL role evidence is omitted.'}
    write_json(OUT/'result.json',result);print(json.dumps(result,indent=2))

if __name__=='__main__':main()

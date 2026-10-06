#!/usr/bin/env python3
"""MM v2 experiment: global XI assignment, optionally with external ratings.

Without --ratings:
  tests only the new coherent role-slot assignment on top of the locked MM base.

With --ratings:
  adds cutoff-safe FotMob/SofaScore rating features and lets performance alter
  player-role assignment scores.

The experiment never collapses P(start) to 0/1.  The MAP XI is used only as a
structured explanatory/competition feature, followed by a residual P(start)
correction and exact-11 renormalization.

Selection: GW6-15 train, GW16-21 development. GW22-38 remains reused diagnostic.
"""
from __future__ import annotations
import argparse,json,sys
from pathlib import Path
import numpy as np
import pandas as pd
from scipy.optimize import minimize
from scipy.special import expit,logit

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'));sys.path.insert(0,str(ROOT/'scripts'))

from build_reproducible_role_benchmark import normalize_eleven
from fpl_v1_1_model.role_classifier import ROLES
from fpl_v1_1_model.xi_assignment import optimize_best_formation
from fpl_v1_1_model.rating_history import build_rating_features
from run_mm_unified_official_roles import SOURCE,full_mm
from run_v4_performance_rating_experiment import build_perf_ledger,add_features as add_perf_features
from run_v4_three_state_sequence_experiment import add_sequence_features,metrics,write_json,write_gzip_csv

OUT_DEFAULT=ROOT/'analysis/results/mm-v2-xi-rating-20261006-v1'
EPS=1e-7
ASSIGN_FEATURES=[
 'xi_selected_map','xi_assignment_score','xi_q_role','xi_hierarchy',
 'xi_score_margin','xi_role_competitors','xi_formation_score_gap'
]
RATING_FEATURES=[
 'rating_hist_n','rating_recent','rating_last','rating_trend',
 'rating_role_z','performance_score','rating_provider_matches'
]


def add_neutral_rating(frame):
    f=frame.copy()
    f['rating_hist_n']=0.;f['rating_recent']=0.;f['rating_last']=0.
    f['rating_trend']=0.;f['rating_role_z']=0.;f['performance_score']=.5
    f['rating_provider_matches']=0.
    return f


def _players_for_group(g,p):
    rows=[]
    for local,(idx,r) in enumerate(g.iterrows()):
        q={role:float(r.get(f'q_{role}_slow',0.0) or 0.0) for role in ROLES}
        h={role:float(r.get(f'H_{role}_slow',0.0) or 0.0) for role in ROLES}
        rows.append({
            'player_uuid':str(r.player_uuid),
            'base_p_start':float(p[idx]),
            'performance':float(r.performance_score),
            'q':q,'H':h,'_index':int(idx)
        })
    return rows


def add_xi_features(frame,p,performance_weight):
    f=frame.copy()
    for c in ASSIGN_FEATURES:f[c]=0.0
    f['xi_assigned_role']='UNKNOWN';f['xi_formation']='UNKNOWN'

    for _,idxs in f.groupby(['fixture_uuid','team_id'],sort=False).indices.items():
        idxs=np.asarray(idxs,dtype=int)
        g=f.iloc[idxs]
        players=_players_for_group(g,p)
        try:
            out=optimize_best_formation(
                players,
                q_weight=.55,h_weight=.85,
                performance_weight=float(performance_weight),
                base_weight=1.0,
                min_q=.005,
            )
        except RuntimeError:
            continue

        xi=out['xi']; selected={a.player_uuid:a for a in xi}
        alternatives=out['alternatives']
        fgap=float(alternatives[0]['score']-alternatives[1]['score']) if len(alternatives)>1 else 0.0

        # Role-level score margins against best alternative player for same role.
        for global_i in idxs:
            pid=str(f.at[global_i,'player_uuid'])
            a=selected.get(pid)
            if a is None:
                continue
            f.at[global_i,'xi_selected_map']=1.0
            f.at[global_i,'xi_assignment_score']=a.score
            f.at[global_i,'xi_q_role']=a.q_role
            f.at[global_i,'xi_hierarchy']=a.hierarchy
            f.at[global_i,'xi_assigned_role']=a.role
            f.at[global_i,'xi_formation']=out['formation']
            f.at[global_i,'xi_formation_score_gap']=fgap

            role=a.role
            candidate_scores=[]
            for pp in players:
                if pp['player_uuid']==pid:continue
                q=float(pp['q'].get(role,0.0));h=float(pp['H'].get(role,0.0))
                if q<.005:continue
                # same scoring formula as optimizer
                from fpl_v1_1_model.xi_assignment import role_score
                candidate_scores.append(role_score(
                    q_role=q,hierarchy=h,performance=pp['performance'],
                    base_p_start=pp['base_p_start'],q_weight=.55,h_weight=.85,
                    performance_weight=float(performance_weight),base_weight=1.0))
            if candidate_scores:
                f.at[global_i,'xi_score_margin']=a.score-max(candidate_scores)
                f.at[global_i,'xi_role_competitors']=float(len(candidate_scores))

    return f


def fit_residual(frame,p0,train,features,l2):
    X=frame[features].to_numpy(float)
    # signed log-like assignment scores can contain large negative values; clip.
    X=np.clip(X,-50,50)
    mu=X[train].mean(0);sd=X[train].std(0);sd[sd<1e-8]=1.
    Z=(X-mu)/sd
    y=frame.y.to_numpy(float)
    off=logit(np.clip(p0,EPS,1-EPS))
    Xt=Z[train];yt=y[train];ot=off[train]
    def fg(b):
        z=ot+Xt@b;p=expit(z)
        loss=np.mean(np.logaddexp(0,z)-yt*z)+.5*l2*np.dot(b,b)/len(yt)
        grad=Xt.T@(p-yt)/len(yt)+l2*b/len(yt)
        return float(loss),grad
    res=minimize(lambda b:fg(b),np.zeros(len(features)),jac=True,method='L-BFGS-B')
    if not res.success:raise RuntimeError(res.message)
    raw=expit(off+Z@res.x)
    return normalize_eleven(frame,raw),{
        'features':features,'l2':float(l2),'coef':res.x.tolist(),
        'mean':mu.tolist(),'scale':sd.tolist()
    }


def compose(frame,p,q,sub):
    return p*frame.start_minutes_mean.to_numpy(float)+(1-p)*q*np.asarray(sub,float)


def evaluate(frame,train,val,performance_weight,with_ratings):
    p0,q,sub,x0,_=full_mm(frame.copy(),train)
    feat=add_xi_features(frame,p0,performance_weight)
    features=ASSIGN_FEATURES+(RATING_FEATURES if with_ratings else [])
    rows=[];models={};preds={}
    for l2 in (.5,2.,10.,40.):
        p,m=fit_residual(feat,p0,train,features,l2)
        x=compose(feat,p,q,sub)
        met=metrics(feat,val,p,q,x)
        rows.append({'l2':l2,**met})
        models[str(l2)]=m;preds[l2]=(p,x)
    base=metrics(feat,val,p0,q,x0)
    cand=pd.DataFrame(rows)
    for c in ['state_log_loss','state_brier','xmins_mae','xmins_rmse']:
        cand['delta_'+c]=cand[c]-base[c]
    cand=cand.sort_values(['state_log_loss','xmins_rmse','xmins_mae'])
    ok=cand[(cand.delta_xmins_rmse<=.05)&(cand.delta_xmins_mae<=.05)]
    selected=None
    if len(ok) and float(ok.iloc[0].state_log_loss)<base['state_log_loss']:
        selected=float(ok.iloc[0].l2)
    return feat,p0,q,sub,x0,base,cand,selected,models,preds


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--ratings',help='CSV rating ledger following MM v2 contract')
    ap.add_argument('--out',default=str(OUT_DEFAULT))
    a=ap.parse_args();out=Path(a.out);out.mkdir(parents=True,exist_ok=True)

    frame=add_sequence_features(pd.read_csv(SOURCE).reset_index(drop=True))
    frame=add_perf_features(frame,build_perf_ledger())
    if a.ratings:
        rating_ledger=pd.read_csv(a.ratings)
        frame=build_rating_features(frame,rating_ledger)
        performance_weight=.45;with_ratings=True
    else:
        frame=add_neutral_rating(frame)
        performance_weight=0.;with_ratings=False

    known=pd.to_datetime(frame.outcome_known_at,utc=True)
    dev=frame.gw.between(16,21).to_numpy()
    dcut=pd.to_datetime(frame.loc[dev,'cutoff'],utc=True).min()
    dtr=(frame.gw.between(6,15)&(known<dcut)).to_numpy()
    feat,p0,q,sub,x0,base,cand,selected,models,preds=evaluate(
        frame,dtr,dev,performance_weight,with_ratings)
    cand.to_csv(out/'development_candidates.csv',index=False)

    test=frame.gw.between(22,38).to_numpy()
    tcut=pd.to_datetime(frame.loc[test,'cutoff'],utc=True).min()
    ttr=(frame.gw.between(6,21)&(known<tcut)).to_numpy()

    pbase,qbase,subbase,xbase,_=full_mm(frame.copy(),ttr)
    ftest=add_xi_features(frame,pbase,performance_weight)
    features=ASSIGN_FEATURES+(RATING_FEATURES if with_ratings else [])
    if selected is None:
        pfinal=pbase.copy();model=None
    else:
        pfinal,model=fit_residual(ftest,pbase,ttr,features,selected)
    xfinal=compose(ftest,pfinal,qbase,subbase)

    base_test=metrics(ftest,test,pbase,qbase,xbase)
    final_test=metrics(ftest,test,pfinal,qbase,xfinal)
    uncertain=test&(pbase>=.2)&(pbase<=.8)
    base_u=metrics(ftest,uncertain,pbase,qbase,xbase)
    final_u=metrics(ftest,uncertain,pfinal,qbase,xfinal)

    pred=ftest.loc[test,['fixture_uuid','player_uuid','team_id','gw','team','player','pos',
                         'expected_role','xi_assigned_role','xi_formation','y','minutes']].copy()
    pred['base_p_start']=pbase[test];pred['v2_p_start']=pfinal[test]
    pred['base_xmins']=xbase[test];pred['v2_xmins']=xfinal[test]
    for c in ASSIGN_FEATURES+RATING_FEATURES:pred[c]=ftest.loc[test,c].to_numpy()
    write_gzip_csv(pred,out/'reused_diagnostic_predictions.csv.gz')

    result={
      'classification':'MM v2 development-selected role-slot assignment experiment; GW22-38 reused diagnostic',
      'ratings_used':bool(with_ratings),
      'rating_source':a.ratings if a.ratings else None,
      'performance_weight_in_assignment':performance_weight,
      'development_base':base,
      'development_candidates':cand.to_dict(orient='records'),
      'selected_l2':selected,
      'reused_diagnostic':{
        'base':base_test,'v2':final_test,
        'delta':{k:final_test[k]-base_test[k] for k in ['state_log_loss','state_brier','xmins_mae','xmins_rmse','xmins_bias']},
        'uncertain_base':base_u,'uncertain_v2':final_u,
        'uncertain_delta':{k:final_u[k]-base_u[k] for k in ['state_log_loss','state_brier','xmins_mae','xmins_rmse','xmins_bias']},
      },
      'rules':{
        'one_player_max_one_slot':True,'exactly_11_unique_map_xi':True,
        'multi_role_allowed_but_single_assignment':True,
        'probabilistic_pstart_preserved':True,
        'minutes_models_unchanged':True,
      },
      'promoted':False,
      'promotion_note':'Do not promote from reused diagnostic alone.'
    }
    write_json(out/'result.json',result)
    write_json(out/'model.json',{'residual':model})
    print(json.dumps(result,indent=2))

if __name__=='__main__':main()

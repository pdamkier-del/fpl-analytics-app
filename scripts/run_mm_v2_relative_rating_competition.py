#!/usr/bin/env python3
"""MM v2 experiment: bounded relative external ratings inside role competition.

This experiment preserves the locked MM, duration/sub models and the XI-only
experiment. External ratings are NOT fed as general player features. They only
modify player-role assignment scores relative to direct competitors for that
same role.

Selection is development-only (GW16-21). GW22-38 remains reused diagnostic.
"""
from __future__ import annotations
import argparse,json,sys
from pathlib import Path
import numpy as np
import pandas as pd

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'));sys.path.insert(0,str(ROOT/'scripts'))

from fpl_v1_1_model.role_classifier import ROLES
from fpl_v1_1_model.xi_assignment import optimize_best_formation,role_score
from fpl_v1_1_model.rating_history import build_rating_features
from run_mm_v2_xi_rating_experiment import (
    ASSIGN_FEATURES, fit_residual, compose
)
from run_mm_unified_official_roles import SOURCE,full_mm
from run_v4_performance_rating_experiment import build_perf_ledger,add_features as add_perf_features
from run_v4_three_state_sequence_experiment import add_sequence_features,metrics,write_json,write_gzip_csv

OUT_DEFAULT=ROOT/'analysis/results/mm-v2-relative-rating-competition-20261006-v1'

def _safe(x,default=0.0):
    try:
        z=float(x)
        return z if np.isfinite(z) else default
    except Exception:
        return default

def _role_maps(row):
    q={role:_safe(row.get(f'q_{role}_slow',0.0)) for role in ROLES}
    h={role:_safe(row.get(f'H_{role}_slow',0.0)) for role in ROLES}
    return q,h

def _base_slot_score(q,h,p):
    return role_score(
        q_role=q,hierarchy=h,performance=.5,base_p_start=p,
        q_weight=.55,h_weight=.85,performance_weight=0.0,base_weight=1.0
    )

def build_players_with_relative_form(g,p,gamma,rel_w,self_w,trend_w,min_q=.005):
    """Build one team-fixture player list with bounded role-specific rating deltas."""
    rows=[]
    raw=[]
    for idx,r in g.iterrows():
        q,h=_role_maps(r)
        raw.append({
            'idx':idx,'player_uuid':str(r.player_uuid),'q':q,'H':h,
            'base_p_start':float(p[idx]),
            'rating_recent':_safe(r.get('rating_recent',0.0)),
            'rating_hist_n':int(_safe(r.get('rating_hist_n',0),0)),
            'rating_self_delta':_safe(r.get('rating_self_delta',0.0)),
            'rating_trend':_safe(r.get('rating_trend',0.0)),
        })

    # For every role, direct comparison is against the strongest other eligible
    # candidate under the pre-rating slot score. This stays target-outcome-free.
    adjustments={x['player_uuid']:{} for x in raw}
    features={x['player_uuid']:{'rel_gap':0.0,'self_shock':0.0,'trend_bounded':0.0,'valid_roles':0} for x in raw}
    for role in ROLES:
        eligible=[]
        for x in raw:
            qr=x['q'].get(role,0.0)
            if qr<min_q: continue
            s=_base_slot_score(qr,x['H'].get(role,0.0),x['base_p_start'])
            eligible.append((s,x))
        if len(eligible)<2: continue
        eligible.sort(key=lambda z:z[0],reverse=True)
        for _,x in eligible:
            others=[y for _,y in eligible if y['player_uuid']!=x['player_uuid']]
            if not others: continue
            comp=others[0]
            if x['rating_hist_n']>=2 and comp['rating_hist_n']>=2:
                rel=np.tanh((x['rating_recent']-comp['rating_recent'])/0.60)
            else:
                rel=0.0
            self_shock=np.tanh(x['rating_self_delta']/0.60) if x['rating_hist_n']>=4 else 0.0
            trend=np.tanh(x['rating_trend']/0.75) if x['rating_hist_n']>=2 else 0.0
            raw_signal=rel_w*rel+self_w*self_shock+trend_w*trend
            bounded=float(np.clip(raw_signal,-1.0,1.0))
            adjustments[x['player_uuid']][role]=float(gamma*bounded)
            # explanatory aggregate: keep strongest-magnitude role signal
            cur=features[x['player_uuid']]
            if abs(bounded)>=abs(cur['rel_gap']*rel_w+cur['self_shock']*self_w+cur['trend_bounded']*trend_w):
                cur['rel_gap']=float(rel);cur['self_shock']=float(self_shock);cur['trend_bounded']=float(trend)
            cur['valid_roles']+=1

    for x in raw:
        rows.append({
            'player_uuid':x['player_uuid'],
            'base_p_start':x['base_p_start'],
            'performance':.5,
            'q':x['q'],'H':x['H'],
            'role_adjustments':adjustments[x['player_uuid']],
            '_index':x['idx'],
            '_rating_explain':features[x['player_uuid']],
        })
    return rows

def add_relative_xi_features(frame,p,cfg,formation_history=None,formation_half_life=5.0,formation_strength=0.0):
    f=frame.copy()
    for c in ASSIGN_FEATURES:f[c]=0.0
    for c in ['rating_comp_rel_gap','rating_comp_self_shock','rating_comp_trend',
              'rating_comp_adjustment','rating_comp_valid_roles']:
        f[c]=0.0
    f['xi_assigned_role']='UNKNOWN';f['xi_formation']='UNKNOWN'

    for _,idxs in f.groupby(['fixture_uuid','team_id'],sort=False).indices.items():
        idxs=np.asarray(idxs,dtype=int);g=f.iloc[idxs]
        players=build_players_with_relative_form(
            g,p,cfg['gamma'],cfg['rel_w'],cfg['self_w'],cfg['trend_w'])
        formation_prior=None
        if formation_history is not None and formation_strength>0:
            cutoff=g.iloc[0]['cutoff']; team_id=int(g.iloc[0]['team_id'])
            formation_prior=formation_history.log_prior(
                team_id,cutoff,half_life=formation_half_life,
                formations=('4-2-3-1','4-3-3','4-4-2','3-4-2-1','3-4-3','3-5-2'),
                strength=formation_strength)
        try:
            out=optimize_best_formation(
                players,formation_log_prior=formation_prior,
                q_weight=.55,h_weight=.85,
                performance_weight=0.0,base_weight=1.0,min_q=.005)
        except RuntimeError:
            continue

        selected={a.player_uuid:a for a in out['xi']}
        alts=out['alternatives']
        fgap=float(alts[0]['score']-alts[1]['score']) if len(alts)>1 else 0.0
        bypid={pp['player_uuid']:pp for pp in players}

        for global_i in idxs:
            pid=str(f.at[global_i,'player_uuid'])
            pp=bypid[pid];ex=pp['_rating_explain']
            f.at[global_i,'rating_comp_rel_gap']=ex['rel_gap']
            f.at[global_i,'rating_comp_self_shock']=ex['self_shock']
            f.at[global_i,'rating_comp_trend']=ex['trend_bounded']
            f.at[global_i,'rating_comp_valid_roles']=ex['valid_roles']
            a=selected.get(pid)
            if a is None: continue
            f.at[global_i,'xi_selected_map']=1.0
            f.at[global_i,'xi_assignment_score']=a.score
            f.at[global_i,'xi_q_role']=a.q_role
            f.at[global_i,'xi_hierarchy']=a.hierarchy
            f.at[global_i,'xi_assigned_role']=a.role
            f.at[global_i,'xi_formation']=out['formation']
            f.at[global_i,'xi_formation_score_gap']=fgap
            f.at[global_i,'rating_comp_adjustment']=a.role_adjustment

            candidate_scores=[]
            for other in players:
                if other['player_uuid']==pid: continue
                q=other['q'].get(a.role,0.0);h=other['H'].get(a.role,0.0)
                if q<.005: continue
                candidate_scores.append(
                    _base_slot_score(q,h,other['base_p_start'])+
                    other['role_adjustments'].get(a.role,0.0))
            if candidate_scores:
                f.at[global_i,'xi_score_margin']=a.score-max(candidate_scores)
                f.at[global_i,'xi_role_competitors']=float(len(candidate_scores))
    return f

def evaluate_variant(frame,train,val,cfg,l2s=(.5,2.,10.,40.),formation_history=None,formation_half_life=5.0,formation_strength=0.0):
    p0,q,sub,x0,_=full_mm(frame.copy(),train)
    feat=add_relative_xi_features(frame,p0,cfg,formation_history=formation_history,formation_half_life=formation_half_life,formation_strength=formation_strength)
    rows=[];models={};preds={}
    for l2 in l2s:
        p,m=fit_residual(feat,p0,train,ASSIGN_FEATURES,l2)
        x=compose(feat,p,q,sub)
        met=metrics(feat,val,p,q,x)
        rows.append({'l2':l2,**met});models[str(l2)]=m;preds[l2]=(p,x)
    base=metrics(feat,val,p0,q,x0)
    return feat,p0,q,sub,x0,base,pd.DataFrame(rows),models,preds

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--ratings',required=True)
    ap.add_argument('--out',default=str(OUT_DEFAULT))
    a=ap.parse_args();out=Path(a.out);out.mkdir(parents=True,exist_ok=True)

    frame=add_sequence_features(pd.read_csv(SOURCE).reset_index(drop=True))
    frame=add_perf_features(frame,build_perf_ledger())
    frame=build_rating_features(frame,pd.read_csv(a.ratings))

    known=pd.to_datetime(frame.outcome_known_at,utc=True)
    dev=frame.gw.between(16,21).to_numpy()
    dcut=pd.to_datetime(frame.loc[dev,'cutoff'],utc=True).min()
    dtr=(frame.gw.between(6,15)&(known<dcut)).to_numpy()

    # XI-only reference recreated through zero-gamma variant.
    xi_cfg={'name':'xi_only','gamma':0.0,'rel_w':1.0,'self_w':0.0,'trend_w':0.0}
    _,_,_,_,_,_,xi_rows,_,_=evaluate_variant(frame,dtr,dev,xi_cfg)
    xi_rows=xi_rows.sort_values(['state_log_loss','xmins_rmse','xmins_mae'])
    xi_best=xi_rows.iloc[0].to_dict()

    configs=[]
    mixtures=[
        ('relative_only',1.0,0.0,0.0),
        ('relative_plus_self',0.75,0.25,0.0),
        ('relative_self_trend',0.65,0.25,0.10),
    ]
    for name,rw,sw,tw in mixtures:
        for gamma in (.02,.04,.06,.10,.15):
            configs.append({'name':name,'gamma':gamma,'rel_w':rw,'self_w':sw,'trend_w':tw})

    all_rows=[];cache={}
    for cfg in configs:
        feat,p0,q,sub,x0,base,cand,models,preds=evaluate_variant(frame,dtr,dev,cfg)
        for _,row in cand.iterrows():
            rec={'variant':cfg['name'],'gamma':cfg['gamma'],'rel_w':cfg['rel_w'],
                 'self_w':cfg['self_w'],'trend_w':cfg['trend_w'],**row.to_dict()}
            for k in ['state_log_loss','state_brier','xmins_mae','xmins_rmse']:
                rec['delta_vs_xi_'+k]=rec[k]-xi_best[k]
            all_rows.append(rec)
        cache[(cfg['name'],cfg['gamma'])]=(feat,p0,q,sub,x0,base,cand,models,preds,cfg)

    grid=pd.DataFrame(all_rows).sort_values(
        ['delta_vs_xi_state_log_loss','delta_vs_xi_xmins_rmse','delta_vs_xi_xmins_mae'])
    grid.to_csv(out/'development_grid.csv',index=False)

    eligible=grid[
        (grid.delta_vs_xi_state_log_loss<0)&
        (grid.delta_vs_xi_xmins_rmse<=.02)&
        (grid.delta_vs_xi_xmins_mae<=.02)
    ]
    selected=None if eligible.empty else eligible.iloc[0].to_dict()

    result={
        'classification':'MM v2 bounded relative-rating role competition experiment',
        'selection_reference':'XI-only development result, not locked MM',
        'xi_only_development_best':xi_best,
        'development_grid':grid.to_dict(orient='records'),
        'selected':selected,
        'rules':{
            'ratings_only_relative_within_role':True,
            'bounded_by_tanh':True,
            'missing_rating_is_neutral':True,
            'one_player_max_one_slot':True,
            'minutes_models_unchanged':True,
            'PM_TS_unchanged':True,
            'GW22_38_reused_diagnostic_only':True,
        }
    }

    if selected is not None:
        cfg={k:selected[k] for k in ['variant','gamma','rel_w','self_w','trend_w']}
        # recreate selected config name format
        cfg2={'name':cfg['variant'],'gamma':float(cfg['gamma']),'rel_w':float(cfg['rel_w']),
              'self_w':float(cfg['self_w']),'trend_w':float(cfg['trend_w'])}
        test=frame.gw.between(22,38).to_numpy()
        tcut=pd.to_datetime(frame.loc[test,'cutoff'],utc=True).min()
        ttr=(frame.gw.between(6,21)&(known<tcut)).to_numpy()
        feat,p0,q,sub,x0,base,cand,models,preds=evaluate_variant(frame,ttr,test,cfg2,l2s=(float(selected['l2']),))
        p,x=preds[float(selected['l2'])]
        met=metrics(feat,test,p,q,x)
        result['reused_diagnostic']={
            'base':base,'relative_rating':met,
            'delta':{k:met[k]-base[k] for k in ['state_log_loss','state_brier','xmins_mae','xmins_rmse','xmins_bias']}
        }
        pred=feat.loc[test,['fixture_uuid','player_uuid','team_id','gw','team','player','pos',
                            'expected_role','xi_assigned_role','xi_formation','y','minutes']].copy()
        pred['base_p_start']=p0[test];pred['v2_p_start']=p[test]
        pred['base_xmins']=x0[test];pred['v2_xmins']=x[test]
        for c in ASSIGN_FEATURES+['rating_recent','rating_long_mean','rating_self_delta','rating_trend',
                                  'rating_comp_rel_gap','rating_comp_self_shock','rating_comp_trend',
                                  'rating_comp_adjustment','rating_comp_valid_roles']:
            pred[c]=feat.loc[test,c].to_numpy()
        write_gzip_csv(pred,out/'reused_diagnostic_predictions.csv.gz')

    write_json(out/'result.json',result)
    print(json.dumps(result,indent=2))

if __name__=='__main__':main()

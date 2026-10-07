from __future__ import annotations
import json
import numpy as np
import pandas as pd
from scipy.special import expit,logit

from fpl_v1_1_model.deadline_components import player_components_at_deadline,weighted_totals
from fpl_v1_1_model.role_event_priors import role_priors_at_deadline,QCOLS
from fpl_v1_1_model.defcon import threshold_probability
from fpl_v1_1_model.negative_events import rare_event_probability
from fpl_v1_1_model.attack import shrunk_rate_per90
from run_v4_performance_rating_experiment import add_features as add_perf_features
from run_soft_role_performance_allocation import apply_model,add_role_axes,GOAL_BASE,ASSIST_BASE
from run_soft_role_defcon import add_axes as add_dc_axes,design as dc_design
from run_defcon_threshold_finalist import invert_p

def build_fixture_components(rg,pastph,rolehist,cutoff,attack,dc,neg,ga_models,dc_model,dccal,
                             perf_ledger,home,away,hgoal,agoal,assist_prob):
    rg=rg.copy()
    comps=player_components_at_deadline(pastph,rg,cutoff,attack=attack,dc=dc,discipline=neg)
    rg=rg.merge(comps.drop(columns=['cutoff'],errors='ignore'),
                on=['fixture_uuid','player_uuid'],how='left',validate='one_to_one')
    if rg.goal_rate90.isna().any():raise ValueError('missing player components')
    tr=rg[['fixture_uuid','player_uuid','team_id','pos']+QCOLS+['max_history_known_at']].copy()
    tr['cutoff']=cutoff
    pri=role_priors_at_deadline(pastph,rolehist,rg[['fixture_uuid','player_uuid','team_id','pos']],tr,cutoff,900)
    rg=rg.merge(pri,on=['fixture_uuid','player_uuid','team_id'],how='left',validate='one_to_one')
    players={pid:g for pid,g in pastph.groupby('player_uuid',sort=False)}
    for kind,event in [('goal','xg'),('assist','xa')]:
        rec=attack[kind]['recency_half_life'];tau=attack[kind]['current_season_position_prior_minutes_tau']
        den=np.array([weighted_totals(players.get(pid,pastph.iloc[:0]),event,rec)[1] for pid in rg.player_uuid])
        adj=tau/(den+tau)*(rg[kind+'_role_prior90'].to_numpy()-rg[kind+'_position_prior90'].to_numpy())
        rg[kind+'_rate90']=np.maximum(0,rg[kind+'_rate90'].to_numpy()+adj)
    tau=dc['position_prior_minutes_tau']
    den=np.array([weighted_totals(players.get(pid,pastph.iloc[:0]),'defcon_count',dc['player_dc_half_life'])[1]
                  for pid in rg.player_uuid])
    rg['role_dc_rate90']=np.maximum(0,rg.dc_rate90.to_numpy()+tau/(den+tau)*
                                    (rg.dc_role_prior90-rg.dc_position_prior90))
    rg['mu_dc']=rg.expected_minutes/90*rg.role_dc_rate90*rg.dc_opponent_factor
    rg['control_xmins']=rg.expected_minutes.astype(float)
    rg=add_perf_features(rg,perf_ledger)
    rg=add_role_axes(rg)
    def mode_for(model):
        if model is None:
            return 'role_only'
        cols=model.get('columns',[])
        if any('__hard_' in x for x in cols):
            return 'hard'
        if any('__axis_' in x for x in cols):
            return 'soft'
        return 'shared'
    gs=apply_model(rg,'goal_rate90',GOAL_BASE,mode_for(ga_models['goal']),ga_models['goal'])
    ass=apply_model(rg,'assist_rate90',ASSIST_BASE,mode_for(ga_models['assist']),ga_models['assist'])
    rg['lambda_home_goals']=hgoal;rg['lambda_away_goals']=agoal
    rg['assist_probability_per_goal']=assist_prob
    teamlam=np.where(rg.team_id.astype(int)==home,hgoal,agoal)
    rg['goal_mu']=teamlam*gs
    rg['assist_mu']=teamlam*assist_prob*ass
    rg=add_dc_axes(rg)
    X=dc_design(rg,'soft').to_numpy(float)
    Z=(X-np.asarray(dc_model['mean']))/np.asarray(dc_model['scale'])
    rg['mu_dc']=np.maximum(0,rg.mu_dc.to_numpy(float)*np.exp(np.clip(Z@np.asarray(dc_model['coef']),-3,3)))
    pos=rg.pos.replace({'GKP':'GK','G':'GK'}).astype(str).to_numpy()
    p0=np.array([threshold_probability(m,p,a) for m,p,a in zip(rg.mu_dc,pos,rg.dc_alpha)])
    coef=np.asarray(dccal['model']['coef']);pcal=expit(coef[0]+coef[1]*logit(np.clip(p0,1e-6,1-1e-6)))
    rg['mu_dc']=[invert_p(p,po,a) if po in ('DEF','MID','FWD') else 0.
                 for p,po,a in zip(pcal,pos,rg.dc_alpha)]
    tau_og=float(neg.get('own_goal_prior_minutes_tau',21511.019415095274))
    og=[]
    broad_hist=pastph.fpl_position.replace({'GKP':'GK'})
    for rr in rg.itertuples(index=False):
        bp='GK' if rr.pos in ('G','GK','GKP') else rr.pos
        pop=pastph[broad_hist==bp];ind=pastph[pastph.player_uuid==rr.player_uuid]
        exposure=float(pop.minutes.sum());prior=90*float(pop.own_goals.sum())/exposure if exposure>0 else 0.
        rate=shrunk_rate_per90(float(ind.own_goals.sum()),float(ind.minutes.sum()),prior,tau_og)
        og.append(rare_event_probability(rr.expected_minutes,rate))
    rg['p_own_goal']=og
    return rg

#!/usr/bin/env python3
"""Audit transfer-path changes and big-haul forecast misses for vFinal proxy v2."""
from __future__ import annotations
import json,sys
from pathlib import Path
import numpy as np,pandas as pd
from scipy.special import expit,logit

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'src'),str(ROOT/'scripts')]
import run_horizon_policy_comparison as hp
import run_transfer_strategy_v3_replay as base
from fpl_xpts.optimize import plan_squad
from fpl_xpts.identity import resolve_uuid_to_fpl_ids
from fpl_xpts.season_replay import OwnedPlayer,initial_squad

OLD=ROOT/'analysis/results/deep_audit_inputs/old'
NEW=ROOT/'analysis/results/deep_audit_inputs/new'
BASE=ROOT/'analysis/results/deep_audit_inputs/base'
VF=ROOT/'analysis/results/vfinal-integrated-20261005-v1'
MINS=ROOT/'analysis/results/v4-combined-minutes-20261005-v1/reused_diagnostic_predictions.csv.gz'
FEAT=ROOT/'analysis/results/workload-recovered-v4/all_features.csv.gz'
OUT=ROOT/'analysis/results/vfinal-v2-transfer-big-haul-audit-20261006-v1'
WEIGHTS=(1.0,.85,.70,.55,.40,.25)

def ints(cell):
    if pd.isna(cell) or str(cell).strip()=='':
        return []
    return [int(float(x)) for x in str(cell).split(';') if str(x).strip() and str(x)!='nan']

def mapping_uuid_to_id():
    feat=pd.read_csv(FEAT,usecols=['player_uuid','player']).drop_duplicates()
    raw=hp.unpack_runtime('players_raw.csv').drop_duplicates('id').copy()
    mp,_=resolve_uuid_to_fpl_ids(feat,raw)
    return mp

def vfinal_current():
    mp=mapping_uuid_to_id()
    p=pd.read_csv(VF/'predictions.csv.gz')
    p['id']=p.player_uuid.astype(str).map(mp)
    p=p[p.id.notna()].copy();p.id=p.id.astype(int)
    x=p.groupby(['gw','id'],as_index=False).agg(
        vfinal_xp=('vfinal_xpts','sum'),
        vfinal_minutes=('vfinal_minutes','sum'),
        vfinal_bonus=('vfinal_bonus','sum')
    )
    m=pd.read_csv(MINS)
    m['id']=m.player_uuid.astype(str).map(mp)
    m=m[m.id.notna()].copy();m.id=m.id.astype(int)
    m['p_fixture']=m.combined_p_start+(1-m.combined_p_start)*m.combined_q_sub
    q=m.groupby(['gw','id'],as_index=False).agg(
        p_no_play=('p_fixture',lambda s:float(np.prod(1-np.clip(s,0,1)))))
    q['vfinal_p_play']=1-q.p_no_play
    inp=pd.read_csv(VF/'vfinal_inputs.csv.gz')
    inp['id']=inp.player_uuid.astype(str).map(mp)
    inp=inp[inp.id.notna()].copy();inp.id=inp.id.astype(int)
    ci=inp.groupby(['gw','id'],as_index=False).agg(
        goal_mu=('goal_mu','sum'),assist_mu=('assist_mu','sum'),
        mu_dc=('mu_dc','sum'),lambda_saves=('lambda_saves','sum'),
        combined_xmins=('combined_xmins','sum'))
    return x.merge(q[['gw','id','vfinal_p_play']],on=['gw','id'],how='left').merge(ci,on=['gw','id'],how='left')

def reconstruct_gw22_state(gws,names,forecast):
    plans=pd.read_csv(BASE/'plans.csv')
    meta1=hp.gw_meta(gws,names,1)
    origin1=hp.complete_current_projection(forecast[forecast.origin_gw==0],meta1,1)
    state=initial_squad(origin1,meta1,[1])
    for gw in range(1,22):
        q=plans[(plans.origin_gw==gw)&(plans.is_executed.astype(str).str.lower().isin(['true','1']))]
        if q.empty:continue
        r=q.iloc[0];meta=hp.gw_meta(gws,names,gw).drop_duplicates('id').set_index('id')
        for pid in ints(r.outgoing):state.squad.pop(pid)
        for pid in ints(r.incoming):state.squad[pid]=OwnedPlayer(pid,int(meta.loc[pid,'price_tenths']))
        state.bank=int(round(float(r.bank_after)*10));state.free_transfers=int(r.free_transfers_after)
    return state

def apply_correction(origin,gw,vf):
    out=origin.copy()
    cur_base=(out[out.gw==gw][['id','xpts_mean','p_play']]
              .groupby('id',as_index=False).agg(base_xp=('xpts_mean','sum'),base_p_play=('p_play','max')))
    cur=vf[vf.gw==gw][['id','vfinal_xp','vfinal_p_play']]
    z=cur_base.merge(cur,on='id',how='inner')
    if z.empty:return out
    z['xp_factor']=np.clip((z.vfinal_xp+0.5)/(z.base_xp+0.5),0.5,1.5)
    bp=np.clip(z.base_p_play.astype(float),1e-4,1-1e-4)
    vp=np.clip(z.vfinal_p_play.fillna(z.base_p_play).astype(float),1e-4,1-1e-4)
    z['pplay_shift']=np.clip(logit(vp)-logit(bp),-1.5,1.5)
    fmap=dict(zip(z.id.astype(int),z.xp_factor.astype(float)))
    smap=dict(zip(z.id.astype(int),z.pplay_shift.astype(float)))
    idx=out.id.astype(int).isin(fmap)
    out.loc[idx,'xpts_mean']=out.loc[idx].apply(lambda r:float(r.xpts_mean)*fmap[int(r.id)],axis=1)
    out.loc[idx,'p_play']=out.loc[idx].apply(
        lambda r:float(expit(logit(float(np.clip(r.p_play,1e-4,1-1e-4)))+smap[int(r.id)])),axis=1)
    exact=dict(zip(z.id.astype(int),z.vfinal_xp.astype(float)))
    pexact=dict(zip(z.id.astype(int),z.vfinal_p_play.astype(float)))
    cm=out.gw.eq(gw)&out.id.astype(int).isin(exact)
    out.loc[cm,'xpts_mean']=out.loc[cm].id.astype(int).map(exact)
    out.loc[cm,'p_play']=out.loc[cm].id.astype(int).map(pexact)
    return out

def horizon_values(origin,gw):
    z=origin[(origin.gw>=gw)&(origin.gw<gw+len(WEIGHTS))].copy()
    z['w']=z.gw.map({gw+i:w for i,w in enumerate(WEIGHTS)}).fillna(0.0)
    z['wx']=z.xpts_mean*z.w
    return z.groupby('id',as_index=False).agg(horizon_value=('wx','sum'),current_xp=('xpts_mean',lambda s:float(s.iloc[0]) if len(s) else np.nan))

def selected_role(planrows,pid):
    q=planrows[planrows.id.astype(int).eq(int(pid))]
    if q.empty:return ''
    return str(q.iloc[0].role)

def main():
    if OUT.exists():raise FileExistsError(OUT)
    OUT.mkdir(parents=True)
    gws,names,forecast=base.prepare();vf=vfinal_current()
    raw=hp.unpack_runtime('players_raw.csv').drop_duplicates('id')
    id_name=dict(zip(raw.id.astype(int),raw.web_name.astype(str)))
    id_pos=dict(zip(raw.id.astype(int),raw.element_type.astype(int)))
    posname={1:'GK',2:'DEF',3:'MID',4:'FWD'}

    oldlog=pd.read_csv(OLD/'gameweek_log.csv');newlog=pd.read_csv(NEW/'gameweek_log.csv')
    oldp=pd.read_csv(OLD/'plans.csv');newp=pd.read_csv(NEW/'plans.csv')
    olde=oldp[oldp.is_executed.astype(str).str.lower().isin(['true','1'])].copy()
    newe=newp[newp.is_executed.astype(str).str.lower().isin(['true','1'])].copy()
    transfer_rows=[]
    for gw in range(22,39):
        ol=oldlog[oldlog.gw==gw].iloc[0];nl=newlog[newlog.gw==gw].iloc[0]
        o=olde[olde.origin_gw==gw];n=newe[newe.origin_gw==gw]
        orow=o.iloc[0] if len(o) else None;nrow=n.iloc[0] if len(n) else None
        oo=ints(orow.outgoing) if orow is not None else [];oi=ints(orow.incoming) if orow is not None else []
        no=ints(nrow.outgoing) if nrow is not None else [];ni=ints(nrow.incoming) if nrow is not None else []
        transfer_rows.append(dict(
          gw=gw,old_score=int(ol.score),new_score=int(nl.score),score_delta=int(nl.score-ol.score),
          old_out='; '.join(id_name.get(x,str(x)) for x in oo),old_in='; '.join(id_name.get(x,str(x)) for x in oi),
          new_out='; '.join(id_name.get(x,str(x)) for x in no),new_in='; '.join(id_name.get(x,str(x)) for x in ni),
          action_changed=bool(oo!=no or oi!=ni),
          old_hits=int(ol.hit_points),new_hits=int(nl.hit_points)))
    td=pd.DataFrame(transfer_rows);td.to_csv(OUT/'old_vs_new_transfers.csv',index=False)

    state=reconstruct_gw22_state(gws,names,forecast)
    known=hp.gw_meta(gws,names,1)
    for seen in range(2,22):
        obs=hp.gw_meta(gws,names,seen)
        known=pd.concat([known[~known.id.isin(obs.id)],obs],ignore_index=True).drop_duplicates('id',keep='last')

    haulrows=[]
    for gw in range(22,39):
        obs=hp.gw_meta(gws,names,gw)
        known=pd.concat([known[~known.id.isin(obs.id)],obs],ignore_index=True).drop_duplicates('id',keep='last')
        meta=known.copy()
        origin=apply_correction(base.origin_with_meta(forecast,meta,gw),gw,vf)
        hv=horizon_values(origin,gw)
        cur=(origin[origin.gw==gw].drop(columns=[c for c in ['meta_team','meta_price_tenths','meta_web_name','meta_position'] if c in origin.columns]))
        cur=hp.complete_current_projection(cur,meta,gw)

        q=newe[newe.origin_gw==gw]
        r=q.iloc[0] if len(q) else None
        incoming=ints(r.incoming) if r is not None else []; outgoing=ints(r.outgoing) if r is not None else []
        mm=meta.drop_duplicates('id').set_index('id')
        for pid in outgoing:state.squad.pop(pid)
        for pid in incoming:state.squad[pid]=OwnedPlayer(pid,int(mm.loc[pid,'price_tenths']))
        if r is not None:
            state.bank=int(round(float(r.bank_after)*10));state.free_transfers=int(r.free_transfers_after)

        plan=plan_squad(cur,list(state.squad),gw)
        planrows=plan.rows.copy()
        owned=set(int(x) for x in state.squad)

        actual=hp.actual_gw(gws,gw).copy()
        # tolerate archive schema variation
        ptscol='points' if 'points' in actual.columns else 'total_points'
        big=actual[actual[ptscol]>=10].sort_values(ptscol,ascending=False).head(12)
        for a in big.itertuples():
            pid=int(a.id);actual_pts=float(getattr(a,ptscol))
            vfr=vf[(vf.gw==gw)&(vf.id==pid)]
            cr=cur[cur.id.astype(int).eq(pid)]
            pred=float(cr.xpts_mean.sum()) if len(cr) else np.nan
            pp=float(cr.p_play.max()) if len(cr) else np.nan
            vmins=float(vfr.vfinal_minutes.iloc[0]) if len(vfr) else np.nan
            goal_mu=float(vfr.goal_mu.iloc[0]) if len(vfr) else np.nan
            assist_mu=float(vfr.assist_mu.iloc[0]) if len(vfr) else np.nan
            h=float(hv.loc[hv.id.astype(int).eq(pid),'horizon_value'].iloc[0]) if any(hv.id.astype(int).eq(pid)) else np.nan
            pos=posname.get(id_pos.get(pid),'?')
            samepos_owned=[x for x in owned if posname.get(id_pos.get(x),'?')==pos]
            comps=hv[hv.id.astype(int).isin(samepos_owned)].sort_values('horizon_value')
            weak_name=id_name.get(int(comps.iloc[0].id),'') if len(comps) else ''
            weak_h=float(comps.iloc[0].horizon_value) if len(comps) else np.nan
            chosen_same=[x for x in incoming if posname.get(id_pos.get(x),'?')==pos]
            chosen=chosen_same[0] if chosen_same else None
            chosen_h=float(hv.loc[hv.id.astype(int).eq(chosen),'horizon_value'].iloc[0]) if chosen is not None and any(hv.id.astype(int).eq(chosen)) else np.nan

            minutes=float(getattr(a,'minutes',np.nan))
            goals=float(getattr(a,'goals_scored',np.nan)) if hasattr(a,'goals_scored') else np.nan
            assists=float(getattr(a,'assists',np.nan)) if hasattr(a,'assists') else np.nan
            surprise=actual_pts-pred if np.isfinite(pred) else np.nan
            if np.isfinite(pp) and pp<0.5 and minutes>=60:
                reason='minutes_availability_miss'
            elif np.isfinite(surprise) and surprise>=10:
                reason='large_outcome_tail_or_event_rate_miss'
            elif pid not in owned and np.isfinite(h) and np.isfinite(weak_h) and h<weak_h:
                reason='ranked_below_owned_same_position_on_6gw_xp'
            elif pid not in owned:
                reason='path_budget_hits_or_multiweek_tradeoff'
            else:
                reason='owned_but_not_large_model_expectation'
            haulrows.append(dict(
              gw=gw,id=pid,player=id_name.get(pid,str(pid)),position=pos,
              actual_points=actual_pts,actual_minutes=minutes,actual_goals=goals,actual_assists=assists,
              forecast_xp=pred,p_play=pp,vfinal_expected_minutes=vmins,
              forecast_goal_mu=goal_mu,forecast_assist_mu=assist_mu,
              surprise=surprise,owned_after_transfers=pid in owned,lineup_role=selected_role(planrows,pid),
              horizon_6gw_value=h,weakest_owned_same_pos=weak_name,weakest_owned_same_pos_horizon=weak_h,
              chosen_incoming_same_pos=id_name.get(chosen,'') if chosen is not None else '',
              chosen_incoming_same_pos_horizon=chosen_h,reason=reason))
    hd=pd.DataFrame(haulrows)
    hd.to_csv(OUT/'big_hauls_diagnostic.csv',index=False)

    # Focus on biggest forecast misses.
    misses=hd.sort_values('surprise',ascending=False).head(30)
    misses.to_csv(OUT/'largest_forecast_misses.csv',index=False)
    summary={
      'old_total':int(oldlog.score.sum()),'new_total':int(newlog.score.sum()),
      'delta':int(newlog.score.sum()-oldlog.score.sum()),
      'changed_action_gws':int(td.action_changed.sum()),
      'worst_path_deltas':td.nsmallest(8,'score_delta')[['gw','score_delta','old_in','new_in']].to_dict(orient='records'),
      'best_path_deltas':td.nlargest(5,'score_delta')[['gw','score_delta','old_in','new_in']].to_dict(orient='records'),
      'big_haul_rows':int(len(hd)),
      'big_hauls_owned':int(hd.owned_after_transfers.sum()),
      'largest_forecast_misses':misses.head(15)[[
        'gw','player','actual_points','forecast_xp','surprise','p_play','vfinal_expected_minutes',
        'forecast_goal_mu','forecast_assist_mu','owned_after_transfers','lineup_role','reason'
      ]].round(3).to_dict(orient='records'),
      'reason_counts':hd.reason.value_counts().to_dict()
    }
    (OUT/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
    print(json.dumps(summary,indent=2))

if __name__=='__main__':main()

#!/usr/bin/env python3
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

MODEL=ROOT/'analysis/results/haul_capture_inputs/model'
BASE=ROOT/'analysis/results/haul_capture_inputs/base'
VF=ROOT/'analysis/results/vfinal-integrated-20261005-v1'
MINS=ROOT/'analysis/results/v4-combined-minutes-20261005-v1/reused_diagnostic_predictions.csv.gz'
FEAT=ROOT/'analysis/results/workload-recovered-v4/all_features.csv.gz'
OUT=ROOT/'analysis/results/vfinal-haul-capture-minutes-audit-20261006-v1'

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
    x=p.groupby(['gw','id'],as_index=False).agg(vfinal_xp=('vfinal_xpts','sum'),vfinal_minutes=('vfinal_minutes','sum'))
    m=pd.read_csv(MINS)
    m['id']=m.player_uuid.astype(str).map(mp)
    m=m[m.id.notna()].copy();m.id=m.id.astype(int)
    m['p_fixture']=m.combined_p_start+(1-m.combined_p_start)*m.combined_q_sub
    q=m.groupby(['gw','id'],as_index=False).agg(p_no_play=('p_fixture',lambda s:float(np.prod(1-np.clip(s,0,1)))))
    q['vfinal_p_play']=1-q.p_no_play
    return x.merge(q[['gw','id','vfinal_p_play']],on=['gw','id'],how='left')

def reconstruct_gw22_state(gws,names,forecast):
    plans=pd.read_csv(BASE/'plans.csv')
    meta1=hp.gw_meta(gws,names,1)
    origin1=hp.complete_current_projection(forecast[forecast.origin_gw==0],meta1,1)
    state=initial_squad(origin1,meta1,[1])
    for gw in range(1,22):
        q=plans[(plans.origin_gw==gw)&(plans.is_executed.astype(str).str.lower().isin(['true','1']))]
        if q.empty: continue
        r=q.iloc[0];meta=hp.gw_meta(gws,names,gw).drop_duplicates('id').set_index('id')
        for pid in ints(r.outgoing): state.squad.pop(pid)
        for pid in ints(r.incoming): state.squad[pid]=OwnedPlayer(pid,int(meta.loc[pid,'price_tenths']))
        state.bank=int(round(float(r.bank_after)*10));state.free_transfers=int(r.free_transfers_after)
    return state

def apply_correction(origin,gw,vf):
    out=origin.copy()
    cur_base=(out[out.gw==gw][['id','xpts_mean','p_play']].groupby('id',as_index=False).agg(base_xp=('xpts_mean','sum'),base_p_play=('p_play','max')))
    cur=vf[vf.gw==gw][['id','vfinal_xp','vfinal_p_play']]
    z=cur_base.merge(cur,on='id',how='inner')
    if z.empty:return out
    z['xp_factor']=np.clip((z.vfinal_xp+0.5)/(z.base_xp+0.5),0.5,1.5)
    bp=np.clip(z.base_p_play.astype(float),1e-4,1-1e-4)
    vp=np.clip(z.vfinal_p_play.fillna(z.base_p_play).astype(float),1e-4,1-1e-4)
    z['shift']=np.clip(logit(vp)-logit(bp),-1.5,1.5)
    fmap=dict(zip(z.id.astype(int),z.xp_factor.astype(float)))
    smap=dict(zip(z.id.astype(int),z['shift'].astype(float)))
    idx=out.id.astype(int).isin(fmap)
    out.loc[idx,'xpts_mean']=out.loc[idx].apply(lambda r:float(r.xpts_mean)*fmap[int(r.id)],axis=1)
    out.loc[idx,'p_play']=out.loc[idx].apply(lambda r:float(expit(logit(float(np.clip(r.p_play,1e-4,1-1e-4)))+smap[int(r.id)])),axis=1)
    exact=dict(zip(z.id.astype(int),z.vfinal_xp.astype(float)))
    pexact=dict(zip(z.id.astype(int),z.vfinal_p_play.astype(float)))
    cm=out.gw.eq(gw)&out.id.astype(int).isin(exact)
    out.loc[cm,'xpts_mean']=out.loc[cm].id.astype(int).map(exact)
    out.loc[cm,'p_play']=out.loc[cm].id.astype(int).map(pexact)
    return out

def main():
    if OUT.exists(): raise FileExistsError(OUT)
    OUT.mkdir(parents=True)
    gws,names,forecast=base.prepare();vf=vfinal_current()
    raw=hp.unpack_runtime('players_raw.csv').drop_duplicates('id')
    id_name=dict(zip(raw.id.astype(int),raw.web_name.astype(str)))
    plans=pd.read_csv(MODEL/'plans.csv')
    exe=plans[plans.is_executed.astype(str).str.lower().isin(['true','1'])].copy()
    state=reconstruct_gw22_state(gws,names,forecast)
    known=hp.gw_meta(gws,names,1)
    for seen in range(2,22):
        obs=hp.gw_meta(gws,names,seen)
        known=pd.concat([known[~known.id.isin(obs.id)],obs],ignore_index=True).drop_duplicates('id',keep='last')
    rows=[];minute_misses=[]
    for gw in range(22,39):
        obs=hp.gw_meta(gws,names,gw)
        known=pd.concat([known[~known.id.isin(obs.id)],obs],ignore_index=True).drop_duplicates('id',keep='last')
        meta=known.copy()
        origin=apply_correction(base.origin_with_meta(forecast,meta,gw),gw,vf)
        cur=origin[origin.gw==gw].drop(columns=[c for c in ['meta_team','meta_price_tenths','meta_web_name','meta_position'] if c in origin.columns])
        cur=hp.complete_current_projection(cur,meta,gw)
        ranks=(cur.groupby('id',as_index=False).agg(forecast_xp=('xpts_mean','sum'),p_play=('p_play','max')).sort_values('forecast_xp',ascending=False).reset_index(drop=True))
        ranks['overall_rank']=np.arange(1,len(ranks)+1)
        rankmap=ranks.set_index('id').overall_rank.to_dict()
        xpmap=ranks.set_index('id').forecast_xp.to_dict()
        ppmap=ranks.set_index('id').p_play.to_dict()
        q=exe[exe.origin_gw==gw];r=q.iloc[0] if len(q) else None
        mm=meta.drop_duplicates('id').set_index('id')
        for pid in ints(r.outgoing) if r is not None else []: state.squad.pop(pid)
        for pid in ints(r.incoming) if r is not None else []: state.squad[pid]=OwnedPlayer(pid,int(mm.loc[pid,'price_tenths']))
        if r is not None:
            state.bank=int(round(float(r.bank_after)*10));state.free_transfers=int(r.free_transfers_after)
        owned=set(int(x) for x in state.squad)
        lineup=plan_squad(cur,list(state.squad),gw).rows.copy()
        role=dict(zip(lineup.id.astype(int),lineup.role.astype(str)))
        actual=hp.actual_gw(gws,gw);pts='points' if 'points' in actual.columns else 'total_points'
        hauls=actual[actual[pts]>=10]
        for a in hauls.itertuples():
            pid=int(a.id);vfr=vf[(vf.gw==gw)&(vf.id==pid)]
            expmin=float(vfr.vfinal_minutes.iloc[0]) if len(vfr) else np.nan
            rr=int(rankmap[pid]) if pid in rankmap else np.nan
            lr=role.get(pid,'')
            rows.append(dict(gw=gw,id=pid,player=id_name.get(pid,str(pid)),actual_points=float(getattr(a,pts)),
                actual_minutes=float(getattr(a,'minutes',np.nan)),forecast_xp=float(xpmap.get(pid,np.nan)),
                p_play=float(ppmap.get(pid,np.nan)),expected_minutes=expmin,overall_xp_rank=rr,
                owned=pid in owned,lineup_role=lr,in_xi=lr in {'XI','C','VC'},captain=lr=='C',
                top15_forecast=(rr<=15 if np.isfinite(rr) else False),
                top30_forecast=(rr<=30 if np.isfinite(rr) else False),
                top50_forecast=(rr<=50 if np.isfinite(rr) else False)))
        active=actual[actual.minutes>=60]
        for a in active.itertuples():
            pid=int(a.id);pp=float(ppmap.get(pid,np.nan));vfr=vf[(vf.gw==gw)&(vf.id==pid)]
            expmin=float(vfr.vfinal_minutes.iloc[0]) if len(vfr) else np.nan
            if (np.isfinite(pp) and pp<0.5) or (np.isfinite(expmin) and expmin<30):
                minute_misses.append(dict(gw=gw,id=pid,player=id_name.get(pid,str(pid)),actual_minutes=float(a.minutes),
                    actual_points=float(getattr(a,pts)),forecast_xp=float(xpmap.get(pid,np.nan)),p_play=pp,
                    expected_minutes=expmin,owned=pid in owned,lineup_role=role.get(pid,'')))
    hd=pd.DataFrame(rows);hd.to_csv(OUT/'all_10plus_hauls.csv',index=False)
    mmiss=pd.DataFrame(minute_misses);mmiss.to_csv(OUT/'minute_availability_misses.csv',index=False)
    uniq=(hd.groupby(['id','player'],as_index=False).agg(haul_gws=('gw','size'),owned_haul_gws=('owned','sum'),xi_haul_gws=('in_xi','sum'),max_actual=('actual_points','max'),mean_forecast=('forecast_xp','mean')))
    uniq['ever_captured']=uniq.owned_haul_gws>0
    uniq.to_csv(OUT/'unique_haul_players.csv',index=False)
    bygw=(hd.groupby('gw',as_index=False).agg(haul_players=('id','size'),owned=('owned','sum'),xi=('in_xi','sum'),top15=('top15_forecast','sum'),top30=('top30_forecast','sum'),top50=('top50_forecast','sum')))
    bygw.to_csv(OUT/'haul_capture_by_gw.csv',index=False)
    summary={
      'haul_player_gws':int(len(hd)),
      'owned_haul_player_gws':int(hd.owned.sum()),
      'owned_capture_rate':float(hd.owned.mean()),
      'xi_haul_player_gws':int(hd.in_xi.sum()),
      'xi_capture_rate':float(hd.in_xi.mean()),
      'captained_haul_player_gws':int(hd.captain.sum()),
      'top15_forecast_haul_player_gws':int(hd.top15_forecast.sum()),
      'top15_forecast_capture_rate':float(hd.top15_forecast.mean()),
      'top30_forecast_capture_rate':float(hd.top30_forecast.mean()),
      'top50_forecast_capture_rate':float(hd.top50_forecast.mean()),
      'unique_players_with_10plus':int(len(uniq)),
      'unique_players_ever_owned_on_haul':int(uniq.ever_captured.sum()),
      'unique_player_capture_rate':float(uniq.ever_captured.mean()),
      'median_forecast_xp_for_10plus':float(hd.forecast_xp.median()),
      'mean_forecast_xp_for_10plus':float(hd.forecast_xp.mean()),
      'median_rank_for_10plus':float(hd.overall_xp_rank.median()),
      'minute_availability_misses_60min':int(len(mmiss)),
      'minute_miss_10plus_count':int((mmiss.actual_points>=10).sum()) if len(mmiss) else 0,
      'minute_miss_examples':mmiss.sort_values(['actual_points','actual_minutes'],ascending=False).head(20).round(3).to_dict(orient='records') if len(mmiss) else [],
      'highest_forecast_missed_hauls':hd[~hd.owned].sort_values('forecast_xp',ascending=False).head(20).round(3).to_dict(orient='records')
    }
    (OUT/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
    print(json.dumps(summary,indent=2))
if __name__=='__main__':main()

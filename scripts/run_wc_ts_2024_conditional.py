#!/usr/bin/env python3
"""Conditional 2024/25 TS v3 robustness replay from GW6 to GW38.

Starts a fresh legal 15-player squad at GW6 from the locked vFinal forecast and
then runs the unchanged TS v3 planner through GW38. This deliberately does not
invent a GW1-5 cold-start provider that is absent from the historical checkpoint.

Forecast/model parameters are frozen. Historical deadline roster/price snapshots
are conditional proxies because their capture clocks are not independently
certified. Chips are OFF.
"""
from __future__ import annotations
import argparse,gzip,json,sys,time
from pathlib import Path
import pandas as pd

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'));sys.path.insert(0,str(ROOT/'scripts'))

import run_horizon_policy_comparison as hp
from fpl_xpts.optimize import plan_squad
from fpl_xpts.wildcard_ts_action import compare_wc_as_ts_action
from fpl_xpts.season_replay import OwnedPlayer,ReplayState,actual_team_points,initial_squad,legalize_team_limit,valid_squad
from fpl_xpts.transfer_planner import PlannerConfig,execute_first_action,plan_transfer_path

WEIGHTS=(1.0,.60,.36,.216,.1296,.07776)
BUFFER=1.0
POS={1:'GKP',2:'DEF',3:'MID',4:'FWD','1':'GKP','2':'DEF','3':'MID','4':'FWD'}

def jsonl(path):
    with gzip.open(path,'rt',encoding='utf-8') as f:return [json.loads(x) for x in f if x.strip()]

def runtime_inputs(derived):
    actual=pd.read_csv(derived/'eligible_player_fixture_actuals.csv.gz',low_memory=False)
    if 'gw' not in actual and 'GW' in actual:actual['gw']=actual.GW
    snaps=jsonl(derived/'deadline_player_candidates.jsonl.gz')
    meta=pd.DataFrame([dict(gw=int(r['gw']),element=int(r['fpl_element']),team=int(r['team_id']),
        position=POS.get(r.get('fpl_position'),str(r.get('fpl_position'))),value=int(r.get('price_tenths') or 0),
        web_name=str(r.get('web_name') or r.get('player_name') or r['fpl_element']))
        for r in snaps if r.get('fpl_element') is not None])
    meta=meta.drop_duplicates(['gw','element'],keep='last')
    names=meta.sort_values('gw').drop_duplicates('element',keep='last').set_index('element').web_name.to_dict()
    z=actual.copy()
    z['element']=pd.to_numeric(z.element,errors='coerce').astype('Int64')
    z=z[z.element.notna()].copy();z.element=z.element.astype(int)
    z=z.merge(meta,on=['gw','element'],how='left',validate='many_to_one',suffixes=('','_deadline'))
    for col in ['team','position','value']:
        dcol=col+'_deadline'
        if dcol in z.columns:z[col]=z[dcol]

    # Conditional snapshot candidates do not always contain a player in the exact
    # GW in which a post-match outcome row exists (typically newly-added players).
    # This is metadata only: forecasts/xP still come exclusively from PM. Prefer
    # the latest prior snapshot; if none exists, use the player's first later
    # snapshot as an explicitly conditional roster-metadata proxy.
    missing=z[['team','position','value']].isna().any(axis=1)
    fallback_rows=0;dropped_rows=0
    if missing.any():
        hist={int(e):g.sort_values('gw') for e,g in meta.groupby('element')}
        for idx,r in z.loc[missing,['gw','element']].iterrows():
            g=hist.get(int(r.element))
            if g is None or g.empty:
                dropped_rows+=1;continue
            prior=g[g.gw<=int(r.gw)]
            q=prior.iloc[-1] if len(prior) else g.iloc[0]
            z.at[idx,'team']=q.team;z.at[idx,'position']=q.position;z.at[idx,'value']=q.value
            fallback_rows+=1
    still=z[['team','position','value']].isna().any(axis=1)
    if still.any():
        dropped_rows+=int(still.sum());z=z.loc[~still].copy()
    print(f'Conditional TS metadata fallback rows={fallback_rows}, dropped rows={dropped_rows}',flush=True)
    z=z.rename(columns={'gw':'GW'})
    keep=['GW','element','team','position','value','total_points','minutes']
    return z[keep].copy(),names

def origin_with_meta(forecast,meta,gw):
    origin=forecast[forecast.origin_gw==gw-1].copy()
    mm=meta[['id','team','price_tenths']].rename(columns={'team':'meta_team','price_tenths':'meta_price_tenths'})
    origin=origin.merge(mm,on='id',how='left')
    if 'team' not in origin:origin['team']=origin.meta_team
    else:origin['team']=origin.team.fillna(origin.meta_team)
    origin['price_tenths']=origin.meta_price_tenths
    return origin

def run_variant(gws,names,forecast,wc_gw:int|None):
    meta=hp.gw_meta(gws,names,6)
    origin0=hp.complete_current_projection(forecast[forecast.origin_gw.eq(5)],meta,6)
    state=initial_squad(origin0,meta,[6])
    config=PlannerConfig(weights=WEIGHTS,hit_uncertainty_buffer=BUFFER,beam_width=20,
        candidates_per_transfer_count=1,candidate_limit_per_position=18,top_targets_per_position=18,
        local_bundle_beam=60,candidate_return_per_depth=12,max_transfers_per_week=5,
        candidate_backend='fast_local',milp_time_limit=2.0)
    known=meta.copy();total=0;log=[]
    for gw in range(6,39):
        obs=hp.gw_meta(gws,names,gw)
        known=pd.concat([known[~known.id.isin(obs.id)],obs],ignore_index=True).drop_duplicates('id',keep='last')
        meta=known.copy()
        origin_raw=forecast[forecast.origin_gw.eq(gw-1)]
        current=hp.complete_current_projection(origin_raw,meta,gw)
        origin=origin_with_meta(forecast,meta,gw)
        forced=legalize_team_limit(state,meta,origin,gw) if gw>6 else []
        wc=None
        if gw==wc_gw:
            wc=compare_wc_as_ts_action(state,meta,origin,gw,config,max_candidates=2,milp_seconds=8.)
            state=wc.state
            hit=0;transfers=wc.transfers
        else:
            normal=plan_transfer_path(state,meta,origin,gw,config)
            moves=execute_first_action(state,normal,meta)
            hit=sum(int(x.get('hit',0)) for x in moves)+sum(int(x.get('hit',0)) for x in forced)
            transfers=len(moves)+len(forced)
        if not valid_squad(meta,state.squad):raise AssertionError('illegal squad')
        plan=plan_squad(current,list(state.squad),gw)
        score,_=actual_team_points(plan.rows,hp.actual_gw(gws,gw),None,hit)
        total+=int(score)
        log.append(dict(gw=gw,score=int(score),cum=int(total),
                        wc=(wc is not None),wc_gain=(wc.gain if wc else None),
                        wc_retained=(15-wc.transfers if wc else None),
                        wc_projection_gws=(len(wc.normal_result.horizon_gws) if wc else None),
                        transfers=int(transfers),hits=int(hit)))
        print('2024-25',wc_gw,gw,'pts',score,'cum',total,flush=True)
    return dict(points=int(total),transfers=sum(r['transfers'] for r in log),
                hits=sum(r['hits'] for r in log),logs=log)

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--derived',required=True)
    ap.add_argument('--vfinal',required=True)
    ap.add_argument('--out',required=True)
    a=ap.parse_args();out=Path(a.out);out.mkdir(parents=True,exist_ok=True)
    gws,names=runtime_inputs(Path(a.derived))
    forecast=pd.read_csv(a.vfinal);forecast.id=forecast.id.astype(int)
    forecast['web_name']=forecast.id.map(names).fillna(forecast.id.astype(str))
    if 'team' not in forecast:forecast['team']=pd.NA
    results={}
    for name,wc_gw in [('baseline',None),('wc_gw12',12),('wc_gw20',20)]:
        r=run_variant(gws,names,forecast,wc_gw)
        pd.DataFrame(r.pop('logs')).to_csv(out/(name+'.csv'),index=False)
        results[name]=r
    if results['baseline']['points']!=1880:
        raise RuntimeError('Baseline drift '+str(results['baseline']['points']))
    (out/'summary.json').write_text(json.dumps(results,indent=2))
    print(json.dumps(results,indent=2))
if __name__=='__main__':main()

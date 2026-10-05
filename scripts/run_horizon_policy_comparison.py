#!/usr/bin/env python3
"""Compare transfer forecast horizons for vFinal replay logic.

This test isolates horizon weighting only. Chips are OFF.

Candidates:
- 3GW equal: (1.00, 1.00, 1.00)
- 3GW decay: (1.00, 0.85, 0.70)
- 6GW decay: (1.00, 0.85, 0.70, 0.55, 0.40, 0.25)

Because full cutoff-safe vFinal rolling forecasts are not yet available for all
GW1-38 origins, this script evaluates the decision rule on the recovered
rolling Phase5Q full-season forecast archive as a strategy proxy. It does NOT
claim to be a vFinal full-season performance replay. The purpose is to choose
the transfer horizon policy before regenerating vFinal rolling forecasts.

No chips, same transfer costs, same lineup/captain rules, same actual outcomes.
"""
from __future__ import annotations
import gzip,io,json,sys
from dataclasses import dataclass
from math import floor
from pathlib import Path
import numpy as np
import pandas as pd
from scipy.optimize import Bounds,LinearConstraint,milp

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))

from fpl_xpts.optimize import POSITION_COUNTS,plan_squad
from fpl_xpts.season_replay import (
    OwnedPlayer,ReplayState,selling_price,valid_squad,legalize_team_limit,
    actual_team_points,initial_squad
)
from run_v4rc_experiment import write_json,sha

LEG=ROOT/'analysis/results/legacy-season-technical-replay-v1'
ROLL=ROOT/'analysis/results/legacy-rolling-recovery-v1'
OUT=ROOT/'analysis/results/horizon-policy-comparison-20261005-v1'

CANDS={
 '3gw_equal':(1.0,1.0,1.0),
 '3gw_decay':(1.0,.85,.70),
 '6gw_decay':(1.0,.85,.70,.55,.40,.25),
}
SAVED_FT_VALUE=2.16
HIT_BUFFER=2.0


def unpack_manifest(folder,name):
    m=json.loads((folder/'manifest.json').read_text())
    e=next(x for x in m['outputs'] if x['name']==name)
    packed=b''.join((folder/p['path']).read_bytes() for p in e['parts'])
    return pd.read_csv(io.BytesIO(gzip.decompress(packed)))


def unpack_runtime(name):
    items=json.loads((LEG/'runtime_input_manifest.json').read_text())
    e=next(x for x in items if x['runtime_path'].endswith(name))
    packed=b''.join((LEG/p['path']).read_bytes() for p in e['parts'])
    return pd.read_csv(io.BytesIO(gzip.decompress(packed)),low_memory=False)


def rolling_forecast():
    return unpack_manifest(ROLL,'player_gw_forecasts')


def horizon_values(origin,current_gw,weights):
    byoff=dict(enumerate(weights))
    f=origin[origin.gw.between(current_gw,current_gw+len(weights)-1)].copy()
    f['weighted']=[float(x)*byoff.get(int(g)-current_gw,0.0) for x,g in zip(f.xpts_mean,f.gw)]
    return f.groupby('id').weighted.sum()


def transfer_costs(state,count,already):
    out=[]
    for off in range(1,count+1):
        ix=already+off
        hit=4 if ix>state.free_transfers else 0
        expiring=state.free_transfers>=5 and ix==1
        cost=(hit+HIT_BUFFER) if hit else (0.0 if expiring else SAVED_FT_VALUE)
        out.append((hit,cost))
    return out


def best_bundle(state,meta,origin,gw,weights,max_total=5,already=0):
    values=horizon_values(origin,gw,weights)
    owned=set(state.squad)
    eligible=set(origin.id.astype(int))|owned
    players=meta[meta.id.isin(eligible)].drop_duplicates('id').copy().reset_index(drop=True)
    if not owned.issubset(set(players.id.astype(int))): return []
    players['value']=players.id.map(values).fillna(0.0).astype(float)
    prices=players.set_index('id').price_tenths.astype(int).to_dict()
    sale={pid:selling_price(o.purchase_price,int(prices[pid])) for pid,o in state.squad.items()}
    players['owned']=players.id.isin(owned)
    players['effective_price']=[sale[int(r.id)] if bool(r.owned) else int(r.price_tenths) for r in players.itertuples()]
    resources=int(state.bank+sum(sale.values()))
    current=float(values.reindex(list(owned)).fillna(0).sum())
    n=len(players)
    rows=[];lo=[];hi=[]
    for pos,c in POSITION_COUNTS.items():
        rows.append((players.position==pos).to_numpy(float));lo.append(float(c));hi.append(float(c))
    for team in players.team.dropna().unique():
        rows.append((players.team==team).to_numpy(float));lo.append(-np.inf);hi.append(3.0)
    rows.append(players.effective_price.to_numpy(float));lo.append(-np.inf);hi.append(float(resources))
    incoming=(~players.owned).to_numpy(float)
    best=None
    for tc in range(1,min(max_total,max(0,5-already))+1):
        rr=rows+[incoming];ll=lo+[float(tc)];hh=hi+[float(tc)]
        res=milp(c=-players.value.to_numpy(float),integrality=np.ones(n),bounds=Bounds(0,1),
                 constraints=LinearConstraint(np.vstack(rr),np.array(ll),np.array(hh)),
                 options={'time_limit':10.0})
        if res.x is None: continue
        selected=set(players.loc[res.x>.5,'id'].astype(int))
        if len(selected)!=15: continue
        gain=float(values.reindex(list(selected)).fillna(0).sum()-current)
        costs=transfer_costs(state,tc,already)
        decision=sum(x[1] for x in costs);net=gain-decision
        if net<=0: continue
        if best is None or net>best['net']+1e-9:
            best=dict(selected=selected,count=tc,gain=gain,net=net,costs=costs)
    if best is None:return []
    by=players.set_index('id');outs=owned-best['selected'];ins=best['selected']-owned
    pairs=[]
    for pos in POSITION_COUNTS:
        oo=sorted([p for p in outs if by.loc[p,'position']==pos],key=lambda p:float(values.get(p,0)))
        ii=sorted([p for p in ins if by.loc[p,'position']==pos],key=lambda p:float(values.get(p,0)),reverse=True)
        if len(oo)!=len(ii):raise RuntimeError('pair mismatch')
        for o,i in zip(oo,ii):pairs.append((float(values.get(i,0)-values.get(o,0)),o,i))
    pairs.sort(reverse=True)
    spend=int(players.loc[players.id.isin(best['selected']),'effective_price'].sum())
    final_bank=resources-spend
    for o in outs:state.squad.pop(o)
    for i in ins:state.squad[i]=OwnedPlayer(i,int(by.loc[i,'price_tenths']))
    state.bank=final_bank
    ans=[]
    for (gain,o,i),(hit,cost) in zip(pairs,best['costs']):
        ans.append(dict(out_id=int(o),in_id=int(i),gain=gain,hit=hit,decision_cost=cost))
    return ans


def gw_meta(gws,names,gw):
    z=gws[gws.GW==gw][['element','team','position','value']].drop_duplicates('element').copy()
    z=z.rename(columns={'element':'id','value':'price_tenths'})
    z['web_name']=z.id.map(names).fillna(z.id.astype(str))
    z['position']=z.position.replace({'GK':'GKP'})
    return z


def actual_gw(gws,gw):
    z=gws[gws.GW==gw].groupby('element',as_index=False).agg(points=('total_points','sum'),minutes=('minutes','sum'))
    return z.rename(columns={'element':'id'})


def complete_current_projection(origin,meta,gw):
    cur=origin[origin.gw==gw].copy()
    mm=meta[['id','web_name','team','position','price_tenths']].rename(columns={
        'web_name':'meta_web_name','team':'meta_team','position':'meta_position','price_tenths':'meta_price_tenths'})
    cur=cur.merge(mm,on='id',how='right')
    cur['gw']=gw
    if 'xpts_mean' not in cur: cur['xpts_mean']=0.0
    cur['xpts_mean']=cur.xpts_mean.fillna(0.0)
    if 'web_name' not in cur: cur['web_name']=cur.meta_web_name
    else: cur['web_name']=cur.web_name.fillna(cur.meta_web_name)
    if 'team' not in cur: cur['team']=cur.meta_team
    else: cur['team']=cur.team.fillna(cur.meta_team)
    if 'position' not in cur: cur['position']=cur.meta_position
    else: cur['position']=cur.position.fillna(cur.meta_position)
    cur['price_tenths']=cur.meta_price_tenths
    return cur


def run_policy(name,weights,gws,forecast,names):
    meta1=gw_meta(gws,names,1)
    origin1=complete_current_projection(forecast[forecast.origin_gw==0],meta1,1)
    state=initial_squad(origin1,meta1,[1]);initial=list(state.squad)
    known=meta1.copy();total=0;control=0;logs=[]
    for gw in range(1,39):
        obs=gw_meta(gws,names,gw)
        known=pd.concat([known[~known.id.isin(obs.id)],obs],ignore_index=True).drop_duplicates('id',keep='last')
        meta=known.copy()
        origin=forecast[forecast.origin_gw==gw-1].copy()
        current=complete_current_projection(origin,meta,gw)
        mm=meta[['id','team','price_tenths']].rename(columns={'team':'meta_team','price_tenths':'meta_price_tenths'})
        origin=origin.merge(mm,on='id',how='left')
        if 'team' not in origin: origin['team']=origin.meta_team
        else: origin['team']=origin.team.fillna(origin.meta_team)
        origin['price_tenths']=origin.meta_price_tenths
        transfers=[];hit_cost=0
        if gw>1:
            transfers=legalize_team_limit(state,meta,origin,gw)
            rem=max(0,5-len(transfers))
            transfers+=best_bundle(state,meta,origin,gw,weights,max_total=rem,already=len(transfers))
            hit_cost=sum(int(x['hit']) for x in transfers)
        if not valid_squad(meta,state.squad):raise RuntimeError(f'invalid squad GW{gw}')
        plan=plan_squad(current,list(state.squad),gw)
        sc,_=actual_team_points(plan.rows,actual_gw(gws,gw),None,hit_cost)
        total+=sc
        cp=plan_squad(current,initial,gw);cs,_=actual_team_points(cp.rows,actual_gw(gws,gw),None,0);control+=cs
        used=len(transfers);state.free_transfers=min(5,max(0,state.free_transfers-used)+1)
        logs.append(dict(gw=gw,score=sc,cumulative=total,transfers=used,hit_cost=hit_cost,bank=state.bank/10))
    return dict(policy=name,weights=list(weights),total_points=int(total),transfers=int(sum(x['transfers'] for x in logs)),
                hit_points=int(sum(x['hit_cost'] for x in logs)),no_transfer_control=int(control),
                uplift=int(total-control),logs=logs)


def main():
    if OUT.exists():raise FileExistsError(OUT)
    OUT.mkdir(parents=True)
    gws=unpack_runtime('merged_gw.csv')
    raw=unpack_runtime('players_raw.csv')
    names=raw.set_index('id').web_name.astype(str).to_dict()
    forecast=rolling_forecast()
    forecast=forecast[['id','web_name','position','gw','origin_gw','xpts_mean','p_play','fixtures']].copy()
    forecast.id=forecast.id.astype(int)

    results=[]
    for name,w in CANDS.items():
        print('Running',name,flush=True)
        r=run_policy(name,w,gws,forecast,names)
        pd.DataFrame(r.pop('logs')).to_csv(OUT/f'{name}_gameweek_log.csv',index=False)
        results.append(r)
    table=pd.DataFrame(results).sort_values('total_points',ascending=False)
    table.to_csv(OUT/'comparison.csv',index=False)
    best=table.iloc[0].to_dict()
    summary=dict(
      classification='transfer-horizon policy test on recovered Phase5Q full-season forecasts; chips off',
      purpose='select horizon policy before cutoff-safe vFinal rolling forecasts are regenerated',
      candidates={k:list(v) for k,v in CANDS.items()},
      same_transfer_costs=dict(hit=4,hit_uncertainty_buffer=HIT_BUFFER,saved_ft_value=SAVED_FT_VALUE),
      results=results,best=best,
      chips='OFF',
      caveat='This is NOT a vFinal full-season performance result; forecast provider is recovered rolling Phase5Q because full vFinal origin-horizon coverage does not yet exist.')
    write_json(OUT/'summary.json',summary)
    outs=[p for p in sorted(OUT.iterdir()) if p.name!='manifest.json']
    write_json(OUT/'manifest.json',dict(sources=[
      dict(path='scripts/run_horizon_policy_comparison.py',sha256=sha(Path(__file__))),
      dict(path='src/fpl_xpts/season_replay.py',sha256=sha(ROOT/'src/fpl_xpts/season_replay.py'))],
      outputs=[dict(path=p.name,sha256=sha(p)) for p in outs]))
    print(json.dumps(summary,indent=2))

if __name__=='__main__':main()

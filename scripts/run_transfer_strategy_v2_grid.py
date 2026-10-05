#!/usr/bin/env python3
"""Repeat the 9 replay grid with lineup-aware transfer strategy (TS v2).

Point/forecast model is LOCKED for this experiment.

The new transfer strategy values a candidate 15-man squad by the projected
manager score it can actually realize in each future GW:
- choose legal XI separately in every forecast GW
- choose captain separately in every forecast GW
- bench players can therefore be retained through bad fixtures and started
  later without forcing a transfer

Objective over horizon:
    sum_g w_g * (XI_xP_g + captain_xP_g)

Chips are OFF. Same hit costs, saved-FT value, price rules and actual scoring as
the previous 9-way proxy replays.

As before, recovered rolling Phase5Q forecasts are used only as a full-season
strategy proxy until cutoff-safe vFinal rolling forecasts exist. This does not
change or refit vFinal itself.
"""
from __future__ import annotations
import gzip,io,json,sys
from pathlib import Path
import numpy as np
import pandas as pd
from scipy.optimize import Bounds,LinearConstraint,milp

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'));sys.path.insert(0,str(ROOT/'scripts'))

import run_horizon_policy_comparison as hp
from fpl_xpts.optimize import POSITION_COUNTS,START_MIN,START_MAX,plan_squad
from fpl_xpts.season_replay import (
    OwnedPlayer,ReplayState,selling_price,valid_squad,legalize_team_limit,
    actual_team_points,initial_squad
)
from run_v4rc_experiment import write_json,sha

OUT=ROOT/'analysis/results/transfer-strategy-v2-grid-20261005-v1'
POLICIES={
 '3gw_085_070':(1.00,.85,.70),
 '3gw_080_060':(1.00,.80,.60),
 '6gw_decay':(1.00,.85,.70,.55,.40,.25),
}
BUFFERS=[1.0,1.5,2.0]
SAVED_FT_VALUE=2.16


def _player_table(meta,origin,gw,weights,owned):
    targets=[gw+i for i in range(len(weights))]
    eligible=set(origin.id.astype(int))|set(owned)
    p=meta[meta.id.isin(eligible)].drop_duplicates('id').copy().reset_index(drop=True)
    # xP matrix, missing forecast => 0
    pivot=origin[origin.gw.isin(targets)].pivot_table(index='id',columns='gw',values='xpts_mean',aggfunc='sum')
    for t in targets:
        p[f'xpt_{t}']=p.id.map(pivot[t] if t in pivot.columns else pd.Series(dtype=float)).fillna(0.0)
    return p,targets


def _manager_score_fixed_squad(players,targets,weights,selected_ids):
    """Optimize XI + captain for a fixed 15-man squad over the horizon."""
    q=players[players.id.isin(selected_ids)].copy().reset_index(drop=True)
    if len(q)!=15:return -1e9
    total=0.0
    for wt,t in zip(weights,targets):
        # use existing lineup optimizer logic through a tiny projection frame
        proj=q[['id','web_name','team','position']].copy()
        proj['gw']=t;proj['xpts_mean']=q[f'xpt_{t}'].to_numpy(float)
        try:
            plan=plan_squad(proj,list(selected_ids),t)
        except Exception:
            return -1e9
        total+=float(wt)*float(plan.expected_score)
    return total


def _build_joint_milp(players,targets,weights,state,transfer_count,resources,sale_prices):
    """Jointly optimize final squad, XI and captain in each future GW."""
    n=len(players);h=len(targets)
    # variables: x[n], s[h*n], c[h*n]
    N=n+2*h*n
    c=np.zeros(N,float)
    for g,(wt,t) in enumerate(zip(weights,targets)):
        xp=players[f'xpt_{t}'].to_numpy(float)
        s0=n+g*n
        c0=n+h*n+g*n
        c[s0:s0+n]=-float(wt)*xp
        c[c0:c0+n]=-float(wt)*xp

    rows=[];lo=[];hi=[]
    def row():
        return np.zeros(N,float)

    # squad structure
    for pos,count in POSITION_COUNTS.items():
        r=row();r[:n]=(players.position==pos).to_numpy(float)
        rows.append(r);lo.append(float(count));hi.append(float(count))
    for team in players.team.dropna().unique():
        r=row();r[:n]=(players.team==team).to_numpy(float)
        rows.append(r);lo.append(-np.inf);hi.append(3.0)
    r=row();r[:n]=players.effective_price.to_numpy(float)
    rows.append(r);lo.append(-np.inf);hi.append(float(resources))
    r=row();r[:n]=(~players.owned).to_numpy(float)
    rows.append(r);lo.append(float(transfer_count));hi.append(float(transfer_count))

    # each GW: 11 starters, legal formation, 1 captain, starter/captain subset of squad
    for g,t in enumerate(targets):
        s0=n+g*n;c0=n+h*n+g*n
        r=row();r[s0:s0+n]=1
        rows.append(r);lo.append(11.0);hi.append(11.0)
        r=row();r[c0:c0+n]=1
        rows.append(r);lo.append(1.0);hi.append(1.0)

        # s_i <= x_i ; c_i <= s_i
        for i in range(n):
            r=row();r[s0+i]=1;r[i]=-1
            rows.append(r);lo.append(-np.inf);hi.append(0.0)
            r=row();r[c0+i]=1;r[s0+i]=-1
            rows.append(r);lo.append(-np.inf);hi.append(0.0)

        for pos in START_MIN:
            mask=(players.position==pos).to_numpy(float)
            r=row();r[s0:s0+n]=mask
            rows.append(r);lo.append(float(START_MIN[pos]));hi.append(float(START_MAX[pos]))

    integrality=np.ones(N)
    bounds=Bounds(np.zeros(N),np.ones(N))
    res=milp(c=c,integrality=integrality,bounds=bounds,
             constraints=LinearConstraint(np.vstack(rows),np.asarray(lo),np.asarray(hi)),
             options={'time_limit':20.0})
    return res


def transfer_costs(state,count,already,buffer):
    out=[]
    for off in range(1,count+1):
        ix=already+off
        hit=4 if ix>state.free_transfers else 0
        expiring=state.free_transfers>=5 and ix==1
        cost=(hit+buffer) if hit else (0.0 if expiring else SAVED_FT_VALUE)
        out.append((hit,cost))
    return out


def best_manager_bundle(state,meta,origin,gw,weights,buffer,max_total=5,already=0):
    owned=set(state.squad)
    players,targets=_player_table(meta,origin,gw,weights,owned)
    if not owned.issubset(set(players.id.astype(int))):return []
    prices=players.set_index('id').price_tenths.astype(int).to_dict()
    sale={pid:selling_price(o.purchase_price,int(prices[pid])) for pid,o in state.squad.items()}
    players['owned']=players.id.isin(owned)
    players['effective_price']=[
        sale[int(r.id)] if bool(r.owned) else int(r.price_tenths) for r in players.itertuples()]
    resources=int(state.bank+sum(sale.values()))
    current_score=_manager_score_fixed_squad(players,targets,weights,list(owned))
    n=len(players)

    best=None
    maximum=min(max_total,max(0,5-already))
    for tc in range(1,maximum+1):
        res=_build_joint_milp(players,targets,weights,state,tc,resources,sale)
        if res.x is None:continue
        selected=set(players.loc[res.x[:n]>.5,'id'].astype(int))
        if len(selected)!=15:continue
        candidate_score=-float(res.fun)
        gain=candidate_score-current_score
        costs=transfer_costs(state,tc,already,buffer)
        decision=float(sum(x[1] for x in costs))
        net=gain-decision
        if net<=0:continue
        if best is None or net>best['net']+1e-9:
            best=dict(selected=selected,count=tc,gain=gain,net=net,costs=costs,
                      current_score=current_score,candidate_score=candidate_score)
    if best is None:return []

    by=players.set_index('id');outs=owned-best['selected'];ins=best['selected']-owned
    # Pair only for readable logs; decision itself was made jointly.
    pairs=[]
    # individual 1-player weighted xP is only used to pair same-position outs/ins
    for pos in POSITION_COUNTS:
        oo=[p for p in outs if by.loc[p,'position']==pos]
        ii=[p for p in ins if by.loc[p,'position']==pos]
        if len(oo)!=len(ii):raise RuntimeError('position pair mismatch')
        def indiv(pid):
            return sum(float(w)*float(by.loc[pid,f'xpt_{t}']) for w,t in zip(weights,targets))
        oo=sorted(oo,key=indiv);ii=sorted(ii,key=indiv,reverse=True)
        for o,i in zip(oo,ii):pairs.append((indiv(i)-indiv(o),o,i))
    pairs.sort(reverse=True)

    spend=int(players.loc[players.id.isin(best['selected']),'effective_price'].sum())
    final_bank=resources-spend
    for o in outs:state.squad.pop(o)
    for i in ins:state.squad[i]=OwnedPlayer(i,int(by.loc[i,'price_tenths']))
    state.bank=final_bank

    ans=[]
    for (pair_gain,o,i),(hit,cost) in zip(pairs,best['costs']):
        ans.append(dict(out_id=int(o),in_id=int(i),gain=float(pair_gain),hit=int(hit),
                        decision_cost=float(cost),bundle_gain=float(best['gain']),
                        bundle_net_gain=float(best['net']),
                        projected_manager_score_before=float(best['current_score']),
                        projected_manager_score_after=float(best['candidate_score'])))
    return ans


def run_policy(name,weights,buffer,gws,forecast,names):
    meta1=hp.gw_meta(gws,names,1)
    origin1=hp.complete_current_projection(forecast[forecast.origin_gw==0],meta1,1)
    state=initial_squad(origin1,meta1,[1]);initial=list(state.squad)
    known=meta1.copy();total=0;control=0;logs=[]
    for gw in range(1,39):
        obs=hp.gw_meta(gws,names,gw)
        known=pd.concat([known[~known.id.isin(obs.id)],obs],ignore_index=True).drop_duplicates('id',keep='last')
        meta=known.copy()
        origin=forecast[forecast.origin_gw==gw-1].copy()
        current=hp.complete_current_projection(origin,meta,gw)
        mm=meta[['id','team','price_tenths']].rename(columns={'team':'meta_team','price_tenths':'meta_price_tenths'})
        origin=origin.merge(mm,on='id',how='left')
        if 'team' not in origin:origin['team']=origin.meta_team
        else:origin['team']=origin.team.fillna(origin.meta_team)
        origin['price_tenths']=origin.meta_price_tenths

        transfers=[];hit_cost=0
        if gw>1:
            transfers=legalize_team_limit(state,meta,origin,gw)
            rem=max(0,5-len(transfers))
            transfers+=best_manager_bundle(state,meta,origin,gw,weights,buffer,max_total=rem,already=len(transfers))
            hit_cost=sum(int(x['hit']) for x in transfers)
        if not valid_squad(meta,state.squad):raise RuntimeError(f'invalid squad GW{gw}')

        plan=plan_squad(current,list(state.squad),gw)
        sc,_=actual_team_points(plan.rows,hp.actual_gw(gws,gw),None,hit_cost)
        total+=sc
        cp=plan_squad(current,initial,gw);cs,_=actual_team_points(cp.rows,hp.actual_gw(gws,gw),None,0);control+=cs
        used=len(transfers);state.free_transfers=min(5,max(0,state.free_transfers-used)+1)
        logs.append(dict(gw=gw,score=sc,cumulative=total,transfers=used,hit_cost=hit_cost,bank=state.bank/10))
    return dict(policy=name,weights=list(weights),hit_buffer=float(buffer),total_points=int(total),
                transfers=int(sum(x['transfers'] for x in logs)),hit_points=int(sum(x['hit_cost'] for x in logs)),
                no_transfer_control=int(control),uplift=int(total-control),logs=logs)


def main():
    if OUT.exists():raise FileExistsError(OUT)
    OUT.mkdir(parents=True)
    gws=hp.unpack_runtime('merged_gw.csv')
    raw=hp.unpack_runtime('players_raw.csv')
    names=raw.set_index('id').web_name.astype(str).to_dict()
    forecast=hp.rolling_forecast()[['id','web_name','position','gw','origin_gw','xpts_mean','p_play','fixtures']].copy()
    forecast.id=forecast.id.astype(int)

    rows=[]
    for policy,w in POLICIES.items():
        for buf in BUFFERS:
            label=f'{policy}_buffer_{buf:.1f}'
            print('Running',label,flush=True)
            r=run_policy(label,w,buf,gws,forecast,names)
            logs=pd.DataFrame(r.pop('logs'));logs.to_csv(OUT/f'{label}_gameweek_log.csv',index=False)
            dev=logs[logs.gw.between(1,21)];late=logs[logs.gw.between(22,38)]
            rows.append(dict(label=label,policy=policy,weights=list(w),hit_buffer=buf,
                total_points=r['total_points'],transfers=r['transfers'],hit_points=r['hit_points'],uplift=r['uplift'],
                points_gw1_21=int(dev.score.sum()),points_gw22_38=int(late.score.sum()),
                transfers_gw1_21=int(dev.transfers.sum()),transfers_gw22_38=int(late.transfers.sum()),
                hit_points_gw1_21=int(dev.hit_cost.sum()),hit_points_gw22_38=int(late.hit_cost.sum()),
                no_transfer_control=r['no_transfer_control']))

    tab=pd.DataFrame(rows).sort_values(['total_points','hit_points','transfers'],ascending=[False,True,True]).reset_index(drop=True)
    tab.to_csv(OUT/'comparison.csv',index=False)
    tab['rank_total']=tab.total_points.rank(method='min',ascending=False)
    byp=tab.groupby('policy').agg(mean_total=('total_points','mean'),min_total=('total_points','min'),
        max_total=('total_points','max'),mean_hits=('hit_points','mean'),mean_transfers=('transfers','mean'),
        mean_rank=('rank_total','mean')).reset_index().sort_values('mean_total',ascending=False)
    byb=tab.groupby('hit_buffer').agg(mean_total=('total_points','mean'),min_total=('total_points','min'),
        max_total=('total_points','max'),mean_hits=('hit_points','mean'),mean_transfers=('transfers','mean'),
        mean_rank=('rank_total','mean')).reset_index().sort_values('mean_total',ascending=False)
    byp.to_csv(OUT/'summary_by_policy.csv',index=False);byb.to_csv(OUT/'summary_by_buffer.csv',index=False)

    summary=dict(
      classification='TS v2 lineup-aware 9-way strategy proxy; chips off; point model locked',
      point_model='LOCKED; no vFinal component refit',
      transfer_objective='weighted projected manager score over horizon with legal XI + captain chosen separately each GW',
      policies={k:list(v) for k,v in POLICIES.items()},hit_buffers=BUFFERS,
      chips='OFF',saved_ft_value=SAVED_FT_VALUE,results=rows,best=tab.iloc[0].to_dict(),
      caveat='Recovered rolling Phase5Q forecasts are used as strategy proxy. Repeat identical TS v2 grid on cutoff-safe vFinal rolling forecasts when available.')
    write_json(OUT/'summary.json',summary)
    outs=[p for p in sorted(OUT.iterdir()) if p.name!='manifest.json']
    write_json(OUT/'manifest.json',dict(sources=[
        dict(path='scripts/run_transfer_strategy_v2_grid.py',sha256=sha(Path(__file__))),
        dict(path='scripts/run_horizon_policy_comparison.py',sha256=sha(ROOT/'scripts/run_horizon_policy_comparison.py'))],
        outputs=[dict(path=p.name,sha256=sha(p)) for p in outs]))
    print(json.dumps(summary,indent=2))

if __name__=='__main__':main()

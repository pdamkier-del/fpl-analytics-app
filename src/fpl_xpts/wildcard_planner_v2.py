from __future__ import annotations
"""Experimental WC v2: cutoff-safe proxy horizon and ownership-aware budget.

No changes to the locked MM, PM, or TS modules.
"""
from dataclasses import dataclass
from dataclasses import replace
import numpy as np
import pandas as pd
from scipy.optimize import Bounds, LinearConstraint, milp
from scipy.sparse import lil_matrix
from .optimize import POSITION_COUNTS, START_MAX, START_MIN, plan_squad
from .season_replay import ReplayState, squad_sale_value, selling_price, valid_squad
from .transfer_planner import _apply_selected_squad, clone_state, plan_transfer_path, PlannerConfig

@dataclass
class WildcardCandidate:
    state: ReplayState
    squad_ids: tuple[int,...]
    budget_tenths: int
    changed: int
    normal_objective: float
    wildcard_objective: float
    gain: float
    effective_price_savings_tenths: int
    projection_source: str
    projected_gws: int

def build_asof_wc_projection(history:pd.DataFrame, meta:pd.DataFrame,
                             origin:pd.DataFrame, gw:int, config:PlannerConfig)->pd.DataFrame:
    """Construct a *proxy* six-week projection when only the next week exists.

    Do not read history originating after the current deadline. Only historical
    per-player next-week xP are used to estimate a persistent baseline.
    Unknown future fixtures default to one; we explicitly do NOT use the final
    season's realised DGW/BGW schedule. The current week remains untouched.
    """
    horizon=[g for g in range(gw,min(39,gw+len(config.weights)))]
    latest=origin[origin.gw.eq(gw)].copy().drop_duplicates('id')
    if not len(latest): raise RuntimeError(f'GW{gw} missing current xP')
    have=set(origin.gw.astype(int).unique())
    if all(g in have for g in horizon):
        return origin[origin.gw.isin(horizon)].copy()
    early=history[(history.origin_gw < gw-1)&(history.origin_gw>=gw-7)].copy()
    early=early[early.gw.eq(early.origin_gw+1)]
    early=early[pd.to_numeric(early.fixtures,errors='coerce').fillna(0).gt(0)]
    if len(early):
        early['per_game']=pd.to_numeric(early.xpts_mean,errors='coerce').fillna(0.)/early.fixtures.clip(lower=1)
        early['recency']=np.exp2(-(gw-1-early.origin_gw)/3.)
        early['wvalue']=early.per_game*early.recency
        hist=early.groupby('id').agg(wvalue=('wvalue','sum'),weight=('recency','sum'))
        historical=(hist.wvalue/hist.weight).to_dict()
    else:historical={}
    # Future unknown GW: conservative regression to a 6-deadline rolling
    # baseline, eliminating one-week opponent spikes. No realised future data.
    curr=latest.set_index('id')
    forecast=[]
    for target in horizon:
        if target==gw:
            forecast.append(latest.copy())
            continue
        # Include true *as-of* multi-GW forecasts when available.
        existing=origin[origin.gw.eq(target)]
        if len(existing) and existing.id.nunique()==latest.id.nunique():
            forecast.append(existing.copy())
            continue
        proj=latest.copy()
        f=pd.to_numeric(latest.fixtures,errors='coerce').fillna(1).to_numpy(float)
        now=pd.to_numeric(latest.xpts_mean,errors='coerce').fillna(0).to_numpy(float)
        current_per_match=now/np.maximum(f,1.)
        ids=latest.id.astype(int)
        prev=np.asarray([historical.get(int(pid),np.nan) for pid in ids],dtype=float)
        proxy=np.where(np.isfinite(prev),.30*current_per_match+.70*prev,current_per_match)
        proxy=np.maximum(0.,proxy)
        # Regression to baseline, small horizon uncertainty degradation.
        proj['xpts_mean']=np.clip(proxy*(.99**(target-gw-1)),0,12)
        proj['p_play']=np.where(np.isfinite(prev),
            np.minimum(1.,.5*pd.to_numeric(latest.p_play,errors='coerce').fillna(0).to_numpy(float)+.5),
            pd.to_numeric(latest.p_play,errors='coerce').fillna(0).to_numpy(float))
        proj['fixtures']=1
        proj['gw']=int(target)
        forecast.append(proj)
    return pd.concat(forecast,ignore_index=True)

def _solve_roster(state:ReplayState,meta:pd.DataFrame,proxy:pd.DataFrame,gw:int,
                  config:PlannerConfig,candidate_limit:int=23,bench_value:float=.16):
    """One six-GW stable XI with a bench-availability reward in an exact MILP.

    The bench coefficient is an explicit approximation to autosub usefulness,
    not an FPL rule nor a tuned hit buffer.
    """
    owned=set(state.squad)
    scores=proxy.assign(weighted=lambda x: x.xpts_mean*x.gw.map({
        gw+i:float(w) for i,w in enumerate(config.weights)}).fillna(0.))
    vals=scores.groupby('id').weighted.sum().to_dict()
    m=meta.drop_duplicates('id').copy()
    if 'status' not in m:m['status']='a'
    m=m[~m.status.eq('u')].copy()
    m['value']=m.id.map(vals).fillna(0.).astype(float)
    # Crucial accounting: retaining a player costs their SALE value,
    # not current purchase price, in a complete-team WC rebalance.
    m['effective_tenths']=[
       selling_price(state.squad[int(r.id)].purchase_price,int(r.price_tenths))
       if int(r.id) in owned else int(r.price_tenths)
       for r in m.itertuples()]
    keep=set(owned)
    for p in POSITION_COUNTS:
        keep.update(m[m.position.eq(p)].nlargest(candidate_limit,'value').id.astype(int))
    m=m[m.id.isin(keep)].reset_index(drop=True)
    n=len(m)
    if n<15:raise RuntimeError('Too few eligible WC candidates')
    v=m.value.to_numpy(float)
    n_vars=3*n; c=np.zeros(n_vars)
    c[:n]=-bench_value*v
    c[n:2*n]=-v
    c[2*n:]=-v
    r=[];lo=[];hi=[]
    def add(entries,lower,upper):
        r.append(entries);lo.append(lower);hi.append(upper)
    for p,count in POSITION_COUNTS.items():
        add([(int(i),1.) for i in np.flatnonzero(m.position.eq(p))],count,count)
    for team in m.team.unique():
        add([(int(i),1.) for i in np.flatnonzero(m.team.eq(team))],0,3)
    add([(i,float(x)) for i,x in enumerate(m.effective_tenths)],0,
        int(state.bank+squad_sale_value(state,meta)))
    add([(n+i,1.) for i in range(n)],11,11)
    add([(2*n+i,1.) for i in range(n)],1,1)
    for p in POSITION_COUNTS:
        positions=np.flatnonzero(m.position.eq(p))
        add([(n+int(i),1.) for i in positions],START_MIN[p],START_MAX[p])
    for i in range(n):
        add([(n+i,1.),(i,-1.)],-np.inf,0)
        add([(2*n+i,1.),(n+i,-1.)],-np.inf,0)
    A=lil_matrix((len(r),n_vars),dtype=float)
    for i,entries in enumerate(r):
        for k,val in entries:A[i,k]=val
    result=milp(c,integrality=np.ones(n_vars),bounds=Bounds(0.,1.),
                constraints=LinearConstraint(A.tocsr(),lo,hi),
                options={'time_limit':25.})
    if result.x is None:raise RuntimeError('WC v2 MILP failed '+str(result.message))
    chosen=set(m.loc[result.x[:n]>.5,'id'].astype(int))
    if not valid_squad(meta,chosen):raise AssertionError('WC v2 invalid squad')
    return chosen

def optimize_wildcard(state:ReplayState,meta:pd.DataFrame,origin:pd.DataFrame,
                      gw:int,config:PlannerConfig,forecast_history:pd.DataFrame,
                      bench_value:float=.16)->WildcardCandidate:
    proxy=build_asof_wc_projection(forecast_history,meta,origin,gw,config)
    chosen=_solve_roster(state,meta,proxy,gw,config,bench_value=bench_value)
    after,outgoing,incoming=_apply_selected_squad(state,chosen,meta)
    if after.bank<0 or not valid_squad(meta,after.squad):
        raise AssertionError('WC v2 invalid permanent state')
    # Official 2025/26 rules: maintain banked FT; do not grant another FT.
    after.free_transfers=int(state.free_transfers)
    after.chips_used['wildcard'].append(int(gw))
    normal=plan_transfer_path(clone_state(state),meta,proxy,gw,config)
    now_xp=float(plan_squad(proxy[proxy.gw.eq(gw)],list(after.squad),gw).expected_score)
    if gw<38:
        shifted=replace(config,weights=tuple(config.weights[1:])+(0.,))
        future=plan_transfer_path(clone_state(after),meta,proxy,gw+1,shifted)
        wc_q=now_xp+float(future.objective)
    else:wc_q=now_xp
    savings=sum(
        max(0,int(meta.set_index('id').loc[pid,'price_tenths'])-
                 selling_price(state.squad[pid].purchase_price,
                   int(meta.set_index('id').loc[pid,'price_tenths'])))
        for pid in state.squad if pid in chosen)
    return WildcardCandidate(after,tuple(sorted(chosen)),int(state.bank+squad_sale_value(state,meta)),
                             len(incoming),float(normal.objective),wc_q,
                             wc_q-float(normal.objective),savings,
                             'asof_current_plus_trailing_forecast_proxy',proxy.gw.nunique())

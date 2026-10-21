"""Private B-only scorer using PM's aligned draws and legal FPL autosubs.

The existing transfer search, prices, FT, hit costs and horizon are reused.
Patches are confined to a single preview worker process and restored on exit.
Production workers never enter this context. Search and XI selection remain
heuristic; this is not a claim of global stochastic-policy optimality.
"""
from contextlib import contextmanager
from functools import lru_cache
import itertools
import sys
import numpy as np
import pandas as pd
from fpl_xpts.optimize import SquadPlan,START_MIN,START_MAX
from b_chain_contract import VERSION,validate_forecast

POSITIONS={1:'GKP',2:'DEF',3:'MID',4:'FWD'}
FIELD=('DEF','MID','FWD')


def autosub_points(points,plays,positions,starters,bench):
    """Score legal automatic replacements; no bench points for cameo starters.

    Rows are aligned PM scenarios; columns are squad players. The three
    outfield bench indices are already in manager priority order. Feasibility
    retains unfilled absent slots in the nominated formation, allowing normal
    FPL replacements even when fewer than eleven players ultimately appear.
    """
    points=np.asarray(points,float);plays=np.asarray(plays,bool)
    positions=np.asarray(positions)
    field=[i for i in starters if positions[i]!='GKP']
    gk=next(i for i in starters if positions[i]=='GKP')
    reserve=next(i for i in bench if positions[i]=='GKP')
    subs=[i for i in bench if positions[i]!='GKP']
    total=points[:,starters].sum(axis=1)
    total+=np.where(~plays[:,gk]&plays[:,reserve],points[:,reserve],0.)
    counts=np.array([sum(positions[i]==pos for i in field)for pos in FIELD])
    missing=np.column_stack([(~plays[:,[i for i in field if positions[i]==pos]]).sum(axis=1)for pos in FIELD])
    available=(~plays[:,field]).sum(axis=1)
    extra=np.zeros(len(points));assigned=np.zeros(len(points),bool)
    subsets=sorted(itertools.product((0,1),repeat=3),key=lambda b:(sum(b),b),reverse=True)
    for bits in subsets:
        chosen=[i for i,yes in zip(subs,bits)if yes]
        k=len(chosen)
        additions=np.array([sum(positions[i]==pos for i in chosen)for pos in FIELD])
        lower=np.maximum(0,counts+additions-np.array([START_MAX[p]for p in FIELD]))
        upper=np.minimum(missing,counts+additions-np.array([START_MIN[p]for p in FIELD]))
        valid=(~assigned)&(available>=k)&plays[:,chosen].all(axis=1)&(upper>=lower).all(axis=1)&(lower.sum()<=k)&(upper.sum(axis=1)>=k)
        extra[valid]=points[:,chosen].sum(axis=1)[valid];assigned|=valid
    if not assigned.all():raise ValueError('No legal autosub resolution')
    return total+extra


class ScenarioScorer:
    def __init__(self,forecast):
        validate_forecast(forecast)
        self.forecast=forecast
        self.players={p['id']:p for p in forecast['players']}
        self.weeks={(p['id'],w['gw']):w for p in forecast['players']for w in p['weeks']}

    @lru_cache(maxsize=32768)
    def decision(self,gw,ids):
        # Preserve existing XI heuristic and deterministic tie order. Correct
        # its score, captain fallback and bench contribution with joint draws.
        by={pos:sorted([pid for pid in ids if POSITIONS[self.players[pid]['position']]==pos],
            key=lambda pid:(-self.weeks[pid,gw]['xpts'],pid))for pos in POSITIONS.values()}
        candidates=[]
        for d in range(3,6):
            for m in range(2,6):
                f=10-d-m
                if 1<=f<=3 and all(len(by[p])>=n for p,n in [('DEF',d),('MID',m),('FWD',f)]):
                    xi=by['GKP'][:1]+by['DEF'][:d]+by['MID'][:m]+by['FWD'][:f]
                    candidates.append((sum(self.weeks[pid,gw]['xpts']for pid in xi),xi))
        if not candidates or len(by['GKP'])!=2:raise ValueError('Invalid B planning squad')
        xi=max(candidates,key=lambda item:item[0])[1]
        bench=sorted([pid for pid in ids if pid not in xi and self.players[pid]['position']!=1],
            key=lambda pid:(-self.weeks[pid,gw]['xpts'],pid))
        bench+=[pid for pid in by['GKP']if pid not in xi]
        ix={pid:i for i,pid in enumerate(ids)}
        pts=np.asarray([self.weeks[pid,gw]['scenarios']['points']for pid in ids],float).T
        play=np.asarray([self.weeks[pid,gw]['scenarios']['minutes']for pid in ids],float).T>0
        starters=[ix[pid]for pid in xi]
        base=autosub_points(pts,play,[POSITIONS[self.players[pid]['position']]for pid in ids],starters,[ix[pid]for pid in bench])
        captain_matrix=pts[:,starters].mean(axis=0)[:,None]+(~play[:,starters]).T@pts[:,starters]/len(pts)
        np.fill_diagonal(captain_matrix,-np.inf)
        c,v=np.unravel_index(np.argmax(captain_matrix),captain_matrix.shape)
        return tuple(xi),tuple(bench),xi[c],xi[v],float(base.mean()+captain_matrix[c,v])

    def plan(self,projections,squad_ids,gw):
        ids=tuple(sorted(map(int,squad_ids)))
        xi,bench,captain,vice,score=self.decision(int(gw),ids)
        rows=projections[projections.gw.eq(gw)&projections.id.isin(ids)].copy()
        if len(rows)!=15:raise ValueError('Incomplete B lineup projection')
        rows['role']='XI'
        rows.loc[rows.id.eq(captain),'role']='C';rows.loc[rows.id.eq(vice),'role']='VC'
        number=0
        for pid in bench:
            if self.players[pid]['position']==1:role='GK bench'
            else:number+=1;role=f'Bench {number}'
            rows.loc[rows.id.eq(pid),'role']=role
        return SquadPlan(rows,score)


@contextmanager
def preview_scoring(forecast):
    """Preview subprocess only; restore all imported aliases on any failure."""
    import fpl_xpts.optimize as optimize
    import fpl_xpts.transfer_planner as planner
    scorer=ScenarioScorer(forecast)
    original=optimize.plan_squad
    changes=[]
    # Reuse all original search/chip entry points while ensuring that their
    # imported plan_squad aliases agree with the score used inside beam search.
    for name,module in list(sys.modules.items()):
        if module and (name.startswith('fpl_xpts.')or name in {'run_live_locked_ts','service.manager_job','run_joint_fh_wc_stopping_replay'}):
            if getattr(module,'plan_squad',None)is original:
                changes.append((module,'plan_squad',original));setattr(module,'plan_squad',scorer.plan)
    fast=planner._fast_manager_score
    changes.append((planner,'_fast_manager_score',fast))
    planner._fast_manager_score=lambda ctx,ids,gw:scorer.decision(int(gw),tuple(sorted(map(int,ids))))[-1]
    try:yield scorer
    finally:
        for module,key,value in reversed(changes):setattr(module,key,value)

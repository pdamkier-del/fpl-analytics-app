from __future__ import annotations

from dataclasses import dataclass
import numpy as np
import pandas as pd
from scipy.optimize import Bounds, LinearConstraint, milp
from scipy.sparse import lil_matrix

from .optimize import POSITION_COUNTS, START_MIN, START_MAX


@dataclass(frozen=True)
class InitialSquadConfig:
    weights: tuple[float, ...] = (1.00, 0.85, 0.70, 0.55, 0.40, 0.25)
    budget_tenths: int = 1000
    time_limit: float = 60.0
    mip_rel_gap: float = 0.002


@dataclass
class InitialSquadResult:
    squad_ids: list[int]
    lineups: dict[int, list[int]]
    captains: dict[int, int]
    vice_captains: dict[int, int]
    objective: float
    bank_tenths: int
    solver_message: str


def optimize_initial_squad_joint(
    projections: pd.DataFrame,
    players: pd.DataFrame,
    start_gw: int = 1,
    config: InitialSquadConfig = InitialSquadConfig(),
) -> InitialSquadResult:
    """Optimize the initial 15-man FPL squad over a rolling horizon.

    All eligible players are considered; there is no top-N candidate filter.
    Ownership, weekly legal XI, captain and vice-captain are optimized jointly.
    Captain fallback uses the same expected-value approximation as the rest of
    the project: xP(captain) + (1-p_play(captain))*xP(vice).
    """
    required={"id","position","team","price_tenths"}
    missing=required-set(players.columns)
    if missing:
        raise ValueError(f"initial squad metadata missing columns: {sorted(missing)}")

    gws=[
        gw for gw in range(start_gw,start_gw+len(config.weights))
        if gw in set(projections.gw.astype(int))
    ]
    if not gws:
        raise ValueError("no projection gameweeks available")

    meta=players.drop_duplicates("id").copy()
    meta=meta[meta.position.isin(POSITION_COUNTS)].copy()
    ids=meta.id.astype(int).tolist()
    n=len(ids); h=len(gws)
    id_to_i={pid:i for i,pid in enumerate(ids)}

    score=np.zeros((h,n),float); pplay=np.ones((h,n),float)
    use=projections[projections.gw.isin(gws)&projections.id.isin(ids)].copy()
    for r in use.itertuples():
        i=id_to_i[int(r.id)]; g=gws.index(int(r.gw))
        score[g,i]=float(r.xpts_mean)
        if hasattr(r,"p_play") and pd.notna(r.p_play):
            pplay[g,i]=float(np.clip(r.p_play,0,1))

    # Variables: own[N], XI[H,N], C[H,N], VC[H,N], T[H,N], VScore[H].
    off_own=0
    off_xi=n
    off_c=off_xi+h*n
    off_vc=off_c+h*n
    off_t=off_vc+h*n
    off_vs=off_t+h*n
    nv=off_vs+h

    def ix(base,g,i): return base+g*n+i

    c=np.zeros(nv,float)
    integ=np.ones(nv,int)
    lb=np.zeros(nv,float); ub=np.ones(nv,float)
    integ[off_t:off_vs]=0
    integ[off_vs:]=0

    rows=[]; los=[]; his=[]
    def add(d,lo,hi):
        rows.append(d);los.append(float(lo));his.append(float(hi))

    for g,w in enumerate(config.weights[:h]):
        c[off_xi+g*n:off_xi+(g+1)*n]=-w*score[g]
        c[off_c+g*n:off_c+(g+1)*n]=-w*score[g]
        L=float(np.min(score[g]));U=float(np.max(score[g]))
        lb[off_vs+g]=L;ub[off_vs+g]=U
        lb[off_t+g*n:off_t+(g+1)*n]=min(0,L)
        ub[off_t+g*n:off_t+(g+1)*n]=max(0,U)
        c[off_t+g*n:off_t+(g+1)*n]=-w*(1-pplay[g])

    # 15-man structure + budget + max 3/club.
    for pos,count in POSITION_COUNTS.items():
        add({off_own+i:1 for i in np.flatnonzero(meta.position.to_numpy()==pos)},count,count)
    for team in pd.unique(meta.team):
        add({off_own+i:1 for i in np.flatnonzero(meta.team.to_numpy()==team)},-np.inf,3)
    add({off_own+i:float(meta.iloc[i].price_tenths) for i in range(n)},-np.inf,config.budget_tenths)

    for g in range(h):
        add({ix(off_xi,g,i):1 for i in range(n)},11,11)
        add({ix(off_c,g,i):1 for i in range(n)},1,1)
        add({ix(off_vc,g,i):1 for i in range(n)},1,1)
        for pos in POSITION_COUNTS:
            add({ix(off_xi,g,i):1 for i in np.flatnonzero(meta.position.to_numpy()==pos)},
                START_MIN[pos],START_MAX[pos])
        for i in range(n):
            add({ix(off_xi,g,i):1,off_own+i:-1},-np.inf,0)
            add({ix(off_c,g,i):1,ix(off_xi,g,i):-1},-np.inf,0)
            add({ix(off_vc,g,i):1,ix(off_xi,g,i):-1},-np.inf,0)
            add({ix(off_c,g,i):1,ix(off_vc,g,i):1},-np.inf,1)

        # vice score and captain*vice fallback McCormick.
        add({off_vs+g:1,**{ix(off_vc,g,i):-score[g,i] for i in range(n)}},0,0)
        L=float(np.min(score[g]));U=float(np.max(score[g]));V=off_vs+g
        for i in range(n):
            C=ix(off_c,g,i);T=ix(off_t,g,i)
            add({T:1,C:-U},-np.inf,0)
            add({T:1,C:-L},0,np.inf)
            add({T:1,V:-1,C:-L},-np.inf,-L)
            add({T:1,V:-1,C:-U},-U,np.inf)

    A=lil_matrix((len(rows),nv),dtype=float)
    for r,d in enumerate(rows):
        if d:
            jj=np.fromiter(d.keys(),dtype=int);vv=np.fromiter(d.values(),dtype=float)
            A[r,jj]=vv
    res=milp(
        c=c,integrality=integ,bounds=Bounds(lb,ub),
        constraints=LinearConstraint(A.tocsr(),np.asarray(los),np.asarray(his)),
        options={"time_limit":float(config.time_limit),"mip_rel_gap":float(config.mip_rel_gap)}
    )
    if res.x is None:
        raise RuntimeError(f"initial squad MILP found no feasible solution: {res.message}")

    x=res.x
    squad=[ids[i] for i in range(n) if x[off_own+i]>.5]
    lineups={};caps={};vcs={}
    for g,gw in enumerate(gws):
        lineups[gw]=[ids[i] for i in range(n) if x[ix(off_xi,g,i)]>.5]
        caps[gw]=ids[int(np.argmax(x[off_c+g*n:off_c+(g+1)*n]))]
        vcs[gw]=ids[int(np.argmax(x[off_vc+g*n:off_vc+(g+1)*n]))]
    cost=int(meta[meta.id.isin(squad)].price_tenths.sum())
    return InitialSquadResult(
        squad_ids=sorted(squad),lineups=lineups,captains=caps,vice_captains=vcs,
        objective=float(-res.fun),bank_tenths=int(config.budget_tenths-cost),
        solver_message=str(res.message)
    )

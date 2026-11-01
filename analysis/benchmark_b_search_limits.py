"""Constrained exact diagnostics, never activated in locked TS or live B."""
import itertools,json,time
from pathlib import Path
import numpy as np
import pandas as pd
from fpl_xpts.season_replay import ReplayState,OwnedPlayer
from fpl_xpts.transfer_planner import _fast_local_candidate_squads
from b_preview_ts import ScenarioScorer,POSITIONS,autosub_points
OUT=Path('analysis/results/integrated-repair-20261031/ts')

def financing():
    positions=['GKP']*2+['DEF']*5+['MID']*5+['FWD']*3+['DEF','MID']
    meta=pd.DataFrame(dict(id=range(1,18),position=positions,team=range(1,18),price_tenths=[50]*15+[40,60],web_name=[f'P{i}'for i in range(1,18)]))
    origin=pd.DataFrame(dict(id=range(1,18),gw=20,xpts_mean=[3.]*15+[2.,20.],p_play=1.))
    state=ReplayState(squad={i:OwnedPlayer(i,50)for i in range(1,16)},bank=0,free_transfers=1)
    t=time.perf_counter();fast=_fast_local_candidate_squads(state,meta,origin,[20],[1.],2,20,100,100);elapsed=time.perf_counter()-t
    values=origin.set_index('id').xpts_mean;by=meta.set_index('id');best=None;legal=0
    for ids in itertools.combinations(range(1,18),15):
        f=by.loc[list(ids)]
        if f.position.value_counts().to_dict()!={'GKP':2,'DEF':5,'MID':5,'FWD':3}or f.price_tenths.sum()>750 or f.team.value_counts().max()>3:continue
        n=len(set(ids)-set(state.squad));hit=4*max(0,n-state.free_transfers)
        value=float(values.loc[list(ids)].sum()-hit);legal+=1
        if best is None or value>best['weighted_value_after_hit']:best=dict(ids=list(ids),transfers=n,hit=hit,bank=int(750-f.price_tenths.sum()),weighted_value_after_hit=value)
    fastbest=max(float(values.loc[list(ids)].sum()-4*max(0,len(ids-set(state.squad))-1))for ids in fast)
    assert best['transfers']==2 and best['hit']==4 and 16 in best['ids']and 17 in best['ids']and best['weighted_value_after_hit']>fastbest
    return dict(scope='One-GW weighted-player-value candidate-generator diagnostic, not a current manager/global six-GW regret estimate',free_transfers=1,chips=False,legal_exact_squads=legal,fast_candidates=len(fast),fast_seconds=elapsed,fast_best_after_hit=fastbest,exact=best,missed_value=best['weighted_value_after_hit']-fastbest)

def joint_lineup():
    rng=np.random.default_rng(20261031);ids=tuple(range(1,16));positions=[1]*2+[2]*5+[3]*5+[4]*3
    # Fixed synthetic aligned scenarios include missing appearances and fallback.
    plays=rng.random((12,15))<rng.uniform(.35,1,(1,15));points=plays*rng.integers(1,12,(12,15));pos=np.array([POSITIONS[p]for p in positions])
    scorer=object.__new__(ScenarioScorer);scorer.players={i:dict(position=p)for i,p in zip(ids,positions)};scorer.weeks={(i,20):dict(xpts=float(points[:,i-1].mean()),scenarios=dict(points=points[:,i-1].tolist(),minutes=(plays[:,i-1]*90).tolist()))for i in ids}
    current=scorer.decision(20,ids);t=time.perf_counter();best=(-np.inf,None);evaluations=0
    for keeper in range(2):
        for d in range(3,6):
            for m in range(2,6):
                f=10-d-m
                if not 1<=f<=3:continue
                for defs in itertools.combinations(range(2,7),d):
                    for mids in itertools.combinations(range(7,12),m):
                        for fwds in itertools.combinations(range(12,15),f):
                            xi=[keeper,*defs,*mids,*fwds];fieldbench=[i for i in range(2,15)if i not in xi]
                            captain=points[:,xi].mean(axis=0)[:,None]+(~plays[:,xi]).T@points[:,xi]/len(points);np.fill_diagonal(captain,-np.inf);c,v=np.unravel_index(np.argmax(captain),captain.shape)
                            for order in itertools.permutations(fieldbench):
                                bench=[*order,1-keeper];base=autosub_points(points,plays,pos,xi,bench);value=float(base.mean()+captain[c,v]);evaluations+=1
                                if value>best[0]:best=(value,dict(xi=[i+1 for i in xi],bench=[i+1 for i in bench],captain=xi[c]+1,vice=xi[v]+1))
    assert best[0]>=current[-1]-1e-10
    return dict(scope='Exhaustive legal XI, bench order, captain and vice within one fixed legal synthetic 15-player squad and 12 joint scenarios',heuristic_score=current[-1],exact_score=best[0],gain=best[0]-current[-1],evaluations=evaluations,seconds=time.perf_counter()-t,heuristic=dict(xi=current[0],bench=current[1],captain=current[2],vice=current[3]),exact=best[1])

def main():
    OUT.mkdir(parents=True,exist_ok=True);result=dict(financing=financing(),joint_lineup=joint_lineup(),live_activated=False,reason='Search limitations demonstrated; no historical transfer-policy benefit or online latency gate established. Locked TSv3 retained.')
    (OUT/'result.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
if __name__=='__main__':main()

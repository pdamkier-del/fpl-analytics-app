"""Fresh-process original scorer/planner invocation and independent path replay."""
import argparse
from dataclasses import asdict
import gzip
import json
import resource
import sys
import time
from pathlib import Path
START=time.perf_counter();ROOT=Path(__file__).resolve().parents[2]
sys.path[:0]=[str(ROOT/'research/ts_search/code'),str(ROOT/'research/ts_funding')]
from run_experiment import load_frozen,write
from reference import transition,legal_nomination,scalar_score
from candidate import funding_pairs
import numpy as np


def audit(ids,gw,scorer,players,f):
    nom=scorer.decision(gw,ids);positions=tuple(players[p]['position']for p in ids)
    if not legal_nomination(ids,positions,nom[:4]):raise ValueError('Illegal nomination')
    weeks={p['id']:next(w for w in p['weeks']if w['gw']==gw)for p in f['players']if p['id']in ids}
    points=np.asarray([weeks[p]['scenarios']['points']for p in ids]).T
    minutes=np.asarray([weeks[p]['scenarios']['minutes']for p in ids]).T
    independent=scalar_score(ids,positions,points,minutes,nom[:4])
    if abs(independent-nom[-1])>1e-8:raise ValueError('Scalar scorer disagreement')
    return nom


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--input',type=Path,required=True);parser.add_argument('--case',type=Path,required=True);parser.add_argument('--frozen-root',type=Path,required=True);parser.add_argument('--arm',choices=['baseline','candidate','keep'],required=True);parser.add_argument('--out',type=Path,required=True);a=parser.parse_args()
    planner,season,scoring,live,config,_=load_frozen(a.frozen_root)
    f=json.loads(gzip.decompress(a.input.read_bytes()));case=json.loads(a.case.read_text())
    players={p['id']:dict(position=p['position'],team=p['team_id'],price=p['price_tenths'])for p in f['players']}
    ids=tuple(case['initial_ids']);initial=season.ReplayState({p:season.OwnedPlayer(p,int(case['purchase_prices'][str(p)]))for p in ids},case['bank'],case['free_transfers'])
    before=asdict(initial);meta,origin=live.project(f);gws=f['gws'];purchases=tuple(sorted((p,int(case['purchase_prices'][str(p)]))for p in ids));bank=case['bank'];ft=case['free_transfers'];objective=0.;path=[]
    with scoring.preview_scoring(f)as scorer:
        plan_start=time.perf_counter()
        if a.arm=='keep':result=None
        elif a.arm=='candidate':
            with funding_pairs(planner):result=planner.plan_transfer_path(initial,meta,origin,gws[0],config)
        else:result=planner.plan_transfer_path(initial,meta,origin,gws[0],config)
        planner_seconds=time.perf_counter()-plan_start
        if asdict(initial)!=before:raise ValueError('Input state mutated')
        if result and len(result.path)!=6:raise ValueError('Incomplete path')
        for index,gw in enumerate(gws):
            action=result.path[index]if result else None
            selected=tuple(sorted((set(dict(purchases))-set(action.outgoing))|set(action.incoming)))if action else tuple(sorted(dict(purchases)))
            if not planner.valid_squad(meta,set(selected)):raise ValueError('Illegal squad')
            move=transition(purchases,bank,ft,selected,players)
            if move is None:raise ValueError('Unaffordable transition')
            after,outgoing,incoming,hits,paid=move
            if action:
                expected=dict(outgoing=outgoing,incoming=incoming,bank_before=bank,bank_after=after[1],free_transfers_before=ft,free_transfers_after=after[2],official_hit_points=hits,uncertainty_penalty=paid*config.hit_uncertainty_buffer)
                if any(getattr(action,k)!=v for k,v in expected.items()):raise ValueError('State accounting disagreement')
                if action.transfers!=len(incoming)or action.transfers>config.max_transfers_per_week:raise ValueError('Transfer count disagreement')
            nom=audit(selected,gw,scorer,players,f);score=nom[-1]
            if action and max(abs(action.projected_manager_score-score),abs(action.utility_this_gw-(score-hits-paid*config.hit_uncertainty_buffer)))>1e-8:raise ValueError('Path score disagreement')
            objective+=config.weights[index]*score-hits-paid*config.hit_uncertainty_buffer
            path.append(dict(gw=gw,ids=selected,nomination=nom,action=asdict(action)if action else None,bank_after=after[1],ft_after=after[2],hits=hits))
            purchases,bank,ft=after
        if result and abs(result.objective-objective)>1e-8:raise ValueError('Objective disagreement')
    output=dict(status='completed',arm=a.arm,objective=objective,path=path,planner_seconds=planner_seconds,worker_seconds=time.perf_counter()-START,peak_rss_kib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,illegal=0,scorer_disagreements=0)
    write(a.out,output)
if __name__=='__main__':main()

"""Exact replay fingerprint for behavior-preserving scoring cleanup."""
import argparse,gzip,hashlib,json
from dataclasses import asdict,replace
from pathlib import Path
import numpy as np
from test_separated_goal_head import decode
from fpl_v1_1_model.joint_simulator import simulate_match,simulate_many


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--tasks',type=Path,required=True);ap.add_argument('--out',type=Path,required=True);ap.add_argument('--reference',type=Path);ap.add_argument('--preview',action='store_true');args=ap.parse_args()
    tasks=json.loads(gzip.open(args.tasks,'rt').read());receipts=[]
    for season,fx,seed,data,dist,factors,conditional in tasks[::3][:100]:
        inp=decode(data);inp=replace(inp,experimental_conditional_penalties=True,players=tuple(replace(p,goal_weight=factors[p.player_id],penalty_fallback_weight=p.goal_weight)for p in inp.players))
        rng=np.random.default_rng(seed);h=hashlib.sha256()
        for _ in range(20):
            trace={};result=simulate_match(inp,rng,trace=trace)
            payload={'players':{k:asdict(v)for k,v in result.items()},'trace':trace,'rng':rng.bit_generator.state}
            h.update(json.dumps(payload,sort_keys=True,separators=(',',':')).encode())
        aggregate=simulate_many(inp,n=20,seed=seed)
        h.update(json.dumps(aggregate,sort_keys=True,separators=(',',':')).encode())
        if args.preview:
            from pm_preview_distributions import simulate_with_distributions
            preview=simulate_with_distributions(inp,n=20,seed=seed,include_samples=True)
            h.update(json.dumps(preview,sort_keys=True,separators=(',',':')).encode())
        receipts.append(dict(season=season,fixture=fx,sha256=h.hexdigest()))
    result=dict(fixtures=len(receipts),match_draws=2000,aggregate_draws=2000,receipts=receipts)
    if args.preview:result['preview_draws']=2000
    if args.reference:
        reference=json.loads(args.reference.read_text())
        if reference!=result:raise ValueError('Scoring refactor changed replay results or random state')
        print('EXACT PARITY:',len(receipts),'fixtures, all player fields, intervals, RNG state and aggregate outputs')
    args.out.write_text(json.dumps(result,indent=2)+'\n')

if __name__=='__main__':main()

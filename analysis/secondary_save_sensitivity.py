"""Analytic + finite-N sensitivity of the B keeper reserve, audit only."""
import argparse
import ast
import inspect
import json
from dataclasses import replace
from pathlib import Path
import numpy as np
from fpl_v1_1_model import b_event_simulator as B
from fpl_v1_1_model.joint_simulator import MatchSimInput,PlayerSimInput


def reserve_simulator(regular_save_mean, *, baseline=False):
    tree=ast.parse(inspect.getsource(B.simulate_match))
    class Reserve(ast.NodeTransformer):
        def visit_If(self,node):
            if ast.unparse(node.test)=='p.is_keeper':
                code=('save_reserve=attempts[opp]*(1-conversion[opp])*np.clip(inp.p_penalty_save_given_miss,0,1)\nregular=max(0,p.lambda_saves-save_reserve)*m/90\nr.saves+=legacy._sample_calibrated_saves(rng,regular,p.save_bucket_tilts)' if baseline else 'regular = _regular_save_mean(inp,p,intervals,attempts,conversion)\nr.saves += legacy._sample_calibrated_saves(rng,regular,p.save_bucket_tilts)')
                node.body=ast.parse(code).body
                return node
            return self.generic_visit(node)
    tree=Reserve().visit(tree);ast.fix_missing_locations(tree)
    ns=dict(B.simulate_match.__globals__,_regular_save_mean=regular_save_mean)
    exec(compile(tree,'<audit-save-reserve-candidate>','exec'),ns)
    return ns['simulate_match']


def fixture(switch,lam,conversion):
    players=[]
    for team in ('h','a'):
        for i,pos in enumerate(['GK']+['DEF']*4+['MID']*4+['FWD']*2):
            players.append(PlayerSimInput(player_id=team+str(i),team=team,position=pos,p_start=1.,p_cameo_given_bench=0.,start_minutes_mean=90.,cameo_minutes_mean=15.,goal_weight=1.,assist_weight=1.,is_keeper=pos=='GK',lambda_saves=lam if pos=='GK' else 0.,penalty_weight=float(i==10),penalty_conversion=conversion[0],penalty_order=1 if i==10 else None))
    inp=MatchSimInput('h','a',2.,2.,tuple(players),lambda_home_penalties=1.,home_penalty_conversion=.78,p_penalty_save_given_miss=1.,experimental_penalty_hierarchy=True,bps_rules='2025-26')
    t={p.player_id:(90,0,90) for p in players}
    # Taker always switches. Optional keeper switch is perfectly aligned, to
    # expose conditional subtraction rather than a pooled team-mean check.
    reserve=replace(players[10],player_id='h11',penalty_conversion=conversion[1],p_start=0.)
    inp=replace(inp,players=inp.players+(reserve,));t['h10']=(45,0,45);t['h11']=(45,45,90)
    if switch:
        reserve=replace(players[11],player_id='a11',p_start=0.)
        inp=replace(inp,players=inp.players+(reserve,));t['a0']=(45,0,45);t['a11']=(45,45,90)
    return inp,t


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--out',type=Path,required=True);parser.add_argument('--draws',type=int,default=10000);a=parser.parse_args()
    from fpl_v1_1_model.experimental_keeper_save_reserve import regular_save_mean
    candidate=reserve_simulator(regular_save_mean)
    baseline=reserve_simulator(regular_save_mean,baseline=True)
    rows=[]
    for switch in (False,True):
        for lam in (0.,2.):
            for conv in ((.1,.9),(.9,.1),(.5,.5)):
                inp,t=fixture(switch,lam,conv)
                intervals={p:(x[1],x[2]) for p,x in t.items()}
                conversion={'h':sum(conv)/2,'a':conv[0]};attempts={'h':1.,'a':0.}
                for p in [p for p in inp.players if p.team=='a' and p.is_keeper]:
                    start,end=intervals[p.player_id];fraction=(end-start)/90
                    pen=sum(max(0,min(end,b)-max(start,c))/90*(1-v) for c,b,v in ((0,45,conv[0]),(45,90,conv[1])))
                    old=max(0.,lam-(1-conversion['h']))*fraction
                    new=regular_save_mean(inp,p,intervals,attempts,conversion)
                    rows.append(dict(switch=switch,lambda_saves=lam,conversion=list(conv),player=p.player_id,target=lam*fraction,expected_penalty_saves=pen,baseline_expected_saves=old+pen,candidate_expected_saves=new+pen,feasible_target=max(lam*fraction,pen),regular_old=old,regular_new=new))
                # Simulate key stress cases; analytic checks cover all 12 cases.
                if conv!=(.1,.9):continue
                for arm,fn in [('baseline',baseline),('candidate',candidate)]:
                    rng=np.random.default_rng(20261101)
                    values={p.player_id:[] for p in inp.players if p.team=='a' and p.is_keeper}
                    for _ in range(a.draws):
                        result=fn(inp,rng,timeline=t)
                        for pid in values:
                            r=result[pid];values[pid].append([r.saves,r.saves//3,5*r.penalty_saves,r.bonus,r.bps])
                    for pid,vals in values.items():
                        z=np.asarray(vals);row=next(r for r in rows if r['switch']==switch and r['lambda_saves']==lam and r['conversion']==list(conv) and r['player']==pid)
                        means=z.mean(axis=0);se=z.std(axis=0,ddof=1)/np.sqrt(a.draws)
                        row[arm+'_simulation']=dict(draws=a.draws,mean_saves=means[0],saves_mcse=se[0],save_points=means[1],penalty_save_points=means[2],bonus=means[3],bps=means[4],p3=float((z[:,0]>=3).mean()),p6=float((z[:,0]>=6).mean()),p9=float((z[:,0]>=9).mean()))
    a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_text(json.dumps(rows,indent=2)+'\n')
    print('sensitivity complete',len(rows),'keeper scenarios',flush=True)

if __name__=='__main__':main()

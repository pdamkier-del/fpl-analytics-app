"""Paired historical B source/event repair replay, isolated from locked benchmarks."""
import argparse,copy,gzip,hashlib,inspect,json,os,sqlite3,time
from pathlib import Path
from contextlib import nullcontext
from dataclasses import replace
from concurrent.futures import ProcessPoolExecutor,as_completed
import numpy as np
import pandas as pd
from test_joint_role_pm import decode,histories
from build_current_b_inputs import historical_B_training
from joint_role_bridge import apply_assignment
from gk_joint_bridge import UNKNOWN
from fpl_v1_1_model.experimental_physical_timeline import PhysicalKernel,physical_sampler
from fpl_v1_1_model.b_event_simulator import conserved_events
from fpl_v1_1_model.joint_simulator import simulate_many
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'analysis/results/integrated-repair-20261031/pm'

def simulate_fixture(task,draws=400):
    season,fx,seed,data,old_dist,factors,_,new_data,new_dist=task
    base=decode(copy.deepcopy(data));new=decode(copy.deepcopy(new_data));rows=[];audits=[];kernels={}
    for arm,original,dist,repair in [('frozen_B',base,old_dist,False),('events_only',base,old_dist,True),('source_and_events',new,new_dist,True)]:
        inp=replace(original,experimental_conditional_penalties=True,players=tuple(replace(p,goal_weight=factors[p.player_id],penalty_fallback_weight=p.goal_weight)for p in original.players))
        key='new'if arm=='source_and_events'else'old'
        if key not in kernels:kernels[key]=PhysicalKernel(inp,dist)
        kernel=kernels[key]
        from gk_joint_bridge import marginals
        moments=dict(kernel.moments)
        for team in (inp.home_team,inp.away_team):
            keepers=[p for p in inp.players if p.team==team and p.is_keeper]
            for pid,mass in marginals(keepers).items():moments[pid]=dict(x=float(mass@np.arange(91)),p=next(p.p_start for p in keepers if p.player_id==pid),pmf=mass)
        with (conserved_events()if repair else nullcontext({}))as audit,physical_sampler(kernel):
            sim=simulate_many(inp,n=draws,seed=seed)
        for p in inp.players:
            if p.player_id.startswith(UNKNOWN):continue
            m=moments[p.player_id];r=sim[p.player_id]
            rows.append(dict(season=season,fixture_uuid=fx,player_uuid=p.player_id,team_id=int(p.team),arm=arm,xp=r['xPts'],xmins=m['x'],p=m['p'],goals=r['goal_points']/(10 if p.is_keeper else 6 if p.position=='DEF'else 5 if p.position=='MID'else 4),assists=r['assist_points']/3,analytic_own_goals=p.p_own_goal*(1-m['pmf'][0])))
        audits.append(dict(season=season,fixture_uuid=fx,arm=arm,events=audit))
    return rows,audits

def evaluate(task,draws=400):
    from dataclasses import asdict
    code_names=['src/fpl_v1_1_model/b_event_simulator.py','src/fpl_v1_1_model/joint_simulator.py','src/fpl_v1_1_model/experimental_physical_timeline.py','src/fpl_v1_1_model/point_accounting.py']
    content=json.dumps(dict(task=task,draws=draws,engine={n:hashlib.sha256((ROOT/n).read_bytes()).hexdigest()for n in code_names},function=inspect.getsource(simulate_fixture)),default=asdict,sort_keys=True).encode()
    key=hashlib.sha256(content).hexdigest();folder=Path(os.environ.get('B_REPAIR_CACHE',ROOT/'work/integrated-b-replay-cache'));folder.mkdir(parents=True,exist_ok=True);path=folder/(key+'.json.gz')
    if path.exists():return json.loads(gzip.decompress(path.read_bytes()))
    result=simulate_fixture(task,draws)
    data=gzip.compress(json.dumps(result,allow_nan=False).encode(),mtime=0);temp=folder/(key+f'.{os.getpid()}.tmp');temp.write_bytes(data);temp.replace(path)
    return result

def main():
    OUT.mkdir(parents=True,exist_ok=True)
    ap=argparse.ArgumentParser();ap.add_argument('--tasks',type=Path);ap.add_argument('--smoke',action='store_true');args=ap.parse_args()
    if args.tasks:
        tasks=json.loads(gzip.open(args.tasks,'rt').read())
    else:
        from test_separated_goal_head import prepare_tasks
        tasks,_=prepare_tasks(json.loads((ROOT/'analysis/results/nonpenalty-goal-head-20261023/final-v2/model.json').read_text()),OUT)
    (OUT/'protocol.json').write_text(json.dumps(dict(draws=400,cohort='Both seasons GW22-38; reused research cohort',arms=['frozen_B','events_only','source_and_events'],task_sha256=hashlib.sha256(args.tasks.read_bytes()).hexdigest()if args.tasks else None,historical_medical_change_included=False,locked_models_changed=False),indent=2)+'\n')
    old=historical_B_training();new=pd.read_csv(ROOT/'analysis/results/integrated-repair-20261031/workload/predictions.csv.gz');new=new[new.arm.eq('all_comp_workload')]
    with sqlite3.connect(f'file:{ROOT/"work/core.sqlite3"}?mode=ro',uri=True)as db:core=pd.read_sql_query("SELECT * FROM player_fixture_observations WHERE is_final=1 AND season IN ('2024-25','2025-26')",db)
    if 'fpl_assists'not in core:raise ValueError('Missing authoritative FPL assists')
    core['assists']=core.fpl_assists
    history=histories(core);prepared=[]
    transported=pd.read_csv(ROOT/'analysis/results/joint-role-candidate-20261022/predictions.csv.gz',low_memory=False)
    for task in tasks:
        season,fx,seed,data,dist,factors,conditional=task
        frozen_rows=transported[transported.season.eq(season)&transported.fixture_uuid.eq(fx)].copy()
        frozen,dist,_=apply_assignment(frozen_rows,history[season],strength=.5)
        checked=frozen.set_index('player_uuid')
        for p in data['players']:
            if not p['is_keeper'] and abs(p['p_start']-checked.loc[p['player_id'],'p'])>1e-6:raise ValueError('Frozen role distribution differs from sealed task')
        task=(season,fx,seed,data,dist,factors,conditional)
        g=old[old.season.eq(season)&old.fixture_uuid.eq(fx)].copy();n=new[new.season.eq(season)&new.fixture_uuid.eq(fx)].set_index('player_uuid')
        if set(g.player_uuid)!=set(n.index):raise ValueError('Historical repaired roster mismatch')
        for c in ['p','q','s','c','x']:g[c]=g.player_uuid.map(n[c])
        adjusted,newdist,_=apply_assignment(g,history[season],strength=.5);by=adjusted.set_index('player_uuid');inp=decode(copy.deepcopy(data))
        # Empirical GK hierarchy/durations are retained, not replaced by raw GK logits.
        updated=replace(inp,players=tuple(p if p.is_keeper else replace(p,p_start=float(by.loc[p.player_id,'p']),p_cameo_given_bench=float(by.loc[p.player_id,'q']),start_minutes_mean=float(by.loc[p.player_id,'s']),cameo_minutes_mean=float(by.loc[p.player_id,'c']))for p in inp.players))
        from dataclasses import asdict
        prepared.append((*task,asdict(updated),newdist))
        if len(prepared)%25==0:print('Prepared integrated fixtures',len(prepared),flush=True)
    if args.smoke:
        print(evaluate(prepared[0],draws=10));return
    rows=[];audits=[]
    with ProcessPoolExecutor(max_workers=4)as pool:
        for i,f in enumerate(as_completed([pool.submit(evaluate,t)for t in prepared])):
            r,a=f.result();rows.extend(r);audits.extend(a)
            if (i+1)%10==0:print('Integrated PM replay',i+1,'/',len(prepared),flush=True)
    frame=pd.DataFrame(rows).merge(core[['season','fixture_uuid','player_uuid','minutes','started','total_points','goals','assists']],on=['season','fixture_uuid','player_uuid'],validate='many_to_one',suffixes=('','_actual'))
    frame=frame.sort_values(['season','fixture_uuid','player_uuid','arm']).reset_index(drop=True)
    audits=sorted(audits,key=lambda r:(r['season'],r['fixture_uuid'],r['arm']))
    if frame.total_points.isna().any():raise ValueError('Missing actual points')
    frame.to_csv(OUT/'predictions.csv.gz',index=False,compression={'method':'gzip','mtime':0})
    reference=pd.read_csv(ROOT/'analysis/results/physical-timeline-20261024/predictions.csv.gz');reference=reference[reference.arm.eq('candidate')]
    proof=frame[frame.arm.eq('frozen_B')].merge(reference,on=['season','fixture_uuid','player_uuid'],suffixes=('','_reference'),validate='one_to_one')
    baseline_error=float(abs(proof.xp-proof.xp_reference).max())
    if len(proof)!=len(reference)or baseline_error>1e-9:raise ValueError('Frozen physical B historical baseline not reproduced: '+str(baseline_error))
    metrics=[]
    for(season,arm),g in frame.groupby(['season','arm']):
        metrics.append(dict(season=season,arm=arm,rows=len(g),fixtures=g.fixture_uuid.nunique(),start_Brier=float(((g.p-g.started)**2).mean()),minute_MAE=float(abs(g.xmins-g.minutes).mean()),minute_bias=float((g.xmins-g.minutes).mean()),xp_MAE=float(abs(g.xp-g.total_points).mean()),xp_bias=float((g.xp-g.total_points).mean()),goal_bias=float((g.goals-g.goals_actual).mean()),assist_bias=float((g.assists-g.assists_actual).mean())))
    result=dict(scope='Both seasons GW22-38, reused research periods; same inclusive team means, NP weights and penalty hierarchy. Historical workload source subset and clock proxies. Medical return and persistent departures require separate current-source diagnostics.',fixtures=len(prepared),draws=400,baseline_max_xp_error=baseline_error,metrics=metrics,production_changed=False)
    (OUT/'result.json').write_text(json.dumps(result,indent=2)+'\n');(OUT/'event-receipts.json.gz').write_bytes(gzip.compress(json.dumps(audits).encode(),mtime=0));print(json.dumps(result,indent=2))
if __name__=='__main__':main()

"""Fixed offline attack-budget ablation. Never imported by live MM/PM/TS.

A one-node AST copy lets the research simulator use team-specific assist
probabilities. The original module/file is not edited. Exact identity is checked
before scoring when both teams use the existing common probability.
"""
import argparse,ast,copy,gzip,hashlib,inspect,json,math,sqlite3
from concurrent.futures import ProcessPoolExecutor,as_completed
from contextlib import contextmanager
from dataclasses import replace
from pathlib import Path
import numpy as np
import pandas as pd
from scipy.special import gammaln
from test_separated_goal_head import decode,UNKNOWN
from fpl_v1_1_model.experimental_physical_timeline import PhysicalKernel,physical_sampler
from fpl_v1_1_model import joint_simulator as joint
ROOT=Path(__file__).resolve().parents[1]
ARMS={'current':1.,'blend50':.5,'individual':0.,'smoothed_assist':1.}

@contextmanager
def team_assists(probabilities):
    original=joint.simulate_match;tree=ast.parse(inspect.getsource(original))
    class Replace(ast.NodeTransformer):
        count=0
        def visit_Attribute(self,node):
            if isinstance(node.value,ast.Name)and node.value.id=='inp'and node.attr=='assist_probability_per_goal':
                self.count+=1
                return ast.copy_location(ast.Call(func=ast.Name(id='_research_apg',ctx=ast.Load()),args=[ast.Name(id='inp',ctx=ast.Load()),ast.Name(id='team',ctx=ast.Load())],keywords=[]),node)
            return self.generic_visit(node)
    edit=Replace();tree=edit.visit(tree);assert edit.count==1;ast.fix_missing_locations(tree)
    namespace=dict(original.__globals__);namespace['_research_apg']=lambda inp,team:probabilities.get(str(team),inp.assist_probability_per_goal)
    exec(compile(tree,'<offline-team-assist-ablation>','exec'),namespace)
    joint.simulate_match=namespace[original.__name__]
    try:yield
    finally:joint.simulate_match=original

def expected_exposure(inp,kernel):
    from gk_joint_bridge import marginals
    masses={}
    for t in [inp.home_team,inp.away_team]:masses.update(marginals([p for p in inp.players if p.team==t and p.is_keeper]))
    return {p.player_id:(float(masses[p.player_id]@np.arange(91))/90 if p.is_keeper else kernel.moments[p.player_id]['x']/90)for p in inp.players}

def alter(inp,exposure,rates,alpha,apg):
    players=list(inp.players);newplayers={};means={};probs={};notes=[]
    for team,lam,pen,conversion in [(inp.home_team,inp.lambda_home_goals,inp.lambda_home_penalties,inp.home_penalty_conversion),(inp.away_team,inp.lambda_away_goals,inp.lambda_away_penalties,inp.away_penalty_conversion)]:
        ps=[p for p in players if p.team==team];e=np.array([exposure[p.player_id]for p in ps]);g=np.array([p.goal_weight for p in ps])*e;a=np.array([p.assist_weight for p in ps])*e
        pk=np.array([p.penalty_weight for p in ps])*e;pk=pk/pk.sum()if pk.sum()else g/g.sum()
        conv=sum(pk[i]*p.penalty_conversion for i,p in enumerate(ps))if inp.experimental_conditional_penalties else conversion
        penalty=pen*conv;ordinary=max(0.,lam-penalty)
        gs=g/g.sum()if g.sum()else np.zeros(len(g));ass=a/a.sum()if a.sum()else np.zeros(len(a))
        individual_g=np.array([rates[p.player_id][0]for p in ps])*e;individual_a=np.array([rates[p.player_id][1]for p in ps])*e
        mixed_g=alpha*ordinary*gs+(1-alpha)*individual_g
        mixed_a=alpha*ordinary*apg*ass+(1-alpha)*individual_a
        totalg=float(mixed_g.sum());totala=float(mixed_a.sum());prob=min(1.,totala/max(totalg,1e-12));probs[str(team)]=prob;means[str(team)]=totalg+penalty
        notes.append(dict(team=str(team),base_total_goals=lam,new_total_goals=means[str(team)],raw_assist_budget=totala,attainable_assist_budget=min(totala,totalg),assist_probability=prob,raw_assists_above_goal_budget=totala>totalg+1e-10))
        for i,p in enumerate(ps):
            # Simulator conditions recipients on the actual on-pitch XI.
            newplayers[p.player_id]=replace(p,goal_weight=float(mixed_g[i]/max(e[i],1e-12)),assist_weight=float(mixed_a[i]/max(e[i],1e-12)))
    return replace(inp,lambda_home_goals=means[str(inp.home_team)],lambda_away_goals=means[str(inp.away_team)],players=tuple(newplayers[p.player_id]for p in players)),probs,notes

def evaluate(task):
    season,fx,seed,data,dist,factors,conditional,rates,smoothed=task
    raw=decode(copy.deepcopy(data));base=replace(raw,experimental_conditional_penalties=True,players=tuple(replace(p,goal_weight=factors[p.player_id],penalty_fallback_weight=p.goal_weight)for p in raw.players))
    kernel=PhysicalKernel(base,dist);e=expected_exposure(base,kernel);rows=[];audits=[]
    # Test research extension identity against the original full point results.
    if seed==IDENTITY_SEEDS[season]:
        with physical_sampler(kernel):one=joint.simulate_many(base,n=32,seed=seed)
        with team_assists({}),physical_sampler(kernel):two=joint.simulate_many(base,n=32,seed=seed)
        assert one==two,'Research extension changes original simulation'
    for arm,alpha in ARMS.items():
        if arm=='current':inp=base;probs={};notes=[];k=kernel
        else:inp,probs,notes=alter(base,e,rates,alpha,smoothed if arm=='smoothed_assist'else base.assist_probability_per_goal);k=PhysicalKernel(inp,dist)
        assert all(abs(k.moments[p.player_id]['x']-kernel.moments[p.player_id]['x'])<1e-9 for p in inp.players if not p.is_keeper)
        with team_assists(probs),physical_sampler(k):result=joint.simulate_many(inp,n=400,seed=seed)
        for p in inp.players:
            if p.player_id.startswith(UNKNOWN):continue
            s=result[p.player_id];gp=10 if p.is_keeper else 6 if p.position=='DEF'else 5 if p.position=='MID'else 4
            rows.append(dict(season=season,fixture_uuid=fx,player_uuid=p.player_id,arm=arm,xp=s['xPts'],pred_goals=s['goal_points']/gp,pred_assists=s['assist_points']/3,pred_bonus=s['expected_bonus'],xmins=e[p.player_id]*90,position=p.position,p_start=p.p_start))
        audits.extend(dict(season=season,fixture_uuid=fx,arm=arm,**n)for n in notes)
    return rows,audits

IDENTITY_SEEDS={}
def main():
    ap=argparse.ArgumentParser();ap.add_argument('--out',type=Path,required=True);ap.add_argument('--tasks',type=Path,default=Path('/workspace/scratch/simple-market-tasks.json.gz'));ap.add_argument('--workers',type=int,default=2);ap.add_argument('--limit',type=int);ap.add_argument('--calibrated-reference',type=Path);args=ap.parse_args();
    global ARMS
    if args.calibrated_reference:ARMS={'blend50_calibrated':.5,'individual_calibrated':0.}
    out=args.out;out.mkdir(parents=True,exist_ok=True)
    if not args.tasks.is_file():
        from test_separated_goal_head import prepare_tasks
        fitted=json.loads((ROOT/'analysis/results/nonpenalty-goal-head-20261023/final-v2/model.json').read_text());generated,_=prepare_tasks(fitted,out);args.tasks.parent.mkdir(parents=True,exist_ok=True);args.tasks.write_bytes(gzip.compress(json.dumps(generated).encode(),mtime=0))
    protocol=dict(research_only=True,arms=ARMS,definitions={'current':'Existing NP scorer weights, team goal means, common historical assist probability and physical MM kernel','individual':'Player NP rates and individually shrunk xA set attack budgets; coherent team scores are their sums plus separate penalty process','blend50':'Equal mixture of team-normalized and individual expected ordinary-goal/assist masses, no weight tuning','smoothed_assist':'Current architecture; assist probability shrunk with 50 prior-goal observations from earlier seasons'},draws=400,MM='Identical analytical physical kernel in every arm; sampled means can fluctuate',cohort='Both seasons GW22-38, previously used research cohort; not independent validation',selection='Fixed four-arm diagnostic; no player-specific tuning or live promotion',metrics='xP RMSE primary, MAE guardrail; bias, goals/assists Poisson NLL+MAE and bonus MAE; fixture-cluster paired bootstrap',known_limits=['Historical availability clocks are proxies','Normal timeline has no red-card removals or concussion process','Individual xA is not the same target as FPL assists','Assist probability capped at 1 to preserve one assist per ordinary goal','Team goal changes affect clean sheets and bonus jointly','No TS activation or backtested transfer policy benefit claimed'],task_sha256=hashlib.sha256(args.tasks.read_bytes()).hexdigest())
    protocol['individual_assist_conversion']='Prefix-only FPL-assists/xA ratio, shrunk with 50 xA to earlier-season ratio' if args.calibrated_reference else 'Unconverted xA sensitivity; not target-equivalent to FPL assists'
    (out/'protocol.json').write_text(json.dumps(protocol,indent=2)+'\n')
    tasks=json.loads(gzip.open(args.tasks,'rt').read());rates=pd.read_csv(ROOT/'analysis/results/simple-market-model-20261025/rate-audit.csv.gz').set_index(['season','fixture_uuid','player_uuid'])
    with sqlite3.connect(f'file:{ROOT/"work/core.sqlite3"}?mode=ro',uri=True)as db:core=pd.read_sql_query('SELECT * FROM player_fixture_observations WHERE is_final=1',db)
    core['known']=pd.to_datetime(core.kickoff_at,utc=True)+pd.to_timedelta(np.where(core.season.eq('2025-26'),3,4),unit='h')
    records={}
    for season in ['2024-25','2025-26']:
        for line in gzip.open(ROOT/f'analysis/results/general-conversion-20261020/{season}_prepared.jsonl.gz','rt'):
            r=json.loads(line);records[season,r['core_fixture']]=r
    if args.limit:tasks=tasks[:args.limit]
    prepared=[];cache={}
    for task in tasks:
        season,fx,seed,data,dist,factors,conditional=task;IDENTITY_SEEDS.setdefault(season,seed);cut=pd.Timestamp(records[season,fx]['cutoff']);key=(season,str(cut))
        if key not in cache:
            past=core[core.known.lt(cut)];current=past[past.season.eq(season)].sort_values(['known','fixture_uuid']);pop=current.groupby('fpl_position')[['xa','minutes']].sum();by={str(k):v for k,v in current.groupby('player_uuid')};prior=past[past.season<season];pg=float(prior.goals.sum());pa=float(prior.fpl_assists.sum());priorp=min(1.,max(.5,pa/pg))if pg else .7;ng=float(current.goals.sum());old=data['assist_probability_per_goal'];smooth=(ng*old+50*priorp)/(ng+50);priorxa=float(prior.xa.sum());prior_conversion=pa/priorxa if priorxa>0 else 1.;conversion=(float(current.fpl_assists.sum())+50*prior_conversion)/(float(current.xa.sum())+50);cache[key]=(pop,by,smooth,conversion)
        pop,by,smooth,conversion=cache[key];rr={}
        for p in data['players']:
            pid=p['player_id']
            if pid.startswith(UNKNOWN):rr[pid]=(0.,0.);continue
            np_rate=float(rates.loc[(season,fx,pid),'nonpenalty_rate90']);pos=p['position'];pos='GKP'if pos=='GK'and 'GKP'in pop.index else pos;prior=pop.loc[pos];h=by.get(pid,current.iloc[:0]if 'current'in locals()else core.iloc[:0]);w=np.exp2(-np.arange(len(h)-1,-1,-1)/28.106996692019756);num=float(w@h.xa);den=float(w@h.minutes);tau=365.22361910394244;ar=90*(num+tau*float(prior.xa/prior.minutes))/(den+tau);rr[pid]=(np_rate,ar*conversion if args.calibrated_reference else ar)
        prepared.append((*task,rr,smooth))
    print('Prepared',len(prepared),'fixtures',flush=True);rows=[];audits=[]
    with ProcessPoolExecutor(max_workers=args.workers)as pool:
        for i,future in enumerate(as_completed([pool.submit(evaluate,t)for t in prepared])):
            r,a=future.result();rows.extend(r);audits.extend(a)
            if (i+1)%10==0:print('Completed',i+1,'/',len(prepared),flush=True)
    pred=pd.DataFrame(rows).merge(core[['season','fixture_uuid','player_uuid','minutes','total_points','goals','fpl_assists','bonus']],on=['season','fixture_uuid','player_uuid'],how='left',validate='many_to_one');assert pred.total_points.notna().all();
    if args.calibrated_reference:
        saved=pd.read_csv(args.calibrated_reference,float_precision='round_trip');saved=saved[saved.arm.eq('current')].drop(columns=['baseline_xp'],errors='ignore');assert set(map(tuple,saved[['season','fixture_uuid']].drop_duplicates().to_numpy()))==set(map(tuple,pred[['season','fixture_uuid']].drop_duplicates().to_numpy()));pred=pd.concat([pred,saved],ignore_index=True)
    reference=pred[pred.arm.eq('current')][['season','fixture_uuid','player_uuid','xp']].rename(columns={'xp':'baseline_xp'});pred=pred.merge(reference,on=['season','fixture_uuid','player_uuid'],validate='many_to_one');pred.to_csv(out/'predictions.csv.gz',index=False);pd.DataFrame(audits).to_csv(out/'budget-audit.csv.gz',index=False)
    metrics=[]
    for (season,arm),g in pred.groupby(['season','arm']):
        for cohort,sub in [('all',g),('played',g[g.minutes.gt(0)]),('attack',g[g.position.isin(['MID','FWD'])]),('high_forecast',g[g.baseline_xp.ge(5)])]:
            if sub.empty:continue
            e=sub.xp-sub.total_points;row=dict(season=season,arm=arm,cohort=cohort,rows=len(sub),xp_mae=float(abs(e).mean()),xp_rmse=float(np.sqrt((e*e).mean())),xp_bias=float(e.mean()),bonus_mae=float(abs(sub.pred_bonus-sub.bonus).mean()))
            for name,target in [('goals','goals'),('assists','fpl_assists')]:
                mu=np.maximum(sub['pred_'+name],1e-9);y=sub[target];row[name+'_mae']=float(abs(mu-y).mean());row[name+'_bias']=float((mu-y).mean());row[name+'_nll']=float((mu-y*np.log(mu)+gammaln(y+1)).mean())
            metrics.append(row)
    pd.DataFrame(metrics).to_csv(out/'metrics.csv',index=False);print(pd.DataFrame(metrics).query("cohort=='all'").to_string(index=False),flush=True)
    bootstrap=[]
    rng=np.random.default_rng(20261031)
    for season,g in pred.groupby('season'):
        g=g.assign(abs_error=abs(g.xp-g.total_points),squared_error=(g.xp-g.total_points)**2)
        by=g.groupby(['fixture_uuid','arm']).agg(ae=('abs_error','sum'),se=('squared_error','sum'),n=('xp','size'))
        for arm in ARMS:
            if arm=='current':continue
            a=by.xs(arm,level='arm');b=by.xs('current',level='arm');assert a.index.equals(b.index)
            delta=[]
            for _ in range(1000):
                ids=rng.integers(len(a),size=len(a));aa=a.iloc[ids].sum();bb=b.iloc[ids].sum();delta.append([float((aa.ae-bb.ae)/aa.n),float(np.sqrt(aa.se/aa.n)-np.sqrt(bb.se/bb.n))])
            ci=np.quantile(delta,[.025,.975],axis=0)
            bootstrap.append(dict(season=season,arm=arm,MAE_delta_ci95=ci[:,0].tolist(),RMSE_delta_ci95=ci[:,1].tolist(),fixture_clusters=len(a)))
    (out/'bootstrap.json').write_text(json.dumps(bootstrap,indent=2)+'\n')
    decision=dict(production_changed=False,live_promotion=False,fixtures=len(prepared),players_per_arm=int(len(pred)/pred.arm.nunique()),identity_extension_exact=True,MM_kernel_unchanged=True,metrics=metrics,independent_holdout=False)
    (out/'decision.json').write_text(json.dumps(decision,indent=2)+'\n')
if __name__=='__main__':main()

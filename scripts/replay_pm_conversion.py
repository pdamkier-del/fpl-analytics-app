#!/usr/bin/env python3
"""Full original-PM A/B, frozen MM first; separate empirical-MM interaction arm."""
import argparse,copy,hashlib,json,os,sqlite3,sys
from pathlib import Path
from contextlib import ExitStack
from dataclasses import asdict
from concurrent.futures import ProcessPoolExecutor,as_completed
import numpy as np,pandas as pd
from scipy.special import gammaln
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT/'src'),str(ROOT/'scripts')]
import research_pm_conversion as research
from audit_capture_io import checked_records,write_records,write_frame
from audit_correctness_historical import decode
from experiment_mm_pm import POINT_COMPONENTS
from fpl_v1_1_model.experimental_pm_conversion import event_weights,shadow_joint_assists,poisson_deviance
from fpl_v1_1_model.experimental_survival_sampler import shadow_survival_sampler
from fpl_v1_1_model import joint_simulator as simulator


def simulate_observed(inp,seed,draws=400):
    """Collect event probabilities while retaining the unchanged simulator/RNG."""
    original=simulator.simulate_match;count={p.player_id:dict(goals=0,assists=0,goal_event=0,assist_event=0,bps=0.,bps_n=0) for p in inp.players}
    def observe(data,rng):
        result=original(data,rng)
        for pid,r in result.items():
            c=count[pid];c['goals']+=r.goals;c['assists']+=r.assists;c['goal_event']+=int(r.goals>0);c['assist_event']+=int(r.assists>0)
            if r.minutes>0:c['bps']+=r.bps;c['bps_n']+=1
        return result
    simulator.simulate_match=observe
    try:sim=simulator.simulate_many(inp,n=draws,seed=seed)
    finally:simulator.simulate_match=original
    for pid,c in count.items():
        sim[pid].update(goal_mean=c['goals']/draws,assist_mean=c['assists']/draws,p_goal=(c['goal_event']+.5)/(draws+1),p_assist=(c['assist_event']+.5)/(draws+1),bps_mean=c['bps']/draws)
    return sim


def evaluate(task):
    index,record,cache,fingerprint=task;signature=hashlib.sha256(json.dumps(dict(record=record,fingerprint=fingerprint),sort_keys=True).encode()).hexdigest();path=Path(cache)/f'{index:04d}.jsonl.gz'
    if path.exists():
        cached=checked_records(path)[0]
        if cached['signature']==signature:return cached['rows']
    rows=[]
    for mode,data in record['inputs'].items():
        inp=decode(copy.deepcopy(data))
        with ExitStack() as stack:
            if mode=='joint_hierarchy':diag=stack.enter_context(shadow_joint_assists())
            else:diag=dict(applied=0,fallback=0)
            if mode.startswith('mm_'):stack.enter_context(shadow_survival_sampler(record['hazards']))
            sim=simulate_observed(inp,record['seed'])
        if mode=='original' and any(sim[pid]['xPts']!=v for pid,v in record['reference'].items()):raise ValueError('Original point reference not exact')
        for p in inp.players:
            if p.player_id not in record['reference']:continue
            s=sim[p.player_id]
            if not np.isclose(sum(s[k] for k in POINT_COMPONENTS),s['xPts'],rtol=0,atol=1e-10):raise ValueError('Point components do not sum')
            team_lam=inp.lambda_home_goals if p.team==inp.home_team else inp.lambda_away_goals
            rows.append(dict(fixture_uuid=record['core_fixture'],gw=record['origin'],mode=mode,player_uuid=p.player_id,pos=p.position,team_id=int(p.team),xp=s['xPts'],goal_mu=s['goal_mean'],assist_mu=s['assist_mean'],p_goal=s['p_goal'],p_assist=s['p_assist'],bps_mean=s['bps_mean'],sim_minutes=s['expected_minutes'],team_lambda=team_lam,**{k:s[k] for k in POINT_COMPONENTS},**{k:s[k] for k in ['p_bonus_1','p_bonus_2','p_bonus_3']},joint_applied=diag['applied'],joint_fallback=diag['fallback']))
    write_records(path,[dict(signature=signature,rows=rows)])
    return rows


def paired_ci(frame,value,base='original'):
    ref=frame[frame['mode'].eq(base)][['fixture_uuid','player_uuid',value]]
    result={};rng=np.random.default_rng(20261015)
    for mode,g in frame.groupby('mode'):
        p=g.merge(ref,on=['fixture_uuid','player_uuid'],validate='one_to_one',suffixes=('','_baseline'));delta=p[value]-p[value+'_baseline']
        b=pd.DataFrame(dict(fixture=p.fixture_uuid,d=delta)).groupby('fixture').d.agg(['sum','size']).to_numpy();draw=b[rng.integers(len(b),size=(2000,len(b)))].sum(1)
        result[mode]=dict(delta=float(delta.mean()),fixture_bootstrap_95_ci=np.quantile(draw[:,0]/draw[:,1],[.025,.975]).tolist())
    return result


def metrics(g):
    e=g.xp-g.total_points;out=dict(rows=len(g),mae=float(abs(e).mean()),rmse=float(np.sqrt((e*e).mean())),bias=float(e.mean()),mean_xp=float(g.xp.mean()),mean_actual=float(g.total_points.mean()),bonus_mae=float(abs(g.expected_bonus-g.bonus).mean()),bonus_bias=float((g.expected_bonus-g.bonus).mean()),point_components={k:float(g[k].mean()) for k in POINT_COMPONENTS})
    for event,col,prob in [('goals','goal_mu','p_goal'),('fpl_assists','assist_mu','p_assist')]:
        y=g[event].to_numpy();mu=np.maximum(g[col].to_numpy(),1e-12);p=g[prob].to_numpy();yes=(y>0).astype(float)
        out[event]=dict(mae=float(abs(mu-y).mean()),rmse=float(np.sqrt(((mu-y)**2).mean())),bias=float((mu-y).mean()),poisson_nll=float((mu-y*np.log(mu)+gammaln(y+1)).mean()),brier=float(((p-yes)**2).mean()),binary_log_loss=float(-(yes*np.log(p)+(1-yes)*np.log1p(-p)).mean()),mean_pred=float(mu.mean()),mean_actual=float(y.mean()))
        bins=pd.cut(g[col],[-np.inf,0,.05,.1,.2,.4,.8,np.inf]);out[event]['calibration']=[dict(bin=str(k),rows=len(v),pred=float(v[col].mean()),actual=float(v[event].mean())) for k,v in g.groupby(bins,observed=True)]
    bins=pd.cut(g.xp,[-np.inf,0,1,2,3,4,5,6,8,np.inf]);out['xp_calibration']=[dict(bin=str(k),rows=len(v),pred=float(v.xp.mean()),actual=float(v.total_points.mean())) for k,v in g.groupby(bins,observed=True)]
    return out


def summarize(p):
    result={}
    for mode,g in p.groupby('mode'):
        result[mode]=metrics(g);result[mode]['played']=metrics(g[g.minutes.gt(0)]);result[mode]['by_position']={k:metrics(v) for k,v in g.groupby('pos')}
    q=p.copy();q['point_abs_error']=abs(q.xp-q.total_points);q['goal_logloss']=-(q.goals.gt(0)*np.log(q.p_goal)+q.goals.eq(0)*np.log1p(-q.p_goal));q['assist_logloss']=-(q.fpl_assists.gt(0)*np.log(q.p_assist)+q.fpl_assists.eq(0)*np.log1p(-q.p_assist))
    comparisons={k:paired_ci(q,k) for k in ['point_abs_error','goal_logloss','assist_logloss']}
    if 'mm_original' in set(q['mode']):comparisons['point_abs_error_within_experimental_MM']=paired_ci(q[q['mode'].str.startswith('mm_')],'point_abs_error',base='mm_original')
    return dict(metrics=result,paired=comparisons)


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--season',required=True);ap.add_argument('--inputs',required=True);ap.add_argument('--mm-root',default='analysis/results/mm-research-20261014');ap.add_argument('--out',default='analysis/results/pm-research-20261015');ap.add_argument('--db',default='work/core.sqlite3');ap.add_argument('--workers',type=int,default=2);ap.add_argument('--arm',choices=['locked','mm'],default='locked');ap.add_argument('--limit',type=int,default=0);a=ap.parse_args();out=Path(a.out);out.mkdir(parents=True,exist_ok=True)
    configs=json.loads((out/'selection.json').read_text())['selected'];obs,teams,names,audit=research.observations(a.db);cuts=research.deadlines(Path(a.mm_root));records=research.target_records(a.inputs,a.db,a.season)
    if a.limit:records=records[:a.limit]
    hazards={}
    if a.arm=='mm':
        for r in checked_records(Path(a.mm_root)/f'{a.season}_starter_hazards.jsonl.gz'):hazards.setdefault(r['gw'],{})[r['player_uuid']]=r['hazard']
    states={};prepared=[]
    for record in records:
        inp=decode(copy.deepcopy(record['input']));cut=cuts[a.season][record['origin']];factors={}
        for family,cfg in configs.items():
            key=(record['origin'],cfg['half'])
            if key not in states:states[key]=research.weighted_states(obs,cut,a.season,cfg['half'])
            factors[family]=research.factors(inp,states[key],cfg['tau'],hierarchical=family=='hierarchy',team_tau=cfg['team_tau'])
        gf,af=factors['goal'][0],factors['assist'][1];hg,ha=factors['hierarchy']
        if a.arm=='locked':
            inputs=dict(original=inp,xg_only=research.pure_xg_input(inp,obs,cut,a.season),finishing=event_weights(inp,gf),assist_conversion=event_weights(inp,assist_factor=af),hierarchy=event_weights(inp,hg,ha),combined=event_weights(inp,gf,af),team_finishing=event_weights(inp,gf,change_total=True),joint_hierarchy=event_weights(inp,hg,ha))
        else:
            mm=decode(copy.deepcopy(record['candidate_inputs']['combined']));inputs=dict(mm_original=mm,mm_combined=event_weights(mm,gf,af),mm_hierarchy=event_weights(mm,hg,ha));h={}
            for gw in sorted(hazards):
                if gw<=record['origin']:h.update(hazards[gw])
            record['hazards']=h
        record['inputs']={k:asdict(v) for k,v in inputs.items()};record.pop('candidate_inputs',None);prepared.append(record)
    write_records(out/f'{a.season}_{a.arm}_inputs.jsonl.gz',prepared)
    cache=out/f'cache_{a.season}_{a.arm}';cache.mkdir(exist_ok=True)
    from importlib.metadata import version
    fingerprint=dict(script=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),candidate=hashlib.sha256((ROOT/'src/fpl_v1_1_model/experimental_pm_conversion.py').read_bytes()).hexdigest(),original_simulator=hashlib.sha256((ROOT/'src/fpl_v1_1_model/joint_simulator.py').read_bytes()).hexdigest(),numpy=version('numpy'),scipy=version('scipy'))
    rows=[]
    with ProcessPoolExecutor(max_workers=a.workers) as pool:
        tasks=[pool.submit(evaluate,(i,r,str(cache),fingerprint)) for i,r in enumerate(prepared)]
        for i,future in enumerate(as_completed(tasks)):
            rows.extend(future.result())
            if (i+1)%10==0:print('PM conversion',a.season,a.arm,i+1,'/',len(prepared),flush=True)
    truth=obs[obs.season.eq(a.season)][['fixture_uuid','player_uuid','goals','fpl_assists','total_points','minutes','bonus']]
    p=pd.DataFrame(rows).merge(truth,on=['fixture_uuid','player_uuid'],how='left',validate='many_to_one')
    if p[['goals','fpl_assists','total_points','minutes','bonus']].isna().any().any():raise ValueError('Missing truth; no imputation allowed')
    # MM-only arm must be paired to its own unchanged PM baseline.
    if a.arm=='mm':p['mode']=p['mode'].replace({'mm_original':'original','mm_combined':'combined','mm_hierarchy':'hierarchy'})
    team_truth=teams[teams.season.eq(a.season)][['fixture_uuid','team_id','gf']]
    t=p.groupby(['mode','fixture_uuid','team_id'],as_index=False).team_lambda.first().merge(team_truth,on=['fixture_uuid','team_id'],validate='many_to_one')
    team_report={mode:dict(sides=len(g),mae=float(abs(g.team_lambda-g.gf).mean()),poisson_deviance=float(poisson_deviance(g.gf,g.team_lambda).mean()),mean_pred=float(g.team_lambda.mean()),mean_actual=float(g.gf.mean())) for mode,g in t.groupby('mode')}
    write_frame(out/f'{a.season}_{a.arm}_predictions.csv.gz',p)
    report=dict(classification='ORIGINAL_PM_CONVERSION_SHADOW_WITH_'+a.arm.upper()+'_MM',season=a.season,arm=a.arm,fixtures=len(prepared),original_exact=a.arm=='locked',draws=400,selection=configs,team_goal_metrics=team_report,results={'all':summarize(p),'GW22_38':summarize(p[p.gw.ge(22)])},joint_diagnostics=p[p['mode'].eq('joint_hierarchy')].groupby('fixture_uuid')[['joint_applied','joint_fallback']].first().sum().to_dict(),source_sha256=hashlib.sha256(Path(a.inputs).read_bytes()).hexdigest(),fingerprint=fingerprint,locked_model_active=False,promotion_allowed=False,limitations=['Reused baseline-development seasons; historical publication proxies','All-xG includes penalties: effective calibration, not identified NPG finishing','FPL-assist/xA ratios mix receiver conversion and special assist rules','No failed-shot creator/receiver links; joint maximum-entropy is not learned pair chemistry','Original penalty/own-goal assist limitations and independent XI physics retained for controlled PM isolation','Binary event probabilities use Jeffreys Monte Carlo smoothing (.5)/(n+1); Poisson count NLL is a diagnostic count approximation','Fixture bootstrap does not include all simulation noise; no certified new TS season total'])
    (out/f'{a.season}_{a.arm}_report.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(dict(season=a.season,arm=a.arm,fixtures=len(prepared),team_goal_metrics=team_report,results={period:{mode:{k:r[k] for k in ['rows','mae','rmse','bias','goals','fpl_assists','bonus_mae']} for mode,r in value['metrics'].items()} for period,value in report['results'].items()}),indent=2))
if __name__=='__main__':main()

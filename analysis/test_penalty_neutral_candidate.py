"""Fixed no-tuning scorer-boundary candidate on the existing joint-role B replay."""
import argparse,copy,gzip,json,sqlite3,hashlib
from pathlib import Path
from dataclasses import replace,asdict
from concurrent.futures import ProcessPoolExecutor,as_completed
import pandas as pd
import numpy as np
from fpl_v1_1_model.experimental_penalty_neutral import PenaltyNeutralState
from fpl_v1_1_model.role_event_priors import QCOLS
from fpl_v1_1_model.experimental_joint_role_assignment import role_lineup_sampler
from fpl_v1_1_model.joint_simulator import simulate_many
from test_joint_role_pm import decode,histories,observations,DurationHistory,prepare,prepare_match,apply_assignment,UNKNOWN

ROOT=Path(__file__).resolve().parents[1]

def evaluate(task):
    season,fx,seed,data,dist,factors,conditional=task;rows=[]
    base=decode(copy.deepcopy(data))
    for arm in ['baseline','candidate']:
        inp=base if arm=='baseline'else replace(base,players=tuple(replace(p,goal_weight=p.goal_weight*factors[p.player_id])for p in base.players))
        if arm=='candidate' and conditional:inp=replace(inp,experimental_conditional_penalties=True)
        with role_lineup_sampler(dist):result=simulate_many(inp,n=400,seed=seed)
        for p in inp.players:
            if p.player_id.startswith(UNKNOWN):continue
            s=result[p.player_id];rows.append(dict(season=season,fixture_uuid=fx,player_uuid=p.player_id,arm=arm,xp=s['xPts'],sim_minutes=s['expected_minutes'],goals=s['goal_points']/(4 if p.position=='FWD'else 6 if p.position in ['DEF','GK','GKP']else 5),bonus=s['expected_bonus']))
    return rows


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--out',type=Path,required=True);parser.add_argument('--workers',type=int,default=2);parser.add_argument('--conditional-penalties',action='store_true');parser.add_argument('--conditional-only',action='store_true');args=parser.parse_args();out=args.out;out.mkdir(parents=True,exist_ok=True)
    protocol={'candidate':'Remove verified penalty attempts from FPL-scale historical xG (.79 each); rebuild both individual and predeadline soft-role priors; multiply only ordinary scorer weights by resulting nonpenalty/inclusive rate ratio. Keep learned predictive performance covariates/coefs frozen.','source':'2024/25 native shotmap penalty counts; 2025/26 recorded scored+missed counts, no xG-gap inference; all 380 matches per season audited','selection':'No tuning, no player-specific thresholds. Fixed single candidate.','period':'2024/25 GW22-38 and 2025/26 GW6-38, reused research diagnostics','draws':400,'gate':'xP MAE delta <= .005 each season, played MAE delta <= .02, abs bias increase <= .02; penalty-taker subgroup abs bias must improve and MAE not worsen > .02','production_changed':False}
    if args.conditional_only and not args.conditional_penalties:raise ValueError('Conditional-only requires conditional flag')
    protocol['conditional_only']=args.conditional_only
    if args.conditional_only:protocol['candidate']='Only align expected penalty conversion with the active taker law; retain inclusive scorer weights and every other input'
    protocol['conditional_penalties']=args.conditional_penalties
    protocol['conditional_change']='Subtract penalty goal expectation using the actual interval-specific on-pitch taker conversion; occurrence and taker laws unchanged' if args.conditional_penalties else None
    (out/'protocol.json').write_text(json.dumps(protocol,indent=2)+'\n')
    with sqlite3.connect(f'file:{ROOT/"work/core.sqlite3"}?mode=ro',uri=True)as db:core=pd.read_sql_query("SELECT * FROM player_fixture_observations WHERE is_final=1 AND season IN ('2024-25','2025-26')",db)
    core['available_at']=pd.to_datetime(core.kickoff_at,utc=True)+pd.to_timedelta(np.where(core.season.eq('2024-25'),4,3),unit='h')
    features={'2024-25':pd.read_csv(ROOT/'analysis/results/penalty-neutral-sources-20261023/predeadline-roles-2024.csv.gz',low_memory=False),'2025-26':pd.read_csv(ROOT/'analysis/results/workload-recovered-v4/all_features.csv.gz',low_memory=False)}
    attempts=pd.read_csv(ROOT/'analysis/results/penalty-neutral-sources-20261023/verified-attempts.csv')[['season','fixture_uuid','player_uuid','attempts']]
    attack=json.loads((ROOT/'analysis/results/joint-component-recovery-v1/player_attack_fit.json').read_text())
    transport=pd.read_csv(ROOT/'analysis/results/joint-role-candidate-20261022/predictions.csv.gz',low_memory=False)
    rolehistory=histories(core);obs=observations(ROOT);duration={};tasks=[];rate_audits=[]
    for season in ['2024-25','2025-26']:
        src=features[season];roles=src[['fixture_uuid','player_uuid','team_id','cutoff','max_history_known_at']+QCOLS].copy()
        state=PenaltyNeutralState(core[core.season.eq(season)],attempts[attempts.season.eq(season)],roles,attack)
        records=[json.loads(line)for line in gzip.open(ROOT/f'analysis/results/general-conversion-20261020/{season}_prepared.jsonl.gz','rt')]
        states={};factor_cache={}
        for r in records:
            origin=r['origin'];cut=pd.Timestamp(r['cutoff'])
            if origin not in states:states[origin]=src[src.gw.le(origin)].sort_values(['gw','cutoff'],kind='stable').drop_duplicates('player_uuid',keep='last').set_index('player_uuid')
            saved=states[origin];inp=decode(copy.deepcopy(r['input']))
            if origin not in factor_cache:
                target=[];cohort=[r0 for r0 in records if r0['origin']==origin]
                for r0 in cohort:
                    if pd.Timestamp(r0['cutoff'])!=cut:raise ValueError('Mixed origin cutoff')
                    for p in r0['input']['players']:
                        pid=p['player_id']
                        if pid not in saved.index:raise ValueError('Missing original target role state')
                        q=saved.loc[pid]
                        target.append(dict(fixture_uuid=r0['core_fixture'],player_uuid=pid,team_id=int(p['team']),pos=p['position'],max_history_known_at=q.max_history_known_at,**{c:q[c]for c in QCOLS}))
                factors,audit=state.factors(pd.DataFrame(target),cut,season);audit['season']=season;rate_audits.append(audit);factor_cache[origin]=factors
            factors=factor_cache[origin]
            g=transport[transport.season.eq(season)&transport.fixture_uuid.eq(r['core_fixture'])].copy();alt,dist,_=apply_assignment(g,rolehistory[season],strength=.5)
            by=g.set_index('player_uuid');inp=replace(inp,players=tuple(replace(p,p_start=float(by.loc[p.player_id,'p']),p_cameo_given_bench=float(by.loc[p.player_id,'q']),start_minutes_mean=float(by.loc[p.player_id,'s']),cameo_minutes_mean=float(by.loc[p.player_id,'c']))for p in inp.players))
            clock=str(r['cutoff'])
            if clock not in duration:duration[clock]=DurationHistory(obs,clock)
            inp,_,_=prepare(inp,g,duration[clock]);inp=prepare_match(inp);by=alt.set_index('player_uuid');inp=replace(inp,players=tuple(p if p.is_keeper else replace(p,p_start=float(by.loc[p.player_id,'p']),p_cameo_given_bench=float(by.loc[p.player_id,'q']))for p in inp.players))
            ff={p.player_id:factors[r['core_fixture'],p.player_id]if not args.conditional_only and not p.player_id.startswith(UNKNOWN)else 1. for p in inp.players}
            tasks.append((season,r['core_fixture'],r['seed'],asdict(inp),dist,ff,args.conditional_penalties))
            if len(tasks)%30==0:print('Prepared penalty fixtures',len(tasks),flush=True)
    pd.concat(rate_audits,ignore_index=True).to_csv(out/'rate-audit.csv.gz',index=False)
    rows=[]
    with ProcessPoolExecutor(max_workers=args.workers)as pool:
        for i,future in enumerate(as_completed([pool.submit(evaluate,t)for t in tasks])):
            rows.extend(future.result())
            if (i+1)%20==0:print('Penalty PM fixtures',i+1,'/',len(tasks),flush=True)
    predictions=pd.DataFrame(rows).merge(core[['season','fixture_uuid','player_uuid','minutes','total_points']],on=['season','fixture_uuid','player_uuid'],validate='many_to_one',how='left')
    if predictions.total_points.isna().any():raise ValueError('Missing actual points')
    reference=pd.read_csv(ROOT/'analysis/results/joint-role-candidate-20261022/pm-predictions.csv.gz');reference=reference[reference.arm.eq('candidate')]
    match=predictions[predictions.arm.eq('baseline')].merge(reference,on=['season','fixture_uuid','player_uuid'],validate='one_to_one',suffixes=('_new','_old'))
    maxerror=float(abs(match.xp_new-match.xp_old).max())
    if maxerror!=0:raise ValueError('Frozen current-B historical baseline not exactly reproduced: '+str(maxerror))
    predictions.to_csv(out/'predictions.csv.gz',index=False);metrics=[];passed=True
    takers={s:set(attempts[attempts.season.eq(s)].player_uuid)for s in ['2024-25','2025-26']}
    for season,g in predictions.groupby('season'):
        for cohort,sub in [('all',g),('played',g[g.minutes.gt(0)]),('takers',g[g.player_uuid.isin(takers[season])])]:
            v={}
            for arm,a in sub.groupby('arm'):
                error=a.xp-a.total_points;v[arm]=dict(mae=float(abs(error).mean()),bias=float(error.mean()),rows=len(a));metrics.append(dict(season=season,cohort=cohort,arm=arm,**v[arm]))
            tolerance=.005 if cohort=='all'else .02
            passed &=v['candidate']['mae']-v['baseline']['mae']<=tolerance and abs(v['candidate']['bias'])-abs(v['baseline']['bias'])<= (.0 if cohort=='takers'else .02)
    pd.DataFrame(metrics).to_csv(out/'metrics.csv',index=False)
    (out/'decision.json').write_text(json.dumps(dict(passed=bool(passed),fixtures=len(tasks),baseline_max_xp_error=maxerror,metrics=metrics,production_changed=False,independent_certification=False),indent=2)+'\n');print('Penalty candidate historical gate',bool(passed),flush=True)

if __name__=='__main__':main()

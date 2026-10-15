#!/usr/bin/env python3
"""Player-first PM v2: cutoff profiles, development selection, original PM replay."""
import argparse,copy,hashlib,json,sqlite3,sys
from pathlib import Path
from dataclasses import asdict
from contextlib import ExitStack
from concurrent.futures import ProcessPoolExecutor,as_completed
import numpy as np,pandas as pd
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT/'src'),str(ROOT/'scripts')]
import research_pm_conversion as old
from audit_capture_io import checked_records,write_records,write_frame
from audit_correctness_historical import decode
from replay_pm_conversion import simulate_observed,summarize
from experiment_mm_pm import POINT_COMPONENTS
from fpl_v1_1_model.experimental_survival_sampler import shadow_survival_sampler
from fpl_v1_1_model.experimental_player_pm import ProfileFit,team_context,historical_opponent_offsets,prepare,lineup_rates,expected_exposure,shadow_player_intensity
from fpl_v1_1_model.experimental_pm_conversion import poisson_deviance

LIMITS=['Reused development seasons, no pristine independent holdout','Historical publication uses kickoff+3/4h proxies, not source availability certification','Broad FPL roles only; no verified temporal tactical role or set-piece orders','All-xG contains penalties; finishing is effective calibration not isolated NPG skill','No failed-shot creator/receiver links: team creative elasticity is not pair chemistry','Original independent-XI, own-goal and special-assist limitations retained to isolate PM','Conditional EB/quasi-Poisson intervals omit parameter/context/MM uncertainty','Fixture bootstrap does not include all Monte Carlo uncertainty','No historical six-GW candidate TS replay or live certification']


def save(path,value):
    Path(path).parent.mkdir(parents=True,exist_ok=True);Path(path).write_text(json.dumps(value,indent=2,default=lambda x:x.item())+'\n')


def data(db):
    obs,teams,names,audit=old.observations(db)
    offsets=historical_opponent_offsets(obs)
    obs=obs.merge(offsets,on=['season','fixture_uuid','team_id'],validate='many_to_one')
    if obs.opponent_offset.isna().any():raise ValueError('Missing causal opponent offset')
    audit['fields']={c:dict(non_null=int(obs[c].notna().sum()),rows=len(obs)) for c in obs if c in ['xg','npxg','xa','shots','shots_on_target','big_chances_created','defcon_count','tackles','recoveries','bps','sub_on_second','sub_off_second']}
    audit['canonical_players']=int(obs.player_uuid.nunique());audit['roles']=obs.fpl_position.value_counts().to_dict()
    with sqlite3.connect(db) as c:
        audit['source_tables']=pd.read_sql_query("SELECT name FROM sqlite_master WHERE type='table'",c).name.tolist()
        audit['set_piece_by_season']=pd.read_sql_query('SELECT season,count(*) AS rows FROM set_piece_role_snapshots GROUP BY season',c).to_dict('records')
        audit['player_source_names']=obs.groupby(['season','source_name']).size().reset_index(name='rows').to_dict('records')
    audit['raw_sources_prior_audit']='docs/audits/2026-10-15-goal-assist-model-research.md: native 2024 shotmaps, source disagreement, missing failed-shot creator links; raw performance-ledger features already used by original allocator'
    return obs,teams,names,audit


def settings():
    return [dict(name=f'{family}_d{half}_n{strength}',family=family,half=half,strength=strength,hierarchical=family=='hier',anchor_weight=0.,creativity=0.,finishing=True) for family in ['simple','hier'] for half in ([365.] if family=='simple' else [180.,365.]) for strength in [5.,20.,80.]]


class Factory:
    def __init__(self,obs,season):self.obs=obs;self.season=season;self.fits={};self.contexts={};self.current_cut=None
    def build(self,inp,cut,cfg):
        if str(cut)!=self.current_cut:
            self.fits.clear();self.contexts.clear();self.current_cut=str(cut)
        key=(str(cut),cfg['half'],cfg['strength'],cfg['hierarchical'])
        if key not in self.fits:self.fits[key]=ProfileFit(self.obs,cut,self.season,cfg['half'],cfg['strength'],cfg['hierarchical'])
        contexts={}
        for team,opp,home in [(inp.home_team,inp.away_team,True),(inp.away_team,inp.home_team,False)]:
            k=(str(cut),str(team),str(opp),home)
            if k not in self.contexts:self.contexts[k]=team_context(self.obs,cut,self.season,int(team),int(opp),home)
            contexts[str(team)]=self.contexts[k]
        return prepare(inp,self.fits[key],contexts,cfg['anchor_weight'],cfg['creativity'],cfg['finishing'])


def screen(records,obs,teams,season,cuts,configs,development=False):
    factory=Factory(obs,season);rows=[]
    truth=obs[obs.season.eq(season)].groupby(['fixture_uuid','team_id'])[['xg','goals']].sum()
    for i,r in enumerate(records):
        if development and not 6<=r['origin']<=21:continue
        inp=decode(copy.deepcopy(r['input']));cut=cuts[season][r['origin']]
        for cfg in [None]+configs:
            mode='original' if cfg is None else cfg['name']
            if cfg is None:rates={str(inp.home_team):{'xg':inp.lambda_home_goals,'total':inp.lambda_home_goals},str(inp.away_team):{'xg':inp.lambda_away_goals,'total':inp.lambda_away_goals}}
            else:
                candidate,spec=factory.build(inp,cut,cfg);rates,_=lineup_rates(candidate,spec,{p.player_id:expected_exposure(p) for p in candidate.players})
            for team,rat in rates.items():
                y=truth.loc[(r['core_fixture'],int(team))];rows.append(dict(season=season,gw=r['origin'],fixture_uuid=r['core_fixture'],team_id=int(team),mode=mode,xg_pred=rat['xg'],goal_pred=rat['total'],xg=float(y.xg),goals=float(y.goals)))
        if (i+1)%50==0:print('Player PM analytic screen',season,i+1,flush=True)
    return pd.DataFrame(rows)


def screen_metrics(f):
    out={}
    for mode,g in f.groupby('mode'):
        out[mode]={}
        for target,col in [('xg','xg_pred'),('goals','goal_pred')]:
            e=g[col]-g[target];out[mode][target]=dict(mae=float(abs(e).mean()),rmse=float(np.sqrt((e*e).mean())),bias=float(e.mean()),deviance=float(poisson_deviance(g[target].to_numpy(),np.maximum(g[col],1e-12)).mean()))
    return out


def selection(args,obs,teams,audit,cuts):
    out=Path(args.out);r24=old.target_records(args.inputs2024,args.db,'2024-25');configs=settings()
    d=screen(r24,obs,teams,'2024-25',cuts,configs,True);m=screen_metrics(d);chosen={}
    for family in ['simple','hier']:
        cfg=min([c for c in configs if c['family']==family],key=lambda c:m[c['name']]['xg']['deviance']);chosen[family]=cfg
    hybrids=[]
    for h in [.25,.5,.75]:
        for beta in [0.,.25]:
            cfg=dict(chosen['hier'],name=f'hybrid_h{h}_b{beta}',family='hybrid',anchor_weight=h,creativity=beta);hybrids.append(cfg)
    dd=screen(r24,obs,teams,'2024-25',cuts,hybrids,True);mm=screen_metrics(dd)
    chosen['hybrid']=min(hybrids,key=lambda c:mm[c['name']]['xg']['deviance'])
    scores={**m,**mm};selected=min(chosen,key=lambda k:scores[chosen[k]['name']]['xg']['deviance'])
    report=dict(classification='PLAYER_PM_V2_PREKICKOFF_DEVELOPMENT_SELECTION_NOT_FULL_PM',development='2024-25 GW6-21',objective='Mean team xG quasi-Poisson deviance; no target minutes/xG used in predictors',selected=chosen,experimental_mm_candidate=selected,development_scores=scores,audit=audit,limitations=LIMITS,locked_model_active=False,promotion_allowed=False)
    save(out/'selection.json',report)
    # Choice persisted BEFORE reading later season captures/evaluation metrics.
    r25=old.target_records(args.inputs2025,args.db,'2025-26');test24=screen(r24,obs,teams,'2024-25',cuts,list(chosen.values()));test25=screen(r25,obs,teams,'2025-26',cuts,list(chosen.values()))
    write_frame(out/'analytic_team_predictions.csv.gz',pd.concat([test24,test25]));save(out/'analytic_report.json',dict(protocol=report,results={'2024-25_GW22-38':screen_metrics(test24[test24.gw.ge(22)]),'2025-26_GW6-38':screen_metrics(test25)},limitations=LIMITS,locked_model_active=False,promotion_allowed=False))
    print(json.dumps(report,indent=2))


def evaluate(task):
    record,cache,fingerprint=task;sig=hashlib.sha256(json.dumps(dict(record=record,fingerprint=fingerprint),sort_keys=True).encode()).hexdigest();path=Path(cache)/(record['core_fixture']+'.jsonl.gz')
    if path.exists():
        oldcache=checked_records(path)[0]
        if oldcache['signature']==sig:return oldcache['rows'],oldcache['teams']
    rows=[];teams=[]
    for mode,item in record['candidates'].items():
        inp=decode(copy.deepcopy(item['input']));diag={}
        with ExitStack() as stack:
            if record['arm']=='mm':stack.enter_context(shadow_survival_sampler(record['hazards']))
            if item['spec'] is not None:stack.enter_context(shadow_player_intensity(item['spec'],diag))
            sim=simulate_observed(inp,record['seed'])
        if mode=='original' and record['arm']=='locked' and any(sim[pid]['xPts']!=v for pid,v in record['reference'].items()):raise ValueError('Locked PM reference mismatch')
        for team,anchor in [(inp.home_team,inp.lambda_home_goals),(inp.away_team,inp.lambda_away_goals)]:
            d=diag.get(str(team));teams.append(dict(fixture_uuid=record['core_fixture'],gw=record['origin'],mode=mode,team_id=int(team),xg_pred=d['xg_sum']/d['draws'] if d else anchor,goal_pred=d['goal_mean_sum']/d['draws'] if d else anchor,active_exposure=d['exposure_sum']/d['draws'] if d else None))
        for p in inp.players:
            if p.player_id not in record['reference']:continue
            s=sim[p.player_id]
            if not np.isclose(sum(s[k] for k in POINT_COMPONENTS),s['xPts'],atol=1e-10,rtol=0):raise ValueError('Point sum mismatch')
            profile=record['groups'][p.player_id]
            rows.append(dict(fixture_uuid=record['core_fixture'],gw=record['origin'],mode=mode,player_uuid=p.player_id,pos=p.position,team_id=int(p.team),xp=s['xPts'],goal_mu=s['goal_mean'],assist_mu=s['assist_mean'],p_goal=s['p_goal'],p_assist=s['p_assist'],bps_mean=s['bps_mean'],sim_minutes=s['expected_minutes'],**{k:s[k] for k in POINT_COMPONENTS},**{k:s[k] for k in ['p_bonus_1','p_bonus_2','p_bonus_3']},**profile))
    write_records(path,[dict(signature=sig,rows=rows,teams=teams)]);return rows,teams


def replay(args,obs,teams,cuts):
    out=Path(args.out);cfgs=json.loads((out/'selection.json').read_text());records=old.target_records(args.inputs,args.db,args.season);records=[r for i,r in enumerate(records) if i%args.shards==args.shard]
    if args.limit:records=records[:args.limit]
    factory=Factory(obs,args.season);hazards={}
    if args.arm=='mm':
        for r in checked_records(Path(args.mm_root)/f'{args.season}_starter_hazards.jsonl.gz'):hazards.setdefault(r['gw'],{})[r['player_uuid']]=r['hazard']
    prepared=[]
    for record in records:
        cut=cuts[args.season][record['origin']];inp=decode(copy.deepcopy(record['input'] if args.arm=='locked' else record['candidate_inputs']['combined']));choices=cfgs['selected'] if args.arm=='locked' else {cfgs['experimental_mm_candidate']:cfgs['selected'][cfgs['experimental_mm_candidate']]}
        candidates={'original':dict(input=asdict(inp),spec=None)};groups={}
        for mode,cfg in choices.items():
            candidate,spec=factory.build(inp,cut,cfg);candidates[mode]=dict(input=asdict(candidate),spec=spec)
            groups={pid:{k:p[k] for k in ['group','limited_history','club_change','role_change']} for pid,p in spec['profiles'].items()}
        h={}
        for gw in sorted(hazards):
            if gw<=record['origin']:h.update(hazards[gw])
        prepared.append(dict(core_fixture=record['core_fixture'],origin=record['origin'],arm=args.arm,cutoff=str(cut),seed=record['seed'],reference=record['reference'],candidates=candidates,hazards=h,groups=groups))
    label=f'{args.season}_{args.arm}_{args.shard}';write_records(out/(label+'_inputs.jsonl.gz'),prepared);cache=out/('cache_'+label);cache.mkdir(exist_ok=True)
    from importlib.metadata import version
    fingerprint=dict(source={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in ['scripts/research_player_pm_v2.py','src/fpl_v1_1_model/experimental_player_pm.py','src/fpl_v1_1_model/joint_simulator.py','scripts/replay_pm_conversion.py']},numpy=version('numpy'),scipy=version('scipy'))
    rows=[];tr=[]
    with ProcessPoolExecutor(max_workers=args.workers) as pool:
        futures=[pool.submit(evaluate,(r,str(cache),fingerprint)) for r in prepared]
        for i,f in enumerate(as_completed(futures)):
            a,b=f.result();rows.extend(a);tr.extend(b)
            if (i+1)%10==0:print('Player PM full',label,i+1,'/',len(prepared),flush=True)
    truth=obs[obs.season.eq(args.season)][['fixture_uuid','player_uuid','goals','fpl_assists','total_points','minutes','bonus','bps']]
    p=pd.DataFrame(rows).merge(truth,on=['fixture_uuid','player_uuid'],validate='many_to_one',how='left')
    if p[['goals','fpl_assists','total_points','minutes','bonus','bps']].isna().any().any():raise ValueError('Missing target, no imputation')
    teamtruth=obs[obs.season.eq(args.season)].groupby(['fixture_uuid','team_id'],as_index=False).xg.sum().merge(teams[teams.season.eq(args.season)][['fixture_uuid','team_id','gf']],on=['fixture_uuid','team_id'],validate='one_to_one')
    t=pd.DataFrame(tr).merge(teamtruth,on=['fixture_uuid','team_id'],validate='many_to_one');t['goals']=t.gf
    write_frame(out/(label+'_predictions.csv.gz'),p);write_frame(out/(label+'_teams.csv.gz'),t)
    save(out/(label+'_completion.json'),dict(fixtures=len(prepared),original_exact=args.arm=='locked',arm=args.arm,source_sha256=hashlib.sha256(Path(args.inputs).read_bytes()).hexdigest(),fingerprint=fingerprint,locked_model_active=False))


def team_report(f):
    result=screen_metrics(f);rng=np.random.default_rng(20261015)
    for mode,g in f.groupby('mode'):
        ref=f[f['mode'].eq('original')];pair=g.merge(ref,on=['fixture_uuid','team_id'],suffixes=('','_ref'),validate='one_to_one')
        for target,col in [('xg','xg_pred'),('goals','goal_pred')]:
            d=abs(pair[col]-pair[target])-abs(pair[col+'_ref']-pair[target]);blocks=pd.DataFrame(dict(fixture=pair.fixture_uuid,d=d)).groupby('fixture').d.agg(['sum','size']).to_numpy();b=blocks[rng.integers(len(blocks),size=(2000,len(blocks)))].sum(1)
            result[mode][target]['paired_mae_delta']=float(d.mean());result[mode][target]['fixture_bootstrap_95_ci']=np.quantile(b[:,0]/b[:,1],[.025,.975]).tolist()
    return result


def aggregate(args):
    out=Path(args.out);result={}
    for season in ['2024-25','2025-26']:
        result[season]={}
        for arm in ['locked','mm']:
            completions=[json.loads((out/f'{season}_{arm}_{i}_completion.json').read_text()) for i in range(args.shards)]
            if sum(c['fixtures'] for c in completions)!=330:raise ValueError('Incomplete seasonal matrix')
            p=pd.concat([pd.read_csv(out/f'{season}_{arm}_{i}_predictions.csv.gz') for i in range(args.shards)],ignore_index=True);t=pd.concat([pd.read_csv(out/f'{season}_{arm}_{i}_teams.csv.gz') for i in range(args.shards)],ignore_index=True)
            if p.duplicated(['fixture_uuid','player_uuid','mode']).any():raise ValueError('Duplicate shard rows')
            if season=='2024-25':p=p[p.gw.ge(22)];t=t[t.gw.ge(22)]
            groups={}
            from replay_pm_conversion import metrics
            for col in ['group','limited_history','club_change','role_change']:
                groups[col]={m:{str(k):metrics(g) for k,g in ff.groupby(col)}for m,ff in p.groupby('mode')}
            summary=dict(points=summarize(p),teams=team_report(t),groups=groups,completions=completions)
            result[season][arm]=summary
            save(out/f'{season}_{arm}_report.json',dict(classification='PLAYER_PM_V2_FULL_ORIGINAL_SCORING_REPLAY',results=summary,limitations=LIMITS,locked_model_active=False,promotion_allowed=False))
    save(out/'matrix_report.json',dict(classification='COMPLETE_PLAYER_PM_V2_RESEARCH_MATRIX',results=result,selection=json.loads((out/'selection.json').read_text()),limitations=LIMITS,locked_model_active=False,promotion_allowed=False))
    compact={s:{arm:dict(points={m:{k:v[k] for k in ['rows','mae','rmse','bias','goals','fpl_assists','bonus_mae','bps_mae']} for m,v in r['points']['metrics'].items()},paired=r['points']['paired'],teams=r['teams'])for arm,r in arms.items()}for s,arms in result.items()};save(out/'summary.json',compact);print(json.dumps(compact,indent=2))


def main():
    p=argparse.ArgumentParser();p.add_argument('--stage',choices=['audit','select','replay','aggregate'],required=True);p.add_argument('--db',default='work/core.sqlite3');p.add_argument('--out',default='analysis/results/player-pm-v2-20261015');p.add_argument('--inputs2024');p.add_argument('--inputs2025');p.add_argument('--inputs');p.add_argument('--mm-root',default='analysis/results/mm-research-20261014');p.add_argument('--season');p.add_argument('--arm',choices=['locked','mm'],default='locked');p.add_argument('--shards',type=int,default=4);p.add_argument('--shard',type=int,default=0);p.add_argument('--workers',type=int,default=2);p.add_argument('--limit',type=int,default=0);a=p.parse_args()
    if a.stage=='aggregate':aggregate(a);return
    obs,teams,names,audit=data(a.db)
    if a.stage=='audit':save(Path(a.out)/'data_audit.json',dict(audit=audit,limitations=LIMITS,locked_model_active=False));print(json.dumps(audit,indent=2));return
    cuts=old.deadlines(Path(a.mm_root))
    if a.stage=='select':selection(a,obs,teams,audit,cuts)
    else:replay(a,obs,teams,cuts)
if __name__=='__main__':main()

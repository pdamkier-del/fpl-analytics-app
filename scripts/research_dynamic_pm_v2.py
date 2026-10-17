#!/usr/bin/env python3
"""Frozen PM v2 profiles -> deadline-only gates -> controlled independent/legal XI."""
import argparse,copy,hashlib,json,sys
from pathlib import Path
from contextlib import ExitStack,contextmanager
from concurrent.futures import ProcessPoolExecutor,as_completed
import numpy as np,pandas as pd
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT/'src'),str(ROOT/'scripts')]
from audit_capture_io import checked_records,write_records,write_frame
from audit_correctness_historical import decode
from research_player_pm_v2 import save,team_report
from research_pm_conversion import observations
from replay_pm_conversion import simulate_observed,metrics,summarize,paired_ci
from experiment_mm_pm import POINT_COMPONENTS
from fpl_v1_1_model import joint_simulator as sim
from fpl_v1_1_model.experimental_player_pm import lineup_rates,expected_exposure,shadow_player_intensity
from fpl_v1_1_model.experimental_dynamic_pm import fit_gate,shadow_legal_minutes,shadow_team_weights
from fpl_v1_1_model.experimental_correctness_simulator import start_marginals
from fpl_v1_1_model.experimental_survival_sampler import shadow_survival_sampler
from fpl_v1_1_model.experimental_pm_conversion import poisson_deviance

BASE=ROOT/'work/dynamic-source';OUT=ROOT/'analysis/results/dynamic-pm-v2-20261015'
LIMITS=['Reused research seasons; no pristine holdout','Historical publication clocks remain kickoff+3/4h proxies','Frozen player profile hyperparameters selected in preceding 2024 development; no change to baseline','Gate training uses analytic expected-exposure xG forecasts, not full-simulator point loss','Profile variance is conditional EB and omits correlated role/MM/context uncertainty','All arms retain IDENTICAL original legacy own-goal/CS and special-assist scoring; no mixed correctness flags','Legal XI reuses existing sampler; vacancies may persist; survival zero-minute starter draws use existing one-minute floor','Return-from-absence proxy is not verified injury evidence','No complete six-GW candidate TS replay; locked2125 benchmark unchanged']


def one(pattern):
    p=list(BASE.rglob(pattern))
    if len(p)!=1:raise ValueError('Missing or ambiguous artifact '+pattern)
    return p[0]


def records(season,arm):
    r=[]
    for i in range(4):r.extend(checked_records(one(f'{season}_{arm}_{i}_inputs.jsonl.gz')))
    if len(r)!=330 or len({x['core_fixture'] for x in r})!=330:raise ValueError('Incomplete frozen captures')
    return sorted(r,key=lambda x:(x['cutoff'],x['core_fixture']))


def features(rs,obs,season,arm):
    rows=[];by={str(pid):g for pid,g in obs.groupby('player_uuid')};truth=obs[obs.season.eq(season)].groupby(['fixture_uuid','team_id']).agg(xg=('xg','sum'),known=('known','max'))
    for record in rs:
        item=record['candidates']['hybrid'];inp=decode(copy.deepcopy(item['input']));spec=item['spec'];cut=pd.Timestamp(record['cutoff']);e={p.player_id:expected_exposure(p) for p in inp.players}
        raw,_=lineup_rates(inp,dict(spec,anchor_weight=0.),e);anchor,_=lineup_rates(inp,dict(spec,anchor_weight=1.),e)
        for team in [inp.home_team,inp.away_team]:
            ps=[p for p in inp.players if p.team==team];pr=spec['profiles'];st=np.array([p.p_start for p in ps]);ex=np.array([e[p.player_id] for p in ps]);n=np.array([pr[p.player_id]['weighted_minutes']/90 for p in ps]);q=np.array([pr[p.player_id]['xg90']['mean'] for p in ps]);sd=np.array([pr[p.player_id]['xg90']['sd'] for p in ps]);context=spec['contexts'][str(team)];mult=context['opponent']*context['venue']
            qa=sum(pr[p.player_id]['xa90']['mean']*e[p.player_id] for p in ps)*mult
            creative=(qa/(context['xa_anchor']*mult))**spec['creativity'];variance=float(np.sum((ex*sd*mult*creative)**2));px=raw[str(team)]['xg'];tx=anchor[str(team)]['xg']
            h=obs[obs.season.eq(season)&obs.team_id.eq(int(team))&obs.known.lt(cut)];games=h.groupby(['fixture_uuid','known'],as_index=False).xg.sum().sort_values(['known','fixture_uuid']).tail(6);last=h[h.fixture_uuid.eq(games.fixture_uuid.iloc[-1])] if len(games) else h.iloc[:0];previous=set(last.loc[last.started.eq(1),'player_uuid']);missing=len(previous)!=11
            changed=1-sum(p.p_start for p in ps if p.player_id in previous)/max(st.sum(),1e-12) if not missing else 0.
            return_mass=0.
            for p in ps:
                g=by.get(p.player_id,obs.iloc[:0]);g=g[g.known.lt(cut)].sort_values(['known','fixture_uuid']);played=g[g.minutes.gt(0)]
                if len(g)>=2 and len(played) and g.tail(2).minutes.eq(0).all() and (cut-played.known.iloc[-1]).total_seconds()>=14*86400:return_mass+=p.p_start
            y=truth.loc[(record['core_fixture'],int(team))]
            row=dict(season=season,mm=arm,fixture_uuid=record['core_fixture'],gw=record['origin'],team_id=int(team),team_key=season+':'+str(team),cutoff=cut,known=y.known,xg=float(y.xg),player_xg=px,team_xg=tx,original_team_xg=float(inp.lambda_home_goals if team==inp.home_team else inp.lambda_away_goals),profile_variance=variance,log_minutes=float(np.log1p(st@n/max(st.sum(),1e-12))),coverage=float(st@(n>0)/max(st.sum(),1e-12)),relative_variance=variance/max(px*px,1e-12),new_fraction=float(st@(n<5)/max(st.sum(),1e-12)),club_fraction=float(sum(p.p_start*pr[p.player_id]['club_change'] for p in ps)/max(st.sum(),1e-12)),role_fraction=float(sum(p.p_start*pr[p.player_id]['role_change'] for p in ps)/max(st.sum(),1e-12)),lineup_change=float(changed),stability=float(games.xg.std(ddof=0)/max(games.xg.mean(),1e-12)) if len(games)>1 else 0.,disagreement=abs(px-tx)/max((px+tx)/2,1e-12),return_proxy=float(return_mass/max(st.sum(),1e-12)),lineup_missing=float(missing),stability_missing=float(len(games)<2))
            for k in [5,20,80]:
                reliability=n/(n+k);row['amount_'+str(k)]=float(st@reliability/max(st.sum(),1e-12));mass=ex*q;row['detail_'+str(k)]=float(mass@reliability/max(mass.sum(),1e-12))
            rows.append(row)
    f=pd.DataFrame(rows)
    if f.duplicated(['fixture_uuid','team_id']).any() or not np.isfinite(f.select_dtypes('number')).all().all():raise ValueError('Invalid gate features')
    return f


def configs():
    return [dict(name='fixed',family='fixed')]+[dict(name=f'{family}_{k}',family=family,k=k)for family,ks in [('minutes',[5,20,80]),('detailed',[5,20,80]),('uncertainty',[1,4,16]),('covariance',[.5,1.])]for k in ks]+[dict(name=f'learned_{hier}_{k}',family='learned',hierarchical=hier,k=k)for hier in [False,True]for k in [.1,1.,10.]]


def weights(frame,cfg,targets=None):
    rows=[]
    for _,target in (frame if targets is None else targets).iterrows():
        w,info=fit_gate(frame,target,cfg)
        if not 0<=w<=1 or not np.isfinite(w):raise ValueError('Invalid gate weight')
        if info.get('max_known') is not None and pd.Timestamp(info['max_known'])>=target.cutoff:raise ValueError('Gate leakage')
        rows.append(dict(fixture_uuid=target.fixture_uuid,team_id=int(target.team_id),gw=int(target.gw),w=w,mode=cfg['name'],xp_proxy=float(w*target.player_xg+(1-w)*target.team_xg),**info))
    return pd.DataFrame(rows)


def select(obs):
    rs=[r for r in records('2024-25','locked') if r['origin']<=21];f=features(rs,obs,'2024-25','locked');validation=f[f.gw.between(14,21)];scores=[];grid=configs()
    for cfg in grid:
        w=weights(f,cfg,validation).merge(validation[['fixture_uuid','team_id','xg']],on=['fixture_uuid','team_id'],validate='one_to_one');v=float(poisson_deviance(w.xg,np.maximum(w.xp_proxy,1e-12)).mean());scores.append(dict(config=cfg,xg_deviance=v,mae=float(abs(w.xp_proxy-w.xg).mean()),mean_w=float(w.w.mean())))
    chosen={}
    for name,families in [('amount',['minutes','detailed']),('uncertainty',['uncertainty']),('covariance',['covariance']),('learned',['learned'])]:chosen[name]=min([s for s in scores if s['config']['family'] in families],key=lambda s:s['xg_deviance'])['config']
    selected=min(chosen,key=lambda k:next(s['xg_deviance'] for s in scores if s['config']['name']==chosen[k]['name']))
    protocol=dict(classification='PREDEADLINE_DYNAMIC_GATE_DEVELOPMENT_SELECTION',source_run=38729720330,source_commit='852f23790ebb4769272b5c8e02b8b30a1794551a',base_profile='Frozen prior PM v2 hierarchy365days, strength5; prior selection reused2024GW6-21',development='2024GW6-13 warm prefix, GW14-21 chronological validation; all fitted labels known<deadline',objective='team xG quasi-Poisson deviance, no target lineup/minutes/results used in gate inputs',grid=scores,chosen=chosen,selected=selected,limitations=LIMITS,locked_model_active=False,promotion_allowed=False)
    save(OUT/'selection.json',protocol)
    # No later season captures are read before this protocol is persisted.
    all_features={};all_weights={}
    for arm in ['locked','mm']:
        ff=pd.concat([features(records(s,arm),obs,s,arm)for s in ['2024-25','2025-26']],ignore_index=True);all_features[arm]=ff;ww=[]
        for name,cfg in chosen.items():
            z=weights(ff,cfg);z['mode']=name;ww.append(z)
        all_weights[arm]=pd.concat(ww,ignore_index=True);write_frame(OUT/f'{arm}_features.csv.gz',ff);write_frame(OUT/f'{arm}_weights.csv.gz',all_weights[arm])
    print(json.dumps(protocol,indent=2))


def observe(inp,seed):
    original=sim.simulate_match;gc={p.player_id:0 for p in inp.players}
    def match(data,rng):
        result=original(data,rng)
        for pid,r in result.items():gc[pid]+=r.goals_conceded_while_on_pitch
        return result
    sim.simulate_match=match
    try:result=simulate_observed(inp,seed)
    finally:sim.simulate_match=original
    for pid,v in result.items():v['gc_mean']=gc[pid]/400
    return result


def evaluate(task):
    record,mode_weights,layout,mm,selected,cache,signature_base=task;sig=hashlib.sha256(json.dumps(dict(record=record,weights=mode_weights,layout=layout,mm=mm,signature=signature_base),sort_keys=True).encode()).hexdigest();path=Path(cache)/(record['core_fixture']+'.jsonl.gz')
    if path.exists():
        saved=checked_records(path)[0]
        if saved['signature']==sig:return saved
    modes=['original','fixed']+([selected]if layout=='independent' or mm=='mm' else ['amount','uncertainty','covariance','learned']);rows=[];teams=[];diagnostics=[]
    for mode in modes:
        item=record['candidates']['original' if mode=='original' else 'hybrid'];inp=decode(copy.deepcopy(item['input']));spec=item['spec'];diag={};ld={}
        if layout=='legal':
            marginal,projection=start_marginals(inp)
            base=decode(copy.deepcopy(record['candidates']['original']['input']));bm,_=start_marginals(base)
            if marginal!=bm:raise ValueError('PM changed feasible MM marginals')
        with ExitStack() as stack:
            if layout=='legal':stack.enter_context(shadow_legal_minutes(record.get('hazards') if mm=='mm' else None,ld))
            elif mm=='mm':stack.enter_context(shadow_survival_sampler(record['hazards']))
            if spec is not None:
                if mode!='fixed':stack.enter_context(shadow_team_weights(mode_weights[mode]))
                stack.enter_context(shadow_player_intensity(spec,diag))
            result=observe(inp,record['seed'])
        if layout=='independent' and mm=='locked' and mode=='original' and any(result[pid]['xPts']!=v for pid,v in record['reference'].items()):raise ValueError('Original locked reproduction failed')
        if layout=='independent' and mode=='fixed' and any(abs(result[pid]['xPts']-v)>1e-12 for pid,v in record['fixed_reference'].items()):raise ValueError('Prior fixed75 reference changed')
        if layout=='legal' and ld.get('legal_draws')!=400:raise ValueError('Legal draw coverage incomplete')
        diagnostics.append(dict(mode=mode,legal=ld,projection=projection if layout=='legal' else None))
        for team,anchor in [(inp.home_team,inp.lambda_home_goals),(inp.away_team,inp.lambda_away_goals)]:
            d=diag.get(str(team));w=.75 if mode=='fixed' else (mode_weights[mode][str(team)] if mode!='original' else 0.)
            teams.append(dict(fixture_uuid=record['core_fixture'],gw=record['origin'],mode=mode,team_id=int(team),xg_pred=d['xg_sum']/d['draws'] if d else anchor,goal_pred=d['goal_mean_sum']/d['draws'] if d else anchor,player_weight=w))
        for p in inp.players:
            v=result[p.player_id]
            if not np.isclose(sum(v[k] for k in POINT_COMPONENTS),v['xPts'],atol=1e-10,rtol=0):raise ValueError('Point reconciliation failed')
            rows.append(dict(fixture_uuid=record['core_fixture'],gw=record['origin'],mode=mode,player_uuid=p.player_id,pos=p.position,team_id=int(p.team),xp=v['xPts'],goal_mu=v['goal_mean'],assist_mu=v['assist_mean'],p_goal=v['p_goal'],p_assist=v['p_assist'],bps_mean=v['bps_mean'],sim_minutes=v['expected_minutes'],p_cs=v['p_clean_sheet_award'],gc_mean=v['gc_mean'],**{k:v[k] for k in POINT_COMPONENTS},**{k:v[k] for k in ['p_bonus_1','p_bonus_2','p_bonus_3']},**record['groups'][p.player_id]))
    saved=dict(signature=sig,rows=rows,teams=teams,diagnostics=diagnostics);write_records(path,[saved]);return saved


def replay(args,obs,team_truth):
    protocol=json.loads((OUT/'selection.json').read_text());rs=records(args.season,args.mm);rs=[r for i,r in enumerate(rs)if i%args.shards==args.shard]
    w=pd.read_csv(OUT/f'{args.mm}_weights.csv.gz');w=w.set_index(['fixture_uuid','mode','team_id']).w
    prior=pd.concat([pd.read_csv(one(f'{args.season}_{args.mm}_{i}_predictions.csv.gz'),usecols=['fixture_uuid','player_uuid','mode','xp'])for i in range(4)]);prior=prior[prior['mode'].eq('hybrid')]
    for r in rs:r['fixed_reference']=prior[prior.fixture_uuid.eq(r['core_fixture'])].set_index('player_uuid').xp.to_dict()
    label=f'{args.season}_{args.mm}_{args.layout}_{args.shard}';cache=OUT/('cache_'+label);cache.mkdir(exist_ok=True)
    from importlib.metadata import version
    fingerprint=dict(files={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest()for p in ['scripts/research_dynamic_pm_v2.py','src/fpl_v1_1_model/experimental_dynamic_pm.py','src/fpl_v1_1_model/experimental_player_pm.py','src/fpl_v1_1_model/experimental_correctness_simulator.py','src/fpl_v1_1_model/joint_simulator.py']},numpy=version('numpy'),scipy=version('scipy'))
    jobs=[]
    for r in rs:
        ww={mode:{str(t):float(w.loc[(r['core_fixture'],mode,int(t))])for t in [r['candidates']['original']['input']['home_team'],r['candidates']['original']['input']['away_team']]}for mode in protocol['chosen']};jobs.append((r,ww,args.layout,args.mm,protocol['selected'],str(cache),fingerprint))
    values=[]
    with ProcessPoolExecutor(max_workers=2)as pool:
        futures=[pool.submit(evaluate,x)for x in jobs]
        for i,future in enumerate(as_completed(futures)):
            values.append(future.result())
            if(i+1)%10==0:print('Dynamic PM',label,i+1,'/',len(jobs),flush=True)
    p=pd.DataFrame([r for v in values for r in v['rows']]);truth=obs[obs.season.eq(args.season)][['fixture_uuid','player_uuid','goals','fpl_assists','total_points','minutes','bonus','bps','goals_conceded_on_pitch']];p=p.merge(truth,on=['fixture_uuid','player_uuid'],how='left',validate='many_to_one')
    if p[['goals','fpl_assists','total_points','minutes','bonus','bps','goals_conceded_on_pitch']].isna().any().any():raise ValueError('Missing target; no imputation')
    p['actual_cs']=(p.minutes.ge(60)&p.goals_conceded_on_pitch.eq(0)).astype(int);p['cs_brier']=(p.p_cs-p.actual_cs)**2;p['gc_abs_error']=abs(p.gc_mean-p.goals_conceded_on_pitch)
    t=pd.DataFrame([r for v in values for r in v['teams']]);tx=obs[obs.season.eq(args.season)].groupby(['fixture_uuid','team_id'],as_index=False).xg.sum();tt=team_truth[team_truth.season.eq(args.season)][['fixture_uuid','team_id','gf']];t=t.merge(tx,on=['fixture_uuid','team_id'],validate='many_to_one').merge(tt,on=['fixture_uuid','team_id'],validate='many_to_one');t['goals']=t.gf
    write_frame(OUT/(label+'_predictions.csv.gz'),p);write_frame(OUT/(label+'_teams.csv.gz'),t);save(OUT/(label+'_completion.json'),dict(fixtures=len(jobs),layout=args.layout,mm=args.mm,source_commit='852f237',fingerprint=fingerprint,diagnostics=[x['diagnostics']for x in values],locked_model_active=False))


def summarize_against(p,reference):
    q=p.copy();q['point_abs_error']=abs(q.xp-q.total_points);q['squared_error']=(q.xp-q.total_points)**2
    return {k:paired_ci(q,k,base=reference)for k in ['point_abs_error','squared_error','cs_brier','gc_abs_error']}


def aggregate(args):
    report={};all_frames={}
    for season in ['2024-25','2025-26']:
        report[season]={}
        for mm,layout in [('locked','independent'),('locked','legal'),('mm','legal')]:
            paths=[OUT/f'{season}_{mm}_{layout}_{i}'for i in range(args.shards)];completions=[json.loads(Path(str(p)+'_completion.json').read_text())for p in paths]
            if sum(c['fixtures']for c in completions)!=330:raise ValueError('Incomplete matrix')
            p=pd.concat([pd.read_csv(str(x)+'_predictions.csv.gz')for x in paths],ignore_index=True);t=pd.concat([pd.read_csv(str(x)+'_teams.csv.gz')for x in paths],ignore_index=True)
            if p.duplicated(['fixture_uuid','player_uuid','mode']).any():raise ValueError('Duplicate predictions')
            if season=='2024-25':p=p[p.gw.ge(22)];t=t[t.gw.ge(22)]
            all_frames[season,mm,layout]=p;points=summarize(p)
            for mode,g in p.groupby('mode'):points['metrics'][mode].update(cs_brier=float(g.cs_brier.mean()),gc_mae=float(g.gc_abs_error.mean()))
            extra=dict(against_fixed=summarize_against(p,'fixed'),team_goals=team_report(t),groups={col:{m:{str(k):dict(rows=len(g),mae=float(abs(g.xp-g.total_points).mean()),rmse=float(np.sqrt(((g.xp-g.total_points)**2).mean())))for k,g in ff.groupby(col)}for m,ff in p.groupby('mode')}for col in ['group','limited_history','club_change','role_change']})
            entry=dict(points=points,**extra,completion=dict(fixtures=330,legal_draws=sum(d['legal'].get('legal_draws',0)for c in completions for ds in c['diagnostics']for d in ds),max_marginal_shift=max([v['max_abs_marginal_change']for c in completions for ds in c['diagnostics']for d in ds for v in (d.get('projection')or{}).values()]+[0.])))
            key=mm+'_'+layout;report[season][key]=entry;save(OUT/f'{season}_{key}_report.json',dict(classification='CONTROLLED_DYNAMIC_WEIGHT_PM_V2',results=entry,limitations=LIMITS,locked_model_active=False,promotion_allowed=False))
        a=all_frames[season,'locked','independent'].copy();b=all_frames[season,'locked','legal'].copy();a['mode']='independent_'+a['mode'];b['mode']='legal_'+b['mode'];both=pd.concat([a,b],ignore_index=True)
        report[season]['xi_only']=summarize_against(both,'independent_original')
    save(OUT/'matrix_report.json',dict(results=report,selection=json.loads((OUT/'selection.json').read_text()),limitations=LIMITS,locked_model_active=False,promotion_allowed=False))
    compact={s:{key:dict(points={m:{k:v[k]for k in ['rows','mae','rmse','bias','cs_brier','gc_mae','goals','fpl_assists','bonus_mae']}for m,v in r['points']['metrics'].items()},paired_original=r['points']['paired']['point_abs_error'],paired_fixed=r['against_fixed']['point_abs_error'],teams=r['team_goals'],completion=r['completion'])for key,r in arms.items()if key!='xi_only'}for s,arms in report.items()};save(OUT/'summary.json',compact);print(json.dumps(compact,indent=2))


def main():
    p=argparse.ArgumentParser();p.add_argument('--stage',choices=['select','replay','aggregate'],required=True);p.add_argument('--season');p.add_argument('--mm',choices=['locked','mm'],default='locked');p.add_argument('--layout',choices=['independent','legal'],default='legal');p.add_argument('--shards',type=int,default=6);p.add_argument('--shard',type=int,default=0);a=p.parse_args();OUT.mkdir(parents=True,exist_ok=True)
    if a.stage=='aggregate':aggregate(a);return
    obs,teams,names,audit=observations(ROOT/'work/core.sqlite3')
    if a.stage=='select':select(obs)
    else:replay(a,obs,teams)
if __name__=='__main__':main()

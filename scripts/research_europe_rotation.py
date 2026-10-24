"""Prior-only European role recovery residual on frozen B. Offline, no promotion."""
import argparse,json,hashlib,sqlite3,gzip,copy
from pathlib import Path
from dataclasses import asdict,replace
from concurrent.futures import ProcessPoolExecutor,as_completed
import numpy as np
import pandas as pd
from scipy.special import expit,logit
from scipy.optimize import minimize
from individual_mm_evidence import load_frame
from research_individual_mm_refinement import project
from audit_correctness_historical import decode
from gk_joint_bridge import observations,DurationHistory,prepare,UNKNOWN
from b_chain_contract import prepare_match
from fpl_v1_1_model.joint_simulator import simulate_many
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'analysis/results/europe-rotation-20261022'
KEY=['season','fixture_uuid','player_uuid']
EURO=['Champions League','Europa League','Conference League','Conference qualification']
COLS=['euro_minutes7','euro_minutes14','euro_rest_gap','euro_latest_start','euro_latest_unused','role_recovery','pl_start_euro_bench']


def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def dump(p,d):p.write_text(json.dumps(d,indent=2,allow_nan=False)+'\n')
def features(f,core,events):
 """No future schedule, future result, or target label enters a feature."""
 out=f.copy().reset_index(drop=True);ev=events.copy();ev['kickoff']=pd.to_datetime(ev.kickoff,utc=True,format='mixed');ev['known_at']=pd.to_datetime(ev.known_at,utc=True,format='mixed')
 ev=ev[ev.player_uuid.notna()&ev.competition.isin(EURO)].copy()
 if ev.duplicated(['season','player_uuid','match_id']).any():raise ValueError('Duplicate European player/match')
 if (ev.known_at<ev.kickoff).any():raise ValueError('Outcome clock precedes kickoff')
 co=core.copy();co['known_at']=pd.to_datetime(co.known_at,utc=True,format='mixed');co['kickoff_at']=pd.to_datetime(co.kickoff_at,utc=True,format='mixed')
 clubs=co[['season','player_uuid','team_id','club']].drop_duplicates()
 # Current club is verified through PL identity; transferred players must not
 # import their former club's role signal into the target club.
 histories={(s,str(p),c):g.sort_values(['known_at','match_id'])for(s,p,c),g in ev.groupby(['season','player_uuid','club'])}
 plhist={(s,str(p),int(t)):g.sort_values(['known_at','fixture_uuid'])for(s,p,t),g in co.groupby(['season','player_uuid','team_id'])}
 names={(s,int(t)):g.club.iloc[0]for(s,t),g in clubs.groupby(['season','team_id'])}
 rows=[]
 for r in out.itertuples():
  cut=pd.Timestamp(r.cutoff);club=names[(r.season,int(r.team_id))];g=histories.get((r.season,str(r.player_uuid),club),ev.iloc[:0]);g=g[g.known_at.lt(cut)]
  past=plhist.get((r.season,str(r.player_uuid),int(r.team_id)),co.iloc[:0]);past=past[past.known_at.lt(cut)]
  recent=g[g.kickoff.gt(cut-pd.Timedelta(days=14))];last=g.iloc[-1]if len(g)else None;pl=past.iloc[-1]if len(past)else None
  v=dict.fromkeys(COLS,0.);context=len(recent)>0;recovery=False;latestclock=None
  if context:
   usable=recent[recent.minutes.notna()];v['euro_minutes7']=float(usable.loc[usable.kickoff.gt(cut-pd.Timedelta(days=7)),'minutes'].sum()/90);v['euro_minutes14']=float(usable.minutes.sum()/90)
   played=g[g.minutes.gt(0)]
   if len(played):
    euro_rest=(cut-played.iloc[-1].kickoff).total_seconds()/86400
    plplayed=past[past.minutes.gt(0)]
    if len(plplayed):v['euro_rest_gap']=max(0.,(cut-plplayed.iloc[-1].kickoff_at).total_seconds()/86400-euro_rest)/7
   v['euro_latest_start']=float(last.started is True or last.started==True) if pd.notna(last.started)else 0.
   v['euro_latest_unused']=float(last.started==False and pd.notna(last.minutes)and last.minutes==0)if pd.notna(last.started)else 0.
   if pl is not None and last.known_at>pl.known_at and last.kickoff>pl.kickoff_at:
    previous=past.iloc[:-1].tail(6);role=float(previous.started.mean())if len(previous)else 0.
    recovery=bool(pl.started==0 and v['euro_latest_start'] and role>=.5)
    v['role_recovery']=float(recovery)*role
    v['pl_start_euro_bench']=float(pl.started==1)*v['euro_latest_unused']
   latestclock=recent.known_at.max().isoformat()
  if str(r.pos)in ['GK','GKP']:v=dict.fromkeys(COLS,0.)
  rows.append(dict(**v,europe_context=context,role_recovery_case=recovery,europe_max_known_at=latestclock,missing_euro_minutes=int(recent.minutes.isna().sum())))
 return pd.concat([out,pd.DataFrame(rows)],axis=1)


def source_frames():
 frozen=load_frame(ROOT/'analysis/results/individual-mm-refinement-20261016/predictions.npz');f=frozen[frozen['mode'].eq('B')].copy()
 up=load_frame(ROOT/'work/mm-integration-source/results/predictions.npz');up=up[up['mode'].eq('role_chance_return_duration')]
 f=f.merge(up[KEY+['pos','news_eligible','news_chance','news_effective_at']],on=KEY,validate='one_to_one')
 with sqlite3.connect(f'file:{ROOT/"work/core.sqlite3"}?mode=ro',uri=True)as db:
  core=pd.read_sql_query('SELECT season,fixture_uuid,player_uuid,team_id,started,minutes,kickoff_at,total_points FROM player_fixture_observations WHERE is_final=1',db)
 events=pd.read_csv(ROOT/'analysis/results/mm-match-importance-20261016/individual_recorded_workload.csv.gz',low_memory=False)
 # Exact player + PL kickoff gives the club mapping; never map by display name.
 pl=events[events.competition.eq('Premier League')][['season','player_uuid','kickoff','club']].copy();pl['clock']=pd.to_datetime(pl.kickoff,utc=True,format='mixed');core['clock']=pd.to_datetime(core.kickoff_at,utc=True,format='mixed')
 aligned=core.merge(pl[['season','player_uuid','clock','club']],on=['season','player_uuid','clock'],how='left',validate='one_to_one')
 names=aligned[['season','team_id','club']].dropna().drop_duplicates()
 if names.duplicated(['season','team_id']).any():raise ValueError('Conflicting club identity')
 core=core.merge(names,on=['season','team_id'],validate='many_to_one');core['known_at']=pd.to_datetime(core.kickoff_at,utc=True,format='mixed')+pd.to_timedelta(np.where(core.season.eq('2024-25'),4,3),unit='h')
 events['known_at']=pd.to_datetime(events.kickoff,utc=True,format='mixed')+pd.to_timedelta(np.where(events.season.eq('2024-25'),4,3),unit='h')
 recovered=pd.read_csv(ROOT/'analysis/results/historical-cup-recovery-v1/restored_player_minutes.csv')
 if len(recovered):
  recovered['season']='2025-26';recovered=recovered.merge(names,on=['season','team_id'],validate='many_to_one')
  comp={'champions-league':'Champions League','europa-league':'Europa League','conference-league':'Conference League'}
  recovered['competition']=recovered.competition.map(comp)
  if recovered.competition.isna().any():raise ValueError('Unknown recovered competition')
  recovered['known_at']=pd.to_datetime(recovered.available_at,utc=True)
  # Replace any existing same-player same-kickoff event, never duplicate it.
  stamp=lambda g:set(zip(g.season,g.player_uuid,pd.to_datetime(g.kickoff,utc=True,format='mixed')))
  recovered_keys=stamp(recovered)
  keep=[k not in recovered_keys for k in zip(events.season,events.player_uuid,pd.to_datetime(events.kickoff,utc=True,format='mixed'))]
  events=pd.concat([events.loc[keep],recovered.reindex(columns=events.columns)],ignore_index=True)
 return f,core,events


def corrected(frame,raw):
 g=frame.copy();g['p']=raw;g['x']=g.p*g.s+(1-g.p)*g.q*g.c
 affected=np.abs(raw-frame.p.to_numpy())>1e-12
 if not affected.any():return frame.copy()
 changedteams=set(zip(frame.loc[affected,'season'],frame.loc[affected,'fixture_uuid'],frame.loc[affected,'team_id']))
 mask=np.array([(s,fx,t)in changedteams for s,fx,t in zip(frame.season,frame.fixture_uuid,frame.team_id)])
 changed=project(g.loc[mask].copy());g.loc[mask,['p','q','x']]=changed[['p','q','x']].to_numpy();g.loc[~mask,['p','q','x']]=frame.loc[~mask,['p','q','x']].to_numpy()
 return g


def fit_offset(frame,X,train,alpha):
 valid=train&frame.p.between(1e-6,1-1e-6).to_numpy()&~frame.pos.isin(['GK','GKP']).to_numpy()
 if valid.sum()<200 or not X[valid].any():return np.zeros(X.shape[1]),np.ones(X.shape[1])
 scale=np.sqrt(np.mean(X[valid]**2,axis=0));scale[scale<1e-8]=1.;Z=X[valid]/scale;base=logit(np.clip(frame.p.to_numpy()[valid],1e-6,1-1e-6));y=frame.y.to_numpy()[valid]
 def fg(beta):
  logits=base+Z@beta;prob=expit(logits)
  return float(np.logaddexp(0,logits).sum()-y@logits+.5*alpha*(beta@beta)),Z.T@(prob-y)+alpha*beta
 res=minimize(fg,np.zeros(X.shape[1]),jac=True,method='L-BFGS-B',bounds=[(-2,2)]*X.shape[1],options={'maxiter':1000,'ftol':1e-12,'gtol':1e-7})
 if not res.success:raise ValueError('Offset optimization failed: '+res.message)
 return res.x,scale


def metrics(g):
 if not len(g):return dict(rows=0)
 return dict(rows=len(g),start_brier=float(((g.p-g.y)**2).mean()),minute_mae=float(abs(g.x-g.minutes).mean()),minute_bias=float((g.x-g.minutes).mean()))


def train_and_evaluate():
 protocol=json.loads((OUT/'protocol.json').read_text());f,core,events=source_frames();f=features(f,core,events)
 f['cutoff']=pd.to_datetime(f.cutoff,utc=True,format='mixed');f=f.merge(core[KEY+['known_at']],on=KEY,validate='one_to_one');f=f.sort_values(['cutoff','season','fixture_uuid','player_uuid']).reset_index(drop=True)
 X=f[COLS].to_numpy(float);raw={a:f.p.to_numpy().copy()for a in [.1,1.,10.]};logs=[]
 for cut,ix in f.groupby('cutoff',sort=True).indices.items():
  ix=np.asarray(ix);train=f.known_at.lt(cut).to_numpy()
  for alpha in raw:
   beta,scale=fit_offset(f,X,train,alpha);z=np.clip(X[ix]/scale@beta,-2,2);r=f.p.to_numpy()[ix].copy();interior=(r>0)&(r<1);r[interior]=expit(logit(r[interior])+z[interior]);r[~np.any(X[ix]!=0,axis=1)]=f.p.to_numpy()[ix][~np.any(X[ix]!=0,axis=1)]
   raw[alpha][ix]=corrected(f.iloc[ix],r).p.to_numpy()
   logs.append(dict(cutoff=cut.isoformat(),alpha=alpha,training_rows=int(train.sum()),last_label_known_at=f.loc[train,'known_at'].max().isoformat()if train.any()else None,coef=beta.tolist(),scale=scale.tolist()))
  print('Origin',cut.isoformat(),flush=True)
 dev=f.season.eq('2024-25')&f.gw.between(14,21);tuning={str(a):float(((raw[a][dev]-f.loc[dev,'y'])**2).mean())for a in raw};alpha=min(raw,key=lambda a:(tuning[str(a)],a));chosen=corrected(f,raw[alpha])
 output=[];report={}
 for season in ['2024-25','2025-26']:
  mask=f.season.eq(season)&f.gw.between(22 if season=='2024-25'else 6,38);b=f[mask].copy();c=chosen[mask].copy()
  groups={'all':np.ones(len(b),bool),'played':b.minutes.gt(0).to_numpy(),'europe_context':b.europe_context.to_numpy(),'role_recovery':b.role_recovery_case.to_numpy()}
  report[season]={name:dict(baseline=metrics(b.loc[ix]),candidate=metrics(c.loc[ix]))for name,ix in groups.items()}
  for arm,g in [('baseline',b),('candidate',c)]:g=g.copy();g['arm']=arm;output.append(g)
 allout=pd.concat(output,ignore_index=True);allout.to_csv(OUT/'mm-predictions.csv.gz',index=False,compression={'method':'gzip','mtime':0})
 # Paired fixture bootstrap; resample whole matches, not player rows.
 paired=chosen[KEY+['p','x']].merge(f[KEY+['p','x','y','minutes']],on=KEY,suffixes=('_candidate','_baseline'),validate='one_to_one')
 paired['delta']=(paired.p_candidate-paired.y)**2-(paired.p_baseline-paired.y)**2
 mask=f.season.eq('2025-26')|f.gw.ge(22);keys=set(map(tuple,f.loc[mask,KEY].to_numpy()));paired=paired[[tuple(r)in keys for r in paired[KEY].to_numpy()]]
 grouped=paired.groupby(['season','fixture_uuid']).delta.agg(['sum','count']);rng=np.random.default_rng(20261022);stats=[]
 for _ in range(2000):
  ix=rng.integers(0,len(grouped),len(grouped));stats.append(float(grouped['sum'].to_numpy()[ix].sum()/grouped['count'].to_numpy()[ix].sum()))
 bounds=np.quantile(stats,[.025,.975]).tolist()
 accepted=all(report[s]['all']['candidate']['start_brier']<report[s]['all']['baseline']['start_brier']and report[s]['all']['candidate']['minute_mae']<=report[s]['all']['baseline']['minute_mae']and abs(report[s]['all']['candidate']['minute_bias'])<=abs(report[s]['all']['baseline']['minute_bias'])+.1 for s in report)and bounds[1]<0
 coverage_ok=all(report[s]['role_recovery']['baseline']['rows']>=50 for s in report)
 result=dict(protocol=protocol,selected_alpha=alpha,development_brier=tuning,metrics=report,pooled_start_brier_delta_CI95=bounds,numerical_MM_gate=bool(accepted),coverage_gate=bool(coverage_ok),independent_source_clock_certification=False,promotion_allowed=False,production_changed=False)
 dump(OUT/'mm-report.json',result);dump(OUT/'fit-log.json',logs)
 dump(OUT/'source-manifest.json',{'inputs':{str(p.relative_to(ROOT)):sha(p)for p in [ROOT/'analysis/results/mm-match-importance-20261016/individual_recorded_workload.csv.gz',ROOT/'analysis/results/mm-match-importance-20261016/rotation_manifest.json',ROOT/'analysis/results/individual-mm-refinement-20261016/predictions.npz',ROOT/'work/mm-integration-source/results/predictions.npz',ROOT/'analysis/results/historical-cup-recovery-v1/restored_player_minutes.csv']},'code_sha256':sha(__file__)})
 print(json.dumps(result,indent=2),flush=True)


def simulate_task(task):
 season,fx,seed,data=task;rows=[]
 for arm,raw in data.items():
  inp=decode(copy.deepcopy(raw));sim=simulate_many(inp,n=400,seed=seed)
  for p in inp.players:
   if p.player_id.startswith(UNKNOWN):continue
   s=sim[p.player_id];rows.append(dict(season=season,fixture_uuid=fx,player_uuid=p.player_id,arm=arm,xp=s['xPts'],sim_minutes=s['expected_minutes']))
 return rows


def points(workers):
 f=pd.read_csv(OUT/'mm-predictions.csv.gz',low_memory=False);obs=observations(ROOT);cache={};tasks=[];reuse=[]
 reference=pd.read_csv(ROOT/'analysis/results/unified-b-chain-20261021/predictions.csv.gz');reference=reference[reference.arm.eq('mean_preserving')].copy();cohort={}
 for season in ['2024-25','2025-26']:
  records=[json.loads(l)for l in gzip.open(ROOT/f'analysis/results/general-conversion-20261020/{season}_prepared.jsonl.gz','rt')];cohort[season]=len(records)
  for r in records:
   fx=r['core_fixture'];b=f[f.season.eq(season)&f.fixture_uuid.eq(fx)&f.arm.eq('baseline')].set_index('player_uuid');c=f[f.season.eq(season)&f.fixture_uuid.eq(fx)&f.arm.eq('candidate')].set_index('player_uuid')
   if set(b.index)!=set(c.index)or not len(b):raise ValueError('Missing frozen candidate rows')
   ref=reference[reference.season.eq(season)&reference.fixture_uuid.eq(fx)]
   if set(ref.player_uuid)!=set(b.index):raise ValueError('Reference PM cohort mismatch')
   if np.max(abs(b.p-c.p))<1e-12:
    for arm in ['baseline','candidate']:
     reuse.extend(ref.assign(arm=arm)[['season','fixture_uuid','player_uuid','arm','xp','sim_minutes']].to_dict('records'))
    continue
   original=decode(copy.deepcopy(r['input']));base=replace(original,players=tuple(replace(p,p_start=float(b.loc[p.player_id,'p']),p_cameo_given_bench=float(b.loc[p.player_id,'q']),start_minutes_mean=float(b.loc[p.player_id,'s']),cameo_minutes_mean=float(b.loc[p.player_id,'c']))for p in original.players))
   if r['cutoff']not in cache:cache[r['cutoff']]=DurationHistory(obs,r['cutoff'])
   base,_,_=prepare(base,b.reset_index(),cache[r['cutoff']]);base=prepare_match(base)
   candidate=replace(base,players=tuple(p if p.is_keeper else replace(p,p_start=float(c.loc[p.player_id,'p']),p_cameo_given_bench=float(c.loc[p.player_id,'q']))for p in base.players))
   # Non-minute PM properties and all GK inputs remain identical.
   for p,q in zip(base.players,candidate.players):
    pp=asdict(p);qq=asdict(q)
    for k in ['p_start','p_cameo_given_bench']:pp.pop(k);qq.pop(k)
    if pp!=qq:raise ValueError('Changed non-minute player inputs')
   tasks.append((season,fx,r['seed'],{'baseline':asdict(base),'candidate':asdict(candidate)}))
 print('PM affected fixtures',len(tasks),'of',sum(cohort.values()),flush=True)
 rows=reuse
 with ProcessPoolExecutor(max_workers=workers)as pool:
  futures=[pool.submit(simulate_task,t)for t in tasks]
  for i,fu in enumerate(as_completed(futures)):
   rows.extend(fu.result())
   if (i+1)%10==0:print('PM completed',i+1,'/',len(tasks),flush=True)
 frame=pd.DataFrame(rows);b=frame[frame.arm.eq('baseline')].merge(reference,on=KEY,validate='one_to_one',suffixes=('_new','_saved'))
 if not np.array_equal(b.xp_new,b.xp_saved)or not np.array_equal(b.sim_minutes_new,b.sim_minutes_saved):raise ValueError('Original unified baseline not reproduced exactly')
 with sqlite3.connect(f'file:{ROOT/"work/core.sqlite3"}?mode=ro',uri=True)as db:truth=pd.read_sql_query('SELECT season,fixture_uuid,player_uuid,total_points,minutes FROM player_fixture_observations WHERE is_final=1',db)
 flags=f[f.arm.eq('baseline')][KEY+['europe_context','role_recovery_case']]
 frame=frame.merge(truth,on=KEY,how='left',validate='many_to_one').merge(flags,on=KEY,validate='many_to_one')
 if frame.total_points.isna().any():raise ValueError('Missing PM actuals')
 report={}
 for (season,arm),g in frame.groupby(['season','arm']):
  groups={'all':np.ones(len(g),bool),'played':g.minutes.gt(0).to_numpy(),'europe_context':g.europe_context.to_numpy(),'role_recovery':g.role_recovery_case.to_numpy()}
  report.setdefault(season,{})[arm]={}
  for name,ix in groups.items():
   z=g.loc[ix];error=z.xp-z.total_points;report[season][arm][name]=dict(rows=len(z),xp_mae=float(abs(error).mean())if len(z)else None,xp_bias=float(error.mean())if len(z)else None)
 frame.to_csv(OUT/'pm-predictions.csv.gz',index=False,compression={'method':'gzip','mtime':0})
 accepted=all(report[s]['candidate']['all']['xp_mae']<=report[s]['baseline']['all']['xp_mae']+.005 and report[s]['candidate']['played']['xp_mae']<=report[s]['baseline']['played']['xp_mae']+.02 and abs(report[s]['candidate']['all']['xp_bias'])<=abs(report[s]['baseline']['all']['xp_bias'])+.02 for s in report)
 dump(OUT/'pm-report.json',dict(metrics=report,fixtures=cohort,affected_fixtures=len(tasks),unchanged_fixtures_reused=sum(cohort.values())-len(tasks),baseline_exact=True,point_noninferiority=accepted,production_changed=False,promotion_allowed=False));print(json.dumps(report,indent=2),flush=True)

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--stage',choices=['mm','pm'],required=True);p.add_argument('--workers',type=int,default=4);a=p.parse_args();OUT.mkdir(exist_ok=True,parents=True)
 train_and_evaluate()if a.stage=='mm'else points(a.workers)

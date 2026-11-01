"""Fixed prior-only role transition screen; never changes an active policy."""
import json
import hashlib
from pathlib import Path
import numpy as np
import pandas as pd
from scipy.special import expit, logit
from research_europe_rotation import source_frames, corrected, fit_offset
from role_transition_evidence import KEY, FEATURES, build_evidence
from fpl_v1_1_model.role_event_priors import QCOLS,validate_roles
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'analysis/results/role-transitions-20261025'

def metrics(g,p='p',x='x'):
    if not len(g):return {'rows':0}
    return dict(rows=len(g),start_brier=float(np.mean((g[p]-g.y)**2)),start_bias=float(np.mean(g[p]-g.y)),minute_mae=float(np.mean(abs(g[x]-g.minutes))),minute_bias=float(np.mean(g[x]-g.minutes)))

def main():
    f,core,_=source_frames()
    roles=[]
    for season,path in [('2024-25','analysis/results/penalty-neutral-sources-20261023/predeadline-roles-2024.csv.gz'),('2025-26','analysis/results/workload-recovered-v4/all_features.csv.gz')]:
        r=pd.read_csv(ROOT/path,usecols=['fixture_uuid','player_uuid','team_id','cutoff','max_history_known_at',*QCOLS]);r['cutoff']=pd.to_datetime(r.cutoff,utc=True,format='mixed');r['max_history_known_at']=pd.to_datetime(r.max_history_known_at,utc=True,format='mixed');validate_roles(r);r['season']=season;roles.append(r)
    role_frame=pd.concat(roles).rename(columns={'team_id':'role_team_id','cutoff':'role_cutoff'})
    f=f.merge(role_frame,on=KEY,validate='one_to_one')
    if not f.team_id.eq(f.role_team_id).all():raise ValueError('Role club mismatch')
    if (pd.to_datetime(f.role_cutoff,utc=True,format='mixed')>pd.to_datetime(f.cutoff,utc=True,format='mixed')).any():raise ValueError('Future role state')
    if f[QCOLS].isna().any().any():raise ValueError('Missing target role states')
    evidence=build_evidence(f[KEY+['team_id','cutoff','pos','news_state','news_chance','news_eligible','news_effective_at',*QCOLS]],core,f,QCOLS)
    evidence.to_csv(OUT/'evidence.csv.gz',index=False,compression={'method':'gzip','mtime':0})
    f=f.merge(evidence,on=KEY,validate='one_to_one').merge(core[KEY+['known_at']],on=KEY,validate='one_to_one')
    f.cutoff=pd.to_datetime(f.cutoff,utc=True,format='mixed');f.known_at=pd.to_datetime(f.known_at,utc=True,format='mixed')
    f=f.sort_values(['cutoff',*KEY]).reset_index(drop=True)
    X=f[FEATURES].fillna(0).to_numpy(float);raw=f.p.to_numpy().copy();logs=[]
    for cut,ix in f.groupby('cutoff',sort=True).indices.items():
        ix=np.asarray(ix);train=f.known_at.lt(cut).to_numpy();beta,scale=fit_offset(f,X,train,10.)
        # The reused optimizer's fixed bounds are inactive; no tuning or clipping.
        if np.max(abs(beta))>=1.999:raise ValueError('Optimizer bounds active: protocol requires unbounded offset')
        r=raw[ix].copy();valid=(r>0)&(r<1)&~f.iloc[ix].pos.isin(['GK','GKP']).to_numpy()
        r[valid]=expit(logit(r[valid])+X[ix][valid]/scale@beta)
        raw[ix]=r
        logs.append(dict(cutoff=cut.isoformat(),training_rows=int(train.sum()),last_label_known_at=f.loc[train,'known_at'].max().isoformat() if train.any() else None,coef=beta.tolist(),scale=scale.tolist()))
        print('Fitted',cut.isoformat(),flush=True)
    c=corrected(f,raw)
    keeper=f.pos.isin(['GK','GKP'])
    if not np.allclose(c.loc[keeper,['p','q','x']],f.loc[keeper,['p','q','x']],atol=1e-12,rtol=0):raise ValueError('Keeper changed')
    # Preserve archived keeper rows exactly, including harmless projection roundoff.
    c.loc[keeper,['p','q','x']]=f.loc[keeper,['p','q','x']]
    cohorts={'all':~keeper,'role_shift':(~keeper)&f.recent_share3.ge(2/3)&f.prior_share6.le(1/3),'opportunity':(~keeper)&f.transition_opportunity3.gt(0),'rival_return':(~keeper)&f.transition_return_pressure.gt(0),'rotation':(~keeper)&f.recent_share3.between(1/3,2/3)}
    report={};passes=[];rng=np.random.default_rng(20261025)
    for season in ['2024-25','2025-26']:
        period=f.season.eq(season)&f.gw.between(22,38);report[season]={}
        for name,mask in cohorts.items():
            m=period&mask;b=metrics(f[m]);a=metrics(c[m]);report[season][name]={'baseline':b,'candidate':a}
            if b['rows']:
                delta=a['start_brier']-b['start_brier'];passes.append(delta<0 if name=='all' else delta<=.005)
                if name=='all':passes.extend([a['minute_mae']<=b['minute_mae']+.05,abs(a['start_bias'])<=abs(b['start_bias'])+.005])
        m=period&cohorts['all'];d=f.loc[m,KEY].copy();d['delta']=(c.loc[m,'p']-f.loc[m,'y'])**2-(f.loc[m,'p']-f.loc[m,'y'])**2
        g=d.groupby('fixture_uuid').delta.agg(['sum','count']);stats=[]
        for _ in range(2000):
            ix=rng.integers(len(g),size=len(g));stats.append(float(g['sum'].to_numpy()[ix].sum()/g['count'].to_numpy()[ix].sum()))
        report[season]['paired_fixture_brier_delta_CI95']=np.quantile(stats,[.025,.975]).tolist()
    final=pd.read_csv(ROOT/'analysis/results/joint-role-candidate-20261022/predictions.csv.gz')
    d=f.merge(final[KEY+['p','x','candidate_p','candidate_x']].rename(columns={'p':'archived_upstream_p','x':'archived_upstream_x'}),on=KEY,validate='one_to_one');diagnosis={}
    if not np.allclose(d.p,d.archived_upstream_p,atol=1e-12,rtol=0) or not np.allclose(d.x,d.archived_upstream_x,atol=1e-10,rtol=0):raise ValueError('Frozen upstream reproduction failed')
    for season in ['2024-25','2025-26']:
        diagnosis[season]={}
        for name,mask in cohorts.items():
            keys=f.loc[mask&f.season.eq(season)&f.gw.between(22,38),KEY];g=d.merge(keys,on=KEY,validate='one_to_one')
            diagnosis[season][name]=metrics(g,'candidate_p','candidate_x')
    # Event time: trigger uses past-only starts. No future sustained-role labels.
    event_rows=[]
    for _,g in f.groupby(['season','player_uuid','team_id']):
        g=g.sort_values('cutoff');last=None
        for ix,r in g.iterrows():
            triggered=bool(cohorts['role_shift'].loc[ix])
            if triggered and (last is None or (r.cutoff-last[0]).days>28):last=(r.cutoff,int(r.team_history_games))
            if last is not None:
                age=int(r.team_history_games)-last[1]
                if 0<=age<=4 and 22<=r.gw<=38 and r.pos not in ['GK','GKP']:
                    event_rows.append(dict(season=r.season,age=age,actual_start=r.y,baseline_p=r.p,candidate_p=c.loc[ix,'p']))
    event=pd.DataFrame(event_rows)
    reaction=[]
    for (season,age),g in event.groupby(['season','age']):
        reaction.append(dict(season=season,team_games_after_trigger=int(age),rows=len(g),actual_start_rate=float(g.actual_start.mean()),baseline_p=float(g.baseline_p.mean()),candidate_p=float(g.candidate_p.mean())))
    coverage={season:dict(rows=int((f.season.eq(season)&~keeper).sum()),with_rival=int((f.season.eq(season)&~keeper&f.rival_uuid.notna()).sum()),known_current_rival=int((f.season.eq(season)&~keeper&f.rival_current_availability.notna()).sum()))for season in ['2024-25','2025-26']}
    result=dict(coverage=coverage,reaction_time_descriptive= reaction,upstream_reproduction_pass=True,upstream_metrics=report,existing_joint_role_diagnosis=diagnosis,upstream_screen_pass=bool(all(passes)),candidate_PM_scored=False,active_B_changed=False,production_changed=False,limitations=['Reused historical research periods, not independent holdout','Proxy outcome availability clocks; incomplete explicit injury availability','Soft-role rivalry proxy, not confirmed coach hierarchy','Goalkeeper forecasts unchanged; this candidate concerns outfield starts'])
    for name,value in [('report.json',result),('fit-log.json',logs)]: (OUT/name).write_text(json.dumps(value,indent=2,allow_nan=False)+'\n')
    pd.concat([f.assign(arm='baseline'),c.assign(arm='candidate')]).to_csv(OUT/'predictions.csv.gz',index=False,compression={'method':'gzip','mtime':0})
    paths=[Path(__file__),ROOT/'scripts/role_transition_evidence.py',OUT/'protocol.json',ROOT/'analysis/results/individual-mm-refinement-20261016/predictions.npz',ROOT/'work/mm-integration-source/results/predictions.npz',ROOT/'work/core.sqlite3',ROOT/'analysis/results/penalty-neutral-sources-20261023/predeadline-roles-2024.csv.gz',ROOT/'analysis/results/workload-recovered-v4/all_features.csv.gz',ROOT/'analysis/results/joint-role-candidate-20261022/predictions.csv.gz',ROOT/'scripts/research_europe_rotation.py']
    (OUT/'source-manifest.json').write_text(json.dumps({str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest()for p in paths},indent=2)+'\n')
    print(json.dumps(result,indent=2),flush=True)
if __name__=='__main__':main()

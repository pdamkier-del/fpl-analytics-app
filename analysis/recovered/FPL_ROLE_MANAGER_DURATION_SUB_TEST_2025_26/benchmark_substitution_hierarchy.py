from pathlib import Path
from collections import defaultdict
import numpy as np, pandas as pd, json
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import brier_score_loss, log_loss

ROOT=Path('/mnt/data/fpl_resume/role_cache')
d=pd.read_csv(ROOT/'duration_substitution_predictions.csv')
d['player_uuid']=d.player_uuid.astype(str)
d=d.sort_values(['gw','fixture_uuid','team_id','player_uuid']).reset_index(drop=True)
EPS=1e-7
# conditional cameo label only defined for actual nonstarters
# baseline cameo logit
p0=np.clip(d.p_cameo_given_bench.values,EPS,1-EPS)
d['cameo_base_logit']=np.log(p0/(1-p0))
d['cameo_y']=((d.y==0)&(d.minutes>0)).astype(int)

# manager regimes same as standing model
regime_starts={7:[1,22],14:[1,22],16:[1,4,9,27],18:[1,32],19:[1,6]}
def regstart(t,g):
 ss=regime_starts.get(int(t),[1]); return max(x for x in ss if x<=int(g))
d['regime_start']=[regstart(t,g) for t,g in zip(d.team_id,d.gw)]

# cutoff-safe recent cameo features per player and expected team sub count
# only GW earlier than target; same-GW DGW is not used because fixture order/deadline state may be ambiguous.
d['recent_cameo_rate3']=0.0; d['recent_cameo_rate8']=0.0; d['recent_bench_evidence']=0.0
for (tid,pid),g in d.groupby(['team_id','player_uuid'],sort=False):
    idx=g.index.to_numpy(); gw=g.gw.to_numpy(); rs=g.regime_start.to_numpy(); y=g.y.to_numpy(); mins=g.minutes.to_numpy()
    for j,ix in enumerate(idx):
        prev=np.arange(j)[(gw[:j] < gw[j]) & (rs[:j]>=rs[j]) & (y[:j]==0)]
        if not len(prev): continue
        for half,col in [(3,'recent_cameo_rate3'),(8,'recent_cameo_rate8')]:
            w=2**(-(gw[j]-gw[prev])/half); rate=float(np.dot(w,(mins[prev]>0).astype(float))/w.sum())
            d.at[ix,col]=rate
        d.at[ix,'recent_bench_evidence']=min(len(prev)/8,1.0)

# actual subs per team-fixture; estimate target expected subs from prior GWs in current manager regime
subs_actual=(d.assign(sub=((d.y==0)&(d.minutes>0)).astype(int))
               .groupby(['gw','fixture_uuid','team_id'],as_index=False)['sub'].sum())
subs_by_team=defaultdict(list)
for z in subs_actual.sort_values(['gw','fixture_uuid']).itertuples(index=False):
    subs_by_team[int(z.team_id)].append((int(z.gw),str(z.fixture_uuid),int(z.sub),regstart(z.team_id,z.gw)))

def exp_subs(tid,gw):
    rs=regstart(tid,gw)
    hist=[x for x in subs_by_team[int(tid)] if x[0]<gw and x[3]>=rs]
    if not hist: return 3.0
    vals=np.array([x[2] for x in hist],float); ages=np.array([gw-x[0] for x in hist],float)
    w=2**(-ages/6.0)
    # shrink to league contemporary 3.5 subs with 2 pseudo-games; this is weak and later tested vs unconstrained.
    return float(np.clip((np.dot(w,vals)+2*3.5)/(w.sum()+2),0,5))
d['expected_team_subs']=[exp_subs(t,g) for t,g in zip(d.team_id,d.gw)]

features=['cameo_base_logit','role_fit_fast','role_h_fast','role_qmax_fast','role_evidence_fast',
          'role_fit_slow','role_h_slow','regime_core3','regime_core10','regime_started_last',
          'recent_cameo_rate3','recent_cameo_rate8','recent_bench_evidence','regime_maturity']

# Walk-forward conditional cameo model, trained only on actual bench cases in prior GWs.
d['p_cameo_hier_raw']=d.p_cameo_given_bench.astype(float)
for gw in sorted(d.gw.unique()):
    if gw<12: continue
    tr=d[(d.gw>=6)&(d.gw<gw)&(d.y==0)]
    te=d[d.gw==gw]
    if len(tr)<1000 or tr.cameo_y.nunique()<2: continue
    m=LogisticRegression(C=0.2,max_iter=2500,class_weight=None)
    m.fit(tr[features],tr.cameo_y)
    d.loc[te.index,'p_cameo_hier_raw']=m.predict_proba(te[features])[:,1]

# Joint team constraint: expected number of substitutes. Shift conditional cameo logits while preserving ranking.
def constrain_group(g):
    pstart=g.p_regime.to_numpy(float)
    raw=np.clip(g.p_cameo_hier_raw.to_numpy(float),EPS,1-EPS)
    target=float(g.expected_team_subs.iloc[0])
    # only bench mass can make a cameo
    maxpossible=float(np.sum(1-pstart))
    target=min(target,maxpossible)
    logits=np.log(raw/(1-raw))
    lo,hi=-25.,25.
    for _ in range(70):
        mid=(lo+hi)/2
        pc=1/(1+np.exp(-(logits+mid)))
        s=np.sum((1-pstart)*pc)
        if s<target: lo=mid
        else: hi=mid
    return 1/(1+np.exp(-(logits+(lo+hi)/2)))

d['p_cameo_hier']=d.p_cameo_hier_raw
for _,idx in d.groupby(['fixture_uuid','team_id']).groups.items():
    ii=np.array(list(idx)); d.loc[ii,'p_cameo_hier']=constrain_group(d.loc[ii])

# xMins variants: isolate each new layer.
p=d.p_regime.to_numpy(float)
base_sm=d.start_minutes_mean.to_numpy(float); base_cm=d.cameo_minutes_mean.to_numpy(float); base_pc=d.p_cameo_given_bench.to_numpy(float)
new_sm=d.start_minutes_duration_v2.to_numpy(float); new_cm=d.cameo_minutes_duration_v2.to_numpy(float); new_pc=d.p_cameo_hier.to_numpy(float)

d['xm_subhier_only']=p*base_sm+(1-p)*new_pc*base_cm
d['xm_subhier_cameodur']=p*base_sm+(1-p)*new_pc*new_cm
d['xm_full_duration_subhier']=p*new_sm+(1-p)*new_pc*new_cm

# Metrics
actual=d.minutes.to_numpy(float)
def met(x,m):
    e=x[m]-actual[m]; return {'mae':float(np.mean(abs(e))),'rmse':float(np.sqrt(np.mean(e*e))),'bias':float(np.mean(e))}
res={}
for label,mask in [('tune_gw12_21',((d.gw>=12)&(d.gw<=21)).to_numpy()),('test_gw22_38',(d.gw>=22).to_numpy())]:
    res[label]={}
    variants={
      'base':d.xm_base.to_numpy(float),'role':d.xm_role.to_numpy(float),'manager_regime':d.xm_regime.to_numpy(float),
      'duration_only':d.xm_duration_v2.to_numpy(float),'subhier_only':d.xm_subhier_only.to_numpy(float),
      'subhier_cameodur':d.xm_subhier_cameodur.to_numpy(float),'full_duration_subhier':d.xm_full_duration_subhier.to_numpy(float)}
    for k,x in variants.items(): res[label][k]=met(x,mask)
    bench=mask&(d.y.to_numpy()==0); yy=(actual[bench]>0).astype(int)
    res[label]['cameo_brier']={
      'baseline':float(brier_score_loss(yy,base_pc[bench])),
      'hier_raw':float(brier_score_loss(yy,d.p_cameo_hier_raw.to_numpy(float)[bench])),
      'hier_constrained':float(brier_score_loss(yy,new_pc[bench]))}
    res[label]['cameo_logloss']={
      'baseline':float(log_loss(yy,np.clip(base_pc[bench],EPS,1-EPS),labels=[0,1])),
      'hier_raw':float(log_loss(yy,np.clip(d.p_cameo_hier_raw.to_numpy(float)[bench],EPS,1-EPS),labels=[0,1])),
      'hier_constrained':float(log_loss(yy,np.clip(new_pc[bench],EPS,1-EPS),labels=[0,1]))}

# expected substitutions calibration
late=d[d.gw>=22].copy()
teamfix=late.groupby(['fixture_uuid','team_id']).agg(actual_subs=('cameo_y','sum'),expected_subs=('expected_team_subs','first'),pred_subs=('p_cameo_hier',lambda s:0.0)).reset_index()
# recompute pred unconditional per group
vals=[]
for (fu,tid),g in late.groupby(['fixture_uuid','team_id']):
    vals.append((fu,tid,float(np.sum((1-g.p_regime)*g.p_cameo_hier))))
vm=pd.DataFrame(vals,columns=['fixture_uuid','team_id','pred_subs'])
teamfix=teamfix.drop(columns='pred_subs').merge(vm,on=['fixture_uuid','team_id'])
res['sub_count_test']={'n_team_fixtures':len(teamfix),'actual_mean':float(teamfix.actual_subs.mean()),'pred_mean':float(teamfix.pred_subs.mean()),'expected_target_mean':float(teamfix.expected_subs.mean()),'mae':float(np.mean(abs(teamfix.pred_subs-teamfix.actual_subs)))}

# by FPL pos for best total variant candidates
basepos=pd.read_csv('/mnt/data/fpl_resume/phase5e/fpl-xpts-2026-27/outputs/v1_1/pstart_v2_core/pstart_v2_fixture_holdout_2025_26.csv',usecols=['gw','fixture_uuid','team_id','player_uuid','pos'])
basepos.player_uuid=basepos.player_uuid.astype(str)
d=d.merge(basepos,on=['gw','fixture_uuid','team_id','player_uuid'],how='left')
out=[]; mask=d.gw>=22
for pos,g in d[mask].groupby('pos'):
    for variant in ['manager_regime','subhier_only','subhier_cameodur','full_duration_subhier']:
        col={'manager_regime':'xm_regime','subhier_only':'xm_subhier_only','subhier_cameodur':'xm_subhier_cameodur','full_duration_subhier':'xm_full_duration_subhier'}[variant]
        e=g[col]-g.minutes
        out.append({'pos':pos,'variant':variant,'n':len(g),'mae':float(abs(e).mean()),'rmse':float(np.sqrt(np.mean(e*e)))})
pd.DataFrame(out).to_csv(ROOT/'substitution_hierarchy_by_position.csv',index=False)

d.to_csv(ROOT/'substitution_hierarchy_predictions.csv',index=False)
(ROOT/'substitution_hierarchy_metrics.json').write_text(json.dumps(res,indent=2)+'\n')
print(json.dumps(res,indent=2))

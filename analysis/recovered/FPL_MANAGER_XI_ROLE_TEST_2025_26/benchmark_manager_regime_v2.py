from pathlib import Path
from collections import defaultdict, Counter
import numpy as np, pandas as pd, json
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import brier_score_loss, log_loss

ROOT=Path('/mnt/data/fpl_resume/phase5e/fpl-xpts-2026-27')
BASE=ROOT/'outputs/v1_1/pstart_v2_core/pstart_v2_fixture_holdout_2025_26.csv'
ROLES=Path('/mnt/data/fpl_resume/role_cache/starter_roles_2025_26.csv')
GWFILE=Path('/mnt/data/fpl5e_recover/fpl-xpts-2026-27/data/cache/history/2025-26/gws/merged_gw.csv')
TEAMS=Path('/mnt/data/fpl5e_recover/fpl-xpts-2026-27/data/cache/history/2025-26/teams.csv')
OUT=Path('/mnt/data/fpl_resume/role_cache')

b=pd.read_csv(BASE); b=b[b.gw>=6].copy(); b.player_uuid=b.player_uuid.astype(str)
r=pd.read_csv(ROLES).sort_values(['team_id','gw','fixture_uuid','slot_order']); r.player_uuid=r.player_uuid.astype(str)
team_names=pd.read_csv(TEAMS).set_index('id')['name'].to_dict()
name_to_id={v:k for k,v in team_names.items()}
# result per team/GW
mg=pd.read_csv(GWFILE,usecols=['GW','team','was_home','team_h_score','team_a_score']).drop_duplicates()
mg['gf']=np.where(mg.was_home,mg.team_h_score,mg.team_a_score); mg['ga']=np.where(mg.was_home,mg.team_a_score,mg.team_h_score)
mg['result']=np.where(mg.gf>mg.ga,1,np.where(mg.gf<mg.ga,-1,0)); mg['team_id']=mg.team.map(name_to_id)
result={(int(x.team_id),int(x.GW)):int(x.result) for x in mg.dropna(subset=['team_id']).itertuples(index=False)}

# regime starts based on documented 2025/26 manager changes. Default regime starts GW1.
# Multiple starts = new manager regime begins that GW.
regime_starts={
  7:[1,22],      # Chelsea: new coach Jan 2026, use first unambiguous next MW
 14:[1,22],      # Man Utd Carrick before MW22
 16:[1,4,9,27],  # Forest: Sep, Oct, Feb changes
 18:[1,32],      # Spurs: De Zerbi before MW32
 19:[1,6],       # West Ham: Nuno before MW6
}
def regime_start(team_id,gw):
    starts=regime_starts.get(team_id,[1]); return max(x for x in starts if x<=gw)

team_games=defaultdict(list)
for (tid,gw,fu),x in r.groupby(['team_id','gw','fixture_uuid'],sort=True):
    team_games[int(tid)].append({'gw':int(gw),'fixture_uuid':str(fu),'formation':x.formation.iloc[0],
                                 'players':set(x.player_uuid.astype(str)),
                                 'roles':dict(zip(x.player_uuid.astype(str),x.role.astype(str)))})

# existing role features
rp=pd.read_csv(OUT/'role_augmented_holdout_predictions.csv'); rp.player_uuid=rp.player_uuid.astype(str)
keep=['gw','fixture_uuid','team_id','player_uuid','role_fit_fast','role_h_fast','role_qmax_fast','role_evidence_fast','role_fit_slow','role_h_slow','role_qmax_slow','role_evidence_slow','role_started_last_gw','p_role','xm_role']

rows=[]
for (gw,fu,tid),grp in b.groupby(['gw','fixture_uuid','team_id'],sort=True):
    gw=int(gw); tid=int(tid); rs=regime_start(tid,gw)
    allhist=[h for h in team_games[tid] if h['gw']<gw]
    hist=[h for h in allhist if h['gw']>=rs]
    hist.sort(key=lambda h:(h['gw'],h['fixture_uuid']))
    last=hist[-1] if hist else None
    # formation prior within current manager regime
    fw=defaultdict(float); denf=0
    for h in hist:
        w=2**(-(gw-h['gw'])/6.0); fw[h['formation']]+=w; denf+=w
    pref=max(fw,key=fw.get) if fw else None; pref_share=fw[pref]/denf if denf else 0
    # lineup transition history within regime and result-conditioned retention
    transitions=[]; byres=defaultdict(list)
    for a,c in zip(hist[:-1],hist[1:]):
        retention=len(a['players']&c['players'])/11.0
        transitions.append(retention); byres[result.get((tid,a['gw']),99)].append(retention)
    stability=np.mean(transitions[-5:]) if transitions else 0.5
    prev_result=result.get((tid,last['gw']),99) if last else 99
    cond_ret=np.mean(byres.get(prev_result,[])) if byres.get(prev_result) else stability
    regime_games=len(hist); regime_maturity=min(regime_games/8.0,1.0)
    for z in grp.itertuples(index=False):
        pid=str(z.player_uuid)
        def wrate(half):
            den=num=0.0
            for h in hist:
                w=2**(-(gw-h['gw'])/half); den+=w; num+=w*(pid in h['players'])
            return num/den if den else 0.0
        core3,core10=wrate(3),wrate(10)
        started_last=1.0 if last and pid in last['players'] else 0.0
        streak=0
        for h in reversed(hist):
            if pid in h['players']: streak+=1
            else: break
        hh=hist[-5:]; recent5=sum(pid in h['players'] for h in hh)/len(hh) if hh else 0
        pf=[h for h in hist if h['formation']==pref] if pref else []
        pf_fit=sum(pid in h['players'] for h in pf)/len(pf) if pf else 0
        # current last role + how often retained same role next match historically
        same_role_trans=[]
        for a,c in zip(hist[:-1],hist[1:]):
            if pid in a['players']:
                same_role_trans.append(1.0 if (pid in c['players'] and a['roles'].get(pid)==c['roles'].get(pid)) else 0.0)
        same_role_ret=np.mean(same_role_trans[-5:]) if same_role_trans else 0.0
        p=float(z.p_start_v2); logit=np.log(np.clip(p,1e-8,1-1e-8)/np.clip(1-p,1e-8,1))
        rows.append({'gw':gw,'fixture_uuid':fu,'team_id':tid,'player_uuid':pid,'y':int(z.y),'minutes':float(z.minutes),
                     'p_base':p,'xm_base':float(z.expected_minutes_v2),'start_minutes_mean':float(z.start_minutes_mean),'cameo_minutes_mean':float(z.cameo_minutes_mean),'p_cameo_given_bench':float(z.p_cameo_given_bench),'base_logit':logit,
                     'regime_core3':core3,'regime_core10':core10,'regime_started_last':started_last,'regime_streak':min(streak,5)/5,'regime_recent5':recent5,
                     'regime_stability':stability,'result_cond_retention':cond_ret,'pref_form_share_regime':pref_share,'pref_form_fit_regime':pf_fit,
                     'same_role_retention':same_role_ret,'regime_maturity':regime_maturity,
                     'incumbent_cond_ret':started_last*cond_ret,'incumbent_stability':started_last*stability,'core_cond_ret':core3*cond_ret,
                     'prev_win':1.0 if prev_result==1 else 0.0,'prev_draw':1.0 if prev_result==0 else 0.0,'prev_loss':1.0 if prev_result==-1 else 0.0})
f=pd.DataFrame(rows).merge(rp[keep],on=['gw','fixture_uuid','team_id','player_uuid'],how='left').fillna(0)
features=['base_logit','role_fit_fast','role_h_fast','role_qmax_fast','role_evidence_fast','role_fit_slow','role_h_slow','role_qmax_slow','role_evidence_slow',
          'regime_core3','regime_core10','regime_started_last','regime_streak','regime_recent5','regime_stability','result_cond_retention','pref_form_share_regime','pref_form_fit_regime','same_role_retention','regime_maturity','incumbent_cond_ret','incumbent_stability','core_cond_ret','prev_win','prev_draw','prev_loss']

def exact11(raw,te):
 out=np.zeros(len(te))
 for _,idx in te.groupby(['fixture_uuid','team_id']).groups.items():
  ii=np.array(list(idx)); p=np.clip(raw[ii],1e-8,1-1e-8); l=np.log(p/(1-p)); lo,hi=-30.,30.
  for _ in range(70):
   mid=(lo+hi)/2
   if (1/(1+np.exp(-(l+mid)))).sum()<11:lo=mid
   else:hi=mid
  out[ii]=1/(1+np.exp(-(l+(lo+hi)/2)))
 return out
f['p_regime']=f.p_base; coefs=[]
for gw in sorted(f.gw.unique()):
 if gw<12: continue
 tr=f[(f.gw>=6)&(f.gw<gw)]; te=f[f.gw==gw]
 if te.empty:continue
 m=LogisticRegression(C=0.2,max_iter=3000).fit(tr[features],tr.y)
 pred=exact11(m.predict_proba(te[features])[:,1],te.reset_index())
 f.loc[te.index,'p_regime']=pred
 coefs.append({'forecast_gw':gw,'intercept':m.intercept_[0],**dict(zip(features,m.coef_[0]))})
f['xm_regime']=f.p_regime*f.start_minutes_mean+(1-f.p_regime)*f.p_cameo_given_bench*f.cameo_minutes_mean
f['p_role']=f.p_role.where(f.p_role>0,f.p_base); f['xm_role']=f.xm_role.where(f.xm_role>0,f.xm_base)

def score(d,p,xm):
 return {'n':len(d),'brier':float(brier_score_loss(d.y,d[p])),'log_loss':float(log_loss(d.y,d[p],labels=[0,1])),'xmins_mae':float(np.mean(abs(d[xm]-d.minutes))),'xmins_rmse':float(np.sqrt(np.mean((d[xm]-d.minutes)**2)))}
res={}
for label,d in [('gw12_38',f[f.gw>=12]),('gw22_38',f[f.gw>=22]),('gw26_38',f[f.gw>=26])]:
 res[label]={'base':score(d,'p_base','xm_base'),'role':score(d,'p_role','xm_role'),'regime':score(d,'p_regime','xm_regime')}
 for ref in ['base','role']:
  res[label]['regime_vs_'+ref+'_pct']={k:100*(res[label]['regime'][k]/res[label][ref][k]-1) for k in ['brier','log_loss','xmins_mae','xmins_rmse']}
res['exact11_max_error']=float(f[f.gw>=12].groupby(['fixture_uuid','team_id']).p_regime.sum().sub(11).abs().max())
(OUT/'manager_regime_v2_metrics.json').write_text(json.dumps(res,indent=2)+'\n')
f.to_csv(OUT/'manager_regime_v2_predictions.csv',index=False); pd.DataFrame(coefs).to_csv(OUT/'manager_regime_v2_coefficients.csv',index=False)
print(json.dumps(res,indent=2))

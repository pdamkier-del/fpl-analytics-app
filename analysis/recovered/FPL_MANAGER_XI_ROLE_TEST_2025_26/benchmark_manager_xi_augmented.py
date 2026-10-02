from pathlib import Path
from collections import defaultdict, Counter
import numpy as np, pandas as pd, json
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import brier_score_loss, log_loss

ROOT=Path('/mnt/data/fpl_resume/phase5e/fpl-xpts-2026-27')
BASE=ROOT/'outputs/v1_1/pstart_v2_core/pstart_v2_fixture_holdout_2025_26.csv'
ROLES=Path('/mnt/data/fpl_resume/role_cache/starter_roles_2025_26.csv')
GWFILE=Path('/mnt/data/fpl5e_recover/fpl-xpts-2026-27/data/cache/history/2025-26/gws/merged_gw.csv')
OUT=Path('/mnt/data/fpl_resume/role_cache')

b=pd.read_csv(BASE); b=b[b.gw>=6].copy(); b.player_uuid=b.player_uuid.astype(str)
r=pd.read_csv(ROLES).sort_values(['team_id','gw','fixture_uuid','slot_order']); r.player_uuid=r.player_uuid.astype(str)

# result by team/GW (first row per fixture-team; enough for previous-match result signal)
g=pd.read_csv(GWFILE)
g=g[['GW','team','was_home','team_h_score','team_a_score']].drop_duplicates()
g['gf']=np.where(g.was_home,g.team_h_score,g.team_a_score); g['ga']=np.where(g.was_home,g.team_a_score,g.team_h_score)
g['result']=np.where(g.gf>g.ga,1,np.where(g.gf<g.ga,-1,0))
# map team name via baseline team id not readily available; instead derive result using fixture team names impossible here.
# We will add previous result later via per-team lineups only when mapped; for now neutral=0. This keeps test clean.

# lineup event objects
team_games=defaultdict(list)
for (tid,gw,fu),x in r.groupby(['team_id','gw','fixture_uuid'],sort=True):
    players=list(x.sort_values('slot_order').player_uuid)
    roles=dict(zip(x.player_uuid,x.role))
    team_games[int(tid)].append({'gw':int(gw),'fixture_uuid':str(fu),'formation':x.formation.iloc[0], 'players':set(players), 'roles':roles})

rows=[]
for (gw,fu,tid),grp in b.groupby(['gw','fixture_uuid','team_id'],sort=True):
    gw=int(gw); tid=int(tid)
    hist=[h for h in team_games[tid] if h['gw']<gw]
    hist.sort(key=lambda x:(x['gw'],x['fixture_uuid']))
    last=hist[-1] if hist else None
    # preferred formation using recency half-life 6 matches/GWs
    fw=defaultdict(float); total_fw=0
    for h in hist:
        w=2**(-(gw-h['gw'])/6.0); fw[h['formation']]+=w; total_fw+=w
    pref_form=max(fw,key=fw.get) if fw else None
    pref_form_share=(fw[pref_form]/total_fw) if total_fw and pref_form else 0.0
    # recent team lineup stability = weighted Jaccard between successive XIs, last 5 transitions
    trans=[]
    for a,c in zip(hist[-6:-1],hist[-5:]):
        inter=len(a['players']&c['players']); union=len(a['players']|c['players']); trans.append(inter/union if union else 0)
    stability=float(np.mean(trans)) if trans else 0.0
    expected_changes=(11*(1-stability)) if trans else 5.5
    # player history summaries
    for z in grp.itertuples(index=False):
        pid=str(z.player_uuid)
        starts=[]; same_form=[]; roles=[]
        for h in hist:
            st=pid in h['players']; starts.append((h['gw'],st))
            if st:
                roles.append((h['gw'],h['roles'].get(pid)))
                if pref_form is not None and h['formation']==pref_form: same_form.append((h['gw'],1))
        def weighted_share(half):
            den=num=0.0
            for h in hist:
                w=2**(-(gw-h['gw'])/half); den+=w; num+=w*(pid in h['players'])
            return num/den if den else 0.0
        core_fast=weighted_share(3.0); core_slow=weighted_share(10.0)
        started_last=1.0 if last and pid in last['players'] else 0.0
        same_role_last=0.0
        last_role=None
        if last and pid in last['players']:
            last_role=last['roles'].get(pid)
            same_role_last=1.0
        # consecutive starts immediately before target (max 5 normalized)
        streak=0
        for h in reversed(hist):
            if pid in h['players']: streak+=1
            else: break
        streak_norm=min(streak,5)/5.0
        # starts in last 2/3/5 actual team games
        def recent_rate(n):
            hh=hist[-n:]
            return sum(pid in h['players'] for h in hh)/len(hh) if hh else 0.0
        # compatibility with preferred formation: starts/player team games when pref formation used
        pf_games=[h for h in hist if h['formation']==pref_form] if pref_form else []
        pf_fit=sum(pid in h['players'] for h in pf_games)/len(pf_games) if pf_games else 0.0
        # player role persistence entropy-ish: max share of observed roles
        rc=Counter(rr for _,rr in roles if rr)
        role_persist=max(rc.values())/sum(rc.values()) if rc else 0.0
        p=float(z.p_start_v2); logit=np.log(np.clip(p,1e-8,1-1e-8)/np.clip(1-p,1e-8,1))
        rows.append({
            'gw':gw,'fixture_uuid':fu,'team_id':tid,'player_uuid':pid,'y':int(z.y),'minutes':float(z.minutes),
            'p_base':p,'xm_base':float(z.expected_minutes_v2),'start_minutes_mean':float(z.start_minutes_mean),
            'cameo_minutes_mean':float(z.cameo_minutes_mean),'p_cameo_given_bench':float(z.p_cameo_given_bench),'base_logit':logit,
            'core_fast':core_fast,'core_slow':core_slow,'started_last':started_last,'streak':streak_norm,
            'start_rate2':recent_rate(2),'start_rate3':recent_rate(3),'start_rate5':recent_rate(5),
            'team_stability':stability,'expected_changes':expected_changes,'pref_form_share':pref_form_share,
            'pref_form_fit':pf_fit,'role_persistence':role_persist,
            'incumbent_x_stability':started_last*stability,'core_x_stability':core_fast*stability,
            'pref_fit_x_pref_share':pf_fit*pref_form_share,
        })
f=pd.DataFrame(rows).reset_index(drop=True)
# merge existing role features from prior benchmark, preserving deadline-safe calculation
rp=pd.read_csv(OUT/'role_augmented_holdout_predictions.csv')
rp.player_uuid=rp.player_uuid.astype(str)
keep=['gw','fixture_uuid','team_id','player_uuid','role_fit_fast','role_h_fast','role_qmax_fast','role_evidence_fast','role_fit_slow','role_h_slow','role_qmax_slow','role_evidence_slow','role_started_last_gw']
f=f.merge(rp[keep],on=['gw','fixture_uuid','team_id','player_uuid'],how='left').fillna(0)

role_features=['base_logit','role_fit_fast','role_h_fast','role_qmax_fast','role_evidence_fast','role_fit_slow','role_h_slow','role_qmax_slow','role_evidence_slow','role_started_last_gw']
xi_features=role_features+['core_fast','core_slow','started_last','streak','start_rate2','start_rate3','start_rate5','team_stability','expected_changes','pref_form_share','pref_form_fit','role_persistence','incumbent_x_stability','core_x_stability','pref_fit_x_pref_share']

def exact11(raw,te):
    out=np.zeros(len(te))
    for _,idx in te.groupby(['fixture_uuid','team_id']).groups.items():
        ii=np.array(list(idx)); p=np.clip(raw[ii],1e-8,1-1e-8); l=np.log(p/(1-p)); lo,hi=-30.,30.
        for _ in range(70):
            mid=(lo+hi)/2
            if (1/(1+np.exp(-(l+mid)))).sum()<11: lo=mid
            else: hi=mid
        out[ii]=1/(1+np.exp(-(l+(lo+hi)/2)))
    return out

f['p_xi']=f.p_base
coefs=[]
for gw in sorted(f.gw.unique()):
    if gw<12: continue
    tr=f[(f.gw>=6)&(f.gw<gw)]; te=f[f.gw==gw]
    if len(tr)<1000 or te.empty: continue
    m=LogisticRegression(C=0.3,max_iter=2500)
    m.fit(tr[xi_features],tr.y)
    tt=te.reset_index(); pred=exact11(m.predict_proba(te[xi_features])[:,1],tt)
    f.loc[te.index,'p_xi']=pred
    coefs.append({'forecast_gw':gw,'intercept':m.intercept_[0],**dict(zip(xi_features,m.coef_[0]))})
f['xm_xi']=f.p_xi*f.start_minutes_mean+(1-f.p_xi)*f.p_cameo_given_bench*f.cameo_minutes_mean

# role-only comparator from existing output, align
comp=rp[['gw','fixture_uuid','team_id','player_uuid','p_role','xm_role']].copy()
f=f.merge(comp,on=['gw','fixture_uuid','team_id','player_uuid'],how='left')
f['p_role']=f.p_role.fillna(f.p_base); f['xm_role']=f.xm_role.fillna(f.xm_base)

def score(d,pcol,xmcol):
    return {'n':len(d),'brier':float(brier_score_loss(d.y,d[pcol])),'log_loss':float(log_loss(d.y,d[pcol],labels=[0,1])),
            'xmins_mae':float(np.mean(np.abs(d[xmcol]-d.minutes))),'xmins_rmse':float(np.sqrt(np.mean((d[xmcol]-d.minutes)**2)))}
res={}
for label,sub in [('active_gw12_38',f[f.gw>=12]),('late_gw22_38',f[f.gw>=22]),('late_gw26_38',f[f.gw>=26])]:
    res[label]={k:score(sub,*cols) for k,cols in {'base':('p_base','xm_base'),'role':('p_role','xm_role'),'manager_xi':('p_xi','xm_xi')}.items()}
    for ref in ['base','role']:
        res[label]['manager_vs_'+ref+'_pct']={m:100*(res[label]['manager_xi'][m]/res[label][ref][m]-1) for m in ['brier','log_loss','xmins_mae','xmins_rmse']}
# by team + position on active
for groupcol,name in [('team_id','by_team'),('role_family','by_role_family')]:
    pass
# attach actual target role family for target match where starter; for bench use latest historical dominant role
# For fair segment, use FPL pos as broad and last-known role-family from role history cutoff-safe
role_family_map={}
for tid,games in team_games.items():
    for h in games:
        for pid,rr in h['roles'].items(): role_family_map[(tid,h['gw'],pid)]=rr
# just output by baseline FPL position from source
pos=b[['gw','fixture_uuid','team_id','player_uuid','pos']].copy(); pos.player_uuid=pos.player_uuid.astype(str)
f=f.merge(pos,on=['gw','fixture_uuid','team_id','player_uuid'],how='left')

def group_report(col,sub):
    out=[]
    for val,d in sub.groupby(col):
        if len(d)<50: continue
        a=score(d,'p_role','xm_role'); z=score(d,'p_xi','xm_xi')
        out.append({col:val,'n':len(d),**{'role_'+k:v for k,v in a.items() if k!='n'},**{'xi_'+k:v for k,v in z.items() if k!='n'},
                    'xmins_mae_improve_pct':100*(1-z['xmins_mae']/a['xmins_mae']), 'brier_improve_pct':100*(1-z['brier']/a['brier']), 'logloss_improve_pct':100*(1-z['log_loss']/a['log_loss'])})
    return pd.DataFrame(out).sort_values('xmins_mae_improve_pct',ascending=False)

group_report('team_id',f[f.gw>=12]).to_csv(OUT/'manager_xi_by_team.csv',index=False)
group_report('pos',f[f.gw>=12]).to_csv(OUT/'manager_xi_by_position.csv',index=False)
pd.DataFrame(coefs).to_csv(OUT/'manager_xi_expanding_coefficients.csv',index=False)
f.to_csv(OUT/'manager_xi_holdout_predictions.csv',index=False)
res['exact11_max_error']=float(f[f.gw>=12].groupby(['fixture_uuid','team_id']).p_xi.sum().sub(11).abs().max())
(OUT/'manager_xi_holdout_metrics.json').write_text(json.dumps(res,indent=2)+'\n')
print(json.dumps(res,indent=2))

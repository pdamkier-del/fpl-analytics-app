#!/usr/bin/env python3
"""MM-only experimental replay: reuse historical 2025/26 role/formation ledger with PR9 B.

Never use current target formation/roles as forecast features. 2024/25 is reported
as unavailable for this joined ledger, not silently filled from a different season.
"""
from pathlib import Path
from collections import defaultdict
import json
import numpy as np
import pandas as pd
from scipy.optimize import linear_sum_assignment,brentq
from scipy.special import expit,logit
from individual_mm_evidence import load_frame
from fpl_v1_1_model.role_classifier import template,role_family

ROOT=Path(__file__).resolve().parents[1]
SRC=ROOT/'analysis/results/individual-mm-refinement-20261016/predictions.npz'
ROLES=ROOT/'analysis/results/reproducible-role-v1/classified_starters.csv'
OUT=ROOT/'analysis/results/mm-formation-replay-20261017'
MODES=['original','best_existing','B']
BANDS=[-1e-9,5,15,30,60,np.inf]
LABELS=['0-5','5-15','15-30','30-60','over-60']

def soft_role_scores(player,past):
    vals=defaultdict(float)
    for prior in past:
        if prior['player_uuid']!=player:continue
        days=max(0.,prior['age_days'])
        vals[prior['role']]+=2**(-days/70.)
    return vals

def calculate():
    OUT.mkdir(parents=True,exist_ok=True)
    p=load_frame(SRC)
    p=p[p['mode'].isin(MODES)&p['season'].eq('2025-26')&p.gw.ge(6)].copy()
    p['player_uuid']=p.player_uuid.astype(str)
    p['fixture_uuid']=p.fixture_uuid.astype(str)
    p['cutoff']=pd.to_datetime(p.cutoff,utc=True,format='mixed')
    for arm in MODES:
        if len(p[p['mode']==arm])!=26159:raise ValueError('Missing PR9 forecasts '+arm)
    history=pd.read_csv(ROLES,low_memory=False)
    required={'fixture_uuid','player_uuid','team_id','formation','final_role','kickoff'}
    if not required.issubset(history):raise ValueError('Missing existing role fields '+str(required-set(history)))
    history=history.dropna(subset=list(required)).copy()
    history['player_uuid']=history.player_uuid.astype(str)
    history['kickoff']=pd.to_datetime(history.kickoff,utc=True,errors='coerce')
    history['known_at']=history.kickoff+pd.Timedelta(hours=3)
    history=history.dropna(subset=['known_at'])
    history['team_id']=history.team_id.astype(int)
    hgames=[]
    for (t,fix),g in history.groupby(['team_id','fixture_uuid'],sort=True):
        forms=g.formation.astype(str).unique()
        if len(forms)!=1 or len(g)!=11:continue
        form=forms[0];slots=['GK']+[r for line in template(form) for r in line]
        if len(slots)!=11:continue
        hgames.append((int(t),str(fix),g.known_at.iloc[0],form,g[['player_uuid','final_role']].to_dict('records')))
    ledger=defaultdict(list)
    for item in hgames:ledger[item[0]].append(item)
    for club in ledger:ledger[club].sort(key=lambda x:x[2])
    all_comp=[]
    pred=[]
    diagnostics=[]
    for (season,fix,team),joined in p.groupby(['season','fixture_uuid','team_id'],sort=True):
        g=joined[joined['mode'].eq('B')].copy()
        if len(g)<11 or int(g.y.sum())!=11:continue
        cut=g.cutoff.iloc[0]
        games=[a for a in ledger.get(int(team),[]) if a[2]<cut and a[1]!=str(fix)]
        prior_formation=None
        if games:
            recent=games[-12:][::-1]
            masses=defaultdict(float)
            for lag,gm in enumerate(recent):masses[gm[3]]+=2**(-lag/5.)
            prior_formation=max(sorted(masses),key=lambda f:masses[f])
        slots=(['GK']+[r for line in template(prior_formation) for r in line]) if prior_formation else []
        formation_available=len(slots)==11 and len(games)>=3
        players=[]
        for a in games:
            age=max(0.,(cut-a[2]).total_seconds()/86400)
            for r in a[4]:players.append({'player_uuid':r['player_uuid'],'role':str(r['final_role']),'age_days':age})
        scores={pl:soft_role_scores(pl,players) for pl in g.player_uuid}
        actual_truth=g.set_index('player_uuid').y.to_dict()
        chosen=[]
        if formation_available:
            ids=g.player_uuid.tolist()
            mat=np.zeros((11,len(ids)))
            pp=np.clip(g.p.to_numpy(float),1e-7,1-1e-7)
            for si,slot in enumerate(slots):
                for j,pl in enumerate(ids):
                    prev=scores[pl];total=sum(prev.values())
                    exact=prev.get(slot,0.)/total if total else 0.
                    family=sum(v for k,v in prev.items() if role_family(k)==role_family(slot))/total if total else 0.
                    compat=0.02+0.78*exact+0.20*family
                    if total and role_family(slot)=='GK' and family<.5:compat=1e-4
                    if total and role_family(slot)!='GK' and prev.get('GK',0)>total*.5:compat=1e-4
                    mat[si,j]=logit(pp[j])+0.5*np.log(compat)
            ix,jx=linear_sum_assignment(-mat)
            chosen=[ids[i] for i in jx]
            if len(set(chosen))!=11:raise ValueError('Duplicate selected player')
        for arm in MODES:
            x=joined[joined['mode'].eq(arm)].copy()
            ids=x.player_uuid.tolist()
            top=set(x.sort_values(['p','player_uuid'],ascending=[False,True]).head(11).player_uuid)
            if len(x)!=len(g) or set(ids)!=set(g.player_uuid):raise ValueError('Unmatched fixture team per arm')
            hits=int(sum(actual_truth.get(k,0) for k in top))
            pred.append(dict(mode=arm,season=season,fixture_uuid=fix,team_id=team,correct=hits,selection='raw_top11',formation=prior_formation,role_games=len(games)))
        if formation_available:
            hits=int(sum(actual_truth.get(k,0) for k in chosen))
            pred.append(dict(mode='B_role_formation',season=season,fixture_uuid=fix,team_id=team,correct=hits,selection='constrained_role_assignment',formation=prior_formation,role_games=len(games)))
            # Diagnostic MM candidate: modest untrained slot selection nudge, source hard zeros preserved.
            # Report separately; cannot claim this is independently calibrated.
            x=g.copy()
            raw=x.p.to_numpy(float)
            nonzero=(raw>1e-10)&(raw<1-1e-10)
            z=logit(np.clip(raw,1e-8,1-1e-8))+np.where(x.player_uuid.isin(chosen),.25,-.25)
            # preserve player probability caps at original B and avoid inventing permission
            # to override hard zeros: this is a bounded diagnostic, no new source integration
            proposed=raw.copy()
            if nonzero.any():proposed[nonzero]=expit(z[nonzero])
            # sum-11 reproject over non-hard-positive values, keeping p=0 strict
            feasible=(raw>1e-10)&(raw<1-1e-10)
            fixed=raw[~feasible].sum()
            if feasible.any() and 0<=11-fixed<=feasible.sum():
                sh=brentq(lambda d:expit(z[feasible]+d).sum()+fixed-11,-40,40)
                proposed[feasible]=expit(z[feasible]+sh)
            else:proposed=raw
            x['p_new']=proposed
            x['x_new']=proposed*x.s+(1-proposed)*x.q*x.c
            x['mode']='B_role_nudge_diagnostic'
            all_comp.append(x)
        diagnostics.append(dict(season=season,fixture_uuid=fix,team_id=team,formation=prior_formation,role_games=len(games),can_score=formation_available))
    xi=pd.DataFrame(pred);xi.to_csv(OUT/'xi_fixtures.csv',index=False)
    coverage=pd.DataFrame(diagnostics);coverage.to_csv(OUT/'role_coverage.csv',index=False)
    metrics=[]
    for arm,gg in xi.groupby('mode'):
        for season,hh in gg.groupby('season'):
            for k in range(12):
                metrics.append(dict(mode=arm,season=season,correct=k,count=int((hh.correct==k).sum()),denominator=len(hh),percentage=100*(hh.correct==k).mean()))
    pd.DataFrame(metrics).to_csv(OUT/'xi_hit_distribution.csv',index=False)
    # Fair paired XI comparison on same formation-coverable fixtures
    role_keys=xi[xi['mode']=='B_role_formation'][['season','fixture_uuid','team_id']]
    matched=xi.merge(role_keys,on=['season','fixture_uuid','team_id'],validate='many_to_one')
    matched.groupby('mode').agg(games=('correct','size'),average_correct=('correct','mean'),exact11=('correct',lambda x:100*(x==11).mean()),atleast10=('correct',lambda x:100*(x>=10).mean())).reset_index().to_csv(OUT/'xi_matched_comparison.csv',index=False)
    base=p.copy()
    if all_comp:
        new=pd.concat(all_comp,ignore_index=True)
        new['x']=new.x_new;new['p']=new.p_new
        base=pd.concat([base,new],ignore_index=True)
    rows=[];bands=[]
    for arm,g in base.groupby('mode'):
        g=g.copy();g['abs_error']=(g.x-g.minutes).abs();g['error']=(g.x-g.minutes)
        rows.append(dict(mode=arm,rows=len(g),mae=g.abs_error.mean(),rmse=np.sqrt(np.mean(g.error**2)),start_brier=np.mean((g.p-g.y)**2),median_error=g.abs_error.median(),p90=g.abs_error.quantile(.9),p95=g.abs_error.quantile(.95),p99=g.abs_error.quantile(.99),top10_error_share=100*g.abs_error.nlargest(int(np.ceil(.1*len(g)))).sum()/g.abs_error.sum()))
        for lo,hi,label in zip(BANDS[:-1],BANDS[1:],LABELS):
            z=g[(g.abs_error>lo)&(g.abs_error<=hi)]
            bands.append(dict(mode=arm,band=label,count=len(z),percent=100*len(z)/len(g),error_share=100*z.abs_error.sum()/g.abs_error.sum()))
    pd.DataFrame(rows).to_csv(OUT/'mm_metrics.csv',index=False)
    pd.DataFrame(bands).to_csv(OUT/'minute_error_bands.csv',index=False)
    # top errors per actual played/not-played, expected starter/not starter are diagnostics only
    base['abs_error']=(base.x-base.minutes).abs()
    base['error_kind']=np.select([
        (base.p>=.5)&(base.y==0), (base.p<.5)&(base.y==1),
        (base.y==1)&(base.p>=.5), (base.y==0)&(base.minutes>0)],
        ['expected_start_did_not','unexpected_start','started_duration_or_probability','cameo_or_probability'],default='correct_nonappearance_or_other')
    base.groupby(['mode','error_kind']).agg(rows=('abs_error','size'),mae=('abs_error','mean'),absolute_error_sum=('abs_error','sum')).reset_index().to_csv(OUT/'error_types.csv',index=False)
    base.sort_values('abs_error',ascending=False).groupby('mode').head(100)[['mode','fixture_uuid','team_id','player_uuid','gw','p','x','y','minutes','abs_error','error_kind']].to_csv(OUT/'top100_errors.csv',index=False)
    (OUT/'summary.json').write_text(json.dumps(dict(capsule_rows=26159,historical_formation_source='2025/26 classified_starters.csv',formation_role_coverage_fixtures=int(coverage.can_score.sum()),total_team_fixtures=len(coverage),constraints='11 slots in the selected historical formation; no target formation used as forecast input',limitations=['Historical kickoff+3h role availability proxy, not verified publication time','2024-25 official role ledger unavailable for direct equivalent role simulation','B_role_nudge_diagnostic is fixed heuristic for research; not fitted or approved','No full Monte Carlo simulator, PM or TS; xM recomputed analytically']),indent=2)+'\n')
    print((OUT/'summary.json').read_text())
    print(pd.read_csv(OUT/'xi_matched_comparison.csv').to_string(index=False))
    print(pd.read_csv(OUT/'mm_metrics.csv').to_string(index=False))
if __name__=='__main__':calculate()

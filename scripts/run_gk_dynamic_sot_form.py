#!/usr/bin/env python3
"""Dynamic goalkeeper SOT/save opportunity experiment.

Goal
----
Test whether the keeper miss is mainly due to a stale SOT opportunity forecast.
The existing long-run SOT model is preserved as the baseline. Candidate models
add a *dynamic form residual* based on fast-vs-slow team attack/defence form.

Features are cutoff-safe and use only prior Premier League fixtures:
- fast/slow attacking SOT ratio
- fast/slow opponent SOT-allowed ratio
- optionally fast/slow attacking xG ratio
- optionally fast/slow opponent xGA ratio

The residual is learned on top of the frozen arithmetic SOT structure, then
mapped to saves with the already frozen save equation. No constant save boost
and no save-bucket correction is used.

Protocol:
- fit residual coefficients on GW6-15
- select feature family / fast half-life on GW16-21
- refit GW6-21
- reused diagnostic GW22-38
- marginal joint xP test on top of the saved DefCon finalist

Not an independent holdout. No automatic promotion.
"""
from __future__ import annotations
import json,sys
from dataclasses import replace
from pathlib import Path
import numpy as np
import pandas as pd
from scipy.optimize import minimize
from scipy.special import gammaln

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'));sys.path.insert(0,str(ROOT/'scripts'))

from fpl_v1_1_model.paired_joint import read_frozen_table,build_pair,run_pair
from run_v4rc_experiment import write_json,sha

FROZEN=ROOT/'analysis/results/deadline-joint-inputs-v1'
ROLE=ROOT/'analysis/results/role-event-priors-20261005-v1'
DC=ROOT/'analysis/results/defcon-threshold-finalist-20261005-v1/calibrated_dc.csv.gz'
KEEPER_FIT=ROOT/'analysis/results/joint-team-keeper-recovery-v1/keeper_fit.json'
OUT=ROOT/'analysis/results/gk-dynamic-sot-form-20261005-v1'

FAST_H=[3.0,6.0,9.0]
L2=[1.0,10.0,50.0]
FAMILIES={
  'sot_form':['att_sot_ratio','def_sot_ratio'],
  'sot_xg_form':['att_sot_ratio','def_sot_ratio','att_xg_ratio','def_xga_ratio'],
}


def full_poisson_nll(y,mu):
    y=np.asarray(y,float);mu=np.maximum(np.asarray(mu,float),1e-9)
    return float(np.mean(mu-y*np.log(mu)+gammaln(y+1)))


def point_metrics(actual_saves,lam):
    actual=np.asarray(actual_saves,float);lam=np.asarray(lam,float)
    # exact expected floor(S/3) under Poisson
    pts=[]
    for x in lam:
        p=np.exp(-x);cum=p;tot=0.;n=0
        while n<200 and 1-cum>1e-12:
            n+=1;p*=x/n;cum+=p;tot+=(n//3)*p
        pts.append(tot)
    pts=np.asarray(pts)
    actual_pts=np.floor(actual/3)
    e=pts-actual_pts
    return dict(
      save_nll=full_poisson_nll(actual,lam),
      save_mae=float(np.mean(np.abs(lam-actual))),
      save_rmse=float(np.sqrt(np.mean((lam-actual)**2))),
      save_bias=float(np.mean(lam-actual)),
      point_mae=float(np.mean(np.abs(e))),
      point_rmse=float(np.sqrt(np.mean(e**2))),
      point_bias=float(np.mean(e)),
      mean_pred_saves=float(np.mean(lam)),mean_actual_saves=float(np.mean(actual)),
      mean_pred_points=float(np.mean(pts)),mean_actual_points=float(np.mean(actual_pts)),
      p3=float(np.mean(1-np.exp(-lam)*(1+lam+lam**2/2))),
      actual_p3=float(np.mean(actual>=3)))


def score(y,p):
    e=np.asarray(p)-np.asarray(y)
    return dict(mae=float(np.mean(np.abs(e))),rmse=float(np.sqrt(np.mean(e**2))),bias=float(np.mean(e)))


def ewma(state,key,value,h):
    decay=2**(-1/h)
    w,s=state.get(key,(0.,0.))
    w*=decay;s*=decay
    w+=1.;s+=float(value)
    state[key]=(w,s)


def get_mean(state,key,default):
    w,s=state.get(key,(0.,0.))
    return float(s/w) if w>0 else float(default)


def load_side_rows():
    """Build one provider-code side row per PL fixture from raw snapshots."""
    rows=[]
    for gw in range(1,39):
        p=ROOT/f'data_v1_1/raw/fpl-core-2025-26/GW{gw}/fixtures.csv'
        z=pd.read_csv(p)
        z=z[(z.gameweek==gw)&(z.tournament.astype(str).str.lower().eq('prem'))].copy()
        for r in z.itertuples(index=False):
            common=dict(gw=int(gw),match_id=str(r.match_id),kickoff=pd.Timestamp(r.kickoff_time))
            rows.append(dict(**common,team_code=int(r.home_team),opp_code=int(r.away_team),home=1,
                sot=float(r.home_shots_on_target),opp_sot=float(r.away_shots_on_target),
                xg=float(r.home_expected_goals_xg),opp_xg=float(r.away_expected_goals_xg),
                actual_saves=float(r.home_keeper_saves)))
            rows.append(dict(**common,team_code=int(r.away_team),opp_code=int(r.home_team),home=0,
                sot=float(r.away_shots_on_target),opp_sot=float(r.home_shots_on_target),
                xg=float(r.away_expected_goals_xg),opp_xg=float(r.home_expected_goals_xg),
                actual_saves=float(r.away_keeper_saves)))
    d=pd.DataFrame(rows).sort_values(['kickoff','match_id','home'],ascending=[True,True,False]).reset_index(drop=True)
    return d


def sequential_features(rows,fast_h):
    fit=json.loads(KEEPER_FIT.read_text())
    long_att=float(fit['selection_protocol']['half_lives_fixed_not_tuned']['attack'])
    long_def=float(fit['selection_protocol']['half_lives_fixed_not_tuned']['defence'])
    sotfit=fit['selected_sot'];savefit=fit['selected_save']

    states={}
    for name,h in [('att_slow',long_att),('def_slow',long_def),
                   ('att_fast',fast_h),('def_fast',fast_h),
                   ('xg_slow',long_att),('xga_slow',long_def),
                   ('xg_fast',fast_h),('xga_fast',fast_h)]:
        states[name]={}

    out=[]
    league_sot=[];league_xg=[]
    for (kick,mid),g in rows.groupby(['kickoff','match_id'],sort=True):
        lg_sot=float(np.mean(league_sot)) if league_sot else 4.5
        lg_xg=float(np.mean(league_xg)) if league_xg else 1.4
        for r in g.itertuples(index=False):
            t=int(r.team_code);o=int(r.opp_code)
            # require enough prior team games for stable current model comparison
            nslow=states['att_slow'].get(t,(0,0))[0]
            oslow=states['def_slow'].get(o,(0,0))[0]
            if nslow>=4 and oslow>=4:
                A=get_mean(states['att_slow'],t,lg_sot)
                D=get_mean(states['def_slow'],o,lg_sot)
                Af=get_mean(states['att_fast'],t,A)
                Df=get_mean(states['def_fast'],o,D)
                X=get_mean(states['xg_slow'],t,lg_xg)
                XA=get_mean(states['xga_slow'],o,lg_xg)
                Xf=get_mean(states['xg_fast'],t,X)
                XAf=get_mean(states['xga_fast'],o,XA)
                base_sot=np.exp(float(sotfit['intercept'])+float(sotfit['attacker_home_log_effect'])*int(r.home))*(
                    float(sotfit['opponent_sot_for_weight'])*A+float(sotfit['team_sot_allowed_weight'])*D)
                base_sot=float(np.clip(base_sot,.05,15))
                base_save=np.exp(float(savefit['intercept'])+float(savefit['attacker_home_log_effect'])*int(r.home))*base_sot**float(savefit['sot_exponent'])
                out.append(dict(
                  gw=int(r.gw),match_id=r.match_id,team_code=t,opp_code=o,home=int(r.home),
                  actual_sot=float(r.sot),actual_saves=float(r.actual_saves),
                  base_sot=base_sot,base_save=float(np.clip(base_save,.01,12)),
                  att_sot_ratio=float(np.log(max(Af,.05)/max(A,.05))),
                  def_sot_ratio=float(np.log(max(Df,.05)/max(D,.05))),
                  att_xg_ratio=float(np.log(max(Xf,.05)/max(X,.05))),
                  def_xga_ratio=float(np.log(max(XAf,.05)/max(XA,.05)))))
        # update only after all sides in fixture were forecast
        for r in g.itertuples(index=False):
            t=int(r.team_code)
            for name,val,h in [
              ('att_slow',r.sot,long_att),('def_slow',r.opp_sot,long_def),
              ('att_fast',r.sot,fast_h),('def_fast',r.opp_sot,fast_h),
              ('xg_slow',r.xg,long_att),('xga_slow',r.opp_xg,long_def),
              ('xg_fast',r.xg,fast_h),('xga_fast',r.opp_xg,fast_h)]:
                ewma(states[name],t,val,h)
            league_sot.append(float(r.sot));league_xg.append(float(r.xg))
    return pd.DataFrame(out)


def fit_residual(df,features,l2,train,target='sot'):
    X=df[features].to_numpy(float);mu=X[train].mean(0);sd=X[train].std(0);sd[sd<1e-8]=1
    Z=(X-mu)/sd
    y=df['actual_'+target].to_numpy(float)
    base=df['base_'+target].to_numpy(float)
    Xt=Z[train];yt=y[train];off=np.log(np.maximum(base[train],1e-9))
    def fg(b):
        z=off+Xt@b;pred=np.exp(np.clip(z,-20,20))
        loss=np.mean(pred-yt*z)+.5*l2*np.dot(b,b)/len(yt)
        grad=Xt.T@(pred-yt)/len(yt)+l2*b/len(yt)
        return float(loss),grad
    res=minimize(lambda b:fg(b),np.zeros(len(features)),jac=True,method='L-BFGS-B')
    if not res.success:raise RuntimeError(res.message)
    mult=np.exp(np.clip(Z@res.x,-2,2))
    return base*mult,dict(features=features,l2=float(l2),coef=res.x.tolist(),mean=mu.tolist(),scale=sd.tolist())


def map_sot_to_save(sot,home):
    fit=json.loads(KEEPER_FIT.read_text())['selected_save']
    return np.clip(np.exp(float(fit['intercept'])+float(fit['attacker_home_log_effect'])*np.asarray(home,float))*np.asarray(sot,float)**float(fit['sot_exponent']),.01,12)


def main():
    if OUT.exists():raise FileExistsError(OUT)
    OUT.mkdir(parents=True)
    write_json(OUT/'protocol.json',dict(
      baseline='frozen long-run arithmetic SOT model',
      candidate='fast-vs-slow recency residual on SOT opportunity',
      train='GW6-15',selection='GW16-21',reused_diagnostic='GW22-38',
      fast_half_lives=FAST_H,families=FAMILIES,l2=L2,
      save_mapping='unchanged frozen sot_only mapping',promotion_allowed=False))

    raw=load_side_rows()
    rows=[]
    frames={}
    for h in FAST_H:
        d=sequential_features(raw,h);frames[h]=d
        tr=d.gw.between(6,15).to_numpy();va=d.gw.between(16,21).to_numpy()
        base=point_metrics(d.loc[va,'actual_saves'],d.loc[va,'base_save'])
        for fam,features in FAMILIES.items():
            for l2 in L2:
                sot,model=fit_residual(d,features,l2,tr,'sot')
                save=map_sot_to_save(sot,d.home)
                m=point_metrics(d.loc[va,'actual_saves'],save[va])
                rows.append(dict(fast_h=h,family=fam,l2=l2,**m,
                    delta_save_nll=m['save_nll']-base['save_nll'],
                    delta_point_mae=m['point_mae']-base['point_mae'],
                    delta_point_rmse=m['point_rmse']-base['point_rmse']))
    cand=pd.DataFrame(rows).sort_values(['save_nll','point_mae','point_rmse']).reset_index(drop=True)
    cand.to_csv(OUT/'development_candidates.csv',index=False)
    best=cand.iloc[0];h=float(best.fast_h);fam=str(best.family);l2=float(best.l2)
    d=frames[h];finaltr=d.gw.between(6,21).to_numpy();test=d.gw.between(22,38).to_numpy()
    sot,model=fit_residual(d,FAMILIES[fam],l2,finaltr,'sot')
    save=map_sot_to_save(sot,d.home)
    base_test=point_metrics(d.loc[test,'actual_saves'],d.loc[test,'base_save'])
    new_test=point_metrics(d.loc[test,'actual_saves'],save[test])
    write_json(OUT/'selection.json',dict(fast_h=h,family=fam,l2=l2,model=model))
    write_json(OUT/'keeper_metrics.json',dict(baseline=base_test,candidate=new_test,
      delta={k:new_test[k]-base_test[k] for k in ['save_nll','save_mae','save_rmse','save_bias','point_mae','point_rmse','point_bias']}))

    # Map provider side forecast to canonical fixture/team through classified starters + lineups.
    labels=pd.read_csv(ROOT/'analysis/results/reproducible-role-v1/classified_starters.csv',
                       usecols=['match_id','fixture_uuid','team_id','player'])
    maps=[]
    for gw in range(22,39):
        line=pd.read_csv(ROOT/f'data_v1_1/raw/all-competitions-2025-26/GW{gw}/lineups.csv')
        line=line[line.is_starting.astype(str).str.lower().isin(['true','1','yes'])].copy()
        j=line.merge(labels,left_on=['match_id','player_name'],right_on=['match_id','player'],how='inner',validate='many_to_many')
        maps.append(j[['match_id','team_code','fixture_uuid','team_id']].drop_duplicates())
    mp=pd.concat(maps,ignore_index=True).drop_duplicates(['match_id','team_code'])
    fd=d.loc[test,['gw','match_id','team_code','base_save']].copy()
    fd['candidate_save']=save[test]
    fd=fd.merge(mp,on=['match_id','team_code'],how='inner',validate='one_to_one')
    fd[['fixture_uuid','team_id','gw','base_save','candidate_save']].to_csv(OUT/'joint_keeper_lambdas.csv.gz',index=False,compression='gzip')

    # Marginal joint test on top of final DC candidate.
    role=read_frozen_table(ROLE,'candidate_inputs')
    dc=pd.read_csv(DC)[['fixture_uuid','player_uuid','mu_cal']]
    role=role.merge(dc,on=['fixture_uuid','player_uuid'],how='left',validate='one_to_one')
    role['mu_dc']=role.mu_cal.fillna(role.mu_dc);role=role.drop(columns=['mu_cal'])
    lookup=fd.set_index(['fixture_uuid','team_id']).candidate_save.to_dict()
    truth=read_frozen_table(FROZEN,'targets')
    rec=[]
    for i,(fx,g) in enumerate(role[role.gw.between(22,38)].groupby('fixture_uuid',sort=True)):
        _,base=build_pair(g)
        treat=replace(base,players=tuple(replace(p,lambda_saves=float(lookup.get((fx,int(p.team)),p.lambda_saves))) if p.is_keeper else p for p in base.players))
        a,b=run_pair(base,treat,n=320,seed=34092501+i)
        for r in g.itertuples():
            rec.append(dict(fixture_uuid=fx,player_uuid=r.player_uuid,gw=r.gw,
                final_dc=a[r.player_uuid]['xPts_nonbonus'],
                final_dc_gk_dynamic=b[r.player_uuid]['xPts_nonbonus'],
                base_save_points=a[r.player_uuid]['save_points'],
                dynamic_save_points=b[r.player_uuid]['save_points']))
    pred=pd.DataFrame(rec);sc=pred.merge(truth,on=['fixture_uuid','player_uuid'],validate='one_to_one')
    y=sc.total_points-sc.bonus;m0=score(y,sc.final_dc);m1=score(y,sc.final_dc_gk_dynamic)
    report=dict(classification='reused_diagnostic_not_independent_holdout',
      selected=dict(fast_h=h,family=fam,l2=l2),keeper_metrics={'baseline':base_test,'candidate':new_test},
      rows=len(sc),fixtures=int(sc.fixture_uuid.nunique()),draws_per_fixture=320,
      nonbonus={'final_dc':m0,'final_dc_plus_dynamic_gk':m1},
      delta_joint={k:m1[k]-m0[k] for k in ['mae','rmse','bias']},promoted=False)
    write_json(OUT/'joint_metrics.json',report)
    pred.to_csv(OUT/'joint_predictions.csv.gz',index=False,compression='gzip')
    outs=[p for p in sorted(OUT.iterdir()) if p.name!='manifest.json']
    write_json(OUT/'manifest.json',dict(sources=[dict(path='scripts/run_gk_dynamic_sot_form.py',sha256=sha(Path(__file__)))],
      outputs=[dict(path=p.name,sha256=sha(p)) for p in outs]))
    print(json.dumps(report,indent=2))


if __name__=='__main__':main()

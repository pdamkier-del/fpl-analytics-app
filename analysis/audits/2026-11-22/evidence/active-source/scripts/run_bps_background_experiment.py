#!/usr/bin/env python3
"""BPS background model validation with correct 2025/26 rules.

The joint simulator already generates the high-confidence event BPS layer
(minutes, goals, assists, clean sheets, saves, goals conceded, cards, own goals,
penalty miss/save). Historical free data cannot reconstruct every Opta BPS
component, so this experiment forecasts a *background BPS* rate from cutoff-safe
underlying-action history and soft tactical roles.

Validation uses 2025/26 BPS rules. The current 2026/27 rules remain the live
forecast rules after model selection.

Candidates:
  event_only          : no background BPS
  role                : soft-role + FPL-position background baseline
  role_recent         : role baseline + recent background/action rates
  role_recent_detail  : role baseline + recent underlying BPS action rates

Development: GW16-21 leave-one-GW-out.
Reused diagnostic: GW22-38, marginally on top of final DC + shared penalties.
No automatic promotion.
"""
from __future__ import annotations
import json,sys
from collections import defaultdict
from dataclasses import replace
from pathlib import Path
import numpy as np
import pandas as pd

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'));sys.path.insert(0,str(ROOT/'scripts'))

from fpl_v1_1_model.paired_joint import read_frozen_table,build_pair,run_pair
from run_v4_performance_rating_experiment import SOURCE,CLASSIFIED,read_all,player_id_map
from run_soft_role_defcon import add_axes,AXES,KEYS
from run_shared_penalty_joint import player_penalty_ledger,build_player_states,build_team_penalty_targets
from run_v4rc_experiment import write_json,sha

ROLE=ROOT/'analysis/results/role-event-priors-20261005-v1'
DC=ROOT/'analysis/results/defcon-threshold-finalist-20261005-v1/calibrated_dc.csv.gz'
PEN=ROOT/'analysis/results/shared-penalty-model-20261005-v1/model_summary.json'
FROZEN=ROOT/'analysis/results/deadline-joint-inputs-v1'
OUT=ROOT/'analysis/results/bps-background-20251005-v1'

HALF=[3.0,6.0,12.0]
L2=[10.0,50.0,200.0]
AXCOL=['axis_'+a for a in AXES]
POSCOL=['pos_GK','pos_DEF','pos_MID','pos_FWD']
DETAIL=['hist_cross','hist_cbi','hist_recovery','hist_tackle','hist_keypass',
        'hist_dribble','hist_foulwon','hist_sot','hist_passbps','hist_negative']


def score(y,p):
    e=np.asarray(p,float)-np.asarray(y,float)
    return dict(mae=float(np.mean(np.abs(e))),rmse=float(np.sqrt(np.mean(e**2))),bias=float(np.mean(e)))


def multiclass_bonus_metrics(actual,p1,p2,p3):
    y=np.asarray(actual,int)
    p=np.c_[1-np.asarray(p1)-np.asarray(p2)-np.asarray(p3),p1,p2,p3]
    p=np.clip(p,1e-9,1);p=p/p.sum(1,keepdims=True)
    return dict(
      log_loss=float(-np.mean(np.log(p[np.arange(len(y)),y]))),
      brier=float(np.mean(np.sum((p-np.eye(4)[y])**2,axis=1))),
      expected_bonus_mae=float(np.mean(np.abs(p@np.arange(4)-y))),
      expected_bonus_rmse=float(np.sqrt(np.mean((p@np.arange(4)-y)**2))),
      mean_pred_bonus=float(np.mean(p@np.arange(4))),mean_actual_bonus=float(np.mean(y)),
      p_any=float(np.mean(1-p[:,0])),actual_any=float(np.mean(y>0)))


def actual_background_ledger():
    stats=read_all('playermatchstats').drop_duplicates(['match_id','player_id'],keep='last').copy()
    stats=stats[stats.match_id.astype(str).str.contains('-prem-')].copy()
    matches=read_all('matches')[['match_id','kickoff_time']].drop_duplicates('match_id',keep='last')
    mapping=player_id_map()
    stats['player_uuid']=pd.to_numeric(stats.player_id,errors='coerce').map(mapping)
    fx=pd.read_csv(CLASSIFIED,usecols=['match_id','fixture_uuid']).drop_duplicates()
    if fx.groupby('match_id').fixture_uuid.nunique().max()>1: raise ValueError('ambiguous fixture mapping')
    fx=fx.drop_duplicates('match_id')
    stats=stats.merge(fx,on='match_id',how='inner',validate='many_to_one')
    stats=stats.merge(matches,on='match_id',how='left',validate='many_to_one')
    stats['available_at']=pd.to_datetime(stats.kickoff_time,utc=True,errors='coerce')+pd.Timedelta(hours=3)
    stats=stats[stats.player_uuid.notna() & stats.available_at.notna()].copy()

    nums=['minutes_played','accurate_crosses','blocks','clearances','interceptions','recoveries',
          'tackles_won','chances_created','successful_dribbles','was_fouled','shots_on_target',
          'accurate_passes','accurate_passes_percent','big_chances_missed','fouls_committed',
          'offsides','total_shots','dispossessed']
    for c in nums:stats[c]=pd.to_numeric(stats[c],errors='coerce').fillna(0.)
    mins=stats.minutes_played.to_numpy(float)
    pct=stats.accurate_passes_percent.to_numpy(float)
    accurate=stats.accurate_passes.to_numpy(float)
    attempts=np.where(pct>1e-6,accurate/(pct/100.0),accurate)
    passbps=np.where(attempts>=30,np.where(pct>=90,6,np.where(pct>=80,4,np.where(pct>=70,2,0))),0)
    cbi=stats.clearances+stats.blocks+stats.interceptions
    shots_off=np.maximum(0,stats.total_shots-stats.shots_on_target)
    # Approximate only the unavailable/background side of 2025/26 BPS.
    # accurate_crosses is a proxy for open-play crosses and dispossessed is a
    # proxy for the unavailable 'being tackled' Opta field.
    comps=pd.DataFrame({
      'cross':stats.accurate_crosses,
      'cbi':np.floor(cbi/2),
      'recovery':np.floor(stats.recoveries/3),
      'tackle':2*stats.tackles_won,
      'keypass':stats.chances_created,
      'dribble':stats.successful_dribbles,
      'foulwon':stats.was_fouled,
      'sot':2*stats.shots_on_target,
      'passbps':passbps,
      'negative':-(3*stats.big_chances_missed+stats.fouls_committed+stats.offsides+shots_off+stats.dispossessed),
    })
    stats['bg2025_proxy']=comps.sum(axis=1)
    stats['bg_rate90']=np.where(mins>0,stats.bg2025_proxy*90/np.maximum(mins,1),0)
    for c in comps:
        stats[c+'_rate90']=np.where(mins>0,comps[c]*90/np.maximum(mins,1),0)
    keep=['fixture_uuid','player_uuid','match_id','available_at','minutes_played','bg2025_proxy','bg_rate90']+[c+'_rate90' for c in comps]
    return stats[keep].sort_values(['player_uuid','available_at','match_id'])


def add_history(frame,ledger,half):
    histories={str(pid):g for pid,g in ledger.groupby('player_uuid',sort=False)}
    cut=pd.to_datetime(frame.cutoff,utc=True)
    out=[]
    ratecols=['bg_rate90','cross_rate90','cbi_rate90','recovery_rate90','tackle_rate90',
              'keypass_rate90','dribble_rate90','foulwon_rate90','sot_rate90','passbps_rate90','negative_rate90']
    for i,r in frame.reset_index(drop=True).iterrows():
        g=histories.get(str(r.player_uuid))
        if g is None:
            past=None
        else:
            past=g[g.available_at<cut.iloc[i]]
        rec={}
        if past is None or len(past)==0:
            for c in ratecols:rec[c]=0.
            rec['hist_n']=0.
        else:
            vals=past.tail(30)
            k=np.arange(len(vals)-1,-1,-1,dtype=float)
            w=2**(-k/half)
            for c in ratecols:rec[c]=float(np.average(vals[c].to_numpy(float),weights=w))
            rec['hist_n']=float(len(past))
        out.append(rec)
    h=pd.DataFrame(out)
    ren={
      'bg_rate90':'hist_bg',
      'cross_rate90':'hist_cross','cbi_rate90':'hist_cbi','recovery_rate90':'hist_recovery',
      'tackle_rate90':'hist_tackle','keypass_rate90':'hist_keypass','dribble_rate90':'hist_dribble',
      'foulwon_rate90':'hist_foulwon','sot_rate90':'hist_sot','passbps_rate90':'hist_passbps',
      'negative_rate90':'hist_negative'}
    h=h.rename(columns=ren)
    return pd.concat([frame.reset_index(drop=True),h],axis=1)


def feature_frame(base,half,ledger):
    f=add_axes(base.copy())
    pos=f.pos.replace({'GKP':'GK'}).astype(str)
    for p in ['GK','DEF','MID','FWD']:f['pos_'+p]=(pos==p).astype(float)
    f=add_history(f,ledger,half)
    return f


def features(family):
    if family=='role':return POSCOL+AXCOL
    if family=='role_recent':return POSCOL+AXCOL+['hist_bg','hist_n']
    if family=='role_recent_detail':return POSCOL+AXCOL+['hist_bg','hist_n']+DETAIL
    raise ValueError(family)


def fit_ridge(df,cols,l2,train):
    X=df[cols].to_numpy(float);y=df.bg_rate90.to_numpy(float)
    mu=X[train].mean(0);sd=X[train].std(0);sd[sd<1e-8]=1
    Z=(X-mu)/sd
    A=np.c_[np.ones(train.sum()),Z[train]]
    w=np.sqrt(np.clip(df.minutes_played.to_numpy(float)[train]/90,.05,1.0))
    Aw=A*w[:,None];yw=y[train]*w
    pen=np.eye(A.shape[1])*l2;pen[0,0]=0
    beta=np.linalg.solve(Aw.T@Aw+pen,Aw.T@yw)
    pred=np.c_[np.ones(len(df)),Z]@beta
    return pred,dict(cols=cols,l2=float(l2),intercept=float(beta[0]),coef=beta[1:].tolist(),mean=mu.tolist(),scale=sd.tolist())


def apply_model(df,model):
    X=df[model['cols']].to_numpy(float)
    Z=(X-np.asarray(model['mean']))/np.asarray(model['scale'])
    return np.asarray(model['intercept']+Z@np.asarray(model['coef']),float)


def bg_reg_metrics(df,pred,mask):
    actual=df.bg2025_proxy.to_numpy(float)[mask]
    pp=pred[mask]*df.minutes_played.to_numpy(float)[mask]/90
    return score(actual,pp)


def prepare_integrated_candidate():
    summ=json.loads(PEN.read_text())
    tau=float(summ['selected']['occurrence_tau']);half=float(summ['selected']['taker_half_life'])
    tau_conv=float(summ['selected']['conversion_tau']);psave=float(summ['selected']['p_keeper_save_given_miss'])
    role=read_frozen_table(ROLE,'candidate_inputs')
    dc=pd.read_csv(DC)[['fixture_uuid','player_uuid','mu_cal']]
    role=role.merge(dc,on=['fixture_uuid','player_uuid'],how='left',validate='one_to_one')
    role['mu_dc']=role.mu_cal.fillna(role.mu_dc);role=role.drop(columns=['mu_cal'])
    sides,pen,tm=player_penalty_ledger()
    pst=build_player_states(role,pen,half,tau_conv)
    teams=build_team_penalty_targets(role,sides,tm,tau)
    role=role.merge(pst,on=['fixture_uuid','player_uuid','team_id','gw'],how='left',validate='one_to_one')
    role['pen_attempt_state']=role.pen_attempt_state.fillna(0);role['pen_conversion']=role.pen_conversion.fillna(.78)
    role=role.merge(teams[['fixture_uuid','team_id','lambda_pen']],on=['fixture_uuid','team_id'],how='left',validate='many_to_one')
    role['lambda_pen']=role.lambda_pen.fillna(float(teams.lambda_pen.mean()))
    role['pen_weight_raw']=role.pen_attempt_state+.02*np.maximum(role.goal_rate90,1e-6)
    den=role.groupby(['fixture_uuid','team_id']).pen_weight_raw.transform('sum')
    role['pen_weight']=np.where(den>0,role.pen_weight_raw/den,0)
    role['team_pen_conversion']=(role.pen_weight*role.pen_conversion).groupby([role.fixture_uuid,role.team_id]).transform('sum')
    return role,psave


def with_bps(inp,g,bg_lookup,psave):
    home=int(g.home_team_id.iloc[0]);away=int(g.away_team_id.iloc[0])
    hrow=g[g.team_id==home].iloc[0];arow=g[g.team_id==away].iloc[0]
    bypid=g.set_index('player_uuid')
    players=[]
    for p in inp.players:
        row=bypid.loc[p.player_id]
        bg=float(bg_lookup.get(p.player_id,0.))
        players.append(replace(p,penalty_weight=float(row.pen_weight),penalty_conversion=float(row.pen_conversion),
                               bps_background_mean=0.,bps_background_sd=0.,
                               bps_background_rate90=bg,bps_background_sd90=0.))
    return replace(inp,players=tuple(players),
        lambda_home_penalties=float(hrow.lambda_pen),lambda_away_penalties=float(arow.lambda_pen),
        home_penalty_conversion=float(hrow.team_pen_conversion),away_penalty_conversion=float(arow.team_pen_conversion),
        p_penalty_save_given_miss=float(psave),bps_rules='2025-26')


def main():
    if OUT.exists():raise FileExistsError(OUT)
    OUT.mkdir(parents=True)
    ledger=actual_background_ledger()

    # Development rows and actual background target.
    dev=read_frozen_table(ROLE,'development_prior_predictions')
    dev=dev[dev.tau==900].copy().reset_index(drop=True)
    allf=pd.read_csv(SOURCE)
    qcols=['q_'+r+'_slow' for r in __import__('fpl_v1_1_model.role_classifier',fromlist=['ROLES']).ROLES]
    featcols=KEYS+['cutoff','pos']+qcols
    base=dev.merge(allf[featcols],on=KEYS,how='left',validate='one_to_one',suffixes=('','_f'))
    if 'pos_f' in base:base['pos']=base.pos.fillna(base.pos_f)
    actual=ledger[['fixture_uuid','player_uuid','minutes_played','bg2025_proxy','bg_rate90']].drop_duplicates(['fixture_uuid','player_uuid'])
    base=base.merge(actual,on=['fixture_uuid','player_uuid'],how='inner',validate='one_to_one')
    base=base[base.minutes_played>0].reset_index(drop=True)

    rows=[];frames={}
    families=['role','role_recent','role_recent_detail']
    for h in HALF:
        f=feature_frame(base,h,ledger);frames[h]=f
        for fam in families:
            cols=features(fam)
            for l2 in L2:
                oof=np.zeros(len(f))
                for gw in sorted(f.gw.unique()):
                    tr=f.gw.to_numpy()!=gw;te=~tr
                    p,_=fit_ridge(f,cols,l2,tr);oof[te]=p[te]
                m=bg_reg_metrics(f,oof,np.ones(len(f),bool))
                rows.append(dict(half=h,family=fam,l2=l2,**m,n_features=len(cols)))
    cv=pd.DataFrame(rows).sort_values(['mae','rmse']).reset_index(drop=True)
    cv.to_csv(OUT/'development_background_cv.csv',index=False)
    best=cv.iloc[0];bh=float(best.half);bfam=str(best.family);bl2=float(best.l2)
    fdev=frames[bh];_,model=fit_ridge(fdev,features(bfam),bl2,np.ones(len(fdev),bool))
    # role-only comparator, matched half-life (history unused but frame convenient)
    role_cv=cv[cv.family=='role'].sort_values(['mae','rmse']).iloc[0]
    rh=float(role_cv.half);rl2=float(role_cv.l2)
    frole=frames[rh];_,role_model=fit_ridge(frole,features('role'),rl2,np.ones(len(frole),bool),)
    write_json(OUT/'selection.json',dict(selected=dict(half=bh,family=bfam,l2=bl2,model=model),
                                          role_baseline=dict(half=rh,l2=rl2,model=role_model)))

    # Diagnostic feature predictions.
    role,psave=prepare_integrated_candidate()
    # Merge cutoff/q for candidate.
    cand=role.merge(allf[featcols],on=KEYS,how='left',validate='one_to_one',suffixes=('','_f'))
    if 'pos_f' in cand:cand['pos']=cand.pos.fillna(cand.pos_f)
    fcand=feature_frame(cand,bh,ledger);rcand=feature_frame(cand,rh,ledger)
    selected_rate=apply_model(fcand,model);role_rate=apply_model(rcand,role_model)
    # conservative clipping based on development target distribution
    lo=float(np.quantile(fdev.bg_rate90,.01));hi=float(np.quantile(fdev.bg_rate90,.99))
    selected_rate=np.clip(selected_rate,lo,hi);role_rate=np.clip(role_rate,lo,hi)
    fcand['selected_bg_rate90']=selected_rate;fcand['role_bg_rate90']=role_rate
    fcand[['fixture_uuid','player_uuid','gw','selected_bg_rate90','role_bg_rate90']].to_csv(
        OUT/'diagnostic_background_rates.csv.gz',index=False,compression='gzip')

    truth=read_frozen_table(FROZEN,'targets')
    rec=[]
    for i,(fx,g) in enumerate(fcand[fcand.gw.between(22,38)].groupby('fixture_uuid',sort=True)):
        _,raw=build_pair(g)
        zero={str(x):0. for x in g.player_uuid}
        rlookup=dict(zip(g.player_uuid.astype(str),g.role_bg_rate90))
        slookup=dict(zip(g.player_uuid.astype(str),g.selected_bg_rate90))
        baseinp=with_bps(raw,g,zero,psave)
        roleinp=with_bps(raw,g,rlookup,psave)
        selinp=with_bps(raw,g,slookup,psave)
        a,b=run_pair(baseinp,roleinp,n=260,seed=37092501+i)
        a2,c=run_pair(baseinp,selinp,n=260,seed=37092501+i)
        for r in g.itertuples():
            pid=str(r.player_uuid)
            rec.append(dict(fixture_uuid=fx,player_uuid=pid,gw=r.gw,
              event_bonus=a[pid]['expected_bonus'],role_bonus=b[pid]['expected_bonus'],selected_bonus=c[pid]['expected_bonus'],
              event_p1=a[pid]['p_bonus_1'],event_p2=a[pid]['p_bonus_2'],event_p3=a[pid]['p_bonus_3'],
              role_p1=b[pid]['p_bonus_1'],role_p2=b[pid]['p_bonus_2'],role_p3=b[pid]['p_bonus_3'],
              selected_p1=c[pid]['p_bonus_1'],selected_p2=c[pid]['p_bonus_2'],selected_p3=c[pid]['p_bonus_3'],
              event_xpts=a[pid]['xPts'],role_xpts=b[pid]['xPts'],selected_xpts=c[pid]['xPts']))
    pred=pd.DataFrame(rec)
    sc=pred.merge(truth,on=['fixture_uuid','player_uuid'],validate='one_to_one')
    report={'classification':'reused_diagnostic_not_independent_holdout','fixtures':int(sc.fixture_uuid.nunique()),'rows':len(sc),
            'draws_per_fixture':260,'selected_background':dict(half=bh,family=bfam,l2=bl2),
            'bonus':{},'total_xpts':{},'promoted':False}
    for name in ['event','role','selected']:
        report['bonus'][name]=multiclass_bonus_metrics(sc.bonus.astype(int),sc[name+'_p1'],sc[name+'_p2'],sc[name+'_p3'])
        report['total_xpts'][name]=score(sc.total_points,sc[name+'_xpts'])
    report['delta_selected_vs_event_bonus']={k:report['bonus']['selected'][k]-report['bonus']['event'][k]
        for k in ['log_loss','brier','expected_bonus_mae','expected_bonus_rmse']}
    report['delta_selected_vs_event_xpts']={k:report['total_xpts']['selected'][k]-report['total_xpts']['event'][k]
        for k in ['mae','rmse','bias']}
    write_json(OUT/'joint_metrics.json',report)
    pred.to_csv(OUT/'joint_predictions.csv.gz',index=False,compression='gzip')
    write_json(OUT/'protocol.json',dict(
      historical_rules='2025-26 official BPS mechanics for validation',
      live_rules='2026-27 kept separate',
      background_proxy='available raw action components; unavailable Opta fields remain residual',
      development='GW16-21 LOOGW',reused_diagnostic='GW22-38',
      candidates=['event_only','soft role','soft role + cutoff-safe recent BPS actions'],promotion_allowed=False))
    outs=[p for p in sorted(OUT.iterdir()) if p.name!='manifest.json']
    write_json(OUT/'manifest.json',dict(sources=[
      dict(path='scripts/run_bps_background_experiment.py',sha256=sha(Path(__file__))),
      dict(path='src/fpl_v1_1_model/bps.py',sha256=sha(ROOT/'src/fpl_v1_1_model/bps.py')),
      dict(path='src/fpl_v1_1_model/joint_simulator.py',sha256=sha(ROOT/'src/fpl_v1_1_model/joint_simulator.py'))],
      outputs=[dict(path=p.name,sha256=sha(p)) for p in outs]))
    print(json.dumps(report,indent=2))

if __name__=='__main__':main()

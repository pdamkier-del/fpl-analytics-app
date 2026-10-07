#!/usr/bin/env python3
"""Conditional 2024/25 rolling vFinal PM adapter.

Model equations/selected parameters remain frozen. Historical 2024/25 inputs are
explicitly conditional proxies:
- final PL schedule is used as the future-schedule proxy;
- provider postmatch events become available at kickoff+4h;
- historical penalty takers are reconstructed from provider xG-vs-npxG + missed penalties;
- measured role positions are unavailable; MM structural-role proxy is inherited;
- 2024/25 had no defensive-contribution FPL points, so simulated DC points are
  removed from xPts as a season scoring adapter, not a model refit.

This is a robustness replay, not a strict historical or independent OOS replay.
"""
from __future__ import annotations
import argparse,gzip,json,sqlite3,sys,re,unicodedata
from collections import defaultdict
from dataclasses import replace
from pathlib import Path
import numpy as np,pandas as pd

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'));sys.path.insert(0,str(ROOT/'scripts'))

from fpl_v1_1_model.deadline_keeper import keeper_saves_at_deadline
from fpl_v1_1_model.role_event_priors import QCOLS
from fpl_v1_1_model.joint_simulator import simulate_many
from fpl_v1_1_model.vfinal_replay_state import fit_team_latent
from run_rolling_vfinal_gw6_38 import load_models,bps_bounds
from run_bps_background_experiment import actual_background_ledger,feature_frame as bps_features,apply_model as bps_apply
from run_vfinal_integrated import make_vfinal_input
from vfinal_replay_components import build_fixture_components
from run_2024_25_conditional_mm import jsonl_gz,perf_ledger,norm

def stat(r,key,default=0.):
    v=(r.get('stats') or {}).get(key)
    try:return float(v) if v is not None else float(default)
    except:return float(default)

def firststat(r,*keys):
    for k in keys:
        v=(r.get('stats') or {}).get(k)
        if v is not None:
            try:return float(v)
            except:return 0.
    return 0.

def team_map(cands):
    d=defaultdict(set)
    for r in cands:
        if r.get('team') is not None and r.get('team_id') is not None:d[norm(r['team'])].add(int(r['team_id']))
    return {k:next(iter(v)) for k,v in d.items() if len(v)==1}

def bps_ledger_2024(obs):
    rows=[]
    for r in obs:
        if not r.get('player_uuid') or r.get('minutes') is None:continue
        mins=float(r.get('minutes') or 0.)
        accurate=firststat(r,'accurate_passes');pct=firststat(r,'accurate_passes_percent')
        attempts=accurate/(pct/100.) if pct>1e-6 else accurate
        passbps=6 if attempts>=30 and pct>=90 else 4 if attempts>=30 and pct>=80 else 2 if attempts>=30 and pct>=70 else 0
        cross=firststat(r,'accurate_crosses')
        blocks=firststat(r,'blocks','shot_blocks','blocked_shots')
        clear=firststat(r,'clearances');inter=firststat(r,'interceptions');recovery=firststat(r,'recoveries')
        tackle=firststat(r,'tackles_won','matchstats.headers.tackles')
        keypass=firststat(r,'chances_created');dribble=firststat(r,'successful_dribbles','dribbles_succeeded')
        foulwon=firststat(r,'was_fouled');sot=firststat(r,'shots_on_target','ShotsOnTarget')
        bcm=firststat(r,'big_chances_missed','big_chance_missed_title');foul=firststat(r,'fouls_committed','fouls')
        off=firststat(r,'offsides','Offsides');shots=firststat(r,'total_shots');disp=firststat(r,'dispossessed')
        shots_off=max(0.,shots-sot)
        comps=dict(cross=cross,cbi=np.floor((clear+blocks+inter)/2),recovery=np.floor(recovery/3),
          tackle=2*tackle,keypass=keypass,dribble=dribble,foulwon=foulwon,sot=2*sot,passbps=passbps,
          negative=-(3*bcm+foul+off+shots_off+disp))
        bg=float(sum(comps.values()))
        rec=dict(fixture_uuid=str(r['match_id']),player_uuid=str(r['player_uuid']),match_id=str(r['match_id']),
          available_at=pd.to_datetime(r['available_at_proxy'],utc=True),minutes_played=mins,bg2025_proxy=bg,
          bg_rate90=(bg*90/max(mins,1) if mins>0 else 0.))
        for k,v in comps.items():rec[k+'_rate90']=(v*90/max(mins,1) if mins>0 else 0.)
        rows.append(rec)
    return pd.DataFrame(rows).sort_values(['player_uuid','available_at','match_id'])

def penalty_history_2024(obs,fixtures,tmap):
    fxgw={int(r.id):int(r.event) for r in fixtures[fixtures.event.notna()].itertuples()}
    fxside={int(r.id):(int(r.team_h),int(r.team_a)) for r in fixtures.itertuples()}
    rows=[]
    for r in obs:
        fid=r.get('fpl_fixture_id')
        if fid is None or pd.isna(fid):continue
        try:fid=int(fid)
        except:continue
        if fid not in fxgw or not r.get('player_uuid'):continue
        tid=tmap.get(norm(r.get('team')))
        if tid is None:continue
        xg=firststat(r,'expected_goals','xg');npxg=firststat(r,'expected_goals_non_penalty')
        diff=max(0.,xg-npxg);attempts=int(max(0,round(diff/.79)))
        missed=int(max(0,round(firststat(r,'missed_penalty'))))
        attempts=max(attempts,missed)
        if attempts<=0:continue
        rows.append(dict(gw=fxgw[fid],fixture_id=fid,team_id=int(tid),player_uuid=str(r['player_uuid']),
                         attempts=float(attempts),scored=float(max(0,attempts-missed))))
    return pd.DataFrame(rows)

def penalty_state(origin,state,phist,fixtures,summary):
    half=float(summary['selected']['taker_half_life']);tau=float(summary['selected']['occurrence_tau'])
    tc=float(summary['selected']['conversion_tau']);decay=2**(-1/half)
    attempts=defaultdict(float);scored=defaultdict(float)
    league_sc=league_at=0.
    for gw in range(1,int(origin)):
        for k in list(attempts):attempts[k]*=decay;scored[k]*=decay
        if len(phist):
            g=phist[phist.gw.eq(gw)]
            for r in g.itertuples(index=False):
                attempts[str(r.player_uuid)]+=float(r.attempts);scored[str(r.player_uuid)]+=float(r.scored)
                league_at+=float(r.attempts);league_sc+=float(r.scored)
    lgconv=league_sc/league_at if league_at>0 else .78
    ps={str(r.player_uuid):(attempts[str(r.player_uuid)],(scored[str(r.player_uuid)]+tc*lgconv)/(attempts[str(r.player_uuid)]+tc))
        for r in state.itertuples(index=False)}
    awarded=defaultdict(lambda:[0.,0.]);conceded=defaultdict(lambda:[0.,0.]);league=[0.,0.]
    if len(phist):
        by=phist[phist.gw<int(origin)].groupby(['gw','fixture_id','team_id'],as_index=False).attempts.sum()
        fxside={int(r.id):(int(r.team_h),int(r.team_a)) for r in fixtures.itertuples()}
        for r in by.itertuples(index=False):
            sides=fxside.get(int(r.fixture_id))
            if not sides:continue
            t=int(r.team_id);o=sides[1] if t==sides[0] else sides[0] if t==sides[1] else None
            if o is None:continue
            awarded[t][0]+=float(r.attempts);awarded[t][1]+=1
            conceded[o][0]+=float(r.attempts);conceded[o][1]+=1;league[0]+=float(r.attempts);league[1]+=1
    lg=league[0]/league[1] if league[1] else .12
    def lam(t,o):
        a,n=awarded[int(t)];c,m=conceded[int(o)]
        return max(1e-6,.5*((a+tau*lg)/(n+tau))+.5*((c+tau*lg)/(m+tau)))
    return ps,lam

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--db',required=True);ap.add_argument('--derived',required=True)
    ap.add_argument('--source',required=True);ap.add_argument('--mm',required=True);ap.add_argument('--out',required=True)
    ap.add_argument('--start-origin',type=int,default=6);ap.add_argument('--end-origin',type=int,default=38)
    ap.add_argument('--max-fixtures',type=int,default=0)
    a=ap.parse_args();derived=Path(a.derived);out=Path(a.out);out.mkdir(parents=True,exist_ok=True)
    src=pd.read_csv(a.source).reset_index(drop=True);mm=pd.read_csv(a.mm)
    src['cutoff']=pd.to_datetime(src.cutoff,utc=True);mm['cutoff']=pd.to_datetime(mm.cutoff,utc=True)
    models=load_models();obs=jsonl_gz(derived/'all_competition_player_observations.jsonl.gz')
    perf=perf_ledger(obs);bpsledger=bps_ledger_2024(obs)
    fixed2025=actual_background_ledger();lo,hi=bps_bounds(src,fixed2025)

    con=sqlite3.connect(Path(a.db))
    ph=pd.read_sql_query("""SELECT season,fixture_uuid,player_uuid,team_id,opponent_team_id,gw,kickoff_at,fpl_position,
      minutes,xg,xa,defcon_count,yellow_cards,fpl_red_cards,own_goals,goals,fpl_assists
      FROM player_fixture_observations WHERE season='2024-25' AND is_final=1""",con)
    th=pd.read_sql_query("""SELECT season,gw,fixture_uuid,team_id,opponent_team_id,was_home,kickoff_at,xg
      FROM team_fixture_observations WHERE season='2024-25' AND source_name='vaastav_historical_core'""",con)
    sot=pd.read_sql_query("""SELECT season,fixture_uuid,team_id,opponent_team_id,was_home,kickoff_at,
      shots_on_target,shots_on_target_conceded FROM team_fixture_observations
      WHERE season='2024-25' AND source_name='football_data_co_uk'""",con)
    con.close()
    for x in (ph,th,sot):
        x['kickoff_at']=pd.to_datetime(x.kickoff_at,utc=True);x['available_at']=x.kickoff_at+pd.Timedelta(hours=4)
    ph=ph.drop_duplicates(['fixture_uuid','player_uuid']);ph['defcon_count']=pd.to_numeric(ph.defcon_count,errors='coerce').fillna(0.)
    for c in ['xg','xa','minutes','yellow_cards','fpl_red_cards','own_goals','goals','fpl_assists']:
        ph[c]=pd.to_numeric(ph[c],errors='coerce').fillna(0.)

    fixtures=pd.read_csv(derived/'pl_fixture_actuals.csv');fixtures['kickoff']=pd.to_datetime(fixtures.kickoff_time,utc=True)
    fixtures=fixtures[fixtures.event.notna()].copy();fixtures['event']=fixtures.event.astype(int)
    sched=fixtures.rename(columns={'id':'match_id','event':'gameweek','team_h':'home_team_id','team_a':'away_team_id'})
    cands=jsonl_gz(derived/'deadline_player_candidates.jsonl.gz');tmap=team_map(cands)
    pens=penalty_history_2024(obs,fixtures,tmap)
    identity=pd.read_csv(derived/'player_identity.csv').dropna(subset=['player_uuid'])
    mp=dict(zip(identity.player_uuid.astype(str),identity.fpl_element.astype(int)))
    pd.DataFrame([{'player_uuid':k,'id':v} for k,v in mp.items()]).to_csv(out/'identity_resolution.csv',index=False)
    rolehist=src[['fixture_uuid','player_uuid','team_id','cutoff','max_history_known_at']+QCOLS].copy()

    rows=[];faudit=[]
    for origin in range(a.start_origin,a.end_origin+1):
        cutoff=src.loc[src.gw.eq(origin),'cutoff'].min()
        sstate=src[src.gw<=origin].sort_values(['gw','cutoff']).drop_duplicates('player_uuid',keep='last').copy()
        mstate=mm[mm.gw<=origin].sort_values(['gw','cutoff']).drop_duplicates('player_uuid',keep='last').copy()
        state=sstate.merge(mstate[['player_uuid','new_p_start','new_xmins','new_q_sub','new_sub_minutes','new_start_minutes']],
                           on='player_uuid',how='inner',validate='one_to_one')
        state['cutoff']=cutoff
        bf=bps_features(state,3.,bpsledger)
        state['bg_mean_rate90']=np.clip(bps_apply(bf,models['bps']),lo,hi)
        broad=state.pos.replace({'G':'GK','GKP':'GK'}).astype(str);sd=models['bpsvar']['position_sd90']
        state['bg_sd90']=[float(sd.get(p,models['bpsvar']['global_sd90'])) for p in broad]

        fx=sched[sched.gameweek.between(origin,min(38,origin+5)) & (sched.kickoff>=cutoff)].drop_duplicates('match_id').copy()
        if a.max_fixtures>0:fx=fx.head(a.max_fixtures)
        if fx.empty:continue
        hist_team=th[th.available_at<=cutoff].copy()
        lambdas=fit_team_latent(hist_team,fx[['match_id','home_team_id','away_team_id']],origin)
        past=ph[ph.available_at<=cutoff].copy()
        goals=float(past.goals.sum());assist_prob=min(1.,max(.5,float(past.fpl_assists.sum())/goals)) if goals>0 else .7
        ps,plam=penalty_state(origin,state,pens,fixtures,models['pen'])
        bmean=state.set_index('player_uuid').bg_mean_rate90.to_dict();bsd=state.set_index('player_uuid').bg_sd90.to_dict()
        origin_count=0
        for fixture_index,fr in enumerate(fx.itertuples(index=False)):
            home=int(fr.home_team_id);away=int(fr.away_team_id)
            rg=state[state.team_id.astype(int).isin([home,away])].copy()
            if rg.empty:continue
            synthetic=f'c24-o{origin}-{int(fr.match_id)}'
            rg['fixture_uuid']=synthetic;rg['home_team_id']=home;rg['away_team_id']=away
            rg['opponent_team_id']=np.where(rg.team_id.astype(int)==home,away,home)
            rg['was_home']=rg.team_id.astype(int)==home;rg['evidence_at']=cutoff;rg['expected_minutes']=rg.new_xmins.astype(float)
            rg['pos']=rg.pos.replace({'G':'GK'})
            # The MM feature frame already carries performance-history columns.
            # vFinal's frozen component builder must construct them exactly once
            # from its own cutoff-safe performance ledger.
            rg=rg.drop(columns=[x for x in rg.columns if str(x).startswith('perf_')],errors='ignore')
            hgoal,agoal=lambdas[str(fr.match_id)]
            rg=build_fixture_components(rg,past,rolehist,cutoff,models['attack'],models['dc'],models['neg'],
                                        models['ga'],models['dc_model'],models['dc_cal'],perf,
                                        home,away,hgoal,agoal,assist_prob,season='2024-25')
            sides=rg[['fixture_uuid','team_id','opponent_team_id','was_home']].drop_duplicates(['fixture_uuid','team_id'])
            try:
                ks=keeper_saves_at_deadline(sot,sides,cutoff,models['keeper'],season='2024-25')
                rg=rg.merge(ks[['fixture_uuid','team_id','lambda_saves']],on=['fixture_uuid','team_id'],how='left',validate='many_to_one')
            except ValueError:
                rg['lambda_saves']=0.
            vals=[ps.get(str(pid),(0.,.78)) for pid in rg.player_uuid]
            rg['pen_attempt_state']=[v[0] for v in vals];rg['pen_conversion']=[v[1] for v in vals]
            rg['pen_weight_raw']=rg.pen_attempt_state+.02*np.maximum(rg.goal_rate90,1e-6)
            den=rg.groupby('team_id').pen_weight_raw.transform('sum');rg['pen_weight']=np.where(den>0,rg.pen_weight_raw/den,0)
            rg['team_pen_conversion']=(rg.pen_weight*rg.pen_conversion).groupby(rg.team_id).transform('sum')
            rg['lambda_pen']=[plam(int(t),int(o)) for t,o in zip(rg.team_id,rg.opponent_team_id)]
            rg['bg_mean_rate90']=rg.player_uuid.map(bmean).fillna(0.);rg['bg_sd90']=rg.player_uuid.map(bsd).fillna(float(models['bpsvar']['global_sd90']))
            rg['control_p_start']=rg.new_p_start;rg['control_xmins']=rg.new_xmins
            rg['p_cameo_given_bench']=rg.new_q_sub;rg['start_minutes_mean']=rg.new_start_minutes;rg['cameo_minutes_mean']=rg.new_sub_minutes
            rg['v4_workload_start_p_start']=rg.new_p_start;rg['v4_workload_start_xmins']=rg.new_xmins
            rg['v4_p_cameo_given_bench']=rg.new_q_sub;rg['v4_start_minutes_mean']=rg.new_start_minutes;rg['v4_cameo_minutes_mean']=rg.new_sub_minutes;rg['cutoff']=cutoff
            inp,_=make_vfinal_input(rg)
            inp=replace(inp,bps_rules='2024-25')
            # Execution-order independent deterministic MC seed so sequential and parallel
            # origin execution produce the same forecast draws.
            sim=simulate_many(inp,n=400,seed=92400000+int(origin)*1000+int(fixture_index))
            for rr in rg.itertuples(index=False):
                fid=mp.get(str(rr.player_uuid))
                if fid is None:continue
                sr=sim[str(rr.player_uuid)]
                xp=float(sr['xPts'])
                xnb=float(sr['xPts_nonbonus'])
                pplay=float(rr.new_p_start+(1-rr.new_p_start)*rr.new_q_sub)
                rows.append(dict(origin_gw=origin-1,decision_gw=origin,gw=int(fr.gameweek),id=int(fid),
                    player_uuid=str(rr.player_uuid),team=int(rr.team_id),position='GKP' if rr.pos in ('G','GK','GKP') else str(rr.pos),
                    xpts_fixture=xp,xpts_nonbonus_fixture=xnb,p_play_fixture=pplay,fixture=int(fr.match_id)))
                origin_count+=1
        faudit.append(dict(decision_gw=origin,cutoff=str(cutoff),fixtures=int(len(fx)),rows=origin_count,
                           future_schedule_proxy=True,penalty_proxy=True))
        print(f'GW{origin}: fixtures={len(fx)} rows={origin_count}',flush=True)

    z=pd.DataFrame(rows)
    if z.empty:raise ValueError('no PM forecast rows')
    agg=z.groupby(['origin_gw','decision_gw','gw','id','player_uuid','team','position'],as_index=False).agg(
        xpts_mean=('xpts_fixture','sum'),fixtures=('fixture','nunique'),
        p_no_play=('p_play_fixture',lambda s:float(np.prod(1-np.clip(s,0,1)))))
    agg['p_play']=1-agg.pop('p_no_play')
    z.to_csv(out/'fixture_predictions.csv.gz',index=False,compression='gzip');agg.to_csv(out/'rolling_vfinal_forecast.csv.gz',index=False,compression='gzip')
    pd.DataFrame(faudit).to_csv(out/'origin_audit.csv',index=False)
    summary=dict(classification='CONDITIONAL_ROBUSTNESS_REPLAY_PM_NOT_STRICT',season='2024-25',
      model_math_changed=False,retuned=False,decision_gws=[a.start_origin,a.end_origin],horizon=6,draws_per_fixture=400,
      future_schedule='FINAL_SEASON_SCHEDULE_PROXY',history_timing='kickoff+4h proxy',
      role_geometry='inherits structural formation proxy from conditional MM',
      penalty_history='provider xG-npxG + missed_penalty reconstruction proxy',
      scoring_adapter='joint simulator historical 2024/25 scoring; defensive-contribution FPL points disabled',
      bps_rules='2024-25 historical scoring adapter; unavailable background Opta fields remain frozen-model proxies',
      phase5q_xp_used=False,rows=int(len(agg)))
    (out/'summary.json').write_text(json.dumps(summary,indent=2)+'\n');print(json.dumps(summary,indent=2))
if __name__=='__main__':main()

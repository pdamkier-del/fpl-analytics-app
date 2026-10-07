#!/usr/bin/env python3
from __future__ import annotations
import argparse,json,sqlite3,sys
from pathlib import Path
import numpy as np,pandas as pd

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'));sys.path.insert(0,str(ROOT/'scripts'))

from fpl_v1_1_model.deadline_keeper import keeper_saves_at_deadline
from fpl_v1_1_model.future_match_importance import load_gw_schedule_snapshots
from fpl_v1_1_model.role_event_priors import QCOLS
from fpl_v1_1_model.joint_simulator import simulate_many
from fpl_v1_1_model.paired_joint import read_frozen_table
from fpl_v1_1_model.vfinal_replay_state import fit_team_latent,penalty_state
from fpl_xpts.identity import resolve_uuid_to_fpl_ids

from run_v4_performance_rating_experiment import build_perf_ledger
from run_shared_penalty_joint import player_penalty_ledger
from run_bps_background_experiment import actual_background_ledger,feature_frame as bps_features,apply_model as bps_apply
from run_vfinal_integrated import make_vfinal_input
from vfinal_replay_components import build_fixture_components
import run_horizon_policy_comparison as hp

RAW=ROOT/'data_v1_1/raw/all-competitions-2025-26'
TEAMS=ROOT/'data_v1_1/derived/mm_v2_ratings/identity_source/data/2025-2026/teams.csv'
P=lambda s:ROOT/s

def load_models():
    attack=json.loads(P('analysis/results/joint-component-recovery-v1/player_attack_fit.json').read_text())
    dc=json.loads(P('analysis/results/joint-component-recovery-v1/defcon_fit.json').read_text())['selected']
    negall=json.loads(P('analysis/results/joint-component-recovery-v1/negative_events_fit.json').read_text())
    neg=negall['recommended_for_joint_model'].copy()
    neg['own_goal_prior_minutes_tau']=negall['development_selected']['own_goal_prior_minutes_tau']
    return dict(
      attack=attack,dc=dc,neg=neg,
      keeper=json.loads(P('analysis/results/joint-team-keeper-recovery-v1/keeper_fit.json').read_text()),
      ga=json.loads(P('analysis/results/soft-role-performance-allocation-20261005-v1/models.json').read_text()),
      dc_model=json.loads(P('analysis/results/soft-role-defcon-20261005-v1/model.json').read_text()),
      dc_cal=json.loads(P('analysis/results/defcon-threshold-finalist-20261005-v1/selection.json').read_text()),
      pen=json.loads(P('analysis/results/shared-penalty-model-20261005-v1/model_summary.json').read_text()),
      bps=json.loads(P('analysis/results/bps-background-20251005-v1/selection.json').read_text())['selected']['model'],
      bpsvar=json.loads(P('analysis/results/bps-variance-calibration-20261005-v1/variance_fit.json').read_text()),
    )

def bps_bounds(source,ledger):
    dev=read_frozen_table(P('analysis/results/role-event-priors-20261005-v1'),'development_prior_predictions')
    dev=dev[dev.tau==900].copy()
    actual=ledger[['fixture_uuid','player_uuid','minutes_played','bg2025_proxy','bg_rate90']].drop_duplicates(['fixture_uuid','player_uuid'])
    cols=['fixture_uuid','player_uuid','team_id','cutoff','pos']+QCOLS
    old=pd.read_csv(P('analysis/results/workload-recovered-v4/all_features.csv.gz'),usecols=cols)
    base=dev.merge(old,on=['fixture_uuid','player_uuid','team_id'],how='left',validate='one_to_one',suffixes=('','_f'))
    if 'pos_f' in base:base['pos']=base.pos.fillna(base.pos_f)
    base=base.merge(actual,on=['fixture_uuid','player_uuid'],how='inner',validate='one_to_one')
    base=base[base.minutes_played>0].reset_index(drop=True)
    f=bps_features(base,3.,ledger)
    return float(np.quantile(f.bg_rate90,.01)),float(np.quantile(f.bg_rate90,.99))

def map_ids(source):
    raw=hp.unpack_runtime('players_raw.csv').drop_duplicates('id')
    mp,matches=resolve_uuid_to_fpl_ids(source[['player_uuid','player']].drop_duplicates(),raw)
    return mp,pd.DataFrame([m.__dict__ for m in matches])

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--db',required=True);ap.add_argument('--source',required=True)
    ap.add_argument('--mm',required=True);ap.add_argument('--out',required=True)
    ap.add_argument('--start-origin',type=int,default=6);ap.add_argument('--end-origin',type=int,default=38)
    ap.add_argument('--max-fixtures',type=int,default=0)
    a=ap.parse_args();out=Path(a.out);out.mkdir(parents=True,exist_ok=True)
    src=pd.read_csv(a.source).reset_index(drop=True);mm=pd.read_csv(a.mm)
    src['cutoff']=pd.to_datetime(src.cutoff,utc=True);mm['cutoff']=pd.to_datetime(mm.cutoff,utc=True)
    models=load_models();perf=build_perf_ledger();bpsledger=actual_background_ledger()
    lo,hi=bps_bounds(src,bpsledger)

    con=sqlite3.connect(Path(a.db))
    ph=pd.read_sql_query("""SELECT season,fixture_uuid,player_uuid,team_id,opponent_team_id,gw,kickoff_at,fpl_position,
      minutes,xg,xa,defcon_count,yellow_cards,fpl_red_cards,own_goals,goals,fpl_assists
      FROM player_fixture_observations WHERE season='2025-26' AND is_final=1""",con)
    th=pd.read_sql_query("""SELECT season,gw,fixture_uuid,team_id,opponent_team_id,was_home,kickoff_at,xg
      FROM team_fixture_observations WHERE season='2025-26' AND source_name='vaastav_historical_core'""",con)
    sot=pd.read_sql_query("""SELECT season,fixture_uuid,team_id,opponent_team_id,was_home,kickoff_at,
      shots_on_target,shots_on_target_conceded FROM team_fixture_observations
      WHERE season='2025-26' AND source_name='football_data_co_uk'""",con)
    con.close()
    for x in (ph,th,sot):
        x['kickoff_at']=pd.to_datetime(x.kickoff_at,utc=True);x['available_at']=x.kickoff_at+pd.Timedelta(hours=3)
    ph=ph.drop_duplicates(['fixture_uuid','player_uuid'])

    teams=pd.read_csv(TEAMS);code_to_team={int(r.code):int(r.id) for r in teams.itertuples()}
    snaps=load_gw_schedule_snapshots(RAW,code_to_team)
    rolehist=src[['fixture_uuid','player_uuid','team_id','cutoff','max_history_known_at']+QCOLS].copy()
    pen_sides,pen,tm=player_penalty_ledger()
    cm=tm[['team_code','team_id']].drop_duplicates();cm=cm[~cm.team_code.duplicated(keep=False)]
    team_code_to_id=dict(zip(cm.team_code.astype(int),cm.team_id.astype(int)))
    mp,ids=map_ids(src);ids.to_csv(out/'identity_resolution.csv',index=False)

    rows=[];faudit=[];counter=0
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

        sched=snaps[origin]
        fx=sched[(sched.competition=='prem')&
                 pd.to_numeric(sched.gameweek,errors='coerce').between(origin,min(38,origin+5))&
                 (sched.kickoff>=cutoff)].drop_duplicates('match_id').copy()
        if a.max_fixtures>0: fx=fx.head(a.max_fixtures).copy()
        if fx.empty:continue
        lambdas=fit_team_latent(th[th.available_at<=cutoff],fx[['match_id','home_team_id','away_team_id']],origin)
        past=ph[ph.available_at<=cutoff].copy()
        g=float(past.goals.sum());ap=min(1.,max(.5,float(past.fpl_assists.sum())/g)) if g>0 else .7
        ps,plam=penalty_state(origin,state,pen_sides,pen,team_code_to_id,models['pen'])
        bmean=state.set_index('player_uuid').bg_mean_rate90.to_dict()
        bsd=state.set_index('player_uuid').bg_sd90.to_dict()
        origin_count=0

        for fr in fx.itertuples(index=False):
            home=int(fr.home_team_id);away=int(fr.away_team_id)
            rg=state[state.team_id.astype(int).isin([home,away])].copy()
            if rg.empty:continue
            rg['fixture_uuid']=f'o{origin}-{fr.match_id}'
            rg['home_team_id']=home;rg['away_team_id']=away
            rg['opponent_team_id']=np.where(rg.team_id.astype(int)==home,away,home)
            rg['was_home']=rg.team_id.astype(int)==home;rg['evidence_at']=cutoff
            rg['expected_minutes']=rg.new_xmins.astype(float);rg['pos']=rg.pos.replace({'G':'GK'})
            hgoal,agoal=lambdas[str(fr.match_id)]
            rg=build_fixture_components(rg,past,rolehist,cutoff,models['attack'],models['dc'],models['neg'],
                                        models['ga'],models['dc_model'],models['dc_cal'],perf,
                                        home,away,hgoal,agoal,ap)

            sides=rg[['fixture_uuid','team_id','opponent_team_id','was_home']].drop_duplicates(['fixture_uuid','team_id'])
            ks=keeper_saves_at_deadline(sot,sides,cutoff,models['keeper'])
            rg=rg.merge(ks[['fixture_uuid','team_id','lambda_saves']],on=['fixture_uuid','team_id'],how='left',validate='many_to_one')

            vals=[ps.get(str(pid),(0.,.78)) for pid in rg.player_uuid]
            rg['pen_attempt_state']=[v[0] for v in vals];rg['pen_conversion']=[v[1] for v in vals]
            rg['pen_weight_raw']=rg.pen_attempt_state+.02*np.maximum(rg.goal_rate90,1e-6)
            den=rg.groupby('team_id').pen_weight_raw.transform('sum')
            rg['pen_weight']=np.where(den>0,rg.pen_weight_raw/den,0)
            rg['team_pen_conversion']=(rg.pen_weight*rg.pen_conversion).groupby(rg.team_id).transform('sum')
            rg['lambda_pen']=[plam(int(t),int(o)) for t,o in zip(rg.team_id,rg.opponent_team_id)]
            rg['bg_mean_rate90']=rg.player_uuid.map(bmean).fillna(0.)
            rg['bg_sd90']=rg.player_uuid.map(bsd).fillna(float(models['bpsvar']['global_sd90']))

            rg['control_p_start']=rg.new_p_start;rg['control_xmins']=rg.new_xmins
            rg['p_cameo_given_bench']=rg.new_q_sub;rg['start_minutes_mean']=rg.new_start_minutes
            rg['cameo_minutes_mean']=rg.new_sub_minutes
            rg['v4_workload_start_p_start']=rg.new_p_start;rg['v4_workload_start_xmins']=rg.new_xmins
            rg['v4_p_cameo_given_bench']=rg.new_q_sub;rg['v4_start_minutes_mean']=rg.new_start_minutes
            rg['v4_cameo_minutes_mean']=rg.new_sub_minutes;rg['cutoff']=cutoff
            inp,_=make_vfinal_input(rg)
            sim=simulate_many(inp,n=400,seed=93000000+counter);counter+=1
            tg=int(fr.gameweek)
            for rr in rg.itertuples(index=False):
                fid=mp.get(str(rr.player_uuid))
                if fid is None:continue
                pplay=float(rr.new_p_start+(1-rr.new_p_start)*rr.new_q_sub)
                rows.append(dict(origin_gw=origin-1,decision_gw=origin,gw=tg,id=int(fid),
                    player_uuid=str(rr.player_uuid),team=int(rr.team_id),
                    position='GKP' if rr.pos in ('G','GK','GKP') else str(rr.pos),
                    xpts_fixture=float(sim[str(rr.player_uuid)]['xPts']),p_play_fixture=pplay,
                    fixture=str(fr.match_id)))
                origin_count+=1
        faudit.append(dict(decision_gw=origin,cutoff=str(cutoff),fixtures=int(len(fx)),rows=origin_count))
        print(f'GW{origin}: horizon fixtures={len(fx)} rows={origin_count}',flush=True)

    z=pd.DataFrame(rows)
    agg=z.groupby(['origin_gw','decision_gw','gw','id','player_uuid','team','position'],as_index=False).agg(
        xpts_mean=('xpts_fixture','sum'),fixtures=('fixture','nunique'),
        p_no_play=('p_play_fixture',lambda s:float(np.prod(1-np.clip(s,0,1)))))
    agg['p_play']=1-agg.pop('p_no_play')
    z.to_csv(out/'fixture_predictions.csv.gz',index=False,compression='gzip')
    agg.to_csv(out/'rolling_vfinal_forecast.csv.gz',index=False,compression='gzip')
    pd.DataFrame(faudit).to_csv(out/'origin_audit.csv',index=False)
    summary={'classification':'cutoff-safe frozen-state rolling locked MM + vFinal PM',
             'decision_gws':[int(a.start_origin),int(a.end_origin)],'horizon':6,'draws_per_fixture':400,
             'phase5q_xp_used':False,'rows':int(len(agg))}
    (out/'summary.json').write_text(json.dumps(summary,indent=2)+'\n');print(json.dumps(summary,indent=2))
if __name__=='__main__':main()

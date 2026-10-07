#!/usr/bin/env python3
from __future__ import annotations

import argparse,json,sqlite3,sys
from pathlib import Path
import numpy as np
import pandas as pd

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
sys.path.insert(0,str(ROOT/'scripts'))

from fpl_v1_1_model.deadline_keeper import keeper_saves_at_deadline
from fpl_v1_1_model.future_match_importance import load_gw_schedule_snapshots
from fpl_v1_1_model.role_event_priors import QCOLS
from fpl_v1_1_model.joint_simulator import simulate_many_samples
from fpl_v1_1_model.vfinal_replay_state import fit_team_latent,penalty_state
from run_v4_performance_rating_experiment import build_perf_ledger
from run_shared_penalty_joint import player_penalty_ledger
from run_bps_background_experiment import actual_background_ledger,feature_frame as bps_features,apply_model as bps_apply
from run_vfinal_integrated import make_vfinal_input
from vfinal_replay_components import build_fixture_components
from run_rolling_vfinal_gw6_38 import load_models,bps_bounds,map_ids,RAW,TEAMS
import run_horizon_policy_comparison as hp

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--db',required=True)
    ap.add_argument('--source',required=True)
    ap.add_argument('--mm',required=True)
    ap.add_argument('--out',required=True)
    ap.add_argument('--origin',type=int,required=True)
    ap.add_argument('--period-end',type=int,required=True)
    ap.add_argument('--draws',type=int,default=400)
    ap.add_argument('--top-k',type=int,default=20)
    a=ap.parse_args()

    origin=int(a.origin)
    if not (6<=origin<=38): raise ValueError('origin must be 6..38')
    if not (origin<=a.period_end<=38): raise ValueError('period-end must be >= origin and <= 38')

    out=Path(a.out);out.mkdir(parents=True,exist_ok=True)
    src=pd.read_csv(a.source).reset_index(drop=True)
    mm=pd.read_csv(a.mm)
    src['cutoff']=pd.to_datetime(src.cutoff,utc=True)
    mm['cutoff']=pd.to_datetime(mm.cutoff,utc=True)

    models=load_models()
    perf=build_perf_ledger()
    bpsledger=actual_background_ledger()
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
        x['kickoff_at']=pd.to_datetime(x.kickoff_at,utc=True)
        x['available_at']=x.kickoff_at+pd.Timedelta(hours=3)
    ph=ph.drop_duplicates(['fixture_uuid','player_uuid'])

    teams=pd.read_csv(TEAMS)
    code_to_team={int(r.code):int(r.id) for r in teams.itertuples()}
    snaps=load_gw_schedule_snapshots(RAW,code_to_team)
    rolehist=src[['fixture_uuid','player_uuid','team_id','cutoff','max_history_known_at']+QCOLS].copy()
    pen_sides,pen,tm=player_penalty_ledger()
    cm=tm[['team_code','team_id']].drop_duplicates()
    cm=cm[~cm.team_code.duplicated(keep=False)]
    team_code_to_id=dict(zip(cm.team_code.astype(int),cm.team_id.astype(int)))
    mp,ids=map_ids(src)
    ids.to_csv(out/'identity_resolution.csv',index=False)

    cutoff=src.loc[src.gw.eq(origin),'cutoff'].min()
    sstate=src[src.gw<=origin].sort_values(['gw','cutoff']).drop_duplicates('player_uuid',keep='last').copy()
    mstate=mm[mm.gw<=origin].sort_values(['gw','cutoff']).drop_duplicates('player_uuid',keep='last').copy()
    state=sstate.merge(
        mstate[['player_uuid','new_p_start','new_xmins','new_q_sub','new_sub_minutes','new_start_minutes']],
        on='player_uuid',how='inner',validate='one_to_one'
    )
    state['cutoff']=cutoff
    bf=bps_features(state,3.,bpsledger)
    state['bg_mean_rate90']=np.clip(bps_apply(bf,models['bps']),lo,hi)
    broad=state.pos.replace({'G':'GK','GKP':'GK'}).astype(str)
    sd=models['bpsvar']['position_sd90']
    state['bg_sd90']=[float(sd.get(p,models['bpsvar']['global_sd90'])) for p in broad]

    sched=snaps[origin]
    fx=sched[
        (sched.competition=='prem') &
        pd.to_numeric(sched.gameweek,errors='coerce').between(origin,a.period_end) &
        (sched.kickoff>=cutoff)
    ].drop_duplicates('match_id').copy()
    if fx.empty: raise ValueError('No future Premier League fixtures in TC horizon')

    lambdas=fit_team_latent(th[th.available_at<=cutoff],fx[['match_id','home_team_id','away_team_id']],origin)
    past=ph[ph.available_at<=cutoff].copy()
    goals=float(past.goals.sum())
    assist_prob=min(1.,max(.5,float(past.fpl_assists.sum())/goals)) if goals>0 else .7
    pen_state,pen_lam=penalty_state(origin,state,pen_sides,pen,team_code_to_id,models['pen'])
    bmean=state.set_index('player_uuid').bg_mean_rate90.to_dict()
    bsd=state.set_index('player_uuid').bg_sd90.to_dict()

    sample_sums={}
    meta_rows={}
    counter=0

    for fr in fx.itertuples(index=False):
        home=int(fr.home_team_id);away=int(fr.away_team_id)
        rg=state[state.team_id.astype(int).isin([home,away])].copy()
        if rg.empty: continue
        rg['fixture_uuid']=f'tc-o{origin}-{fr.match_id}'
        rg['home_team_id']=home
        rg['away_team_id']=away
        rg['opponent_team_id']=np.where(rg.team_id.astype(int)==home,away,home)
        rg['was_home']=rg.team_id.astype(int)==home
        rg['evidence_at']=cutoff
        rg['expected_minutes']=rg.new_xmins.astype(float)
        rg['pos']=rg.pos.replace({'G':'GK'})

        hgoal,agoal=lambdas[str(fr.match_id)]
        rg=build_fixture_components(
            rg,past,rolehist,cutoff,models['attack'],models['dc'],models['neg'],
            models['ga'],models['dc_model'],models['dc_cal'],perf,
            home,away,hgoal,agoal,assist_prob
        )

        sides=rg[['fixture_uuid','team_id','opponent_team_id','was_home']].drop_duplicates(['fixture_uuid','team_id'])
        ks=keeper_saves_at_deadline(sot,sides,cutoff,models['keeper'])
        rg=rg.merge(
            ks[['fixture_uuid','team_id','lambda_saves']],
            on=['fixture_uuid','team_id'],how='left',validate='many_to_one'
        )

        vals=[pen_state.get(str(pid),(0.,.78)) for pid in rg.player_uuid]
        rg['pen_attempt_state']=[v[0] for v in vals]
        rg['pen_conversion']=[v[1] for v in vals]
        rg['pen_weight_raw']=rg.pen_attempt_state+.02*np.maximum(rg.goal_rate90,1e-6)
        den=rg.groupby('team_id').pen_weight_raw.transform('sum')
        rg['pen_weight']=np.where(den>0,rg.pen_weight_raw/den,0)
        rg['team_pen_conversion']=(rg.pen_weight*rg.pen_conversion).groupby(rg.team_id).transform('sum')
        rg['lambda_pen']=[pen_lam(int(t),int(o)) for t,o in zip(rg.team_id,rg.opponent_team_id)]
        rg['bg_mean_rate90']=rg.player_uuid.map(bmean).fillna(0.)
        rg['bg_sd90']=rg.player_uuid.map(bsd).fillna(float(models['bpsvar']['global_sd90']))

        rg['control_p_start']=rg.new_p_start
        rg['control_xmins']=rg.new_xmins
        rg['p_cameo_given_bench']=rg.new_q_sub
        rg['start_minutes_mean']=rg.new_start_minutes
        rg['cameo_minutes_mean']=rg.new_sub_minutes
        rg['v4_workload_start_p_start']=rg.new_p_start
        rg['v4_workload_start_xmins']=rg.new_xmins
        rg['v4_p_cameo_given_bench']=rg.new_q_sub
        rg['v4_start_minutes_mean']=rg.new_start_minutes
        rg['v4_cameo_minutes_mean']=rg.new_sub_minutes
        rg['cutoff']=cutoff

        inp,_=make_vfinal_input(rg)
        sim=simulate_many_samples(inp,n=int(a.draws),seed=96000000+origin*1000+counter)
        counter+=1
        target_gw=int(fr.gameweek)

        for rr in rg.itertuples(index=False):
            fid=mp.get(str(rr.player_uuid))
            if fid is None: continue
            key=(target_gw,int(fid))
            arr=np.asarray(sim[str(rr.player_uuid)],dtype=np.float32)
            if key in sample_sums:
                sample_sums[key]+=arr
            else:
                sample_sums[key]=arr.copy()
            meta_rows[key]=dict(
                gw=target_gw,candidate_id=int(fid),candidate_name=str(rr.player),
                player_uuid=str(rr.player_uuid),team=int(rr.team_id),
                position='GKP' if rr.pos in ('G','GK','GKP') else str(rr.pos)
            )

    if not sample_sums:
        raise ValueError('No TC samples generated')

    means=[]
    for key,arr in sample_sums.items():
        meta=meta_rows[key].copy()
        meta['mean_points']=float(np.mean(arr))
        means.append(meta)
    mean_df=pd.DataFrame(means)

    selected=[]
    for gw,g in mean_df.groupby('gw',sort=True):
        selected.append(g.sort_values('mean_points',ascending=False).head(int(a.top_k)))
    selected=pd.concat(selected,ignore_index=True)
    keep_keys={(int(r.gw),int(r.candidate_id)) for r in selected.itertuples(index=False)}

    rows=[]
    for key,arr in sample_sums.items():
        if key not in keep_keys: continue
        meta=meta_rows[key]
        for sim_id,pts in enumerate(arr):
            rows.append(dict(
                simulation=int(sim_id),
                gw=int(meta['gw']),
                candidate_id=int(meta['candidate_id']),
                candidate_name=str(meta['candidate_name']),
                player_uuid=str(meta['player_uuid']),
                team=int(meta['team']),
                position=str(meta['position']),
                points=float(pts),
            ))

    sample_df=pd.DataFrame(rows)
    sample_df.to_csv(out/'tc_samples.csv.gz',index=False,compression='gzip')
    selected.sort_values(['gw','mean_points'],ascending=[True,False]).to_csv(out/'tc_candidates.csv',index=False)

    summary=dict(
        classification='TC long-horizon frozen vFinal opportunity samples',
        origin_gw=origin,
        period_end_gw=int(a.period_end),
        draws=int(a.draws),
        top_k_per_gw=int(a.top_k),
        model_math_changed=False,
        tc_only=True,
        future_schedule_source='deadline schedule snapshot at origin',
        rows=int(len(sample_df)),
        candidate_rows=int(len(selected)),
    )
    (out/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
    print(json.dumps(summary,indent=2))

if __name__=='__main__':
    main()

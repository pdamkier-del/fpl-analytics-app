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

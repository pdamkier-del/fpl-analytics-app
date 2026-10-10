#!/usr/bin/env python3
"""Run the unchanged frozen vFinal team attack/defence latent strength fit.

Historical 2026 FPL player xG (only sides with all played players present)
provides observed team xG; 6 upcoming fixture schedules are official FPL.
Not a complete PM/vFinal player-xP run; no model refitting/tuning.
"""
from __future__ import annotations
from pathlib import Path
import json
import numpy as np,pandas as pd
from fpl_v1_1_model.vfinal_replay_state import fit_team_latent

ROOT=Path(__file__).resolve().parents[1]
WORK=ROOT/'work/live-final-model'
BASE=ROOT/'data_v1_1/derived/live_locked_inputs/2026-27-v1'
OUT=BASE/'future_team_goal_lambdas.csv.gz'
AUDIT=WORK/'live_vfinal_team_latent.json'

def run():
    meta=json.loads((WORK/'source_manifest.json').read_text())
    origin=int(meta["target_gw"])
    cutoff=pd.Timestamp(meta['observed_at'])
    games=json.loads((WORK/'fixtures.json').read_text())
    history=pd.read_csv(BASE/'observed_team_xg_history.csv.gz')
    history['available_at']=pd.to_datetime(history.available_at,utc=True,errors='raise')
    history=history.loc[history.available_at<cutoff].copy()
    if len(history)<20 or history.team_id.nunique()!=20:
        raise ValueError('Insufficient pre-cutoff 2026 team historical xG evidence')
    future=[]
    for row in games:
        gw=row.get('event')
        if gw is None or not origin<=int(gw)<=min(38,origin+5) or row.get('finished'):
            continue
        kickoff=pd.Timestamp(row['kickoff_time'])
        if kickoff<cutoff:continue
        future.append(dict(match_id=f"fpl-2026-27-{row['id']}",fpl_fixture_id=int(row['id']),
             gw=int(gw),home_team_id=int(row['team_h']),away_team_id=int(row['team_a']),
             kickoff_at=kickoff.isoformat()))
    targets=pd.DataFrame(future)
    if targets.empty or targets.fpl_fixture_id.duplicated().any() or targets.gw.nunique()!=6:
        raise ValueError('No complete six-GW official fixture horizon')
    strengths=fit_team_latent(history,targets[['match_id','home_team_id','away_team_id']],origin)
    if len(strengths)!=len(targets):raise ValueError('Original frozen team latent fitter omitted fixtures')
    targets['lambda_home_goals']=[strengths[str(mid)][0] for mid in targets.match_id]
    targets['lambda_away_goals']=[strengths[str(mid)][1] for mid in targets.match_id]
    if not np.isfinite(targets[['lambda_home_goals','lambda_away_goals']].to_numpy(float)).all():
        raise ValueError('Nonfinite frozen team-strength predictions')
    if (~targets[['lambda_home_goals','lambda_away_goals']].apply(lambda x:x.between(.05,5))).any().any():
        raise ValueError('Out-of-contract team goal lambdas')
    targets.to_csv(OUT,index=False,compression='gzip')
    audit={'classification':'UNCHANGED_FROZEN_VFINAL_TEAM_LATENT_INPUT_NOT_FULL_PM',
           'season':'2026-27','origin_gw':origin,'historical_team_fixture_sides':len(history),
           'fixture_predictions':len(targets),'future_gws':sorted(map(int,targets.gw.unique())),
           'frozen_fit':'fpl_v1_1_model.vfinal_replay_state.fit_team_latent',
           'frozen_parameters':{'ridge':.25,'half_life':16.},
           'observed_player_xg_complete_only':True,'target_outcomes_used':0,
           'goal_lambda_range':[float(targets[['lambda_home_goals','lambda_away_goals']].min().min()),
             float(targets[['lambda_home_goals','lambda_away_goals']].max().max())],
           'full_pm_completed':False,'live_certified':False}
    AUDIT.write_text(json.dumps(audit,indent=2,allow_nan=False)+'\n')
    print('FROZEN VFINAL CURRENT TEAM STRENGTH:',json.dumps(audit))
    return targets
if __name__=='__main__':run()

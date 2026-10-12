#!/usr/bin/env python3
"""Read-only transparent opponent-adjusted Sunderland baseline vs frozen PM."""
from pathlib import Path
import pandas as pd, numpy as np
B=Path('data_v1_1/derived/live_locked_inputs/2026-27-v1')
h=pd.read_csv(B/'observed_team_xg_history.csv.gz')
f=pd.read_csv(B/'vfinal_live_full_simulator_input.csv.gz')
assert set(['team_id','opponent_team_id','xg','gw']).issubset(h)
assert set(['team_id','opponent_team_id','lambda_home_goals','lambda_away_goals','home_team_id','target_gw']).issubset(f)
h=h[h.gw<7].copy()
# Historical rows represent team fixture sides. No reliance on player events.
means=h.groupby('team_id').agg(attack=('xg','mean'),games=('xg','size'))
opp=h[['team_id','opponent_team_id','xg']].rename(columns={'team_id':'attacker','opponent_team_id':'team_id'})
against=opp.groupby('team_id').agg(defence=('xg','mean'),games_against=('xg','size'))
league=float(h.xg.mean())
print('BASE_LEAGUE_XG_PER_TEAM_GAME',round(league,4))
print('BASE_SUNDERLAND',means.loc[20].to_dict(),against.loc[20].to_dict())
sub=f[(f.team_id==20)&(f.fpl_element==542)].sort_values('target_gw')
for r in sub.itertuples(index=False):
    opponent=int(r.opponent_team_id)
    teamxg=float(means.loc[20,'attack'])
    opxga=float(against.loc[opponent,'defence'])
    simple=teamxg*opxga/league
    frozen=float(r.lambda_home_goals if r.home_team_id==20 else r.lambda_away_goals)
    print('BASE_COMPARE',dict(gw=int(r.target_gw),opponent_id=opponent,sunderland_hist_xg=round(teamxg,3),opponent_hist_xga=round(opxga,3),simple_opponent_adjusted_xg=round(simple,3),frozen_PM_goals=round(frozen,3),gap=round(frozen-simple,3)))

# Diagnose the observed finishing gap using exactly the same completed fixtures.
ph=pd.read_csv(B/'player_fixture_observations.csv.gz',low_memory=False)
side=ph.groupby(['fixture_uuid','team_id'],as_index=False).agg(actual_goals=('goals','sum'),actual_assists=('fpl_assists','sum'),observed_xg=('xg','sum'))
same=h.merge(side,on=['fixture_uuid','team_id'],how='left',validate='one_to_one')
sun=same[same.team_id.eq(20)].sort_values('gw')
print('FINISH_SUNDERLAND_MATCHES',sun[['gw','xg','observed_xg','actual_goals','actual_assists']].to_json(orient='records'))
print('FINISH_SUNDERLAND_TOTAL',dict(games=len(sun),xg=round(float(sun.xg.sum()),3),goals=round(float(sun.actual_goals.sum()),3),goals_per_game=round(float(sun.actual_goals.mean()),3),xg_per_game=round(float(sun.xg.mean()),3),finishing_ratio=round(float(sun.actual_goals.sum()/sun.xg.sum()),3)))
le=ph[ph.fpl_element.eq(542)].sort_values('gw')
print('FINISH_LEFEE',dict(games=len(le),minutes=float(le.minutes.sum()),xg=float(le.xg.sum()),xa=float(le.xa.sum()),goals=float(le.goals.sum()),fpl_assists=float(le.fpl_assists.sum())))

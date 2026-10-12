#!/usr/bin/env python3
"""Read-only audit of existing simulator events; never changes locked scoring."""
from pathlib import Path
import sys,json
from dataclasses import replace
import numpy as np,pandas as pd
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT/'src'),str(ROOT/'scripts')]
from fpl_v1_1_model.joint_simulator import MatchSimInput,PlayerSimInput,simulate_match
from fpl_v1_1_model.negative_events import competing_card_probabilities
from run_vfinal_integrated import make_vfinal_input
OUT=ROOT/'analysis/results/full-model-audit-20261012'

def own_goal_probe():
    # Explicit forensic fixture; not a real squad or personal recommendation.
    p=PlayerSimInput('audit-defender','H','DEF',1.,0.,90.,16.,p_own_goal=1.)
    q=PlayerSimInput('audit-opponent','A','FWD',1.,0.,90.,16.)
    r=simulate_match(MatchSimInput('H','A',0.,0.,(p,q)),np.random.default_rng(1))['audit-defender']
    return dict(classification='SYNTHETIC_FORENSIC_PROBE_ONLY',minutes=r.minutes,own_goals=r.own_goal,goals_conceded=r.goals_conceded_while_on_pitch,clean_sheet=r.clean_sheet,contradiction=r.own_goal>r.goals_conceded_while_on_pitch)

def main():
    frame=pd.read_csv(ROOT/'data_v1_1/derived/live_locked_inputs/2026-27-v1/vfinal_live_full_simulator_input.csv.gz',low_memory=False);saved=pd.read_csv(ROOT/'data_v1_1/derived/live_locked_inputs/2026-27-v1/live_vfinal_fixture_xp.csv.gz');offset={fx:i for i,fx in enumerate(sorted(frame.fixture_uuid.unique()))};rows=[]
    focus=frame[frame.target_gw.eq(frame.target_gw.min())&frame.player.isin(['Haaland','Saka'])]
    for fx,g in focus.groupby('fixture_uuid'):
        group=frame[frame.fixture_uuid.eq(fx)];inp,_=make_vfinal_input(group);inp=replace(inp,bps_rules='2026-27');rng=np.random.default_rng(93000000+offset[fx]);events={pid:[] for pid in g.player_uuid}
        for draw in range(400):
            results=simulate_match(inp,rng)
            for pid in events:events[pid].append(results[str(pid)])
        for r in g.itertuples():
            ev=events[r.player_uuid];base=saved[saved.fixture_uuid.eq(fx)&saved.player_uuid.eq(r.player_uuid)].iloc[0]
            xp=float(np.mean([v.points for v in ev]));assert xp==base.xpts_fixture
            goal_pts=4 if r.pos=='FWD' else 5
            rows.append(dict(player=r.player,gw=int(r.target_gw),xp=xp,goal_mu_input=float(r.goal_mu),goal_points=float(np.mean([goal_pts*v.goals for v in ev])),penalty_goal_points=float(np.mean([goal_pts*v.penalty_goals for v in ev])),ordinary_goal_points=float(np.mean([goal_pts*(v.goals-v.penalty_goals) for v in ev])),goal_rate90_input=float(r.goal_rate90),lambda_pen=float(r.lambda_pen),pen_weight=float(r.pen_weight),pen_conversion=float(r.pen_conversion)))
    cards=competing_card_probabilities(45.,.2,0.)
    report=dict(classification='READ_ONLY_EVENT_SEMANTICS_AUDIT',focus=rows,own_goal=own_goal_probe(),discipline_exposure_diagnostic=dict(expected_minutes=45.,p_play=.5,probability_from_mean_exposure=cards.yellow,unconditional_simulated_probability=.5*cards.yellow,interpretation='The exposure-derived fixture probability is applied only after appearance; possible extra attenuation requiring conditional-hazard backtesting.'),penalty_note='Team penalty goal mass is subtracted from ordinary team goals, so total-goal double counting is not confirmed. Ordinary player weights still come from inclusive goal/xG rates; penalty-taker redistribution needs separate npxG/source/calibration validation.',promotion_allowed=False,locked_model_active=False)
    OUT.mkdir(parents=True,exist_ok=True);(OUT/'joint_event_semantics_report.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report),flush=True)
if __name__=='__main__':main()

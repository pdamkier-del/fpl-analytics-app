"""Phase 4B adapters: turn frozen component forecasts into joint match inputs.

This module does not refit any Phase 1-3 half-life. It is deliberately a thin
integration layer so the joint simulator can be exercised on the same historical
forecast rows that were already frozen by the component phases.
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Mapping
import math
from .joint_simulator import PlayerSimInput, MatchSimInput
from .negative_events import DisciplineProbabilities

@dataclass(frozen=True)
class FrozenPlayerForecast:
    player_id: str
    team_id: int
    position: str
    p_start: float
    expected_minutes: float
    start_minutes_mean: float
    cameo_minutes_mean: float
    p_cameo_given_bench: float
    goal_mu: float
    assist_mu: float
    dc_mu: float=0.0
    dc_alpha: float=0.0
    p_yellow: float=0.0
    p_red: float=0.0
    lambda_saves: float=0.0
    bps_background_mean: float=0.0
    bps_background_sd: float=0.0
    p_own_goal: float=0.0
    bps_background_rate90: float|None=None
    bps_background_sd90: float|None=None
    save_bucket_tilts: tuple[float,float,float,float,float]|None=None
    penalty_weight: float=0.0
    penalty_conversion: float=0.78


def _rate_weight(mu: float, xmins: float) -> float:
    """Convert fixture mean back to an on-pitch allocation propensity."""
    if mu <= 0 or xmins <= 1e-9:
        return 0.0
    return float(mu) * 90.0 / float(xmins)


def player_to_sim_input(p: FrozenPlayerForecast) -> PlayerSimInput:
    py=max(0.0,float(p.p_yellow)); pr=max(0.0,float(p.p_red))
    s=py+pr
    if s>1.0:
        py/=s; pr/=s
    disc=DisciplineProbabilities(1.0-py-pr,py,pr)
    dc_mu90=(float(p.dc_mu)*90.0/float(p.expected_minutes)) if p.expected_minutes>1e-9 else 0.0
    pos="GK" if p.position=="GKP" else p.position
    return PlayerSimInput(
        player_id=str(p.player_id),team=str(p.team_id),position=pos,
        p_start=min(1.0,max(0.0,float(p.p_start))),
        p_cameo_given_bench=min(1.0,max(0.0,float(p.p_cameo_given_bench))),
        start_minutes_mean=float(p.start_minutes_mean),cameo_minutes_mean=float(p.cameo_minutes_mean),
        goal_weight=_rate_weight(p.goal_mu,p.expected_minutes),
        assist_weight=_rate_weight(p.assist_mu,p.expected_minutes),
        dc_mu_90=max(0.0,dc_mu90),dc_alpha=max(0.0,float(p.dc_alpha)),discipline=disc,
        p_own_goal=min(1.0,max(0.0,float(p.p_own_goal))),
        bps_background_mean=float(p.bps_background_mean),bps_background_sd=max(0.0,float(p.bps_background_sd)),
        bps_background_rate90=(None if p.bps_background_rate90 is None else float(p.bps_background_rate90)),
        bps_background_sd90=(None if p.bps_background_sd90 is None else max(0.0,float(p.bps_background_sd90))),
        is_keeper=pos=="GK",lambda_saves=max(0.0,float(p.lambda_saves)),
        save_bucket_tilts=p.save_bucket_tilts,
        penalty_weight=max(0.0,float(p.penalty_weight)),
        penalty_conversion=min(1.0,max(0.0,float(p.penalty_conversion))),
    )


def build_match_input(*,home_team_id:int,away_team_id:int,lambda_home_goals:float,lambda_away_goals:float,
                      players:list[FrozenPlayerForecast],assist_probability_per_goal:float=0.90,
                      lambda_home_penalties:float=0.0,lambda_away_penalties:float=0.0,
                      home_penalty_conversion:float=0.78,away_penalty_conversion:float=0.78,
                      p_penalty_save_given_miss:float=0.0,bps_rules:str="2026-27")->MatchSimInput:
    if not (0 <= assist_probability_per_goal <= 1):
        raise ValueError("assist_probability_per_goal must be in [0,1]")
    return MatchSimInput(
        str(home_team_id),str(away_team_id),float(lambda_home_goals),float(lambda_away_goals),
        tuple(player_to_sim_input(p) for p in players),float(assist_probability_per_goal),
        lambda_home_penalties=max(0.0,float(lambda_home_penalties)),
        lambda_away_penalties=max(0.0,float(lambda_away_penalties)),
        home_penalty_conversion=min(1.0,max(0.0,float(home_penalty_conversion))),
        away_penalty_conversion=min(1.0,max(0.0,float(away_penalty_conversion))),
        p_penalty_save_given_miss=min(1.0,max(0.0,float(p_penalty_save_given_miss))),
        bps_rules=str(bps_rules),
    )

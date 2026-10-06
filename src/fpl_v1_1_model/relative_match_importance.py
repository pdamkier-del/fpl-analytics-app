"""Relative Match Importance v2.

A team's active competitions compete for a fixed importance budget. Raw
competition priority combines base competition value with stage urgency; the
shares are normalized so active competition shares always sum to one.

This module is experimental and does not replace the locked MI reference.
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Mapping,Sequence
from .match_importance import BASE_COMPETITION_VALUES,canonical_competition

# Deliberately more separated than v1. These are *urgency multipliers*, not
# final probabilities or direct player effects.
STAGE_URGENCY={
    "league_phase":0.45,
    "group":0.45,
    "early_cup":0.40,
    "third_round":0.42,
    "fourth_round":0.50,
    "fifth_round":0.62,
    "playoff":0.68,
    "round_of_16":0.78,
    "quarter_final":1.00,
    "semi_final":1.35,
    "final":1.85,
    "prem_early":0.55,
    "prem_mid":0.72,
    "prem_late":1.00,
    "prem_run_in":1.25,
}

def canonical_stage(value:str|None)->str:
    s=str(value or "").strip().lower().replace("-","_").replace(" ","_")
    aliases={
      "leaguephase":"league_phase","group_stage":"group",
      "round_of_16":"round_of_16","last_16":"round_of_16","r16":"round_of_16",
      "quarterfinal":"quarter_final","quarter_finals":"quarter_final",
      "semifinal":"semi_final","semi_final":"semi_final","semi_finals":"semi_final",
      "finals":"final",
    }
    return aliases.get(s,s)

def stage_urgency(stage:str|None,default=.55)->float:
    return float(STAGE_URGENCY.get(canonical_stage(stage),default))

def raw_competition_priority(competition:str,stage:str|None,
                             base_values:Mapping[str,float]=BASE_COMPETITION_VALUES)->float:
    c=canonical_competition(competition)
    return max(0.0,float(base_values.get(c,0.0)))*max(0.0,stage_urgency(stage))

def normalized_competition_shares(
    active:Sequence[tuple[str,str|None]],
    base_values:Mapping[str,float]=BASE_COMPETITION_VALUES,
)->dict[str,float]:
    """Return fixed-budget shares; shares sum to 1 over positive active comps."""
    raw={}
    for comp,stage in active:
        c=canonical_competition(comp)
        raw[c]=raw.get(c,0.0)+raw_competition_priority(c,stage,base_values)
    denom=sum(raw.values())
    if denom<=0:return {c:0.0 for c in raw}
    return {c:v/denom for c,v in raw.items()}

def premier_stage_bucket(gw:int)->str:
    g=max(1,min(38,int(gw)))
    if g<=10:return "prem_early"
    if g<=25:return "prem_mid"
    if g<=33:return "prem_late"
    return "prem_run_in"

def infer_stage_2025_26(competition:str,kickoff,gameweek=None)->str:
    """Cutoff-safe stage inference from fixed competition calendar structure.

    Uses competition/date only, never match outcomes or later advancement.
    Intended for the 2025/26 historical experiment.
    """
    import pandas as pd
    c=canonical_competition(competition)
    ts=pd.Timestamp(kickoff)
    m,d=ts.month,ts.day
    if c=="prem":
        return premier_stage_bucket(int(gameweek) if gameweek is not None and gameweek==gameweek else 19)
    if c in {"champions-league","europa-league"}:
        if m<=1 or m>=9:return "league_phase"
        if m==2:return "playoff"
        if m==3:return "round_of_16"
        if m==4 and d<=20:return "quarter_final"
        if m==4 or (m==5 and d<=10):return "semi_final"
        if m==5:return "final"
    if c=="conference-league":
        if m<=12 and m>=9:return "league_phase"
        if m==2:return "playoff"
        if m==3:return "round_of_16"
        if m==4 and d<=20:return "quarter_final"
        if m==4 or (m==5 and d<=15):return "semi_final"
        if m==5:return "final"
    if c=="fa-cup":
        if m==1:return "third_round"
        if m==2:return "fourth_round"
        if m==3:return "fifth_round"
        if m==4 and d<=15:return "quarter_final"
        if m==4 or (m==5 and d<=10):return "semi_final"
        if m==5:return "final"
    if c=="efl-cup":
        if m in (8,9,10):return "early_cup"
        if m==12:return "quarter_final"
        if m in (1,2):return "semi_final"
        if m==3:return "final"
    return "early_cup"

# Important PL boundaries are configurable because European qualification can
# differ by season. 2025/26 experiment uses title, UCL/Europe and relegation
# boundaries; callers may override them with a season-specific certified set.
DEFAULT_PL_BOUNDARIES=(1,5,7,17)

def premier_race_multiplier(
    *,position:int,points:float,opponent_position:int,opponent_points:float,
    table_points_by_position:Mapping[int,float],games_remaining:int,
    important_boundaries:Sequence[int]=DEFAULT_PL_BOUNDARIES,
)->float:
    """Cutoff-safe PL race urgency multiplier.

    Increases PL priority when a club is close in points to an important table
    boundary and when the opponent is a direct rival. The multiplier changes
    only PL's raw share; normalized_competition_shares_v2 keeps the total
    importance budget fixed.
    """
    # A points gap means more late in the season because there are fewer points
    # left to recover. Keep the scale conservative and bounded.
    remaining=max(1,int(games_remaining))
    scale=max(2.0,min(8.0,0.22*remaining+1.5))

    closeness=0.0
    for b in important_boundaries:
        bp=table_points_by_position.get(int(b))
        if bp is None: continue
        gap=abs(float(points)-float(bp))
        closeness=max(closeness,max(0.0,1.0-gap/scale))

    opp_gap=abs(float(points)-float(opponent_points))
    same_race=max(0.0,1.0-opp_gap/scale)
    position_proximity=max(0.0,1.0-abs(int(position)-int(opponent_position))/4.0)
    direct_rival=same_race*position_proximity

    # Late-season races should matter more than identical gaps in autumn.
    late=1.0-min(1.0,remaining/37.0)
    multiplier=1.0 + (0.55+0.35*late)*closeness + (0.30+0.35*late)*direct_rival
    return float(min(2.10,max(1.0,multiplier)))

def normalized_competition_shares_v2(
    active:Sequence[tuple[str,str|None]],
    *,
    premier_race_mult:float=1.0,
    base_values:Mapping[str,float]=BASE_COMPETITION_VALUES,
)->dict[str,float]:
    """Fixed-budget shares with PL race context. Sum is always one."""
    raw={}
    for comp,stage in active:
        c=canonical_competition(comp)
        v=raw_competition_priority(c,stage,base_values)
        if c=="prem":
            v*=max(0.0,float(premier_race_mult))
        raw[c]=raw.get(c,0.0)+v
    denom=sum(raw.values())
    if denom<=0:return {c:0.0 for c in raw}
    return {c:v/denom for c,v in raw.items()}

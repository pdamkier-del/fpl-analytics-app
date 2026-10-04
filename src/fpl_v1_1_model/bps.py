"""2026/27 FPL Bonus Points System mechanics for the joint simulator.

This module encodes the *known official event-to-BPS rules* and exact bonus tie
allocation.  It does not claim that Historical Core can reconstruct every BPS
component: several Opta event fields are unavailable in the free historical
feed.  Missing background BPS therefore remains a separate modelling problem.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping


@dataclass(frozen=True)
class BPSComponents:
    minutes: int = 0
    position: str = "MID"
    non_penalty_goals: int = 0
    penalty_goals: int = 0
    assists: int = 0
    clean_sheet: int = 0
    penalty_saves: int = 0
    saves_total: int = 0
    saves_inside_box: int = 0
    big_chance_saves: int = 0
    successful_open_play_crosses: int = 0
    big_chances_created: int = 0
    clearances_blocks_interceptions: int = 0
    recoveries: int = 0
    successful_tackles: int = 0
    key_passes: int = 0
    successful_dribbles: int = 0
    winning_goals: int = 0
    goal_line_clearances: int = 0
    fouls_won: int = 0
    shots_on_target: int = 0
    passes_attempted: int = 0
    passes_completed: int = 0
    goals_conceded: int = 0
    penalties_conceded: int = 0
    penalty_misses: int = 0
    yellow_cards: int = 0
    red_cards: int = 0
    own_goals: int = 0
    big_chances_missed: int = 0
    errors_leading_to_goal: int = 0
    errors_leading_to_attempt: int = 0
    fouls_conceded: int = 0
    offsides: int = 0
    shots_off_target: int = 0

    def __post_init__(self) -> None:
        numeric = [v for k,v in self.__dict__.items() if k != "position"]
        if any(int(v) < 0 for v in numeric):
            raise ValueError("BPS component counts must be non-negative")
        if self.saves_inside_box > self.saves_total or self.big_chance_saves > self.saves_total:
            raise ValueError("save subtypes cannot exceed total saves")
        if self.passes_completed > self.passes_attempted:
            raise ValueError("passes_completed cannot exceed passes_attempted")


def bps_2026_27(c: BPSComponents) -> int:
    """Deterministic BPS from generated 2026/27 event components.

    2026/27 changes encoded here: no ``being tackled`` penalty; CBI scores one
    BPS per three (not two); every GK save earns 2 BPS, with +1 for an inside-box
    save and +1 for a big-chance save; penalty-save base is 7 BPS.  A saved
    penalty should also be present in the relevant save counters, yielding the
    intended combined save BPS.
    """
    pos=c.position
    score=0
    if c.minutes > 0:
        score += 6 if c.minutes > 60 else 3
    score += 12*c.penalty_goals
    goal_value={"GK":12,"GKP":12,"DEF":12,"MID":18,"FWD":24}.get(pos,18)
    score += goal_value*c.non_penalty_goals
    score += 9*c.assists
    if pos in ("GK","GKP","DEF"):
        score += 12*int(bool(c.clean_sheet))
    score += 7*c.penalty_saves
    score += 2*c.saves_total + c.saves_inside_box + c.big_chance_saves
    score += c.successful_open_play_crosses
    score += 3*c.big_chances_created
    score += c.clearances_blocks_interceptions//3
    score += c.recoveries//3
    score += 2*c.successful_tackles
    score += c.key_passes
    score += c.successful_dribbles
    score += 3*c.winning_goals
    score += 9*c.goal_line_clearances
    score += c.fouls_won
    score += 2*c.shots_on_target
    if c.passes_attempted >= 30:
        pct=100.0*c.passes_completed/c.passes_attempted
        if pct >= 90: score += 6
        elif pct >= 80: score += 4
        elif pct >= 70: score += 2
    if pos in ("GK","GKP","DEF"):
        score -= 4*c.goals_conceded
    score -= 3*c.penalties_conceded
    score -= 6*c.penalty_misses
    score -= 3*c.yellow_cards
    score -= 9*c.red_cards
    score -= 6*c.own_goals
    score -= 3*c.big_chances_missed
    score -= 3*c.errors_leading_to_goal
    score -= c.errors_leading_to_attempt
    score -= c.fouls_conceded
    score -= c.offsides
    score -= c.shots_off_target
    return int(score)


def allocate_bonus_points(bps_by_player: Mapping[str,int]) -> dict[str,int]:
    """Apply official 3/2/1 bonus allocation including all tie cases."""
    if not bps_by_player:
        return {}
    groups: dict[int,list[str]]={}
    for player,score in bps_by_player.items():
        groups.setdefault(int(score),[]).append(player)
    levels=sorted(groups,reverse=True)
    out={p:0 for p in bps_by_player}
    slots=[3,2,1]
    rank_index=0
    for level in levels:
        if rank_index >= 3:
            break
        players=groups[level]
        n=len(players)
        # Official tie logic is equivalent to all tied players taking the bonus
        # attached to the best occupied rank, while the tied ranks are consumed.
        bonus=slots[rank_index]
        for p in players:
            out[p]=bonus
        rank_index += n
    return out

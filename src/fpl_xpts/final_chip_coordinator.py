"""Frozen chip parameters and additive four-chip arbitration.

The individual FH/WC/BB and TC model scores are computed by existing modules.
This module only picks at most one eligible chip per GW; it does NOT refit any
model or anticipate realized future performance.
"""
from __future__ import annotations
from dataclasses import dataclass

from .simple_chip_thresholds import (
    LOCKED_LAMBDA_FH, LOCKED_LAMBDA_WC, choose_locked_fh_wc
)
from .bench_boost_policy import LOCKED_LAMBDA_BB, locked_bb_threshold

@dataclass(frozen=True)
class FinalChipDecision:
    chip: str
    q_fh: float
    q_wc: float
    q_bb: float
    q_tc: float

def choose_final_chip(
    *,
    gw: int,
    fh_available: bool,
    wc_available: bool,
    bb_available: bool,
    tc_available: bool,
    fh_gain: float=0.0,
    wc_gain: float=0.0,
    bb_gain: float=0.0,
    tc_action: str="SAVE_TC",
    tc_use_edge: float=float("-inf"),
    tc_candidate_is_eligible: bool=False,
) -> FinalChipDecision:
    """Choose exactly one chip or normal, respecting each locked timing gate.

    TC's *locked model* decides USE_TC vs SAVE_TC and its own marginal
    use-edge; this is not recalculated here. A TC must target an owned
    starting-XI player and one cannot select another chip simultaneously.
    All FH/WC thresholds are unchanged. Bench Boost is measured against
    the ordinary TS lineup including expected autosubs.
    """
    if not 1<=gw<=38: raise ValueError("Invalid GW")
    mask=(1 if fh_available else 0)|(2 if wc_available else 0)
    prior=choose_locked_fh_wc(gw,mask,fh_gain,wc_gain)
    q_fh=prior.q_fh
    q_wc=prior.q_wc
    q_bb=bb_gain-locked_bb_threshold(gw) if bb_available else float("-inf")
    q_tc=(float(tc_use_edge) if tc_available and tc_action=="USE_TC"
          and tc_candidate_is_eligible else float("-inf"))
    # On ties, preserve chip rights rather than exercising them.
    scores={"normal":0.0,"fh":q_fh,"wc":q_wc,"bb":q_bb,"tc":q_tc}
    choice=max(scores,key=lambda chip:(scores[chip],chip=="normal"))
    return FinalChipDecision(choice,q_fh,q_wc,q_bb,q_tc)

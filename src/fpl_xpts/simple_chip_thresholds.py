from __future__ import annotations
from dataclasses import dataclass

# User-approved locked values (2026-10-09). Do not retune while developing BB.
LOCKED_LAMBDA_FH = 10.0
LOCKED_LAMBDA_WC = 20.0

@dataclass
class ChipDecision:
    choice: str
    g_fh_now: float
    g_wc_now: float
    q_normal: float
    q_fh: float
    q_wc: float

def choose_simple_chip(gw:int,mask:int,fh_gain:float,wc_gain:float,
                       lambda_fh:float,lambda_wc:float)->ChipDecision:
    if not 1 <= gw <= 38: raise ValueError("Invalid GW")
    start,end=(1,19) if gw<=19 else (20,38)
    f=(end-gw)/(end-start)
    qfh=fh_gain-lambda_fh*f if mask&1 else float("-inf")
    qwc=wc_gain-lambda_wc*f if mask&2 else float("-inf")
    scores={"normal":0.0,"fh":qfh,"wc":qwc}
    choice=max(scores,key=lambda x:(scores[x],x=="normal"))
    return ChipDecision(choice,fh_gain,wc_gain,0.0,qfh,qwc)


def choose_locked_fh_wc(gw: int, mask: int, fh_gain: float, wc_gain: float) -> ChipDecision:
    """Frozen FH/WC policy; preserves original choice function for audit replays."""
    return choose_simple_chip(gw, mask, fh_gain, wc_gain, LOCKED_LAMBDA_FH, LOCKED_LAMBDA_WC)

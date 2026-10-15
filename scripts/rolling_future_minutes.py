"""Opt-in schedule-aware future fixture minutes, research-only.

Never uses future results, later news, or realized future minutes.
Default zero coefficient exactly reproduces the frozen-origin minute inputs.
"""
from __future__ import annotations
import math


def project_fixture_minutes(p_start, start_minutes, p_cameo, cameo_minutes,
                            days_rest=None, short_rest_start_penalty=0.0):
    """Conditional known-schedule short-rest scenario, not fitted or certified.

    Penalty applies only if the *known-at-origin* rest interval is below
    four days. Never automatically returns injured players to the XI.
    """
    values=(p_start,start_minutes,p_cameo,cameo_minutes,short_rest_start_penalty)
    if not all(math.isfinite(float(v)) for v in values):
        raise ValueError("Nonfinite origin-minute parameter")
    if not (0<=p_start<=1 and 0<=p_cameo<=1 and
            0<=start_minutes<=90 and 0<=cameo_minutes<=90 and
            0<=short_rest_start_penalty<=1):
        raise ValueError("Invalid origin-minute parameter")
    if days_rest is not None and (not math.isfinite(float(days_rest)) or days_rest<0):
        raise ValueError("Invalid days_rest")
    factor=1.0
    if days_rest is not None and days_rest<4:
        factor=1.0-short_rest_start_penalty*(4.0-days_rest)/4.0
    p=float(p_start)*factor
    xmins=p*float(start_minutes)+(1-p)*float(p_cameo)*float(cameo_minutes)
    return {
        "p_start":p,"start_minutes":float(start_minutes),
        "p_cameo":float(p_cameo),"cameo_minutes":float(cameo_minutes),
        "xmins":xmins,"days_rest":days_rest,"short_rest_factor":factor,
        "scenario_only":True
    }

"""Strictly select the latest player state known by an origin cutoff.

Research helper only: verifies snapshot chronology, not source publication time.
"""
from __future__ import annotations


def select_deadline_state(frame, origin, cutoff):
    if frame.empty or "cutoff" not in frame or "gw" not in frame or "player_uuid" not in frame:
        raise ValueError("Player snapshot requires cutoff, gw and player_uuid")
    if frame["cutoff"].isna().any():
        raise ValueError("Player snapshot contains missing cutoff timestamps")
    chosen = frame[(frame["gw"] <= origin) & (frame["cutoff"] <= cutoff)]
    chosen = chosen.sort_values(["cutoff", "gw"]).drop_duplicates("player_uuid", keep="last").copy()
    if chosen.empty:
        raise ValueError(f"No player state available by GW{origin} deadline")
    if (chosen["cutoff"] > cutoff).any():
        raise AssertionError("Future state included in forecast")
    return chosen

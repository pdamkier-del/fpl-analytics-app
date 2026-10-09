"""Exact adapter for existing locked TC-v2 timing into manager-owned squads.

Do not change the TC policy calibration or eligibility rules here. TC is
exercisable only when its designated candidate is in the current TS starting XI.
TC is a captain bonus, so a player unavailable on this squad cannot be
credited as if owned. Realized scoring remains in season_replay.
"""
from __future__ import annotations
from pathlib import Path
import pandas as pd

from .chip_planner import TCV2Config, decide_tc_v2_from_samples

def load_tc_origin(root: str | Path, gw: int, *, prefix: str = "tc-origin-") -> pd.DataFrame:
    root=Path(root)
    p=root/f"{prefix}{gw}"/"tc_samples.csv.gz"
    if not p.exists():raise FileNotFoundError(p)
    return pd.read_csv(p)

def tc_v2_opportunity(samples: pd.DataFrame, gw: int) -> dict:
    """Call existing TC-v2 without changing any of its calibrated parameters."""
    end=19 if gw<=19 else 38
    return decide_tc_v2_from_samples(
        samples,current_gw=gw,period_end_gw=end,config=TCV2Config()
    )

def tc_candidate_eligible(decision: dict, lineup: pd.DataFrame) -> bool:
    if decision.get('action')!='USE_TC' or decision.get('candidate_id') is None:
        return False
    pid=int(decision['candidate_id'])
    return bool(((lineup.id.astype(int)==pid)&lineup.role.isin(('C','VC','XI'))).any())

def tc_captain_lineup(lineup: pd.DataFrame, candidate_id: int) -> pd.DataFrame:
    """Retain TS selected XI but assign TC candidate captain for this one GW."""
    pid=int(candidate_id)
    rows=lineup.copy()
    if not ((rows.id.astype(int)==pid)&rows.role.isin(('C','VC','XI'))).any():
        raise ValueError('TC player is not in the current starting XI')
    captain=int(rows.loc[rows.role.eq('C'),'id'].iloc[0])
    if captain==pid:return rows
    vice=int(rows.loc[rows.role.eq('VC'),'id'].iloc[0])
    rows.loc[rows.id.eq(captain),'role']='VC' if vice==pid else 'XI'
    rows.loc[rows.id.eq(pid),'role']='C'
    return rows

def tc_origin_provider(root: str | Path, *, prefix: str = "tc-origin-"):
    def provider(gw: int, state, lineup: pd.DataFrame) -> dict:
        samples=load_tc_origin(root,gw,prefix=prefix)
        return tc_v2_opportunity(samples,gw)
    return provider

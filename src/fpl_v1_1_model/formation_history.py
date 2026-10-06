"""Cutoff-safe team formation history for MM expected-XI selection."""
from __future__ import annotations
from collections import defaultdict
from math import log
import pandas as pd

class FormationHistory:
    def __init__(self):
        self.games=defaultdict(list)

    def add_game(self,team,known_at,fixture,formation):
        t=pd.to_datetime(known_at,utc=True)
        self.games[int(team)].append({
            "known_at":t,"fixture":str(fixture),"formation":str(formation)
        })

    def before(self,team,cutoff):
        cut=pd.to_datetime(cutoff,utc=True)
        return sorted(
            (g for g in self.games[int(team)] if g["known_at"]<cut),
            key=lambda g:(g["known_at"],g["fixture"])
        )

    def distribution(self,team,cutoff,half_life=5.0,formations=None,smoothing=.15):
        games=self.before(team,cutoff)
        allowed=list(formations or sorted({g["formation"] for g in games}))
        if not allowed:
            return {}
        mass={f:float(smoothing) for f in allowed}
        for lag,g in enumerate(reversed(games)):
            if g["formation"] not in mass:
                continue
            mass[g["formation"]]+=2.0**(-lag/float(half_life))
        den=sum(mass.values())
        return {f:v/den for f,v in mass.items()} if den else {}

    def log_prior(self,team,cutoff,half_life=5.0,formations=None,smoothing=.15,strength=1.0):
        dist=self.distribution(team,cutoff,half_life=half_life,formations=formations,smoothing=smoothing)
        return {f:float(strength)*log(max(1e-9,p)) for f,p in dist.items()}

def history_from_classified_starters(frame:pd.DataFrame,known_delay_hours=3.0):
    """Build one formation observation per completed team-match.

    The input is the post-match classified starter ledger. Formation labels are
    outcomes and therefore become available only after the match.
    """
    required={"team_id","fixture_uuid","kickoff","formation"}
    missing=required-set(frame.columns)
    if missing:
        raise ValueError(f"missing formation history columns: {sorted(missing)}")
    x=frame.copy()
    x["kickoff"]=pd.to_datetime(x.kickoff,utc=True,errors="coerce")
    if x.kickoff.isna().any():
        raise ValueError("invalid kickoff")
    one=x[["team_id","fixture_uuid","kickoff","formation"]].drop_duplicates()
    if one.duplicated(["team_id","fixture_uuid"]).any():
        raise ValueError("multiple formations for same team-match")
    h=FormationHistory()
    for r in one.itertuples(index=False):
        h.add_game(r.team_id,r.kickoff+pd.Timedelta(hours=known_delay_hours),r.fixture_uuid,r.formation)
    return h

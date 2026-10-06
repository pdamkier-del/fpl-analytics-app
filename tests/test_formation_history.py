import pandas as pd
import pytest
from fpl_v1_1_model.formation_history import FormationHistory,history_from_classified_starters

def test_future_formation_not_used():
    h=FormationHistory()
    h.add_game(1,"2026-01-01T20:00:00Z","a","4-2-3-1")
    h.add_game(1,"2026-01-10T20:00:00Z","b","3-4-2-1")
    d=h.distribution(1,"2026-01-05T12:00:00Z",formations=["4-2-3-1","3-4-2-1"])
    assert d["4-2-3-1"]>d["3-4-2-1"]

def test_recent_formation_gets_more_weight():
    h=FormationHistory()
    h.add_game(1,"2026-01-01T20:00:00Z","a","4-3-3")
    h.add_game(1,"2026-01-08T20:00:00Z","b","4-2-3-1")
    d=h.distribution(1,"2026-01-09T12:00:00Z",half_life=2,formations=["4-3-3","4-2-3-1"])
    assert d["4-2-3-1"]>d["4-3-3"]

def test_build_one_formation_per_team_match():
    x=pd.DataFrame([
      {"team_id":1,"fixture_uuid":"f","kickoff":"2026-01-01T12:00:00Z","formation":"4-3-3","player_uuid":"p1"},
      {"team_id":1,"fixture_uuid":"f","kickoff":"2026-01-01T12:00:00Z","formation":"4-3-3","player_uuid":"p2"},
    ])
    h=history_from_classified_starters(x)
    assert len(h.games[1])==1
    assert h.games[1][0]["formation"]=="4-3-3"

"""Tests for isolated finishing candidate. No production-model activation."""
import unittest
from dataclasses import dataclass
import pandas as pd
from fpl_v1_1_model.experimental_elite_finishing import (
    finishing_estimates, with_finishing_candidate,
)

@dataclass(frozen=True)
class Player:
    player_id: str
    goal_weight: float

@dataclass(frozen=True)
class Input:
    players: tuple

class FinishingTests(unittest.TestCase):
    def setUp(self):
        self.hist = pd.DataFrame([
            dict(player_uuid="star", known="2025-01-01T12:00:00Z", goals=12., xg=8.),
            dict(player_uuid="young", known="2025-01-01T12:00:00Z", goals=1., xg=0.5),
            dict(player_uuid="star", known="2026-12-01T12:00:00Z", goals=999., xg=1.),
        ])
        self.cut = "2026-10-16T12:00:00Z"

    def test_no_target_leakage(self):
        a = finishing_estimates(self.hist, self.cut, ["star", "young"])
        b = finishing_estimates(self.hist.iloc[:2], self.cut, ["star", "young"])
        self.assertEqual(a, b)

    def test_weak_history_shrunk_to_neutral(self):
        r = finishing_estimates(self.hist, self.cut, ["star", "young", "new"], cap=(0.5, 2.))
        self.assertGreater(r["star"]["factor"], 1)
        self.assertLess(r["young"]["factor"], 1.1)
        self.assertEqual(r["new"]["factor"], 1.)

    def test_missing_data_rejected(self):
        bad = self.hist.copy()
        bad.loc[0, "xg"] = float("nan")
        with self.assertRaises(ValueError):
            finishing_estimates(bad, self.cut, ["star"])

    def test_replacement_not_double_multiplier(self):
        inp = Input((Player("star", 1.2),))
        spec = {"finishing": True, "profiles": {
            "star": {"finishing": {"mean": 1.2}, "xg90": {"mean": 0.8}}
        }}
        new, updated = with_finishing_candidate(inp, spec, {
            "star": {"factor": 1.1}
        })
        self.assertAlmostEqual(new.players[0].goal_weight, 1.1)
        self.assertAlmostEqual(updated["profiles"]["star"]["finishing"]["mean"], 1.1)
        self.assertEqual(spec["profiles"]["star"]["finishing"]["mean"], 1.2)

if __name__ == "__main__":
    unittest.main()

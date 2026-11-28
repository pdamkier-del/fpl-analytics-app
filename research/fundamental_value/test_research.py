import unittest

import pandas as pd

from run import lineup, score, sell_price, snapshot, transfer_cost


class RulesTest(unittest.TestCase):
    def test_half_profit_and_full_loss(self):
        self.assertEqual(sell_price(50, 53), 51)
        self.assertEqual(sell_price(50, 51), 50)
        self.assertEqual(sell_price(50, 47), 47)

    def test_transfer_banking_and_hits(self):
        self.assertEqual(transfer_cost(0, 2, 2), (0, 2))
        self.assertEqual(transfer_cost(0, 2, 5), (0, 3))
        self.assertEqual(transfer_cost(2, 1, 5), (4, 1))
        self.assertEqual(transfer_cost(2, 3, 5), (0, 2))

    def test_substitutions_and_vice_respect_formation(self):
        positions = ["GK", "DEF", "DEF", "DEF", "MID", "MID", "MID", "MID",
                     "MID", "FWD", "FWD", "MID", "DEF", "GK"]
        info = {i: (pos, 1, 50) for i, pos in enumerate(positions)}
        actual = {i: (1, 90) for i in info}
        actual.update({0: (0, 0), 1: (0, 0), 5: (8, 90),
                       11: (12, 90), 12: (4, 90), 13: (2, 90)})
        self.assertEqual(score((tuple(range(11)), 1, 5, [11, 12, 13]),
                               actual, info), 30)

    def test_lineup_captain_and_legal_formation(self):
        positions = ["GK"]*2 + ["DEF"]*5 + ["MID"]*5 + ["FWD"]*3
        info = {i: (pos, 1, 50) for i, pos in enumerate(positions)}
        starters, captain, vice, bench = lineup(info, info, {i: i for i in info})
        self.assertEqual(len(starters), 11)
        self.assertEqual(captain, 14)
        self.assertEqual(vice, 13)
        self.assertEqual(len(bench), 4)
        self.assertGreaterEqual(sum(info[i][0] == "DEF" for i in starters), 3)

    def test_late_result_excluded_even_if_gameweek_label_is_old(self):
        rows = []
        for gw, kickoff, points in [(4, "2024-09-01", 3), (6, "2024-09-30", 99),
                                    (7, "2024-10-09", 200), (8, "2024-10-10", 300)]:
            rows.append(dict(GW=gw, kickoff=pd.Timestamp(kickoff, tz="UTC"),
                             fixture=gw, element=1, position="MID", club=1, value=55,
                             selected=5000, transfers_balance=1, minutes=90, starts=1,
                             xgi=.2, total_points=points, goals_scored=0, assists=0))
        raw = pd.DataFrame(rows)
        fixtures = pd.DataFrame({"id": [4, 6, 7, 8], "event": [4, 6, 7, 8],
                                 "team_a": [2]*4, "team_h": [1]*4,
                                 "team_h_score": [1]*4, "team_a_score": [0]*4})
        before = snapshot(raw, fixtures, 8, 4)
        raw.loc[raw.GW.ge(7), "total_points"] = 10000
        pd.testing.assert_frame_equal(before, snapshot(raw, fixtures, 8, 4))
        self.assertEqual(before.loc[1, "vintage"], 6)
        raw.loc[raw.GW.eq(6), "kickoff"] = pd.Timestamp("2024-10-09", tz="UTC")
        after = snapshot(raw, fixtures, 8, 4)
        self.assertEqual(after.loc[1, "vintage"], 4)


if __name__ == "__main__":
    unittest.main()

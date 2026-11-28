import unittest

import pandas as pd

from replay import extend


class ExtensionTests(unittest.TestCase):
    def test_fit_uses_only_past_issues(self):
        origin = pd.DataFrame({"id": [1], "gw": [15], "xpts_mean": [5.0], "p_play": [.8]})
        vintages = pd.DataFrame([
            dict(id=1, origin_gw=6, gw=12, xpts_mean=2.0),
            dict(id=1, origin_gw=7, gw=12, xpts_mean=3.0),
            dict(id=1, origin_gw=8, gw=14, xpts_mean=1.0),
            dict(id=1, origin_gw=9, gw=14, xpts_mean=9999.0),
        ])
        extended, n, factor = extend(origin, vintages, 10, 8, learn=True)
        self.assertEqual(n, 1)
        self.assertEqual(factor, 1.5)
        self.assertEqual(extended.gw.tolist(), [15, 16, 17])
        self.assertEqual(extended.xpts_mean.tolist(), [5.0, 7.5, 7.5])
        self.assertEqual(extended.p_play.tolist(), [.8, .8, .8])

    def test_extension_stops_at_season_end(self):
        origin = pd.DataFrame({"id": [1], "gw": [38], "xpts_mean": [5.0]})
        extended, n, factor = extend(origin, pd.DataFrame(), 35, 10, learn=True)
        pd.testing.assert_frame_equal(extended, origin)
        self.assertEqual((n, factor), (0, 1.0))


if __name__ == "__main__":
    unittest.main()

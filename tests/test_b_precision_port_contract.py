"""No-runtime smoke checks for the isolated precision helper.

These deliberately do not import the forecasting model or activate the publisher.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from b_simulation_precision import fixture_offset, resolution, NORMAL_DRAWS, PRECISE_DRAWS


class PrecisionPortContract(unittest.TestCase):
    def test_modes_and_budgets(self):
        self.assertEqual(NORMAL_DRAWS, 2000)
        self.assertEqual(PRECISE_DRAWS, 10000)
        self.assertEqual(resolution(), 2000)
        self.assertEqual(resolution("normal", 60), 2000)
        self.assertEqual(resolution("validation", 60), 10000)
        self.assertEqual(resolution("close", 60), 10000)
        for mode, count in [("close", 61), ("normal", 0), ("invalid", 3)]:
            with self.assertRaises(ValueError):
                resolution(mode, count)

    def test_offsets_stable_across_batch_order(self):
        f = fixture_offset("fixture-1", "2026-27")
        self.assertEqual(f, fixture_offset("fixture-1", "2026-27"))
        self.assertEqual(f, {x: fixture_offset(x, "2026-27") for x in ["fixture-2", "fixture-1"]}["fixture-1"])
        self.assertNotEqual(f, fixture_offset("fixture-1", "2025-26"))

    def test_summary_is_not_a_ts_scenario_payload(self):
        import inspect
        from b_simulation_precision import browser_summary
        self.assertIn("validate_forecast(forecast)", inspect.getsource(browser_summary))
        self.assertIn("canonical_forecast_sha256", inspect.getsource(browser_summary))


if __name__ == "__main__":
    unittest.main()

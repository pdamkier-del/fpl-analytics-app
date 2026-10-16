import unittest
from datetime import datetime, timezone
from scripts.research_role_injury_club_audit import Evidence, asof_status, club_error_report

def evidence(state, pub, cap=None, confidence="official"):
    return Evidence("p1","clubA","2026-10-01T00:00:00Z",pub,cap or pub,
                    "https://example.org/report","club",state,
                    confidence=confidence)

class InjuryRoleTests(unittest.TestCase):
    def test_never_look_ahead(self):
        rows=[evidence("OUT","2026-10-13T12:00:00Z"),
              evidence("AVAILABLE","2026-10-15T12:00:00Z")]
        self.assertEqual(asof_status(rows,"2026-10-14T11:00:00Z","p1")["state"],"OUT")
        self.assertEqual(asof_status(rows,"2026-10-16T11:00:00Z","p1")["state"],"AVAILABLE")

    def test_unknown_is_not_available(self):
        self.assertEqual(asof_status([],"2026-10-16T11:00:00Z","p1")["state"],"UNKNOWN")

    def test_same_clock_conflict_unknown(self):
        rows=[evidence("OUT","2026-10-13T12:00:00Z"),evidence("AVAILABLE","2026-10-13T12:00:00Z")]
        self.assertEqual(asof_status(rows,"2026-10-14T11:00:00Z","p1")["state"],"UNKNOWN")

    def test_late_capture_not_visible(self):
        row=evidence("OUT","2026-10-13T12:00:00Z","2026-10-16T12:00:00Z")
        self.assertEqual(asof_status([row],"2026-10-14T11:00:00Z","p1")["state"],"UNKNOWN")

    def test_team_audit_detects_regression(self):
        rows=[dict(season="25",club="A",player_uuid="p1",fixture_uuid="f1",
                   actual_minutes=90,baseline_minutes=85,candidate_minutes=60),
              dict(season="25",club="B",player_uuid="p2",fixture_uuid="f1",
                   actual_minutes=0,baseline_minutes=30,candidate_minutes=0)]
        out=club_error_report(rows)
        self.assertEqual(out[0]["club"],"A")
        self.assertAlmostEqual(out[0]["delta_mae"],25)
        self.assertEqual(out[1]["club"],"B")
        self.assertAlmostEqual(out[1]["delta_mae"],-30)

if __name__=="__main__":
    unittest.main()

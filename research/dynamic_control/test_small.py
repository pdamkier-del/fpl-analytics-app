import unittest
from pathlib import Path
from small import actions, exact_action, exact_solver, load_cases, beam_action, committed_value


class SmallReferences(unittest.TestCase):
    cases = {case.name: case for case in load_cases(Path(__file__).with_name("cases.json"))}

    def test_hand_values_and_choices(self):
        references = {
            "roll_for_two": (20, (0, 1)),
            "funding_bundle": (14, (2, 3)),
            "short_term_trap": (16, (0,)),
            "availability_shock": (33.2, (0, 3)),
            "bank_threshold": (6.5, (0,)),
            "value_of_adaptation": (17, (0,)),
        }
        for name, (points, squad) in references.items():
            with self.subTest(name=name):
                case = self.cases[name]
                v, q = exact_solver(case)
                self.assertAlmostEqual(v(0, case.initial), points)
                self.assertEqual(exact_action(case, 0, case.initial, q)[0], squad)

    def test_selling_irreversibility_and_discount(self):
        case = self.cases["short_term_trap"]
        _, after, _ = next(a for a in actions(case, 0, case.initial) if a[0] == (1,))
        self.assertNotIn((0,), [a[0] for a in actions(case, 1, after)])
        self.assertEqual(beam_action(case, 0, case.initial, 6, 8, .6)[0], (1,))

    def test_terminal_branch_recourse(self):
        case = self.cases["value_of_adaptation"]
        v, q = exact_solver(case)
        self.assertEqual(v(0, case.initial) - committed_value(case, case.initial, q), 4)
        self.assertEqual(beam_action(case, 0, case.initial, 2, 8)[0], (1,))
        self.assertEqual(beam_action(case, 0, case.initial, 1, 8, terminal=True)[0], (0,))


if __name__ == "__main__":
    unittest.main()

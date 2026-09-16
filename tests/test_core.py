import unittest
import numpy as np
from src.game import Count, advance
from scripts.audit_baseline import fit, metrics
from scripts.verify_join import bridge


class CoreTests(unittest.TestCase):
    def test_walk(self):
        self.assertEqual(advance(Count(3, 1), "ball").result, "walk")

    def test_strikeout(self):
        for event in ["whiff", "called_strike", "tipped_strike"]:
            self.assertEqual(advance(Count(1, 2), event).result, "strikeout")

    def test_two_strike_foul(self):
        self.assertEqual(advance(Count(2, 2), "foul"), Count(2, 2))

    def test_full_pa(self):
        c = Count()
        for e in ["ball", "called_strike", "foul", "foul", "whiff"]:
            c = advance(c, e)
        self.assertTrue(c.ended)
        self.assertEqual(c.result, "strikeout")

    def test_impossible(self):
        for b, s in [(4, 0), (0, 3), (-1, 0)]:
            with self.assertRaises(ValueError):
                Count(b, s)
        with self.assertRaises(ValueError):
            advance(Count(0, 0, True), "ball")
        with self.assertRaises(ValueError):
            advance(Count(), "unknown")

    def test_all_contacts_end(self):
        for e in [
            "out",
            "single",
            "double",
            "triple",
            "home_run",
            "reach_on_error",
            "fielders_choice",
        ]:
            self.assertTrue(advance(Count(), e).ended)

    def test_covariance_positive(self):
        m, c = fit(np.array([[1.0, 2.0]]), fit(np.array([[0.0, 0.0], [1.0, 1.0]])))
        self.assertTrue((np.linalg.eigvalsh(c) > 0).all())

    def test_sampling_reproducible(self):
        m, c = fit(np.array([[1.0, 2.0], [3.0, 4.0], [0.0, 2.0]]))
        np.testing.assert_array_equal(
            np.random.default_rng(8).multivariate_normal(m, c, 10),
            np.random.default_rng(8).multivariate_normal(m, c, 10),
        )

    def test_bridge_excludes_nonpitches(self):
        f = {
            "gamePk": 1,
            "liveData": {
                "plays": {
                    "allPlays": [
                        {
                            "about": {"atBatIndex": 2},
                            "playEvents": [
                                {"isPitch": False},
                                {"isPitch": True, "playId": "x", "pitchNumber": 1},
                            ],
                        }
                    ]
                }
            },
        }
        b = bridge(f)
        self.assertEqual(len(b), 1)
        self.assertEqual(b.iloc[0].at_bat_number, 3)


if __name__ == "__main__":
    unittest.main()

import unittest, time
import numpy as np
from src.engine import Engine


class EngineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.e = Engine()
        p = next(p for p in cls.e.players["pitchers"] if p["id"] == "656302")
        b = next(b for b in cls.e.players["hitters"] if b["id"] == "665489")
        cls.ctx = (p["id"], b["id"], "FF", 2, 1, 2, 1)

    def test_probability_mass_and_reproducibility(self):
        for mode in ["realistic", "perfect"]:
            a = self.e.evaluate(self.ctx, [0, 2.5], mode)
            b = self.e.evaluate(self.ctx, [0, 2.5], mode)
            self.assertAlmostEqual(sum(a["probabilities"].values()), 1, places=10)
            self.assertTrue(all(0 <= p <= 1 for p in a["probabilities"].values()))
            self.assertEqual(a, b)

    def test_perfect_is_exact(self):
        self.assertEqual(
            self.e.evaluate(self.ctx, [0.1, 2.6], "perfect")["locations"], [[0.1, 2.6]]
        )

    def test_realistic_has_variation(self):
        self.assertGreater(np.std(self.e.evaluate(self.ctx, [0, 2.5])["locations"]), 0)

    def test_surface_finite_and_repertoire(self):
        s = self.e.surface("656302", "665489", 2, 1, 2, 1)
        self.assertEqual(len(s), 99 * len(self.e.pitchers["656302"]["pitches"]))
        self.assertTrue(all(np.isfinite(r["realistic"]) for r in s))

    def test_hitter_target_interactions(self):
        ctx = list(self.ctx)
        ctx[1] = next(b["id"] for b in self.e.players["hitters"] if b["id"] != "665489")
        a = self.e.predict(self.ctx, np.array([[0, 2.5], [1, 3.5]]))["run_value"]
        b = self.e.predict(tuple(ctx), np.array([[0, 2.5], [1, 3.5]]))["run_value"]
        self.assertGreater(abs((a[1] - a[0]) - (b[1] - b[0])), 1e-8)

    def test_profiles_are_real_and_eligible(self):
        for p in self.e.players["pitchers"]:
            self.assertGreaterEqual(p["n"], 300)
            self.assertGreaterEqual(p["outings"], 10)
            for v in p["pitches"]:
                self.assertGreaterEqual(v["n"], 50)
                self.assertGreaterEqual(v["usage"], 0.02)
                self.assertGreaterEqual(v["command"]["n"], 30)


if __name__ == "__main__":
    unittest.main()

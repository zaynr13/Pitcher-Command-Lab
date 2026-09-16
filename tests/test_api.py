import unittest
from fastapi.testclient import TestClient
from src.api import app


class APITests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)
        cls.client.__enter__()

    @classmethod
    def tearDownClass(cls):
        cls.client.__exit__(None, None, None)

    def payload(self):
        return dict(
            pitcher="656302",
            hitter="665489",
            pitch="FF",
            balls=2,
            strikes=1,
            outs=2,
            bases=1,
            x=0,
            z=2.5,
            seed=123,
        )

    def test_full_api(self):
        p = self.payload()
        r = self.client.post("/api/throw", json=p)
        self.assertEqual(r.status_code, 200, r.text)
        self.assertEqual(r.json(), self.client.post("/api/throw", json=p).json())
        self.assertIn("event", r.json())

    def test_optimal_call_has_no_numerical_penalty(self):
        p = self.payload()
        s = self.client.post("/api/surface", json=p).json()
        best = s["best_realistic"]
        p.update(pitch=best["pitch"], x=best["target"][0], z=best["target"][1])
        r = self.client.post("/api/throw", json=p).json()
        self.assertLess(r["decision_loss"], 1e-10)

    def test_invalid_inputs(self):
        for change in [
            {"balls": 4},
            {"pitch": "KN"},
            {"pitcher": "0"},
            {"x": 5},
            {"mode": "other"},
        ]:
            self.assertEqual(
                self.client.post(
                    "/api/analyze", json={**self.payload(), **change}
                ).status_code,
                422,
            )

    def test_metadata(self):
        r = self.client.get("/api/players").json()
        self.assertEqual(
            next(p["name"] for p in r["pitchers"] if p["id"] == "656302"), "Dylan Cease"
        )
        self.assertEqual(len(r["pitchers"]), 365)


if __name__ == "__main__":
    unittest.main()

"""Reproduce bounded exploratory comparisons; no causal claims."""

import json, sys, time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.engine import Engine, ROOT
import numpy as np

E = Engine()
p = next(p for p in E.players["pitchers"] if p["name"] == "Dylan Cease")
h = next(p for p in E.players["hitters"] if p["name"] == "Vladimir Guerrero Jr.")
ctx = (p["id"], h["id"], "FF", 2, 1, 2, 1)
start = time.perf_counter()
a = E.evaluate(ctx, [0, 2.5])
analysis_ms = (time.perf_counter() - start) * 1000
start = time.perf_counter()
s = E.surface(p["id"], h["id"], 2, 1, 2, 1)
surface_ms = (time.perf_counter() - start) * 1000
s = [r for r in s if r["target_support"]["supported"]]
pr = min(s, key=lambda x: x["perfect"])
re = min(s, key=lambda x: x["realistic"])
r = {
    "example": {
        "pitcher": p["name"],
        "hitter": h["name"],
        "count": "2-1",
        "outs": 2,
        "bases": "first",
        "perfect_grid_optimum": pr,
        "realistic_grid_optimum": re,
        "target_distance_feet": float(
            np.linalg.norm(np.array(pr["target"]) - re["target"])
        ),
    },
    "timing_single_run_ms": {"analyze": analysis_ms, "uncached_surface": surface_ms},
    "scope": "One illustrative modeled matchup; not a population estimate, confidence interval, causal result, or held-out policy evaluation.",
}
(ROOT / "models/research-example.json").write_text(json.dumps(r, indent=2))
print(json.dumps(r, indent=2))

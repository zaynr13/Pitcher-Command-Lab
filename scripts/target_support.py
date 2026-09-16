"""Training-only observed target density at optimization candidates."""

import json, argparse
from pathlib import Path
import numpy as np, pandas as pd

ROOT = Path(__file__).resolve().parents[1]
ap = argparse.ArgumentParser()
ap.add_argument("--data", type=Path, required=True)
a = ap.parse_args()
t = pd.read_csv(a.data / "targets-2025.csv.gz")
p = pd.read_csv(
    a.data / "pbp-2025.csv.gz",
    usecols=["game_pk", "play_id", "pitcher_id", "pitch_type", "date", "game_type"],
)
d = t.merge(p, on=["game_pk", "play_id"], validate="one_to_one")
d = d[d.plausible.eq(True) & d.game_type.eq("R") & (d.date < "2025-07-01")]
grid = np.array(
    [(x, z) for z in np.linspace(0.75, 4.25, 11) for x in np.linspace(-1.5, 1.5, 9)]
)
out = {}
for (pid, pt), g in d.groupby(["pitcher_id", "pitch_type"]):
    xy = g[["naive_x_in", "naive_z_in"]].to_numpy() / 12
    out[f"{pid}:{pt}"] = (
        (np.sum((grid[:, None, :] - xy[None, :, :]) ** 2, axis=2) <= 0.5**2)
        .sum(axis=1)
        .tolist()
    )
(ROOT / "models/target-support.json").write_text(
    json.dumps(
        {
            "radius_feet": 0.5,
            "minimum_observations": 20,
            "grid": grid.tolist(),
            "cells": out,
        }
    )
)
print("Target support cells", len(out))

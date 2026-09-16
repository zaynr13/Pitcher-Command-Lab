"""Reproduce season coverage checks independently of model training."""

import argparse, json
from pathlib import Path
import pandas as pd

ap = argparse.ArgumentParser()
ap.add_argument("--data", type=Path, required=True)
ap.add_argument("--year", type=int, required=True)
ap.add_argument("--out", type=Path, required=True)
a = ap.parse_args()
t = pd.read_csv(a.data / f"targets-{a.year}.csv.gz")
p = pd.read_csv(a.data / f"pbp-{a.year}.csv.gz")
d = t.merge(p, on=["game_pk", "play_id"], validate="one_to_one")
u = d[d.plausible.eq(True) & d.game_type.eq("R")]
r = {
    "year": a.year,
    "targets": len(t),
    "pitches": len(p),
    "joined": len(d),
    "usable_regular": len(u),
    "pitchers": int(u.pitcher_id.nunique()),
    "hitters": int(u.batter_id.nunique()),
    "fields": list(t.columns),
}
a.out.write_text(json.dumps(r, indent=2))
print(json.dumps(r, indent=2))

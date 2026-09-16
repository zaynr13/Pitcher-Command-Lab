"""Held-out command coverage by pitch, support, pitcher and park."""

import sys, json, argparse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import numpy as np, pandas as pd
from scripts.audit_baseline import fit, metrics

ROOT = Path(__file__).resolve().parents[1]
ap = argparse.ArgumentParser()
ap.add_argument("--data", type=Path, required=True)
a = ap.parse_args()
t = pd.read_csv(a.data / "targets-2025.csv.gz")
p = pd.read_csv(a.data / "pbp-2025.csv.gz")
d = t.merge(p, on=["game_pk", "play_id"], validate="one_to_one")
d = d[d.plausible.eq(True) & d.game_type.eq("R")].dropna(
    subset=["naive_x_in", "naive_z_in", "plate_x_in", "plate_z_in"]
)
d["cell"] = d.pitcher_id.astype(str) + ":" + d.pitch_type
tr = d[d.date < "2025-07-01"]
te = d[d.date >= "2025-08-01"].copy()
cells = json.loads((ROOT / "models/command-baseline.json").read_text())["cells"]
errors = (
    tr[["plate_x_in", "plate_z_in"]].to_numpy()
    - tr[["naive_x_in", "naive_z_in"]].to_numpy()
)
league = fit(errors)
groups = {
    pt: fit(
        g[["plate_x_in", "plate_z_in"]].to_numpy()
        - g[["naive_x_in", "naive_z_in"]].to_numpy(),
        league,
        100,
    )
    for pt, g in tr.groupby("pitch_type")
}
chosen = [cells.get(c) for c in te.cell]
means = []
cov = []
n = []
for c, pt in zip(chosen, te.pitch_type):
    if c:
        means.append(c["mean"])
        cov.append(c["covariance"])
        n.append(c["n"])
    else:
        m, v = groups.get(pt, league)
        means.append(m)
        cov.append(v)
        n.append(0)
e = (
    te[["plate_x_in", "plate_z_in"]].to_numpy()
    - te[["naive_x_in", "naive_z_in"]].to_numpy()
)
r = e - np.array(means)
cov = np.array(cov)
dist = np.einsum("ni,nij,nj->n", r, np.linalg.inv(cov), r)
te["in80"] = dist <= -2 * np.log(0.2)
te["in50"] = dist <= -2 * np.log(0.5)
te["nll"] = np.log(2 * np.pi) + 0.5 * np.linalg.slogdet(cov)[1] + 0.5 * dist
te["support"] = pd.cut(
    n, [-1, 29, 149, 599, np.inf], labels=["unavailable", "limited", "medium", "high"]
)
report = {}
for key in ["pitch_type", "support", "pitcher_id", "park"]:
    g = te.groupby(key, observed=True).agg(
        n=("in80", "size"),
        coverage80=("in80", "mean"),
        coverage50=("in50", "mean"),
        nll=("nll", "mean"),
    )
    g = g[g.n >= 200]
    report[key] = {
        str(idx): {c: int(row[c]) if c == "n" else float(row[c]) for c in g.columns}
        for idx, row in g.iterrows()
    }
report["note"] = (
    "Descriptive held-out subgroup diagnostics, minimum 200 test observations. Repeated diagnostics are developmental. Pitch observations cluster within games; binomial intervals would overstate precision."
)
(ROOT / "models/subgroup-validation.json").write_text(json.dumps(report, indent=2))
print("Pitch coverage", report["pitch_type"])
print("Support coverage", report["support"])
print(
    "Pitcher range",
    min(x["coverage80"] for x in report["pitcher_id"].values()),
    max(x["coverage80"] for x in report["pitcher_id"].values()),
)

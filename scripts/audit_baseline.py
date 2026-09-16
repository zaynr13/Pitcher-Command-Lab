"""Audit actual OpenCommand exports and temporally evaluate a pooled command baseline."""

import argparse, hashlib, json
from pathlib import Path
import numpy as np
import pandas as pd


def fit(errors, prior=None, strength=100):
    n = len(errors)
    mean = errors.mean(0)
    second = errors.T @ errors / n
    if prior is not None:
        mean = (n * mean + strength * prior[0]) / (n + strength)
        second = (n * second + strength * (prior[1] + np.outer(prior[0], prior[0]))) / (
            n + strength
        )
    return mean, second - np.outer(mean, mean) + np.eye(2) * 1e-4


def metrics(e, means, covs):
    r = e - means
    inv = np.linalg.inv(covs)
    d = np.einsum("ni,nij,nj->n", r, inv, r)
    return dict(
        n=len(e),
        rmse_x_inches=float(np.sqrt(np.mean(r[:, 0] ** 2))),
        rmse_z_inches=float(np.sqrt(np.mean(r[:, 1] ** 2))),
        negative_log_likelihood=float(
            np.mean(np.log(2 * np.pi) + 0.5 * np.linalg.slogdet(covs)[1] + 0.5 * d)
        ),
        coverage_50=float(np.mean(d <= -2 * np.log(0.5))),
        coverage_80=float(np.mean(d <= -2 * np.log(0.2))),
    )


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args()
    a.out.mkdir(parents=True, exist_ok=True)
    t = pd.read_csv(a.data / "targets-2025.csv.gz")
    p = pd.read_csv(a.data / "pbp-2025.csv.gz")
    keys = ["game_pk", "play_id"]
    assert not t.duplicated(keys).any() and not p.duplicated(keys).any()
    d = t.merge(p, on=keys, how="left", validate="one_to_one", indicator=True)
    mask = (d["_merge"] == "both") & d["plausible"].eq(True) & d.game_type.eq("R")
    mask &= np.isfinite(
        d[["naive_x_in", "naive_z_in", "plate_x_in", "plate_z_in"]]
    ).all(axis=1)
    u = d.loc[mask].copy()
    u["ex"] = u.plate_x_in - u.naive_x_in
    u["ez"] = u.plate_z_in - u.naive_z_in
    u["cell"] = u.pitcher_id.astype(str) + ":" + u.pitch_type.astype(str)
    train = u[u.date < "2025-07-01"]
    valid = u[(u.date >= "2025-07-01") & (u.date < "2025-08-01")]
    test = u[u.date >= "2025-08-01"]
    e = train[["ex", "ez"]].to_numpy()
    global_fit = fit(e)
    groups = {
        k: fit(g[["ex", "ez"]].to_numpy(), global_fit, 100)
        for k, g in train.groupby("pitch_type")
    }

    def evaluate(frame, strength):
        cells = {
            k: fit(g[["ex", "ez"]].to_numpy(), groups[g.pitch_type.iloc[0]], strength)
            for k, g in train.groupby("cell")
        }
        choices = [
            cells.get(row.cell, groups.get(row.pitch_type, global_fit))
            for row in frame.itertuples()
        ]
        return (
            metrics(
                frame[["ex", "ez"]].to_numpy(),
                np.array([v[0] for v in choices]),
                np.array([v[1] for v in choices]),
            ),
            cells,
        )

    tuning = {str(s): evaluate(valid, s)[0] for s in [50, 100, 300, 1000]}
    strength = int(min(tuning, key=lambda s: tuning[s]["negative_log_likelihood"]))
    final, cells = evaluate(test, strength)
    baseline = metrics(
        test[["ex", "ez"]].to_numpy(),
        np.repeat(global_fit[0][None, :], len(test), 0),
        np.repeat(global_fit[1][None, :, :], len(test), 0),
    )
    pitchbaseline = [groups.get(x, global_fit) for x in test.pitch_type]
    pbmetrics = metrics(
        test[["ex", "ez"]].to_numpy(),
        np.array([x[0] for x in pitchbaseline]),
        np.array([x[1] for x in pitchbaseline]),
    )
    pc = u.groupby("pitcher_id").agg(
        pitches=("play_id", "size"), outings=("game_pk", "nunique")
    )
    hc = u.groupby("batter_id").size()
    report = {
        "status": "command baseline only; not production validated",
        "source_files": {
            f: {"sha256": hashlib.sha256((a.data / f).read_bytes()).hexdigest()}
            for f in ["targets-2025.csv.gz", "pbp-2025.csv.gz"]
        },
        "target_fields": list(t.columns),
        "pbp_fields": list(p.columns),
        "target_rows": len(t),
        "pbp_rows": len(p),
        "matched_targets": int((d["_merge"] == "both").sum()),
        "usable_regular_season": len(u),
        "unique_pitchers": int(u.pitcher_id.nunique()),
        "unique_hitters": int(u.batter_id.nunique()),
        "date_range": [u.date.min(), u.date.max()],
        "missing_fraction": d.drop(columns="_merge").isna().mean().to_dict(),
        "pitch_types": u.pitch_type.value_counts().to_dict(),
        "pitcher_threshold_sensitivity": {
            str(n): int(((pc.pitches >= n) & (pc.outings >= 10)).sum())
            for n in [300, 500, 750, 1000]
        },
        "hitter_pitches_seen_sensitivity": {
            str(n): int((hc >= n).sum()) for n in [500, 750, 1000, 1500]
        },
        "coordinate_max_difference_inches": float(
            np.max(
                np.abs(
                    u[["plate_x_in", "plate_z_in"]].to_numpy()
                    - 12 * u[["plate_x", "plate_z"]].to_numpy()
                )
            )
        ),
        "split": {
            "train_before": "2025-07-01",
            "validation_before": "2025-08-01",
            "test_after_inclusive": "2025-08-01",
            "train_n": len(train),
            "validation_n": len(valid),
            "test_n": len(test),
        },
        "tuning": tuning,
        "selected_prior_strength": strength,
        "test": {
            "league": baseline,
            "pitch_type": pbmetrics,
            "pitcher_pitch_type": final,
        },
        "limitations": [
            "Naive glove target is a noisy proxy, not intended target ground truth.",
            "Camera reconstruction uses observed trajectories; measurement error may be correlated with realized location.",
            "Published inferred targets explicitly excluded: upstream infer_targets(a,a) fits in-sample.",
            "No hitter model, Statcast join validation, or full product acceptance established by this report.",
        ],
    }
    (a.out / "audit.json").write_text(json.dumps(report, indent=2, allow_nan=False))
    artifact = {
        "target_definition": "naive glove target in inches",
        "trained_before": "2025-07-01",
        "prior_strength": strength,
        "cells": {
            k: {
                "mean": v[0].tolist(),
                "covariance": v[1].tolist(),
                "n": int((train.cell == k).sum()),
            }
            for k, v in cells.items()
        },
    }
    (a.out / "command-baseline.json").write_text(json.dumps(artifact, allow_nan=False))
    print(
        json.dumps(
            {
                k: report[k]
                for k in [
                    "target_rows",
                    "pbp_rows",
                    "matched_targets",
                    "usable_regular_season",
                    "unique_pitchers",
                    "unique_hitters",
                    "pitcher_threshold_sensitivity",
                    "hitter_pitches_seen_sensitivity",
                    "test",
                ]
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()

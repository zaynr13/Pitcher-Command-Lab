"""Chronological train/selection/test with player-agnostic comparisons."""

import argparse, json, sys, time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import joblib, numpy as np, pandas as pd
from sklearn.linear_model import LogisticRegression, Ridge
from sklearn.metrics import (
    log_loss,
    mean_squared_error,
    mean_absolute_error,
    roc_auc_score,
)
from src.modeling import (
    features,
    preprocessor,
    labels,
    NUM,
    CAT,
    PLAYERS,
    BoundedRegressor,
)


def evaluate_classifier(model, x, y):
    p = model.predict_proba(x)
    classes = model.classes_
    one = np.array([y.to_numpy() == c for c in classes]).T
    conf = p.max(1)
    correct = classes[p.argmax(1)] == y.to_numpy()
    bins = []
    for lo in np.arange(0, 1, 0.1):
        m = (conf >= lo) & (conf < lo + 0.1)
        if m.any():
            bins.append(
                {
                    "n": int(m.sum()),
                    "predicted": float(conf[m].mean()),
                    "observed": float(correct[m].mean()),
                }
            )
    r = {
        "n": len(y),
        "log_loss": float(log_loss(y, p, labels=classes)),
        "brier_multiclass": float(np.mean(np.sum((p - one) ** 2, axis=1))),
        "top_label_ece": float(
            sum(b["n"] * abs(b["predicted"] - b["observed"]) for b in bins) / len(y)
        ),
        "calibration": bins,
    }
    if len(classes) == 2:
        r["roc_auc"] = float(roc_auc_score(y, p[:, 1]))
    return r


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args()
    a.out.mkdir(parents=True, exist_ok=True)
    cols = (
        NUM
        + CAT
        + PLAYERS
        + [
            "sz_top",
            "sz_bot",
            "game_pk",
            "at_bat_number",
            "pitch_number",
            "game_date",
            "game_type",
            "description",
            "events",
            "launch_speed",
            "launch_angle",
            "estimated_woba_using_speedangle",
            "delta_run_exp",
            "player_name",
        ]
    )
    d = pd.concat(
        [
            pd.read_csv(p, usecols=lambda c: c in cols, low_memory=False)
            for p in sorted(a.data.glob("statcast-*.csv"))
        ],
        ignore_index=True,
    )
    d = d[d.game_type.eq("R")].drop_duplicates(
        ["game_pk", "at_bat_number", "pitch_number"]
    )
    d = d[d.plate_x.notna() & d.plate_z.notna() & d.pitch_type.notna()].copy()
    # IDs must stay identical across train and API.
    for c in PLAYERS:
        d[c] = d[c].astype("int64").astype(str)
    tr = d.game_date < "2025-07-01"
    va = (d.game_date >= "2025-07-01") & (d.game_date < "2025-08-01")
    te = d.game_date >= "2025-08-01"
    x = features(d)
    report = {
        "rows": len(d),
        "splits": {
            "train": int(tr.sum()),
            "validation": int(va.sum()),
            "test": int(te.sum()),
        },
        "models": {},
    }
    bundle = {"models": {}, "preprocessors": {}}
    matrices = {}
    for players in [False, True]:
        name = "player" if players else "agnostic"
        pre = preprocessor(players)
        matrices[name] = (
            pre.fit_transform(x[tr]),
            pre.transform(x[va]),
            pre.transform(x[te]),
        )
        bundle["preprocessors"][name] = pre
    for kind in ["swing", "called", "contact", "hit"]:
        y, mask = labels(d, kind)
        runs = {}
        candidates = {}
        for name in matrices:
            xt, xv, xe = matrices[name]
            mt = mask[tr].to_numpy()
            mv = mask[va].to_numpy()
            me = mask[te].to_numpy()
            model = LogisticRegression(C=0.3, max_iter=1500, solver="lbfgs", tol=1e-4)
            start = time.time()
            model.fit(xt[mt], y[tr & mask])
            v = evaluate_classifier(model, xv[mv], y[va & mask])
            test = evaluate_classifier(model, xe[me], y[te & mask])
            runs[name] = {"validation": v, "test": test}
            candidates[name] = model
            print(
                kind,
                name,
                "seconds",
                round(time.time() - start, 1),
                "test loss",
                test["log_loss"],
                flush=True,
            )
        selected = min(runs, key=lambda n: runs[n]["validation"]["log_loss"])
        report["models"][kind] = {"selected": selected, **runs}
        bundle["models"][kind] = {
            "preprocessor": selected,
            "model": candidates[selected],
        }
    for kind, col in [
        ("exit_velocity", "launch_speed"),
        ("launch_angle", "launch_angle"),
        ("xwoba", "estimated_woba_using_speedangle"),
        ("run_value", "delta_run_exp"),
    ]:
        y = d[col]
        mask = y.notna()
        if kind != "run_value":
            mask &= d.description.eq("hit_into_play")
        runs = {}
        candidates = {}
        for name in matrices:
            xt, xv, xe = matrices[name]
            model = Ridge(alpha=300, solver="lsqr")
            model.fit(xt[mask[tr]], y[tr & mask])
            model = BoundedRegressor(
                model, float(y[tr & mask].min()), float(y[tr & mask].max())
            )
            v = model.predict(xv[mask[va]])
            pred = model.predict(xe[mask[te]])
            base = float(y[tr & mask].mean())
            runs[name] = {
                "validation_rmse": float(np.sqrt(mean_squared_error(y[va & mask], v))),
                "test": {
                    "n": int((te & mask).sum()),
                    "rmse": float(np.sqrt(mean_squared_error(y[te & mask], pred))),
                    "mae": float(mean_absolute_error(y[te & mask], pred)),
                    "mean_baseline_rmse": float(
                        np.sqrt(
                            mean_squared_error(y[te & mask], np.repeat(base, len(pred)))
                        )
                    ),
                },
            }
            candidates[name] = model
        selected = min(runs, key=lambda n: runs[n]["validation_rmse"])
        report["models"][kind] = {"selected": selected, **runs}
        bundle["models"][kind] = {
            "preprocessor": selected,
            "model": candidates[selected],
        }
        print(kind, runs[selected], flush=True)
    joblib.dump(bundle, a.out / "response.joblib", compress=3)
    (a.out / "response-validation.json").write_text(
        json.dumps(report, indent=2, allow_nan=False)
    )
    # All serving profiles use training observations, never realized physics from test pitches.
    train = d[tr]
    profiles = []
    command = json.loads((a.out / "command-baseline.json").read_text())["cells"]
    for pid, g in train.groupby("pitcher"):
        if len(g) < 300 or g.game_pk.nunique() < 10:
            continue
        pitches = []
        for pt, h in g.groupby("pitch_type"):
            key = f"{pid}:{pt}"
            cmd = command.get(key)
            if len(h) < 50 or len(h) / len(g) < 0.02 or cmd is None or cmd["n"] < 30:
                continue
            physical = {
                c: float(h[c].median())
                for c in [
                    "release_speed",
                    "pfx_x",
                    "pfx_z",
                    "release_spin_rate",
                    "release_extension",
                ]
                if h[c].notna().any()
            }
            pitches.append(
                {
                    "type": pt,
                    "mean_velocity": float(h.release_speed.mean()),
                    "usage": len(h) / len(g),
                    "n": len(h),
                    "physics": physical,
                    "command": cmd,
                }
            )
        if pitches:
            profiles.append(
                {
                    "id": pid,
                    "name": f"MLB {pid}",
                    "hand": str(g.p_throws.mode().iloc[0]),
                    "n": len(g),
                    "outings": int(g.game_pk.nunique()),
                    "pitches": pitches,
                }
            )
    hitters = []
    for bid, g in train.groupby("batter"):
        if (
            len(g) < 500
            or g[["game_pk", "at_bat_number"]].drop_duplicates().shape[0] < 100
        ):
            continue
        hitters.append(
            {
                "id": bid,
                "name": f"MLB {bid}",
                "hand": str(g.stand.mode().iloc[0]),
                "switch": g.stand.nunique() > 1,
                "n": len(g),
                "pa": int(g[["game_pk", "at_bat_number"]].drop_duplicates().shape[0]),
                "zone_top": float(g.sz_top.median()),
                "zone_bottom": float(g.sz_bot.median()),
            }
        )
    (a.out / "players.json").write_text(
        json.dumps(
            {"pitchers": profiles, "hitters": hitters, "profile_cutoff": "2025-07-01"},
            allow_nan=False,
        )
    )
    print("Serving coverage", len(profiles), len(hitters), flush=True)


if __name__ == "__main__":
    main()

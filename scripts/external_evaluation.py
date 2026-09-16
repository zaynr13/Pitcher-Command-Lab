"""Once-only external window evaluation after model selection. No refitting."""

import sys, json, hashlib, argparse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import joblib, numpy as np, pandas as pd
from sklearn.metrics import mean_squared_error, mean_absolute_error
from src.modeling import features, labels, NUM, CAT, PLAYERS
from scripts.train_hitter import evaluate_classifier

ROOT = Path(__file__).resolve().parents[1]


def to_front(d):
    """Savant 2026 mid-plane -> front-plane, using the 9-parameter trajectory velocities."""
    vy = d.vy0.to_numpy()
    ay = d.ay.to_numpy()

    def t(y):
        distance = 50 - y
        disc = vy * vy - 2 * ay * distance
        return 2 * distance / (-vy + np.sqrt(disc))

    front = t(17 / 12)
    middle = t(17 / 24)
    x = (
        d.plate_x.to_numpy()
        + d.vx0.to_numpy() * (front - middle)
        + 0.5 * d.ax.to_numpy() * (front**2 - middle**2)
    )
    z = (
        d.plate_z.to_numpy()
        + d.vz0.to_numpy() * (front - middle)
        + 0.5 * d.az.to_numpy() * (front**2 - middle**2)
    )
    out = d.copy()
    out["plate_x"] = x
    out["plate_z"] = z
    return out


def paired_game_bootstrap(d, y, a, b):
    # Positive means a has lower MSE than b. Resample complete games.
    z = (
        pd.DataFrame({"game": d.game_pk, "gain": (y - b) ** 2 - (y - a) ** 2, "n": 1})
        .groupby("game")
        .agg({"gain": "sum", "n": "sum"})
    )
    rng = np.random.default_rng(1729)
    idx = rng.integers(0, len(z), size=(1000, len(z)))
    diff = z.gain.to_numpy()[idx].sum(1) / z.n.to_numpy()[idx].sum(1)
    return {
        "games": len(z),
        "mean_mse_reduction": float(z.gain.sum() / z.n.sum()),
        "bootstrap_95_interval": np.quantile(diff, [0.025, 0.975]).tolist(),
        "replicates": 1000,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", type=Path, required=True)
    a = ap.parse_args()
    path = ROOT / "models/response.joblib"
    bundle = joblib.load(path)
    old = joblib.load(ROOT / "models/response-linear.joblib")
    cols = (
        NUM
        + CAT
        + PLAYERS
        + [
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
            "vx0",
            "vy0",
            "vz0",
            "ax",
            "ay",
            "az",
        ]
    )
    d = pd.concat(
        [
            pd.read_csv(p, usecols=cols, low_memory=False)
            for p in sorted(a.data.glob("statcast-*.csv"))
        ],
        ignore_index=True,
    )
    d = (
        d[d.game_type.eq("R")]
        .drop_duplicates(["game_pk", "at_bat_number", "pitch_number"])
        .dropna(
            subset=[
                "plate_x",
                "plate_z",
                "vx0",
                "vy0",
                "vz0",
                "ax",
                "ay",
                "az",
                "pitch_type",
            ]
        )
        .copy()
    )
    for c in PLAYERS:
        d[c] = d[c].astype("int64").astype(str)
    harmonized = to_front(d)
    x = features(harmonized)
    report = {
        "model_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "dates": [d.game_date.min(), d.game_date.max()],
        "n": len(d),
        "games": int(d.game_pk.nunique()),
        "coordinate_shift_mean_inches": {
            "x": float(((harmonized.plate_x - d.plate_x) * 12).mean()),
            "z": float(((harmonized.plate_z - d.plate_z) * 12).mean()),
        },
        "models": {},
        "scope": "Previously unused 12-day external window. Conditional response evaluation uses observed physics; not end-to-end target-policy validation. ABS/behavior changes remain after coordinate conversion.",
    }
    matrices = {key: pre.transform(x) for key, pre in bundle["preprocessors"].items()}
    for kind in ["swing", "called", "contact", "hit"]:
        y, m = labels(d, kind)
        entry = bundle["models"][kind]
        report["models"][kind] = evaluate_classifier(
            entry["model"], matrices[entry["preprocessor"]][m], y[m]
        )
    for kind, col in [
        ("exit_velocity", "launch_speed"),
        ("launch_angle", "launch_angle"),
        ("xwoba", "estimated_woba_using_speedangle"),
        ("run_value", "delta_run_exp"),
    ]:
        m = d[col].notna()
        if kind != "run_value":
            m &= d.description.eq("hit_into_play")
        entry = bundle["models"][kind]
        pred = entry["model"].predict(matrices[entry["preprocessor"]][m])
        y = d.loc[m, col].to_numpy()
        r = {
            "n": int(m.sum()),
            "rmse": float(np.sqrt(mean_squared_error(y, pred))),
            "mae": float(mean_absolute_error(y, pred)),
        }
        report["models"][kind] = r
        if kind == "run_value":
            prior = old["models"][kind]
            bp = prior["model"].predict(
                old["preprocessors"][prior["preprocessor"]].transform(x[m])
            )
            r["linear_baseline_rmse"] = float(np.sqrt(mean_squared_error(y, bp)))
            r["paired_game_bootstrap"] = paired_game_bootstrap(d[m], y, pred, bp)
    out = ROOT / "models/external-validation.json"
    if out.exists():
        raise RuntimeError(
            "External report already exists; preserve it and explicitly version any repeated evaluation"
        )
    out.write_text(json.dumps(report, indent=2, allow_nan=False))
    print(json.dumps({k: v for k, v in report.items() if k != "models"}, indent=2))
    print(
        json.dumps(
            {
                k: {a: b for a, b in v.items() if a != "calibration"}
                for k, v in report["models"].items()
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()

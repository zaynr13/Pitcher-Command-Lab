"""One fitted response chain powers game play and analytical surfaces."""

import json
from functools import lru_cache
from pathlib import Path
import joblib, numpy as np, pandas as pd
from src.modeling import features

ROOT = Path(__file__).resolve().parents[1]


class Engine:
    def __init__(self):
        self.bundle = joblib.load(ROOT / "models/response.joblib")
        self.target_support = (
            json.loads((ROOT / "models/target-support.json").read_text())
            if (ROOT / "models/target-support.json").exists()
            else None
        )
        self.subgroups = (
            json.loads((ROOT / "models/subgroup-validation.json").read_text())
            if (ROOT / "models/subgroup-validation.json").exists()
            else None
        )
        self.players = json.loads((ROOT / "models/players.json").read_text())
        self.pitchers = {p["id"]: p for p in self.players["pitchers"]}
        self.hitters = {p["id"]: p for p in self.players["hitters"]}

    def profile(self, pid, pt):
        return next(p for p in self.pitchers[pid]["pitches"] if p["type"] == pt)

    def frame(self, pid, bid, pt, balls, strikes, outs, bases, locations):
        pitch = self.profile(pid, pt)
        p = self.pitchers[pid]
        b = self.hitters[bid]
        stand = ("L" if p["hand"] == "R" else "R") if b["switch"] else b["hand"]
        row = {
            **pitch["physics"],
            "pitch_type": pt,
            "pitcher": pid,
            "batter": bid,
            "p_throws": p["hand"],
            "stand": stand,
            "balls": balls,
            "strikes": strikes,
            "outs_when_up": outs,
            **{f"on_{i}b": int(bool(bases & (1 << (i - 1)))) for i in [1, 2, 3]},
        }
        df = pd.DataFrame([row] * len(locations))
        df["plate_x"] = locations[:, 0]
        df["plate_z"] = locations[:, 1]
        for c in [
            "release_speed",
            "pfx_x",
            "pfx_z",
            "release_spin_rate",
            "release_extension",
        ]:
            if c not in df:
                df[c] = np.nan
        return features(df)

    def predict(self, context, locations):
        x = self.frame(*context, locations)
        trans = {}
        out = {}
        for kind, entry in self.bundle["models"].items():
            key = entry["preprocessor"]
            if key not in trans:
                trans[key] = self.bundle["preprocessors"][key].transform(x)
            model = entry["model"]
            if hasattr(model, "predict_proba"):
                probs = model.predict_proba(trans[key])
                out[kind] = {str(c): probs[:, i] for i, c in enumerate(model.classes_)}
            else:
                out[kind] = model.predict(trans[key])
        return out

    def errors(self, pid, pt, n, seed):
        c = self.profile(pid, pt)["command"]
        return (
            np.random.default_rng(seed).multivariate_normal(
                c["mean"], c["covariance"], size=n
            )
            / 12
        )

    def support(self, pid, pt, target):
        if self.target_support is None:
            return {"n": 0, "supported": False, "note": "Target support unavailable"}
        grid = np.array(self.target_support["grid"])
        i = int(np.argmin(np.sum((grid - np.array(target)) ** 2, axis=1)))
        n = self.target_support["cells"].get(f"{pid}:{pt}", [0] * len(grid))[i]
        return {
            "n": n,
            "supported": n >= self.target_support["minimum_observations"],
            "reference_target": grid[i].tolist(),
            "radius_feet": self.target_support["radius_feet"],
            "note": "Count within 0.5 ft of the nearest candidate target, not a confidence interval.",
        }

    def evaluate(self, context, target, mode="realistic", n=256):
        loc = np.array(target)[None, :] + (
            self.errors(context[0], context[2], n, 1729)
            if mode == "realistic"
            else np.zeros((1, 2))
        )
        p = self.predict(context, loc)
        s = p["swing"]["1"]
        c = p["called"]["1"]
        probs = {
            "ball": float(np.mean((1 - s) * (1 - c))),
            "called_strike": float(np.mean((1 - s) * c)),
        }
        for k, v in p["contact"].items():
            if k != "in_play":
                probs[k] = float(np.mean(s * v))
        for k, v in p["hit"].items():
            probs[k] = float(np.mean(s * p["contact"]["in_play"] * v))
        rv = p["run_value"]
        return {
            "target_support": self.support(context[0], context[2], target),
            "probabilities": probs,
            "swing": float(s.mean()),
            "whiff_given_swing": float(
                np.mean(s * p["contact"]["whiff"]) / max(s.mean(), 1e-9)
            ),
            "run_value": float(rv.mean()),
            "integration_se": (
                float(rv.std(ddof=1) / np.sqrt(len(rv))) if len(rv) > 1 else 0.0
            ),
            "exit_velocity_given_in_play": float(
                np.average(
                    p["exit_velocity"],
                    weights=np.maximum(s * p["contact"]["in_play"], 1e-12),
                )
            ),
            "xwoba_given_in_play": float(
                np.average(
                    p["xwoba"], weights=np.maximum(s * p["contact"]["in_play"], 1e-12)
                )
            ),
            "locations": loc[:128].tolist(),
        }

    @lru_cache(maxsize=24)
    def surface(self, pid, bid, balls, strikes, outs, bases):
        # 99 candidates per pitch, common random numbers reduce comparison noise.
        targets = np.array(
            [
                (x, z)
                for z in np.linspace(0.75, 4.25, 11)
                for x in np.linspace(-1.5, 1.5, 9)
            ]
        )
        entries = []
        for pitch in self.pitchers[pid]["pitches"]:
            pt = pitch["type"]
            ctx = (pid, bid, pt, balls, strikes, outs, bases)
            err = self.errors(pid, pt, 64, 1729)
            loc = (targets[:, None, :] + err[None, :, :]).reshape(-1, 2)
            p = self.predict(ctx, loc)
            perfect = self.predict(ctx, targets)
            rv = p["run_value"].reshape(len(targets), -1)
            sw = p["swing"]["1"].reshape(len(targets), -1)
            wh = p["contact"]["whiff"].reshape(len(targets), -1)
            for i, t in enumerate(targets):
                entries.append(
                    {
                        "target_support": self.support(pid, pt, t),
                        "pitch": pt,
                        "target": t.tolist(),
                        "realistic": float(rv[i].mean()),
                        "perfect": float(perfect["run_value"][i]),
                        "swing": float(sw[i].mean()),
                        "whiff": float(np.sum(sw[i] * wh[i]) / max(sw[i].sum(), 1e-9)),
                        "execution_sd": float(rv[i].std()),
                        "integration_se": float(rv[i].std(ddof=1) / 8),
                    }
                )
        return entries

"""Compare nonlinear value baselines on July, retaining all development results."""

import sys, json, time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import numpy as np, pandas as pd, joblib
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.model_selection import GroupKFold
from sklearn.linear_model import Ridge
from sklearn.preprocessing import OrdinalEncoder
from sklearn.compose import ColumnTransformer
from sklearn.pipeline import FeatureUnion
from sklearn.metrics import mean_squared_error, mean_absolute_error
from src.modeling import (
    NUM,
    CAT,
    PLAYERS,
    features,
    BoundedRegressor,
    LinearPlusTree,
    StackedValue,
)

ROOT = Path(__file__).resolve().parents[1]


def main():
    import argparse

    ap = argparse.ArgumentParser()
    ap.add_argument("--data", type=Path, required=True)
    a = ap.parse_args()
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
            "delta_run_exp",
        ]
    )
    d = pd.concat(
        [
            pd.read_csv(p, usecols=cols, low_memory=False)
            for p in sorted(a.data.glob("statcast-*.csv"))
        ],
        ignore_index=True,
    )
    d = d[
        d.game_type.eq("R")
        & d.plate_x.notna()
        & d.plate_z.notna()
        & d.pitch_type.notna()
        & d.delta_run_exp.notna()
    ].drop_duplicates(["game_pk", "at_bat_number", "pitch_number"])
    for c in PLAYERS:
        d[c] = d[c].astype("int64").astype(str)
    x = features(d)
    y = d.delta_run_exp.to_numpy()
    tr = (d.game_date < "2025-07-01").to_numpy()
    va = ((d.game_date >= "2025-07-01") & (d.game_date < "2025-08-01")).to_numpy()
    te = (d.game_date >= "2025-08-01").to_numpy()
    path = ROOT / "models/response.joblib"
    baseline = ROOT / "models/response-linear.joblib"
    if not baseline.exists():
        baseline.write_bytes(path.read_bytes())
    bundle = joblib.load(baseline)
    entry = bundle["models"]["run_value"]
    linear = entry["model"]
    lpre = bundle["preprocessors"][entry["preprocessor"]]
    dense = ColumnTransformer(
        [
            ("num", "passthrough", NUM),
            (
                "cat",
                OrdinalEncoder(handle_unknown="use_encoded_value", unknown_value=-1),
                CAT,
            ),
        ],
        sparse_threshold=0.0,
    )
    xt = dense.fit_transform(x[tr])
    xv = dense.transform(x[va])
    xe = dense.transform(x[te])
    xl = lpre.transform(x[tr])
    vl = lpre.transform(x[va])
    el = lpre.transform(x[te])
    lp = linear.predict(xl)
    report = {}
    candidates = {}
    catmask = [False] * len(NUM) + [True] * len(CAT)

    def score(name, pv, pt):
        report[name] = {
            "validation_rmse": float(np.sqrt(mean_squared_error(y[va], pv))),
            "test_rmse": float(np.sqrt(mean_squared_error(y[te], pt))),
            "test_mae": float(mean_absolute_error(y[te], pt)),
        }
        print(name, report[name], flush=True)

    score("linear", linear.predict(vl), linear.predict(el))
    for name, residual in [("tree", False), ("linear_plus_tree", True)]:
        model = HistGradientBoostingRegressor(
            max_iter=150,
            max_leaf_nodes=15,
            min_samples_leaf=300,
            l2_regularization=30,
            learning_rate=0.08,
            categorical_features=catmask,
            early_stopping=False,
            random_state=1729,
        )
        start = time.time()
        model.fit(xt, y[tr] - lp if residual else y[tr])
        lo = float(y[tr].min())
        hi = float(y[tr].max())
        if residual:
            fitted = LinearPlusTree(linear, model, xl.shape[1], lo, hi)
            pre = FeatureUnion([("linear", lpre), ("dense", dense)])
            pv = np.clip(linear.predict(vl) + model.predict(xv), lo, hi)
            pt = np.clip(linear.predict(el) + model.predict(xe), lo, hi)
        else:
            fitted = BoundedRegressor(model, lo, hi)
            pre = dense
            pv = fitted.predict(xv)
            pt = fitted.predict(xe)
        score(name, pv, pt)
        print("seconds", round(time.time() - start, 2), flush=True)
        candidates[name] = (pre, fitted)
    # Game-group cross-fitting prevents each observation from influencing its own latent label feature.
    oof = np.empty(int(tr.sum()))
    for fitidx, predidx in GroupKFold(5).split(xl, y[tr], groups=d.loc[tr, "game_pk"]):
        fold = Ridge(alpha=300, solver="lsqr")
        fold.fit(xl[fitidx], y[tr][fitidx])
        oof[predidx] = fold.predict(xl[predidx])
    stack = HistGradientBoostingRegressor(
        max_iter=150,
        max_leaf_nodes=15,
        min_samples_leaf=300,
        l2_regularization=30,
        learning_rate=0.08,
        categorical_features=catmask + [False],
        early_stopping=False,
        random_state=1729,
    )
    stack.fit(np.column_stack([xt, oof]), y[tr])
    pv = stack.predict(np.column_stack([xv, linear.predict(vl)]))
    pt = stack.predict(np.column_stack([xe, linear.predict(el)]))
    score("cross_fitted_stack", pv, pt)
    candidates["cross_fitted_stack"] = (
        FeatureUnion([("linear", lpre), ("dense", dense)]),
        StackedValue(
            linear, stack, xl.shape[1], float(y[tr].min()), float(y[tr].max())
        ),
    )
    selected = min(report, key=lambda n: report[n]["validation_rmse"])
    if selected != "linear":
        pre, model = candidates[selected]
        bundle["preprocessors"]["value_nonlinear"] = pre
        bundle["models"]["run_value"] = {
            "preprocessor": "value_nonlinear",
            "model": model,
        }
        joblib.dump(bundle, path, compress=3)
    final = {
        "selected": selected,
        "models": report,
        "selection": "July validation RMSE only",
        "test_note": "Developmental August+ comparison; not a new untouched holdout",
        "parameters": {
            "iterations": 150,
            "leaves": 15,
            "minimum_leaf": 300,
            "l2": 30,
            "learning_rate": 0.08,
        },
        "n_test": int(te.sum()),
    }
    (ROOT / "models/value-validation.json").write_text(json.dumps(final, indent=2))
    print("Selected", selected, flush=True)


if __name__ == "__main__":
    main()

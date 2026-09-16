"""Shared preprocessing: outcome labels never enter inference features."""

import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.base import BaseEstimator, TransformerMixin
from scipy import sparse
from sklearn.preprocessing import OneHotEncoder, StandardScaler, SplineTransformer
from sklearn.impute import SimpleImputer
from sklearn.pipeline import Pipeline

NUM = [
    "plate_x",
    "plate_z",
    "release_speed",
    "pfx_x",
    "pfx_z",
    "release_spin_rate",
    "release_extension",
    "balls",
    "strikes",
    "outs_when_up",
    "on_1b",
    "on_2b",
    "on_3b",
]
CAT = ["pitch_type", "stand", "p_throws"]
PLAYERS = ["pitcher", "batter"]
SWINGS = [
    "swinging_strike",
    "swinging_strike_blocked",
    "foul",
    "foul_tip",
    "hit_into_play",
]
WHIFF = ["swinging_strike", "swinging_strike_blocked"]
TAKES = ["ball", "blocked_ball", "called_strike"]


def features(d):
    x = d[NUM + CAT + PLAYERS].copy()
    for c in ["on_1b", "on_2b", "on_3b"]:
        x[c] = (
            x[c].notna().astype(float)
            if not x[c].dropna().isin([0, 1]).all()
            else x[c].fillna(0)
        )
    for c in CAT + PLAYERS:
        x[c] = x[c].fillna("unknown").astype(str)
    return x


class LocationInteractions(BaseEstimator, TransformerMixin):
    def fit(self, x, y=None):
        self.encoder_ = OneHotEncoder(handle_unknown="ignore")
        self.encoder_.fit(x.iloc[:, 2:].fillna("unknown").astype(str))
        return self

    def transform(self, x):
        cat = self.encoder_.transform(x.iloc[:, 2:].fillna("unknown").astype(str))
        px = x.iloc[:, 0].fillna(0).to_numpy() / 1.5
        pz = (x.iloc[:, 1].fillna(2.5).to_numpy() - 2.5) / 2
        return sparse.hstack(
            [cat.multiply(v[:, None]) for v in [px, pz, px**2, pz**2, px * pz]],
            format="csr",
        )


def preprocessor(players=True):
    return ColumnTransformer(
        [
            (
                "numeric",
                Pipeline(
                    [
                        ("impute", SimpleImputer(strategy="median")),
                        ("scale", StandardScaler()),
                    ]
                ),
                NUM,
            ),
            (
                "location",
                Pipeline(
                    [
                        ("impute", SimpleImputer(strategy="median")),
                        ("spline", SplineTransformer(n_knots=5, degree=3)),
                    ]
                ),
                ["plate_x", "plate_z"],
            ),
            (
                "interactions",
                LocationInteractions(),
                ["plate_x", "plate_z", "pitch_type"] + (["batter"] if players else []),
            ),
            (
                "categories",
                OneHotEncoder(handle_unknown="ignore"),
                CAT + (PLAYERS if players else []),
            ),
        ],
        sparse_threshold=1.0,
    )


def labels(d, kind):
    if kind == "swing":
        return d.description.isin(SWINGS).astype(int), d.description.isin(
            SWINGS + TAKES
        )
    if kind == "called":
        return d.description.eq("called_strike").astype(int), d.description.isin(TAKES)
    if kind == "contact":
        y = np.where(
            d.description.isin(WHIFF),
            "whiff",
            np.where(
                d.description.eq("hit_into_play"),
                "in_play",
                np.where(d.description.eq("foul_tip"), "tipped_strike", "foul"),
            ),
        )
        return pd.Series(y, index=d.index), d.description.isin(SWINGS)
    if kind == "hit":
        mapping = {
            "single": "single",
            "double": "double",
            "triple": "triple",
            "home_run": "home_run",
            "field_out": "out",
            "force_out": "out",
            "grounded_into_double_play": "out",
            "double_play": "out",
            "sac_fly": "out",
            "sac_bunt": "out",
            "fielders_choice_out": "out",
            "triple_play": "out",
            "sac_fly_double_play": "out",
            "sac_bunt_double_play": "out",
            "field_error": "reach_on_error",
            "fielders_choice": "fielders_choice",
        }
        return d.events.map(mapping), d.description.eq("hit_into_play") & d.events.isin(
            mapping
        )
    raise ValueError(kind)


class BoundedRegressor:
    """Bound regression outputs to the response range observed in training."""

    def __init__(self, model, low, high):
        self.model = model
        self.low = low
        self.high = high

    def predict(self, x):
        return np.clip(self.model.predict(x), self.low, self.high)


class LinearPlusTree:
    """Add a pooled nonlinear residual to a regularized player-aware linear model."""

    def __init__(self, linear, tree, n_linear, low, high):
        self.linear = linear
        self.tree = tree
        self.n_linear = n_linear
        self.low = low
        self.high = high

    def predict(self, x):
        residual = x[:, self.n_linear :]
        if sparse.issparse(residual):
            residual = residual.toarray()
        return np.clip(
            self.linear.predict(x[:, : self.n_linear]) + self.tree.predict(residual),
            self.low,
            self.high,
        )


class StackedValue:
    """A nonlinear model with an out-of-fold-trained linear-value feature."""

    def __init__(self, linear, tree, n_linear, low, high):
        self.linear = linear
        self.tree = tree
        self.n_linear = n_linear
        self.low = low
        self.high = high

    def predict(self, x):
        core = x[:, self.n_linear :]
        if sparse.issparse(core):
            core = core.toarray()
        latent = self.linear.predict(x[:, : self.n_linear])
        return np.clip(
            self.tree.predict(np.column_stack([core, latent])), self.low, self.high
        )

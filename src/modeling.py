"""Shared preprocessing: outcome labels never enter inference features."""
import numpy as np
import pandas as pd
from sklearn.base import BaseEstimator, TransformerMixin
from scipy import sparse
from sklearn.preprocessing import OneHotEncoder
NUM = ['plate_x', 'plate_z', 'release_speed', 'pfx_x', 'pfx_z', 'release_spin_rate', 'release_extension', 'balls', 'strikes', 'outs_when_up', 'on_1b', 'on_2b', 'on_3b']
CAT = ['pitch_type', 'stand', 'p_throws']
PLAYERS = ['pitcher', 'batter']

def features(d):
    x = d[NUM + CAT + PLAYERS].copy()
    for c in ['on_1b', 'on_2b', 'on_3b']:
        x[c] = x[c].notna().astype(float) if not x[c].dropna().isin([0, 1]).all() else x[c].fillna(0)
    for c in CAT + PLAYERS:
        x[c] = x[c].fillna('unknown').astype(str)
    return x

class LocationInteractions(BaseEstimator, TransformerMixin):

    def fit(self, x, y=None):
        self.encoder_ = OneHotEncoder(handle_unknown='ignore')
        self.encoder_.fit(x.iloc[:, 2:].fillna('unknown').astype(str))
        return self

    def transform(self, x):
        cat = self.encoder_.transform(x.iloc[:, 2:].fillna('unknown').astype(str))
        px = x.iloc[:, 0].fillna(0).to_numpy() / 1.5
        pz = (x.iloc[:, 1].fillna(2.5).to_numpy() - 2.5) / 2
        return sparse.hstack([cat.multiply(v[:, None]) for v in [px, pz, px ** 2, pz ** 2, px * pz]], format='csr')

class BoundedRegressor:
    """Bound regression outputs to the response range observed in training."""

    def __init__(self, model, low, high):
        self.model = model
        self.low = low
        self.high = high

    def predict(self, x):
        return np.clip(self.model.predict(x), self.low, self.high)

class StackedValue:
    """A nonlinear model with an out-of-fold-trained linear-value feature."""

    def __init__(self, linear, tree, n_linear, low, high):
        self.linear = linear
        self.tree = tree
        self.n_linear = n_linear
        self.low = low
        self.high = high

    def predict(self, x):
        core = x[:, self.n_linear:]
        if sparse.issparse(core):
            core = core.toarray()
        latent = self.linear.predict(x[:, :self.n_linear])
        return np.clip(self.tree.predict(np.column_stack([core, latent])), self.low, self.high)

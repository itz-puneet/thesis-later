"""Offline baselines for Phase 2.

LApredict (Zeng et al., 2021): logistic regression driven by lines-added (LA).
JITLine (Pornprasit & Tantithamthavorn, 2021): random forest on change
features with SMOTE-style rebalancing (token features + LIME line-level
localization omitted here -- commit-level prediction is what Phase 2 needs;
extend if line-level results are desired).
"""
from __future__ import annotations

import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from config import KAMEI_FEATURES

LA_IDX = KAMEI_FEATURES.index("la")


class LApredict:
    """Logistic regression on the single 'lines added' feature."""

    def __init__(self, seed: int = 42):
        self.pipe = Pipeline([
            ("scale", StandardScaler()),
            ("lr", LogisticRegression(max_iter=1000, random_state=seed,
                                      class_weight="balanced")),
        ])

    def fit(self, X, y):
        self.pipe.fit(np.log1p(X[:, [LA_IDX]]), y)
        return self

    def predict(self, X):
        return self.pipe.predict(np.log1p(X[:, [LA_IDX]]))

    def predict_proba(self, X):
        return self.pipe.predict_proba(np.log1p(X[:, [LA_IDX]]))


class JITLine:
    """RF over all Kamei features with simple minority oversampling."""

    def __init__(self, seed: int = 42, n_estimators: int = 300):
        self.rf = RandomForestClassifier(
            n_estimators=n_estimators, random_state=seed, n_jobs=-1,
            class_weight="balanced_subsample")
        self.seed = seed

    @staticmethod
    def _oversample(X, y, seed):
        """Duplicate-with-jitter oversampling (swap in imblearn.SMOTE for the
        full JITLine replication)."""
        rng = np.random.default_rng(seed)
        pos = np.where(y == 1)[0]
        neg = np.where(y == 0)[0]
        if len(pos) == 0 or len(pos) >= len(neg):
            return X, y
        extra = rng.choice(pos, size=len(neg) - len(pos), replace=True)
        X_extra = X[extra] * rng.normal(1.0, 0.02, size=(len(extra), X.shape[1]))
        return np.vstack([X, X_extra]), np.concatenate([y, np.ones(len(extra), int)])

    def fit(self, X, y):
        Xo, yo = self._oversample(np.asarray(X), np.asarray(y), self.seed)
        self.rf.fit(np.log1p(np.abs(Xo)) * np.sign(Xo), yo)
        return self

    def predict(self, X):
        X = np.asarray(X)
        return self.rf.predict(np.log1p(np.abs(X)) * np.sign(X))

    def predict_proba(self, X):
        X = np.asarray(X)
        return self.rf.predict_proba(np.log1p(np.abs(X)) * np.sign(X))

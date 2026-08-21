"""Offline baselines for Phase 2: LApredict and JITLine.

LApredict (Zeng et al., 2021): Single-feature logistic regression driven by lines added (LA).
JITLine (Pornprasit & Tantithamthavorn, 2021): Random forest over all 14 Kamei features
with minority class rebalancing and feature log-transformations.
"""
from __future__ import annotations

import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from codebase.config import KAMEI_FEATURES

LA_IDX = KAMEI_FEATURES.index("la")


class LApredict:
    """Logistic regression baseline on the single 'lines added' (LA) feature."""

    def __init__(self, seed: int = 42):
        self.seed = seed
        self.pipe = Pipeline([
            ("scale", StandardScaler()),
            ("lr", LogisticRegression(
                max_iter=1000,
                random_state=seed,
                class_weight="balanced"
            )),
        ])

    def fit(self, X: np.ndarray, y: np.ndarray):
        X = np.asarray(X, dtype=float)
        y = np.asarray(y, dtype=int)
        # In case all labels are single-class in a small fold/split
        if len(np.unique(y)) < 2:
            self._single_class = int(y[0]) if len(y) > 0 else 0
            self._is_single = True
            return self
        self._is_single = False
        la_col = np.log1p(np.maximum(X[:, [LA_IDX]], 0.0))
        self.pipe.fit(la_col, y)
        return self

    def predict(self, X: np.ndarray) -> np.ndarray:
        if getattr(self, "_is_single", False):
            return np.full(len(X), self._single_class, dtype=int)
        X = np.asarray(X, dtype=float)
        la_col = np.log1p(np.maximum(X[:, [LA_IDX]], 0.0))
        return self.pipe.predict(la_col)

    def predict_proba(self, X: np.ndarray) -> np.ndarray:
        if getattr(self, "_is_single", False):
            p = np.zeros((len(X), 2), dtype=float)
            p[:, self._single_class] = 1.0
            return p
        X = np.asarray(X, dtype=float)
        la_col = np.log1p(np.maximum(X[:, [LA_IDX]], 0.0))
        return self.pipe.predict_proba(la_col)


class JITLine:
    """Random Forest classifier over all 14 Kamei features with minority oversampling."""

    def __init__(self, seed: int = 42, n_estimators: int = 100):
        self.seed = seed
        self.n_estimators = n_estimators
        self.rf = RandomForestClassifier(
            n_estimators=n_estimators,
            random_state=seed,
            n_jobs=1,
            class_weight="balanced_subsample"
        )

    @staticmethod
    def _oversample(X: np.ndarray, y: np.ndarray, seed: int) -> tuple[np.ndarray, np.ndarray]:
        """Duplicate minority samples with slight Gaussian jitter."""
        rng = np.random.default_rng(seed)
        pos = np.where(y == 1)[0]
        neg = np.where(y == 0)[0]
        if len(pos) == 0 or len(neg) == 0 or len(pos) >= len(neg):
            return X, y
        n_needed = len(neg) - len(pos)
        extra_idx = rng.choice(pos, size=n_needed, replace=True)
        X_extra = X[extra_idx] * rng.normal(1.0, 0.02, size=(n_needed, X.shape[1]))
        return np.vstack([X, X_extra]), np.concatenate([y, np.ones(n_needed, dtype=int)])

    def _transform(self, X: np.ndarray) -> np.ndarray:
        X = np.asarray(X, dtype=float)
        return np.log1p(np.abs(X)) * np.sign(X)

    def fit(self, X: np.ndarray, y: np.ndarray):
        X = np.asarray(X, dtype=float)
        y = np.asarray(y, dtype=int)
        if len(np.unique(y)) < 2:
            self._single_class = int(y[0]) if len(y) > 0 else 0
            self._is_single = True
            return self
        self._is_single = False
        X_res, y_res = self._oversample(X, y, self.seed)
        X_trans = self._transform(X_res)
        self.rf.fit(X_trans, y_res)
        return self

    def predict(self, X: np.ndarray) -> np.ndarray:
        if getattr(self, "_is_single", False):
            return np.full(len(X), self._single_class, dtype=int)
        X_trans = self._transform(X)
        return self.rf.predict(X_trans)

    def predict_proba(self, X: np.ndarray) -> np.ndarray:
        if getattr(self, "_is_single", False):
            p = np.zeros((len(X), 2), dtype=float)
            p[:, self._single_class] = 1.0
            return p
        X_trans = self._transform(X)
        return self.rf.predict_proba(X_trans)

"""PATCH: drop-in replacement for JITLine in codebase/models/baselines.py.

Why: current JITLine G-mean (0.28-0.48) sits far below the one-feature
LApredict (0.65) -- the RF is threshold-starved under 8.5% imbalance, so the
oracle-vs-BSZZ anomaly currently mixes two effects (minority enrichment +
threshold artifact). This patch removes the artifact so the enrichment effect
can be measured cleanly.

Changes:
1. SMOTE oversampling when imblearn is installed (published JITLine uses
   SMOTE); jitter-duplication fallback otherwise, so no hard dependency.
2. Threshold moving: decision threshold tuned to maximize G-mean on the
   chronologically LAST 20% of the training data (a validation tail -- no
   temporal leakage; in naive k-fold the tail is random, which matches that
   regime's own dishonesty and is fine).
3. Same public interface (fit / predict / predict_proba), so
   run_phase2_impact.py needs no changes -- only re-running.
"""
from __future__ import annotations

import numpy as np
from sklearn.ensemble import RandomForestClassifier

try:
    from imblearn.over_sampling import SMOTE
    _HAS_SMOTE = True
except ImportError:
    _HAS_SMOTE = False

from codebase.config import KAMEI_FEATURES


class JITLine:
    """RF over 14 Kamei features + SMOTE + G-mean-optimal threshold moving."""

    def __init__(self, seed: int = 42, n_estimators: int = 100,
                 val_frac: float = 0.2):
        self.seed = seed
        self.val_frac = val_frac
        self.threshold = 0.5
        self.rf = RandomForestClassifier(
            n_estimators=n_estimators, random_state=seed, n_jobs=1,
            class_weight="balanced_subsample")

    # ---------- helpers ----------
    @staticmethod
    def _prep(X: np.ndarray) -> np.ndarray:
        X = np.asarray(X, dtype=float)
        return np.log1p(np.abs(X)) * np.sign(X)

    def _oversample(self, X: np.ndarray, y: np.ndarray):
        pos = int((y == 1).sum())
        if pos < 2 or pos >= (y == 0).sum():
            return X, y
        if _HAS_SMOTE:
            k = min(5, pos - 1)
            return SMOTE(random_state=self.seed, k_neighbors=k).fit_resample(X, y)
        rng = np.random.default_rng(self.seed)              # jitter fallback
        idx = np.where(y == 1)[0]
        extra = rng.choice(idx, size=(y == 0).sum() - pos, replace=True)
        Xe = X[extra] * rng.normal(1.0, 0.02, size=(len(extra), X.shape[1]))
        return np.vstack([X, Xe]), np.concatenate([y, np.ones(len(extra), int)])

    @staticmethod
    def _best_gmean_threshold(y_true: np.ndarray, proba: np.ndarray) -> float:
        best_t, best_g = 0.5, -1.0
        for t in np.unique(np.round(proba, 3)):
            pred = (proba >= t).astype(int)
            tpr = ((pred == 1) & (y_true == 1)).sum() / max((y_true == 1).sum(), 1)
            tnr = ((pred == 0) & (y_true == 0)).sum() / max((y_true == 0).sum(), 1)
            g = np.sqrt(tpr * tnr)
            if g > best_g:
                best_g, best_t = g, float(t)
        return best_t

    # ---------- API ----------
    def fit(self, X: np.ndarray, y: np.ndarray):
        X = self._prep(X)
        y = np.asarray(y, dtype=int)
        if len(np.unique(y)) < 2:
            self._single = int(y[0]) if len(y) else 0
            return self
        self._single = None

        # validation tail for threshold tuning (last val_frac of the split,
        # which is chronologically last under the chronological regime)
        cut = max(int(len(y) * (1 - self.val_frac)), 1)
        X_fit, y_fit = X[:cut], y[:cut]
        X_val, y_val = X[cut:], y[cut:]
        if (y_fit == 1).sum() < 2 or len(np.unique(y_fit)) < 2:
            X_fit, y_fit = X, y            # too small to hold out a tail
            X_val, y_val = X, y            # tune in-sample (documented fallback)

        Xo, yo = self._oversample(X_fit, y_fit)
        self.rf.fit(Xo, yo)

        if len(np.unique(y_val)) == 2:
            proba = self.rf.predict_proba(X_val)[:, 1]
            self.threshold = self._best_gmean_threshold(y_val, proba)
        else:
            self.threshold = 0.5

        # refit on ALL training data with the chosen threshold frozen
        Xo, yo = self._oversample(X, y)
        self.rf.fit(Xo, yo)
        return self

    def predict(self, X: np.ndarray) -> np.ndarray:
        if getattr(self, "_single", None) is not None:
            return np.full(len(X), self._single, dtype=int)
        proba = self.rf.predict_proba(self._prep(X))[:, 1]
        return (proba >= self.threshold).astype(int)

    def predict_proba(self, X: np.ndarray) -> np.ndarray:
        if getattr(self, "_single", None) is not None:
            p = np.zeros((len(X), 2)); p[:, self._single] = 1.0
            return p
        return self.rf.predict_proba(self._prep(X))

"""Offline baselines for Phase 2: LApredict and JITLine.

LApredict (Zeng et al., 2021): Single-feature logistic regression driven by lines added (LA).
JITLine (Pornprasit & Tantithamthavorn, 2021): Random forest over all 14 Kamei features
with SMOTE / jitter minority oversampling, feature log-transformations, and G-mean-optimal
threshold moving.
"""
from __future__ import annotations

import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

try:
    from imblearn.over_sampling import SMOTE
    _HAS_SMOTE = True
except ImportError:
    _HAS_SMOTE = False

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
    """RF over 14 Kamei features + SMOTE + G-mean-optimal threshold moving.

    threshold_mode selects how the decision threshold is estimated:
      "cv"   (default) chronologically blocked out-of-fold probabilities
      "oob"  out-of-bag probabilities of the original rows
      "tail" legacy: fit on the first 80%, tune on the last 20%, refit on 100%

    Measured over 21 projects x 3 seeds x {oracle, BSZZ} labels, chronological,
    oracle-scored -- "cv" gives the best G-mean (0.523 vs 0.486 tail, 0.366 oob)
    and the fewest degenerate all-one-class runs (4.8% vs 9.5% tail, 17.5% oob).
    "oob" is retained for the ablation appendix: its probabilities come from only
    ~63% of the trees, so a threshold tuned on them is miscalibrated against the
    full ensemble used at prediction time.

    Threshold selection uses OUT-OF-BAG probabilities of the original training
    rows. The earlier protocol fit on the first 80% of the split, tuned the
    threshold on the last 20%, then refit on 100% and kept that threshold --
    but the refit shifted the model's calibration by roughly 0.35 in
    probability, so the frozen threshold no longer matched the model it was
    applied to, and the resulting predicted-positive rate swung from 1.4% to
    68.5% across projects.

    OOB estimates are leakage-free by construction (each sample is scored only
    by trees that did not see it), so the threshold can be tuned on the full
    training split against a single fit of the final model. Synthetic SMOTE
    rows are excluded from tuning: imblearn appends generated samples after the
    originals, so the first n_original OOB rows are the real ones.
    """

    def __init__(self, seed: int = 42, n_estimators: int = 100, val_frac: float = 0.2,
                 threshold_mode: str = "cv"):
        self.seed = seed
        self.val_frac = val_frac
        self.threshold_mode = threshold_mode
        self.threshold = 0.5
        self.threshold_source = "default"
        self.rf = RandomForestClassifier(
            n_estimators=n_estimators,
            random_state=seed,
            n_jobs=1,
            class_weight="balanced_subsample",
            bootstrap=True,
            oob_score=True,
        )

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

    def _cv_threshold(self, X: np.ndarray, y: np.ndarray, n_splits: int = 3) -> bool:
        """Tune on out-of-fold probabilities from chronologically blocked folds.

        Fold models see (k-1)/k of the training rows, close to the 100% the
        final model sees, so their probability scale matches it better than
        OOB estimates (~63% of trees) do.
        """
        n = len(y)
        if n < 3 * n_splits:
            return False
        bounds = np.linspace(0, n, n_splits + 1).astype(int)
        oof = np.full(n, np.nan)
        for i in range(n_splits):
            lo, hi = bounds[i], bounds[i + 1]
            te = np.zeros(n, bool); te[lo:hi] = True
            tr = ~te
            if len(np.unique(y[tr])) < 2 or (y[tr] == 1).sum() < 2:
                continue
            rf = RandomForestClassifier(
                n_estimators=self.rf.n_estimators, random_state=self.seed,
                n_jobs=1, class_weight="balanced_subsample",
            )
            Xo, yo = self._oversample(X[tr], y[tr])
            rf.fit(Xo, yo)
            oof[te] = rf.predict_proba(X[te])[:, 1]
        ok = np.isfinite(oof)
        if ok.sum() < 2 or len(np.unique(y[ok])) < 2:
            return False
        self.threshold = self._best_gmean_threshold(y[ok], oof[ok])
        self.threshold_source = "cv"
        return True

    def _tail_threshold(self, X: np.ndarray, y: np.ndarray) -> bool:
        """Legacy fallback: tune on a chronological tail when OOB is unusable."""
        cut = max(int(len(y) * (1 - self.val_frac)), 1)
        X_fit, y_fit, X_val, y_val = X[:cut], y[:cut], X[cut:], y[cut:]
        if (y_fit == 1).sum() < 2 or len(np.unique(y_fit)) < 2 or len(np.unique(y_val)) < 2:
            return False
        rf_tmp = RandomForestClassifier(
            n_estimators=self.rf.n_estimators, random_state=self.seed,
            n_jobs=1, class_weight="balanced_subsample",
        )
        Xo, yo = self._oversample(X_fit, y_fit)
        rf_tmp.fit(Xo, yo)
        self.threshold = self._best_gmean_threshold(y_val, rf_tmp.predict_proba(X_val)[:, 1])
        self.threshold_source = "tail"
        return True

    # ---------- API ----------
    def fit(self, X: np.ndarray, y: np.ndarray):
        X = self._prep(X)
        y = np.asarray(y, dtype=int)
        if len(np.unique(y)) < 2:
            self._single = int(y[0]) if len(y) else 0
            return self
        self._single = None

        n_orig = len(y)
        Xo, yo = self._oversample(X, y)
        self.rf.fit(Xo, yo)          # single fit on ALL training data

        tuned = False
        if self.threshold_mode == "oob":
            # Out-of-bag probabilities of the original rows only.
            oob = getattr(self.rf, "oob_decision_function_", None)
            if oob is not None and oob.ndim == 2 and oob.shape[0] >= n_orig:
                p = oob[:n_orig, 1]
                ok = np.isfinite(p)                  # never out-of-bag -> NaN
                if ok.sum() >= 2 and len(np.unique(y[ok])) == 2:
                    self.threshold = self._best_gmean_threshold(y[ok], p[ok])
                    self.threshold_source = "oob"
                    tuned = True
        elif self.threshold_mode == "cv":
            tuned = self._cv_threshold(X, y)

        if not tuned:
            tuned = self._tail_threshold(X, y)
        if not tuned:
            self.threshold = 0.5
            self.threshold_source = "default"
        return self

    def predict(self, X: np.ndarray) -> np.ndarray:
        if getattr(self, "_single", None) is not None:
            return np.full(len(X), self._single, dtype=int)
        proba = self.rf.predict_proba(self._prep(X))[:, 1]
        return (proba >= self.threshold).astype(int)

    def predict_proba(self, X: np.ndarray) -> np.ndarray:
        if getattr(self, "_single", None) is not None:
            p = np.zeros((len(X), 2))
            p[:, self._single] = 1.0
            return p
        return self.rf.predict_proba(self._prep(X))

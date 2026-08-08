"""Online ensemble learners: Online Bagging -> OOB -> ORB.

ORB (Oversampling Rate Boosting; Cabral, Minku, Shihab & Mujahid, 2019)
extends Oversampling Online Bagging by multiplying the minority-class Poisson
rate with a boost factor driven by the model's recent prediction bias.

Instrumentation: `trace` records the boost factor, bias signal, and effective
lambda over time -- required for Phase 3 mechanism plots.
"""
from __future__ import annotations

import numpy as np


def _sigmoid(z):
    return 1.0 / (1.0 + np.exp(-np.clip(z, -30, 30)))


class _OnlineBase:
    """Poisson-weighted online bagging over incremental base learners.

    Base learner: online logistic regression with per-member weight vectors,
    vectorized across the whole ensemble (one matrix op per stream instance).
    For full replication of Cabral et al. (2019), swap the base for
    river.tree.HoeffdingTreeClassifier -- the ensemble logic is identical.
    Features are standardized online (running mean/var) and log-compressed.
    """

    def __init__(self, n_estimators=20, seed=42, lr=0.15, l2=1e-4):
        self.rng = np.random.default_rng(seed)
        self.n_estimators = n_estimators
        self.lr, self.l2 = lr, l2
        self.W = None            # (n_estimators, d+1) incl. bias
        # online feature standardization (Welford)
        self._n = 0
        self._mu = None
        self._m2 = None

    # ---- feature preprocessing ----------------------------------------
    def _transform(self, x, update=False):
        x = np.log1p(np.abs(np.asarray(x, float))) * np.sign(x)
        if self._mu is None:
            self._mu = np.zeros_like(x); self._m2 = np.ones_like(x)
        if update:
            self._n += 1
            d = x - self._mu
            self._mu += d / self._n
            self._m2 += d * (x - self._mu)
        sd = np.sqrt(self._m2 / max(self._n, 1)) + 1e-6
        return np.append((x - self._mu) / sd, 1.0)  # bias term

    def _ensure_W(self, d):
        if self.W is None:
            self.W = self.rng.normal(0, 0.01, size=(self.n_estimators, d))

    # ---- core ops -------------------------------------------------------
    def _update_members(self, x, y, ks, weight: float = 1.0):
        """One vectorized SGD step; member i's gradient scaled by Poisson
        draw ks[i] (k-fold presentation == k-weighted update)."""
        z = self._transform(x, update=True)
        self._ensure_W(len(z))
        p = _sigmoid(self.W @ z)                    # (n_estimators,)
        g = (p - y) * ks * weight                    # per-member scale
        self.W -= self.lr * (np.outer(g, z) + self.l2 * self.W)

    def predict_proba_one(self, x) -> float:
        if self.W is None:
            return 0.5
        z = self._transform(x)
        return float(_sigmoid(self.W @ z).mean())

    def predict_one(self, x) -> int:
        if self.W is None:
            return 0
        z = self._transform(x)
        votes = (_sigmoid(self.W @ z) >= 0.5)
        return int(votes.mean() >= 0.5)

    # split-ensemble probabilities (used by co-teaching agreement check)
    def _half_probas(self, x) -> tuple[float, float]:
        if self.W is None:
            return 0.5, 0.5
        z = self._transform(x)
        p = _sigmoid(self.W @ z)
        h = len(p) // 2
        return float(p[:h].mean()), float(p[h:].mean())


class OOB(_OnlineBase):
    """Oversampling Online Bagging: lambda scales with observed imbalance."""

    def __init__(self, n_estimators=20, seed=42, decay=0.99):
        super().__init__(n_estimators, seed)
        self.decay = decay
        self.rate1 = 0.5  # decayed fraction of class-1 examples seen

    def _lambda(self, y) -> float:
        # minority gets rate (majority share / minority share), majority gets 1
        r1 = min(max(self.rate1, 1e-3), 1 - 1e-3)
        return (1 - r1) / r1 if y == 1 and r1 < 0.5 else \
               (r1 / (1 - r1) if y == 0 and r1 > 0.5 else 1.0)

    def learn_one(self, x, y, weight: float = 1.0):
        self.rate1 = self.decay * self.rate1 + (1 - self.decay) * (y == 1)
        lam = self._lambda(y)
        ks = self.rng.poisson(lam, size=self.n_estimators)
        self._update_members(x, y, ks, weight)


class ORB(OOB):
    """OOB + prediction-bias-driven boosting of the oversampling rate."""

    def __init__(self, n_estimators=20, seed=42, decay=0.99, theta=0.4,
                 l0=10.0, l1=12.0, m=1.5, n=3.0, target_defect_rate=None):
        super().__init__(n_estimators, seed, decay)
        self.theta = theta
        self.l0, self.l1, self.m, self.n = l0, l1, m, n
        self.target = target_defect_rate
        self.ma_pred = 0.5          # moving average of recent predictions
        self.trace: list[dict] = []  # Phase 3 instrumentation

    def observe_prediction(self, pred: int):
        self.ma_pred = self.theta * self.ma_pred + (1 - self.theta) * pred

    def predict_one(self, x) -> int:
        p = super().predict_one(x)
        self.observe_prediction(p)
        return p

    def _boost(self, y) -> float:
        """obf(): amplify minority when the model under-predicts defects,
        amplify majority when it over-predicts them (Cabral et al. 2019
        exponential-shaped boost)."""
        target = self.target if self.target is not None else \
            min(max(self.rate1, 1e-3), 1 - 1e-3)
        if y == 1 and self.ma_pred < target:      # missing defects
            return ((self.m ** self.ma_pred - self.m ** target) /
                    (1 - self.m ** target)) * self.l0 + 1 if self.m != 1 else 1.0
        if y == 0 and self.ma_pred > target:      # crying wolf
            return ((self.n ** (1 - self.ma_pred) - self.n ** (1 - target)) /
                    (1 - self.n ** (1 - target))) * self.l1 + 1 if self.n != 1 else 1.0
        return 1.0

    def learn_one(self, x, y, weight: float = 1.0):
        self.rate1 = self.decay * self.rate1 + (1 - self.decay) * (y == 1)
        boost = max(self._boost(y), 1.0)
        lam = self._lambda(y) * boost
        self.trace.append(dict(y=int(y), boost=float(boost), lam=float(lam),
                               ma_pred=float(self.ma_pred),
                               rate1=float(self.rate1)))
        ks = self.rng.poisson(lam, size=self.n_estimators)
        self._update_members(x, y, ks, weight)

"""Online ensemble learners: Online Bagging -> OOB -> ORB.

ORB (Oversampling Rate Boosting; Cabral, Minku, Shihab & Mujahid, 2019)
extends Oversampling Online Bagging by multiplying the minority-class Poisson
rate with a boost factor driven by the model's recent prediction bias.

Instrumentation: `trace` records the boost factor, bias signal, and effective
lambda over time -- essential for Phase 3 noise amplifier mechanism plots.
"""
from __future__ import annotations

import numpy as np


def _sigmoid(z: np.ndarray) -> np.ndarray:
    return 1.0 / (1.0 + np.exp(-np.clip(z, -30.0, 30.0)))


class _OnlineBase:
    """Poisson-weighted online bagging over incremental logistic base learners.

    Vectorized across the entire ensemble (one matrix multiplication per stream instance).
    Features are standardized online via Welford's algorithm and log-compressed.
    """

    def __init__(self, n_estimators: int = 20, seed: int = 42, lr: float = 0.15, l2: float = 1e-4):
        self.rng = np.random.default_rng(seed)
        self.n_estimators = n_estimators
        self.lr, self.l2 = lr, l2
        self.W: np.ndarray | None = None  # (n_estimators, d+1) incl. bias term
        # Running statistics for online feature standardization (Welford)
        self._n = 0
        self._mu: np.ndarray | None = None
        self._m2: np.ndarray | None = None

    def _transform(self, x: np.ndarray, update: bool = False) -> np.ndarray:
        x = np.log1p(np.abs(np.asarray(x, dtype=float))) * np.sign(x)
        if self._mu is None:
            self._mu = np.zeros_like(x)
            self._m2 = np.ones_like(x)
        if update:
            self._n += 1
            d = x - self._mu
            self._mu += d / self._n
            self._m2 += d * (x - self._mu)
        sd = np.sqrt(self._m2 / max(self._n, 1)) + 1e-6
        return np.append((x - self._mu) / sd, 1.0)  # append bias feature

    def _ensure_W(self, d: int):
        if self.W is None:
            self.W = self.rng.normal(0, 0.01, size=(self.n_estimators, d))

    def _update_members(self, x: np.ndarray, y: int, ks: np.ndarray, weight: float = 1.0):
        """Vectorized SGD step; member i's gradient is scaled by Poisson draw ks[i]."""
        z = self._transform(x, update=True)
        self._ensure_W(len(z))
        p = _sigmoid(self.W @ z)                     # (n_estimators,)
        g = (p - y) * ks * weight                    # per-member scaled gradient
        self.W -= self.lr * (np.outer(g, z) + self.l2 * self.W)

    def predict_proba_one(self, x: np.ndarray) -> float:
        if self.W is None:
            return 0.5
        z = self._transform(x)
        return float(_sigmoid(self.W @ z).mean())

    def predict_one(self, x: np.ndarray) -> int:
        if self.W is None:
            return 0
        z = self._transform(x)
        votes = (_sigmoid(self.W @ z) >= 0.5)
        return int(votes.mean() >= 0.5)

    def _half_probas(self, x: np.ndarray) -> tuple[float, float]:
        """Split-ensemble probabilities (used by co-teaching agreement check in Phase 4)."""
        if self.W is None:
            return 0.5, 0.5
        z = self._transform(x)
        p = _sigmoid(self.W @ z)
        h = len(p) // 2
        return float(p[:h].mean()), float(p[h:].mean())


class OOB(_OnlineBase):
    """Oversampling Online Bagging: lambda scales with observed imbalance."""

    def __init__(self, n_estimators: int = 20, seed: int = 42, decay: float = 0.99):
        super().__init__(n_estimators, seed)
        self.decay = decay
        self.rate1 = 0.5  # decayed fraction of class-1 examples seen

    def _lambda(self, y: int) -> float:
        r1 = min(max(self.rate1, 1e-3), 1.0 - 1e-3)
        if y == 1 and r1 < 0.5:
            return (1.0 - r1) / r1
        elif y == 0 and r1 > 0.5:
            return r1 / (1.0 - r1)
        return 1.0

    def learn_one(self, x: np.ndarray, y: int, weight: float = 1.0):
        self.rate1 = self.decay * self.rate1 + (1.0 - self.decay) * (y == 1)
        lam = self._lambda(y)
        ks = self.rng.poisson(lam, size=self.n_estimators)
        self._update_members(x, y, ks, weight)


class ORB(OOB):
    """OOB + prediction-bias-driven boosting of the oversampling rate."""

    def __init__(
        self,
        n_estimators: int = 20,
        seed: int = 42,
        decay: float = 0.99,
        theta: float = 0.4,
        l0: float = 10.0,
        l1: float = 12.0,
        m: float = 1.5,
        n: float = 3.0,
        target_defect_rate: float | None = None,
    ):
        super().__init__(n_estimators, seed, decay)
        self.theta = theta
        self.l0, self.l1, self.m, self.n = l0, l1, m, n
        self.target = target_defect_rate
        self.ma_pred = 0.5          # moving average of recent predictions
        self.trace: list[dict] = []  # Phase 3 instrumentation

    def observe_prediction(self, pred: int):
        self.ma_pred = self.theta * self.ma_pred + (1.0 - self.theta) * pred

    def predict_one(self, x: np.ndarray) -> int:
        p = super().predict_one(x)
        self.observe_prediction(p)
        return p

    def _boost(self, y: int) -> float:
        """obf(): exponential boosting function from Cabral et al. (2019)."""
        target = self.target if self.target is not None else min(max(self.rate1, 1e-3), 1.0 - 1e-3)
        if y == 1 and self.ma_pred < target:      # model missing defects
            if self.m != 1.0 and (1.0 - self.m ** target) != 0:
                boost = ((self.m ** self.ma_pred - self.m ** target) / (1.0 - self.m ** target)) * self.l0 + 1.0
                return max(boost, 1.0)
        if y == 0 and self.ma_pred > target:      # model crying wolf
            if self.n != 1.0 and (1.0 - self.n ** (1.0 - target)) != 0:
                boost = ((self.n ** (1.0 - self.ma_pred) - self.n ** (1.0 - target)) / (1.0 - self.n ** (1.0 - target))) * self.l1 + 1.0
                return max(boost, 1.0)
        return 1.0

    def learn_one(self, x: np.ndarray, y: int, weight: float = 1.0):
        self.rate1 = self.decay * self.rate1 + (1.0 - self.decay) * (y == 1)
        boost = self._boost(y)
        lam = self._lambda(y) * boost
        self.trace.append(
            dict(
                y=int(y),
                boost=float(boost),
                lam=float(lam),
                ma_pred=float(self.ma_pred),
                rate1=float(self.rate1),
            )
        )
        ks = self.rng.poisson(lam, size=self.n_estimators)
        self._update_members(x, y, ks, weight)

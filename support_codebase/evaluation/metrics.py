"""Chance-anchored metrics and prequential (fading) tracking.

Primary outcome metrics: MCC and G-mean (per Destefanis et al. 2026 audit
recommendations). F1/accuracy are intentionally not used as outcomes.
"""
from __future__ import annotations

import numpy as np
from scipy import stats
from sklearn.metrics import cohen_kappa_score, matthews_corrcoef


def mcc(y_true, y_pred) -> float:
    return float(matthews_corrcoef(y_true, y_pred))


def gmean(y_true, y_pred) -> float:
    y_true, y_pred = np.asarray(y_true), np.asarray(y_pred)
    tpr = ((y_pred == 1) & (y_true == 1)).sum() / max((y_true == 1).sum(), 1)
    tnr = ((y_pred == 0) & (y_true == 0)).sum() / max((y_true == 0).sum(), 1)
    return float(np.sqrt(tpr * tnr))


def label_quality(oracle, szz) -> dict:
    """Phase 1: quality of an SZZ label column against the oracle."""
    oracle, szz = np.asarray(oracle), np.asarray(szz)
    tp = int(((szz == 1) & (oracle == 1)).sum())
    fp = int(((szz == 1) & (oracle == 0)).sum())
    fn = int(((szz == 0) & (oracle == 1)).sum())
    tn = int(((szz == 0) & (oracle == 0)).sum())
    return dict(
        precision=tp / max(tp + fp, 1),
        recall=tp / max(tp + fn, 1),
        fp_rate=fp / max(fp + tn, 1),      # rho_0: clean -> "defective"
        fn_rate=fn / max(fn + tp, 1),      # rho_1: defective -> "clean"
        kappa=float(cohen_kappa_score(oracle, szz)),
        mcc=mcc(oracle, szz),
        n=tp + fp + fn + tn,
    )


class PrequentialTracker:
    """Fading confusion matrix for test-then-train evaluation.

    Each cell decays by `fading` before every update, so metrics reflect
    recent performance (standard practice in stream mining).
    """

    def __init__(self, fading: float = 0.99):
        self.f = fading
        self.tp = self.fp = self.fn = self.tn = 0.0
        self.history: list[dict] = []

    def update(self, y_true: int, y_pred: int, ts=None):
        self.tp *= self.f; self.fp *= self.f; self.fn *= self.f; self.tn *= self.f
        if y_true == 1 and y_pred == 1: self.tp += 1
        elif y_true == 0 and y_pred == 1: self.fp += 1
        elif y_true == 1 and y_pred == 0: self.fn += 1
        else: self.tn += 1
        self.history.append(dict(ts=ts, gmean=self.gmean(), mcc=self.mcc()))

    def gmean(self) -> float:
        tpr = self.tp / max(self.tp + self.fn, 1e-9)
        tnr = self.tn / max(self.tn + self.fp, 1e-9)
        return float(np.sqrt(tpr * tnr))

    def mcc(self) -> float:
        num = self.tp * self.tn - self.fp * self.fn
        den = np.sqrt((self.tp + self.fp) * (self.tp + self.fn) *
                      (self.tn + self.fp) * (self.tn + self.fn))
        return float(num / den) if den > 0 else 0.0


def wilcoxon_with_cliffs(a, b) -> dict:
    """Paired Wilcoxon signed-rank + Cliff's delta effect size."""
    a, b = np.asarray(a, float), np.asarray(b, float)
    try:
        stat, p = stats.wilcoxon(a, b)
    except ValueError:  # all-zero differences
        stat, p = 0.0, 1.0
    gt = sum((x > y) for x in a for y in b)
    lt = sum((x < y) for x in a for y in b)
    delta = (gt - lt) / (len(a) * len(b))
    mag = ("negligible" if abs(delta) < .147 else "small" if abs(delta) < .33
           else "medium" if abs(delta) < .474 else "large")
    return dict(wilcoxon_stat=float(stat), p_value=float(p),
                cliffs_delta=float(delta), magnitude=mag)

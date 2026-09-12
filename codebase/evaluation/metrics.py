"""Chance-anchored metrics and prequential (fading) tracking.

Primary outcome metrics: MCC and G-mean (per Destefanis et al. 2026 audit
recommendations). F1/accuracy are intentionally not used as outcomes.
"""
from __future__ import annotations

import numpy as np
from scipy import stats
from sklearn.metrics import cohen_kappa_score, matthews_corrcoef


def mcc(y_true: np.ndarray | list, y_pred: np.ndarray | list) -> float:
    """Matthews Correlation Coefficient (chance-anchored at 0.0)."""
    y_true = np.asarray(y_true, dtype=int)
    y_pred = np.asarray(y_pred, dtype=int)
    if len(np.unique(y_true)) < 2 or len(np.unique(y_pred)) < 2:
        # Avoid zero-division warnings when array has single class
        tp = np.sum((y_true == 1) & (y_pred == 1))
        tn = np.sum((y_true == 0) & (y_pred == 0))
        fp = np.sum((y_true == 0) & (y_pred == 1))
        fn = np.sum((y_true == 1) & (y_pred == 0))
        denom = np.sqrt((tp + fp) * (tp + fn) * (tn + fp) * (tn + fn))
        return float((tp * tn - fp * fn) / denom) if denom > 0 else 0.0
    return float(matthews_corrcoef(y_true, y_pred))


def gmean(y_true: np.ndarray | list, y_pred: np.ndarray | list) -> float:
    """Geometric mean of per-class recalls: sqrt(TPR * TNR)."""
    y_true, y_pred = np.asarray(y_true, dtype=int), np.asarray(y_pred, dtype=int)
    pos_count = np.sum(y_true == 1)
    neg_count = np.sum(y_true == 0)
    if pos_count == 0 or neg_count == 0:
        return 0.0
    tpr = float(np.sum((y_pred == 1) & (y_true == 1)) / pos_count)
    tnr = float(np.sum((y_pred == 0) & (y_true == 0)) / neg_count)
    return float(np.sqrt(tpr * tnr))


def label_quality(oracle: np.ndarray | list, szz: np.ndarray | list) -> dict:
    """Evaluate quality of an SZZ label column against the oracle."""
    oracle, szz = np.asarray(oracle, dtype=int), np.asarray(szz, dtype=int)
    tp = int(np.sum((szz == 1) & (oracle == 1)))
    fp = int(np.sum((szz == 1) & (oracle == 0)))
    fn = int(np.sum((szz == 0) & (oracle == 1)))
    tn = int(np.sum((szz == 0) & (oracle == 0)))
    return dict(
        precision=float(tp / max(tp + fp, 1)),
        recall=float(tp / max(tp + fn, 1)),
        fp_rate=float(fp / max(fp + tn, 1)),      # rho_0: clean -> defective
        fn_rate=float(fn / max(fn + tp, 1)),      # rho_1: defective -> clean
        kappa=float(cohen_kappa_score(oracle, szz)),
        mcc=mcc(oracle, szz),
        n=int(tp + fp + fn + tn),
    )


class PrequentialTracker:
    """Fading confusion matrix for test-then-train streaming evaluation.

    Each cell decays by `fading` factor before every update, giving recent
    performance higher weight.
    """

    def __init__(self, fading: float = 0.99):
        self.f = fading
        self.tp = 0.0
        self.fp = 0.0
        self.fn = 0.0
        self.tn = 0.0
        self.history: list[dict] = []

    def update(self, y_true: int, y_pred: int, ts: float | None = None):
        self.tp *= self.f
        self.fp *= self.f
        self.fn *= self.f
        self.tn *= self.f

        if y_true == 1 and y_pred == 1:
            self.tp += 1.0
        elif y_true == 0 and y_pred == 1:
            self.fp += 1.0
        elif y_true == 1 and y_pred == 0:
            self.fn += 1.0
        else:
            self.tn += 1.0

        self.history.append(dict(ts=ts, gmean=self.gmean(), mcc=self.mcc()))

    def gmean(self) -> float:
        tpr = self.tp / max(self.tp + self.fn, 1e-9)
        tnr = self.tn / max(self.tn + self.fp, 1e-9)
        return float(np.sqrt(tpr * tnr))

    def mcc(self) -> float:
        num = self.tp * self.tn - self.fp * self.fn
        den = np.sqrt(
            (self.tp + self.fp) * (self.tp + self.fn) * (self.tn + self.fp) * (self.tn + self.fn)
        )
        return float(num / den) if den > 0 else 0.0


def paired_effect(a: np.ndarray | list, b: np.ndarray | list,
                  n_boot: int = 10000, seed: int = 42) -> dict:
    """Paired Wilcoxon test with PAIRED effect sizes.

    The design pairs by project and the Wilcoxon test honours that, but
    `wilcoxon_with_cliffs` reported Cliff's delta computed all-versus-all
    (denominator n*m), which discards the pairing the design deliberately
    preserves. This returns effect sizes that keep it:

      rank_biserial   matched-pairs rank-biserial correlation, (W+ - W-)/(W+ + W-),
                      derived from the same signed ranks the p-value uses
      median_diff     median of the paired differences
      hodges_lehmann  median of the Walsh averages of the differences, the
                      location estimator that accompanies the signed-rank test
      ci_low/ci_high  percentile bootstrap CI **for the Hodges-Lehmann
                      estimator** -- the HL statistic is recomputed inside every
                      resample, so the interval targets the quantity it is
                      reported beside
      median_ci_low/high
                      percentile bootstrap CI for the median paired difference,
                      reported separately because it is a different estimator

    Magnitude thresholds follow the usual |r| convention: 0.1 small,
    0.3 medium, 0.5 large. Cliff's delta is still returned, labelled
    `cliffs_delta_unpaired`, so earlier tables remain comparable.
    """
    a, b = np.asarray(a, dtype=float), np.asarray(b, dtype=float)
    if len(a) != len(b) or len(a) == 0:
        return dict(wilcoxon_stat=0.0, p_value=1.0, rank_biserial=0.0,
                    median_diff=0.0, hodges_lehmann=0.0, ci_low=0.0, ci_high=0.0,
                    cliffs_delta_unpaired=0.0, magnitude="negligible", n_pairs=0)

    d = a - b
    nz = d[d != 0]
    if len(nz) == 0:
        return dict(wilcoxon_stat=0.0, p_value=1.0, rank_biserial=0.0,
                    median_diff=0.0, hodges_lehmann=0.0, ci_low=0.0, ci_high=0.0,
                    cliffs_delta_unpaired=0.0, magnitude="negligible", n_pairs=len(a))

    try:
        stat, p = stats.wilcoxon(a, b)
    except Exception:
        stat, p = 0.0, 1.0

    # matched-pairs rank-biserial from the signed ranks
    ranks = stats.rankdata(np.abs(nz))
    w_pos, w_neg = ranks[nz > 0].sum(), ranks[nz < 0].sum()
    total = w_pos + w_neg
    rb = float((w_pos - w_neg) / total) if total > 0 else 0.0

    # Hodges-Lehmann: median of Walsh averages
    walsh = np.add.outer(d, d)[np.triu_indices(len(d))] / 2.0
    hl = float(np.median(walsh))

    # Bootstrap BOTH estimators, each resampled as itself. An earlier version
    # bootstrapped the median of the differences and reported that interval
    # beside the Hodges-Lehmann point estimate; the interval then targeted a
    # different quantity from the one it appeared to qualify.
    rng = np.random.default_rng(seed)
    n = len(d)
    idx = rng.integers(0, n, size=(n_boot, n))
    D = d[idx]                                     # (n_boot, n)
    iu = np.triu_indices(n)
    walsh_boot = (D[:, iu[0]] + D[:, iu[1]]) / 2.0  # (n_boot, n(n+1)/2)
    hl_boot = np.median(walsh_boot, axis=1)
    lo, hi = np.percentile(hl_boot, [2.5, 97.5])
    med_boot = np.median(D, axis=1)
    mlo, mhi = np.percentile(med_boot, [2.5, 97.5])

    gt = sum((x > y) for x in a for y in b)
    lt = sum((x < y) for x in a for y in b)
    cd = (gt - lt) / (len(a) * len(b))

    r = abs(rb)
    mag = "negligible" if r < 0.1 else "small" if r < 0.3 else "medium" if r < 0.5 else "large"
    return dict(wilcoxon_stat=float(stat), p_value=float(p), rank_biserial=rb,
                median_diff=float(np.median(d)), hodges_lehmann=hl,
                ci_low=float(lo), ci_high=float(hi),              # targets HL
                median_ci_low=float(mlo), median_ci_high=float(mhi),
                cliffs_delta_unpaired=float(cd), magnitude=mag, n_pairs=int(len(a)))


def wilcoxon_with_cliffs(a: np.ndarray | list, b: np.ndarray | list) -> dict:
    """Paired Wilcoxon signed-rank test + Cliff's delta effect size."""
    a, b = np.asarray(a, dtype=float), np.asarray(b, dtype=float)
    if len(a) != len(b) or len(a) == 0:
        return dict(wilcoxon_stat=0.0, p_value=1.0, cliffs_delta=0.0, magnitude="negligible")

    # Wilcoxon signed-rank test
    diffs = a - b
    if np.all(diffs == 0):
        stat, p = 0.0, 1.0
    else:
        try:
            stat, p = stats.wilcoxon(a, b)
        except Exception:
            stat, p = 0.0, 1.0

    # Cliff's delta: (count(x > y) - count(x < y)) / (n * m)
    gt = sum((x > y) for x in a for y in b)
    lt = sum((x < y) for x in a for y in b)
    n_pairs = len(a) * len(b)
    delta = (gt - lt) / n_pairs if n_pairs > 0 else 0.0

    abs_d = abs(delta)
    if abs_d < 0.147:
        mag = "negligible"
    elif abs_d < 0.33:
        mag = "small"
    elif abs_d < 0.474:
        mag = "medium"
    else:
        mag = "large"

    return dict(
        wilcoxon_stat=float(stat),
        p_value=float(p),
        cliffs_delta=float(delta),
        magnitude=mag,
    )

"""Three evaluation regimes for Phase 2.

1. naive_kfold          -- Random stratified shuffling (temporally dishonest upper bound).
2. chronological        -- Time-ordered 50/50 train/test split (honest batch evaluation).
3. prequential_latency  -- Online stream test-then-train respecting verification latency (W=90 days).
"""
from __future__ import annotations

import heapq
from typing import Callable, Any
import numpy as np
import pandas as pd
from sklearn.model_selection import StratifiedKFold

from codebase.config import KAMEI_FEATURES, VERIFICATION_WAIT_DAYS, PREQUENTIAL_FADING
from codebase.evaluation.metrics import mcc, gmean, PrequentialTracker


def naive_kfold(
    model_factory: Callable[[], Any],
    df: pd.DataFrame,
    label_col: str,
    eval_label_col: str | None = None,
    k: int = 10,
    seed: int = 42,
) -> dict:
    """Random stratified k-fold cross-validation."""
    eval_label_col = eval_label_col or label_col
    X = df[KAMEI_FEATURES].to_numpy(dtype=float)
    y_train_src = df[label_col].to_numpy(dtype=int)
    y_eval = df[eval_label_col].to_numpy(dtype=int)

    # In case there are very few instances of minority class for 10-fold
    pos_count = np.sum(y_train_src == 1)
    k_actual = min(k, max(pos_count, 2), len(df))
    if k_actual < 2:
        k_actual = 2

    preds = np.zeros(len(df), dtype=int)
    try:
        skf = StratifiedKFold(n_splits=k_actual, shuffle=True, random_state=seed)
        splits = skf.split(X, y_train_src)
    except Exception:
        # Fallback to non-stratified KFold if stratification fails
        from sklearn.model_selection import KFold
        kf = KFold(n_splits=k_actual, shuffle=True, random_state=seed)
        splits = kf.split(X, y_train_src)

    for tr, te in splits:
        m = model_factory()
        m.fit(X[tr], y_train_src[tr])
        preds[te] = m.predict(X[te])

    return dict(
        regime="naive_kfold",
        mcc=mcc(y_eval, preds),
        gmean=gmean(y_eval, preds),
    )


def chronological(
    model_factory: Callable[[], Any],
    df: pd.DataFrame,
    label_col: str,
    eval_label_col: str | None = None,
    train_frac: float = 0.5,
) -> dict:
    """Chronological (time-aware) batch train/test split."""
    eval_label_col = eval_label_col or label_col
    df_sorted = df.sort_values("author_ts").reset_index(drop=True)
    cut = int(len(df_sorted) * train_frac)
    if cut < 1:
        cut = 1
    if cut >= len(df_sorted):
        cut = len(df_sorted) - 1

    tr = df_sorted.iloc[:cut]
    te = df_sorted.iloc[cut:]

    X_tr = tr[KAMEI_FEATURES].to_numpy(dtype=float)
    y_tr = tr[label_col].to_numpy(dtype=int)

    X_te = te[KAMEI_FEATURES].to_numpy(dtype=float)
    y_ev = te[eval_label_col].to_numpy(dtype=int)

    m = model_factory()
    m.fit(X_tr, y_tr)
    preds = m.predict(X_te)

    return dict(
        regime="chronological",
        mcc=mcc(y_ev, preds),
        gmean=gmean(y_ev, preds),
    )


def prequential_latency(
    online_model: Any,
    df: pd.DataFrame,
    label_col: str,
    eval_label_col: str | None = None,
    wait_days: float = VERIFICATION_WAIT_DAYS,
    fading: float = PREQUENTIAL_FADING,
    latency_mode: str = "real",
    fix_ts_col: str | None = None,
) -> dict:
    """Test-then-train streaming evaluation with verification latency.

    Timeline per commit i (author time t_i), latency_mode="real":
      * t_i:      model predicts (scored immediately against eval label)
      * clean-labeled commit:            train example (y=0) at t_i + W
      * defect-labeled, fix_ts <= t_i+W: train example (y=1) at fix_ts
      * defect-labeled, fix_ts >  t_i+W: y=0 at t_i+W  THEN  y=1 at fix_ts
      * defect-labeled, fix_ts unknown:  y=0 at t_i+W only (label never arrives
        -- honest: without a linked fix, the pipeline would never learn it)
    """
    eval_label_col = eval_label_col or label_col
    d = df.sort_values("author_ts").reset_index(drop=True)
    n = len(d)

    X = d[KAMEI_FEATURES].to_numpy(dtype=float)
    y_train = d[label_col].to_numpy(dtype=int)
    y_eval = d[eval_label_col].to_numpy(dtype=int)
    t = d["author_ts"].to_numpy(dtype=float)
    W = wait_days * 86400.0

    if latency_mode == "real":
        # pick the label source's own mapping when available
        col = fix_ts_col or f"fix_ts_{label_col.replace('label_', '')}"
        if col not in d.columns:
            col = "fix_ts"
        if col not in d.columns or d[col].notna().sum() == 0:
            raise ValueError(
                f"latency_mode='real' but no usable fix_ts column for {label_col} "
                f"(looked for '{col}'). Run patch_build_fix_ts.py first, or pass "
                f"latency_mode='uniform' explicitly (and report it as fixed-delay)."
            )
        fix_ts = d[col].to_numpy(dtype=float)
    elif latency_mode == "uniform":
        fix_ts = np.full(n, np.nan)
    else:
        raise ValueError(f"unknown latency_mode: {latency_mode}")

    tracker = PrequentialTracker(fading)
    pending: list[tuple[float, int, int, int]] = []  # (arrival_ts, tiebreak, idx, label)
    tie = 0  # heapq tiebreaker: preserves push order at equal timestamps,
             # guaranteeing tentative-clean is consumed before its correction

    for i in range(n):
        now = t[i]
        while pending and pending[0][0] <= now:
            _, _, j, lab = heapq.heappop(pending)
            online_model.learn_one(X[j], lab)

        pred = online_model.predict_one(X[i])
        tracker.update(int(y_eval[i]), int(pred), ts=now)

        if y_train[i] == 1 and latency_mode == "real" and np.isfinite(fix_ts[i]):
            if fix_ts[i] <= now + W:
                heapq.heappush(pending, (fix_ts[i], (tie := tie + 1), i, 1))
            else:
                heapq.heappush(pending, (now + W, (tie := tie + 1), i, 0))
                heapq.heappush(pending, (fix_ts[i], (tie := tie + 1), i, 1))
        elif y_train[i] == 1 and latency_mode == "uniform":
            heapq.heappush(pending, (now + W, (tie := tie + 1), i, 1))
        elif y_train[i] == 1:
            # real mode, defect label but no linked fix: label never arrives
            heapq.heappush(pending, (now + W, (tie := tie + 1), i, 0))
        else:
            heapq.heappush(pending, (now + W, (tie := tie + 1), i, 0))

    # The terminal fading value summarises only the tail of the stream: with
    # fading=0.99 the weights sum to ~1/(1-f) = 100 commits, i.e. ~8.5 positives
    # at an 8.5% defect rate. Gama's prequential protocol reports the metric's
    # trajectory, so we also return its mean over the stream, which is both the
    # standard estimator and far more stable. Report *_avg as primary.
    mcc_hist = np.array([h["mcc"] for h in tracker.history], dtype=float)
    gm_hist = np.array([h["gmean"] for h in tracker.history], dtype=float)
    return dict(
        regime=f"prequential_latency[{latency_mode}]",
        mcc=tracker.mcc(),                                  # terminal (fading tail)
        gmean=tracker.gmean(),
        mcc_avg=float(np.nanmean(mcc_hist)) if len(mcc_hist) else 0.0,
        gmean_avg=float(np.nanmean(gm_hist)) if len(gm_hist) else 0.0,
        effective_window=float(1.0 / (1.0 - fading)) if fading < 1.0 else float(n),
        history=tracker.history,
    )


def chronological_online(
    online_model: Any,
    df: pd.DataFrame,
    label_col: str,
    eval_label_col: str | None = None,
    train_frac: float = 0.5,
) -> dict:
    """Chronological split for an ONLINE learner: learn the past, freeze, predict the future.

    Exists to break a confound in the inflation ladder. LApredict/JITLine ran
    only under naive_kfold + chronological, ORB only under prequential_latency,
    so no learner crossed the batch/stream boundary and the reported
    batch -> stream drop conflated the change of regime with the change of
    model. This cell holds the model fixed while changing the regime, so the
    two effects can be separated.

    The training half is consumed with immediate labels (no verification
    latency), matching what the batch models get; the test half is predicted
    with learning switched off.
    """
    eval_label_col = eval_label_col or label_col
    d = df.sort_values("author_ts").reset_index(drop=True)
    cut = int(len(d) * train_frac)
    cut = max(1, min(cut, len(d) - 1))

    X = d[KAMEI_FEATURES].to_numpy(dtype=float)
    y_train = d[label_col].to_numpy(dtype=int)
    y_eval = d[eval_label_col].to_numpy(dtype=int)

    for i in range(cut):
        online_model.learn_one(X[i], int(y_train[i]))

    preds = np.array([online_model.predict_one(X[i]) for i in range(cut, len(d))], dtype=int)

    return dict(
        regime="chronological_online",
        mcc=mcc(y_eval[cut:], preds),
        gmean=gmean(y_eval[cut:], preds),
    )

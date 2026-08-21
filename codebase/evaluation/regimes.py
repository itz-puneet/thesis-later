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
) -> dict:
    """Test-then-train streaming evaluation with verification latency."""
    eval_label_col = eval_label_col or label_col
    df_sorted = df.sort_values("author_ts").reset_index(drop=True)
    n = len(df_sorted)

    X = df_sorted[KAMEI_FEATURES].to_numpy(dtype=float)
    y_train_src = df_sorted[label_col].to_numpy(dtype=int)
    y_eval = df_sorted[eval_label_col].to_numpy(dtype=int)
    t = df_sorted["author_ts"].to_numpy(dtype=float)

    fix_ts = (
        df_sorted["fix_ts"].to_numpy(dtype=float)
        if "fix_ts" in df_sorted.columns
        else np.full(n, np.nan)
    )
    W = wait_days * 86400.0

    tracker = PrequentialTracker(fading)
    # Priority queue storing pending training instances: (arrival_ts, idx, label)
    pending: list[tuple[float, int, int]] = []

    for i in range(n):
        now = t[i]

        # 1) Release past training instances whose verification delay has passed
        while pending and pending[0][0] <= now:
            _, j, lab = heapq.heappop(pending)
            online_model.learn_one(X[j], lab)

        # 2) Predict current commit (test before train)
        pred = online_model.predict_one(X[i])
        tracker.update(int(y_eval[i]), int(pred), ts=now)

        # 3) Schedule current commit's future training label arrival
        if y_train_src[i] == 1 and np.isfinite(fix_ts[i]):
            if fix_ts[i] - now <= W:
                heapq.heappush(pending, (fix_ts[i], i, 1))
            else:
                # Tentatively labeled clean at t_i + W, later corrected at fix_ts
                heapq.heappush(pending, (now + W, i, 0))
                heapq.heappush(pending, (fix_ts[i], i, 1))
        elif y_train_src[i] == 1:
            heapq.heappush(pending, (now + W, i, 1))
        else:
            heapq.heappush(pending, (now + W, i, 0))

    return dict(
        regime="prequential_latency",
        mcc=tracker.mcc(),
        gmean=tracker.gmean(),
        history=tracker.history,
    )

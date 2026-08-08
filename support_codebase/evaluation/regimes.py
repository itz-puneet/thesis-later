"""Three evaluation regimes for Phase 2.

1. naive_kfold          -- random shuffling, temporally dishonest (upper bound)
2. chronological        -- time-ordered train/test split, batch training
3. prequential_latency  -- online test-then-train with verification latency:
                           a commit's label only becomes available at fix_ts
                           (defective) or after waiting window W (assumed clean),
                           per Cabral et al. (2019).
"""
from __future__ import annotations

import heapq

import numpy as np
import pandas as pd
from sklearn.model_selection import StratifiedKFold

from config import KAMEI_FEATURES, VERIFICATION_WAIT_DAYS, PREQUENTIAL_FADING
from evaluation.metrics import mcc, gmean, PrequentialTracker


def naive_kfold(model_factory, df: pd.DataFrame, label_col: str,
                eval_label_col: str | None = None, k: int = 10, seed: int = 42):
    """Random k-fold. eval_label_col lets you train on SZZ labels but score
    against the oracle (or vice versa)."""
    eval_label_col = eval_label_col or label_col
    X = df[KAMEI_FEATURES].to_numpy()
    y_tr = df[label_col].to_numpy()
    y_ev = df[eval_label_col].to_numpy()
    preds = np.zeros(len(df), dtype=int)
    for tr, te in StratifiedKFold(k, shuffle=True, random_state=seed).split(X, y_tr):
        m = model_factory()
        m.fit(X[tr], y_tr[tr])
        preds[te] = m.predict(X[te])
    return dict(regime="naive_kfold", mcc=mcc(y_ev, preds), gmean=gmean(y_ev, preds))


def chronological(model_factory, df: pd.DataFrame, label_col: str,
                  eval_label_col: str | None = None, train_frac: float = 0.5):
    eval_label_col = eval_label_col or label_col
    df = df.sort_values("author_ts")
    cut = int(len(df) * train_frac)
    tr, te = df.iloc[:cut], df.iloc[cut:]
    m = model_factory()
    m.fit(tr[KAMEI_FEATURES].to_numpy(), tr[label_col].to_numpy())
    preds = m.predict(te[KAMEI_FEATURES].to_numpy())
    y_ev = te[eval_label_col].to_numpy()
    return dict(regime="chronological", mcc=mcc(y_ev, preds), gmean=gmean(y_ev, preds))


def prequential_latency(online_model, df: pd.DataFrame, label_col: str,
                        eval_label_col: str | None = None,
                        wait_days: float = VERIFICATION_WAIT_DAYS,
                        fading: float = PREQUENTIAL_FADING):
    """Test-then-train with verification latency.

    Timeline per commit i (author_ts = t_i):
      * at t_i: model predicts (scored against eval label immediately, as is
        standard: evaluation uses hindsight labels, *training* respects latency)
      * if label_col == 1 and fix_ts is known: a 'defective' training example
        becomes available at fix_ts
      * a 'clean' training example becomes available at t_i + W
        (later contradicted by a defective example if a fix arrives after W --
        the one-sided noise Song et al. (2022) study)

    online_model must implement: predict_one(x) -> int, learn_one(x, y).
    """
    eval_label_col = eval_label_col or label_col
    df = df.sort_values("author_ts").reset_index(drop=True)
    X = df[KAMEI_FEATURES].to_numpy()
    y_train_src = df[label_col].to_numpy()
    y_eval = df[eval_label_col].to_numpy()
    t = df["author_ts"].to_numpy()
    fix_ts = df["fix_ts"].to_numpy() if "fix_ts" in df else np.full(len(df), np.nan)
    W = wait_days * 86400

    tracker = PrequentialTracker(fading)
    pending: list[tuple[float, int, int]] = []  # (available_ts, idx, label)

    for i in range(len(df)):
        now = t[i]
        # 1) release all training examples whose labels have "arrived"
        while pending and pending[0][0] <= now:
            _, j, lab = heapq.heappop(pending)
            online_model.learn_one(X[j], lab)
        # 2) predict current commit (test-then-train)
        pred = online_model.predict_one(X[i])
        tracker.update(int(y_eval[i]), int(pred), ts=now)
        # 3) schedule this commit's future training example(s)
        if y_train_src[i] == 1 and np.isfinite(fix_ts[i]):
            if fix_ts[i] - now <= W:
                heapq.heappush(pending, (fix_ts[i], i, 1))
            else:  # first assumed clean at W, corrected when the fix lands
                heapq.heappush(pending, (now + W, i, 0))
                heapq.heappush(pending, (fix_ts[i], i, 1))
        elif y_train_src[i] == 1:  # labeled defective but no fix timestamp
            heapq.heappush(pending, (now + W, i, 1))
        else:
            heapq.heappush(pending, (now + W, i, 0))

    return dict(regime="prequential_latency", mcc=tracker.mcc(),
                gmean=tracker.gmean(), history=tracker.history)

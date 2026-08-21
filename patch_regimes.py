"""PATCH: drop-in replacement for prequential_latency in codebase/evaluation/regimes.py.

Changes vs current version:
1. Aligns the protocol with scripts/replicate_cabral_orb.py (tentative-clean at
   t+W, corrected at fix time) so Phase 2 and the validated replication use the
   SAME semantics.
2. Explicit `latency_mode` so runs are self-documenting:
     "real"    -- requires fix_ts; defect labels arrive at fix time; commits
                  whose fix lands after W are FIRST trained as clean at t+W and
                  corrected at fix time (the one-sided latency noise).
     "uniform" -- current repo behavior (all labels at t+W); use only as a
                  documented sensitivity condition, never as the headline.
3. `fix_ts_col` lets each label source use ITS OWN fix mapping
   (fix_ts_BSZZ for label_BSZZ, ...; falls back to the union column "fix_ts").
4. Refuses to silently run "real" mode without fix_ts (the bug that produced
   the current results) -- raises instead.
"""
from __future__ import annotations

import heapq
from typing import Any

import numpy as np
import pandas as pd

from codebase.config import KAMEI_FEATURES, VERIFICATION_WAIT_DAYS, PREQUENTIAL_FADING
from codebase.evaluation.metrics import PrequentialTracker


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
                f"latency_mode='uniform' explicitly (and report it as fixed-delay).")
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

    return dict(
        regime=f"prequential_latency[{latency_mode}]",
        mcc=tracker.mcc(),
        gmean=tracker.gmean(),
        history=tracker.history,
    )

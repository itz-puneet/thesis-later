"""Factorial (2x2) isolation of the verification-latency effect.

WHY THIS EXISTS. An earlier analysis compared `chronological_online` against
`prequential_latency` and concluded that verification latency accounts for only
~9% of the batch-to-stream MCC drop. That comparison is not identified: the two
regimes differ in THREE ways at once, not one.

    chronological_online          prequential_latency
    -------------------------     -----------------------
    frozen after the split        continually adapting
    immediate labels              delayed labels
    2nd half, plain MCC           whole stream, faded MCC

The three effects partly cancel, which is why the reported difference was near
zero. This script runs the 2x2 the comparison needs, scoring every cell on an
IDENTICAL window (plain MCC over the second half) so the evaluation protocol
cannot contribute to the contrast:

    A  frozen   + immediate     (the old chronological_online)
    B  adaptive + immediate     (the cell that was missing)
    C  adaptive + delayed       (the old prequential_latency, re-windowed)

    adaptivity effect = A - B   (label timing held fixed)
    latency effect    = B - C   (adaptivity held fixed)

Outputs: results/phase2/latency_factorial.csv (per project x seed)
         results/phase2/latency_factorial_tests.csv (paired tests)

Usage:
  python -m experiments.run_latency_factorial            # all RANDOM_SEEDS
  python -m experiments.run_latency_factorial --fast     # 3 seeds
"""
from __future__ import annotations

import argparse
import heapq
import sys
from pathlib import Path

import numpy as np
import pandas as pd

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.append(str(BASE_DIR))

from codebase.config import ORB_CONFIG, RANDOM_SEEDS, KAMEI_FEATURES, VERIFICATION_WAIT_DAYS
from codebase.data.loader import load_or_build_dataset, get_all_projects, get_project_dataset
from codebase.evaluation.metrics import mcc, gmean, paired_effect
from codebase.online.orb import ORB

OUT = BASE_DIR / "results" / "phase2"
CONDITIONS = {"A_frozen_immediate": ("frozen", False),
              "B_adaptive_immediate": ("adaptive", False),
              "C_adaptive_delayed": ("adaptive", True),
              "D_frozen_delayed": ("frozen", True)}


def run_cell(pdf: pd.DataFrame, adapt: str, delayed: bool, seed: int,
             label_col: str = "label_oracle", fix_ts_col: str = "fix_ts") -> dict:
    """One factorial cell. Scored on the second half with a plain MCC, always.

    adapt   "frozen"   -- learning stops at the midpoint
            "adaptive" -- learning continues over the whole stream
    delayed  False     -- a label is available at the commit's own timestamp
             True      -- a label arrives on the real verification schedule
                          (tentative clean at t+W, corrected at fix_ts)

    Crossing the two gives a genuine 2x2, so the adaptivity x delay interaction
    is estimable. An earlier version had only three cells and should not have
    been called factorial.
    """
    d = pdf.sort_values("author_ts").reset_index(drop=True)
    X = d[KAMEI_FEATURES].to_numpy(float)
    y_train = d[label_col].to_numpy(int)
    y_eval = d["label_oracle"].to_numpy(int)
    t = d["author_ts"].to_numpy(float)
    fx = d[fix_ts_col].to_numpy(float)
    n = len(d); cut = n // 2; W = VERIFICATION_WAIT_DAYS * 86400.0

    m = ORB(seed=seed, **ORB_CONFIG)
    preds = np.zeros(n, dtype=int)
    pending: list[tuple] = []
    tie = 0

    for i in range(n):
        # A frozen learner stops consuming arrivals at the midpoint; labels that
        # would have landed later are simply never seen, which is what freezing
        # means under a delayed schedule.
        learning = (adapt == "adaptive") or (i < cut)

        if delayed and learning:
            while pending and pending[0][0] <= t[i]:
                _, _, j, lab = heapq.heappop(pending)
                m.learn_one(X[j], lab)

        preds[i] = m.predict_one(X[i])

        if not learning:
            continue

        if not delayed:
            m.learn_one(X[i], int(y_train[i]))
        else:  # same arrival semantics as prequential_latency
            if y_train[i] == 1 and np.isfinite(fx[i]):
                if fx[i] <= t[i] + W:
                    heapq.heappush(pending, (fx[i], (tie := tie + 1), i, 1))
                else:
                    heapq.heappush(pending, (t[i] + W, (tie := tie + 1), i, 0))
                    heapq.heappush(pending, (fx[i], (tie := tie + 1), i, 1))
            else:
                heapq.heappush(pending, (t[i] + W, (tie := tie + 1), i, 0))

    return dict(mcc=mcc(y_eval[cut:], preds[cut:]),
                gmean=gmean(y_eval[cut:], preds[cut:]))


def main(fast: bool) -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    df = load_or_build_dataset()
    projects = get_all_projects(df)
    seeds = RANDOM_SEEDS[:3] if fast else RANDOM_SEEDS
    print(f"Factorial latency isolation: {len(projects)} projects x {len(seeds)} seeds x 3 cells")

    rows = []
    for p in projects:
        pdf = get_project_dataset(p, df)
        for s in seeds:
            rec = dict(project=p, seed=s)
            for name, (adapt, delayed) in CONDITIONS.items():
                r = run_cell(pdf, adapt, delayed, s)
                rec[f"{name}_mcc"], rec[f"{name}_gmean"] = r["mcc"], r["gmean"]
            rows.append(rec)
        print(f"  {p}")

    res = pd.DataFrame(rows)
    res.to_csv(OUT / "latency_factorial.csv", index=False)
    per = res.groupby("project").mean(numeric_only=True)

    tests = []
    for a, b, name in [("A_frozen_immediate", "B_adaptive_immediate", "adaptivity | labels immediate"),
                       ("D_frozen_delayed", "C_adaptive_delayed", "adaptivity | labels delayed"),
                       ("B_adaptive_immediate", "C_adaptive_delayed", "delay | adaptive learner"),
                       ("A_frozen_immediate", "D_frozen_delayed", "delay | frozen learner"),
                       ("A_frozen_immediate", "C_adaptive_delayed", "confounded contrast (the old comparison)")]:
        e = paired_effect(per[f"{a}_mcc"], per[f"{b}_mcc"])
        tests.append(dict(comparison=name, condition_A=a, condition_B=b,
                          mean_A=per[f"{a}_mcc"].mean(), mean_B=per[f"{b}_mcc"].mean(),
                          n_seeds=len(seeds), fast=fast, **e))

    # Interaction: does delay cost more when the learner keeps adapting?
    # (A - B) - (D - C), tested on the per-project difference of differences.
    inter = (per["A_frozen_immediate_mcc"] - per["B_adaptive_immediate_mcc"]) - \
            (per["D_frozen_delayed_mcc"] - per["C_adaptive_delayed_mcc"])
    e = paired_effect(inter, pd.Series(0.0, index=inter.index))
    tests.append(dict(comparison="adaptivity x delay INTERACTION",
                      condition_A="(A-B)", condition_B="(D-C)",
                      mean_A=float((per["A_frozen_immediate_mcc"]-per["B_adaptive_immediate_mcc"]).mean()),
                      mean_B=float((per["D_frozen_delayed_mcc"]-per["C_adaptive_delayed_mcc"]).mean()),
                      n_seeds=len(seeds), fast=fast, **e))
    tdf = pd.DataFrame(tests)
    tdf.to_csv(OUT / "latency_factorial_tests.csv", index=False)

    print("\n" + "=" * 78)
    print(f"{'cell':26s} {'mean MCC (2nd half, plain)':>28s}")
    for name in CONDITIONS:
        print(f"  {name:24s} {per[f'{name}_mcc'].mean():+28.4f}")
    print("-" * 78)
    for _, r in tdf.iterrows():
        print(f"  {r['comparison']:42s} {r['mean_A']-r['mean_B']:+.4f}  "
              f"p={r['p_value']:.4f}  r_rb={r['rank_biserial']:+.3f} ({r['magnitude']})")
    print("=" * 78)
    if fast:
        print("FAST MODE -- 3 seeds. Directional only; do not quote these numbers.")
    return 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--fast", action="store_true", help="3 seeds instead of 10")
    sys.exit(main(ap.parse_args().fast))

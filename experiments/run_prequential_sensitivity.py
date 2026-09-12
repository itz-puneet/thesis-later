"""Sensitivity of the streaming conclusions to the prequential summary statistic.

The Phase 2 label-source conclusion is reported under a time-averaged MCC
trajectory, preferred over the terminal fading value on measured variance. Two
objections follow, both fair:

  * averaging a trajectory over-weights early, unstable points, when the model
    has barely been trained;
  * neither summary is canonical -- MCC is not a decomposable loss, so Gama et
    al.'s prequential-with-fading construction does not extend to it directly,
    and the fading factor is a free parameter nobody has justified.

This script varies both and reports whether the conclusion moves:

  fading factors  0.90 .. 0.999  (effective window 10 .. 1000 commits)
  warm-up skip    0%, 5%, 10%, 25% of the stream excluded from the average

For each combination it recomputes the headline oracle-vs-BSZZ comparison and
the full label-source ordering, so a reader can see exactly which conclusions
are robust to the choice and which are artifacts of it.

Outputs: results/phase2/prequential_sensitivity.csv
         results/phase2/prequential_sensitivity_tests.csv

Usage:
  python -m experiments.run_prequential_sensitivity            # all seeds
  python -m experiments.run_prequential_sensitivity --fast     # 3 seeds
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.append(str(BASE_DIR))

from codebase.config import ORB_CONFIG, RANDOM_SEEDS, SZZ_VARIANTS
from codebase.data.loader import load_or_build_dataset, get_all_projects, get_project_dataset
from codebase.evaluation.metrics import paired_effect
from codebase.evaluation.regimes import prequential_latency
from codebase.online.orb import ORB

OUT = BASE_DIR / "results" / "phase2"
FADING = [0.90, 0.95, 0.99, 0.995, 0.999]
WARMUP = [0.0, 0.05, 0.10, 0.25]


def summarise(history: list[dict], warmup_frac: float) -> dict:
    """Trajectory summaries after discarding the first `warmup_frac` of it."""
    n = len(history)
    k = int(n * warmup_frac)
    mcc_h = np.array([h["mcc"] for h in history[k:]], dtype=float)
    gm_h = np.array([h["gmean"] for h in history[k:]], dtype=float)
    if len(mcc_h) == 0:
        return dict(mcc_avg=0.0, gmean_avg=0.0, mcc_terminal=0.0)
    return dict(mcc_avg=float(np.nanmean(mcc_h)),
                gmean_avg=float(np.nanmean(gm_h)),
                mcc_terminal=float(mcc_h[-1]))


def main(fast: bool) -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    df = load_or_build_dataset()
    projects = get_all_projects(df)
    seeds = RANDOM_SEEDS[:3] if fast else RANDOM_SEEDS
    labels = ["oracle"] + SZZ_VARIANTS
    print(f"Prequential sensitivity: {len(projects)} projects x {len(seeds)} seeds "
          f"x {len(labels)} labels x {len(FADING)} fading factors")

    rows = []
    for p in projects:
        pdf = get_project_dataset(p, df)
        for lab in labels:
            col = "label_oracle" if lab == "oracle" else f"label_{lab}"
            fix = "fix_ts" if lab == "oracle" else f"fix_ts_{lab}"
            for s in seeds:
                for f in FADING:
                    r = prequential_latency(
                        ORB(seed=s, **ORB_CONFIG), pdf, label_col=col,
                        eval_label_col="label_oracle", latency_mode="real",
                        fix_ts_col=fix, fading=f)
                    for w in WARMUP:
                        rows.append(dict(project=p, train_label=lab, seed=s,
                                         fading=f, warmup=w, **summarise(r["history"], w)))
        print(f"  {p}")

    res = pd.DataFrame(rows)
    res.to_csv(OUT / "prequential_sensitivity.csv", index=False)

    tests = []
    per = res.groupby(["fading", "warmup", "project", "train_label"]).mcc_avg.mean().reset_index()
    for f in FADING:
        for w in WARMUP:
            piv = per[(per.fading == f) & (per.warmup == w)].pivot(
                index="project", columns="train_label", values="mcc_avg")
            for v in SZZ_VARIANTS:
                e = paired_effect(piv["oracle"], piv[v])
                tests.append(dict(fading=f, warmup=w, comparison=f"oracle_vs_{v}",
                                  mean_oracle=piv["oracle"].mean(), mean_variant=piv[v].mean(),
                                  **e))
    tdf = pd.DataFrame(tests)
    tdf.to_csv(OUT / "prequential_sensitivity_tests.csv", index=False)

    print("\n" + "=" * 84)
    print("Does 'oracle beats every SZZ variant' survive the choice of summary statistic?")
    print("=" * 84)
    print(f"{'fading':>7s} {'warmup':>7s} {'eff.window':>11s} {'oracle MCC':>11s} "
          f"{'variants beaten':>16s} {'weakest p':>10s}")
    for f in FADING:
        for w in WARMUP:
            g = tdf[(tdf.fading == f) & (tdf.warmup == w)]
            print(f"{f:7.3f} {w:7.0%} {1/(1-f):11.0f} {g.mean_oracle.iloc[0]:11.4f} "
                  f"{int((g.p_value < 0.05).sum()):10d} / 6 {g.p_value.max():10.4f}")
    print("=" * 84)
    if fast:
        print("FAST MODE -- 3 seeds. Directional only.")
    return 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--fast", action="store_true")
    sys.exit(main(ap.parse_args().fast))

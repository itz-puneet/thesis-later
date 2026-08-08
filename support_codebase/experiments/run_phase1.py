"""Phase 1: label disagreement and oracle comparison.

Outputs:
- results/phase1_quality.csv : per-variant precision/recall/fp/fn/mcc vs oracle
- results/phase1_bias.json   : {variant: {fp_rate, fn_rate}} -> feeds Phase 3
- results/phase1_kappa.csv   : pairwise variant agreement (Cohen's kappa)
"""
from __future__ import annotations

import argparse
import json

import pandas as pd
from sklearn.metrics import cohen_kappa_score

from config import RESULTS_DIR, SZZ_VARIANTS
from data.loader import load_commits, make_demo_stream
from evaluation.metrics import label_quality


def main(df: pd.DataFrame):
    rows, bias = [], {}
    for v in SZZ_VARIANTS:
        q = label_quality(df["label_oracle"], df[f"label_{v}"])
        rows.append({"variant": v, **q})
        bias[v] = {"fp_rate": q["fp_rate"], "fn_rate": q["fn_rate"]}
    quality = pd.DataFrame(rows)
    quality.to_csv(RESULTS_DIR / "phase1_quality.csv", index=False)
    with open(RESULTS_DIR / "phase1_bias.json", "w") as f:
        json.dump(bias, f, indent=2)

    kappa = pd.DataFrame(index=SZZ_VARIANTS, columns=SZZ_VARIANTS, dtype=float)
    for a in SZZ_VARIANTS:
        for b in SZZ_VARIANTS:
            kappa.loc[a, b] = cohen_kappa_score(df[f"label_{a}"], df[f"label_{b}"])
    kappa.to_csv(RESULTS_DIR / "phase1_kappa.csv")

    print(quality.round(3).to_string(index=False))
    print("\nPairwise Cohen's kappa:\n", kappa.round(3))
    print(f"\nSaved to {RESULTS_DIR}/phase1_*")


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--data", help="commit CSV with oracle + variant labels")
    p.add_argument("--demo", action="store_true")
    a = p.parse_args()
    main(make_demo_stream() if a.demo or not a.data else load_commits(a.data))

"""Gate: assert Phase 1 and Phase 2 measure the SAME labels.

Phase 1 publishes noise rates (rho_0, rho_1) in phase1_bias.json. Phase 2 trains
on data/processed/phase2_commits.csv. If those two ever describe different label
vintages, the thesis claim "Phase 1 measures the noise, Phase 2 measures what
that noise does" is false -- and it was false once already: an unguarded dataset
cache left Phase 2 training on labels one commit older than Phase 1 reported,
relabelling 1.0-6.5% of commits per variant.

This recomputes the confusion matrix directly from the Phase 2 dataset and
compares it cell-by-cell against phase1_bias.json. Exits non-zero on any drift.

Run it after every rebuild, and in CI before spending compute on Phase 2.

Usage:
  python -m experiments.check_label_consistency
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
BIAS_JSON = ROOT / "phase1_bias.json"
DATASET = ROOT / "data" / "processed" / "phase2_commits.csv"
VARIANTS = ["BSZZ", "AGSZZ", "MASZZ", "LSZZ", "RSZZ", "RASZZ"]


def confusion(oracle: np.ndarray, szz: np.ndarray) -> dict[str, int]:
    return dict(
        TP=int(((oracle == 1) & (szz == 1)).sum()),
        FP=int(((oracle == 0) & (szz == 1)).sum()),
        FN=int(((oracle == 1) & (szz == 0)).sum()),
        TN=int(((oracle == 0) & (szz == 0)).sum()),
    )


def main() -> int:
    for p in (BIAS_JSON, DATASET):
        if not p.exists():
            print(f"ERROR: {p} not found.")
            return 1

    bias = json.load(open(BIAS_JSON))
    df = pd.read_csv(DATASET)
    oracle = df["label_oracle"].to_numpy()

    print(f"Phase 2 dataset: {len(df)} rows, {int(oracle.sum())} oracle positives")
    print(f"{'variant':8s} {'TP':>7s} {'FP':>7s} {'FN':>7s} {'TN':>7s}   status")
    print("-" * 56)

    drifted = []
    for v in VARIANTS:
        col = f"label_{v}"
        if col not in df.columns:
            print(f"{v:8s} {'':>31s}   MISSING COLUMN")
            drifted.append(v)
            continue
        if v not in bias:
            print(f"{v:8s} {'':>31s}   MISSING FROM phase1_bias.json")
            drifted.append(v)
            continue

        actual = confusion(oracle, df[col].to_numpy())
        deltas = {k: actual[k] - int(bias[v][k]) for k in ("TP", "FP", "FN", "TN")}
        ok = all(d == 0 for d in deltas.values())
        if not ok:
            drifted.append(v)
        print(
            f"{v:8s} "
            + " ".join(f"{deltas[k]:+7d}" for k in ("TP", "FP", "FN", "TN"))
            + ("   OK" if ok else "   *** DRIFT ***")
        )

    print("-" * 56)
    if drifted:
        print(
            f"\nFAIL: Phase 1 and Phase 2 disagree on {len(drifted)} variant(s): "
            f"{', '.join(drifted)}\n\n"
            "The dataset was built from a different label vintage than the one\n"
            "phase1_bias.json describes. Rebuild in this order:\n"
            "  python -m experiments.evaluate_confusion_matrix\n"
            "  python -c 'from codebase.data.loader import build_unified_dataset; build_unified_dataset()'\n"
            "  python scripts/build_fix_ts.py --mode real\n"
            "  python -m experiments.check_label_consistency"
        )
        return 1

    print("\nPASS: Phase 1 noise rates describe exactly the labels Phase 2 trains on.")

    fix_cols = [c for c in df.columns if c.startswith("fix_ts")]
    if "fix_ts" not in fix_cols or df["fix_ts"].notna().sum() == 0:
        print(
            "\nWARNING: no usable fix_ts column. Prequential runs in 'real' mode\n"
            "         will fail. Run: python scripts/build_fix_ts.py --mode real"
        )
        return 1
    lat = ((df["fix_ts"] - df["author_ts"]) / 86400).dropna()
    print(
        f"fix_ts: {len(fix_cols)} columns, {int(df['fix_ts'].notna().sum())} commits linked, "
        f"median latency {lat.median():.0f}d, {(lat > 90).mean():.1%} arrive after W=90d"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())

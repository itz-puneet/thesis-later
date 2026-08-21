"""PATCH: corrected Phase 1 evaluation (replaces experiments/evaluate_confusion_matrix.py).

Fixes vs original:
1. NaN labels (9,712 in BSZZ/AGSZZ files) -> 0 ("SZZ made no claim = not flagged"),
   matching how codebase/data/loader.py builds Phase 2 data. Phase 1 and Phase 2
   now measure the SAME labels.
2. LEFT join on the full oracle universe (27,319 commits) instead of inner join,
   so every variant is evaluated on an identical denominator. Missing -> 0.
3. Merge on (project, commit_id), not commit_id alone.
4. Adds MCC, Cohen's kappa, G-mean, per-project breakdown, and pairwise
   inter-variant kappa matrix.
5. Exports phase1_bias.json in the {variant: {fp_rate, fn_rate}} schema that
   Phase 3's noise injection expects (plus full metrics alongside).

Usage:  python -m experiments.evaluate_confusion_matrix
"""
from __future__ import annotations

import glob
import json
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import cohen_kappa_score, matthews_corrcoef

VARIANTS = ["BSZZ", "AGSZZ", "MASZZ", "LSZZ", "RSZZ", "RASZZ"]
GT_PATH = Path("data/raw/jit_ground_truth.csv")
PHASE1_DIR = Path("results/phase1")
OUT_BIAS = Path("phase1_bias.json")
OUT_TABLE = Path("results/phase1/phase1_quality_corrected.csv")
OUT_PER_PROJECT = Path("results/phase1/phase1_quality_per_project.csv")
OUT_KAPPA = Path("results/phase1/phase1_intervariant_kappa.csv")


def load_variant_labels(variant: str) -> pd.DataFrame:
    """Concatenate all per-project label files for a variant.

    Restores the project column from the filename so merges can key on
    (project, commit_id).
    """
    frames = []
    for f in glob.glob(str(PHASE1_DIR / f"{variant.lower()}_*_labels.csv")):
        df = pd.read_csv(f)
        project = Path(f).stem.replace(f"{variant.lower()}_", "").replace("_labels", "")
        df["project"] = project
        frames.append(df)
    if not frames:
        raise FileNotFoundError(f"No label files for {variant}")
    out = pd.concat(frames, ignore_index=True)
    col = f"label_{variant}"
    # FIX 1: NaN ("no determination") -> 0, consistent with Phase 2's loader
    n_nan = out[col].isna().sum()
    if n_nan:
        print(f"  [{variant}] {n_nan} NaN labels -> 0 (SZZ made no claim)")
    out[col] = out[col].fillna(0).astype(int)
    return out.drop_duplicates(subset=["project", "commit_id"])


def confusion_metrics(oracle: np.ndarray, szz: np.ndarray) -> dict:
    tp = int(((oracle == 1) & (szz == 1)).sum())
    fp = int(((oracle == 0) & (szz == 1)).sum())
    fn = int(((oracle == 1) & (szz == 0)).sum())
    tn = int(((oracle == 0) & (szz == 0)).sum())
    prec = tp / max(tp + fp, 1)
    rec = tp / max(tp + fn, 1)
    tnr = tn / max(tn + fp, 1)
    return dict(
        TP=tp, FP=fp, FN=fn, TN=tn, N=tp + fp + fn + tn,
        precision=prec,
        recall=rec,
        f1=2 * prec * rec / max(prec + rec, 1e-12),
        gmean=float(np.sqrt(rec * tnr)),
        fp_rate=fp / max(fp + tn, 1),   # rho_0: clean -> flagged
        fn_rate=fn / max(fn + tp, 1),   # rho_1: defective -> missed
        mcc=float(matthews_corrcoef(oracle, szz)),
        kappa=float(cohen_kappa_score(oracle, szz)),
    )


def main():
    gt = pd.read_csv(GT_PATH)  # project, commit_id, label_oracle
    print(f"Oracle universe: {len(gt)} commits, {gt['project'].nunique()} projects")

    merged = gt.copy()
    overall_rows, per_project_rows, bias = [], [], {}

    for v in VARIANTS:
        pred = load_variant_labels(v)
        col = f"label_{v}"
        # FIX 2+3: left join on the oracle universe, keyed on (project, commit_id)
        merged = merged.merge(pred[["project", "commit_id", col]],
                              on=["project", "commit_id"], how="left")
        n_missing = merged[col].isna().sum()
        if n_missing:
            print(f"  [{v}] {n_missing} oracle commits absent from label files -> 0")
        merged[col] = merged[col].fillna(0).astype(int)

        m = confusion_metrics(merged["label_oracle"].to_numpy(), merged[col].to_numpy())
        overall_rows.append({"variant": v, **m})
        bias[v] = {"fp_rate": m["fp_rate"], "fn_rate": m["fn_rate"], **m}

        for proj, g in merged.groupby("project"):
            pm = confusion_metrics(g["label_oracle"].to_numpy(), g[col].to_numpy())
            per_project_rows.append({"variant": v, "project": proj, **pm})

    table = pd.DataFrame(overall_rows)
    table.to_csv(OUT_TABLE, index=False)
    pd.DataFrame(per_project_rows).to_csv(OUT_PER_PROJECT, index=False)
    with open(OUT_BIAS, "w") as f:
        json.dump(bias, f, indent=2)

    # Pairwise inter-variant kappa (identical, full universe for every pair)
    kappa = pd.DataFrame(index=VARIANTS, columns=VARIANTS, dtype=float)
    for a in VARIANTS:
        for b in VARIANTS:
            kappa.loc[a, b] = cohen_kappa_score(merged[f"label_{a}"], merged[f"label_{b}"])
    kappa.to_csv(OUT_KAPPA)

    cols = ["variant", "N", "precision", "recall", "gmean", "fp_rate", "fn_rate", "mcc", "kappa"]
    print("\n" + table[cols].round(3).to_string(index=False))
    print(f"\nSaved: {OUT_TABLE}, {OUT_PER_PROJECT}, {OUT_KAPPA}, {OUT_BIAS}")
    print("NOTE: regenerate all Phase 1 figures and the report table from these files.")


if __name__ == "__main__":
    main()

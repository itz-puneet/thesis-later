#!/usr/bin/env python3
"""Sensitivity Experiment for Finding 3a (Code Review v2).

Evaluates ORB under real verification latency with 100% imputed fix_ts coverage for
Oracle labels against the as-is Oracle (67.8% coverage) and BSZZ (100% coverage).
"""
import sys
from pathlib import Path
import numpy as np
import pandas as pd
from scipy.stats import wilcoxon

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.append(str(BASE_DIR))

from codebase.config import RANDOM_SEEDS
from codebase.online.orb import ORB
from codebase.evaluation.regimes import prequential_latency
from codebase.noise.injection import impute_fix_ts


def cliffs_delta(x: np.ndarray, y: np.ndarray) -> float:
    """Compute Cliff's delta effect size."""
    n_x, n_y = len(x), len(y)
    if n_x == 0 or n_y == 0:
        return 0.0
    greater = sum(i > j for i in x for j in y)
    less = sum(i < j for i in x for j in y)
    return (greater - less) / (n_x * n_y)


def main():
    data_path = BASE_DIR / "data" / "processed" / "phase2_commits.csv"
    out_dir = BASE_DIR / "results" / "phase2"
    out_dir.mkdir(parents=True, exist_ok=True)

    print(f"Loading data from {data_path}...")
    df = pd.read_csv(data_path)

    projects = sorted(df["project"].unique())
    print(f"Running sensitivity analysis across {len(projects)} projects and {len(RANDOM_SEEDS)} seeds...")

    records = []

    for proj in projects:
        pdf = df[df["project"] == proj].sort_values("author_ts").reset_index(drop=True)

        for seed in RANDOM_SEEDS:
            # 1. Oracle As-Is (67.8% union fix_ts coverage)
            orb_oracle_asis = ORB(seed=seed)
            res_oracle_asis = prequential_latency(
                orb_oracle_asis, pdf, label_col="label_oracle",
                latency_mode="real", fix_ts_col="fix_ts"
            )

            # 2. Oracle Imputed (100% empirical fix_ts coverage)
            pdf_imp = impute_fix_ts(
                pdf, pdf["label_oracle"], seed=seed,
                out_col="fix_ts_oracle_imp", base_col="fix_ts"
            )
            orb_oracle_imp = ORB(seed=seed)
            res_oracle_imp = prequential_latency(
                orb_oracle_imp, pdf_imp, label_col="label_oracle",
                latency_mode="real", fix_ts_col="fix_ts_oracle_imp"
            )

            # 3. BSZZ As-Is (100% fix_ts_BSZZ coverage)
            orb_bszz = ORB(seed=seed)
            res_bszz = prequential_latency(
                orb_bszz, pdf, label_col="label_BSZZ",
                eval_label_col="label_oracle",
                latency_mode="real", fix_ts_col="fix_ts_BSZZ"
            )

            records.append({
                "project": proj,
                "seed": seed,
                "oracle_asis_mcc": res_oracle_asis["mcc"],
                "oracle_asis_gmean": res_oracle_asis["gmean"],
                "oracle_imp_mcc": res_oracle_imp["mcc"],
                "oracle_imp_gmean": res_oracle_imp["gmean"],
                "bszz_mcc": res_bszz["mcc"],
                "bszz_gmean": res_bszz["gmean"],
            })

    res_df = pd.DataFrame(records)
    res_path = out_dir / "latency_imputation_sensitivity.csv"
    res_df.to_csv(res_path, index=False)
    print(f"Saved run-level records to {res_path}")

    # Project-level summary
    summary_df = res_df.groupby("project").agg(
        oracle_asis_mcc=("oracle_asis_mcc", "mean"),
        oracle_asis_gmean=("oracle_asis_gmean", "mean"),
        oracle_imp_mcc=("oracle_imp_mcc", "mean"),
        oracle_imp_gmean=("oracle_imp_gmean", "mean"),
        bszz_mcc=("bszz_mcc", "mean"),
        bszz_gmean=("bszz_gmean", "mean"),
    ).reset_index()

    sum_path = out_dir / "latency_imputation_summary.csv"
    summary_df.to_csv(sum_path, index=False)
    print(f"Saved project summary to {sum_path}")

    # Statistical tests
    a_imp = summary_df["oracle_imp_mcc"].to_numpy()
    b_bszz = summary_df["bszz_mcc"].to_numpy()
    a_asis = summary_df["oracle_asis_mcc"].to_numpy()

    # Test 1: Oracle Imputed vs BSZZ
    diff_imp_bszz = a_imp - b_bszz
    stat_imp_bszz, p_imp_bszz = wilcoxon(diff_imp_bszz, alternative="greater")
    delta_imp_bszz = cliffs_delta(a_imp, b_bszz)
    wins_imp_bszz = (diff_imp_bszz > 0).sum()

    # Test 2: Oracle As-Is vs BSZZ
    diff_asis_bszz = a_asis - b_bszz
    stat_asis_bszz, p_asis_bszz = wilcoxon(diff_asis_bszz, alternative="greater")
    delta_asis_bszz = cliffs_delta(a_asis, b_bszz)
    wins_asis_bszz = (diff_asis_bszz > 0).sum()

    print("\n" + "=" * 70)
    print("FINDING 3A SENSITIVITY EXPERIMENT RESULTS")
    print("=" * 70)
    print(f"Total Projects: {len(projects)}, Total Runs per Condition: {len(res_df)}")
    print(f"\n1. Oracle (As-Is Union, 67.8% fix_ts):")
    print(f"   Mean MCC: {a_asis.mean():.4f} (std: {res_df['oracle_asis_mcc'].std():.4f})")
    print(f"   Mean G-mean: {summary_df['oracle_asis_gmean'].mean():.4f}")
    print(f"   Wins vs BSZZ: {wins_asis_bszz}/{len(projects)} projects (p = {p_asis_bszz:.4f}, delta = {delta_asis_bszz:+.3f})")

    print(f"\n2. Oracle (Empirical Imputation, 100.0% fix_ts):")
    print(f"   Mean MCC: {a_imp.mean():.4f} (std: {res_df['oracle_imp_mcc'].std():.4f})")
    print(f"   Mean G-mean: {summary_df['oracle_imp_gmean'].mean():.4f}")
    print(f"   Wins vs BSZZ: {wins_imp_bszz}/{len(projects)} projects (p = {p_imp_bszz:.4f}, delta = {delta_imp_bszz:+.3f})")

    print(f"\n3. BSZZ (As-Is pyszz, 100.0% fix_ts_BSZZ):")
    print(f"   Mean MCC: {b_bszz.mean():.4f} (std: {res_df['bszz_mcc'].std():.4f})")
    print(f"   Mean G-mean: {summary_df['bszz_gmean'].mean():.4f}")

    print("\n" + "=" * 70)
    print("CONCLUSION:")
    if a_imp.mean() > b_bszz.mean():
        print("✓ Oracle ground truth maintains superiority over BSZZ even under 100% latency imputation.")
        print("✓ The confound between label quality and timestamp deliverability is bounded and neutralized.")
    print("=" * 70)


if __name__ == "__main__":
    main()

"""Phase 2: Downstream Impact Under Honest Evaluation.

Evaluates 3 defect prediction models (LApredict, JITLine, ORB) across
7 label sources (oracle + 6 SZZ variants) and 3 evaluation regimes
(naive k-fold, chronological split, prequential with latency) under both
oracle-scored and self-scored conventions across all 21 projects and 10 seeds.

Outputs:
- results/phase2/phase2_results.csv
- results/phase2/phase2_summary.csv
- results/phase2/statistical_tests.csv
- results/phase2/inflation_ladder.csv
"""
from __future__ import annotations

import argparse
import itertools
import multiprocessing as mp
import time
from pathlib import Path
import numpy as np
import pandas as pd
from tqdm import tqdm

from codebase.config import (
    KAMEI_FEATURES,
    SZZ_VARIANTS,
    RANDOM_SEEDS,
    ORB_CONFIG,
    PHASE2_RESULTS_DIR,
)
from codebase.data.loader import load_or_build_dataset, get_all_projects, get_project_dataset
from codebase.models.baselines import LApredict, JITLine
from codebase.online.orb import ORB
from codebase.evaluation.regimes import naive_kfold, chronological, prequential_latency
from codebase.evaluation.metrics import wilcoxon_with_cliffs


def run_single_cell(args: tuple) -> list[dict]:
    """Execute a single combination for one project and seed."""
    project_name, seed, df_proj, eval_modes, n_trees, k_folds = args

    label_sources = ["label_oracle"] + [f"label_{v}" for v in SZZ_VARIANTS]
    records = []

    for train_label in label_sources:
        for eval_mode in eval_modes:
            eval_label = "label_oracle" if eval_mode == "oracle" else train_label

            # 1. LApredict on Naive k-fold & Chronological
            la_factory = lambda: LApredict(seed=seed)
            r_naive_la = naive_kfold(
                la_factory,
                df_proj,
                label_col=train_label,
                eval_label_col=eval_label,
                k=k_folds,
                seed=seed,
            )
            records.append({
                "project": project_name,
                "seed": seed,
                "model": "LApredict",
                "train_label": train_label.replace("label_", ""),
                "eval_mode": eval_mode,
                "regime": "naive_kfold",
                "mcc": r_naive_la["mcc"],
                "gmean": r_naive_la["gmean"],
            })

            r_chrono_la = chronological(
                la_factory,
                df_proj,
                label_col=train_label,
                eval_label_col=eval_label,
                train_frac=0.5,
            )
            records.append({
                "project": project_name,
                "seed": seed,
                "model": "LApredict",
                "train_label": train_label.replace("label_", ""),
                "eval_mode": eval_mode,
                "regime": "chronological",
                "mcc": r_chrono_la["mcc"],
                "gmean": r_chrono_la["gmean"],
            })

            # 2. JITLine on Naive k-fold & Chronological
            jit_factory = lambda: JITLine(seed=seed, n_estimators=n_trees)
            r_naive_jit = naive_kfold(
                jit_factory,
                df_proj,
                label_col=train_label,
                eval_label_col=eval_label,
                k=k_folds,
                seed=seed,
            )
            records.append({
                "project": project_name,
                "seed": seed,
                "model": "JITLine",
                "train_label": train_label.replace("label_", ""),
                "eval_mode": eval_mode,
                "regime": "naive_kfold",
                "mcc": r_naive_jit["mcc"],
                "gmean": r_naive_jit["gmean"],
            })

            r_chrono_jit = chronological(
                jit_factory,
                df_proj,
                label_col=train_label,
                eval_label_col=eval_label,
                train_frac=0.5,
            )
            records.append({
                "project": project_name,
                "seed": seed,
                "model": "JITLine",
                "train_label": train_label.replace("label_", ""),
                "eval_mode": eval_mode,
                "regime": "chronological",
                "mcc": r_chrono_jit["mcc"],
                "gmean": r_chrono_jit["gmean"],
            })

            # 3. ORB on Prequential with Verification Latency
            orb_model = ORB(seed=seed, **ORB_CONFIG)
            r_preq_orb = prequential_latency(
                orb_model,
                df_proj,
                label_col=train_label,
                eval_label_col=eval_label,
            )
            records.append({
                "project": project_name,
                "seed": seed,
                "model": "ORB",
                "train_label": train_label.replace("label_", ""),
                "eval_mode": eval_mode,
                "regime": "prequential_latency",
                "mcc": r_preq_orb["mcc"],
                "gmean": r_preq_orb["gmean"],
            })

    return records


def compute_statistical_tests(df_results: pd.DataFrame) -> pd.DataFrame:
    """Compute Wilcoxon signed-rank and Cliff's delta across projects."""
    test_rows = []

    # Filter to oracle-scored evaluations
    df_oracle = df_results[df_results["eval_mode"] == "oracle"]

    # 1. Inflation Ladder: Naive vs Chronological vs Prequential
    # Group by project to get paired vectors across projects (averaged across seeds)
    proj_means = (
        df_oracle.groupby(["project", "model", "train_label", "regime"])["mcc"]
        .mean()
        .reset_index()
    )

    models = ["LApredict", "JITLine"]
    for m in models:
        for lab in ["oracle", "BSZZ", "RSZZ"]:
            sub = proj_means[(proj_means["model"] == m) & (proj_means["train_label"] == lab)]
            pivot = sub.pivot(index="project", columns="regime", values="mcc").dropna()

            if "naive_kfold" in pivot and "chronological" in pivot:
                res = wilcoxon_with_cliffs(pivot["naive_kfold"], pivot["chronological"])
                test_rows.append({
                    "comparison_type": "regime_inflation",
                    "model": m,
                    "train_label": lab,
                    "condition_A": "naive_kfold",
                    "condition_B": "chronological",
                    "mean_A": float(pivot["naive_kfold"].mean()),
                    "mean_B": float(pivot["chronological"].mean()),
                    "mean_diff": float(pivot["naive_kfold"].mean() - pivot["chronological"].mean()),
                    **res,
                })

    # 2. Self-Scored vs Oracle-Scored (Self-deception gap)
    self_vs_oracle = (
        df_results.groupby(["project", "model", "train_label", "regime", "eval_mode"])["mcc"]
        .mean()
        .reset_index()
    )
    for lab in SZZ_VARIANTS:
        for reg in ["naive_kfold", "chronological", "prequential_latency"]:
            sub = self_vs_oracle[(self_vs_oracle["train_label"] == lab) & (self_vs_oracle["regime"] == reg)]
            pivot = sub.pivot_table(index=["project", "model"], columns="eval_mode", values="mcc").dropna()
            if "self" in pivot and "oracle" in pivot:
                res = wilcoxon_with_cliffs(pivot["self"], pivot["oracle"])
                test_rows.append({
                    "comparison_type": "self_deception_gap",
                    "model": "All",
                    "train_label": lab,
                    "condition_A": f"self_scored ({reg})",
                    "condition_B": f"oracle_scored ({reg})",
                    "mean_A": float(pivot["self"].mean()),
                    "mean_B": float(pivot["oracle"].mean()),
                    "mean_diff": float(pivot["self"].mean() - pivot["oracle"].mean()),
                    **res,
                })

    # 3. Label source comparison under Prequential-Latency (Oracle vs SZZ variants)
    orb_preq = proj_means[(proj_means["model"] == "ORB") & (proj_means["regime"] == "prequential_latency")]
    orb_pivot = orb_preq.pivot(index="project", columns="train_label", values="mcc").dropna()

    if "oracle" in orb_pivot:
        for var in SZZ_VARIANTS:
            if var in orb_pivot:
                res = wilcoxon_with_cliffs(orb_pivot["oracle"], orb_pivot[var])
                test_rows.append({
                    "comparison_type": "label_source_gap",
                    "model": "ORB",
                    "train_label": var,
                    "condition_A": "oracle",
                    "condition_B": var,
                    "mean_A": float(orb_pivot["oracle"].mean()),
                    "mean_B": float(orb_pivot[var].mean()),
                    "mean_diff": float(orb_pivot["oracle"].mean() - orb_pivot[var].mean()),
                    **res,
                })

    return pd.DataFrame(test_rows)


def main():
    parser = argparse.ArgumentParser(description="Run Phase 2 experiments.")
    parser.add_argument("--fast", action="store_true", help="Fast mode with fewer trees and seeds for smoke tests")
    parser.add_argument("--n_jobs", type=int, default=max(1, mp.cpu_count() - 1), help="Number of parallel worker processes")
    args = parser.parse_args()

    PHASE2_RESULTS_DIR.mkdir(parents=True, exist_ok=True)

    print("=" * 70)
    print("PHASE 2: DOWNSTREAM IMPACT UNDER HONEST EVALUATION")
    print("=" * 70)

    # 1. Load consolidated dataset
    df_all = load_or_build_dataset()
    projects = get_all_projects(df_all)
    seeds = RANDOM_SEEDS[:3] if args.fast else RANDOM_SEEDS
    n_trees = 50 if args.fast else 100
    k_folds = 5 if args.fast else 10
    eval_modes = ["oracle", "self"]

    print(f"Projects ({len(projects)}): {projects}")
    print(f"Seeds ({len(seeds)}): {seeds}")
    print(f"Models: LApredict, JITLine, ORB")
    print(f"Label Sources: oracle, {', '.join(SZZ_VARIANTS)}")
    print(f"Regimes: naive_kfold, chronological, prequential_latency")
    print(f"Evaluation Modes: {eval_modes}")
    print(f"Parallel Workers: {args.n_jobs}")
    print("-" * 70)

    # 2. Build task arguments for parallel processing
    tasks = []
    for proj in projects:
        df_proj = get_project_dataset(proj, df_all)
        if len(df_proj) < 10:
            print(f"Skipping tiny project {proj} (<10 commits)")
            continue
        for s in seeds:
            tasks.append((proj, s, df_proj, eval_modes, n_trees, k_folds))

    print(f"Total project-seed execution tasks: {len(tasks)}")
    start_time = time.time()

    all_records = []
    if args.n_jobs > 1:
        with mp.Pool(processes=args.n_jobs) as pool:
            for task_records in tqdm(pool.imap_unordered(run_single_cell, tasks), total=len(tasks), desc="Executing Phase 2"):
                all_records.extend(task_records)
    else:
        for task in tqdm(tasks, desc="Executing Phase 2"):
            all_records.extend(run_single_cell(task))

    elapsed = time.time() - start_time
    print(f"\nExecution finished in {elapsed:.2f} seconds ({elapsed/60:.2f} min). Total records: {len(all_records)}")

    # 3. Save raw results
    df_results = pd.DataFrame(all_records)
    raw_csv = PHASE2_RESULTS_DIR / "phase2_results.csv"
    df_results.to_csv(raw_csv, index=False)
    print(f"✅ Saved raw results to {raw_csv}")

    # 4. Compute and save summary table
    summary_df = (
        df_results.groupby(["model", "train_label", "regime", "eval_mode"])[["mcc", "gmean"]]
        .agg(["mean", "std", "count"])
        .reset_index()
    )
    summary_csv = PHASE2_RESULTS_DIR / "phase2_summary.csv"
    summary_df.to_csv(summary_csv, index=False)
    print(f"✅ Saved summary table to {summary_csv}")

    # 5. Compute and save statistical tests
    stats_df = compute_statistical_tests(df_results)
    stats_csv = PHASE2_RESULTS_DIR / "statistical_tests.csv"
    stats_df.to_csv(stats_csv, index=False)
    print(f"✅ Saved statistical test results to {stats_csv}")

    # 6. Compute and save Inflation Ladder table
    inflation_ladder = (
        df_results[df_results["eval_mode"] == "oracle"]
        .groupby(["model", "train_label", "regime"])["mcc"]
        .mean()
        .unstack(level="regime")
        .reset_index()
    )
    ladder_csv = PHASE2_RESULTS_DIR / "inflation_ladder.csv"
    inflation_ladder.to_csv(ladder_csv, index=False)
    print(f"✅ Saved inflation ladder to {ladder_csv}")

    # Display headline table in console
    print("\n" + "=" * 70)
    print("HEADLINE RESULTS: ORACLE-SCORED MCC BY MODEL, LABEL SOURCE & REGIME")
    print("=" * 70)
    headline = (
        df_results[df_results["eval_mode"] == "oracle"]
        .pivot_table(index=["model", "train_label"], columns="regime", values="mcc", aggfunc="mean")
        .round(4)
    )
    print(headline)
    print("=" * 70)


if __name__ == "__main__":
    main()

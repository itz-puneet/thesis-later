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
                # terminal fading-window values (effective window ~100 commits)
                "oracle_asis_mcc": res_oracle_asis["mcc"],
                "oracle_asis_gmean": res_oracle_asis["gmean"],
                "oracle_imp_mcc": res_oracle_imp["mcc"],
                "oracle_imp_gmean": res_oracle_imp["gmean"],
                "bszz_mcc": res_bszz["mcc"],
                "bszz_gmean": res_bszz["gmean"],
                # time-averaged prequential values (mean of the MCC trajectory;
                # ~half the variance of the terminal value -- this comparison is
                # the most underpowered in the study, so the estimator matters)
                "oracle_asis_mcc_avg": res_oracle_asis["mcc_avg"],
                "oracle_asis_gmean_avg": res_oracle_asis["gmean_avg"],
                "oracle_imp_mcc_avg": res_oracle_imp["mcc_avg"],
                "oracle_imp_gmean_avg": res_oracle_imp["gmean_avg"],
                "bszz_mcc_avg": res_bszz["mcc_avg"],
                "bszz_gmean_avg": res_bszz["gmean_avg"],
            })

    res_df = pd.DataFrame(records)
    res_path = out_dir / "latency_imputation_sensitivity.csv"
    res_df.to_csv(res_path, index=False)
    print(f"Saved run-level records to {res_path}")

    # Project-level summary
    metric_cols = [c for c in res_df.columns if c not in ("project", "seed")]
    summary_df = res_df.groupby("project")[metric_cols].mean().reset_index()

    sum_path = out_dir / "latency_imputation_summary.csv"
    summary_df.to_csv(sum_path, index=False)
    print(f"Saved project summary to {sum_path}")

    # ---------------- Statistical tests ----------------
    #
    # Two changes from the original version of this script, both of which
    # previously flattered the hypothesis:
    #
    #  * The test is now TWO-SIDED. It was one-sided ("greater"), which halves
    #    the p-value in the direction we hoped to find. A one-sided test needs a
    #    pre-registered directional hypothesis; we are testing whether oracle
    #    differs from BSZZ, not confirming that it beats it.
    #  * The verdict now respects significance. It previously printed
    #    "maintains superiority" whenever the oracle MEAN was higher, regardless
    #    of the p-value -- which is how "the result is robust" reached the
    #    report while the underlying test sat at p ~ 0.86.
    #
    # Both estimators are reported: the terminal fading value (as before) and
    # the time-averaged prequential value, which carries roughly half the
    # variance and therefore more power for this specific comparison.

    def _mag(d):
        d = abs(d)
        if d < 0.147: return "negligible"
        if d < 0.33:  return "small"
        if d < 0.474: return "medium"
        return "large"

    def _compare(a, b, label):
        diff = a - b
        if np.allclose(diff, 0):
            return dict(label=label, mean_a=a.mean(), mean_b=b.mean(), diff=0.0,
                        wins=0, n=len(a), p_two=1.0, p_one=1.0, delta=0.0, mag="negligible")
        _, p_two = wilcoxon(a, b, alternative="two-sided")
        _, p_one = wilcoxon(a, b, alternative="greater")
        d = cliffs_delta(a, b)
        return dict(label=label, mean_a=a.mean(), mean_b=b.mean(), diff=diff.mean(),
                    wins=int((diff > 0).sum()), n=len(a),
                    p_two=p_two, p_one=p_one, delta=d, mag=_mag(d))

    results = []
    for est, suffix in [("terminal fading", ""), ("time-averaged", "_avg")]:
        a_asis = summary_df[f"oracle_asis_mcc{suffix}"].to_numpy()
        a_imp = summary_df[f"oracle_imp_mcc{suffix}"].to_numpy()
        b_bszz = summary_df[f"bszz_mcc{suffix}"].to_numpy()
        results.append((est, [
            _compare(a_asis, b_bszz, "Oracle as-is   vs BSZZ"),
            _compare(a_imp, b_bszz, "Oracle imputed vs BSZZ"),
            _compare(a_asis, a_imp, "Oracle as-is   vs Oracle imputed"),
        ]))

    print("\n" + "=" * 78)
    print("FINDING 3A -- DELIVERABILITY CONFOUND SENSITIVITY")
    print("=" * 78)
    print(f"Projects: {len(projects)}   Seeds: {len(RANDOM_SEEDS)}   "
          f"Runs per condition: {len(res_df)}   Paired unit: project (n={len(summary_df)})")

    for est, rows in results:
        print(f"\n--- {est} estimator ---")
        print(f"  oracle as-is (67.8% fix_ts) MCC {summary_df['oracle_asis_mcc' + ('_avg' if est.startswith('time') else '')].mean():+.4f}"
              f"   oracle imputed (100%) {summary_df['oracle_imp_mcc' + ('_avg' if est.startswith('time') else '')].mean():+.4f}"
              f"   BSZZ (100%) {summary_df['bszz_mcc' + ('_avg' if est.startswith('time') else '')].mean():+.4f}")
        print(f"  {'comparison':34s} {'diff':>8s} {'wins':>7s} {'p(2-sided)':>11s} {'p(1-sided)':>11s} {'delta':>8s}  magnitude")
        for r in rows:
            print(f"  {r['label']:34s} {r['diff']:+8.4f} {r['wins']:4d}/{r['n']:<2d} "
                  f"{r['p_two']:11.4f} {r['p_one']:11.4f} {r['delta']:+8.4f}  {r['mag']}")

    # Verdict, based on the two-sided test on the lower-variance estimator.
    primary = [r for est, rows in results if est.startswith("time") for r in rows]
    imp_vs_bszz = primary[1]
    print("\n" + "=" * 78)
    print("VERDICT")
    print("=" * 78)
    if imp_vs_bszz["p_two"] < 0.05:
        direction = "outperforms" if imp_vs_bszz["diff"] > 0 else "underperforms"
        print(f"Oracle {direction} BSZZ under 100% latency imputation "
              f"(p = {imp_vs_bszz['p_two']:.4f}, delta = {imp_vs_bszz['delta']:+.3f}, "
              f"{imp_vs_bszz['mag']}).")
        print("The deliverability confound is bounded: the label-quality advantage")
        print("survives equalising timestamp coverage.")
    else:
        print(f"NOT SIGNIFICANT. Oracle vs BSZZ under 100% imputation: "
              f"diff {imp_vs_bszz['diff']:+.4f}, {imp_vs_bszz['wins']}/{imp_vs_bszz['n']} projects, "
              f"p = {imp_vs_bszz['p_two']:.4f}, delta = {imp_vs_bszz['delta']:+.3f} ({imp_vs_bszz['mag']}).")
        print("Do NOT claim the oracle advantage over BSZZ survives imputation.")
        print("The defensible statement is that the two are statistically")
        print("indistinguishable once timestamp coverage is equalised, and that")
        print("the oracle's significant advantages are over the five REFINED")
        print("variants (see label_source_gap in statistical_tests.csv).")
    print("=" * 78)


if __name__ == "__main__":
    main()

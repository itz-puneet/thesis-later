"""Turn Phase 3/4 result CSVs into thesis-ready figures + stats tables.


Run after each experiment completes:
  python scripts/make_phase34_figures.py --phase 3
  python scripts/make_phase34_figures.py --phase 4

Outputs -> reports/figures/ (300 DPI PNG) and results/phaseN/*_stats.csv.
Every figure filename matches the thesis figure label it will carry, keeping
the "every figure has a generating script" invariant.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy.stats import wilcoxon

from codebase.evaluation.metrics import paired_effect
from experiments.run_phase2_impact import _holm

_ROOT = Path(__file__).resolve().parent.parent
FIGS = _ROOT / "reports" / "figures"; FIGS.mkdir(parents=True, exist_ok=True)
P3 = _ROOT / "results" / "phase3"; P4 = _ROOT / "results" / "phase4"
plt.rcParams.update({"figure.dpi": 300, "font.size": 9, "axes.grid": True,
                     "grid.alpha": 0.3})


def _ci_band(g: pd.DataFrame, val: str):
    m = g[val].mean()
    s = g[val].std() / np.sqrt(max(g[val].count(), 1))
    return m, 1.96 * s


# ---------------------------------------------------------------- Phase 3
def fig_dose_response(df: pd.DataFrame, metric: str, latency: str):
    fig, ax = plt.subplots(figsize=(5, 3.2))
    sub = df[df.latency == latency]
    for prof, g in sub.groupby("profile"):
        agg = g.groupby("dose").apply(lambda x: pd.Series(_ci_band(x, metric)),
                                      include_groups=False)
        agg.columns = ["m", "ci"]
        ax.plot(agg.index, agg.m, marker="o", label=prof)
        ax.fill_between(agg.index, agg.m - agg.ci, agg.m + agg.ci, alpha=0.15)
    ax.set_xlabel("injected noise dose")
    ax.set_ylabel(metric.upper())
    ax.set_title(f"ORB dose-response ({latency} latency)")
    ax.legend(fontsize=7)
    fig.tight_layout()
    fig.savefig(FIGS / f"fig_p3_dose_{metric}_{latency}.png")
    plt.close(fig)


def fig_arm_compression(df: pd.DataFrame, metric: str = "mcc"):
    """The two-arm figure: same profiles, uniform vs real latency."""
    if df.latency.nunique() < 2:
        return
    fig, axes = plt.subplots(1, 2, figsize=(8, 3.2), sharey=True)
    for ax, latency in zip(axes, ["uniform", "real"]):
        sub = df[df.latency == latency]
        for prof, g in sub.groupby("profile"):
            agg = g.groupby("dose")[metric].mean()
            ax.plot(agg.index, agg.values, marker="o", label=prof)
        ax.set_title(f"{latency} latency"); ax.set_xlabel("dose")
    axes[0].set_ylabel(metric.upper()); axes[0].legend(fontsize=7)
    fig.suptitle("Latency compresses label-noise sensitivity", y=1.02)
    fig.tight_layout()
    fig.savefig(FIGS / f"fig_p3_arm_compression_{metric}.png", bbox_inches="tight")
    plt.close(fig)


def fig_repair(rep: pd.DataFrame, metric: str = "mcc_avg"):
    order = ["oracle", "BSZZ_fp_repaired", "BSZZ_fn_repaired", "BSZZ"]
    fig, ax = plt.subplots(figsize=(4.5, 3.2))
    proj = rep.groupby(["condition", "project"])[metric].mean().reset_index()
    means = proj.groupby("condition")[metric].mean().reindex(order)
    errs = 1.96 * proj.groupby("condition")[metric].sem().reindex(order)
    ax.bar(range(len(order)), means.values, yerr=errs.values, capsize=3)
    ax.set_xticks(range(len(order)))
    ax.set_xticklabels(order, rotation=20, ha="right", fontsize=7)
    ax.set_ylabel(f"{metric} (oracle-scored)")
    ax.set_title("Repair experiment: which SZZ error hurts ORB more?")
    fig.tight_layout(); fig.savefig(FIGS / f"fig_p3_repair_{metric}.png"); plt.close(fig)
    return proj


def repair_stats(rep: pd.DataFrame) -> pd.DataFrame:
    """Paired tests for the repair experiment, under BOTH estimators.

    Phase 2's review required paired effect sizes and a multiplicity
    correction; the same standard applies here, so this reports
    matched-pairs rank-biserial, Hodges-Lehmann with a bootstrap CI, and
    Holm across the whole set rather than a bare Wilcoxon statistic.
    """
    rows = []
    for metric in ["mcc_avg", "mcc"]:
        proj = rep.groupby(["condition", "project"])[metric].mean().reset_index()
        piv = proj.pivot(index="project", columns="condition",
                         values=metric).dropna()
        for a, b in [("BSZZ_fp_repaired", "BSZZ"), ("BSZZ_fn_repaired", "BSZZ"),
                     ("BSZZ_fn_repaired", "BSZZ_fp_repaired"), ("oracle", "BSZZ")]:
            if a not in piv or b not in piv:
                continue
            e = paired_effect(piv[a].to_numpy(), piv[b].to_numpy())
            rows.append(dict(metric=metric, A=a, B=b, n=len(piv),
                             mean_A=piv[a].mean(), mean_B=piv[b].mean(),
                             hodges_lehmann=e["hodges_lehmann"],
                             ci_low=e["ci_low"], ci_high=e["ci_high"],
                             rank_biserial=e["rank_biserial"],
                             n_favouring_A=int((piv[a] > piv[b]).sum()),
                             p=e["p_value"]))
    out = pd.DataFrame(rows)
    if not out.empty:
        # Holm within each estimator, and globally across all of them.
        out["p_holm"] = np.nan
        for m, g in out.groupby("metric"):
            out.loc[g.index, "p_holm"] = _holm(g["p"].to_numpy())
        out["p_holm_global"] = _holm(out["p"].to_numpy())
    out.to_csv(P3 / "phase3_repair_stats.csv", index=False)
    return out


def phase3():
    dr = pd.read_csv(P3 / "phase3_dose_response.csv")
    rep = pd.read_csv(P3 / "phase3_repair.csv")
    # mcc_avg (time-averaged) is primary; mcc (terminal fading) is the
    # secondary. Phase 2 was corrected for reporting only the terminal value,
    # so every Phase 3 artefact carries both.
    for metric in ["mcc_avg", "gmean_avg", "mcc", "gmean"]:
        if metric not in dr.columns:
            continue
        for latency in dr.latency.unique():
            fig_dose_response(dr, metric, latency)
    for metric in ["mcc_avg", "mcc"]:
        if metric in dr.columns:
            fig_arm_compression(dr, metric)
        if metric in rep.columns:
            fig_repair(rep, metric)
    stats = repair_stats(rep)

    # Degradation-slope table: metric lost per 10% dose, by profile x latency.
    #
    # Dose is the expected flipped fraction over ALL commits, so at matched
    # dose the FN-heavy profile strips a far larger share of the 8.5% minority
    # class than the FP-heavy one. Past a saturation point it removes every
    # positive label, and MCC then measures a stream with no learnable signal.
    # Fitting a straight line through that region understates the slope and
    # invites a comparison the design does not support, so slopes are fitted
    # on the non-degenerate cells and the saturation point is reported beside
    # them. The full-range fit is kept, flagged, for transparency.
    if "n_pos_retained" in dr.columns:
        ok = dr.groupby(["profile", "latency", "dose"])["n_pos_retained"].mean()
        live = ok[ok > 0].reset_index()[["profile", "latency", "dose"]]
        dr_live = dr.merge(live, on=["profile", "latency", "dose"])
    else:
        dr_live = dr

    slopes = []
    for metric in ["mcc_avg", "mcc"]:
        if metric not in dr.columns:
            continue
        for scope, frame in [("non_degenerate", dr_live), ("all_doses", dr)]:
            for (prof, lat), g in frame.groupby(["profile", "latency"]):
                agg = g.groupby("dose")[metric].mean()
                if len(agg) < 2:
                    continue
                b = np.polyfit(agg.index, agg.values, 1)[0]
                slopes.append(dict(metric=metric, scope=scope, profile=prof,
                                   latency=lat, n_doses_fitted=len(agg),
                                   max_dose_fitted=float(agg.index.max()),
                                   per_10pct_dose=round(b * 0.10, 4)))
    sl = pd.DataFrame(slopes)
    sl.to_csv(P3 / "phase3_slopes.csv", index=False)

    if "n_pos_retained" in dr.columns:
        surv = (dr.groupby(["profile", "dose"])
                  .apply(lambda g: g["n_pos_retained"].sum() / g["n_pos_true"].sum(),
                         include_groups=False)
                  .unstack().round(4))
        surv.to_csv(P3 / "phase3_minority_survival.csv")
        print("\n=== Share of true positive labels surviving injection ===")
        print("(a column of zeros means that dose destroys the minority class)")
        print(surv.to_string())
        print("\n=== Degradation slopes, primary estimator, non-degenerate fit ===")
        prim = sl[(sl.metric == "mcc_avg") & (sl.scope == "non_degenerate")]
        print(prim.pivot(index="profile", columns="latency",
                         values="per_10pct_dose").to_string())

    if not stats.empty:
        print("\n=== Repair experiment, paired tests (primary estimator first) ===")
        cols = ["metric", "A", "B", "hodges_lehmann", "ci_low", "ci_high",
                "rank_biserial", "n_favouring_A", "p_holm", "p_holm_global"]
        print(stats[cols].to_string(index=False))
    print(f"\nPhase 3 figures -> {FIGS}, stats -> {P3}")


# ---------------------------------------------------------------- Phase 4
def phase4():
    res = pd.read_csv(P4 / "phase4_results.csv")
    proj = res.groupby(["condition", "model", "project"])["mcc"].mean().reset_index()

    # main figure: grouped bars, models x key conditions
    conds = [c for c in ["oracle", "BSZZ", "LSZZ", "injected_fn20"]
             if c in res.condition.unique()]
    models = ["OOB", "ORB", "NA(damp)", "NA(rescue)", "NA(damp+rescue)",
              "NA(damp+rescue+lc)"]
    fig, ax = plt.subplots(figsize=(7, 3.4))
    width = 0.8 / len(models)
    for i, m in enumerate(models):
        vals, errs = [], []
        for c in conds:
            g = proj[(proj.model == m) & (proj.condition == c)]["mcc"]
            vals.append(g.mean()); errs.append(1.96 * g.sem())
        ax.bar(np.arange(len(conds)) + i * width, vals, width,
               yerr=errs, capsize=2, label=m)
    ax.set_xticks(np.arange(len(conds)) + 0.4 - width / 2)
    ax.set_xticklabels(conds); ax.set_ylabel("MCC (oracle-scored)")
    ax.set_title("Phase 4 ablation across label conditions")
    ax.legend(fontsize=6, ncol=3)
    fig.tight_layout(); fig.savefig(FIGS / "fig_p4_ablation.png"); plt.close(fig)

    # per-condition NA(damp+rescue) vs ORB scatter (project-paired)
    piv = proj.pivot_table(index=["condition", "project"], columns="model",
                           values="mcc").reset_index()
    if {"NA(damp+rescue)", "ORB"} <= set(piv.columns):
        fig, ax = plt.subplots(figsize=(3.6, 3.6))
        for c, g in piv.groupby("condition"):
            ax.scatter(g["ORB"], g["NA(damp+rescue)"], s=12, label=c, alpha=0.7)
        lims = [min(ax.get_xlim()[0], ax.get_ylim()[0]),
                max(ax.get_xlim()[1], ax.get_ylim()[1])]
        ax.plot(lims, lims, "k--", lw=0.8)
        ax.set_xlabel("ORB MCC"); ax.set_ylabel("NA(damp+rescue) MCC")
        ax.set_title("Project-paired comparison"); ax.legend(fontsize=6)
        fig.tight_layout(); fig.savefig(FIGS / "fig_p4_paired_scatter.png")
        plt.close(fig)

    print(f"Phase 4 figures -> {FIGS}; headline tests already in "
          f"{P4}/phase4_headline_tests.csv")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--phase", type=int, choices=[3, 4], required=True)
    (phase3 if ap.parse_args().phase == 3 else phase4)()

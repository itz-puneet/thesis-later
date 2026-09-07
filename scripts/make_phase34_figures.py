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
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy.stats import wilcoxon

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


def fig_repair(rep: pd.DataFrame):
    order = ["oracle", "BSZZ_fp_repaired", "BSZZ_fn_repaired", "BSZZ"]
    fig, ax = plt.subplots(figsize=(4.5, 3.2))
    proj = rep.groupby(["condition", "project"])["mcc"].mean().reset_index()
    means = proj.groupby("condition")["mcc"].mean().reindex(order)
    errs = 1.96 * proj.groupby("condition")["mcc"].sem().reindex(order)
    ax.bar(range(len(order)), means.values, yerr=errs.values, capsize=3)
    ax.set_xticks(range(len(order)))
    ax.set_xticklabels(order, rotation=20, ha="right", fontsize=7)
    ax.set_ylabel("MCC (oracle-scored)")
    ax.set_title("Repair experiment: which SZZ error hurts ORB more?")
    fig.tight_layout(); fig.savefig(FIGS / "fig_p3_repair.png"); plt.close(fig)

    # paired stats table
    piv = proj.pivot(index="project", columns="condition", values="mcc").dropna()
    rows = []
    for a, b in [("BSZZ_fp_repaired", "BSZZ"), ("BSZZ_fn_repaired", "BSZZ"),
                 ("BSZZ_fn_repaired", "BSZZ_fp_repaired")]:
        if a in piv and b in piv:
            stat, p = wilcoxon(piv[a], piv[b])
            rows.append(dict(A=a, B=b, mean_A=piv[a].mean(), mean_B=piv[b].mean(),
                             mean_diff=piv[a].mean() - piv[b].mean(),
                             wilcoxon=stat, p=p, n=len(piv)))
    pd.DataFrame(rows).to_csv(P3 / "phase3_repair_stats.csv", index=False)


def phase3():
    dr = pd.read_csv(P3 / "phase3_dose_response.csv")
    rep = pd.read_csv(P3 / "phase3_repair.csv")
    for metric in ["mcc", "gmean"]:
        for latency in dr.latency.unique():
            fig_dose_response(dr, metric, latency)
    fig_arm_compression(dr)
    fig_repair(rep)
    # degradation-slope table: MCC lost per 10% dose, by profile x latency
    slopes = []
    for (prof, lat), g in dr.groupby(["profile", "latency"]):
        agg = g.groupby("dose")["mcc"].mean()
        b = np.polyfit(agg.index, agg.values, 1)[0]
        slopes.append(dict(profile=prof, latency=lat, mcc_per_10pct=round(b * 0.10, 4)))
    pd.DataFrame(slopes).to_csv(P3 / "phase3_slopes.csv", index=False)
    print(f"Phase 3 figures -> {FIGS}, stats -> {P3}")


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

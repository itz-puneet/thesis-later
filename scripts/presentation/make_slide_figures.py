"""Figures for the presentation, sized for slides.

Run from the repository root:
    python scripts/presentation/make_slide_figures.py

The plots show the same results as the figures of the report, but with larger
text so that they stay readable when projected.
"""
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.metrics import cohen_kappa_score

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent / "images"
OUT.mkdir(exist_ok=True)

VARIANTS = ["BSZZ", "AGSZZ", "MASZZ", "LSZZ", "RSZZ", "RASZZ"]
NAME = {"oracle": "Reference", "BSZZ": "B-SZZ", "AGSZZ": "AG-SZZ", "MASZZ": "MA-SZZ",
        "LSZZ": "L-SZZ", "RSZZ": "R-SZZ", "RASZZ": "RA-SZZ"}
BLUE, RED, GREY, GREEN, ORANGE = "#2b6ca3", "#b5412f", "#9aa0a6", "#3c8d5a", "#d98b2b"

plt.rcParams.update({
    "font.size": 10, "axes.titlesize": 10.5, "axes.labelsize": 10,
    "xtick.labelsize": 9, "ytick.labelsize": 9, "legend.fontsize": 9,
    "axes.spines.top": False, "axes.spines.right": False,
    "axes.grid": True, "grid.alpha": 0.3, "grid.linewidth": 0.5,
    "savefig.bbox": "tight", "savefig.pad_inches": 0.04, "savefig.dpi": 260,
})


def save(fig, name):
    fig.savefig(OUT / f"{name}.png")
    plt.close(fig)
    print("wrote", name)


def cell(r, model, label, regime, mode, col="mcc"):
    s = r[(r.model == model) & (r.train_label == label) & (r.regime == regime) & (r.eval_mode == mode)]
    return s[col].mean()


def projects(c):
    g = c.groupby("project")
    d = pd.DataFrame({"commits": g.size(), "rate": 100 * g.label_oracle.mean()}).sort_values("commits")
    fig, ax = plt.subplots(1, 2, figsize=(4.6, 3.7), sharey=True)
    ax[0].barh(d.index, d.commits, color=BLUE)
    ax[0].set_xlabel("Commits")
    ax[1].barh(d.index, d.rate, color=RED)
    ax[1].axvline(100 * c.label_oracle.mean(), color="k", ls="--", lw=0.8)
    ax[1].set_xlabel("Defect-introducing (%)")
    for a in ax:
        a.grid(axis="y", visible=False)
        a.tick_params(axis="y", labelsize=7.5)
    fig.tight_layout()
    save(fig, "projects")


def noise_rates(bias):
    fig, ax = plt.subplots(figsize=(3.7, 3.1))
    for v in VARIANTS:
        ax.scatter(bias[v]["fp_rate"], bias[v]["fn_rate"], s=45, color=BLUE, zorder=3)
        off = {"AGSZZ": (-46, -4), "MASZZ": (7, -10)}.get(v, (7, 4))
        ax.annotate(NAME[v], (bias[v]["fp_rate"], bias[v]["fn_rate"]),
                    textcoords="offset points", xytext=off, fontsize=9)
    ax.set_xlabel(r"False-alarm rate $\rho_0$")
    ax.set_ylabel(r"Miss rate $\rho_1$")
    ax.set_xlim(0.03, 0.32)
    save(fig, "noise_rates")


def kappa(c):
    cols = ["oracle"] + VARIANTS
    lab = {k: c[f"label_{k}"].values for k in cols}
    K = np.array([[cohen_kappa_score(lab[a], lab[b]) for b in cols] for a in cols])
    fig, ax = plt.subplots(figsize=(4.3, 3.5))
    im = ax.imshow(K, cmap="Blues", vmin=0, vmax=1)
    ax.set_xticks(range(len(cols)))
    ax.set_yticks(range(len(cols)))
    ax.set_xticklabels([NAME[k] for k in cols], rotation=35, ha="right")
    ax.set_yticklabels([NAME[k] for k in cols])
    for i in range(len(cols)):
        for j in range(len(cols)):
            ax.text(j, i, f"{K[i, j]:.2f}", ha="center", va="center", fontsize=8,
                    color="white" if K[i, j] > 0.6 else "black")
    ax.grid(False)
    for s in ax.spines.values():
        s.set_visible(False)
    fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04, label=r"Cohen's $\kappa$")
    save(fig, "kappa")


def leakage(r):
    o = r[(r.eval_mode == "oracle") & (r.train_label == "oracle")]
    fig, ax = plt.subplots(1, 2, figsize=(5.4, 3.0), sharey=True)
    for a, model in zip(ax, ["JITLine", "LApredict"]):
        m = o[o.model == model].groupby(["project", "regime"]).mcc.mean().unstack()
        for _, row in m.iterrows():
            down = row.naive_kfold > row.chronological
            a.plot([0, 1], [row.naive_kfold, row.chronological], marker="o", ms=3, lw=0.9,
                   color=BLUE if down else RED, alpha=0.75)
        a.plot([0, 1], [m.naive_kfold.mean(), m.chronological.mean()], color="k", lw=2.2, marker="o", ms=5)
        a.set_xticks([0, 1])
        a.set_xticklabels(["Random\n$k$-fold", "Chrono-\nlogical"])
        a.set_xlim(-0.3, 1.3)
        a.set_title(model)
    ax[0].set_ylabel("MCC (reference labels)")
    fig.tight_layout()
    save(fig, "leakage")


def self_scoring(r):
    fig, ax = plt.subplots(1, 2, figsize=(5.6, 3.0), sharey=True)
    x = np.arange(len(VARIANTS))
    for a, regime, title in zip(ax, ["naive_kfold", "chronological"], ["Random $k$-fold", "Chronological split"]):
        for off, model, col in [(-0.2, "JITLine", RED), (0.2, "LApredict", BLUE)]:
            gap = [cell(r, model, v, regime, "self") - cell(r, model, v, regime, "oracle") for v in VARIANTS]
            a.bar(x + off, gap, 0.4, color=col, label=model)
        a.axhline(0, color="k", lw=0.7)
        a.set_xticks(x)
        a.set_xticklabels([NAME[v] for v in VARIANTS], rotation=40, ha="right")
        a.set_title(title)
        a.grid(axis="x", visible=False)
    ax[0].set_ylabel("Self-scored minus\nreference-scored MCC")
    ax[0].legend(frameon=False)
    fig.tight_layout()
    save(fig, "self_scoring")


def ladder(r):
    bars = [
        ("JITLine\nB-SZZ\n$k$-fold\n(self-scored)", cell(r, "JITLine", "BSZZ", "naive_kfold", "self"), GREY),
        ("JITLine\nB-SZZ\n$k$-fold", cell(r, "JITLine", "BSZZ", "naive_kfold", "oracle"), ORANGE),
        ("JITLine\nReference\n$k$-fold", cell(r, "JITLine", "oracle", "naive_kfold", "oracle"), ORANGE),
        ("JITLine\nReference\nchrono.", cell(r, "JITLine", "oracle", "chronological", "oracle"), BLUE),
        ("ORB\nReference\nchrono.-\nonline", cell(r, "ORB", "oracle", "chronological_online", "oracle"), BLUE),
        ("ORB\nReference\nprequential", cell(r, "ORB", "oracle", "prequential_latency", "oracle", "mcc_avg"), GREEN),
    ]
    fig, ax = plt.subplots(figsize=(5.6, 3.2))
    x = np.arange(len(bars))
    ax.bar(x, [b[1] for b in bars], color=[b[2] for b in bars], width=0.65)
    for i, b in enumerate(bars):
        ax.text(i, b[1] + 0.008, f"{b[1]:.3f}", ha="center", fontsize=9)
    ax.set_xticks(x)
    ax.set_xticklabels([b[0] for b in bars], fontsize=8)
    ax.set_ylabel("MCC")
    ax.set_ylim(0, 0.47)
    ax.grid(axis="x", visible=False)
    save(fig, "ladder")


if __name__ == "__main__":
    commits = pd.read_csv(ROOT / "data/processed/phase2_commits.csv")
    results = pd.read_csv(ROOT / "results/phase2/phase2_results.csv")
    bias = json.load(open(ROOT / "phase1_bias.json"))
    projects(commits)
    noise_rates(bias)
    kappa(commits)
    leakage(results)
    self_scoring(results)
    ladder(results)

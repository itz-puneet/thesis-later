"""Generate the figures used in the progress report.

Run from the repository root:
    python supervisor_report/make_figures.py

All figures are built from the committed result files, so they can be
regenerated at any time. Output goes to supervisor_report/figures/.
"""
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.metrics import cohen_kappa_score

ROOT = Path(__file__).resolve().parent.parent
OUT = Path(__file__).resolve().parent / "figures"
OUT.mkdir(exist_ok=True)

VARIANTS = ["BSZZ", "AGSZZ", "MASZZ", "LSZZ", "RSZZ", "RASZZ"]
NAME = {"oracle": "Reference", "BSZZ": "B-SZZ", "AGSZZ": "AG-SZZ", "MASZZ": "MA-SZZ",
        "LSZZ": "L-SZZ", "RSZZ": "R-SZZ", "RASZZ": "RA-SZZ"}
BLUE, RED, GREY, GREEN, ORANGE = "#2b6ca3", "#b5412f", "#9aa0a6", "#3c8d5a", "#d98b2b"

plt.rcParams.update({
    "font.size": 9, "axes.titlesize": 9.5, "axes.labelsize": 9,
    "xtick.labelsize": 8, "ytick.labelsize": 8, "legend.fontsize": 8,
    "axes.spines.top": False, "axes.spines.right": False,
    "axes.grid": True, "grid.alpha": 0.3, "grid.linewidth": 0.5,
    "figure.dpi": 150, "savefig.bbox": "tight", "savefig.pad_inches": 0.03,
})


def save(fig, name):
    fig.savefig(OUT / f"{name}.pdf")
    plt.close(fig)
    print("wrote", name)


def load():
    commits = pd.read_csv(ROOT / "data/processed/phase2_commits.csv")
    results = pd.read_csv(ROOT / "results/phase2/phase2_results.csv")
    tests = pd.read_csv(ROOT / "results/phase2/statistical_tests.csv")
    bias = json.load(open(ROOT / "phase1_bias.json"))
    return commits, results, tests, bias


def fig_projects(c):
    g = c.groupby("project")
    d = pd.DataFrame({"commits": g.size(), "rate": 100 * g.label_oracle.mean()}).sort_values("commits")
    fig, ax = plt.subplots(1, 2, figsize=(7.0, 3.9), sharey=True)
    ax[0].barh(d.index, d.commits, color=BLUE)
    ax[0].set_xlabel("Number of commits")
    ax[1].barh(d.index, d.rate, color=RED)
    ax[1].axvline(100 * c.label_oracle.mean(), color="k", ls="--", lw=0.8)
    ax[1].set_xlabel("Defect-introducing commits (%)")
    for a in ax:
        a.grid(axis="y", visible=False)
    fig.tight_layout()
    save(fig, "fig_projects")


def fig_latency(c):
    lat = ((c.fix_ts - c.author_ts) / 86400).dropna()
    lat = lat[lat > 0]
    fig, ax = plt.subplots(figsize=(6.2, 2.9))
    ax.hist(np.clip(lat, 0, 1500), bins=60, color=BLUE)
    ax.axvline(90, color=RED, lw=1.6, label="Waiting period (90 days)")
    ax.axvline(lat.median(), color=ORANGE, lw=1.6, ls="--", label=f"Median ({lat.median():.0f} days)")
    ax.set_xlabel("Verification latency in days (values above 1500 shown at 1500)")
    ax.set_ylabel("Number of commits")
    ax.legend(frameon=False)
    save(fig, "fig_latency")


def fig_szz_quality(bias):
    names = [NAME[v] for v in VARIANTS]
    prec = [bias[v]["precision"] for v in VARIANTS]
    rec = [bias[v]["recall"] for v in VARIANTS]
    fig, ax = plt.subplots(1, 2, figsize=(7.0, 2.9))
    x = np.arange(len(VARIANTS))
    ax[0].bar(x - 0.2, prec, 0.4, color=RED, label="Precision")
    ax[0].bar(x + 0.2, rec, 0.4, color=BLUE, label="Recall")
    ax[0].set_xticks(x)
    ax[0].set_xticklabels(names, rotation=20)
    ax[0].set_ylim(0, 0.75)
    ax[0].axhline(max(prec), color="k", ls="--", lw=0.8)
    ax[0].text(0.45, max(prec) + 0.015, "highest precision (0.272)", fontsize=7.5)
    ax[0].legend(frameon=False)
    ax[0].set_title("(a) Precision and recall")
    for v in VARIANTS:
        ax[1].scatter(bias[v]["fp_rate"], bias[v]["fn_rate"], s=40, color=BLUE, zorder=3)
        off = {"AGSZZ": (-38, -3), "MASZZ": (7, -8)}.get(v, (6, 4))
        ax[1].annotate(NAME[v], (bias[v]["fp_rate"], bias[v]["fn_rate"]),
                       textcoords="offset points", xytext=off, fontsize=8)
    ax[1].set_xlabel(r"False-alarm rate $\rho_0$")
    ax[1].set_ylabel(r"Miss rate $\rho_1$")
    ax[1].set_xlim(0.04, 0.31)
    ax[1].set_title("(b) Two types of label error")
    fig.tight_layout()
    save(fig, "fig_szz_quality")


def fig_szz_volume(bias):
    names = [NAME[v] for v in VARIANTS]
    tp = np.array([bias[v]["TP"] for v in VARIANTS])
    fp = np.array([bias[v]["FP"] for v in VARIANTS])
    fn = np.array([bias[v]["FN"] for v in VARIANTS])
    x = np.arange(len(VARIANTS))
    fig, ax = plt.subplots(figsize=(6.2, 2.9))
    ax.bar(x - 0.2, tp, 0.4, color=GREEN, label="Correctly flagged (TP)")
    ax.bar(x - 0.2, fp, 0.4, bottom=tp, color=RED, label="Wrongly flagged (FP)")
    ax.bar(x + 0.2, fn, 0.4, color=GREY, label="Missed defects (FN)")
    ax.set_xticks(x)
    ax.set_xticklabels(names)
    ax.set_ylabel("Number of commits")
    ax.legend(frameon=False)
    save(fig, "fig_szz_volume")


def fig_szz_perproject(c):
    rows = []
    for p, g in c.groupby("project"):
        o = g.label_oracle.values
        for v in VARIANTS:
            f = g[f"label_{v}"].values
            tp = ((f == 1) & (o == 1)).sum()
            rows.append((v, tp / max(f.sum(), 1), tp / max(o.sum(), 1)))
    d = pd.DataFrame(rows, columns=["v", "precision", "recall"])
    fig, ax = plt.subplots(1, 2, figsize=(7.0, 2.8))
    for a, col, title in zip(ax, ["precision", "recall"], ["(a) Precision", "(b) Recall"]):
        a.boxplot([d[d.v == v][col] for v in VARIANTS], tick_labels=[NAME[v] for v in VARIANTS],
                  medianprops=dict(color=RED), flierprops=dict(markersize=3))
        a.set_title(title)
        a.set_ylim(0, 1)
        a.tick_params(axis="x", rotation=20)
    fig.tight_layout()
    save(fig, "fig_szz_perproject")


def fig_kappa(c):
    cols = ["oracle"] + VARIANTS
    lab = {k: c[f"label_{k}"].values for k in cols}
    K = np.array([[cohen_kappa_score(lab[a], lab[b]) for b in cols] for a in cols])
    fig, ax = plt.subplots(figsize=(4.6, 3.8))
    im = ax.imshow(K, cmap="Blues", vmin=0, vmax=1)
    ax.set_xticks(range(len(cols)))
    ax.set_yticks(range(len(cols)))
    ax.set_xticklabels([NAME[k] for k in cols], rotation=35, ha="right")
    ax.set_yticklabels([NAME[k] for k in cols])
    for i in range(len(cols)):
        for j in range(len(cols)):
            ax.text(j, i, f"{K[i, j]:.2f}", ha="center", va="center", fontsize=7.5,
                    color="white" if K[i, j] > 0.6 else "black")
    ax.grid(False)
    for s in ax.spines.values():
        s.set_visible(False)
    fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04, label=r"Cohen's $\kappa$")
    save(fig, "fig_kappa")


def cell(r, model, label, regime, mode, col="mcc"):
    s = r[(r.model == model) & (r.train_label == label) & (r.regime == regime) & (r.eval_mode == mode)]
    return s[col].mean()


def fig_ladder(r):
    bars = [
        ("JITLine\nB-SZZ\n$k$-fold\n(self-scored)", cell(r, "JITLine", "BSZZ", "naive_kfold", "self"), GREY),
        ("JITLine\nB-SZZ\n$k$-fold", cell(r, "JITLine", "BSZZ", "naive_kfold", "oracle"), ORANGE),
        ("JITLine\nReference\n$k$-fold", cell(r, "JITLine", "oracle", "naive_kfold", "oracle"), ORANGE),
        ("JITLine\nReference\nchronological", cell(r, "JITLine", "oracle", "chronological", "oracle"), BLUE),
        ("ORB\nReference\nchrono-online", cell(r, "ORB", "oracle", "chronological_online", "oracle"), BLUE),
        ("ORB\nReference\nprequential", cell(r, "ORB", "oracle", "prequential_latency", "oracle", "mcc_avg"), GREEN),
    ]
    fig, ax = plt.subplots(figsize=(6.6, 3.1))
    x = np.arange(len(bars))
    ax.bar(x, [b[1] for b in bars], color=[b[2] for b in bars], width=0.65)
    for i, b in enumerate(bars):
        ax.text(i, b[1] + 0.008, f"{b[1]:.3f}", ha="center", fontsize=8)
    ax.set_xticks(x)
    ax.set_xticklabels([b[0] for b in bars], fontsize=8)
    ax.set_ylabel("MCC")
    ax.set_ylim(0, 0.46)
    ax.grid(axis="x", visible=False)
    save(fig, "fig_ladder")


def fig_leakage(r):
    o = r[(r.eval_mode == "oracle") & (r.train_label == "oracle")]
    fig, ax = plt.subplots(1, 2, figsize=(6.6, 2.9), sharey=True)
    for a, model, title in zip(ax, ["JITLine", "LApredict"], ["(a) JITLine", "(b) LApredict"]):
        m = o[o.model == model].groupby(["project", "regime"]).mcc.mean().unstack()
        for _, row in m.iterrows():
            down = row.naive_kfold > row.chronological
            a.plot([0, 1], [row.naive_kfold, row.chronological], marker="o", ms=3, lw=0.9,
                   color=BLUE if down else RED, alpha=0.75)
        a.plot([0, 1], [m.naive_kfold.mean(), m.chronological.mean()], color="k", lw=2.2, marker="o", ms=5)
        a.set_xticks([0, 1])
        a.set_xticklabels(["Random $k$-fold", "Chronological"])
        a.set_xlim(-0.25, 1.25)
        a.set_title(title)
    ax[0].set_ylabel("MCC (reference labels)")
    fig.tight_layout()
    save(fig, "fig_leakage")


def fig_self_scoring(r):
    fig, ax = plt.subplots(1, 2, figsize=(7.0, 2.9), sharey=True)
    x = np.arange(len(VARIANTS))
    for a, regime, title in zip(ax, ["naive_kfold", "chronological"],
                                ["(a) Random $k$-fold", "(b) Chronological split"]):
        for off, model, col in [(-0.2, "JITLine", RED), (0.2, "LApredict", BLUE)]:
            gap = [cell(r, model, v, regime, "self") - cell(r, model, v, regime, "oracle") for v in VARIANTS]
            a.bar(x + off, gap, 0.4, color=col, label=model)
        a.axhline(0, color="k", lw=0.7)
        a.set_xticks(x)
        a.set_xticklabels([NAME[v] for v in VARIANTS], rotation=20)
        a.set_title(title)
        a.grid(axis="x", visible=False)
    ax[0].set_ylabel("Self-scored MCC minus\nreference-scored MCC")
    ax[0].legend(frameon=False)
    fig.tight_layout()
    save(fig, "fig_self_scoring")


def fig_label_source(r, t):
    p = r[(r.model == "ORB") & (r.regime == "prequential_latency") & (r.eval_mode == "oracle")]
    m = p.groupby("train_label")[["mcc_avg", "mcc"]].mean()
    order = ["oracle"] + list(m.drop("oracle").sort_values("mcc_avg", ascending=False).index)
    fig, ax = plt.subplots(1, 2, figsize=(7.0, 2.9))
    x = np.arange(len(order))
    ax[0].bar(x - 0.2, m.loc[order, "mcc_avg"], 0.4, color=GREEN, label="Time-averaged")
    ax[0].bar(x + 0.2, m.loc[order, "mcc"], 0.4, color=GREY, label="Terminal")
    ax[0].axhline(0, color="k", lw=0.7)
    ax[0].set_xticks(x)
    ax[0].set_xticklabels([NAME[k] for k in order], rotation=20)
    ax[0].set_ylabel("MCC")
    ax[0].legend(frameon=False)
    ax[0].set_title("(a) Mean MCC by training labels")
    ax[0].grid(axis="x", visible=False)
    g = t[(t.comparison_type == "label_source_gap") & (t.metric == "mcc_avg")].set_index("train_label")
    vs = order[1:]
    y = np.arange(len(vs))[::-1]
    hl = g.loc[vs, "hodges_lehmann"].values
    ax[1].errorbar(hl, y, xerr=[hl - g.loc[vs, "ci_low"].values, g.loc[vs, "ci_high"].values - hl],
                   fmt="o", color=BLUE, capsize=3, ms=4)
    ax[1].axvline(0, color="k", lw=0.7)
    ax[1].set_yticks(y)
    ax[1].set_yticklabels([NAME[k] for k in vs])
    ax[1].set_xlabel("Reference minus variant (MCC)")
    ax[1].set_title("(b) Estimated difference, 95% CI")
    ax[1].set_xlim(-0.01, 0.1)
    fig.tight_layout()
    save(fig, "fig_label_source")


def fig_estimators(r):
    p = r[(r.model == "ORB") & (r.regime == "prequential_latency") & (r.eval_mode == "oracle")]
    pm = p.groupby(["project", "train_label"])[["mcc", "mcc_avg"]].mean().reset_index()
    fig, ax = plt.subplots(1, 2, figsize=(7.0, 2.9))
    bins = np.linspace(-0.2, 0.4, 28)
    ax[0].hist(pm.mcc, bins=bins, alpha=0.7, color=GREY, label=f"Terminal (s.d. {pm.mcc.std():.3f})")
    ax[0].hist(pm.mcc_avg, bins=bins, alpha=0.7, color=GREEN, label=f"Time-averaged (s.d. {pm.mcc_avg.std():.3f})")
    ax[0].set_xlabel("Project-level MCC")
    ax[0].set_ylabel("Count")
    ax[0].set_ylim(0, 48)
    ax[0].legend(frameon=False, loc="upper right")
    ax[0].set_title("(a) Spread of the two summaries")
    for v, col in [("oracle", GREEN), ("BSZZ", RED)]:
        s = pm[pm.train_label == v]
        ax[1].scatter(s.mcc, s.mcc_avg, s=18, color=col, label=NAME[v], zorder=3)
    lim = [-0.15, 0.35]
    ax[1].plot(lim, lim, "k--", lw=0.7)
    ax[1].set_xlim(lim)
    ax[1].set_ylim(lim)
    ax[1].set_xlabel("Terminal MCC")
    ax[1].set_ylabel("Time-averaged MCC")
    ax[1].legend(frameon=False)
    ax[1].set_title("(b) Per-project values")
    fig.tight_layout()
    save(fig, "fig_estimators")


def fig_factorial():
    f = pd.read_csv(ROOT / "results/phase2/latency_factorial.csv")
    m = f.groupby("project").mean(numeric_only=True)
    cells = {"frozen": ["A_frozen_immediate_mcc", "D_frozen_delayed_mcc"],
             "adaptive": ["B_adaptive_immediate_mcc", "C_adaptive_delayed_mcc"]}
    fig, ax = plt.subplots(figsize=(4.4, 2.9))
    for name, col, mk in [("frozen", GREY, "s"), ("adaptive", BLUE, "o")]:
        mean = m[cells[name]].mean().values
        se = m[cells[name]].std().values / np.sqrt(len(m))
        ax.errorbar([0, 1], mean, yerr=se, marker=mk, color=col, capsize=3,
                    label=f"{name.capitalize()} learner")
    ax.set_xticks([0, 1])
    ax.set_xticklabels(["Labels immediate", "Labels delayed"])
    ax.set_xlim(-0.3, 1.3)
    ax.set_ylabel("MCC (second half of stream)")
    ax.legend(frameon=False)
    save(fig, "fig_factorial")


def fig_anomaly(r):
    j = r[(r.model == "JITLine") & (r.regime == "chronological") & (r.eval_mode == "oracle")]
    m = j.groupby(["project", "train_label"]).mcc.mean().unstack()
    d = (m.BSZZ - m.oracle).sort_values()
    fig, ax = plt.subplots(figsize=(5.6, 3.9))
    ax.barh(d.index, d.values, color=[BLUE if v > 0 else RED for v in d.values])
    ax.axvline(0, color="k", lw=0.7)
    ax.set_xlabel("MCC with B-SZZ labels minus MCC with reference labels")
    ax.grid(axis="y", visible=False)
    save(fig, "fig_anomaly")


def fig_sensitivity():
    s = pd.read_csv(ROOT / "results/phase2/prequential_sensitivity_tests.csv")
    s["variant"] = s.comparison.str.replace("oracle_vs_", "")
    fad = sorted(s.fading.unique())
    fig, ax = plt.subplots(figsize=(5.6, 3.0))
    for v in VARIANTS:
        g = s[s.variant == v].groupby("fading").hodges_lehmann
        ax.plot(range(len(fad)), g.mean().loc[fad], marker="o", ms=3.5, label=NAME[v])
        ax.fill_between(range(len(fad)), g.min().loc[fad], g.max().loc[fad], alpha=0.12)
    ax.axhline(0, color="k", lw=0.7)
    ax.set_xticks(range(len(fad)))
    ax.set_xticklabels([f"{x:g}" for x in fad])
    ax.set_xlabel("Fading factor")
    ax.set_ylabel("Reference minus variant (MCC)")
    ax.set_ylim(-0.005, 0.085)
    ax.legend(frameon=False, ncol=3, loc="lower center", bbox_to_anchor=(0.5, 1.0))
    save(fig, "fig_sensitivity")


if __name__ == "__main__":
    commits, results, tests, bias = load()
    fig_projects(commits)
    fig_latency(commits)
    fig_szz_quality(bias)
    fig_szz_volume(bias)
    fig_szz_perproject(commits)
    fig_kappa(commits)
    fig_ladder(results)
    fig_leakage(results)
    fig_self_scoring(results)
    fig_label_source(results, tests)
    fig_estimators(results)
    fig_factorial()
    fig_anomaly(results)
    fig_sensitivity()

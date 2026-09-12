"""Generate the Phase 1 / Phase 2 result figures into reports/figures/.

Replaces the figure half of the retired scripts/generate_report.py. That script
also emitted a 600-line HTML/Markdown report whose framing went stale after the
Phase B analysis (it attributed the whole batch->stream drop to verification
latency, and predated mcc_avg, the Holm columns and the new test families).
Phase1_Phase2_Master_Results.md is the report now; this script only draws.

Every figure is derived from committed CSVs, so it is reproducible without
re-running any experiment:

  f1  Phase 1 label quality + the FP-heavy / FN-heavy split
  f2  The inflation ladder, literature number -> honest number
  f3  Self-deception gap, per model
  f4  Label-source comparison under both prequential estimators
  f5  Why the batch->stream contrast is confounded, plus the 2x2 that fixes it
  f6  Verification latency distribution against the W=90d window
  f7  Why the two estimators disagree (variance comparison)
  f8  Per-project JITLine BSZZ-over-oracle anomaly
  f9  What predicts that anomaly (nothing does) + the opennlp counter-example

Usage:
  python scripts/make_figures.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.append(str(ROOT))

OUT = ROOT / "reports" / "figures"
VARIANTS = ["BSZZ", "AGSZZ", "MASZZ", "LSZZ", "RSZZ", "RASZZ"]

plt.rcParams.update({
    "figure.dpi": 150, "savefig.dpi": 150, "savefig.bbox": "tight",
    "font.size": 9, "axes.grid": True, "grid.alpha": 0.25, "axes.axisbelow": True,
})


def _load():
    r = pd.read_csv(ROOT / "results/phase2/phase2_results.csv")
    return dict(
        results=r,
        oracle=r[r.eval_mode == "oracle"],
        commits=pd.read_csv(ROOT / "data/processed/phase2_commits.csv"),
        bias=json.load(open(ROOT / "phase1_bias.json")),
    )


def f1_phase1_noise(d):
    b = d["bias"]
    fig, ax = plt.subplots(1, 2, figsize=(10, 3.6))
    x = np.arange(len(VARIANTS)); w = 0.38
    ax[0].bar(x - w/2, [b[v]["precision"] for v in VARIANTS], w, label="Precision", color="#c0392b")
    ax[0].bar(x + w/2, [b[v]["recall"] for v in VARIANTS], w, label="Recall", color="#2980b9")
    ax[0].axhline(0.272, ls="--", c="k", lw=0.9)
    ax[0].text(0.05, 0.285, "precision ceiling 27.2%", fontsize=7)
    ax[0].set_xticks(x); ax[0].set_xticklabels(VARIANTS, rotation=20); ax[0].set_ylim(0, 0.8)
    ax[0].set_title("Phase 1: SZZ label quality vs oracle"); ax[0].legend(fontsize=7)
    r0 = [b[v]["fp_rate"] for v in VARIANTS]; r1 = [b[v]["fn_rate"] for v in VARIANTS]
    ax[1].scatter(r0, r1, s=70, c="#8e44ad", zorder=3)
    for v, a, c in zip(VARIANTS, r0, r1):
        ax[1].annotate(v, (a, c), textcoords="offset points", xytext=(5, 4), fontsize=7.5)
    ax[1].set_xlabel(r"$\rho_0$  false-alarm rate"); ax[1].set_ylabel(r"$\rho_1$  miss rate")
    ax[1].set_title("Asymmetric noise: FP-heavy vs FN-heavy")
    plt.tight_layout(); fig.savefig(OUT / "f1_phase1_noise.png"); plt.close(fig)


def f2_inflation_ladder(d):
    g = d["oracle"].groupby(["model", "regime", "train_label"]).mcc.mean()
    avg = d["oracle"][d["oracle"].regime == "prequential_latency"].groupby("train_label").mcc_avg.mean()
    self_bszz = d["results"][(d["results"].model == "JITLine") & (d["results"].regime == "naive_kfold")
                             & (d["results"].train_label == "BSZZ") & (d["results"].eval_mode == "self")].mcc.mean()
    cfg = [("JITLine BSZZ k-fold\nSELF-scored", self_bszz, "#7f8c8d"),
           ("JITLine oracle\nk-fold", g[("JITLine", "naive_kfold", "oracle")], "#e67e22"),
           ("LApredict oracle\nchronological", g[("LApredict", "chronological", "oracle")], "#f1c40f"),
           ("JITLine oracle\nchronological", g[("JITLine", "chronological", "oracle")], "#27ae60"),
           ("ORB oracle\nchrono-online", g[("ORB", "chronological_online", "oracle")], "#2980b9"),
           ("ORB oracle\nprequential+latency", avg["oracle"], "#8e44ad")]
    fig, ax = plt.subplots(figsize=(7.5, 4))
    ax.bar([c[0] for c in cfg], [c[1] for c in cfg], color=[c[2] for c in cfg])
    for i, c in enumerate(cfg):
        ax.text(i, c[1] + 0.008, f"{c[1]:.4f}", ha="center", fontsize=8)
    ax.set_ylabel("MCC (oracle-scored unless noted)")
    ax.set_title("From the literature's number to an honest one\n(last bar = time-averaged prequential)")
    plt.xticks(fontsize=7.5); plt.tight_layout(); fig.savefig(OUT / "f2_inflation_ladder.png"); plt.close(fig)


def f3_self_deception(d):
    r = d["results"]
    fig, ax = plt.subplots(figsize=(7.5, 3.8))
    x = np.arange(len(VARIANTS)); w = 0.38
    for i, (m, c) in enumerate([("JITLine", "#c0392b"), ("LApredict", "#2980b9")]):
        g = r[(r.model == m) & (r.regime == "naive_kfold")].groupby(["train_label", "eval_mode"]).mcc.mean().unstack()
        ax.bar(x + (i - 0.5) * w, [g.loc[v, "self"] - g.loc[v, "oracle"] for v in VARIANTS], w, label=m, color=c)
    ax.axhline(0, c="k", lw=0.8); ax.set_xticks(x); ax.set_xticklabels(VARIANTS)
    ax.set_ylabel("MCC inflation (self-scored − oracle-scored)")
    ax.set_title("Self-deception gap is model-dependent (naive k-fold)")
    ax.legend(fontsize=8); plt.tight_layout(); fig.savefig(OUT / "f3_self_deception.png"); plt.close(fig)


def f4_label_source(d):
    p = d["oracle"][d["oracle"].regime == "prequential_latency"]
    m = p.groupby("train_label")[["mcc", "mcc_avg"]].mean()
    order = ["oracle"] + sorted(VARIANTS, key=lambda v: -m.loc[v, "mcc_avg"])
    fig, ax = plt.subplots(figsize=(7.5, 3.8))
    x = np.arange(len(order)); w = 0.38
    ax.bar(x - w/2, [m.loc[l, "mcc_avg"] for l in order], w, label="time-averaged (primary)", color="#27ae60")
    ax.bar(x + w/2, [m.loc[l, "mcc"] for l in order], w, label="terminal fading", color="#bdc3c7")
    ax.axhline(0, c="k", lw=0.8); ax.set_xticks(x); ax.set_xticklabels(order, rotation=15)
    ax.set_ylabel("MCC (oracle-scored)")
    ax.set_title("ORB under real latency: label quality matters\n(oracle beats all six under the primary estimator)")
    ax.legend(fontsize=8); plt.tight_layout(); fig.savefig(OUT / "f4_label_source.png"); plt.close(fig)


def f5_decomposition(d):
    """The batch->stream contrast is confounded; show that, not a decomposition.

    An earlier version of this figure split the drop into "91% learner, 9%
    latency". That split was not identified: chronological_online and
    prequential_latency differ in three ways at once (frozen vs adaptive,
    immediate vs delayed labels, and second-half plain MCC vs whole-stream
    faded MCC). Matching only the window already flips the sign of the old
    contrast, from +0.0093 to -0.0222.

    Left panel: the descriptive ladder, with the confounded step marked.
    Right panel: the 2x2 that does identify the effects, from
    results/phase2/latency_factorial.csv.
    """
    g = d["oracle"].groupby(["model", "regime", "train_label"]).mcc.mean()
    la, ji = g[("LApredict", "chronological", "oracle")], g[("JITLine", "chronological", "oracle")]
    oc, op = g[("ORB", "chronological_online", "oracle")], g[("ORB", "prequential_latency", "oracle")]

    fig, ax = plt.subplots(1, 2, figsize=(12, 4.4))

    names = ["LApredict\nchronological", "JITLine\nchronological",
             "ORB\nchrono-online", "ORB\nprequential\n+latency"]
    vals = [la, ji, oc, op]
    ax[0].bar(names, vals, color=["#f1c40f", "#27ae60", "#2980b9", "#8e44ad"], width=0.6)
    for i, v in enumerate(vals):
        ax[0].text(i, v + 0.004, f"{v:.4f}", ha="center", fontsize=8.5, fontweight="bold")
    ax[0].annotate("", xy=(3, 0.13), xytext=(2, 0.13),
                   arrowprops=dict(arrowstyle="<->", color="#c0392b", lw=1.8))
    ax[0].text(2.5, 0.138, "CONFOUNDED\nlearner + regime + window\nall change here",
               ha="center", fontsize=7.5, color="#c0392b", fontweight="bold")
    ax[0].set_ylabel("MCC (oracle-scored, terminal)"); ax[0].set_ylim(0, 0.20)
    ax[0].set_title("Descriptive ladder -- NOT a causal decomposition", fontsize=9.5)
    ax[0].tick_params(labelsize=7.5)

    fpath = ROOT / "results" / "phase2" / "latency_factorial.csv"
    if fpath.exists():
        f = pd.read_csv(fpath).groupby("project").mean(numeric_only=True)
        cells = ["A_frozen_immediate", "B_adaptive_immediate", "C_adaptive_delayed"]
        labs = ["A frozen\n+ immediate", "B adaptive\n+ immediate", "C adaptive\n+ delayed"]
        m = [f[f"{c}_mcc"].mean() for c in cells]
        ax[1].bar(labs, m, color=["#2980b9", "#16a085", "#8e44ad"], width=0.6)
        for i, v in enumerate(m):
            ax[1].text(i, v + 0.003, f"{v:.4f}", ha="center", fontsize=8.5, fontweight="bold")
        top = max(m) * 1.68
        ax[1].annotate("", xy=(1, top * 0.86), xytext=(0, top * 0.86),
                       arrowprops=dict(arrowstyle="<->", color="#c0392b", lw=1.6))
        ax[1].text(0.5, top * 0.875, f"adaptivity {m[0]-m[1]:+.4f}\np = 0.11",
                   ha="center", fontsize=7.5, color="#c0392b", fontweight="bold")
        ax[1].annotate("", xy=(2, top * 0.70), xytext=(1, top * 0.70),
                       arrowprops=dict(arrowstyle="<->", color="#16a085", lw=1.6))
        ax[1].text(1.5, top * 0.715, f"latency {m[1]-m[2]:+.4f}\np = 0.34",
                   ha="center", fontsize=7.5, color="#16a085", fontweight="bold")
        ax[1].set_ylim(0, top)
        ax[1].set_ylabel("MCC (2nd half, plain -- identical window)")
        ax[1].set_title("The 2x2 that identifies them\n(3 seeds -- preliminary, neither significant)", fontsize=9.5)
        ax[1].tick_params(labelsize=7.5)
    else:
        ax[1].text(0.5, 0.5, "run experiments/run_latency_factorial.py",
                   ha="center", va="center", transform=ax[1].transAxes)

    plt.tight_layout(); fig.savefig(OUT / "f5_decomposition.png"); plt.close(fig)


def f6_latency(d):
    c = d["commits"]
    lat = ((c.fix_ts - c.author_ts) / 86400).dropna(); lat = lat[lat > 0]
    fig, ax = plt.subplots(figsize=(7.5, 3.6))
    ax.hist(np.clip(lat, 0, 1500), bins=70, color="#34495e")
    ax.axvline(90, c="#c0392b", lw=2, label="W = 90 d window")
    ax.axvline(lat.median(), c="#f39c12", lw=2, ls="--", label=f"median {lat.median():.0f} d")
    ax.set_xlabel("verification latency (days, clipped at 1500)"); ax.set_ylabel("commits")
    ax.set_title(f"{(lat>90).mean():.1%} of defect labels arrive AFTER the 90-day window\n"
                 "(first delivered as wrong 'clean' labels)")
    ax.legend(fontsize=8); plt.tight_layout(); fig.savefig(OUT / "f6_latency.png"); plt.close(fig)


def f7_estimators(d):
    p = d["oracle"][d["oracle"].regime == "prequential_latency"]
    pm = p.groupby(["project", "train_label"])[["mcc", "mcc_avg"]].mean().reset_index()
    fig, ax = plt.subplots(1, 2, figsize=(10, 3.6))
    for lab, col, c in [("terminal fading", "mcc", "#bdc3c7"), ("time-averaged", "mcc_avg", "#27ae60")]:
        ax[0].hist(pm[col], bins=25, alpha=0.65, label=f"{lab} (sd={pm[col].std():.3f})", color=c)
    ax[0].set_xlabel("project-level MCC"); ax[0].set_ylabel("count")
    ax[0].set_title("Terminal estimator has ~2x the spread"); ax[0].legend(fontsize=7.5)
    sub = pm[pm.train_label.isin(["oracle", "BSZZ"])]
    for v, c in [("oracle", "#27ae60"), ("BSZZ", "#c0392b")]:
        s = sub[sub.train_label == v]
        ax[1].scatter(s.mcc, s.mcc_avg, label=v, color=c, s=32, zorder=3)
    lim = [-0.15, 0.35]; ax[1].plot(lim, lim, "k--", lw=0.8); ax[1].set_xlim(lim); ax[1].set_ylim(lim)
    ax[1].set_xlabel("terminal MCC"); ax[1].set_ylabel("time-averaged MCC")
    ax[1].set_title("Per project: averaged > terminal almost everywhere"); ax[1].legend(fontsize=8)
    plt.tight_layout(); fig.savefig(OUT / "f7_estimators.png"); plt.close(fig)


def f8_jitline_anomaly(d):
    o = d["oracle"]
    j = o[(o.model == "JITLine") & (o.regime == "chronological")].groupby(
        ["project", "train_label"]).mcc.mean().unstack()
    diff = (j.BSZZ - j.oracle).sort_values()
    fig, ax = plt.subplots(figsize=(7.5, 4.2))
    ax.barh(range(len(diff)), diff.values, color=["#27ae60" if v < 0 else "#c0392b" for v in diff.values])
    ax.set_yticks(range(len(diff))); ax.set_yticklabels(diff.index, fontsize=7)
    ax.axvline(0, c="k", lw=0.8)
    ax.set_xlabel("MCC(BSZZ-trained) − MCC(oracle-trained)")
    ax.set_title(f"JITLine chronological: BSZZ beats oracle in {int((diff>0).sum())}/21 projects\n"
                 "(FP-heavy noise as accidental minority augmentation)")
    plt.tight_layout(); fig.savefig(OUT / "f8_jitline_anomaly.png"); plt.close(fig)


def f9_anomaly_predictors(d):
    """Where BSZZ beats oracle -- and why the enrichment story is incomplete.

    The per-project gap is stable (97.7% of its between-project variance is real
    rather than seed noise, 16/21 projects >2 SE from zero), but no project
    characteristic predicts it. opennlp is the load-bearing counter-example:
    a large BSZZ win where BSZZ supplies FEWER positives than the oracle, so
    minority enrichment cannot be the mechanism there.
    """
    o, c = d["oracle"], d["commits"]
    j = o[(o.model == "JITLine") & (o.regime == "chronological")]
    piv = j.groupby(["project", "train_label"]).mcc.mean().unstack()
    gap = (piv.BSZZ - piv.oracle)
    stats_ = {}
    for proj, g in c.groupby("project"):
        half = g.sort_values("author_ts").iloc[:len(g) // 2]
        stats_[proj] = (int(half.label_oracle.sum()),
                        g.label_BSZZ.mean() / g.label_oracle.mean())
    tp = pd.Series({k: v[0] for k, v in stats_.items()})
    en = pd.Series({k: v[1] for k, v in stats_.items()})

    fig, ax = plt.subplots(1, 2, figsize=(10, 4))
    for a, x, xlab, title in [
        (ax[0], tp, "oracle positives in the chronological training half",
         "Starvation: directionally right, not significant\n(Mann-Whitney p = 0.25 on a median split)"),
        (ax[1], en, "BSZZ positive rate / oracle positive rate",
         "Enrichment does not explain it\n(opennlp: a large BSZZ win with FEWER positives)")]:
        col = ["#c0392b" if v > 0 else "#27ae60" for v in gap[x.index]]
        a.scatter(x, gap[x.index], c=col, s=45, zorder=3)
        a.axhline(0, c="k", lw=0.8)
        a.set_xlabel(xlab); a.set_ylabel("MCC(BSZZ) − MCC(oracle)")
        a.set_title(title, fontsize=9)
    ax[1].axvline(1.0, ls="--", c="#7f8c8d", lw=1)
    ax[1].text(1.15, gap.max() * 0.92, "1x = same positive rate", fontsize=7, color="#7f8c8d")
    for a, x in [(ax[0], tp), (ax[1], en)]:
        a.annotate("opennlp", (x["opennlp"], gap["opennlp"]),
                   textcoords="offset points", xytext=(8, -2), fontsize=8, fontweight="bold")
    fig.suptitle("Red = BSZZ-trained JITLine beat oracle-trained (13/21 projects)", fontsize=9, y=1.02)
    plt.tight_layout(); fig.savefig(OUT / "f9_anomaly_predictors.png"); plt.close(fig)


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    d = _load()
    for fn in (f1_phase1_noise, f2_inflation_ladder, f3_self_deception, f4_label_source,
               f5_decomposition, f6_latency, f7_estimators, f8_jitline_anomaly,
           f9_anomaly_predictors):
        fn(d)
        print(f"  [OK] {fn.__name__}")
    print(f"\n9 figures written to {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

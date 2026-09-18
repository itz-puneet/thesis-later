"""Phase 3 ADDENDUM: close the four causal gaps in the repair/compression story.
Place at: experiments/run_phase3_addendum.py

Conditions added (all reuse existing machinery):

A. error_matched   -- remove a RANDOM |FN|-sized subset of BSZZ's FPs (seeded),
                      so FP-repair and FN-repair correct the same label mass.
B. repair_fraction -- repair 25/50/75/100% of each error type separately:
                      the two slopes are the marginal MCC value per corrected
                      label of each error type (dose-controlled repair).
C. fn_ceiling      -- restore FNs with IMMEDIATE delivery (fix_ts = author_ts+1s)
                      and, separately, delivery exactly at t+W: separates
                      "FNs don't matter" from "FNs can't arrive in time".
D. no_latency arm  -- dose-response with labels delivered at t+1s (true
                      no-latency control; the existing 'uniform' arm delays
                      everything by W and cannot test latency masking).

Also runs a TOST equivalence test (margin +-0.02 MCC, pre-declared) on the
original FN-repair null, upgrading absence-of-evidence to evidence-of-absence
if it passes.

Outputs (results/phase3/): phase3_addendum.csv, phase3_addendum_stats.csv,
phase3_dose_nolatency.csv

Usage:
  python -m experiments.run_phase3_addendum --fast    # 3 seeds, 5 projects
  python -m experiments.run_phase3_addendum
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import wilcoxon

sys.path.append(str(Path(__file__).resolve().parent.parent))

from codebase.config import ORB_CONFIG, RANDOM_SEEDS
from codebase.data.loader import load_or_build_dataset, get_all_projects, get_project_dataset
from codebase.evaluation.regimes import prequential_latency
from codebase.online.orb import ORB
from codebase.noise.injection import (
    load_bias_profiles, symmetric_noise, asymmetric_noise, impute_fix_ts)

OUT = Path("results/phase3"); OUT.mkdir(parents=True, exist_ok=True)
FRACTIONS = [0.25, 0.50, 0.75, 1.00]
DOSES = [0.05, 0.10, 0.15, 0.20, 0.25, 0.30]
TOST_MARGIN = 0.02  # pre-declared equivalence margin for the FN-repair null


def run_orb(frame, label_col, seed, latency_mode, fix_ts_col=None):
    orb = ORB(seed=seed, **ORB_CONFIG)
    r = prequential_latency(orb, frame, label_col, eval_label_col="label_oracle",
                            latency_mode=latency_mode, fix_ts_col=fix_ts_col)
    hist = pd.DataFrame(r["history"]) if r.get("history") else pd.DataFrame()
    return dict(mcc=r["mcc"], gmean=r["gmean"],
                mcc_avg=float(hist["mcc"].mean()) if "mcc" in hist else r["mcc"],
                gmean_avg=float(hist["gmean"].mean()) if "gmean" in hist else r["gmean"])


def _immediate_fix_ts(df, labels, at_window=False):
    """Delivery-ceiling fix_ts: positives arrive at t+1s (or exactly t+W)."""
    d = df.copy()
    W = 90 * 86400.0
    t = d["author_ts"].to_numpy(dtype=float)
    out = np.full(len(d), np.nan)
    pos = np.asarray(labels, dtype=int) == 1
    out[pos] = t[pos] + (W if at_window else 1.0)
    d["fix_ts_ceiling"] = out
    return d


def repair_addendum(df, project, seeds):
    """Conditions A, B, C on real BSZZ labels, real latency."""
    o = df["label_oracle"].to_numpy(dtype=int)
    b = df["label_BSZZ"].to_numpy(dtype=int)
    fp_idx = np.where((b == 1) & (o == 0))[0]
    fn_idx = np.where((b == 0) & (o == 1))[0]
    rows = []
    for seed in seeds:
        rng = np.random.default_rng(seed)
        conds = {}

        # A: error-matched FP removal (|FN| randomly chosen FPs)
        k = min(len(fn_idx), len(fp_idx))
        sel = rng.choice(fp_idx, size=k, replace=False)
        lab = b.copy(); lab[sel] = 0
        conds[f"fp_repair_matched(n={k})"] = (lab, "fix_ts_BSZZ", df)

        # B: repair-fraction curves for both error types
        for f in FRACTIONS:
            selp = rng.choice(fp_idx, size=int(round(f * len(fp_idx))), replace=False)
            lab = b.copy(); lab[selp] = 0
            conds[f"fp_repair_frac_{f:.2f}"] = (lab, "fix_ts_BSZZ", df)

            seln = rng.choice(fn_idx, size=int(round(f * len(fn_idx))), replace=False)
            lab = b.copy(); lab[seln] = 1
            d = impute_fix_ts(df, lab, seed)             # realistic delivery
            conds[f"fn_repair_frac_{f:.2f}"] = (lab, "fix_ts_noisy", d)

        # C: FN delivery ceilings (full restoration, immediate / at-window)
        lab_full = b.copy(); lab_full[fn_idx] = 1
        d_imm = _immediate_fix_ts(df, lab_full, at_window=False)
        conds["fn_repair_immediate"] = (lab_full, "fix_ts_ceiling", d_imm)
        d_w = _immediate_fix_ts(df, lab_full, at_window=True)
        conds["fn_repair_at_window"] = (lab_full, "fix_ts_ceiling", d_w)

        # anchors
        conds["BSZZ"] = (b, "fix_ts_BSZZ", df)

        for name, (labels, ftcol, frame) in conds.items():
            fr = frame.copy(); fr["label_cond"] = labels
            r = run_orb(fr, "label_cond", seed, "real", fix_ts_col=ftcol)
            rows.append(dict(project=project, seed=seed, condition=name, **r))
    return rows


def dose_nolatency(df, project, seeds, profiles):
    """Condition D: dose-response with labels at t+1s (no-latency control)."""
    y = df["label_oracle"].to_numpy(dtype=int)
    rows = []
    for seed in seeds:
        for profile in ["symmetric", "fp_heavy", "mid", "fn_heavy"]:
            for dose in DOSES:
                if profile == "symmetric":
                    noisy = symmetric_noise(y, dose, seed)
                else:
                    key = {"fp_heavy": "BSZZ", "mid": "RASZZ", "fn_heavy": "LSZZ"}[profile]
                    noisy = asymmetric_noise(y, dose, *profiles[key], seed)
                d = _immediate_fix_ts(df, noisy)
                d["label_noisy"] = noisy
                r = run_orb(d, "label_noisy", seed, "real", fix_ts_col="fix_ts_ceiling")
                rows.append(dict(project=project, seed=seed, profile=profile,
                                 dose=dose, latency="none", **r))
    return rows


def tost_fn_null():
    """Equivalence test on the ORIGINAL FN-repair result (mcc_avg)."""
    rep = pd.read_csv(OUT / "phase3_repair.csv")
    piv = rep.groupby(["project", "condition"])["mcc_avg"].mean().unstack()
    d = (piv["BSZZ_fn_repaired"] - piv["BSZZ"]).dropna()
    # Wilcoxon-based TOST: reject "diff <= -m" and "diff >= +m"
    p_lower = wilcoxon(d + TOST_MARGIN, alternative="greater").pvalue
    p_upper = wilcoxon(d - TOST_MARGIN, alternative="less").pvalue
    p_tost = max(p_lower, p_upper)
    return dict(test="TOST_fn_repair_vs_BSZZ", margin=TOST_MARGIN, n=len(d),
                mean_diff=float(d.mean()), p_lower=float(p_lower),
                p_upper=float(p_upper), p_tost=float(p_tost),
                equivalent_at_05=bool(p_tost < 0.05))


def main(fast: bool):
    df_all = load_or_build_dataset()
    profiles = load_bias_profiles()
    projects = get_all_projects(df_all)
    seeds = RANDOM_SEEDS[:3] if fast else RANDOM_SEEDS
    if fast:
        projects = projects[:5]

    add_rows, dose_rows = [], []
    for p in projects:
        print(f">>> {p}")
        dfp = get_project_dataset(p, df_all)
        add_rows += repair_addendum(dfp, p, seeds)
        dose_rows += dose_nolatency(dfp, p, seeds, profiles)
        pd.DataFrame(add_rows).to_csv(OUT / "phase3_addendum.csv", index=False)

    pd.DataFrame(add_rows).to_csv(OUT / "phase3_addendum.csv", index=False)
    pd.DataFrame(dose_rows).to_csv(OUT / "phase3_dose_nolatency.csv", index=False)

    # paired stats vs BSZZ anchor
    a = pd.DataFrame(add_rows)
    piv = a.groupby(["project", "condition"])["mcc_avg"].mean().unstack()
    stats = []
    for c in [c for c in piv.columns if c != "BSZZ"]:
        d = (piv[c] - piv["BSZZ"]).dropna()
        if len(d) >= 6:
            stats.append(dict(condition=c, n=len(d), mean_diff=float(d.mean()),
                              wins=int((d > 0).sum()),
                              p=float(wilcoxon(piv[c].dropna(),
                                               piv["BSZZ"].reindex(d.index)).pvalue)))
    stats.append(tost_fn_null())
    pd.DataFrame(stats).to_csv(OUT / "phase3_addendum_stats.csv", index=False)
    print(pd.DataFrame(stats).round(4).to_string(index=False))
    print(f"\nSaved to {OUT}/")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--fast", action="store_true")
    main(ap.parse_args().fast)

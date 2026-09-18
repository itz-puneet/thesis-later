"""Phase 3 ADDENDUM: close the four causal gaps in the repair story.

Written against the supervisor's Deep_Review_Phase3.md. The design is theirs;
the implementation differs from the script shipped with that review in four
places where the shipped version would not have tested what it claimed:

  * Condition D ("no-latency arm") set fix_ts on POSITIVES only. In
    prequential_latency, fix_ts is consulted only when the training label is 1;
    negatives -- 91.5% of this corpus -- are delayed by W unconditionally. That
    arm therefore still carried the dominant latency effect. This module uses a
    real latency_mode="none" added to regimes.py instead.

  * Condition C accelerated EVERY positive in the repaired vector, BSZZ's own
    1,495 true and 6,565 false positives included, then compared against a
    realistically-delivered BSZZ. That conflates "restored the FNs" with
    "accelerated every positive label". Anchors BSZZ_immediate and
    BSZZ_at_window are added so the ceiling contrast isolates the restoration.

  * mcc_avg was recomputed from the history frame with a silent fallback to the
    TERMINAL mcc if the key was missing. prequential_latency already returns
    mcc_avg; that is what is used here.

  * The paired statistics carried no effect size, no interval and no
    multiplicity correction. They now use the same paired_effect + Holm
    machinery as Phases 2 and 3.

Conditions (all on real BSZZ labels, real latency unless stated):
  anchors           BSZZ, BSZZ_immediate, BSZZ_at_window
  A error-matched   remove a random |FN|-sized subset of the FPs, so FP-repair
                    and FN-repair correct the same label mass (8:1 confound)
  B repair-fraction repair 25/50/75/100% of each error type separately; the
                    slopes are the marginal MCC value per corrected label
  C delivery ceiling FNs restored with immediate / at-window arrival, against
                    the matching anchor: separates "FNs do not matter" from
                    "FNs cannot arrive in time to matter"
  D no-latency arm  dose-response with latency_mode="none"

Plus a TOST equivalence test (pre-declared margin +-0.02 MCC) on the original
FN-repair null, upgrading absence of evidence to evidence of absence if it
passes.

Outputs (results/phase3/): phase3_addendum.csv, phase3_addendum_stats.csv,
phase3_marginal_value.csv, phase3_dose_nolatency.csv

Usage:
  python -m experiments.run_phase3_addendum --fast   # 3 seeds, 5 projects
  python -m experiments.run_phase3_addendum
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import wilcoxon

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.append(str(BASE_DIR))

from codebase.config import ORB_CONFIG, RANDOM_SEEDS
from codebase.data.loader import (load_or_build_dataset, get_all_projects,
                                  get_project_dataset)
from codebase.evaluation.metrics import paired_effect
from codebase.evaluation.regimes import prequential_latency
from codebase.online.orb import ORB
from codebase.noise.injection import (load_bias_profiles, symmetric_noise,
                                      asymmetric_noise, impute_fix_ts)
from experiments.run_phase2_impact import _holm

OUT = BASE_DIR / "results" / "phase3"
OUT.mkdir(parents=True, exist_ok=True)

FRACTIONS = [0.25, 0.50, 0.75, 1.00]
DOSES = [0.05, 0.10, 0.15, 0.20, 0.25, 0.30]
TOST_MARGIN = 0.02          # pre-declared, half the measured FP-repair effect
W_SECONDS = 90 * 86400.0
PROFILE_SOURCES = {"fp_heavy": "BSZZ", "mid": "RASZZ", "fn_heavy": "LSZZ"}


def run_orb(frame: pd.DataFrame, label_col: str, seed: int,
            latency_mode: str, fix_ts_col: str | None = None) -> dict:
    orb = ORB(seed=seed, **ORB_CONFIG)
    r = prequential_latency(orb, frame, label_col, eval_label_col="label_oracle",
                            latency_mode=latency_mode, fix_ts_col=fix_ts_col)
    return dict(mcc_avg=r["mcc_avg"], gmean_avg=r["gmean_avg"],
                mcc=r["mcc"], gmean=r["gmean"])


def _positive_arrival(df: pd.DataFrame, labels: np.ndarray,
                      at_window: bool = False) -> pd.DataFrame:
    """fix_ts placing every positive label at t+1s (or exactly t+W).

    Only positives are affected because only positives consult fix_ts. The
    negative stream still arrives at t+W, which is why this is a *ceiling on
    positive delivery* and not a no-latency arm -- see latency_mode="none".
    """
    d = df.copy()
    t = d["author_ts"].to_numpy(dtype=float)
    out = np.full(len(d), np.nan)
    pos = np.asarray(labels, dtype=int) == 1
    out[pos] = t[pos] + (W_SECONDS if at_window else 1.0)
    d["fix_ts_ceiling"] = out
    return d


def repair_addendum(df: pd.DataFrame, project: str, seeds: list[int]) -> list:
    o = df["label_oracle"].to_numpy(dtype=int)
    b = df["label_BSZZ"].to_numpy(dtype=int)
    fp_idx = np.where((b == 1) & (o == 0))[0]
    fn_idx = np.where((b == 0) & (o == 1))[0]
    rows = []

    for seed in seeds:
        rng = np.random.default_rng(seed)
        conds: dict[str, tuple] = {}

        # --- anchors ----------------------------------------------------
        conds["BSZZ"] = (b, "fix_ts_BSZZ", df, "real")
        conds["BSZZ_immediate"] = (b, "fix_ts_ceiling",
                                   _positive_arrival(df, b), "real")
        conds["BSZZ_at_window"] = (b, "fix_ts_ceiling",
                                   _positive_arrival(df, b, True), "real")

        # --- A: error-matched FP removal --------------------------------
        k = min(len(fn_idx), len(fp_idx))
        if k > 0:
            lab = b.copy()
            lab[rng.choice(fp_idx, size=k, replace=False)] = 0
            conds["fp_repair_matched"] = (lab, "fix_ts_BSZZ", df, "real")

        # --- B: repair-fraction curves ----------------------------------
        for f in FRACTIONS:
            if len(fp_idx):
                lab = b.copy()
                lab[rng.choice(fp_idx, size=int(round(f * len(fp_idx))),
                               replace=False)] = 0
                conds[f"fp_repair_frac_{f:.2f}"] = (lab, "fix_ts_BSZZ", df, "real")
            if len(fn_idx):
                lab = b.copy()
                lab[rng.choice(fn_idx, size=int(round(f * len(fn_idx))),
                               replace=False)] = 1
                d = impute_fix_ts(df, lab, seed)
                conds[f"fn_repair_frac_{f:.2f}"] = (lab, "fix_ts_noisy", d, "real")

        # --- C: FN delivery ceilings ------------------------------------
        if len(fn_idx):
            full = b.copy(); full[fn_idx] = 1
            conds["fn_repair_immediate"] = (full, "fix_ts_ceiling",
                                            _positive_arrival(df, full), "real")
            conds["fn_repair_at_window"] = (full, "fix_ts_ceiling",
                                            _positive_arrival(df, full, True), "real")

        for name, (labels, ftcol, frame, mode) in conds.items():
            fr = frame.copy()
            fr["label_cond"] = labels
            r = run_orb(fr, "label_cond", seed, mode, fix_ts_col=ftcol)
            rows.append(dict(project=project, seed=seed, condition=name,
                             n_fp_available=len(fp_idx), n_fn_available=len(fn_idx),
                             n_labels_corrected=_corrected(name, len(fp_idx), len(fn_idx), k),
                             **r))
    return rows


def _corrected(name: str, n_fp: int, n_fn: int, k: int) -> int:
    """How many labels this condition actually changed, for marginal value."""
    if name.startswith("fp_repair_frac_"):
        return int(round(float(name.rsplit("_", 1)[1]) * n_fp))
    if name.startswith("fn_repair_frac_"):
        return int(round(float(name.rsplit("_", 1)[1]) * n_fn))
    if name == "fp_repair_matched":
        return k
    if name.startswith("fn_repair_"):
        return n_fn
    return 0


def dose_nolatency(df: pd.DataFrame, project: str, seeds: list[int],
                   profiles: dict) -> list:
    """Condition D: the true no-latency dose-response arm."""
    y = df["label_oracle"].to_numpy(dtype=int)
    rows = []
    for seed in seeds:
        for profile in ["symmetric", "fp_heavy", "mid", "fn_heavy"]:
            for dose in DOSES:
                if profile == "symmetric":
                    noisy = symmetric_noise(y, dose, seed)
                else:
                    rho0, rho1 = profiles[PROFILE_SOURCES[profile]]
                    noisy = asymmetric_noise(y, dose, rho0, rho1, seed)
                d = df.copy()
                d["label_noisy"] = noisy
                r = run_orb(d, "label_noisy", seed, "none")
                rows.append(dict(project=project, seed=seed, profile=profile,
                                 dose=dose, latency="none",
                                 n_pos_true=int((y == 1).sum()),
                                 n_pos_noisy=int((noisy == 1).sum()),
                                 n_pos_retained=int(((y == 1) & (noisy == 1)).sum()),
                                 **r))
    return rows


def tost_fn_null() -> dict:
    """Equivalence test on the ORIGINAL FN-repair null (mcc_avg)."""
    rep = pd.read_csv(OUT / "phase3_repair.csv")
    piv = rep.groupby(["project", "condition"])["mcc_avg"].mean().unstack()
    d = (piv["BSZZ_fn_repaired"] - piv["BSZZ"]).dropna().to_numpy()
    p_lower = wilcoxon(d + TOST_MARGIN, alternative="greater").pvalue
    p_upper = wilcoxon(d - TOST_MARGIN, alternative="less").pvalue
    p_tost = float(max(p_lower, p_upper))
    return dict(test="TOST_fn_repair_vs_BSZZ", margin=TOST_MARGIN, n=len(d),
                mean_diff=float(d.mean()), p_lower=float(p_lower),
                p_upper=float(p_upper), p_tost=p_tost,
                equivalent_at_05=bool(p_tost < 0.05))


def _contrast(piv: pd.DataFrame, a: str, b: str, family: str) -> dict | None:
    if a not in piv.columns or b not in piv.columns:
        return None
    both = piv[[a, b]].dropna()
    if len(both) < 6:
        return None
    e = paired_effect(both[a].to_numpy(), both[b].to_numpy())
    return dict(family=family, A=a, B=b, n=len(both),
                mean_A=float(both[a].mean()), mean_B=float(both[b].mean()),
                hodges_lehmann=e["hodges_lehmann"], ci_low=e["ci_low"],
                ci_high=e["ci_high"], rank_biserial=e["rank_biserial"],
                n_favouring_A=int((both[a] > both[b]).sum()), p=e["p_value"])


def analyse(add: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    piv = add.groupby(["project", "condition"])["mcc_avg"].mean().unstack()
    rows = []

    # Everything against the realistic BSZZ anchor.
    for c in sorted(piv.columns):
        if c == "BSZZ":
            continue
        r = _contrast(piv, c, "BSZZ", "vs_BSZZ_anchor")
        if r:
            rows.append(r)

    # The error-matched contrast: same label mass corrected on both sides.
    rows += [r for r in [
        _contrast(piv, "fp_repair_matched", "fn_repair_frac_1.00", "error_matched"),
        _contrast(piv, "fp_repair_matched", "BSZZ", "error_matched"),
    ] if r]

    # Delivery ceiling, isolated against its own anchor.
    rows += [r for r in [
        _contrast(piv, "fn_repair_immediate", "BSZZ_immediate", "delivery_ceiling"),
        _contrast(piv, "fn_repair_at_window", "BSZZ_at_window", "delivery_ceiling"),
        _contrast(piv, "BSZZ_immediate", "BSZZ", "delivery_ceiling"),
    ] if r]

    stats = pd.DataFrame(rows)
    if not stats.empty:
        stats["p_holm"] = np.nan
        for _, g in stats.groupby("family"):
            stats.loc[g.index, "p_holm"] = _holm(g["p"].to_numpy())
        stats["p_holm_global"] = _holm(stats["p"].to_numpy())

    # Marginal value per corrected label, from the repair-fraction curves.
    marg = []
    corrected = add.groupby("condition")["n_labels_corrected"].mean()
    for kind in ["fp", "fn"]:
        pts = []
        for f in FRACTIONS:
            c = f"{kind}_repair_frac_{f:.2f}"
            if c in piv.columns:
                d = (piv[c] - piv["BSZZ"]).dropna()
                pts.append((float(corrected.get(c, np.nan)), float(d.mean())))
        pts = [(x, y) for x, y in pts if np.isfinite(x)]
        if len(pts) >= 2:
            xs, ys = np.array([p[0] for p in pts]), np.array([p[1] for p in pts])
            slope = float(np.polyfit(xs, ys, 1)[0])
            marg.append(dict(error_type=kind, n_points=len(pts),
                             max_labels_corrected=float(xs.max()),
                             delta_mcc_at_full=float(ys[-1]),
                             mcc_per_1000_labels=round(slope * 1000, 5)))
    return stats, pd.DataFrame(marg)


def main(fast: bool):
    df_all = load_or_build_dataset()
    profiles = load_bias_profiles()
    projects = get_all_projects(df_all)
    seeds = RANDOM_SEEDS[:3] if fast else RANDOM_SEEDS
    if fast:
        projects = projects[:5]

    add_rows, dose_rows = [], []
    for p in projects:
        print(f">>> {p}", flush=True)
        dfp = get_project_dataset(p, df_all)
        add_rows += repair_addendum(dfp, p, seeds)
        dose_rows += dose_nolatency(dfp, p, seeds, profiles)

    add = pd.DataFrame(add_rows)
    add.to_csv(OUT / "phase3_addendum.csv", index=False)
    pd.DataFrame(dose_rows).to_csv(OUT / "phase3_dose_nolatency.csv", index=False)

    stats, marg = analyse(add)
    stats.to_csv(OUT / "phase3_addendum_stats.csv", index=False)
    marg.to_csv(OUT / "phase3_marginal_value.csv", index=False)
    pd.DataFrame([tost_fn_null()]).to_csv(OUT / "phase3_tost.csv", index=False)

    pd.set_option("display.width", 220)
    print("\n=== Paired contrasts (mcc_avg, primary estimator) ===")
    if stats.empty:
        # Every contrast needs n >= 6 projects for the signed-rank test to be
        # able to reach significance at all; --fast runs 5 and so yields none.
        print("  (none: fewer than 6 paired projects -- expected under --fast)")
    else:
        cols = ["family", "A", "B", "hodges_lehmann", "ci_low", "ci_high",
                "rank_biserial", "n_favouring_A", "p_holm", "p_holm_global"]
        print(stats[cols].round(4).to_string(index=False))
    print("\n=== Marginal value per corrected label ===")
    print("  (none)" if marg.empty else marg.to_string(index=False))
    print("\n=== TOST on the FN-repair null ===")
    print(pd.DataFrame([tost_fn_null()]).round(4).to_string(index=False))
    print(f"\nSaved to {OUT}/")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--fast", action="store_true")
    main(ap.parse_args().fast)

"""Phase 3: dose-response + mechanism + repair experiments.
Place at: experiments/run_phase3_noise.py  (replaces the empty file).

Design (reflecting the measured Phase 1/2 reality):

A) DOSE-RESPONSE. Inject noise into label_oracle under 4 profiles:
     symmetric (control), FP-heavy (BSZZ bias), mid (RASZZ), FN-heavy (LSZZ),
   at doses 5..30%, run ORB, score against clean oracle.
   Two latency arms:
     uniform  -- PRIMARY: isolates noise mechanics from latency effects
     real     -- sensitivity: uses impute_fix_ts() so injected FP flips don't
                 silently self-filter (unlinked commits never deliver labels)

B) MECHANISM. From orb.trace, record mean boost/lambda received by
   (i) truly-defective, (ii) falsely-positive, (iii) falsely-negative-affected
   training instances -- evidence for amplification vs starvation.

C) REPAIR (causal, on REAL labels -- the strongest claim in the chapter).
   Conditions: BSZZ as-is, BSZZ with FPs surgically removed (oracle knowledge),
   BSZZ with FNs restored, oracle. Which repair recovers more ORB performance
   directly tests FP-amplification vs FN-starvation on real labels.

Outputs (results/phase3/):
  phase3_dose_response.csv, phase3_mechanism.csv, phase3_repair.csv

Usage:
  python -m experiments.run_phase3_noise --fast     # 3 seeds, 5 projects
  python -m experiments.run_phase3_noise            # full
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.append(str(Path(__file__).resolve().parent.parent))

from codebase.config import ORB_CONFIG, RANDOM_SEEDS
from codebase.data.loader import load_or_build_dataset, get_all_projects, get_project_dataset
from codebase.evaluation.regimes import prequential_latency
from codebase.online.orb import ORB
from codebase.noise.injection import (
    load_bias_profiles, symmetric_noise, asymmetric_noise, impute_fix_ts)

OUT = Path("results/phase3"); OUT.mkdir(parents=True, exist_ok=True)
DOSES = [0.05, 0.10, 0.15, 0.20, 0.25, 0.30]
PROFILE_SOURCES = {"fp_heavy": "BSZZ", "mid": "RASZZ", "fn_heavy": "LSZZ"}


def make_noisy(y: np.ndarray, profile: str, dose: float, seed: int,
               profiles: dict) -> np.ndarray:
    if profile == "symmetric":
        return symmetric_noise(y, dose, seed)
    rho0, rho1 = profiles[PROFILE_SOURCES[profile]]
    return asymmetric_noise(y, dose, rho0, rho1, seed)


def run_orb(df: pd.DataFrame, label_col: str, seed: int,
            latency_mode: str, fix_ts_col: str | None = None):
    orb = ORB(seed=seed, **ORB_CONFIG)
    res = prequential_latency(orb, df, label_col, eval_label_col="label_oracle",
                              latency_mode=latency_mode, fix_ts_col=fix_ts_col)
    return orb, res


def mechanism_stats(orb: ORB, df_sorted: pd.DataFrame, label_col: str) -> dict:
    """Boost/lambda mass received by each label-error class.

    Trace rows are appended per learn_one in arrival order; we align them by
    replaying arrival identity via the trace's own y and the error masks'
    marginal rates (per-class aggregate, robust to ordering).
    """
    tr = pd.DataFrame(orb.trace)
    if tr.empty:
        return {}
    o = df_sorted["label_oracle"].to_numpy()
    s = df_sorted[label_col].to_numpy()
    return dict(
        mean_boost_pos_labels=float(tr.loc[tr.y == 1, "boost"].mean()),
        mean_lam_pos_labels=float(tr.loc[tr.y == 1, "lam"].mean()),
        mean_boost_neg_labels=float(tr.loc[tr.y == 0, "boost"].mean()),
        fp_label_rate=float(((s == 1) & (o == 0)).mean()),
        fn_label_rate=float(((s == 0) & (o == 1)).mean()),
        final_ma_pred=float(tr["ma_pred"].iloc[-1]) if "ma_pred" in tr else np.nan,
    )


def dose_response(df: pd.DataFrame, project: str, seeds: list[int],
                  profiles: dict, latency_arms: list[str]) -> tuple[list, list]:
    rows, mech = [], []
    y = df["label_oracle"].to_numpy(dtype=int)
    for seed in seeds:
        for profile in ["symmetric", "fp_heavy", "mid", "fn_heavy"]:
            for dose in DOSES:
                noisy = make_noisy(y, profile, dose, seed, profiles)
                d = df.copy(); d["label_noisy"] = noisy
                for arm in latency_arms:
                    if arm == "real":
                        d2 = impute_fix_ts(d, noisy, seed)   # adds fix_ts_noisy
                        orb, r = run_orb(d2, "label_noisy", seed, "real",
                                         fix_ts_col="fix_ts_noisy")
                    else:
                        orb, r = run_orb(d, "label_noisy", seed, "uniform")
                    rec = dict(project=project, seed=seed, profile=profile,
                               dose=dose, latency=arm,
                               mcc=r["mcc"], gmean=r["gmean"])
                    rows.append(rec)
                    ds = d.sort_values("author_ts").reset_index(drop=True)
                    mech.append({**rec, **mechanism_stats(orb, ds, "label_noisy")})
    return rows, mech


def repair_experiment(df: pd.DataFrame, project: str, seeds: list[int]) -> list:
    """BSZZ vs FP-repaired vs FN-repaired vs oracle, under REAL latency."""
    rows = []
    o = df["label_oracle"].to_numpy(dtype=int)
    b = df["label_BSZZ"].to_numpy(dtype=int)
    conds = {
        "BSZZ": (b, "fix_ts_BSZZ"),
        "BSZZ_fp_repaired": (np.where((b == 1) & (o == 0), 0, b), "fix_ts_BSZZ"),
        "BSZZ_fn_repaired": (np.where((b == 0) & (o == 1), 1, b), None),  # needs imputation
        "oracle": (df["label_oracle"].to_numpy(dtype=int), None),
    }
    for seed in seeds:
        for name, (labels, ftcol) in conds.items():
            d = df.copy(); d["label_cond"] = labels
            if ftcol is None:
                d = impute_fix_ts(d, labels, seed, base_col="fix_ts")
                ftcol = "fix_ts_noisy"
            _, r = run_orb(d, "label_cond", seed, "real", fix_ts_col=ftcol)
            rows.append(dict(project=project, seed=seed, condition=name,
                             mcc=r["mcc"], gmean=r["gmean"]))
    return rows


def main(fast: bool):
    df_all = load_or_build_dataset()
    profiles = load_bias_profiles()
    projects = get_all_projects(df_all)
    seeds = RANDOM_SEEDS[:3] if fast else RANDOM_SEEDS
    if fast:
        projects = projects[:5]
    latency_arms = ["uniform"] if fast else ["uniform", "real"]

    all_rows, all_mech, all_repair = [], [], []
    for p in projects:
        print(f">>> {p}")
        dfp = get_project_dataset(p, df_all)
        r, m = dose_response(dfp, p, seeds, profiles, latency_arms)
        all_rows += r; all_mech += m
        all_repair += repair_experiment(dfp, p, seeds)

    pd.DataFrame(all_rows).to_csv(OUT / "phase3_dose_response.csv", index=False)
    pd.DataFrame(all_mech).to_csv(OUT / "phase3_mechanism.csv", index=False)
    rep = pd.DataFrame(all_repair)
    rep.to_csv(OUT / "phase3_repair.csv", index=False)

    print("\n=== Repair experiment (mean MCC / G-mean across projects & seeds) ===")
    print(rep.groupby("condition")[["mcc", "gmean"]].mean().round(3))
    print(f"\nSaved to {OUT}/")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--fast", action="store_true")
    main(ap.parse_args().fast)

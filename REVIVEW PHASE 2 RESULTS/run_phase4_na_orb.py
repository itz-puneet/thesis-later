"""Phase 4: Noise-Aware ORB evaluation + ablation.
Place at: experiments/run_phase4_na_orb.py  (replaces the empty file).

Grid:
  models        : OOB, ORB, NA(damp), NA(rescue), NA(damp+rescue),
                  NA(damp+rescue+lc)   [ablation-first, per plan]
  label sources : oracle (clean control / non-degradation check)
                  + all 6 real SZZ variants
                  + injected 20% fn_heavy noise (bridge to Phase 3)
  latency       : real (per-source fix_ts; imputed for injected condition)
  seeds         : all RANDOM_SEEDS; stats = per-project paired Wilcoxon +
                  Cliff's delta on the two PRE-REGISTERED headline comparisons.

PRE-REGISTERED headline tests (decide nothing else post-hoc):
  H1: NA(damp+rescue) > ORB on label_BSZZ  (FP-heavy real noise)
  H2: NA(damp+rescue) > ORB on label_LSZZ  (FN-heavy real noise)
  Non-degradation: NA(damp+rescue) vs ORB on label_oracle (expect ~equal;
  a significant DROP here kills adoptability regardless of H1/H2).

Outputs (results/phase4/): phase4_results.csv, phase4_headline_tests.csv

Usage:
  python -m experiments.run_phase4_na_orb --fast
  python -m experiments.run_phase4_na_orb
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.append(str(Path(__file__).resolve().parent.parent))

from codebase.config import ORB_CONFIG, RANDOM_SEEDS, SZZ_VARIANTS
from codebase.data.loader import load_or_build_dataset, get_all_projects, get_project_dataset
from codebase.evaluation.regimes import prequential_latency
from codebase.evaluation.metrics import wilcoxon_with_cliffs
from codebase.noise.injection import load_bias_profiles, asymmetric_noise, impute_fix_ts
from codebase.online.noise_aware_orb import ablation_grid

OUT = Path("results/phase4"); OUT.mkdir(parents=True, exist_ok=True)
INJECTED_DOSE = 0.20
HEADLINE_MODEL, BASELINE_MODEL = "NA(damp+rescue)", "ORB"


def conditions(df: pd.DataFrame, seed: int, profiles: dict) -> list[tuple]:
    """(condition_name, label_col, fix_ts_col, frame) tuples."""
    conds = [("oracle", "label_oracle", "fix_ts", df)]
    for v in SZZ_VARIANTS:
        conds.append((v, f"label_{v}", f"fix_ts_{v}", df))
    rho0, rho1 = profiles["LSZZ"]
    noisy = asymmetric_noise(df["label_oracle"].to_numpy(dtype=int),
                             INJECTED_DOSE, rho0, rho1, seed)
    d = df.copy(); d["label_injected"] = noisy
    d = impute_fix_ts(d, noisy, seed)
    conds.append(("injected_fn20", "label_injected", "fix_ts_noisy", d))
    return conds


def main(fast: bool):
    df_all = load_or_build_dataset()
    profiles = load_bias_profiles()
    projects = get_all_projects(df_all)
    seeds = RANDOM_SEEDS[:3] if fast else RANDOM_SEEDS
    if fast:
        projects = projects[:5]
    # LC weights use the label source's own measured rates where applicable;
    # BSZZ's are the FP-heavy reference passed to the grid builder
    rho_ref = profiles["BSZZ"]

    rows = []
    for p in projects:
        print(f">>> {p}")
        dfp = get_project_dataset(p, df_all)
        for seed in seeds:
            for cond, label_col, ftcol, frame in conditions(dfp, seed, profiles):
                for name, model in ablation_grid(seed, ORB_CONFIG, rho_ref).items():
                    try:
                        r = prequential_latency(model, frame, label_col,
                                                eval_label_col="label_oracle",
                                                latency_mode="real",
                                                fix_ts_col=ftcol)
                    except ValueError:   # oracle / sparse fix_ts fallback
                        r = prequential_latency(model, frame, label_col,
                                                eval_label_col="label_oracle",
                                                latency_mode="uniform")
                    rows.append(dict(project=p, seed=seed, condition=cond,
                                     model=name, mcc=r["mcc"], gmean=r["gmean"]))
        pd.DataFrame(rows).to_csv(OUT / "phase4_results.csv", index=False)  # checkpoint

    res = pd.DataFrame(rows)
    res.to_csv(OUT / "phase4_results.csv", index=False)

    # ---- pre-registered headline tests (project-level pairing) ----------
    tests = []
    for cond, tag in [("BSZZ", "H1_fp_heavy"), ("LSZZ", "H2_fn_heavy"),
                      ("oracle", "non_degradation")]:
        sub = res[res.condition == cond]
        pm = sub.groupby(["project", "model"])["mcc"].mean().unstack()
        if HEADLINE_MODEL in pm and BASELINE_MODEL in pm:
            pv = pm[[HEADLINE_MODEL, BASELINE_MODEL]].dropna()
            t = wilcoxon_with_cliffs(pv[HEADLINE_MODEL], pv[BASELINE_MODEL])
            tests.append(dict(test=tag, condition=cond,
                              mean_headline=float(pv[HEADLINE_MODEL].mean()),
                              mean_baseline=float(pv[BASELINE_MODEL].mean()),
                              n_projects=len(pv), **t))
    pd.DataFrame(tests).to_csv(OUT / "phase4_headline_tests.csv", index=False)

    print("\n=== Mean MCC by condition x model ===")
    print(res.groupby(["condition", "model"])["mcc"].mean().unstack().round(3))
    print("\n=== Headline tests ===")
    print(pd.DataFrame(tests).round(4).to_string(index=False))
    print(f"\nSaved to {OUT}/")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--fast", action="store_true")
    main(ap.parse_args().fast)

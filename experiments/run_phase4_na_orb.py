"""Phase 4: Noise-Aware ORB evaluation + ablation.

RE-REGISTERED (v2) after Phase 3. Committed before any Phase 4 run; v1 is
retired unrun, so nothing here is chosen with knowledge of a Phase 4 result.

WHY THE REGISTRATION CHANGED
  v1 made NA(damp+rescue) the headline on the reasoning that SZZ starves an
  online learner of true positives. Phase 3 refuted that:

    * restoring BSZZ's false negatives recovers nothing, under realistic,
      immediate AND at-window delivery (TOST p = 0.0008, margin +-0.02) --
      so rescue targets an error that has been shown not to cost anything;
    * removing all 6,565 of BSZZ's false positives recovers +0.0402
      (17/21, global Holm 0.0019);
    * BUT at matched corrected mass the two are indistinguishable
      (HL +0.0050, CI [-0.0093, +0.0176]). The effect is VOLUME, not
      per-label severity: FP-repair is roughly linear at +0.147 MCC per
      1,000 labels corrected.

  So the mechanism-aligned intervention is train-time FP suppression, and the
  quantity that should predict its benefit is HOW MANY false positives the
  label source contains. That is H3 below, and it is the sharpest test here:
  a binary "filter beats ORB" is much weaker than a predicted ordering across
  six label sources whose FP counts are known in advance from Phase 1.

PRE-REGISTERED TESTS (nothing else is confirmatory)
  H1  primary    NA(fp_filter) > ORB on label_BSZZ          [6,565 FPs]
  H2  secondary  NA(fp_filter) > ORB on label_MASZZ         [5,030 FPs]
                 and label_AGSZZ                            [4,786 FPs]
  H3  ordering   Across the six SZZ variants, the benefit of fp_filter over
                 ORB is positively rank-correlated with the variant's Phase 1
                 false-positive count (Spearman rho > 0, one-sided).
                 FP counts, fixed in advance: BSZZ 6565, MASZZ 5030,
                 AGSZZ 4786, RASZZ 4531, RSZZ 2316, LSZZ 1665.
  ND  gate       NA(fp_filter) vs ORB on label_oracle: no significant drop,
                 TOST margin +-0.02 on mcc_avg. Failure kills adoptability
                 whatever H1-H3 do.
  MP  probe      NA(rescue) - ORB <= 0 on every SZZ source. Registered as a
                 PREDICTION, not a hope: rescue manufactures positives, and
                 Phase 3 says added positives are worthless. If rescue helps,
                 the Phase 3 mechanism account needs revision. Either outcome
                 is informative, which is why it earns its compute.
  R1  risk       lambda self-antagonism. ORB sets its oversampling rate from
                 the observed positive rate, and Phase 3 measured the boost to
                 be a near-perfect inverse of delivered positive supply
                 (Spearman rho = -1.000). Every positive the filter suppresses
                 therefore raises lambda for the survivors. Registered
                 prediction: rate_update="suppress" underperforms "observed",
                 and the gap widens with filter rate. Recorded per run via
                 FPFilterORB.filter_stats().

  All tests: project-paired Wilcoxon on mcc_avg (time-averaged prequential --
  Phase 3's repair tests lost every significance under the terminal estimator,
  so the choice is load-bearing and is declared here), Hodges-Lehmann with
  bootstrap CI, matched-pairs rank-biserial, Holm within this family. Both
  estimators are recorded; mcc_avg is primary. Everything else is exploratory
  and labelled so.

HELD-OUT PROJECTS
  commons-scxml, opennlp, commons-math are excluded from every reported
  number. The fp_filter defaults were chosen by looking at them, so including
  them would leak the tuning set into the results.

MODEL SET
  OOB, ORB                              baselines
  NA(fp_filter)                         primary
  NA(fp_filter/suppress)                R1 arm
  NA(damp)                              prior FP-side defence, for comparison
  NA(rescue)                            MP probe only
  NA(fp_filter+damp)                    composition

Grid:
  label sources : oracle + all 6 SZZ variants + injected 20% fn_heavy noise
  latency       : real (per-source fix_ts; imputed for the injected condition)
  seeds         : all RANDOM_SEEDS

Outputs (results/phase4/): phase4_results.csv, phase4_headline_tests.csv,
phase4_filter_stats.csv

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

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.append(str(BASE_DIR))

from codebase.config import ORB_CONFIG, RANDOM_SEEDS, SZZ_VARIANTS
from codebase.data.loader import load_or_build_dataset, get_all_projects, get_project_dataset
from codebase.evaluation.regimes import prequential_latency
from codebase.evaluation.metrics import paired_effect
from codebase.noise.injection import load_bias_profiles, asymmetric_noise, impute_fix_ts
from codebase.online.noise_aware_orb import NoiseAwareORB, FPFilterORB
from codebase.online.orb import OOB, ORB
from experiments.run_phase2_impact import _holm
from scipy.stats import spearmanr

OUT = BASE_DIR / "results" / "phase4"; OUT.mkdir(parents=True, exist_ok=True)
INJECTED_DOSE = 0.20
HEADLINE_MODEL, BASELINE_MODEL = "NA(fp_filter)", "ORB"

# Excluded from every reported number: the fp_filter defaults were chosen by
# looking at these. See the module docstring.
HELD_OUT_PROJECTS = ("commons-scxml", "opennlp", "commons-math")

# Phase 1 false-positive counts, fixed in advance. H3 predicts the benefit of
# fp_filter is positively rank-correlated with this column.
FP_COUNTS = {"BSZZ": 6565, "MASZZ": 5030, "AGSZZ": 4786,
             "RASZZ": 4531, "RSZZ": 2316, "LSZZ": 1665}


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


def ablation_grid_v2(seed: int, orb_config: dict) -> dict:
    """Re-registered model set. See the module docstring for why."""
    base = dict(orb_config)
    return {
        "OOB": OOB(n_estimators=base.get("n_estimators", 20), seed=seed),
        "ORB": ORB(seed=seed, **base),
        "NA(fp_filter)": FPFilterORB(seed=seed, **base),
        "NA(fp_filter/suppress)": FPFilterORB(seed=seed, rate_update="suppress", **base),
        "NA(damp)": NoiseAwareORB(seed=seed, use_damp=True, use_rescue=False, **base),
        "NA(rescue)": NoiseAwareORB(seed=seed, use_damp=False, use_rescue=True, **base),
        "NA(fp_filter+damp)": FPFilterORB(seed=seed, **base),  # damp composed in v3
    }


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
                for name, model in ablation_grid_v2(seed, ORB_CONFIG).items():
                    try:
                        r = prequential_latency(model, frame, label_col,
                                                eval_label_col="label_oracle",
                                                latency_mode="real",
                                                fix_ts_col=ftcol)
                    except ValueError:   # oracle / sparse fix_ts fallback
                        r = prequential_latency(model, frame, label_col,
                                                eval_label_col="label_oracle",
                                                latency_mode="uniform")
                    fs = model.filter_stats() if hasattr(model, "filter_stats") else {}
                    rows.append(dict(project=p, seed=seed, condition=cond,
                                     model=name,
                                     held_out=p in HELD_OUT_PROJECTS,
                                     mcc_avg=r["mcc_avg"], gmean_avg=r["gmean_avg"],
                                     mcc=r["mcc"], gmean=r["gmean"], **fs))
        pd.DataFrame(rows).to_csv(OUT / "phase4_results.csv", index=False)  # checkpoint

    res = pd.DataFrame(rows)
    res.to_csv(OUT / "phase4_results.csv", index=False)

    # ---- pre-registered tests (project-paired, mcc_avg primary) --------
    #
    # Held-out projects are dropped BEFORE any test: the fp_filter defaults
    # were chosen by looking at them.
    rep = res[~res.held_out] if "held_out" in res.columns else res
    tests = []

    def _paired(cond, model_a, model_b, tag):
        sub = rep[rep.condition == cond]
        pm = sub.groupby(["project", "model"])["mcc_avg"].mean().unstack()
        if model_a not in pm or model_b not in pm:
            return None
        pv = pm[[model_a, model_b]].dropna()
        if len(pv) < 6:
            return None
        e = paired_effect(pv[model_a].to_numpy(), pv[model_b].to_numpy())
        return dict(test=tag, condition=cond, model_a=model_a, model_b=model_b,
                    n_projects=len(pv),
                    mean_a=float(pv[model_a].mean()), mean_b=float(pv[model_b].mean()),
                    hodges_lehmann=e["hodges_lehmann"], ci_low=e["ci_low"],
                    ci_high=e["ci_high"], rank_biserial=e["rank_biserial"],
                    n_favouring_a=int((pv[model_a] > pv[model_b]).sum()),
                    p=e["p_value"])

    for cond, tag in [("BSZZ", "H1_fp_filter_vs_orb_bszz"),
                      ("MASZZ", "H2a_fp_filter_vs_orb_maszz"),
                      ("AGSZZ", "H2b_fp_filter_vs_orb_agszz"),
                      ("oracle", "ND_non_degradation")]:
        t = _paired(cond, HEADLINE_MODEL, BASELINE_MODEL, tag)
        if t:
            tests.append(t)

    tests = pd.DataFrame(tests)
    if not tests.empty:
        tests["p_holm"] = _holm(tests["p"].to_numpy())

    # H3: does the benefit track the variant's false-positive count?
    gains = []
    for v, n_fp in FP_COUNTS.items():
        sub = rep[rep.condition == v]
        pm = sub.groupby(["project", "model"])["mcc_avg"].mean().unstack()
        if HEADLINE_MODEL in pm and BASELINE_MODEL in pm:
            d = (pm[HEADLINE_MODEL] - pm[BASELINE_MODEL]).dropna()
            gains.append(dict(variant=v, n_false_positives=n_fp,
                              mean_gain=float(d.mean()), n_projects=len(d)))
    h3 = pd.DataFrame(gains)
    if len(h3) >= 3:
        rho, pv = spearmanr(h3["n_false_positives"], h3["mean_gain"])
        h3["spearman_rho"] = round(float(rho), 4)
        h3["p_one_sided"] = round(float(pv / 2 if rho > 0 else 1 - pv / 2), 4)
    h3.to_csv(OUT / "phase4_h3_volume.csv", index=False)

    # R1: the lambda self-antagonism arm, and realised filter behaviour.
    fcols = [c for c in ["n_filtered", "n_pos_seen", "filter_rate",
                         "mean_lambda_pos", "filter_active_from"] if c in res.columns]
    if fcols:
        (res[res.model.str.contains("fp_filter", na=False)]
            .groupby(["model", "condition"])[fcols].mean()
            .round(4).to_csv(OUT / "phase4_filter_stats.csv"))

    tests.to_csv(OUT / "phase4_headline_tests.csv", index=False)

    print(f"\n=== Reporting on {rep.project.nunique()} projects "
          f"({len(HELD_OUT_PROJECTS)} held out) ===")
    print("\n=== H3: gain vs false-positive count ===")
    print(h3.to_string(index=False))
    print("\n=== Mean mcc_avg by condition x model (reporting projects) ===")
    print(rep.groupby(["condition", "model"])["mcc_avg"].mean().unstack().round(3))
    print("\n=== Pre-registered tests ===")
    print("  (none: need >= 6 paired projects)" if tests.empty
          else tests.round(4).to_string(index=False))
    print(f"\nSaved to {OUT}/")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--fast", action="store_true")
    main(ap.parse_args().fast)

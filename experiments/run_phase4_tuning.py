"""Phase 4 Step C: tune FPFilterORB on the THREE HELD-OUT PROJECTS only.

These projects -- commons-scxml, opennlp, commons-math -- are excluded from
every reported Phase 4 number (run_phase4_na_orb.HELD_OUT_PROJECTS). Nothing
measured here may be quoted as a result; the only output that leaves this
script is one frozen configuration.

SELECTION RULE, declared before the sweep runs
  1. ND gate first. A configuration is ELIGIBLE only if it does not degrade
     the oracle arm: mean mcc_avg on label_oracle must be within `ND_MARGIN`
     (0.02, the same margin pre-registered for the Phase 4 ND test) of plain
     ORB's. A filter that wins on BSZZ and damages clean labels is not
     adoptable, so this gate is applied BEFORE looking at any gain.
  2. Among eligible configurations, maximise mean gain over ORB on
     label_BSZZ, which is H1's target and the FP-heaviest source.
  3. Ties broken toward the more conservative filter (lower filter rate),
     because a smaller intervention that buys the same gain is preferable and
     carries less of the R1 feedback risk.

  rate_update is NOT tuned. It is the R1 arm: both levels are run and
  reported, and the frozen config takes "observed" regardless of which scores
  better, because R1 is a registered prediction about the mechanism and
  optimising it would convert a test into a fit.

Grid
  mode/threshold : fixed tau in {0.15, 0.25, 0.35}
                   quantile q in {0.05, 0.10, 0.20}
  eps            : {0.0, 0.1}      discard vs residual weight
  min_pos        : {20, 30, 50}    warm-up counted in POSITIVE labels
  rate_update    : {observed, suppress}    [R1 arm, reported not tuned]
  conditions     : oracle (ND gate), BSZZ, MASZZ, LSZZ (spans FP volume)

Outputs (results/phase4/): phase4_tuning.csv, phase4_tuning_summary.csv,
phase4_tuning_r1.csv, phase4_frozen_config.json

Usage:
  python -m experiments.run_phase4_tuning --fast
  python -m experiments.run_phase4_tuning
"""
from __future__ import annotations

import argparse
import itertools
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.append(str(BASE_DIR))

from codebase.config import ORB_CONFIG, RANDOM_SEEDS
from codebase.data.loader import load_or_build_dataset, get_project_dataset
from codebase.evaluation.regimes import prequential_latency
from codebase.online.orb import ORB
from codebase.online.noise_aware_orb import FPFilterORB
from experiments.run_phase4_na_orb import HELD_OUT_PROJECTS

OUT = BASE_DIR / "results" / "phase4"
OUT.mkdir(parents=True, exist_ok=True)

ND_MARGIN = 0.02
CONDITIONS = [("oracle", "label_oracle", "fix_ts"),
              ("BSZZ", "label_BSZZ", "fix_ts_BSZZ"),
              ("MASZZ", "label_MASZZ", "fix_ts_MASZZ"),
              ("LSZZ", "label_LSZZ", "fix_ts_LSZZ")]

# Quantile first so --fast exercises the arm that actually passes the ND gate.
RULES = ([dict(mode="quantile", q=q) for q in (0.05, 0.10, 0.20, 0.30)]
         + [dict(mode="fixed", tau=t) for t in (0.15, 0.25, 0.35)])
EPS = (0.0, 0.1)
MIN_POS = (20, 30, 50)
RATE_UPDATE = ("observed", "suppress")


def _rule_name(rule: dict) -> str:
    return (f"fixed/tau={rule['tau']}" if rule["mode"] == "fixed"
            else f"quantile/q={rule['q']}")


def _run(model, frame, label_col, fix_ts_col):
    try:
        return prequential_latency(model, frame, label_col,
                                   eval_label_col="label_oracle",
                                   latency_mode="real", fix_ts_col=fix_ts_col)
    except ValueError:      # sparse fix_ts (oracle arm on some projects)
        return prequential_latency(model, frame, label_col,
                                   eval_label_col="label_oracle",
                                   latency_mode="uniform")


def sweep(fast: bool) -> pd.DataFrame:
    df_all = load_or_build_dataset()
    seeds = RANDOM_SEEDS[:3] if fast else RANDOM_SEEDS
    rules = RULES[:2] if fast else RULES
    min_pos = MIN_POS[:1] if fast else MIN_POS
    eps_vals = EPS[:1] if fast else EPS

    rows = []
    for project in HELD_OUT_PROJECTS:
        dfp = get_project_dataset(project, df_all)
        print(f">>> {project} ({len(dfp)} commits)", flush=True)
        for cond, label_col, ftcol in CONDITIONS:
            for seed in seeds:
                # baseline, once per (project, condition, seed)
                r = _run(ORB(seed=seed, **ORB_CONFIG), dfp, label_col, ftcol)
                rows.append(dict(project=project, condition=cond, seed=seed,
                                 config="ORB", rule="-", eps=np.nan,
                                 min_pos=np.nan, rate_update="-",
                                 mcc_avg=r["mcc_avg"], mcc=r["mcc"],
                                 filter_rate=np.nan, n_filtered=np.nan))
                for rule, eps, mp, ru in itertools.product(
                        rules, eps_vals, min_pos, RATE_UPDATE):
                    m = FPFilterORB(seed=seed, eps=eps,
                                    min_pos_for_threshold=mp,
                                    rate_update=ru, **rule, **ORB_CONFIG)
                    r = _run(m, dfp, label_col, ftcol)
                    st = m.filter_stats()
                    rows.append(dict(
                        project=project, condition=cond, seed=seed,
                        config=f"{_rule_name(rule)}|eps={eps}|minpos={mp}|{ru}",
                        rule=_rule_name(rule), eps=eps, min_pos=mp,
                        rate_update=ru, mcc_avg=r["mcc_avg"], mcc=r["mcc"],
                        filter_rate=st["filter_rate"], n_filtered=st["n_filtered"]))
        pd.DataFrame(rows).to_csv(OUT / "phase4_tuning.csv", index=False)
    return pd.DataFrame(rows)


def select(res: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """Apply the declared selection rule. ND gate first, then gain on BSZZ."""
    base = (res[res.config == "ORB"]
            .groupby("condition")["mcc_avg"].mean())
    cand = res[res.config != "ORB"]

    summary = (cand.groupby(["config", "rule", "eps", "min_pos", "rate_update",
                             "condition"])
                   .agg(mcc_avg=("mcc_avg", "mean"),
                        filter_rate=("filter_rate", "mean"))
                   .reset_index())
    summary["orb_mcc_avg"] = summary["condition"].map(base)
    summary["gain"] = summary["mcc_avg"] - summary["orb_mcc_avg"]

    wide = summary.pivot_table(index=["config", "rule", "eps", "min_pos",
                                      "rate_update"],
                               columns="condition",
                               values=["gain", "filter_rate"]).reset_index()
    wide.columns = ["_".join(c).strip("_") if isinstance(c, tuple) else c
                    for c in wide.columns]

    nd_col, h1_col = "gain_oracle", "gain_BSZZ"
    if nd_col not in wide or h1_col not in wide:
        return summary, {}
    wide["nd_pass"] = wide[nd_col] >= -ND_MARGIN

    # rate_update is not tuned: freeze on "observed" (see the module docstring).
    pool = wide[wide.nd_pass & (wide.rate_update == "observed")].copy()
    if pool.empty:
        return summary, {"error": "no configuration passed the ND gate"}
    fr = "filter_rate_BSZZ"
    pool = pool.sort_values([h1_col, fr], ascending=[False, True])
    best = pool.iloc[0]

    frozen = dict(
        selected_config=str(best["config"]),
        rule=str(best["rule"]), eps=float(best["eps"]),
        min_pos_for_threshold=int(best["min_pos"]),
        rate_update="observed",
        gain_on_BSZZ=round(float(best[h1_col]), 4),
        gain_on_oracle_ND=round(float(best[nd_col]), 4),
        nd_margin=ND_MARGIN,
        filter_rate_on_BSZZ=round(float(best.get(fr, np.nan)), 4),
        n_eligible_configs=int(len(pool)),
        n_configs_evaluated=int(wide.rate_update.eq("observed").sum()),
        held_out_projects=list(HELD_OUT_PROJECTS),
        selection_rule="ND gate (oracle within -0.02 of ORB) THEN max gain on "
                       "BSZZ THEN lower filter rate; rate_update fixed to "
                       "'observed' as the R1 arm rather than tuned",
    )
    return wide, frozen


def r1_report(res: pd.DataFrame) -> pd.DataFrame:
    """R1: does suppressing positives (and so raising lambda) cost performance?"""
    cand = res[res.config != "ORB"].copy()
    cand["cfg_wo_ru"] = (cand["rule"] + "|eps=" + cand["eps"].astype(str)
                         + "|minpos=" + cand["min_pos"].astype(str))
    piv = (cand.groupby(["cfg_wo_ru", "condition", "rate_update"])["mcc_avg"]
               .mean().unstack())
    if not {"observed", "suppress"} <= set(piv.columns):
        return pd.DataFrame()
    piv = piv.dropna()
    piv["observed_minus_suppress"] = piv["observed"] - piv["suppress"]
    out = piv.reset_index()
    print("\n=== R1: lambda self-antagonism arm ===")
    print(f"  registered prediction: observed > suppress")
    print(f"  mean(observed - suppress) = {out['observed_minus_suppress'].mean():+.4f}")
    print(f"  favours 'observed' in {(out['observed_minus_suppress'] > 0).sum()}"
          f"/{len(out)} configuration-condition cells")
    return out


def main(fast: bool):
    res = sweep(fast)
    res.to_csv(OUT / "phase4_tuning.csv", index=False)
    wide, frozen = select(res)
    wide.to_csv(OUT / "phase4_tuning_summary.csv", index=False)
    r1 = r1_report(res)
    if not r1.empty:
        r1.to_csv(OUT / "phase4_tuning_r1.csv", index=False)
    (OUT / "phase4_frozen_config.json").write_text(json.dumps(frozen, indent=2))

    pd.set_option("display.width", 220)
    print("\n=== Top eligible configurations (ND gate passed, observed arm) ===")
    cols = [c for c in ["config", "gain_BSZZ", "gain_MASZZ", "gain_LSZZ",
                        "gain_oracle", "filter_rate_BSZZ"] if c in wide.columns]
    if "nd_pass" in wide.columns:
        top = wide[wide.nd_pass & (wide.rate_update == "observed")]
        print(top.sort_values("gain_BSZZ", ascending=False)[cols]
                 .head(10).round(4).to_string(index=False))
    print("\n=== FROZEN CONFIG ===")
    print(json.dumps(frozen, indent=2))
    print(f"\nSaved to {OUT}/  -- held-out only, not reportable")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--fast", action="store_true")
    main(ap.parse_args().fast)

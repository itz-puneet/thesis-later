"""Phase 3: dose-response diagnosis of ORB under label noise.

For each dose in NOISE_LEVELS and each noise model (symmetric control vs.
asymmetric calibrated to Phase 1 bias), inject noise into the oracle labels,
run ORB under prequential-with-latency evaluation scored against the clean
oracle, and record (a) final MCC/G-mean and (b) ORB internals (mean boost on
false-positive vs. true-positive labels) -- the "boost amplifies noise"
mechanism evidence.

Outputs: results/phase3_dose_response.csv, results/phase3_mechanism.csv
"""
from __future__ import annotations

import argparse

import numpy as np
import pandas as pd

from config import RESULTS_DIR, NOISE_LEVELS, ORB as ORB_CFG
from data.loader import load_commits, make_demo_stream
from evaluation.regimes import prequential_latency
from noise.injection import symmetric_noise, asymmetric_noise, load_phase1_bias
from online.orb import ORB


def run_condition(df, noisy_labels, seed):
    d = df.copy()
    d["label_noisy"] = noisy_labels
    orb = ORB(seed=seed, **ORB_CFG)
    res = prequential_latency(orb, d, "label_noisy", eval_label_col="label_oracle")
    trace = pd.DataFrame(orb.trace)
    # mechanism: how much boost did mislabeled minority examples receive?
    d = d.sort_values("author_ts").reset_index(drop=True)
    is_fp_label = (d["label_noisy"] == 1) & (d["label_oracle"] == 0)
    # trace rows align with learn_one calls; approximate via label identity
    mech = dict(
        mean_boost_all=float(trace["boost"].mean()),
        mean_boost_minority=float(trace.loc[trace["y"] == 1, "boost"].mean()),
        fp_label_fraction=float(is_fp_label.mean()),
    )
    return res["mcc"], res["gmean"], mech


def main(df: pd.DataFrame, bias_json: str | None, seed: int = 42):
    try:
        fp_fn = load_phase1_bias(bias_json or str(RESULTS_DIR / "phase1_bias.json"),
                                 "B-SZZ")
    except FileNotFoundError:
        print("phase1_bias.json not found -- run Phase 1 first; using (2:1) ratio")
        fp_fn = (0.2, 0.1)

    y = df["label_oracle"].to_numpy()
    rows, mech_rows = [], []
    for dose in NOISE_LEVELS:
        for model_name, noisy in [
            ("symmetric", symmetric_noise(y, dose, seed)),
            ("asymmetric_szz", asymmetric_noise(y, dose, fp_fn, seed)),
        ]:
            mcc_v, gm, mech = run_condition(df, noisy, seed)
            rows.append(dict(noise_model=model_name, dose=dose,
                             mcc=mcc_v, gmean=gm))
            mech_rows.append(dict(noise_model=model_name, dose=dose, **mech))
            print(f"{model_name:>15} dose={dose:.2f}  MCC={mcc_v:.3f}  G-mean={gm:.3f}")

    pd.DataFrame(rows).to_csv(RESULTS_DIR / "phase3_dose_response.csv", index=False)
    pd.DataFrame(mech_rows).to_csv(RESULTS_DIR / "phase3_mechanism.csv", index=False)
    print(f"\nSaved to {RESULTS_DIR}/phase3_*")


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--data")
    p.add_argument("--bias-json")
    p.add_argument("--demo", action="store_true")
    a = p.parse_args()
    main(make_demo_stream() if a.demo or not a.data else load_commits(a.data),
         a.bias_json)

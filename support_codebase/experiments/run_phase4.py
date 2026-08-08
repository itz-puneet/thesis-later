"""Phase 4: Noise-Aware ORB vs. ORB/OOB.

Conditions:
- real SZZ labels (each variant) and injected asymmetric noise at 20%
- ablation: {confidence only, loss-correction only, both, both+agreement}
- clean-oracle control (non-degradation check)

Output: results/phase4_results.csv
"""
from __future__ import annotations

import argparse

import pandas as pd

from config import RESULTS_DIR, SZZ_VARIANTS, ORB as ORB_CFG, NA_ORB, RANDOM_SEEDS
from data.loader import load_commits, make_demo_stream
from evaluation.regimes import prequential_latency
from evaluation.metrics import wilcoxon_with_cliffs
from noise.injection import load_phase1_bias
from online.orb import OOB, ORB
from online.noise_aware_orb import NoiseAwareORB


def build_models(seed, rho):
    base = {k: v for k, v in ORB_CFG.items()}
    return {
        "OOB": OOB(n_estimators=base["n_estimators"], seed=seed),
        "ORB": ORB(seed=seed, **base),
        "NA-ORB(conf)": NoiseAwareORB(seed=seed, noise_rates=None,
                                      use_loss_correction=False, **base),
        "NA-ORB(lc)": NoiseAwareORB(seed=seed, noise_rates=rho,
                                    min_confidence=1.0,  # disable conf term
                                    use_loss_correction=True, **base),
        "NA-ORB(full)": NoiseAwareORB(seed=seed, noise_rates=rho,
                                      use_loss_correction=True, **base),
        "NA-ORB(full+agree)": NoiseAwareORB(seed=seed, noise_rates=rho,
                                            use_loss_correction=True,
                                            use_agreement_check=True, **base),
    }


def main(df: pd.DataFrame, seeds=None):
    seeds = seeds or RANDOM_SEEDS[:3]
    try:
        rho = load_phase1_bias(str(RESULTS_DIR / "phase1_bias.json"), "B-SZZ")
    except FileNotFoundError:
        rho = (0.2, 0.25)

    label_cols = ["label_oracle"] + [f"label_{v}" for v in SZZ_VARIANTS]
    rows = []
    for label_col in label_cols:
        for seed in seeds:
            for name, model in build_models(seed, rho).items():
                r = prequential_latency(model, df, label_col,
                                        eval_label_col="label_oracle")
                rows.append(dict(model=name, labels=label_col, seed=seed,
                                 mcc=r["mcc"], gmean=r["gmean"]))
                print(f"{name:>20} | {label_col:15} | seed={seed} "
                      f"| MCC={r['mcc']:.3f} G={r['gmean']:.3f}")

    out = pd.DataFrame(rows)
    out.to_csv(RESULTS_DIR / "phase4_results.csv", index=False)

    # headline test: NA-ORB(full) vs ORB on noisiest label source
    noisy = out[out.labels == "label_B-SZZ"]
    a = noisy[noisy.model == "NA-ORB(full)"].sort_values("seed")["mcc"].values
    b = noisy[noisy.model == "ORB"].sort_values("seed")["mcc"].values
    if len(a) and len(b):
        print("\nNA-ORB(full) vs ORB on B-SZZ labels:",
              wilcoxon_with_cliffs(a, b))
    print(f"\nSaved to {RESULTS_DIR}/phase4_results.csv")


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--data")
    p.add_argument("--demo", action="store_true")
    a = p.parse_args()
    demo = a.demo or not a.data
    main(make_demo_stream(n=3000) if demo else load_commits(a.data))

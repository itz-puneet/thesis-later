"""Phase 2: downstream impact under honest evaluation.

Grid: {LApredict, JITLine, ORB} x {oracle + 5 SZZ label sources}
      x {naive k-fold, chronological, prequential-with-latency}.

All configurations are *scored against the oracle label* so that differences
reflect training-label quality and evaluation honesty, not moving targets.
(Also rerun with eval_label=train_label to reproduce the field's standard,
self-referential scoring -- the contrast between the two is Figure "inflation
ladder".)

Output: results/phase2_grid.csv
"""
from __future__ import annotations

import argparse

import pandas as pd

from config import RESULTS_DIR, SZZ_VARIANTS, ORB as ORB_CFG
from data.loader import load_commits, make_demo_stream
from evaluation.regimes import naive_kfold, chronological, prequential_latency
from models.baselines import LApredict, JITLine
from online.orb import ORB


def main(df: pd.DataFrame, seed: int = 42, fast: bool = False):
    n_trees, k = (100, 5) if fast else (300, 10)
    label_sources = ["label_oracle"] + [f"label_{v}" for v in SZZ_VARIANTS]
    rows = []
    for label_col in label_sources:
        for model_name, factory in [
                ("LApredict", lambda: LApredict(seed)),
                ("JITLine", lambda: JITLine(seed, n_estimators=n_trees))]:
            for regime_fn in (naive_kfold, chronological):
                kw = dict(k=k) if regime_fn is naive_kfold else {}
                r = regime_fn(factory, df, label_col,
                              eval_label_col="label_oracle", **kw)
                rows.append(dict(model=model_name, labels=label_col, **r))
        orb = ORB(seed=seed, **{k: v for k, v in ORB_CFG.items()})
        r = prequential_latency(orb, df, label_col, eval_label_col="label_oracle")
        r.pop("history", None)
        rows.append(dict(model="ORB", labels=label_col, **r))

    out = pd.DataFrame(rows)
    out.to_csv(RESULTS_DIR / "phase2_grid.csv", index=False)
    print(out.pivot_table(index=["model", "labels"], columns="regime",
                          values="mcc").round(3))
    print(f"\nSaved to {RESULTS_DIR}/phase2_grid.csv")


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--data")
    p.add_argument("--demo", action="store_true")
    a = p.parse_args()
    demo = a.demo or not a.data
    main(make_demo_stream(n=3000) if demo else load_commits(a.data), fast=demo)

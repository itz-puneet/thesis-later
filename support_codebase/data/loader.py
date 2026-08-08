"""Data loading for JIT-SDP experiments.

Expected commit-level CSV schema
--------------------------------
commit_id : str            unique hash
project   : str
author_ts : int/float      author timestamp (unix seconds) -- defines stream order
fix_ts    : float|NaN      timestamp when a fix linked this commit as inducing
                           (NaN = never linked; label arrival time for online eval)
<Kamei features>           ns, nd, nf, entropy, la, ld, lt, fix, ndev, age, nuc,
                           exp, rexp, sexp
label_oracle    : {0,1}    human-verified label (JIT-Defects4J subset only)
label_B-SZZ ... label_R-SZZ : {0,1}  per-variant SZZ labels (from szz/variants.py)

Real datasets to wire in:
- JIT-Defects4J (oracle):  https://github.com/jacknichao/JIT-Defects4J
- ApacheJIT (scale):       https://github.com/hosseinkshvrz/apachejit
- Cabral et al. 2019 stream datasets (10 GitHub projects).
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from config import KAMEI_FEATURES, SZZ_VARIANTS


def load_commits(path: str) -> pd.DataFrame:
    """Load a prepared commit-level dataset and validate schema."""
    df = pd.read_csv(path)
    required = {"commit_id", "author_ts"} | set(KAMEI_FEATURES)
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"Dataset missing required columns: {sorted(missing)}")
    return df.sort_values("author_ts").reset_index(drop=True)


def make_demo_stream(
    n: int = 6000,
    defect_rate: float = 0.12,
    drift_at: float = 0.5,
    seed: int = 42,
) -> pd.DataFrame:
    """Synthetic commit stream for pipeline smoke tests.

    Simulates: (1) informative Kamei-like features, (2) a mid-stream concept
    drift, (3) verification latency (fix_ts lags author_ts), and (4) five SZZ
    variants as progressively-less-noisy views of the oracle label, with
    asymmetric error structure (FP-heavy for B-SZZ, conservative for R-SZZ).
    """
    rng = np.random.default_rng(seed)
    ts = np.cumsum(rng.exponential(3600 * 4, size=n))  # ~1 commit / 4h

    y = (rng.random(n) < defect_rate).astype(int)
    X = rng.lognormal(mean=1.0, sigma=1.0, size=(n, len(KAMEI_FEATURES)))
    # make features informative; flip sign of signal after the drift point
    signal = np.where(np.arange(n) < int(n * drift_at), 1.0, -0.6)
    for j in [4, 5, 7, 10]:  # la, ld, fix, nuc
        X[:, j] *= 1.0 + 1.5 * y * signal * rng.random(n)

    df = pd.DataFrame(X, columns=KAMEI_FEATURES)
    df.insert(0, "commit_id", [f"c{i:06d}" for i in range(n)])
    df.insert(1, "project", "demo")
    df.insert(2, "author_ts", ts)
    df["label_oracle"] = y

    # verification latency: defective commits get a fix 10-300 days later
    lat = rng.uniform(10, 300, size=n) * 86400
    df["fix_ts"] = np.where(y == 1, ts + lat, np.nan)

    # SZZ variants = oracle + variant-specific asymmetric noise
    # (fp_rate, fn_rate) roughly ordered from worst (B) to best (R)
    variant_noise = {
        "B-SZZ": (0.20, 0.25), "AG-SZZ": (0.15, 0.22),
        "MA-SZZ": (0.12, 0.20), "RA-SZZ": (0.08, 0.18), "R-SZZ": (0.05, 0.15),
    }
    for v in SZZ_VARIANTS:
        fp, fn = variant_noise[v]
        noisy = y.copy()
        flip_up = (y == 0) & (rng.random(n) < fp)    # clean -> "defective"
        flip_dn = (y == 1) & (rng.random(n) < fn)    # defective -> "clean"
        noisy[flip_up] = 1
        noisy[flip_dn] = 0
        df[f"label_{v}"] = noisy
    return df

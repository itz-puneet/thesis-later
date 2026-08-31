"""Phase 3 noise injection. Place at: codebase/noise/injection.py
(create codebase/noise/__init__.py alongside).

Injects synthetic label noise into oracle labels under two model families:

  symmetric(dose)              -- uniform flips (control condition)
  asymmetric(dose, rho0, rho1) -- class-conditional flips whose FP:FN ratio
                                  matches a measured SZZ bias profile, scaled
                                  so total expected flip mass == dose

Profiles come from phase1_bias.json (measured on the SAME label universe as
Phase 2 after the NaN fix). Recommended three-profile sweep:
  FP-heavy : BSZZ  (rho0=0.263, rho1=0.359)
  mid      : RASZZ (rho0=0.181, rho1=0.562)
  FN-heavy : LSZZ  (rho0=0.067, rho1=0.733)

Also provides impute_fix_ts(): under latency_mode="real", injected FP flips on
never-linked commits would silently self-filter (their labels never arrive).
For the real-latency arm, impute fix_ts for noisy-positive commits from the
project's empirical latency distribution (seed-controlled).
"""
from __future__ import annotations

import json

import numpy as np
import pandas as pd


def load_bias_profiles(path: str = "phase1_bias.json") -> dict[str, tuple[float, float]]:
    with open(path) as f:
        bias = json.load(f)
    return {v: (d["fp_rate"], d["fn_rate"]) for v, d in bias.items()}


def symmetric_noise(y: np.ndarray, dose: float, seed: int) -> np.ndarray:
    rng = np.random.default_rng(seed)
    y = np.asarray(y, dtype=int).copy()
    flip = rng.random(len(y)) < dose
    y[flip] = 1 - y[flip]
    return y


def asymmetric_noise(y: np.ndarray, dose: float,
                     rho0: float, rho1: float, seed: int) -> np.ndarray:
    """Class-conditional flips at rates (s*rho0, s*rho1); s chosen so the
    expected flipped fraction equals `dose`."""
    rng = np.random.default_rng(seed)
    y = np.asarray(y, dtype=int).copy()
    p1 = float((y == 1).mean())
    base = rho0 * (1.0 - p1) + rho1 * p1
    s = dose / max(base, 1e-9)
    r0, r1 = min(s * rho0, 1.0), min(s * rho1, 1.0)
    u = rng.random(len(y))
    flip = ((y == 0) & (u < r0)) | ((y == 1) & (u < r1))
    y[flip] = 1 - y[flip]
    return y


def empirical_latency_pool(df: pd.DataFrame,
                           fix_ts_col: str = "fix_ts") -> np.ndarray:
    """Observed (fix_ts - author_ts) latencies, in seconds, for linked commits."""
    lat = (df[fix_ts_col] - df["author_ts"]).dropna()
    lat = lat[lat > 0].to_numpy()
    if len(lat) == 0:
        # conservative fallback: 30..720 days uniform
        return np.arange(30, 721, 30) * 86400.0
    return lat


def impute_fix_ts(df: pd.DataFrame, noisy_labels: np.ndarray,
                  seed: int, out_col: str = "fix_ts_noisy",
                  base_col: str = "fix_ts") -> pd.DataFrame:
    """fix_ts for a synthetic label column, for latency_mode='real' runs.

    - noisy-positive AND already linked      -> keep real fix_ts
    - noisy-positive AND unlinked (e.g. an injected FP flip)
                                             -> author_ts + latency sampled from
                                                the empirical pool (per seed)
    - noisy-negative                          -> NaN (fix_ts unused for y=0)
    """
    rng = np.random.default_rng(seed)
    d = df.copy()
    pool = empirical_latency_pool(d, base_col)
    base = d[base_col].to_numpy(dtype=float) if base_col in d else np.full(len(d), np.nan)
    out = np.full(len(d), np.nan)
    pos = np.asarray(noisy_labels, dtype=int) == 1
    linked = pos & np.isfinite(base)
    out[linked] = base[linked]
    need = pos & ~np.isfinite(base)
    out[need] = d["author_ts"].to_numpy(dtype=float)[need] + rng.choice(pool, size=int(need.sum()))
    d[out_col] = out
    return d

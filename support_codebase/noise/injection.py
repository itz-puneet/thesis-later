"""Phase 3: synthetic label-noise injection.

Two noise models applied to oracle labels:
- symmetric: uniform flips at total rate `dose` (control condition)
- asymmetric ("SZZ-calibrated"): FP/FN flip rates in the ratio measured for a
  given SZZ variant in Phase 1, scaled to hit the requested total dose.
"""
from __future__ import annotations

import json

import numpy as np


def symmetric_noise(y, dose: float, seed: int = 42) -> np.ndarray:
    rng = np.random.default_rng(seed)
    y = np.asarray(y).copy()
    flip = rng.random(len(y)) < dose
    y[flip] = 1 - y[flip]
    return y


def asymmetric_noise(y, dose: float, fp_fn_ratio: tuple[float, float],
                     seed: int = 42) -> np.ndarray:
    """Flip labels with class-conditional rates whose ratio matches the
    measured SZZ bias (rho_0 : rho_1), scaled so the expected fraction of
    flipped labels equals `dose`."""
    rng = np.random.default_rng(seed)
    y = np.asarray(y).copy()
    rho0, rho1 = fp_fn_ratio                     # measured fp_rate, fn_rate
    p1 = (y == 1).mean()
    # expected flips = rho0*s*(1-p1) + rho1*s*p1 = dose  -> solve scale s
    base = rho0 * (1 - p1) + rho1 * p1
    s = dose / max(base, 1e-9)
    r0, r1 = min(rho0 * s, 1.0), min(rho1 * s, 1.0)
    u = rng.random(len(y))
    flip = ((y == 0) & (u < r0)) | ((y == 1) & (u < r1))
    y[flip] = 1 - y[flip]
    return y


def load_phase1_bias(path: str, variant: str) -> tuple[float, float]:
    """Read (fp_rate, fn_rate) for a variant from Phase 1's exported JSON."""
    with open(path) as f:
        bias = json.load(f)
    return bias[variant]["fp_rate"], bias[variant]["fn_rate"]

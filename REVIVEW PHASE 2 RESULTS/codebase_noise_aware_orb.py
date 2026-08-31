"""Phase 4: Noise-Aware ORB. Place at: codebase/online/noise_aware_orb.py

Extends your validated ORB with independently switchable noise defenses. The
design reflects the Phase 1/2 measurements, not the original proposal:

1. DAMP path (Confident-Learning-style, streaming): each arriving label gets a
   confidence c in (0,1] from running per-class self-confidence thresholds; c
   modulates ONLY the boost amplification, so a suspicious minority label falls
   back to plain OOB weight instead of being amplified. Targets FP noise.

2. RESCUE path (NEW -- motivated by measured FN rates of 0.36-0.73 and 53% of
   labels arriving late): when a commit arrives labeled CLEAN but the ensemble
   is confident it is defective (prob above the class-1 running threshold by a
   margin), the instance is trained as a low-weight PROVISIONAL POSITIVE
   instead of a full-weight negative. Targets FN noise -- which Phase 1 showed
   is the larger error mass for every refined variant.

3. CAPPED loss correction (Natarajan-style): with measured rho0+rho1 of
   0.62 (BSZZ) to 0.80 (LSZZ), the exact unbiased weight
   (1-rho_other)/(1-rho0-rho1) reaches 3-5x and destabilizes SGD. Weights are
   therefore capped (default 2.0) and OFF by default; treat as an ablation arm,
   not the core mechanism.

4. Optional co-teaching-style agreement check via _half_probas().

Requires from codebase.online.orb: ORB with rate1/decay/_lambda/_boost/
predict_proba_one/_update_members/n_estimators/rng (your current file has all).
"""
from __future__ import annotations

from collections import deque

import numpy as np

from codebase.online.orb import ORB


class NoiseAwareORB(ORB):
    def __init__(self, *args,
                 confidence_window: int = 500,
                 min_confidence: float = 0.05,
                 warmup: int = 30,
                 use_damp: bool = True,
                 use_rescue: bool = True,
                 rescue_margin: float = 1.25,   # prob must exceed thr1 * margin
                 rescue_weight: float = 0.5,    # provisional positive weight
                 noise_rates: tuple[float, float] | None = None,
                 use_loss_correction: bool = False,
                 lc_cap: float = 2.0,
                 use_agreement_check: bool = False,
                 agreement_penalty: float = 0.3,
                 **kwargs):
        super().__init__(*args, **kwargs)
        self.win = {0: deque(maxlen=confidence_window),
                    1: deque(maxlen=confidence_window)}
        self.min_conf = min_confidence
        self.warmup = warmup
        self.use_damp = use_damp
        self.use_rescue = use_rescue
        self.rescue_margin = rescue_margin
        self.rescue_weight = rescue_weight
        self.rho = noise_rates
        self.use_lc = use_loss_correction and noise_rates is not None
        self.lc_cap = lc_cap
        self.use_agree = use_agreement_check
        self.agree_penalty = agreement_penalty
        self.na_trace: list[dict] = []

    # ---- streaming class self-confidence thresholds ---------------------
    def _class_threshold(self, y: int) -> float | None:
        w = self.win[y]
        return float(np.mean(w)) if len(w) >= self.warmup else None

    def _confidence(self, p1: float, y: int) -> float:
        """c = P_model(y|x) / running self-confidence threshold of class y."""
        p_y = p1 if y == 1 else 1.0 - p1
        thr = self._class_threshold(y)
        c = 1.0 if thr is None else min(p_y / max(thr, 1e-6), 1.0)
        self.win[y].append(p_y)
        return max(c, self.min_conf)

    # ---- capped loss-correction weight ----------------------------------
    def _lc_weight(self, y: int) -> float:
        if not self.use_lc:
            return 1.0
        rho0, rho1 = self.rho
        denom = max(1.0 - rho0 - rho1, 1e-6)
        w = (1.0 - (rho0 if y == 1 else rho1)) / denom
        return float(min(w, self.lc_cap))

    def _agreement_flag(self, x: np.ndarray, y: int) -> bool:
        pA, pB = self._half_probas(x)
        conf = 0.75
        return (pA < 1 - conf and pB < 1 - conf) if y == 1 else \
               (pA > conf and pB > conf)

    # ---- main entry -------------------------------------------------------
    def learn_one(self, x: np.ndarray, y: int, weight: float = 1.0):
        p1 = self.predict_proba_one(x)

        # RESCUE: arriving clean label, ensemble confidently disagrees
        rescued = False
        if self.use_rescue and y == 0:
            thr1 = self._class_threshold(1)
            if thr1 is not None and p1 >= min(thr1 * self.rescue_margin, 0.95):
                rescued = True

        y_eff = 1 if rescued else y
        w = weight * (self.rescue_weight if rescued else 1.0) * self._lc_weight(y_eff)

        c = self._confidence(p1, y) if self.use_damp else 1.0
        if self.use_agree and not rescued and self._agreement_flag(x, y):
            c *= self.agree_penalty

        # ORB bookkeeping on the EFFECTIVE label; confidence modulates only
        # the amplification term (full boost for trusted labels, plain-OOB
        # behaviour for suspicious ones)
        self.rate1 = self.decay * self.rate1 + (1 - self.decay) * (y_eff == 1)
        boost = max(self._boost(y_eff), 1.0)
        lam = self._lambda(y_eff) * (1.0 + (boost - 1.0) * c)

        self.na_trace.append(dict(y=int(y), y_eff=int(y_eff), rescued=rescued,
                                  conf=float(c), boost=float(boost),
                                  lam=float(lam), w=float(w), p1=float(p1)))
        ks = self.rng.poisson(max(lam, 0.0), size=self.n_estimators)
        self._update_members(x, y_eff, ks, w)


def ablation_grid(seed: int, orb_config: dict,
                  noise_rates: tuple[float, float]) -> dict:
    """The Phase 4 model set. NA(damp+rescue) is the headline candidate."""
    from codebase.online.orb import OOB, ORB as _ORB
    base = dict(orb_config)
    return {
        "OOB": OOB(n_estimators=base.get("n_estimators", 20), seed=seed),
        "ORB": _ORB(seed=seed, **base),
        "NA(damp)": NoiseAwareORB(seed=seed, use_damp=True, use_rescue=False, **base),
        "NA(rescue)": NoiseAwareORB(seed=seed, use_damp=False, use_rescue=True, **base),
        "NA(damp+rescue)": NoiseAwareORB(seed=seed, use_damp=True, use_rescue=True, **base),
        "NA(damp+rescue+lc)": NoiseAwareORB(seed=seed, use_damp=True, use_rescue=True,
                                            noise_rates=noise_rates,
                                            use_loss_correction=True, **base),
    }

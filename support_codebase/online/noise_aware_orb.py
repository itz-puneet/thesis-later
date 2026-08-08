"""Phase 4: Noise-Aware ORB.

Extends ORB with three optional noise defenses, applied at the moment a
(possibly noisy) training label arrives:

1. Streaming label-confidence term (Confident-Learning-style; Northcutt 2021):
   maintain running per-class self-confidence thresholds over a sliding
   window of the ensemble's out-of-model probabilities; an arriving label
   whose predicted probability for its own class is far below that class's
   threshold receives low confidence c in (0, 1].

2. Loss correction (Natarajan et al., 2013): importance weights from known
   noise rates (rho0, rho1) -- supplied from Phase 1 measurements -- applied
   as sample weights so training is unbiased in expectation.

3. Optional co-teaching-style agreement check (Han et al., 2018): split the
   ensemble into two halves; if both halves confidently contradict the
   arriving label, flag it and multiply confidence by a penalty.

The key design decision (and the thesis's differentiator from Cabral & Minku
2023 / Song et al. 2022): the confidence signal modulates the *oversampling
boost*, i.e. lambda_effective = lambda_ORB(y) * c(x, y), so low-confidence
minority labels are not amplified by the boost function.
"""
from __future__ import annotations

from collections import deque

import numpy as np

from online.orb import ORB


class NoiseAwareORB(ORB):
    def __init__(self, *args,
                 confidence_window: int = 500,
                 min_confidence: float = 0.05,
                 noise_rates: tuple[float, float] | None = None,
                 use_loss_correction: bool = True,
                 use_agreement_check: bool = False,
                 agreement_penalty: float = 0.3,
                 **kwargs):
        super().__init__(*args, **kwargs)
        self.window = {0: deque(maxlen=confidence_window),
                       1: deque(maxlen=confidence_window)}
        self.min_conf = min_confidence
        self.rho = noise_rates                # (rho0, rho1) from Phase 1
        self.use_lc = use_loss_correction and noise_rates is not None
        self.use_agree = use_agreement_check
        self.agree_penalty = agreement_penalty
        self.na_trace: list[dict] = []

    # ---- 1. streaming confident-learning term -------------------------
    def _confidence(self, x, y) -> float:
        """c = P_model(y | x) / running self-confidence threshold of class y,
        clipped to [min_conf, 1]. Cold start (empty window) -> c = 1."""
        p1 = self.predict_proba_one(x)
        p_y = p1 if y == 1 else 1.0 - p1
        thr_window = self.window[y]
        if len(thr_window) < 30:              # cold start
            c = 1.0
        else:
            thr = float(np.mean(thr_window))  # class self-confidence threshold
            c = min(p_y / max(thr, 1e-6), 1.0)
        self.window[y].append(p_y)
        return max(c, self.min_conf)

    # ---- 2. loss-correction sample weight ------------------------------
    def _lc_weight(self, y) -> float:
        """Unbiased-risk importance weight under class-conditional noise
        (simplified positive-weight form of Natarajan et al. 2013):
        w(y) = (1 - rho_{other}) / (1 - rho0 - rho1)."""
        if not self.use_lc:
            return 1.0
        rho0, rho1 = self.rho
        denom = max(1.0 - rho0 - rho1, 1e-6)
        return (1.0 - (rho0 if y == 1 else rho1)) / denom

    # ---- 3. co-teaching-style agreement check --------------------------
    def _agreement_flag(self, x, y) -> bool:
        """True if BOTH ensemble halves confidently contradict label y."""
        pA, pB = self._half_probas(x)
        confident = 0.75
        if y == 1:   # label says defective; both halves sure it's clean?
            return pA < 1 - confident and pB < 1 - confident
        return pA > confident and pB > confident

    # ---- main entry -----------------------------------------------------
    def learn_one(self, x, y, weight: float = 1.0):
        c = self._confidence(x, y)
        if self.use_agree and self._agreement_flag(x, y):
            c *= self.agree_penalty
        w = weight * self._lc_weight(y)

        # ORB bookkeeping, then confidence-modulated boost
        self.rate1 = self.decay * self.rate1 + (1 - self.decay) * (y == 1)
        boost = max(self._boost(y), 1.0)
        # Confidence modulates ONLY the amplification term: a fully trusted
        # label gets the full ORB boost; a suspicious label falls back to
        # plain OOB behaviour (boost -> 1) instead of being amplified.
        lam = self._lambda(y) * (1.0 + (boost - 1.0) * c)
        self.na_trace.append(dict(y=int(y), conf=float(c), boost=float(boost),
                                  lam=float(lam), w=float(w)))
        ks = self.rng.poisson(max(lam, 0.0), size=self.n_estimators)
        self._update_members(x, y, ks, w)

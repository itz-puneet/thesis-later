"""Phase 4: Noise-Aware ORB.

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

    def _observe(self, p1: float, y: int) -> float:
        """Record this arrival in class y's window; return its confidence ratio.

        The window is maintained UNCONDITIONALLY, not only when damping is on.
        The RESCUE path reads the class-1 threshold, so gating window
        maintenance on `use_damp` left `win[1]` permanently empty in the
        rescue-only ablation arm: `_class_threshold(1)` returned None on every
        arrival, no commit was ever rescued, and NA(rescue) was byte-identical
        to plain ORB. Whether the returned confidence is *used* is still the
        damping switch's decision -- see learn_one.
        """
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

        # Observe first (fills the windows for both paths), then decide whether
        # damping actually applies. Note the rescue check above deliberately
        # runs BEFORE this, so an arrival never influences its own threshold.
        c_obs = self._observe(p1, y)
        c = c_obs if self.use_damp else 1.0
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


class FPFilterORB(ORB):
    """ORB + train-time false-positive suppression. Phase 4 primary model.

    Phase 3 established that what costs an online learner performance on SZZ
    labels is the VOLUME of false positives, not any per-label severity: at
    matched corrected mass FP-repair and FN-repair are indistinguishable
    (HL +0.0050, CI [-0.0093, +0.0176]), while removing all 6,565 of BSZZ's
    false positives recovers +0.0402. Restoring false negatives is equivalent
    to no repair at all (TOST p = 0.0008, margin +-0.02), under realistic,
    immediate and at-window delivery alike. So the train-time analogue worth
    building suppresses suspected false positives and leaves the negative
    stream untouched.

    A positive-labelled arrival the ensemble confidently contradicts is
    treated as a suspected SZZ false positive: trained at weight `eps` (0
    discards it) and excluded from the boost.

    TWO DECISION RULES, and why the default is not the quantile.
      The review specified a running q-quantile of recently delivered
      positives, on the reasoning that it needs no calibration. Measured on
      this corpus that rule is degenerate: the ensemble's members agree almost
      completely, so p1 is bimodal at 0 and 1 and the 10th percentile of a
      trailing window is 0.0000 in nearly every segment of every stream. A
      strict comparison against a threshold of zero can never fire -- on
      opennlp/BSZZ it filtered 0 of 75 positive arrivals.

        mode="quantile"  (default) the review's rule, repaired: the comparison
                         is non-strict, so the saturated-at-zero case still
                         catches the confidently-contradicted positives. It
                         filters a BOUNDED fraction (about q) by construction,
                         which is what makes it safe on clean labels.
        mode="fixed"     filter when p1 < tau. Retained for comparison, and
                         NOT recommended -- see below.

      WHY FIXED IS NOT THE DEFAULT. A fixed threshold filters however many
      positives the model happens to be unconfident about, with no bound and
      no reference to how many false positives the source actually contains.
      On the ORACLE arm, where every positive label is correct and there is
      nothing to remove, tau=0.15-0.25 suppressed 67-73% of positives and drove
      mcc_avg from 0.096 to approximately 0.000 -- a total non-degradation
      failure. The quantile rule suppresses about q by construction, so on
      clean labels it costs little: at q=0.05-0.20 the oracle arm IMPROVED
      (+0.010 to +0.013) while BSZZ gained +0.023 to +0.036.

      The lesson generalises: a confidence threshold cannot distinguish "this
      label is probably wrong" from "my model has not learned this pattern
      yet", so the intervention must be bounded in size rather than in
      confidence.

      All of these observations come from commons-scxml, opennlp and
      commons-math only -- which is why those three are declared HELD OUT in
      run_phase4_na_orb.HELD_OUT_PROJECTS and excluded from every reported
      Phase 4 number. None of them may be quoted as a result.

    THE REGISTERED RISK -- lambda self-antagonism.
      ORB sets its oversampling rate from the observed positive rate:
      `_lambda(1) = (1 - rate1) / rate1`. Phase 3 measured the consequence
      directly: the boost rate applied to positive arrivals is a near-perfect
      inverse of how many positives the stream delivers (Spearman rho = -1.000
      across profiles at matched dose). Every positive this filter suppresses
      therefore RAISES lambda for the positives that survive it -- the filter
      works against the mechanism it is bolted onto. `rate_update` controls
      whether it does:

        "observed"  (default) rate1 is updated as if the positive label had
                    been accepted, so suppressing a label expresses distrust
                    of THAT label without telling the ensemble the positive
                    class is rarer than it is. lambda is left alone.
        "suppress"  the arrival is skipped entirely, so rate1 drifts down and
                    lambda rises. This is what a naive implementation does.

      Registered prediction: "suppress" underperforms "observed", and the gap
      widens with filter rate. If that is wrong, the Phase 3 mechanism account
      needs revision.

    A second registered risk is self-reinforcement: a suppressed positive is
    never learned, so its probability stays low and it is suppressed again.
    `fp_trace` records every decision so the filter's realised rate and (joined
    against oracle labels by the runner) its precision are measurable rather
    than assumed.

    Warm-up is counted in POSITIVE labels, not arrivals. Positives are what is
    scarce -- under real latency some projects deliver fewer than 30 of them in
    an entire stream -- and a quantile over an empty window is undefined. Below
    `min_pos_for_threshold` collected probabilities the filter is inert and the
    model is plain ORB, which is the safe direction. `filter_active_from`
    records when it engaged, or None if it never did.
    """

    accepts_sample_id = True

    def __init__(self, *args,
                 mode: str = "quantile",
                 tau: float = 0.25,
                 q: float = 0.10,
                 eps: float = 0.0,
                 min_pos_for_threshold: int = 30,
                 window: int = 500,
                 rate_update: str = "observed",
                 **kwargs):
        super().__init__(*args, **kwargs)
        if rate_update not in ("observed", "suppress"):
            raise ValueError("rate_update must be 'observed' or 'suppress'")
        if mode not in ("fixed", "quantile"):
            raise ValueError("mode must be 'fixed' or 'quantile'")
        self.mode = mode
        self.tau = tau
        self.q = q
        self.eps = eps
        self.min_pos_for_threshold = min_pos_for_threshold
        self.rate_update = rate_update
        self.p1_pos: deque[float] = deque(maxlen=window)
        self.n_seen = 0
        self.n_pos_seen = 0
        self.n_filtered = 0
        self.filter_active_from: int | None = None
        self.fp_trace: list[dict] = []

    def _threshold(self) -> float | None:
        if self.mode == "fixed":
            return self.tau
        if len(self.p1_pos) < self.min_pos_for_threshold:
            return None
        return float(np.quantile(np.asarray(self.p1_pos, dtype=float), self.q))

    def _suspect(self, p1: float, thr: float | None) -> bool:
        if thr is None:
            return False
        # Non-strict in quantile mode: p1 saturates at exactly 0.0 on this
        # corpus, and those are precisely the contradicted positives.
        return p1 < thr if self.mode == "fixed" else p1 <= thr

    def learn_one(self, x: np.ndarray, y: int, weight: float = 1.0,
                  sample_id: int | None = None):
        self.n_seen += 1
        if y != 1:
            super().learn_one(x, y, weight)
            return

        self.n_pos_seen += 1
        p1 = self.predict_proba_one(x)
        thr = self._threshold()
        suspected = self._suspect(p1, thr)
        self.p1_pos.append(float(p1))

        if suspected:
            if self.filter_active_from is None:
                self.filter_active_from = self.n_seen
            self.n_filtered += 1
            self.fp_trace.append(dict(sample_id=sample_id, n_seen=self.n_seen,
                                      p1=float(p1), thr=float(thr), filtered=True))
            if self.rate_update == "observed":
                # Distrust this label without telling the ensemble that
                # positives are rarer than they are -- see the class docstring.
                self.rate1 = self.decay * self.rate1 + (1.0 - self.decay) * 1.0
            if self.eps > 0:
                ks = self.rng.poisson(self.eps, size=self.n_estimators)
                self._update_members(x, 1, ks, weight)
            return

        self.fp_trace.append(dict(sample_id=sample_id, n_seen=self.n_seen,
                                  p1=float(p1),
                                  thr=None if thr is None else float(thr),
                                  filtered=False))
        super().learn_one(x, y, weight)

    def filter_stats(self) -> dict:
        return dict(n_seen=self.n_seen, n_pos_seen=self.n_pos_seen,
                    n_filtered=self.n_filtered,
                    filter_rate=self.n_filtered / max(self.n_pos_seen, 1),
                    filter_active_from=self.filter_active_from,
                    mean_lambda_pos=float(np.mean(
                        [t["lam"] for t in self.trace if t["y"] == 1])) if any(
                        t["y"] == 1 for t in self.trace) else float("nan"))

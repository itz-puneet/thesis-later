"""PATCH: re-register Phase 4 around the Phase 3 reversal, BEFORE its first run.

Two parts:

PART 1 -- add to codebase/online/noise_aware_orb.py: an `fp_filter` mode.
Phase 3 showed the winning intervention is FP-removal (train-time analogue of
the repair that recovered +0.04 MCC), not FN-rescue (the repair that recovered
nothing). fp_filter discards / epsilon-weights positive-labeled arrivals whose
ensemble probability sits in the running low quantile of delivered-positive
probabilities -- a two-hyperparameter, calibration-free FP suppressor
(Backup A "filtering" from the alternatives doc, now mechanism-aligned).

PART 2 -- replace the pre-registration block in experiments/run_phase4_na_orb.py.
Old registration (NA(damp+rescue) headline, FN framing) is retired with Phase 3's
hypothesis. Since Phase 4 has produced zero results, re-registering now is
legitimate; commit this patch with a message citing the Phase 3 reversal.
"""

# ============================================================================
# PART 1 -- append to codebase/online/noise_aware_orb.py
# ============================================================================
PART1 = '''
class FPFilterORB(ORB):
    """ORB + train-time false-positive filtering (Phase-3-aligned primary).

    A positive-labeled arrival whose ensemble p1 falls below the running
    q-quantile of recently delivered positives' p1 is treated as a suspected
    SZZ false positive: trained with weight `eps` (0 = discard) and EXCLUDED
    from the boost. Negative-labeled arrivals are untouched -- Phase 3 showed
    restoring/boosting the positive side of the stream recovers nothing.

    Hyperparameters: q (filter quantile), eps (residual weight), warmup_frac
    (fraction of arrivals before filtering activates -- fixes the cold-start
    harm observed in smoke tests).
    """

    def __init__(self, *args, q: float = 0.10, eps: float = 0.0,
                 warmup_frac: float = 0.05, window: int = 500, **kwargs):
        super().__init__(*args, **kwargs)
        from collections import deque
        self.q, self.eps, self.warmup_frac = q, eps, warmup_frac
        self.p1_pos = deque(maxlen=window)   # p1 of delivered positive labels
        self.n_seen = 0
        self.n_stream_est = None             # optional; warmup uses n_seen only
        self.fp_trace: list[dict] = []

    def _filter_threshold(self):
        import numpy as np
        if len(self.p1_pos) < max(30, int(self.warmup_frac * max(self.n_seen, 1))):
            return None
        return float(np.quantile(self.p1_pos, self.q))

    def learn_one(self, x, y, weight: float = 1.0):
        import numpy as np
        self.n_seen += 1
        if y == 1:
            p1 = self.predict_proba_one(x)
            thr = self._filter_threshold()
            suspected = thr is not None and p1 < thr
            self.p1_pos.append(p1)
            self.fp_trace.append(dict(p1=float(p1), thr=thr, filtered=suspected))
            if suspected:
                if self.eps > 0:
                    # residual-weight training, no boost, no rate1 update
                    lam = self._lambda(1) * 0 + self.eps
                    ks = self.rng.poisson(lam, size=self.n_estimators)
                    self._update_members(x, 1, ks, weight)
                return
        # default ORB behaviour for everything else
        super().learn_one(x, y, weight)
'''

# ============================================================================
# PART 2 -- replacement pre-registration block for run_phase4_na_orb.py
# (replace the docstring hypotheses, HEADLINE_MODEL constant, ablation set,
#  and the headline-tests list)
# ============================================================================
PART2_DOCSTRING = """
RE-REGISTERED HYPOTHESES (v2, post-Phase-3; committed before any Phase 4 run).
Rationale: Phase 3's controlled repair on real labels showed FP-removal
recovers +0.0402 MCC (17/21, global Holm .0019) while FN-restoration recovers
nothing (HL -0.0012, CI [-0.0093,+0.0080]). The v1 registration's headline
NA(damp+rescue) and its FN framing are therefore retired unrun.

  H1  (primary):     NA(fp_filter) > ORB on label_BSZZ      [FP-heaviest source]
  H2  (secondary):   NA(fp_filter) > ORB on label_MASZZ and label_AGSZZ
                     [mid-FP sources; tests generalization beyond BSZZ]
  ND  (gate):        NA(fp_filter) vs ORB on label_oracle -- no significant drop
                     (TOST margin +-0.02 on mcc_avg); failure kills adoptability.
  MP  (mechanism probe, registered PREDICTION not hope):
                     NA(rescue) - ORB <= 0 on every SZZ source. Rescue
                     manufactures positives; Phase 3 says added positives are
                     worthless at realistic delivery and FPs are amplified --
                     so rescue confirming <=0 independently corroborates the
                     Phase 3 mechanism. If rescue HELPS, the mechanism story
                     needs revision. Either outcome is informative.
  All tests: project-paired Wilcoxon on time-averaged MCC, HL + rank-biserial,
  Holm within this 4-test family. Everything else exploratory and labeled so.

MODEL SET (ablation):
  OOB, ORB, NA(fp_filter), NA(damp), NA(fp_filter+damp),
  NA(rescue)                      [mechanism probe only]
  NA(fp_filter+precweight)        [w+ = measured variant precision, replaces
                                   capped Natarajan arm: down-weights the
                                   error type Phase 3 showed matters]
"""

PART2_CODE = '''
HEADLINE_MODEL, BASELINE_MODEL = "NA(fp_filter)", "ORB"

def ablation_grid_v2(seed: int, orb_config: dict, precision_by_variant: dict):
    from codebase.online.orb import OOB, ORB as _ORB
    from codebase.online.noise_aware_orb import NoiseAwareORB, FPFilterORB
    base = dict(orb_config)
    return {
        "OOB": OOB(n_estimators=base.get("n_estimators", 20), seed=seed),
        "ORB": _ORB(seed=seed, **base),
        "NA(fp_filter)": FPFilterORB(seed=seed, **base),
        "NA(damp)": NoiseAwareORB(seed=seed, use_damp=True, use_rescue=False, **base),
        "NA(fp_filter+damp)": None,   # compose after tuning if both survive solo
        "NA(rescue)": NoiseAwareORB(seed=seed, use_damp=False, use_rescue=True, **base),
    }

HEADLINE_TESTS = [
    ("BSZZ",  "H1_fp_filter_vs_orb_bszz"),
    ("MASZZ", "H2a_fp_filter_vs_orb_maszz"),
    ("AGSZZ", "H2b_fp_filter_vs_orb_agszz"),
    ("oracle","ND_non_degradation_tost"),
]
# For "precweight": pass sample weight w = precision_hat[variant] into
# learn_one for positive-labeled arrivals of that variant (one line where the
# runner calls learn_one via prequential_latency -> add weight hook, or wrap
# the model). precision_hat comes from phase1_bias.json per label source.
'''

if __name__ == "__main__":
    print(__doc__)
    print("--- PART 1 (append to noise_aware_orb.py) ---")
    print(PART1)
    print("--- PART 2 (pre-registration replacement) ---")
    print(PART2_DOCSTRING)
    print(PART2_CODE)

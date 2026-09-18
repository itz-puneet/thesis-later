"""Global configuration for the SZZ-noise / JIT-SDP thesis experiments."""
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
RAW_DATA_DIR = DATA_DIR / "raw"
PROCESSED_DATA_DIR = DATA_DIR / "processed"
RESULTS_DIR = ROOT / "results"
PHASE1_RESULTS_DIR = RESULTS_DIR / "phase1"
PHASE2_RESULTS_DIR = RESULTS_DIR / "phase2"
NOTEBOOKS_DIR = ROOT / "notebooks"

for d in (DATA_DIR, RAW_DATA_DIR, PROCESSED_DATA_DIR, RESULTS_DIR, PHASE1_RESULTS_DIR, PHASE2_RESULTS_DIR):
    d.mkdir(parents=True, exist_ok=True)

# 10 Random seeds for statistical stability
RANDOM_SEEDS = [7, 13, 21, 42, 77, 101, 123, 202, 314, 999]

# Kamei et al. (2013) 14 change-level features
KAMEI_FEATURES = [
    "ns", "nd", "nf", "entropy",          # diffusion
    "la", "ld", "lt",                     # size
    "fix",                                # purpose
    "ndev", "age", "nuc",                 # history
    "exp", "rexp", "sexp",                # experience
]

# SZZ Variants evaluated in Phase 1 and 2
SZZ_VARIANTS = ["BSZZ", "AGSZZ", "MASZZ", "LSZZ", "RSZZ", "RASZZ"]

# Phase 3: noise doses (fraction of labels perturbed)
NOISE_LEVELS = [0.05, 0.10, 0.15, 0.20, 0.25, 0.30]

# Online evaluation parameters
VERIFICATION_WAIT_DAYS = 90     # waiting window W (Cabral et al., 2019)
PREQUENTIAL_FADING = 0.99       # fading factor for prequential metrics

# ORB hyperparameters (Cabral et al., 2019 defaults)
ORB_CONFIG = dict(
    n_estimators=20,
    theta=0.4,                       # decay for moving-average of predictions (bias signal)
    l0=10.0, l1=12.0, m=1.5, n=3.0,  # boost-function shape parameters
    target_defect_rate=None,         # None -> use running observed rate
)

# Phase 4: NoiseAwareORB (damp/rescue) defaults. Unreferenced since the Phase 4
# re-registration demoted rescue to a mechanism probe; kept for that arm.
NA_ORB_DAMP_CONFIG = dict(
    confidence_window=500,   # sliding window for running class-confidence thresholds
    min_confidence=0.05,     # floor so no instance is fully silenced
    use_loss_correction=True,
    use_agreement_check=False,
)


# ---------------------------------------------------------------------------
# Phase 4: frozen FPFilterORB configuration (Step C, run 35317549121)
#
# Tuned ONLY on the three held-out projects below, which are excluded from
# every reported Phase 4 number. 42 configurations were evaluated on the
# registered arm; 24 passed the non-degradation gate. Selection rule, declared
# before the sweep: ND gate first (oracle within -0.02 of ORB), then maximum
# gain on BSZZ, then the more conservative filter.
#
# Held-out gains for this configuration: BSZZ +0.0451, MASZZ +0.0232,
# LSZZ +0.0131, oracle +0.0072, filter rate on BSZZ 0.24. None of these are
# results -- they are tuning-set numbers and must never be quoted as findings.
#
# q = 0.3 is an interior optimum, not a grid edge: extending the sweep to
# q = 0.4 and 0.5 lowered the BSZZ gain to 0.0402 and 0.0288.
#
# rate_update is NOT tuned. It is the R1 registered arm and is frozen at
# "observed" regardless of which level scored better, because optimising it
# would convert a registered prediction into a fit.
# ---------------------------------------------------------------------------
NA_ORB_HELD_OUT_PROJECTS = ("commons-scxml", "opennlp", "commons-math")

FP_FILTER_CONFIG = {
    "mode": "quantile",
    "q": 0.30,
    "eps": 0.1,
    "min_pos_for_threshold": 30,
    "rate_update": "observed",
}

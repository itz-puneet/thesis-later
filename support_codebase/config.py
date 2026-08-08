"""Global configuration for the SZZ-noise / JIT-SDP thesis experiments."""
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DATA_DIR = ROOT / "datasets"
RESULTS_DIR = ROOT / "results"
FIGURES_DIR = ROOT / "figures"
for d in (DATA_DIR, RESULTS_DIR, FIGURES_DIR):
    d.mkdir(exist_ok=True)

RANDOM_SEEDS = [7, 13, 21, 42, 77, 101, 123, 202, 314, 999]  # 10 runs per config

# Kamei et al. (2013) change-level features
KAMEI_FEATURES = [
    "ns", "nd", "nf", "entropy",          # diffusion
    "la", "ld", "lt",                     # size
    "fix",                                # purpose
    "ndev", "age", "nuc",                 # history
    "exp", "rexp", "sexp",                # experience
]

SZZ_VARIANTS = ["B-SZZ", "AG-SZZ", "MA-SZZ", "RA-SZZ", "R-SZZ"]

# Phase 3: noise doses (fraction of labels perturbed)
NOISE_LEVELS = [0.05, 0.10, 0.15, 0.20, 0.25, 0.30]

# Online evaluation
VERIFICATION_WAIT_DAYS = 90     # waiting window W (Cabral et al., 2019)
PREQUENTIAL_FADING = 0.99       # fading factor for prequential metrics

# ORB hyperparameters (Cabral et al., 2019 defaults, tune per dataset)
ORB = dict(
    n_estimators=20,
    theta=0.4,       # decay for moving-average of predictions (bias signal)
    l0=10.0, l1=12.0, m=1.5, n=3.0,  # boost-function shape parameters
    target_defect_rate=None,          # None -> use running observed rate
)

# Phase 4: Noise-Aware ORB
NA_ORB = dict(
    confidence_window=500,   # sliding window for running class-confidence thresholds
    min_confidence=0.05,     # floor so no instance is fully silenced
    use_loss_correction=True,
    use_agreement_check=False,  # optional co-teaching-style check
)

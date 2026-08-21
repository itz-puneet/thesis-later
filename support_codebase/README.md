# [ARCHIVED / SCAFFOLD ONLY] SZZ Noise × JIT-SDP — Support Codebase

> **WARNING / ARCHIVED NOTICE**:
> This directory (`support_codebase/`) contains early prototyping scaffold code and is **ARCHIVED**.
> The active, authoritative codebase is located under `codebase/` and `experiments/`.
> Do NOT import from `support_codebase` in new experiments or scripts.

## Original Layout
```
config.py                 # global constants, paths, hyperparameters
data/loader.py            # dataset loading + schema (Kamei features)
szz/variants.py           # SZZ variant interface (pyszz adapters + placeholders)
models/baselines.py       # LApredict, JITLine (offline baselines)
online/orb.py             # Online Bagging, OOB, ORB
online/noise_aware_orb.py # Phase 4: Noise-Aware ORB
noise/injection.py        # Phase 3: symmetric + asymmetric noise models
evaluation/metrics.py     # MCC, G-mean, prequential tracker, stats tests
evaluation/regimes.py     # naive k-fold / chronological / prequential-with-latency
experiments/run_phase1.py ... run_phase4.py
```

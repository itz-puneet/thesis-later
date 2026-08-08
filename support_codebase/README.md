# SZZ Noise × JIT-SDP — Thesis Codebase

Modular implementation of the four thesis phases.

## Layout
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

## Quick start
```bash
pip install -r requirements.txt
python -m experiments.run_phase1 --demo   # runs on synthetic demo data
python -m experiments.run_phase2 --demo
python -m experiments.run_phase3 --demo
python -m experiments.run_phase4 --demo
```
Replace `--demo` with `--data path/to/commits.csv` once real datasets are wired in
(see `data/loader.py` docstring for the expected schema).

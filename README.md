# Thesis: SZZ Label Noise in Just-In-Time Defect Prediction

This repository contains the experimental pipeline and empirical artifacts for the thesis investigating the downstream impact of SZZ heuristic label noise in Just-In-Time Software Defect Prediction (JIT-SDP).

---

## Environment Setup

To set up the environment on any machine:

### 1. Clone the Repository
```bash
git clone git@github.com:itz-puneet/thesis-later.git
cd thesis-later
```

### 2. Set Up Virtual Environment
Ensure you have Python 3 (>= 3.10) installed:
```bash
python3 -m venv venv
```

### 3. Activate Virtual Environment
- **Linux / macOS**:
  ```bash
  source venv/bin/activate
  ```
- **Windows**:
  ```cmd
  venv\Scripts\activate
  ```

### 4. Install Dependencies
```bash
pip install --upgrade pip
pip install -r requirements.txt
```

---

## Experiment Execution Commands

Below are all the commands required to run each stage of the thesis pipeline.

### Step 0: ORB Benchmark Replication (Cabral et al., 2019)
Validates the streaming Oversampling Rate Boosting (ORB) implementation against published benchmarks:
```bash
python scripts/replicate_cabral_orb.py
```
*Outputs: `results/replication/cabral2019_orb_replication.csv`*

---

### Step 1: Phase 1 — SZZ Label Extraction & Quality Evaluation

#### (A) Fast Evaluation on Pre-computed Labels (Instant, ~2 seconds)
Evaluates all 6 SZZ variants (BSZZ, AGSZZ, MASZZ, LSZZ, RSZZ, RASZZ) against the human oracle ground truth with NaN handling and full universe left-joins:
```bash
python -m experiments.evaluate_confusion_matrix
```
*Outputs:*
- `phase1_bias.json` *(noise parameters $\rho_0, \rho_1$ for Phase 3)*
- `results/phase1/phase1_quality_corrected.csv`
- `results/phase1/phase1_quality_per_project.csv`
- `results/phase1/phase1_intervariant_kappa.csv`

#### (B) Full PySZZ Pipeline Re-run (Extract from Git Repositories)
Runs the full PySZZ $v2$ pipeline across the 21 cloned repositories, outputting both raw fix-to-inducing JSON mappings and binary label CSVs:
```bash
# Run on all 21 projects and all 6 variants:
python -m experiments.run_phase1_oracle

# Test on a single project:
python -m experiments.run_phase1_oracle --projects giraph

# Specify specific variants:
python -m experiments.run_phase1_oracle --variants bszz agszz rszz --overwrite
```
*Outputs: `results/phase1_raw/*.json` and `results/phase1/*_labels.csv`*

---

### Step 1b: One-Time Extraction of Small Committed Inputs

Heavy experiments run on GitHub Actions, where the 101 MB JIT-Fine zip and the 830 MB
of cloned repositories are unavailable. Both are replaced by two small committed files,
regenerated only if Phase 1 is re-run from scratch:

```bash
# Stable Kamei features / author_ts / label_oracle -> data/processed/phase2_features.csv (4.2 MB)
# Memory-safe (streams the inner zip); cap it on a small machine:
systemd-run --user --scope -p MemoryMax=2G -p MemorySwapMax=0 \
    venv/bin/python scripts/extract_base_features.py

# Author dates of the 5,453 Defects4J fix commits -> data/raw/fix_commit_dates.csv (0.4 MB)
python scripts/extract_fix_dates.py
```

Only `extract_fix_dates.py` needs the cloned repos; only `extract_base_features.py`
needs the zip. After both are committed, every later rebuild runs from small inputs.

---

### Step 2: Verification Latency Construction (`fix_ts`)

#### Option A: Real Verification Latency (Recommended when raw mappings exist)
Reconstructs exact commit-level defect arrival timestamps ($fix\_ts$) from Defects4J fix dates:
```bash
python scripts/build_fix_ts.py --mode real
```

#### Option B: Fixed-Delay Online Evaluation Fallback ($W = 90$ days)
Sets uniform 90-day waiting delay across all commits:
```bash
python scripts/build_fix_ts.py --mode uniform
```
*Updates: `data/processed/phase2_commits.csv` with `fix_ts` columns.*

---

### Step 3: Phase 2 — Downstream Impact Evaluation

Evaluates 3 models (`LApredict`, threshold-tuned `JITLine`, `ORB`) across 7 label sources (oracle + 6 SZZ variants) and 3 evaluation regimes (naive $k$-fold, chronological 50/50, prequential streaming with latency).

#### Quick Smoke Test (Fast mode: 3 seeds, 50 trees, 5 folds)
```bash
python -m experiments.run_phase2_impact --fast
```

#### Full Experiment (All 21 projects, 10 seeds, auto-detect CPU cores)
- **With Real Verification Latency:**
  ```bash
  python -m experiments.run_phase2_impact --latency_mode real
  ```
- **With Uniform Delay:**
  ```bash
  python -m experiments.run_phase2_impact --latency_mode uniform
  ```
- **Specifying Parallel Workers Explicitly:**
  ```bash
  python -m experiments.run_phase2_impact --latency_mode real --n_jobs 8
  ```

*Outputs (`results/phase2/`):*
- `phase2_results.csv` *(14,700 evaluation runs)*
- `phase2_summary.csv` *(mean and std metrics by model/regime/label)*
- `statistical_tests.csv` *(paired Wilcoxon & Cliff's delta statistics)*
- `inflation_ladder.csv` *(regime inflation metrics)*

---

### Step 3b: Label-Consistency Gate (run after every rebuild)

Asserts that the noise rates published in `phase1_bias.json` describe exactly the labels
in `data/processed/phase2_commits.csv`. Phase 2 once trained on a label vintage one commit
older than Phase 1 reported, because the dataset cache was never invalidated; this check
makes that unreachable and runs in CI before any compute is spent.

```bash
python -m experiments.check_label_consistency
```

Rebuild order matters — `build_unified_dataset()` cannot reconstruct `fix_ts`:

```bash
python -m experiments.evaluate_confusion_matrix
python -c "from codebase.data.loader import build_unified_dataset; build_unified_dataset()"
python scripts/build_fix_ts.py --mode real
python -m experiments.check_label_consistency
```

`load_or_build_dataset()` refuses to serve a cache older than the Phase 1 label files,
so forgetting this sequence raises rather than silently producing stale results.

---

### Step 3c: Running the Heavy Pipeline on GitHub Actions

The full chain (Phase 1 evaluation → rebuild → `fix_ts` → gate → Phase 2 → imputation
sensitivity → reports) runs on a runner via the **Phase 2 Pipeline** workflow
(`.github/workflows/phase2_experiment.yml`), triggered from the Actions tab:

| Input | Values | Notes |
|---|---|---|
| `stage` | `smoke` / `full` | `smoke` = 3 seeds / 50 trees / 5 folds (~25 min); `full` = 10 seeds (~2 h) |
| `latency_mode` | `real` / `uniform` | `real` requires the committed `fix_commit_dates.csv` |
| `push_results` | true / false | Commits results back to `master`; `full` stage only |

Run `smoke` first — it exercises the entire chain including the gate, so a mistake costs
minutes rather than hours. Results and figures are uploaded as artifacts on every run,
including failures.

---

### Step 4: Report and Visualization Generation
Regenerates publication-ready figures, tables, and reports from experimental outputs:
```bash
python scripts/generate_report.py
```
*Outputs: HTML and Markdown summaries under `reports/` and figures in `reports/figures/`.*

---

## Project Structure & Documentation

- `01_Learning_Guide.md`: Theoretical concepts and learning guide for the thesis.
- `02_Thesis_Outline.md`: Structure and chapter outline of the thesis.
- `03_Execution_and_Supervisor_Plan.md`: Phase-wise milestones and meeting checklists.
- `Code_Review_Report.md`: In-depth code review report, findings, and verified strengths.
- `codebase/`:
  - `config.py`: Global constants, paths, and hyperparameters.
  - `data/loader.py`: Unified dataset loading and schema formatting.
  - `models/baselines.py`: `LApredict` and SMOTE/threshold-tuned `JITLine`.
  - `online/orb.py`: Oversampling Rate Boosting (ORB) online learner.
  - `evaluation/regimes.py`: Naive $k$-fold, chronological split, and prequential streaming latency.
  - `evaluation/metrics.py`: MCC, G-mean, Prequential Tracker, Wilcoxon & Cliff's $\delta$.
- `experiments/`: Experiment execution scripts (`evaluate_confusion_matrix.py`, `run_phase1_oracle.py`, `run_phase2_impact.py`).
- `scripts/`: Utility scripts (`build_fix_ts.py`, `replicate_cabral_orb.py`, `generate_report.py`).
- `results/`: Artifacts, tables, and statistical outputs for Phase 1, Phase 2, and replication.

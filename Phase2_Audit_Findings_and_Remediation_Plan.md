# Independent Audit of Phases 1 & 2 — Findings and Remediation Plan

**Audit date:** 2026-09-03
**Scope:** working tree at `master` @ `31c41a4`, plus the label-file history back to `88b4eb2`.
**Method:** every headline number in `Phase1_Phase2_Comprehensive_Analysis_and_Supervisor_Pitch.md` was recomputed from the committed artifacts (`results/phase1/`, `results/phase2/`, `data/processed/phase2_commits.csv`, `phase1_bias.json`) rather than read from the reports. Where the reports and the artifacts disagree, the artifacts win. The dataset was rebuilt once, diffed, and then restored byte-identical (`git status` is clean apart from the two report files).

---

## Table of Contents

1. [Executive summary](#1-executive-summary)
2. [What is verified correct](#2-what-is-verified-correct)
3. [BLOCKER — Phase 2 trained on stale labels](#3-blocker--phase-2-trained-on-stale-labels)
4. [MAJOR — Overstated claims about Oracle vs BSZZ](#4-major--overstated-claims-about-oracle-vs-bszz)
5. [MAJOR — The third rung of the inflation ladder confounds model with regime](#5-major--the-third-rung-of-the-inflation-ladder-confounds-model-with-regime)
6. [MODERATE — Methodological issues to fix or document](#6-moderate--methodological-issues-to-fix-or-document)
7. [MINOR — Numeric corrections to the pitch document](#7-minor--numeric-corrections-to-the-pitch-document)
8. [Remediation plan — ordered, with commands](#8-remediation-plan--ordered-with-commands)
9. [Revised claims you can defend after the re-run](#9-revised-claims-you-can-defend-after-the-re-run)
10. [How to frame this to your supervisor](#10-how-to-frame-this-to-your-supervisor)
11. [Implications for Phase 3 and Phase 4](#11-implications-for-phase-3-and-phase-4)
12. [Appendix — verification commands](#12-appendix--verification-commands)

---

## 1. Executive summary

The pipeline is sound in construction. The ORB implementation is validated, the experiment grid is correctly wired with no train/eval label leakage, the statistics are paired at the right unit, and your two strongest claims — temporal leakage and the self-deception gap — survive multiple-comparison correction with room to spare.

There is, however, **one blocking data-consistency bug**: the dataset Phase 2 trained on carries an older vintage of the SZZ labels than the one Phase 1 reports. Every Phase 2 number in the report was therefore computed on labels whose noise rates are not the ρ₀/ρ₁ you publish. This is the same class of bug as Finding 1 in `Code_Review_Report.md`, re-opened in the opposite direction, and it was not caught by `Code_Review_v2.md`.

Beyond that, three claims in the pitch document assert more than the statistics support, and a handful of reported figures do not match their source files.

| # | Severity | Finding | Effort to fix |
|---|---|---|---|
| 3 | **BLOCKER** | Phase 2 trained on the pre-`22acb13` label vintage; Phase 1 reports the post-`22acb13` vintage | ~6–10 h compute + guard |
| 4 | **MAJOR** | "Oracle conclusively outperforms all SZZ variants" is false for BSZZ (p = 0.39) | Text rewrite |
| 5 | **MAJOR** | Batch→streaming rung of the inflation ladder confounds regime with learner | 1 experiment or a text rewrite |
| 6a | MODERATE | Prequential metric is a terminal value over an effective window of ~100 commits | ~1 h code + re-run |
| 6b | MODERATE | No multiple-comparison correction despite outline §3.4 promising it | ~1 h |
| 6c | MODERATE | Self-deception tests pool two models into 42 non-independent pairs, described as "21 projects" | ~1 h |
| 6d | MODERATE | JITLine threshold protocol is unstable; frozen threshold mismatches the refit model | ~2 h |
| 6e | MODERATE | Oracle's `fix_ts` is a union of SZZ mappings — SZZ inside the SZZ-free condition | Disclosure |
| 6f | MODERATE | Unweighted mean over projects spanning 544–4,026 commits, 1.8–19.3% defect rate | Appendix + robustness check |
| 7 | MINOR | Six reported figures do not match their source files | ~30 min |

---

## 2. What is verified correct

Do not re-litigate any of these. They reproduce exactly.

**Phase 1 is internally self-consistent.** Re-running the merge in `experiments/evaluate_confusion_matrix.py` by hand reproduces `phase1_bias.json` exactly: BSZZ TP+FP = 1,495 + 6,565 = 8,060 flagged commits, and an independent rebuild from `results/phase1/*_labels.csv` also yields 8,060. All six variants sit on an identical 27,319-commit denominator with zero NaN and zero dropped rows. The oracle universe (`data/raw/jit_ground_truth.csv`) and the JIT-Fine feature set share all 27,319 `(project, commit_id)` keys with zero asymmetric difference.

**Reproducibility is restored.** `results/phase1_raw/` contains all 126 fix→inducing JSONs (6 variants × 21 projects). This was the artifact whose loss made Phase 1 unreproducible in the first code review; `fix_ts` reconstruction and Phase 3 both depend on it.

**The ORB replication is a genuine credibility artifact.** `results/replication/cabral2019_orb_replication.csv` covers 14 Cabral et al. datasets × 10 seeds, G-mean 0.46–0.93, mean ≈ 0.68 — squarely in the published range. Your low Phase 2 numbers are a property of the data, not the implementation. (One caveat in §7.)

**No leakage in the experiment wiring.** `naive_kfold` and `chronological` train on `label_col` and score on `eval_label_col` with no cross-contamination. JITLine's threshold is tuned on a tail of the *training* split only. ORB's Welford normalizer updates only inside `learn_one`, never during `predict_one`. The `heapq` tiebreaker in `prequential_latency` correctly guarantees the tentative-clean label is consumed before its later correction at the same timestamp.

**Row counts and win counts reproduce.** 14,700 rows, all unique on `(project, seed, model, train_label, eval_mode, regime)`. JITLine chronological: BSZZ beats oracle in exactly 13/21 projects (0.1309 vs 0.1028). ORB as-is: oracle beats BSZZ in exactly 14/21. The κ matrix, the +0.1407 regime-inflation delta, and the +0.1803 self-deception delta all reproduce.

**Your two headline claims survive Holm correction across all 30 tests.**

| Claim | Raw p | Holm-adjusted (m=30) |
|---|---|---|
| Regime inflation, JITLine oracle, naive → chronological | 2.86e-06 | **8.0e-05** |
| Self-deception gap, BSZZ, naive k-fold | 6.54e-08 | **2.0e-06** |
| Self-deception gap, BSZZ, chronological | 7.14e-06 | **1.8e-04** |
| Self-deception gap, MASZZ / LSZZ / RASZZ, naive k-fold | 2.1e-06 – 6.5e-06 | 6.1e-05 – 1.7e-04 |
| Label-source gap, ORB oracle vs RASZZ | 8.52e-04 | **0.0196** |

Nine of thirty tests survive Holm at α = 0.05. That is your defensible ground and it is solid.

---

## 3. BLOCKER — Phase 2 trained on stale labels

### 3.1 What I found

`data/processed/phase2_commits.csv` — the single file every Phase 2 model reads — carries the SZZ label columns as they existed at commit `975302a` (2026-08-23), **one commit before** the Phase 1 label regeneration in `22acb13` (2026-08-31 10:19). `phase1_bias.json` and `results/phase1/phase1_quality_corrected.csv` were regenerated from the *new* labels in `93c3fcf` (10:36). Phase 2 then ran at `9634ee4` (14:30 IST) against the old ones.

Rebuilding the dataset from the current label files and diffing against the file Phase 2 actually used:

| Variant | Positives used by Phase 2 | Positives in current Phase 1 | Commits relabelled | % of corpus |
|---|---|---|---|---|
| BSZZ | 7,318 | 8,060 | 742 | 2.72% |
| AGSZZ | 4,474 | 5,876 | 1,546 | 5.66% |
| MASZZ | 5,394 | 6,154 | 860 | 3.15% |
| LSZZ | 2,130 | 2,287 | 285 | 1.04% |
| RSZZ | 2,699 | 3,015 | 420 | 1.54% |
| RASZZ | 4,153 | 5,553 | 1,768 | 6.47% |

The positive counts in `phase2_commits.csv` match the label files at `975302a` **exactly, for all six variants** — that is what pins the vintage. For BSZZ I confirmed per-commit agreement of 1.00000 against the `88b4eb2` files.

### 3.2 Why this matters, twice over

**(a) The published noise parameters are not the noise parameters of the labels you trained on.** Recomputing the confusion matrix directly against `phase2_commits.csv` gives a materially different noise profile:

| Variant | ρ₀ reported (Phase 1) | ρ₀ actually trained on | ρ₁ reported | ρ₁ actually trained on | Precision reported | Precision actual |
|---|---|---|---|---|---|---|
| BSZZ | 0.2627 | **0.2364** | 0.3589 | **0.3954** | 0.1855 | **0.1927** |
| AGSZZ | 0.1915 | **0.1406** | 0.5326 | **0.5879** | 0.1855 | **0.2148** |
| MASZZ | 0.2013 | **0.1730** | 0.5180 | **0.5407** | 0.1826 | **0.1986** |
| LSZZ | 0.0666 | **0.0613** | 0.7333 | **0.7436** | 0.2720 | **0.2808** |
| RSZZ | 0.0927 | **0.0818** | 0.7003 | **0.7196** | 0.2318 | **0.2423** |
| RASZZ | 0.1813 | **0.1309** | 0.5617 | **0.6218** | 0.1840 | **0.2124** |

Your thesis narrative is *"Phase 1 measures the noise, Phase 2 measures what that noise does."* Right now the two halves of that sentence describe different label sets. An examiner who runs your own `evaluate_confusion_matrix.py` against your own `phase2_commits.csv` will find this in about ten minutes.

**(b) Your two review documents quote two different vintages.** The "Corrected Phase 1 table" in `Code_Review_Report.md` (BSZZ precision 0.193, recall 0.605, ρ₀ 0.236, ρ₁ 0.395) reproduces *exactly* from `phase2_commits.csv` — it is the stale vintage. The table in the pitch document is the fresh vintage. Both are presented as "the corrected Phase 1 table." Only one can be.

### 3.3 Root cause

Two mechanisms compound:

1. **`codebase/data/loader.py:120-125`** — `load_or_build_dataset()` returns the cached CSV whenever the file exists. Nothing compares its mtime against `results/phase1/*_labels.csv`, and `--force_rebuild` is never passed by `run_phase2_impact.py`. Regenerating Phase 1 therefore has no effect on Phase 2 unless you delete the cache by hand.
2. **`scripts/build_fix_ts.py`** reads the stale CSV, adds seven `fix_ts` columns, and writes it back. This refreshed the mtime to 10:42 — *after* the Phase 1 regeneration at 10:36 — which makes the file look current to any timestamp-based sanity check. That is very likely why `Code_Review_v2.md` verified the `fix_ts` columns were present and never questioned the labels beside them.

### 3.4 The trap waiting in the fix

`build_unified_dataset()` selects its `fix_ts` columns off the JIT-Fine pickles, which contain none:

```python
fix_ts_cols = [c for c in full_df.columns if c.startswith("fix_ts")]
```

So **rebuilding the dataset silently deletes all seven `fix_ts` columns.** I confirmed this by rebuilding and inspecting the result, then restored your file from a backup. If you rebuild and immediately launch Phase 2, `prequential_latency` will raise on the missing column (good) — but if any partial `fix_ts` survives, you would get a silent fallback to a degenerate latency model. The correct order is non-negotiable:

```
rebuild dataset  →  build_fix_ts.py --mode real  →  run_phase2_impact.py
```

### 3.5 How to fix

**Step 1 — make the cache self-invalidating.** In `codebase/data/loader.py`, compare the cache mtime against the newest Phase 1 label file and rebuild automatically:

```python
def load_or_build_dataset(force_rebuild: bool = False) -> pd.DataFrame:
    out_csv = PROCESSED_DATA_DIR / "phase2_commits.csv"
    if out_csv.exists() and not force_rebuild:
        newest_label = max(
            (p.stat().st_mtime for p in PHASE1_RESULTS_DIR.glob("*_labels.csv")),
            default=0.0,
        )
        if newest_label > out_csv.stat().st_mtime:
            raise RuntimeError(
                f"{out_csv} is older than results/phase1/*_labels.csv. "
                "Phase 1 labels changed since this cache was built. Rebuild with "
                "load_or_build_dataset(force_rebuild=True), then re-run "
                "scripts/build_fix_ts.py --mode real (the rebuild drops fix_ts)."
            )
        return pd.read_csv(out_csv)
    return build_unified_dataset()
```

Raising rather than silently rebuilding is deliberate — a silent rebuild would drop `fix_ts` and leave you worse off.

**Step 2 — make `build_unified_dataset` preserve `fix_ts`.** Before writing, re-merge any `fix_ts*` columns from the existing CSV on `(project, commit_id)`, or print a loud warning that `build_fix_ts.py` must be re-run. The former is better; the latter is one line.

**Step 3 — add a provenance stamp.** Write a sidecar `data/processed/phase2_commits.provenance.json` recording the SHA-256 of each label file and the git commit at build time, and assert it at the top of `run_phase2_impact.py`. This is the artifact that turns "I fixed it" into "I can prove it stayed fixed," and it is exactly the kind of thing an examiner rewards.

**Step 4 — rebuild, re-link, re-run.** See §8.

### 3.6 What to expect after the re-run

The drift is 1–6.5% of commits and moves every variant in the same direction (more positives, higher recall, higher ρ₀). Predictions:

- **Phase 1 table:** unchanged (it is already the fresh vintage). Only Phase 2 moves.
- **Precision ceiling, asymmetric bifurcation, high inter-variant κ vs low oracle κ:** all qualitative Phase 1 findings are untouched.
- **JITLine BSZZ-over-oracle anomaly:** likely *strengthens*. BSZZ gains 742 positives, so the minority-enrichment effect grows.
- **Self-deception gap:** likely widens slightly for AGSZZ and RASZZ, which gained the most positives (5.7% and 6.5%).
- **ORB oracle vs BSZZ:** genuinely uncertain. The gap is +0.0126 with p = 0.39; a 2.7% relabelling of BSZZ can flip the sign of the mean. **Do not pre-commit to the direction of this result in the meeting.** See §4.

---

## 4. MAJOR — Overstated claims about Oracle vs BSZZ

### 4.1 What the data says

Your own `results/phase2/statistical_tests.csv`, row 25:

```
label_source_gap, ORB, BSZZ, oracle vs BSZZ:
  mean 0.06845 vs 0.05588, diff +0.01257
  p = 0.3926, Cliff's delta = 0.156, magnitude = "small"
```

14/21 project wins at n = 21 is not distinguishable from a coin flip. The mean gap is small and unstable: BSZZ wins hard where it wins (parquet-mr −0.2198, commons-compress −0.1792, commons-digester −0.1150), which is precisely why the signed-rank test comes back at 0.39.

The imputation sensitivity is weaker still. Recomputing from `results/phase2/latency_imputation_summary.csv`:

| Comparison | Wins | Wilcoxon p |
|---|---|---|
| Oracle (as-is) vs BSZZ | 14/21 | 0.3926 |
| Oracle (imputed) vs BSZZ | **12/21** (report says 13/21) | **1.0000** |
| Oracle (as-is) vs Oracle (imputed) | 11/21 | 0.3926 |

### 4.2 What *is* supported

Oracle significantly outperforms every **refined** variant, and four of five survive Holm correction within the six-test label-source family:

| Comparison | Raw p | Holm (m=6) | Cliff's δ |
|---|---|---|---|
| Oracle vs RASZZ | 0.00085 | **0.0051** | 0.483 (large) |
| Oracle vs AGSZZ | 0.0063 | **0.0314** | 0.397 (medium) |
| Oracle vs MASZZ | 0.0101 | **0.0405** | 0.546 (large) |
| Oracle vs RSZZ | 0.0127 | **0.0405** | 0.451 (medium) |
| Oracle vs LSZZ | 0.0263 | 0.0527 (borderline) | 0.397 (medium) |
| Oracle vs BSZZ | 0.3926 | 0.3926 (n.s.) | 0.156 (small) |

That is still a strong, publishable result: **under honest streaming evaluation with real verification latency, label quality demonstrably matters — training on developer-verified ground truth beats every refined SZZ variant.** You lose nothing by excluding BSZZ from that sentence, and you gain a defensible position.

### 4.3 Where to fix the text

Three places in `Phase1_Phase2_Comprehensive_Analysis_and_Supervisor_Pitch.md`:

| Location | Current | Replace with |
|---|---|---|
| Exec. summary, point 4 (line 56) | "Oracle ground truth **conclusively outperforms all noisy SZZ variants** (winning 14 of 21 projects against BSZZ)" | "Oracle ground truth significantly outperforms all five *refined* SZZ variants (p ≤ 0.026, Cliff's δ 0.40–0.55). Against FP-heavy BSZZ the advantage is directionally consistent (14/21 projects, +0.013 MCC) but not statistically distinguishable at n = 21 (p = 0.39)." |
| Finding 2.5 (line 262–267) | "Oracle-trained ORB is the best-performing model … Oracle ORB beats BSZZ ORB in 14 of 21 projects" | Keep the ranking, add: "the gap over BSZZ is within sampling noise; the significant separations are against AGSZZ, MASZZ, LSZZ, RSZZ and RASZZ." |
| Finding 2.7 (line 281) | "The deliverability confound is **strictly bounded and neutralized**." | "The ordering direction survives full latency imputation (0.0602 vs 0.0559, 12/21 projects). Neither the as-is nor the imputed comparison against BSZZ reaches significance, so the deliverability confound is bounded but the BSZZ comparison remains inconclusive in both directions." |
| §5.3 Q1 and Q5 answers | "Oracle wins conclusively" / "The result is robust." | Mirror the above. |

**Why this matters more than it looks.** A supervisor who asks "is that difference significant?" and gets "yes, conclusively" from you, then reads p = 0.3926 in your own CSV, will discount everything else in the document — including the two findings that *are* rock solid at p < 1e-5. Overclaiming a weak result is the fastest way to lose credit for a strong one.

---

## 5. MAJOR — The third rung of the inflation ladder confounds model with regime

### 5.1 The problem

The experiment grid is not fully crossed. From `results/phase2/phase2_results.csv`:

```
JITLine    naive_kfold, chronological          (2,940 each)
LApredict  naive_kfold, chronological          (2,940 each)
ORB        prequential_latency                 (2,940)
```

There is **no cell where any learner crosses the batch/stream boundary.** Yet both ladder diagrams present a single descending chain whose final step swaps the learner:

- Executive summary pipeline (lines 59–84): "−0.035 to −0.100 MCC (Latency Dynamics)" from batch JITLine/LApredict down to ORB.
- §4 Synthesis (lines 289–303): "Layer 3: Online Streaming with Real Verification Latency (Δ = −0.092 MCC)".

That Δ is not a latency effect. It is *latency + a Random Forest replaced by an ensemble of 20 online logistic regressors*, and the two are perfectly confounded.

### 5.2 A second, smaller problem in the same diagram

The §4 ladder switches label source mid-chain. Layer 1 starts at BSZZ-trained JITLine (0.377 self-scored → 0.161 oracle-scored, Δ = −0.216 ✓). Layer 2 then quotes "−0.141 for **Oracle** JITLine". But 0.161 − 0.141 = 0.020, not the 0.103 shown; the correct BSZZ-chain drop is 0.1607 → 0.1309, i.e. −0.030. The diagram reads as one commit's journey down the ladder, but it is three different configurations spliced together.

### 5.3 Two ways to fix, pick one

**Option A (stronger, ~2 hours of work).** Add ORB under the chronological regime: train the online learner sequentially over the first 50% of the stream, freeze it, and batch-predict the second 50%. This gives you the missing cell and turns the confound into a clean two-way decomposition:

```
JITLine  chronological  ──┐
                          ├── learner effect (same regime, different model)
ORB      chronological  ──┘
                          │
                          └── regime effect (same model, different regime)
ORB      prequential_latency
```

Now you can write "of the −0.092 MCC batch→stream drop, X is attributable to the online learner and Y to verification latency" — which is a genuinely novel decomposition and directly serves RQ2. It also gives Phase 4 a batch reference point for Noise-Aware ORB.

**Option B (honest, 20 minutes).** Relabel the rung and drop the single-number Δ: "Step 3 replaces the batch learner with an online ensemble *and* imposes real verification latency; the two effects are not separated in the current design (see Threats to Validity)." Then rebuild the §4 ladder as a single coherent chain — one model, one label source, three regimes — and put the model comparison in a separate figure.

Option A is worth the two hours. Your outline §5.1 already promises "3 models × 5 label sources × 3 evaluation regimes," a full crossing, and the current grid does not deliver it. This is the single most likely thing for an examiner to press on in the Chapter 5 viva.

---

## 6. MODERATE — Methodological issues to fix or document

### 6a. The prequential metric is a terminal value over ~100 commits

`codebase/evaluation/regimes.py:169` returns `tracker.mcc()` — the value of the fading confusion matrix at the *end* of the stream. With `PREQUENTIAL_FADING = 0.99`, the sum of weights converges to 1/(1−0.99) = **100**. So every ORB number in your report is computed on an effective sample of roughly the last 100 commits of each project, containing about 8.5 expected positives at an 8.5% defect rate.

Three consequences:

1. **High variance by construction.** Across-project σ of the ORB oracle mean is 0.073; within-project σ across 10 seeds is 0.026. The 21-project mean of 0.0685 has SE ≈ 0.016 — comfortably non-zero, but individual project values (−0.090 to +0.178) are near-noise.
2. **It is not what Cabral et al. report.** The fading-factor prequential protocol (Gama et al.) is normally presented as a *trajectory*, with the summary being the average of the metric over the stream. Reporting only the endpoint is a different estimator and needs to be named as such.
3. **The inflation ladder compares unlike quantities.** Rungs 1–2 are full-sample batch MCC over ~50% of a project; rung 3 is a 100-commit terminal fading MCC. Placing them on one axis with a subtraction between them is apples-to-oranges.

**Fix (~1 hour).** `PrequentialTracker.history` already records `mcc` and `gmean` at every step — you are throwing it away. Persist it and report the time-averaged prequential metric alongside the terminal one:

```python
hist = r_preq_orb["history"]
records.append({
    ...,
    "mcc": r_preq_orb["mcc"],                                   # terminal (as now)
    "mcc_prequential_avg": float(np.mean([h["mcc"] for h in hist])),
    "gmean_prequential_avg": float(np.mean([h["gmean"] for h in hist])),
})
```

Report the time-averaged value as primary (it is the standard estimator and far more stable), keep the terminal value as a secondary column, and state the fading factor and its effective window size in the methods chapter. As a bonus, the trajectory gives you a free figure — per-class recall over time — which is exactly what outline §6.1 asks Phase 3 to produce.

### 6b. No multiple-comparison correction

Outline §3.4 explicitly promises "Wilcoxon + Cliff's delta, multiple-comparison correction." `statistical_tests.csv` contains 30 tests with raw p-values only.

The good news is that correcting costs you almost nothing. Applying Holm **within each test family** (the defensible choice — the three families answer different questions):

- **Regime inflation (m = 6):** JITLine oracle survives at 1.7e-05; JITLine RSZZ at 0.036. The four LApredict/BSZZ rows were never significant anyway.
- **Self-deception (m = 18):** all five "large" naive-k-fold rows survive comfortably.
- **Label source (m = 6):** four of six survive; LSZZ lands at 0.053, BSZZ at 0.39. See §4.2.

Add `p_holm` and `p_bh` columns to `compute_statistical_tests()` and state the family definition in the methods chapter. Twelve lines of code, and it closes an explicit promise in your own outline.

### 6c. Self-deception tests pool two models and are described as "21 projects"

`experiments/run_phase2_impact.py:214` pivots on `["project", "model"]`:

```python
pivot = sub.pivot_table(index=["project", "model"], columns="eval_mode", values="mcc")
```

For `naive_kfold` and `chronological` this yields **42 rows** (21 projects × {JITLine, LApredict}), not 21. Two consequences:

1. JITLine and LApredict on the same project are treated as independent observations. They are not — they share the project, the labels, the features and the split.
2. The report (line 214) says "Paired Wilcoxon signed-rank tests across 21 projects." That is true for the regime-inflation and label-source families, false for self-deception. It is also detectable from the p-values: p = 6.54e-08 is below the floor achievable by an exact signed-rank test at n = 21 (2/2²¹ ≈ 9.5e-07), which tells the reader n > 25 and the normal approximation was used.

**Fix.** Either report the self-deception gap per model (two rows, n = 21 each — cleanest), or keep the pooled test and change the caption to "42 project × model pairs; note that the two models on a given project are not independent." The former is better and the effect is large enough to survive either way.

### 6d. JITLine's threshold protocol is unstable and not principled

`codebase/models/baselines.py:141-149` does this:

1. Fit the RF on the first 80% of the training split.
2. Tune the decision threshold for best G-mean on the last 20%.
3. **Refit the RF on 100% of the training split** — including the tuning tail.
4. Keep the threshold from step 2, applied to the model from step 3.

Step 4 applies a threshold calibrated against one model to a differently-calibrated model. I measured the shift on six projects:

| Project | Frozen threshold (in use) | Post-refit in-sample optimum | Test-set predicted-positive rate | JITLine MCC | LApredict MCC |
|---|---|---|---|---|---|
| commons-math | 0.30 | 0.68 | 18.6% | 0.202 | 0.203 |
| ant-ivy | 0.33 | 0.67 | 43.7% | 0.165 | 0.229 |
| commons-lang | 0.12 | 0.71 | 48.3% | 0.062 | 0.079 |
| commons-configuration | 0.34 | 0.66 | **1.4%** | 0.084 | 0.100 |
| commons-compress | 0.39 | 0.73 | 23.1% | 0.158 | 0.124 |
| opennlp | 0.09 | 0.76 | **68.5%** | 0.021 | 0.163 |

The refit shifts the optimal operating point by roughly 0.35 in probability. The frozen threshold happens to work *better* than re-tuning post-refit (which overfits in-sample and collapses to MCC ≈ 0), so the current code is accidentally reasonable — but the resulting predicted-positive rate swings from 1.4% to 68.5% across projects, which is why JITLine's chronological G-mean (0.458–0.540) still sits **below** a single-feature logistic regression (0.607–0.698).

That last fact is the one a supervisor will notice: *a 14-feature Random Forest with SMOTE and threshold moving is being beaten on both MCC and G-mean by logistic regression on `la` alone.* You need an answer better than "noise."

**Fix (~2 hours).** Tune the threshold on out-of-bag probabilities from the RF fit on the *full* training split (`RandomForestClassifier(oob_score=True)`, then `rf.oob_decision_function_[:, 1]`). This removes the fit/refit mismatch entirely, uses all training data for both purposes, and remains leakage-free. Also record the chosen threshold per run and report its variance in the appendix — that table *is* the evidence for your "threshold artifact" decomposition in Finding 2.3, and right now you assert the decomposition without showing it.

Note the validation tails are tiny: with 544–4,026 commits per project, a 50% training split and a 20% tail means the threshold is sometimes chosen on fewer than 10 positive examples. Say so.

### 6e. The oracle's `fix_ts` is built from SZZ mappings

`scripts/build_fix_ts.py:150`:

```python
union = mapping.groupby(["project", "commit_id"])["fix_ts"].min().rename("fix_ts")
```

`fix_ts` (the column `prequential_latency` falls back to for `label_oracle`, since no `fix_ts_oracle` exists) is the union over *all six SZZ variants'* fix→inducing mappings. So an oracle-defective commit receives a label-arrival time only if some SZZ variant happened to link it to a fix, and the arrival date is that variant's fix date.

Your imputation experiment addresses the **coverage** half of this (67.8% → 100%). It does not address the **timing** half: for the 67.8% that are linked, the arrival date still comes from an SZZ link, which for a mislinked commit is the wrong fix and hence the wrong date. This is an SZZ-derived construct sitting inside the condition you present as SZZ-free.

**Fix.** This is a disclosure item, not a code fix, unless you can obtain JIT-Defects4J's own fix→inducing linkage (which would resolve it properly and is worth an hour of looking). At minimum, add a paragraph in Chapter 5 methods and a line in Threats to Validity. Note that the direction of the bias is not obviously favourable to you, so disclosing it costs nothing and pre-empts the question.

Measured for the record:

| Label source | fix_ts coverage among its positives | Median latency | Share arriving after W=90d |
|---|---|---|---|
| oracle | 67.8% | 109.4 d | 52.8% |
| BSZZ | 100.0% | 95.0 d | 50.8% |
| AGSZZ | 98.4% | 87.9 d | 49.7% |
| MASZZ | 99.1% | 91.9 d | 50.2% |
| LSZZ | 97.0% | 62.6 d | 47.3% |
| RSZZ | 98.1% | 24.7 d | 38.0% |
| RASZZ | 95.6% | 73.7 d | 47.9% |

The RSZZ row is interesting in its own right and worth a sentence: RSZZ's median latency is 24.7 days against BSZZ's 95, because restricting to the single most-likely inducing commit preferentially keeps recently-touched lines. Label *quality* and label *timeliness* are correlated across variants — a finding you have measured but not reported.

### 6f. Unweighted project means over very heterogeneous projects

Every reported figure is an unweighted mean over 21 projects. Those projects are not comparable:

| Project | Commits | Oracle positives | Rate | Positives in chronological training half |
|---|---|---|---|---|
| commons-digester | 1,079 | 19 | 1.8% | **5** |
| commons-validator | 598 | 36 | 6.0% | **11** |
| commons-collections | 1,823 | 50 | 2.7% | 19 |
| commons-beanutils | 611 | 37 | 6.1% | 23 |
| … | | | | |
| ant-ivy | 1,771 | 332 | 18.7% | 218 |
| giraph | 844 | 163 | 19.3% | 110 |
| commons-math | 4,026 | 335 | 8.3% | 196 |

commons-digester trains on **five** positive examples and then contributes equally to the grand mean as commons-math's 196. Degenerate (exactly zero) MCC occurs in 4.9% of JITLine chronological runs.

**Fix.** Report the per-project N table in the appendix (outline back matter already plans for it). Add one robustness check: re-run the headline comparisons excluding projects below a positive-count floor (say 20 in the training half — this drops commons-digester and commons-validator) and state whether conclusions change. If they do not, you have strengthened the result for free; if they do, you needed to know.

---

## 7. MINOR — Numeric corrections to the pitch document

| # | Location | Claim | Correct value |
|---|---|---|---|
| 1 | Exec. summary line 56; Finding 2.6 line 272; §5.2 Stage 3 | "median 113 days, 53% arriving after W=90 days" | 113 d / 53.0% is over **all 8,819 commits with any union `fix_ts`**. For the oracle-defective stream it is **109.4 d / 52.8%**. Say which population; both are fine, but the report attributes the figure to the oracle stream. |
| 2 | Finding 2.3 line 256; §5.3 Q2 | "BSZZ … flags 29.7% of commits as positive" | Wrong under either vintage. **26.8%** in the labels Phase 2 used (7,318/27,319); **29.5%** under the current Phase 1 labels (8,060/27,319). Recompute after the re-run. |
| 3 | Exec. summary line 53 | "Between **72.8% and 81.5%** … are false alarms" | Finding 1.1 (line 131) says 81.7%, which is correct: 1 − 0.1826 (MASZZ, lowest precision) = 81.74%. Fix the exec. summary. |
| 4 | Finding 2.7 line 279; §5.3 Q5 | "Oracle (Imputed) … Wins vs BSZZ: **13/21**" | **12/21**, recomputed from `latency_imputation_summary.csv`. |
| 5 | Header line 6; §5.2 Stage 1 | "14,700 Total Runs" | Correct as a row count, but includes **1,050 exact duplicates**: for `train_label=oracle`, the `oracle`-scored and `self`-scored cells are identical by construction (`eval_label = label_oracle` either way). 13,650 distinct configurations. Either say "14,700 evaluation records (13,650 distinct configurations)" or drop the duplicate cells and halve that ORB compute. |
| 6 | §2.1, §5.3 Q1 | ORB replication used to defend the low absolute scores | The 14 Cabral datasets have defect ratios of **0.22–0.43**; your corpus is **0.085**. The replication validates the implementation, but at a very different imbalance regime. State that before someone else does — it is a strength when you raise it yourself and a wound when they do. |
| 7 | README | Command list | `experiments/run_latency_imputation_sensitivity.py` exists and produced a reported result, but is absent from the README's execution commands. Add it as Step 3b. |

---

## 8. Remediation plan — ordered, with commands

### Phase A — Restore label consistency (must complete before anything else)

```bash
cd /home/afler/Documents/thesis-later
source venv/bin/activate

# A1. Back up the current dataset (it holds the only copy of the fix_ts columns).
cp data/processed/phase2_commits.csv data/processed/phase2_commits.PRE_AUDIT.csv

# A2. Confirm the Phase 1 table is the fresh vintage (should print BSZZ 8060 flagged).
python -m experiments.evaluate_confusion_matrix

# A3. Rebuild the dataset from the CURRENT label files. NOTE: this DROPS fix_ts.
python -c "from codebase.data.loader import build_unified_dataset; build_unified_dataset()"

# A4. Re-link verification latency. Non-optional after A3.
python scripts/build_fix_ts.py --mode real

# A5. Verify: BSZZ positives must now be 8060, and all 7 fix_ts columns present.
python -c "
import pandas as pd
d = pd.read_csv('data/processed/phase2_commits.csv')
print('rows', len(d))
print('BSZZ pos', d.label_BSZZ.sum(), '(expect 8060)')
print('fix_ts cols', [c for c in d.columns if c.startswith('fix_ts')])
assert d.label_BSZZ.sum() == 8060
assert 'fix_ts' in d.columns and d.fix_ts.notna().sum() > 0
print('OK')
"
```

Then apply the code changes from §3.5 (loader guard, `fix_ts` preservation, provenance sidecar) and commit them **before** re-running, so the re-run is covered by the guard.

### Phase B — Apply the method fixes (do them now, so you re-run once, not twice)

| Fix | File | Effort |
|---|---|---|
| Persist prequential trajectory + time-averaged metric (§6a) | `codebase/evaluation/regimes.py`, `experiments/run_phase2_impact.py` | ~1 h |
| Holm + BH columns in the stats table (§6b) | `experiments/run_phase2_impact.py::compute_statistical_tests` | ~30 min |
| Self-deception test per model, not pooled (§6c) | same function | ~30 min |
| OOB-based threshold tuning; record threshold per run (§6d) | `codebase/models/baselines.py` | ~2 h |
| ORB under chronological regime (§5.3 Option A) | `codebase/evaluation/regimes.py`, runner | ~2 h |
| Drop the duplicated `eval_mode` cells for `train_label=oracle` (§7 item 5) | runner | ~20 min |

### Phase C — Re-run and regenerate

```bash
python -m experiments.run_phase2_impact --latency_mode real --n_jobs 8
python -m experiments.run_latency_imputation_sensitivity
python scripts/generate_report.py
```

Budget the same wall-clock as your last full run. Run the imputation sensitivity in the same session so both use the same label vintage — a mismatch there was part of how this bug hid.

### Phase D — Rewrite the reports

Work through §4.3 and §7 mechanically. Then regenerate every number in the pitch document from the new CSVs rather than editing the old figures by hand — hand-editing is what produced the 29.7% / 13-of-21 / 81.5% discrepancies in the first place. Consider making `generate_report.py` emit the pitch document's tables directly so the numbers can never drift from their source again.

### Phase E — Verify before the meeting

```bash
# Phase 1 and Phase 2 must now agree on the labels. This should print ~0 for every variant.
python -c "
import pandas as pd, glob, json
from pathlib import Path
gt = pd.read_csv('data/raw/jit_ground_truth.csv')
p2 = pd.read_csv('data/processed/phase2_commits.csv')
bias = json.load(open('phase1_bias.json'))
for v in ['BSZZ','AGSZZ','MASZZ','LSZZ','RSZZ','RASZZ']:
    o, s = p2.label_oracle.values, p2[f'label_{v}'].values
    tp = int(((s==1)&(o==1)).sum()); fp = int(((s==1)&(o==0)).sum())
    fn = int(((s==0)&(o==1)).sum()); tn = int(((s==0)&(o==0)).sum())
    b = bias[v]
    print(f'{v:6s} drift TP={tp-b[\"TP\"]:+4d} FP={fp-b[\"FP\"]:+4d} FN={fn-b[\"FN\"]:+4d} TN={tn-b[\"TN\"]:+4d}')
"
```

Put this in CI. It is a three-line assertion that would have caught the blocker on the day it was introduced.

---

## 9. Revised claims you can defend after the re-run

Numbers below will shift slightly; the structure will not.

**Tier 1 — bulletproof (survive Holm across all 30 tests):**
1. Random k-fold cross-validation inflates JITLine's measured MCC by +0.14 over chronological evaluation (Holm p = 8e-05, δ = 0.74, large).
2. Self-scoring on SZZ labels inflates apparent performance by +0.18 MCC for BSZZ (Holm p = 2e-06, δ = 0.81, large), and the gap persists under chronological evaluation (+0.097, Holm p = 1.8e-04).
3. SZZ variants agree strongly with each other (κ up to 0.933) and poorly with developer-verified ground truth (κ = 0.158–0.202).
4. No SZZ variant exceeds 27.2% precision; noise is asymmetric and variant-dependent, spanning ρ₀ ∈ [6.7%, 26.3%] and ρ₁ ∈ [35.9%, 73.3%].

**Tier 2 — solid with correct framing:**
5. Under honest streaming evaluation with real verification latency, oracle labels significantly outperform all five refined SZZ variants (Holm p ≤ 0.041 for four of five). The advantage over FP-heavy BSZZ is directionally consistent but not significant at n = 21.
6. FP-heavy labels act as accidental minority augmentation for batch learners: BSZZ-trained JITLine beats oracle-trained JITLine in 13/21 projects, and the effect survives correction for the decision-threshold artifact.
7. Verification latency imposes severe FN-like noise on *every* label source — over half of defect labels arrive after W = 90 days — compressing the measurable difference between clean and noisy training labels in the online regime.

**Tier 3 — report as observations, not conclusions:**
8. Absolute deployable MCC under realistic conditions is ~0.07 on this benchmark. (Note the caveat in §6a about which estimator this is.)
9. Low-capacity models are more noise-robust than high-capacity ones (LApredict's chronological MCC varies by only 0.015 across all seven label sources).

Finding 7 is arguably your most novel result and it is currently buried at §3.4 Finding 2.6. Consider promoting it: *"we show that verification latency and label noise are not additive — latency partially masks label-quality differences, which means every prior evaluation that ignored latency also mis-estimated the cost of label noise."* That is a Chapter 5 headline, and it sets up Phase 3 perfectly.

---

## 10. How to frame this to your supervisor

Do not hide the blocker, and do not lead with it. Lead with what it demonstrates.

> "Before this meeting I ran a consistency audit across the whole pipeline and found that my Phase 2 dataset cache had gone stale relative to my Phase 1 label regeneration — Phase 2 trained on labels one commit older than the noise rates I was reporting, affecting 1–6.5% of commits per variant. I traced the root cause to an unguarded cache in the loader, I have a fix and a CI assertion for it, and I am re-running. The qualitative findings are unaffected. I'm flagging it because it is a live instance of exactly the phenomenon my thesis studies: label provenance is fragile, and pipelines silently desynchronize unless you assert on it."

That reframing is not spin. A thesis on label-noise provenance that ships a provenance assertion in CI is a stronger artifact than one that never had the bug.

Then be straight about the two claims you are walking back (Oracle vs BSZZ significance; the ladder's third rung) and explain what you are doing about each. Supervisors trust students who bring them corrections more than students who bring them only good news, and the corrections here are cheap — you lose one non-significant comparison and gain a cleaner decomposition.

---

## 11. Implications for Phase 3 and Phase 4

**Do not start Phase 3 until Phase A is complete.** `phase1_bias.json` is the direct input to the noise injection (outline §4.3, §6.1). Injecting ρ₀ = 0.2627 to simulate BSZZ while your real BSZZ condition carries ρ₀ = 0.2364 would make the synthetic and real arms non-comparable — and the whole point of Phase 3 is to compare them.

**The `mid` calibration point needs rechecking.** §6.1 of the pitch document calibrates `mid` to RASZZ (ρ₀ = 0.1813, ρ₁ = 0.5617). RASZZ has the largest label drift of any variant (6.47%), so this parameter will move the most. Re-read it from the regenerated JSON rather than copying from the current document.

**The self-filtering trap (Code Review v2, item 3b) is real and confirmed by my measurements.** Only 67.8% of oracle-defective commits have a `fix_ts`, and clean commits are unlinked at an even higher rate. Under `latency_mode="real"`, a clean commit flipped to "defective" by synthetic FP injection mostly has no `fix_ts`, so its poisoned label never reaches training and the injected noise silently self-filters. Your two-arm design (uniform-latency primary arm for mechanics, real-latency secondary arm with imputed timestamps for realism) handles this correctly — keep it, and state the reasoning explicitly in Chapter 6 methods. It is a non-obvious interaction between your two noise sources and it will read as sophistication.

**Phase 4's design premise needs a check against §6a.** The rescue path is motivated by "missing and delayed labels (FN noise) dominate false alarms (FP noise)." That conclusion currently rests on ORB numbers computed as terminal 100-commit fading statistics. Recompute the FN-vs-FP dominance from the time-averaged prequential trajectory before you commit to the architecture — if the dominance is an artifact of where in the stream you sample, you would rather find out now than after building the algorithm around it.

**One design opportunity.** The trajectory data from §6a gives you ORB's per-class recall over time for free, which outline §6.1 lists as a required Phase 3 deliverable ("λ trajectory, boost factor over time, per-class recall trajectories"). `ORB.trace` already records `boost`, `lam`, `ma_pred` and `rate1` per learning step and is likewise discarded. Persisting both is perhaps 20 lines and it front-loads a chunk of Chapter 6.

---

## 12. Appendix — verification commands

Every claim in this document is reproducible with the following. Run from the repo root with the venv active.

**Label vintage mismatch (§3):**
```bash
python - <<'EOF'
import pandas as pd, glob
from pathlib import Path
gt = pd.read_csv("data/raw/jit_ground_truth.csv")
p2 = pd.read_csv("data/processed/phase2_commits.csv")
for v in ["BSZZ","AGSZZ","MASZZ","LSZZ","RSZZ","RASZZ"]:
    col = f"label_{v}"
    frames = []
    for f in glob.glob(f"results/phase1/{v.lower()}_*_labels.csv"):
        d = pd.read_csv(f)
        d["project"] = Path(f).stem.replace(f"{v.lower()}_","").replace("_labels","")
        frames.append(d)
    pred = pd.concat(frames, ignore_index=True)
    pred[col] = pred[col].fillna(0).astype(int)
    pred = pred.drop_duplicates(subset=["project","commit_id"])
    m = gt.merge(pred[["project","commit_id",col]], on=["project","commit_id"], how="left")
    m[col] = m[col].fillna(0).astype(int)
    print(f"{v:6s} current_phase1={int(m[col].sum()):5d}  used_by_phase2={int(p2[col].sum()):5d}")
EOF
```

**Oracle vs BSZZ significance (§4):**
```bash
python -c "
import pandas as pd
s = pd.read_csv('results/phase2/statistical_tests.csv')
print(s[s.comparison_type=='label_source_gap'][['train_label','mean_A','mean_B','p_value','cliffs_delta','magnitude']].to_string(index=False))
"
```

**Imputation win count (§4.1):**
```bash
python -c "
import pandas as pd; from scipy import stats
s = pd.read_csv('results/phase2/latency_imputation_summary.csv')
for a,b in [('oracle_asis_mcc','bszz_mcc'),('oracle_imp_mcc','bszz_mcc')]:
    print(a,'vs',b,'wins',int((s[a]>s[b]).sum()),'/',len(s),'p=%.4f'%stats.wilcoxon(s[a],s[b]).pvalue)
"
```

**Grid crossing (§5.1):**
```bash
python -c "
import pandas as pd
print(pd.read_csv('results/phase2/phase2_results.csv').groupby(['model','regime']).size())
"
```

**Latency coverage and medians (§6e):**
```bash
python - <<'EOF'
import pandas as pd
d = pd.read_csv("data/processed/phase2_commits.csv")
for v in ["oracle","BSZZ","AGSZZ","MASZZ","LSZZ","RSZZ","RASZZ"]:
    lab = "label_oracle" if v=="oracle" else f"label_{v}"
    col = "fix_ts" if v=="oracle" else f"fix_ts_{v}"
    pos = d[d[lab]==1]
    lat = ((pos[col]-pos.author_ts)/86400).dropna()
    print(f"{v:7s} cov={pos[col].notna().mean():7.3%} median={lat.median():7.1f}d >90d={(lat>90).mean():7.3%}")
EOF
```

**Per-project sizes (§6f):**
```bash
python -c "
import pandas as pd
d = pd.read_csv('data/processed/phase2_commits.csv')
g = d.groupby('project').agg(n=('label_oracle','size'), pos=('label_oracle','sum'))
g['rate'] = (g.pos/g.n).round(3)
print(g.sort_values('n').to_string())
"
```

---

*Audit performed against the working tree at `31c41a4`. The dataset was rebuilt once for the §3 diff and restored byte-identical; no experimental artifact was modified.*

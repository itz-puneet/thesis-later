# Independent Audit of Phases 1 & 2 — Findings, Fixes, and Remaining Work

**Audit date:** 2026-09-03. **Remediation completed:** 2026-09-04.
**Original scope:** working tree at `master` @ `31c41a4`, plus the label-file history back to `88b4eb2`.
**Current scope:** `master` @ `830eb48` — dataset rebuilt from current labels, Phase B method fixes applied, full 10-seed/100-tree Phase 2 grid re-run (16,380 records), pushed.
**Method:** every headline number was recomputed from the committed artifacts (`results/phase1/`, `results/phase2/`, `data/processed/phase2_commits.csv`, `phase1_bias.json`), not read from the reports. Where reports and artifacts disagreed, the artifacts won. All fixes below were tested locally, then validated end-to-end on a GitHub Actions runner (smoke stage) before being spent on a full run.

This document originally described only what was wrong. It now also describes what was done about it and what is still open — read §0 for the state of play, then the rest for the detail behind it.

---

## 0. State of play — read this first

| | |
|---|---|
| **Fixed and verified in CI** | Stale-label blocker (§1), heavy-pipeline-on-a-laptop problem (§1.4), batch/stream confound (§2), prequential terminal-vs-averaged estimator (§3a), no multiplicity correction (§3b), pooled self-deception tests (§3c), unstable JITLine threshold (§3d), duplicate result rows (§3f) |
| **Fixed as disclosure only (no code change needed)** | Oracle-vs-BSZZ overclaim (§4) — now has the correct language ready to paste in |
| **Not yet done — still needs your attention** | `fix_ts` SZZ-inside-SZZM-free construct (§5a, disclosure), unweighted project means / robustness check (§5b), rewriting the two report documents to match the new numbers (§6), Phase 3 parameterization from the *new* `phase1_bias.json`, which happens to be numerically unchanged but must be re-read, not assumed (§7) |

**The single most important fact:** `phase1_bias.json` did not change. It was already the fresh label vintage before this remediation started — only `data/processed/phase2_commits.csv` was stale. So every Phase 1 number in your existing documents is still correct. Every Phase 2 number needs replacing with the values in §2–§3 below.

**Verification, right now, reproduces clean:**
```
$ python -m experiments.check_label_consistency
...
PASS: Phase 1 noise rates describe exactly the labels Phase 2 trains on.
fix_ts: 7 columns, 8819 commits linked, median latency 113d, 53.0% arrive after W=90d
```
This assertion now runs automatically in CI, before any experiment compute is spent (`.github/workflows/phase2_experiment.yml`, step "GATE — Phase 1 / Phase 2 label consistency"). It cannot silently regress again.

---

## Table of Contents

1. [What was found: the stale-label blocker, and how it was fixed](#1-what-was-found-the-stale-label-blocker-and-how-it-was-fixed)
2. [What was found: the ladder's third rung confounded model with regime — fixed](#2-what-was-found-the-ladders-third-rung-confounded-model-with-regime--fixed)
3. [What was found: six methodological gaps — all fixed](#3-what-was-found-six-methodological-gaps--all-fixed)
4. [What was found: an overstated claim — resolved by disclosure](#4-what-was-found-an-overstated-claim--resolved-by-disclosure)
5. [What remains open](#5-what-remains-open)
6. [What you still need to do](#6-what-you-still-need-to-do)
7. [Implications for Phase 3 and Phase 4](#7-implications-for-phase-3-and-phase-4)
8. [Current headline numbers — the ones to actually cite](#8-current-headline-numbers--the-ones-to-actually-cite)
9. [What was verified correct from the start](#9-what-was-verified-correct-from-the-start)
10. [Appendix — how to reproduce every number in this document](#10-appendix--how-to-reproduce-every-number-in-this-document)

---

## 1. What was found: the stale-label blocker, and how it was fixed

### 1.1 What was found

`data/processed/phase2_commits.csv` — the single file every Phase 2 model reads — carried SZZ label columns from commit `975302a` (2026-08-23), **one commit before** the Phase 1 label regeneration in `22acb13` (2026-08-31 10:19). `phase1_bias.json` was regenerated from the *new* labels in `93c3fcf` (10:36). Phase 2 then ran at `9634ee4` (14:30 IST) against the old ones.

Rebuilding the dataset from the current label files and diffing against the file Phase 2 had actually used:

| Variant | Positives Phase 2 trained on | Positives in Phase 1's labels | Commits relabelled |
|---|---|---|---|
| BSZZ | 7,318 | 8,060 | 742 (2.72%) |
| AGSZZ | 4,474 | 5,876 | 1,546 (5.66%) |
| MASZZ | 5,394 | 6,154 | 860 (3.15%) |
| LSZZ | 2,130 | 2,287 | 285 (1.04%) |
| RSZZ | 2,699 | 3,015 | 420 (1.54%) |
| RASZZ | 4,153 | 5,553 | 1,768 (6.47%) |

**Root cause, two mechanisms compounding:**
1. `load_or_build_dataset()` returned the cached CSV unconditionally — nothing compared its mtime against `results/phase1/*_labels.csv`.
2. `scripts/build_fix_ts.py` read the stale CSV, added `fix_ts` columns, and wrote it back — refreshing the mtime to *after* the Phase 1 regeneration, so the file looked current to any timestamp check. This is very likely why the earlier code review verified `fix_ts` was present and never questioned the labels beside it.

**A trap discovered while fixing it:** `build_unified_dataset()` selected `fix_ts` columns off the JIT-Fine feature source, which has none. A naive rebuild silently deleted all seven `fix_ts` columns. Confirmed by rebuilding and inspecting the result before any permanent fix existed.

### 1.2 What was fixed

All in `codebase/data/loader.py`, `scripts/build_fix_ts.py`, and a new `experiments/check_label_consistency.py`:

- **`load_or_build_dataset()` now raises** if the cached dataset predates the newest `results/phase1/*_labels.csv` file, instead of silently serving stale data. Tested: touching a label file and calling it raises with the exact remediation steps in the message; a correct rebuild clears it.
- **`build_unified_dataset()` now carries `fix_ts*` columns forward** from the previous build by re-merging on `(project, commit_id)`, and prints a loud warning if none are found to carry.
- **A provenance sidecar** (`data/processed/phase2_commits.provenance.json`) now records the SHA-256 of every Phase 1 label file, the positive count per variant, and the git commit at build time.
- **`experiments/check_label_consistency.py`** (new) recomputes the confusion matrix directly from `phase2_commits.csv` and asserts it matches `phase1_bias.json` cell-by-cell for all six variants. Verified against the *stale* dataset before the fix: it failed 6/6 variants, with deltas from −24 to −1,273 flagged commits. Verified against the corrected dataset: passes 6/6.
- This check now runs as a **CI gate** before any Phase 2 compute — see §1.4.

### 1.3 The two 101 MB / 830 MB inputs, replaced

The rebuild needs the 101 MB JIT-Fine zip (for features) and normally needs 830 MB of cloned Apache repos (for `fix_ts` reconstruction via `git log`). Neither is available on a CI runner, and the 101 MB zip decompression was what froze the local laptop mid-audit (7.1 GB RAM, zero swap).

Both were replaced with small, committed, one-time-extracted artifacts:

| Bulky input | Replaced by | Size | Verified |
|---|---|---|---|
| `data/raw/JIT-Fine-replication.zip` (101 MB) | `data/processed/phase2_features.csv` | 4.18 MB | Byte-identical to the live dataset across all 16 feature columns |
| 830 MB of cloned repos | `data/raw/fix_commit_dates.csv` | 0.37 MB | Reproduces `fix_ts` exactly: 8,819 linked, median 113d, 53.0% > 90d |

Extraction (`scripts/extract_base_features.py`) streams the inner zip to a temp file and releases each split before loading the next, rather than holding two full in-memory copies — this is what let it run under a 2 GB memory cap where the old path peaked near 1 GB.

### 1.4 CI now runs the entire chain

`.github/workflows/phase2_experiment.yml` was rewritten from "run Phase 2 against whatever's committed" to the full chain: Phase 1 evaluation → dataset rebuild → `fix_ts` reconstruction → **gate** → Phase 2 grid → imputation sensitivity → reports → push. The gate sits before the expensive steps, so a label mismatch now costs ~1 minute of CI time instead of 2+ hours.

**Validated on GitHub Actions, not just locally** — three runs:

| Run | Stage | Result | Notes |
|---|---|---|---|
| `33788560377` | smoke | ✅ success (14 min) | First proof the chain works with no zip/repos on the runner |
| `33791065056` | full | Data chain ✅, **push ❌** | Every experiment succeeded; push failed on a workflow bug (see below) |
| `33802621822` | smoke | ✅ success | Re-validated after Phase B changes, before spending a second full run |
| `33806126870` | full | ✅ success, **including push** (4.8 h) | Current `master` state |

**One bug found and fixed in the workflow itself:** `scripts/generate_report.py` writes each figure to *both* `reports/figures/` and `manuscript/figures/`, but the commit step only staged `reports/`. Eight tracked PNGs were left modified-but-unstaged, and `git pull --rebase` refused to run against a dirty tree — so a fully successful 2h13m compute run never reached `master`. Results were recovered from the run's uploaded artifact (not lost), the workflow was fixed (stage `manuscript/` too, add `--autostash` as a second line of defence), and the corrected results were committed with provenance noting they were recovered from run `33791065056`. The next full run (`33806126870`) exercised the fixed push path successfully.

### 1.5 What actually happened to the numbers

Prediction from the original audit: *"the drift is 1–6.5% of commits... JITLine BSZZ-over-oracle anomaly likely strengthens... ORB oracle vs BSZZ is genuinely uncertain, do not pre-commit to the direction."* All three predictions were correct — see §8 for the actual after-numbers.

---

## 2. What was found: the ladder's third rung confounded model with regime — fixed

### 2.1 What was found

LApredict/JITLine ran only under `naive_kfold` + `chronological`; ORB ran only under `prequential_latency`. No learner crossed the batch/stream boundary, so the reported "latency" drop in the inflation ladder was actually *latency + swapping a Random Forest for an online ensemble*, perfectly confounded.

### 2.2 What was fixed

Added `chronological_online()` to `codebase/evaluation/regimes.py`: it holds ORB's architecture fixed while changing only the regime — learn the first 50% of the stream sequentially (no verification latency), freeze, batch-predict the second 50%. This is the missing grid cell. Two new statistical-test families in `experiments/run_phase2_impact.py` — `regime_effect_model_fixed` and `learner_effect_regime_fixed` — decompose the drop.

### 2.3 What the decomposition actually shows (10 seeds, full run, oracle labels)

| | MCC |
|---|---|
| LApredict chronological (batch LR) | 0.1734 |
| JITLine chronological (batch RF) | 0.1027 |
| **ORB chronological_online** ← the new cell | **0.0777** |
| ORB prequential_latency | 0.0685 |

| Effect | Δ MCC | p | Holm | Magnitude |
|---|---|---|---|---|
| **Learner** (LApredict → ORB, regime fixed) | **+0.0957** | 0.0001 | **0.0004** | **large** |
| **Regime/latency** (ORB fixed, chrono → prequential) | +0.0093 | **0.8382** | 0.8382 | **negligible** |

**The finding inverts the original framing.** The ladder attributed the entire 0.1050 batch→stream MCC drop to "verification latency." The decomposition shows latency accounts for **~9%** of it and is statistically indistinguishable from zero once the learner is held fixed. The rest — ~91% — is the learner swap (batch Random Forest / logistic regression → 20-member online logistic ensemble).

This is a stronger, more defensible claim than the one it replaces: *once the learner architecture is held constant, verification latency does not measurably degrade MCC on this corpus.* It also changes what Chapter 5 should say about "the cost of latency" — that cost is real for the *variant-compression* finding (§8, Finding 7) but not for the *absolute MCC drop* the ladder previously implied.

For BSZZ labels the pattern is similar but noisier: learner effect +0.0867 (p=0.0011, Holm-significant), regime effect +0.0200 (p=0.4857, n.s.).

---

## 3. What was found: six methodological gaps — all fixed

### 3a. Prequential metric was a terminal value over an effective ~100-commit window — fixed

**Found:** `PrequentialTracker.mcc()` returned the fading confusion matrix's value at the *end* of the stream. With `fading=0.99`, weights sum to 1/(1−0.99) = 100, so every ORB number was computed on roughly the last 100 commits per project (~8.5 expected positives). This is a different, far noisier estimator than the trajectory-average that Gama et al.'s prequential protocol normally reports.

**Fixed:** `prequential_latency()` now also returns `mcc_avg` / `gmean_avg` — the mean of the tracker's full trajectory — alongside the terminal value, and `effective_window`. Both are persisted per run.

**What changed, full run, 10 seeds, oracle-scored:**

| Label | Terminal MCC | Time-averaged MCC |
|---|---|---|
| oracle | 0.0685 | **0.0970** (+42%) |
| BSZZ | 0.0566 | 0.0578 |
| MASZZ | **−0.0030** | **+0.0353** |
| AGSZZ | 0.0125 | 0.0365 |
| LSZZ | 0.0209 | 0.0582 |
| RSZZ | 0.0104 | 0.0315 |
| RASZZ | 0.0184 | 0.0395 |

Spread halved: terminal sd 0.0985 → averaged sd 0.0534. **MASZZ's negative MCC — previously the one label source that looked actively harmful — disappears under the correct estimator.** Rank ordering is essentially unchanged (oracle still 1st, MASZZ still last), so the qualitative story survives, but the "0.0685 deployable MCC" headline figure should become ~0.097.

### 3b. No multiple-comparison correction — fixed

**Found:** outline §3.4 promised Holm correction; `statistical_tests.csv` had 30+ raw p-values with none applied.

**Fixed:** `add_multiplicity_correction()` in `experiments/run_phase2_impact.py` adds `p_holm` and `p_bh` columns, corrected **within each test family** (regime_inflation, self_deception_gap, label_source_gap, regime_effect_model_fixed, learner_effect_regime_fixed — five families now, was three). Verified against hand-computed Holm values before deployment; matched exactly.

### 3c. Self-deception tests pooled two models into non-independent pairs — fixed

**Found:** the test pivoted on `(project, model)`, yielding 42 pairs (21 projects × 2 models) described in the report as "21 projects." JITLine and LApredict on the same project are not independent observations.

**Fixed:** tests are now computed per model with honest project-level pairing (n=21 per model per variant per regime). This surfaced something the pooled test was hiding — the two models' self-deception gaps are very different in size:

| Variant (naive k-fold) | JITLine gap | JITLine Holm p | LApredict gap | LApredict Holm p |
|---|---|---|---|---|
| BSZZ | +0.2480 | 0.0000 | +0.1569 | 0.0003 |
| AGSZZ | +0.1948 | 0.0000 | +0.0469 | 0.9428 (n.s.) |
| MASZZ | +0.2100 | 0.0000 | +0.0632 | 0.6439 (n.s.) |
| LSZZ | +0.1072 | 0.0002 | +0.0602 | 0.5009 (n.s.) |
| RSZZ | +0.0701 | 0.0230 | −0.0237 | 0.9714 (n.s., wrong sign) |
| RASZZ | +0.1913 | 0.0001 | +0.0603 | 0.6563 (n.s.) |

**JITLine's self-deception gap is large and significant for every variant. LApredict's is significant only for BSZZ.** The pooled test's "self-deception is universal" framing was an artifact of JITLine dominating the pooled mean; the correct claim is model-dependent, and that dependence is itself informative (it lines up with Finding 6 in §8 — low-capacity models resist noise, including the noise of circular scoring).

### 3d. JITLine's threshold protocol was unstable — fixed, and the fix required correcting the original audit's own recommendation

**Found:** the old protocol fit on the first 80% of a split, tuned the threshold on the last 20%, then refit on 100% and kept the stale threshold. Measured calibration shift after refit: ~0.35 in probability; test-set predicted-positive rate ranged from 1.4% to 68.5% across projects; JITLine's G-mean sat below single-feature LApredict.

**What the original audit recommended:** out-of-bag (OOB) threshold tuning — fit once on 100%, tune on `RandomForestClassifier(oob_score=True).oob_decision_function_`.

**What measurement showed:** OOB was tested against the old protocol and a third option (chronologically blocked out-of-fold tuning) across 21 projects × 3 seeds × {oracle, BSZZ}:

| Mode | Oracle MCC | Oracle G-mean | Threshold SD | Degenerate (all-one-class) runs |
|---|---|---|---|---|
| `tail` (old) | 0.1031 | 0.4855 | 0.1415 | 9.5% |
| `oob` (**original audit's recommendation**) | 0.0874 | **0.3655** | 0.1018 | **17.5%** |
| `cv` (blocked out-of-fold) | 0.1004 | **0.5226** | **0.1062** | **4.8%** |

**OOB was measurably the worst option — it doubled the degenerate-run rate and gave the lowest G-mean of the three.** The reason: OOB probabilities come from only ~63% of the trees (the ones for which a given row was out-of-bag), so a threshold tuned on them is miscalibrated against the full 100%-of-trees ensemble used at prediction time — a different, subtler version of the same fit/refit mismatch the fix was meant to solve. Chronologically blocked cross-validation was implemented instead and set as the default (`JITLine(threshold_mode="cv")`); all three modes remain selectable for an ablation table.

**Full run result, 10 seeds, chronological, oracle-scored:** G-mean 0.4915 (old) → **0.5297** (fixed); degenerate runs 9.5% → **2.4%**. The BSZZ-over-oracle anomaly survives a fourth independent threshold protocol: gap +0.0258, BSZZ wins **13/21** projects.

### 3e. `fix_ts` coverage/timing table — measured, unchanged by the label fix

Re-measured after the corrected rebuild (values are stable because they depend on the mapping structure, not the label vintage):

| Label source | fix_ts coverage | Median latency | Share > W=90d |
|---|---|---|---|
| oracle | 67.8% | 109.4 d | 52.8% |
| BSZZ | 100.0% | 95.0 d | 50.8% |
| AGSZZ | 98.4% | 87.9 d | 49.7% |
| MASZZ | 99.1% | 91.9 d | 50.2% |
| LSZZ | 97.0% | 62.6 d | 47.3% |
| RSZZ | 98.1% | 24.7 d | 38.0% |
| RASZZ | 95.6% | 73.7 d | 47.9% |

This is disclosure, not a bug — see §5a for what's still open here.

### 3f. Duplicated result rows — fixed

**Found:** for `train_label=oracle`, the `oracle`-scored and `self`-scored cells are identical by construction (`eval_label = label_oracle` either way), so 1,050 of the original 14,700 records were exact duplicates.

**Fixed:** the runner now skips the `self`-scored pass entirely when `train_label == "label_oracle"`. Verified in the current 16,380-record output: `oracle`-trained rows carry only `eval_mode='oracle'`.

---

## 4. What was found: an overstated claim — resolved by disclosure

### 4.1 What was found

The pitch document stated "Oracle ground truth conclusively outperforms all noisy SZZ variants (winning 14 of 21 projects against BSZZ)." The underlying test: `label_source_gap`, ORB, oracle vs BSZZ, **p = 0.3926, Cliff's δ = 0.156 ("small")**. A 14/21 win count at n=21 is not distinguishable from a coin flip, and BSZZ's few large wins (parquet-mr, commons-compress, commons-digester) explain why the signed-rank test came back non-significant.

### 4.2 What the fresh data says (does not need further code changes — this was a statistics/writing gap, not a bug)

Post label-fix and post Phase B, the comparison is, if anything, **weaker**:

| Comparison | Before | After (current) |
|---|---|---|
| Oracle vs BSZZ, wins | 14/21 | **13/21** |
| p-value | 0.3926 | **0.4948** |
| Cliff's δ | 0.156 (small) | **0.1429 (negligible** — below your own `metrics.py` 0.147 cutoff) |
| Imputed oracle vs BSZZ, wins | 12/21 | **11/21** |
| Imputed p-value | 1.0000 | **0.8649** |

Against the five refined variants, the claim is fully supported and stronger than before — all five now survive Holm correction (AGSZZ, MASZZ, LSZZ, RSZZ, RASZZ: p_holm 0.0426–0.0451; MASZZ is now "large" at δ=0.5057).

### 4.3 The language to use (paste-ready)

Replace every instance of "Oracle conclusively outperforms all noisy SZZ variants" with:

> "Oracle ground truth significantly outperforms all five refined SZZ variants (AGSZZ, MASZZ, LSZZ, RSZZ, RASZZ; Holm-adjusted p ≤ 0.045, Cliff's δ 0.42–0.51). Against FP-heavy BSZZ specifically, the advantage is directionally consistent (13/21 projects, +0.012 MCC) but statistically negligible (p = 0.49, δ = 0.14) — and this negligibility is robust to full latency imputation (11/21, p = 0.86)."

This is not a retreat. It is a *sharper* claim: label quality matters, specifically and measurably, for the five variants that are conservative enough to produce a real quality gap — and does not matter (on this corpus, at this sample size) for the one variant whose high recall happens to compensate for its high false-alarm rate. That asymmetry is itself worth a sentence in the discussion chapter.

---

## 5. What remains open

### 5a. Oracle's `fix_ts` is still a union of SZZ mappings — disclosure not yet written

Still true: `label_oracle`'s verification-latency timestamps come from the union of all six SZZ variants' fix→inducing mappings (`scripts/build_fix_ts.py`), since JIT-Defects4J has no oracle-native fix→inducing linkage in this repo. Your imputation experiment addresses the *coverage* half (67.8%→100%) but not the *timing* half — a linked oracle commit's arrival date is still whichever SZZ variant's (possibly wrong) fix it was matched to.

**Not a code fix.** Either locate JIT-Defects4J's own linkage (worth an hour of searching) or add the disclosure paragraph to Chapter 5 methods and Threats to Validity, using the coverage/timing table in §3e. The RSZZ row (24.7-day median latency vs BSZZ's 95) is worth its own sentence — label quality and label timeliness are correlated across variants, a result you have now measured twice but not yet written up.

### 5b. Unweighted project means — not yet addressed

Every reported figure remains an unweighted mean over 21 projects ranging from 544 to 4,026 commits and 1.8%–19.3% defect rate. commons-digester trains on 5 positive examples in the chronological split and counts equally toward the grand mean as commons-math's 196.

**Not started.** Two independent pieces of remaining work: (1) report the per-project N table in the appendix (data already sitting in `data/processed/phase2_commits.csv`, just needs extracting), (2) re-run the headline comparisons excluding projects below a positive-count floor and state whether conclusions change. Given how much of §2–§4 already moved once, this robustness check is worth doing before the numbers are considered final for the thesis text.

---

## 6. What you still need to do

This audit and its remediation fixed the *data and code*. It did not touch the *prose*. Concretely:

1. **`reports/phase1_phase2_report.md` / `.html`** (auto-generated by `scripts/generate_report.py`) reflect the current numbers but were written by a report generator that predates Phase B — it does not know about `chronological_online`, `mcc_avg`, the Holm columns, or the new test families. It still frames the batch→stream gap as a latency effect. This needs a generator update, not just a re-run.
2. **`Phase1_Phase2_Comprehensive_Analysis_and_Supervisor_Pitch.md`** is now stale in every Phase 2 number and in the "Oracle conclusively outperforms" framing (§4.3 gives you the replacement language). The Phase 1 numbers in it are still correct.
3. §5a and §5b above are genuinely unstarted work, not documentation debt.
4. Once 1–3 are done, re-verify the specific numeric corrections originally catalogued (median/coverage population labeling, BSZZ positive-rate percentage, the 81.7% vs 81.5% precision-ceiling rounding, the record-count footnote) — these were minor and mostly about *which* denominator a percentage uses; re-check them against the current `results/phase2/` rather than assuming they still apply verbatim.

---

## 7. Implications for Phase 3 and Phase 4

**Phase 3 is now unblocked.** `phase1_bias.json` is unchanged by this remediation (it was already correct), and it is now *provably* the noise profile of the labels Phase 2 actually trained on — the gate enforces this going forward. The `mid` calibration point (RASZZ: ρ₀=0.1813, ρ₁=0.5617) is unchanged from the original document; no action needed there.

**The self-filtering trap** (a synthetic FP flip on a clean commit usually has no `fix_ts`, so its poisoned label never reaches training under `latency_mode="real"`) is still real and still needs the two-arm design (uniform-latency primary, real-latency-with-imputation secondary) described in the original audit. Nothing in this remediation changes that guidance.

**Phase 4's "FN noise dominates" premise needs re-checking against the corrected prequential estimator (§3a).** The original premise rested on terminal-value ORB numbers. Under the time-averaged estimator, MASZZ's apparent harm disappears and the variant ordering compresses further (see §3a table). Recompute the FN-vs-FP dominance argument from `mcc_avg`, which is now available per run, before finalizing the Noise-Aware ORB architecture around it.

**ORB's per-step trace is still being discarded.** `ORB.trace` records `boost`, `lam`, `ma_pred`, `rate1` per learning step — exactly the "boost factor over time" deliverable outline §6.1 asks for — and it is computed but not persisted anywhere. This remains a ~20-line addition, unclaimed by this remediation pass.

---

## 8. Current headline numbers — the ones to actually cite

Superseding §9 of the original document. All below are from `results/phase2/` at `master` @ `830eb48`, 10 seeds, gate-verified.

**Tier 1 — unchanged, still bulletproof:**
1. Random k-fold inflates JITLine's oracle-scored MCC by +0.1273 over chronological (was +0.1407 pre-fix; still p<1e-6, Holm p=0.0000, δ=0.74, large).
2. Self-scoring on SZZ inflates apparent performance — now shown per model (§3c): JITLine's gap is large and significant for all six variants; LApredict's only for BSZZ.
3. SZZ variants agree strongly with each other (κ up to 0.933), poorly with oracle (κ 0.158–0.202). *(Phase 1 — unaffected by any of this remediation.)*
4. No SZZ variant exceeds 27.2% precision; asymmetric, variant-dependent noise. *(Phase 1 — unaffected.)*

**Tier 2 — corrected, now stronger or more precisely scoped:**
5. Oracle significantly outperforms all five refined SZZ variants (Holm p ≤ 0.045); the BSZZ comparison is negligible, not "conclusive" (§4).
6. FP-heavy BSZZ still beats oracle for JITLine (13/21, gap +0.0258), now measured under a fourth, better-calibrated threshold protocol (§3d).
7. **New, and arguably your strongest single result now:** once learner architecture is held fixed, verification latency does not measurably degrade absolute MCC (Δ=+0.0093, p=0.84) — the batch→stream drop in the old ladder was ~91% a learner-swap artifact, ~9% latency (§2.3). Verification latency's real cost shows up instead as *compression of the label-source ordering* (variant MCCs cluster together under real latency where they were more separated under chronological batch evaluation), not as an absolute penalty.

**Tier 3 — report as observations:**
8. Absolute "deployable" MCC under realistic conditions is **~0.097** using the correct time-averaged prequential estimator (was reported as 0.0685 — a terminal-value artifact, §3a).
9. Low-capacity LApredict remains far more noise-resistant than JITLine, and this now shows up directly in the self-deception gap too (§3c) — not just in raw MCC variance across label sources as originally stated.

---

## 9. What was verified correct from the start

Unchanged from the original audit — still true, still don't re-litigate:

- Phase 1 is internally self-consistent (BSZZ TP+FP=8,060 reproduces exactly from `results/phase1/*_labels.csv`; all six variants on an identical 27,319-commit denominator).
- `results/phase1_raw/` contains all 126 fix→inducing JSONs.
- The ORB replication (`results/replication/cabral2019_orb_replication.csv`) is genuine: G-mean 0.46–0.93, mean≈0.68 across 14 Cabral et al. datasets, squarely in the published range. (Caveat: those datasets run at 22–43% defect ratio vs. this corpus's 8.5% — state that when citing the replication as validation.)
- No train/eval label leakage in the experiment wiring, in either the original code or the Phase B additions.

---

## 10. Appendix — how to reproduce every number in this document

All commands run from the repo root with the venv active, against current `master`.

**Confirm the gate passes (the single most important check):**
```bash
python -m experiments.check_label_consistency
```

**Ladder decomposition (§2.3):**
```bash
python - <<'EOF'
import pandas as pd
r = pd.read_csv("results/phase2/phase2_results.csv"); o = r[r.eval_mode=="oracle"]
g = o.groupby(["model","regime","train_label"]).mcc.mean()
la, ji = g[("LApredict","chronological","oracle")], g[("JITLine","chronological","oracle")]
oc, op = g[("ORB","chronological_online","oracle")], g[("ORB","prequential_latency","oracle")]
print(f"learner effect {la-oc:+.4f}   regime/latency effect {oc-op:+.4f}")
print(f"latency = {100*(oc-op)/(la-op):.0f}% of the {la-op:.4f} drop")
EOF
```

**Prequential terminal vs averaged (§3a):**
```bash
python -c "
import pandas as pd
r = pd.read_csv('results/phase2/phase2_results.csv')
p = r[(r.eval_mode=='oracle') & (r.regime=='prequential_latency')]
print(p.groupby('train_label')[['mcc','mcc_avg']].mean().round(4))
"
```

**Oracle vs BSZZ significance, current (§4.2):**
```bash
python -c "
import pandas as pd
s = pd.read_csv('results/phase2/statistical_tests.csv')
print(s[s.comparison_type=='label_source_gap'][['train_label','mean_diff','p_value','p_holm','cliffs_delta','magnitude']].round(4).to_string(index=False))
"
```

**Per-model self-deception (§3c):**
```bash
python -c "
import pandas as pd
s = pd.read_csv('results/phase2/statistical_tests.csv')
sd = s[(s.comparison_type=='self_deception_gap') & (s.condition_A.str.contains('naive'))]
print(sd[['model','train_label','mean_diff','p_value','p_holm','magnitude']].round(4).to_string(index=False))
"
```

**JITLine threshold-mode comparison (§3d) — this one is not cached, it re-fits:**
```bash
python - <<'EOF'
import numpy as np, pandas as pd
from codebase.data.loader import load_or_build_dataset, get_all_projects, get_project_dataset
from codebase.config import KAMEI_FEATURES
from codebase.models.baselines import JITLine
from codebase.evaluation.metrics import mcc, gmean
df = load_or_build_dataset(); rows = []
for proj in get_all_projects(df):
    d = get_project_dataset(proj, df); cut = len(d)//2
    tr, te = d.iloc[:cut], d.iloc[cut:]
    Xtr, Xte = tr[KAMEI_FEATURES].to_numpy(float), te[KAMEI_FEATURES].to_numpy(float)
    for lab in ["label_oracle","label_BSZZ"]:
        ytr, yte = tr[lab].to_numpy(int), te.label_oracle.to_numpy(int)
        for mode in ["tail","oob","cv"]:
            for s in [7,13,21]:
                m = JITLine(seed=s, n_estimators=100, threshold_mode=mode)
                m.fit(Xtr, ytr); pr = m.predict(Xte)
                rows.append(dict(label=lab, mode=mode, mcc=mcc(yte,pr), gmean=gmean(yte,pr)))
r = pd.DataFrame(rows)
print(r.groupby("mode")[["mcc","gmean"]].mean().round(4))
EOF
```

**Gate failure on the old stale dataset, for reference (§1.2):** the artifact backup used to produce this table no longer exists in the repo (it was a scratch file, deliberately not committed). To reproduce the demonstration, check out `975302a`'s `results/phase1/*_labels.csv`, rebuild the dataset from them, and run the gate against current `phase1_bias.json` — it will fail on all six variants by construction.

---

*This document supersedes the 2026-09-03 version. Historical findings are preserved above with their resolution; nothing was deleted, only annotated with outcome.*

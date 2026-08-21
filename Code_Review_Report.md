# Code Review: thesis-later Repository
**Reviewed:** full clone of `itz-puneet/thesis-later` (master, 15 commits) — code, data, and results were executed/re-computed locally to verify findings, not just read.

---

## Overall verdict

This is a genuinely solid empirical pipeline: real pyszz_v2 runs across 21 cloned repos, a validated ORB implementation, a clean 14,700-run experiment grid with checkpointing and multiprocessing, and proper paired statistics. Three of the four red flags from the earlier report review are now resolved or explained. But I found **one confirmed data bug that invalidates the current Phase 1 table and `phase1_bias.json`** (the file that parameterizes Phase 3), plus a methodological gap in the latency simulation and an inconsistency between your two prequential implementations. All are fixable with the patches provided.

**Good news first — verified strengths:**

1. **Your ORB implementation is validated.** `results/replication/cabral2019_orb_replication.csv` shows G-mean 0.55–0.90 (mean ≈ 0.68) across Cabral et al.'s 14 datasets — squarely in the published range. This is the single most important credibility artifact in the repo. The earlier concern "is ORB under-tuned?" is closed: your low Phase 2 numbers are a property of the data (8.5% defect rate, oracle scoring), not the implementation.
2. **G-mean was computed all along** — it's in `phase2_results.csv` (ORB mean G-mean 0.525 on the 21 projects). It just never made it into the report. Add it; it changes the story (see Finding 3).
3. The experiment runner (`run_phase2_impact.py`) is well-designed: per-project × per-seed parallel cells, dual scoring conventions, fast mode, project-level paired tests. No leakage between train/eval label columns — I checked the wiring.

---

## Finding 1 (CRITICAL, confirmed): NaN labels silently corrupt Phase 1 and desynchronize it from Phase 2

**What I found.** The per-commit label files for BSZZ and AGSZZ contain **9,712 NaN labels each** (BSZZ: 67,528 zeros / 8,216 ones / 9,712 NaN). MASZZ, LSZZ, RSZZ, RASZZ are clean 0/1. In `experiments/evaluate_confusion_matrix.py`, the cells are computed with `merged[label_col] == 1` / `== 0` — NaN fails both comparisons, so those rows **silently vanish from the confusion matrix**. That is exactly your Table 1 denominator mismatch: 24,313 (BSZZ/AGSZZ) vs 27,281 (others). It is not the git-blame philosophy difference you hypothesized — your blame explanation may be *why* pyszz produced no determination for those commits, but the bug is that "no determination" became NaN in one conversion path and 0 in another.

**Why it's critical, twice over:**
- **Phase 1 ≠ Phase 2 labels.** `codebase/data/loader.py` does `.fillna(0)` when building `phase2_commits.csv`, so Phase 2 trains on NaN→0 labels while Phase 1's bias table excludes those commits. Your ρ₀/ρ₁ in `phase1_bias.json` — the parameters Phase 3 will inject — were measured on a different label set than the one your models actually consume.
- The exclusion is non-random (NaN concentrates in specific commits), so BSZZ/AGSZZ precision/recall are biased relative to the other four variants.

**Corrected Phase 1 table** (recomputed on the full 27,319-commit oracle universe, NaN→0, left join — run yourself with the patch):

| Variant | Precision | Recall | ρ₀ (FPR) | ρ₁ (FNR) | MCC | κ |
|---|---|---|---|---|---|---|
| BSZZ | 0.193 | **0.605** ↓from 0.656 | 0.236 | 0.395 | 0.232 | 0.187 |
| AGSZZ | 0.215 | **0.412** ↓from 0.447 | 0.141 | 0.588 | 0.205 | 0.192 |
| MASZZ | 0.199 | 0.459 | 0.173 | 0.541 | 0.201 | 0.179 |
| LSZZ | 0.281 | 0.256 | 0.061 | 0.744 | 0.203 | 0.203 |
| RSZZ | 0.242 | 0.280 | 0.082 | 0.720 | 0.186 | 0.185 |
| RASZZ | 0.212 | 0.378 | 0.131 | 0.622 | 0.192 | 0.183 |

The qualitative story survives (precision ceiling ~28%, two-sided noise, FN-heavy refined variants), which is good — but every number in Table 1, the kappa heatmap, and `phase1_bias.json` must be regenerated. **Patch: `patch_evaluate_confusion_matrix.py`** does this, adds MCC/κ/per-project breakdowns, and exports a corrected `phase1_bias.json` in the ρ₀/ρ₁ format Phase 3 expects.

**Also decide and document the semantics:** NaN→0 ("SZZ made no claim ⇒ not flagged") is the right call and matches how any consumer of SZZ labels would behave, but say so explicitly in the thesis. And trace where the NaNs were introduced — the label files were produced by a conversion step that isn't in the repo (the `run_phase1_oracle.py` output format is fix→inducing mappings, but the committed files are per-commit binaries, so a notebook overwrote them). **Commit that conversion script.** Right now Phase 1 is not reproducible from the repo alone, and the fix→inducing mapping — which you need for Finding 2 — appears to have been overwritten.

---

## Finding 2 (MAJOR): "verification latency" is currently a uniform 90-day delay, not verification latency

`phase2_commits.csv` has **no `fix_ts` column**. In `codebase/evaluation/regimes.py::prequential_latency`, `fix_ts` therefore loads as all-NaN, and every commit — defective or clean — falls into the `now + W` branches. Two consequences:

1. **Every label arrives at exactly t+90d.** Real verification latency means defect labels arrive at the *fix time* (median often far beyond 90 days), while commits are *tentatively assumed clean* at t+W and corrected later. That tentative-clean-then-correct dynamic — the one-sided noise Song et al. (2022) study, and the thing your gap statement leans on — never occurs in your Phase 2 runs.
2. **Your two prequential implementations disagree.** `scripts/replicate_cabral_orb.py` *does* implement tentative-clean at W then correction at W+1000s. So the validated replication and the reported Phase 2 use different protocols. An examiner will find this.

Note the direction of the error is *optimistic for defect labels* (they arrive at 90d even when the real fix came years later) and *pessimistic for the tentative-clean noise* (there is none). Net effect on ORB unknown — which is precisely why it must be fixed, not argued away.

**Fix options, in order of preference:**
- **(a) Build real `fix_ts`.** You already have everything needed: `jit_defects4j.csv` gives the 5,453 fix hashes, the 21 repos are cloned locally, and pyszz's raw output maps each fix to its inducing commits. Re-emit that mapping (it existed before the label-conversion overwrite), pull fix-commit author dates via `git log`, and set each inducing commit's `fix_ts` = earliest linked fix date. **Patch: `patch_build_fix_ts.py`** implements the whole flow, including the git-date extraction and a per-variant + oracle mapping merge.
- **(b) Documented fallback** if mapping recovery fails for some variants: keep uniform-delay but rename it honestly ("fixed-delay online evaluation, W=90d") and state the limitation. The patch supports `--mode uniform` for exactly this.

Your README's "metadata-poor setting" note reads as if this were a deliberate design choice — with `fix_ts` reconstructable from data you already have, that framing won't survive review. Reconstruct it.

---

## Finding 3 (MAJOR, now diagnosed): the oracle-trained JITLine "anomaly" is real, systematic, and is a *finding* — but your JITLine has a threshold problem

I verified: BSZZ-trained JITLine beats oracle-trained JITLine (chronological, oracle-scored) in **15/21 projects**, and G-mean makes the mechanism obvious: oracle-trained G-mean = **0.228** vs BSZZ-trained = **0.482**. With an 8.5% defect rate, the oracle-trained RF collapses toward the majority class; BSZZ's 26.8% positive rate injects ~3× more minority mass and buys recall that both MCC and G-mean reward. This is the "FP-heavy noise acts as accidental minority augmentation for batch learners" result — write it up as such, it's one of your most interesting numbers.

**But separate the phenomenon from the implementation artifact.** Your JITLine's G-mean (0.28–0.48) sits far *below* the one-feature LApredict (0.65) — that's not the published JITLine's behavior and signals the classifier is decision-threshold-starved, not information-starved. Causes in `codebase/models/baselines.py`:
- Jitter-duplication oversampling is weak with ~40 positives per train split (real JITLine uses SMOTE);
- RF `predict()` at the default 0.5 probability threshold under heavy imbalance predicts almost nothing positive, regardless of `class_weight`.

**Patch: `patch_jitline.py`** adds (i) SMOTE when `imblearn` is available (jitter fallback otherwise) and (ii) threshold moving: the decision threshold is tuned to maximize G-mean on the *tail 20% of the training split* (chronologically last, so no leakage). Re-run Phase 2 for JITLine after applying — expect the oracle-vs-BSZZ gap to shrink but likely not vanish, which cleanly separates "threshold artifact" from "minority-enrichment effect." That decomposition is a thesis-quality analysis.

---

## Finding 4 (MODERATE): Phase 1 evaluation universe & reporting

- `evaluate_confusion_matrix.py` uses `how="inner"` merge — commits in the oracle set that SZZ never emitted rows for silently drop out (38 commits currently; would grow if any variant run were incomplete). Use a **left join on the oracle universe** with missing→0. The patch does this.
- The merge is on `commit_id` alone across all projects' files. Full SHA-1 collisions are practically impossible, so this is safe — but merge on `(project, commit_id)` anyway; it's free insurance and the ground truth has both columns.
- Report improvements: add MCC, κ, and G-mean columns (the report's own thesis is "F1/precision-alone reporting is the field's flaw" — Table 1 currently reports P/R/F1 most prominently); replace the "85% deflation" headline with your *measured* deltas (naive→chronological: +0.137 MCC for JITLine, p=3.1e-5, δ=0.60 — that row in `statistical_tests.csv` is your strongest defensible claim).

## Finding 5 (MINOR, verified-fine or small fixes)

- `naive_kfold`'s adaptive `k_actual = min(k, pos_count, ...)` is a sensible guard; document it since it changes k for tiny projects.
- `wilcoxon_with_cliffs` (support_codebase heritage) computes Cliff's δ with an O(n²) double loop — fine at n=21, just noting.
- Cabral replication: `now + W + 1000.0` for defect arrival and the `commit_type == 2` immediate-label branch are approximations of Cabral's protocol — one comment line explaining each will preempt questions.
- `phase2_commits.csv` per-project sizes (544–4,026 commits) mean chronological 50/50 splits leave as few as ~23 positives in training for the smallest projects. Report per-project N in the thesis appendix; consider flagging projects below a positive-count floor.
- `run_phase3_noise.py` and `run_phase4_na_orb.py` are empty files — expected at this stage, but the corrected `phase1_bias.json` from the Phase 1 patch is a *prerequisite* for writing them. Don't start Phase 3 until Finding 1 is merged.
- Repo hygiene: `codebase/` vs `support_codebase/` duplication will bite you — the old `support_codebase` still contains divergent copies of `regimes.py`/`orb.py`. Delete or clearly mark it as archived scaffold so nobody (including future-you) imports the wrong one.

---

## Priority order

| # | Action | Patch | Effort |
|---|---|---|---|
| 1 | Regenerate Phase 1 table + `phase1_bias.json` (NaN fix, left join, full metrics) | `patch_evaluate_confusion_matrix.py` | minutes |
| 2 | Commit the missing label-conversion script; re-emit fix→inducing mappings | (your notebook) | ~1 day |
| 3 | Build `fix_ts`; rerun Phase 2's ORB rows with true latency | `patch_build_fix_ts.py` + `patch_regimes.py` | 1–2 days compute |
| 4 | Threshold-tuned JITLine; rerun JITLine rows; decompose the anomaly | `patch_jitline.py` | ~1 day compute |
| 5 | Report v2: G-mean columns, measured-delta headline, latency wording | edit report | hours |
| 6 | Only then: Phase 3 using corrected ρ₀/ρ₁ | — | as planned |

One framing note for the supervisor meeting: none of these findings weaken the thesis — the corrected Phase 1 still shows a ~28% precision ceiling and two-sided variant-dependent noise, the ORB replication validates your instrument, and the JITLine anomaly upgraded from "bug?" to "result." What changes is that you can now show you *caught* a label-consistency bug between phases — which is, rather poetically, a live demonstration of your own thesis topic.

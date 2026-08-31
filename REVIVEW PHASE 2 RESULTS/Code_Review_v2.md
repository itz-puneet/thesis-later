# Code Review v2 — post-fix rerun (Phases 1 & 2)

**Scope:** fresh clone of `itz-puneet/thesis-later` @ `9634ee4`. All numbers below were recomputed locally from your committed results/data, not taken from your report.

---

## 1. Fix verification — all four majors are properly closed

| Prior finding | Status | Evidence (verified locally) |
|---|---|---|
| NaN label bug / denominator mismatch | **Closed** | Label files regenerated: BSZZ = {0: 85,662, 1: 9,071}, zero NaN. Corrected eval script adopted; every variant now evaluated on the identical 27,319-commit universe. `phase1_bias.json` regenerated (BSZZ ρ₀=0.263/ρ₁=0.359 … LSZZ ρ₀=0.067/ρ₁=0.733). |
| Phase 1 not reproducible / mappings lost | **Closed** | `results/phase1_raw/` now contains the fix→inducing JSONs (218k lines) — the artifact Phase 3 and fix_ts both depend on. |
| Uniform-delay masquerading as verification latency | **Closed** | `build_fix_ts.py` committed; `phase2_commits.csv` has per-variant `fix_ts_*` + union. Reconstructed latency: **median 113 days, p90 ≈ 1,597 days, 53% of defect labels arrive after W=90d** — so the tentative-clean-then-correct dynamic is now live and, empirically, dominant. `prequential_latency` has the real/uniform guard and per-source `fix_ts_col`; Phase 2 rerun with `latency_mode: real`. |
| JITLine threshold starvation | **Closed** | SMOTE + G-mean threshold moving adopted. JITLine G-mean: 0.28→0.48 (chronological), 0.38→0.59 (k-fold). |

Also noted approvingly: the GitHub Actions workflow for cloud Phase 2 runs — that's exactly the reproducibility posture an examiner wants to see.

## 2. What the corrected numbers now say (your updated headline results)

**The JITLine anomaly decomposed cleanly — this is now a two-part finding.** After the threshold fix, oracle-trained JITLine (chronological, oracle-scored) improved from 0.067→0.103 MCC, and BSZZ-trained from 0.113→0.131; BSZZ still wins in 13/21 projects (was 15/21). Write it exactly this way in the thesis: *part of the earlier gap was a decision-threshold artifact (removed by threshold moving), and a residual minority-enrichment effect remains — FP-heavy labels genuinely help batch learners under 8.5% imbalance.* You have before/after numbers for both components; few theses get such a clean decomposition.

**ORB under real latency: the sanity ordering is restored.** Oracle-trained ORB is now the best label source (MCC 0.068, G-mean 0.546), winning in 14/21 projects vs BSZZ (0.056/0.506). Under the old uniform-delay run, BSZZ ≈ oracle — so real latency was the missing ingredient. Also, the inflation-ladder statistic strengthened: JITLine oracle naive→chronological is now 0.243→0.103 (δ=0.74, p=2.9e-6), and the self-deception gap holds at +0.18 MCC (δ=0.81, p=6.5e-8). These two rows of `statistical_tests.csv` are your defensible headlines.

**But the FN-dominance hypothesis needs revision.** The earlier (uniform-delay) run showed a clean "precise-but-blind variants hurt ORB most" ordering. Under real latency the variant ordering is compressed and mixed (LSZZ 0.026 > RSZZ 0.018 > AGSZZ 0.016 > RASZZ 0.005 > MASZZ −0.003). The likely reason is itself interesting: with 53% of defect labels arriving late, **latency already imposes heavy FN-like noise on every label source**, shrinking the marginal difference between FP-heavy and FN-heavy variants. Your Phase 3 must now separate three entangled quantities — SZZ FP noise, SZZ FN noise, and latency-induced label delay — which is exactly what the dose-controlled design (and the repair experiment below) is for. Don't present the old ordering claim; present the compression as a finding and let Phase 3 resolve the mechanism.

## 3. New issues found in this review

**3a (MODERATE) — fix_ts coverage is label-source-dependent, a confound you must disclose and bound.** By construction, 100% of BSZZ-flagged commits have `fix_ts_BSZZ` (a commit is flagged *because* a mapping links it), but only **67.8% of oracle-defective commits** have a union fix_ts — so for oracle-trained ORB, ~1/3 of true defect labels *never arrive*. Oracle still wins despite this handicap, which strengthens the result, but the comparison currently mixes label *quality* with label *deliverability*. Also, the oracle's fix_ts is a union of SZZ mappings — an SZZ-dependent construct used inside your "SZZ-free" condition. Fix: run the imputed-latency sensitivity (code provided — `fix_ts` sampled from the empirical latency distribution for unlinked defective commits, seed-controlled) and report both. If the ordering holds under imputation, the confound is bounded and dead.

**3b (MODERATE) — Phase 3 has a design trap under real latency.** If you inject synthetic FP flips into oracle labels and run `latency_mode="real"`, a clean commit flipped to "defective" mostly has no fix_ts (71% of clean commits are unlinked) — so its poisoned label **never reaches training** and your FP noise silently self-filters. Dose-response curves would understate FP sensitivity. The provided Phase 3 runner handles this: primary arm under `uniform` latency (isolates noise mechanics), secondary arm under `real` latency with imputed fix_ts for injected positives (realism check). This subtlety is worth a paragraph in the methodology chapter — it's a non-obvious interaction between the two noise sources.

**3c (MINOR) —** `support_codebase/` still present with divergent copies of `orb.py`/`regimes.py`; archive or delete before anyone imports the wrong one. ORB seed variance is healthy (mean per-project MCC σ=0.026 over 10 seeds), so 10 seeds suffice for Phase 4 power at project-level pairing. The self-scored ORB rows retrain the identical model twice per cell (only scoring differs) — score both conventions from one prediction stream to halve ORB compute in future reruns.

## 4. Ship-it checklist before the supervisor meeting

1. Report v2 tables straight from `phase1_quality_corrected.csv` (with MCC/κ/G-mean columns) and the new `statistical_tests.csv` rows; retire the "85% deflation" phrasing for the measured deltas.
2. One new figure: reconstructed latency distribution (median 113d, 53% > 90d line marked) — it justifies the entire online-evaluation apparatus in a single picture.
3. One slide: JITLine anomaly decomposition (before/after threshold fix, 15/21 → 13/21).
4. Disclose 3a with the imputation sensitivity plan (or its result if you run it first — it's cheap).

Everything else in this package is forward motion: the Phase 3/4 modules and runners are written against your repo's actual APIs (`codebase.config`, your loader, your `prequential_latency` signature) — see `Phase3_4_Plan_and_Expectations.md` for how to run them and what results to expect.

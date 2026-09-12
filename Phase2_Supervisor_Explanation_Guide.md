# Phase 2: How to Explain the Results and the Statistical Tests

**For:** supervisor meeting on Phase 2 (Downstream Impact Under Honest Evaluation)
**Data source:** `results/phase2/` at `master` @ `0a07a82` — 16,380 evaluation records, 21 Apache projects × 10 seeds × 7 label sources × 3 models × 4 regime-scoring combinations
**Verified:** label-consistency gate passes; the noise rates in `phase1_bias.json` describe exactly the labels these models trained on
**Estimators:** every streaming result is reported under two prequential summary statistics — the *time-averaged* value (primary) and the *terminal* fading value (secondary). Neither is a canonical standard; the preference is justified by measured variance, not citation. They agree on all but one comparison; see §7.

---

## Table of Contents

1. [The one-paragraph version](#1-the-one-paragraph-version)
2. [What Phase 2 actually measured](#2-what-phase-2-actually-measured)
3. [The five findings, in the order you should present them](#3-the-five-findings-in-the-order-you-should-present-them)
4. [The statistical tests: what they are and why these ones](#4-the-statistical-tests-what-they-are-and-why-these-ones)
5. [Test family 1 — Regime inflation](#5-test-family-1--regime-inflation)
6. [Test family 2 — Self-deception gap](#6-test-family-2--self-deception-gap)
7. [Test family 3 — Label source gap](#7-test-family-3--label-source-gap)
8. [Test families 4 & 5 — The batch→stream decomposition](#8-test-families-4--5--the-batchstream-decomposition)
9. [How to explain the multiplicity correction](#9-how-to-explain-the-multiplicity-correction)
10. [Anticipated questions and honest answers](#10-anticipated-questions-and-honest-answers)
11. [What to say about the label-vintage bug](#11-what-to-say-about-the-label-vintage-bug)
12. [Numbers cheat-sheet](#12-numbers-cheat-sheet)

---

## 1. The one-paragraph version

If you have sixty seconds, say this:

> "Phase 2 asked what SZZ label noise actually costs a defect prediction model, once you stop evaluating it dishonestly. I ran three models across seven label sources and four evaluation regimes — 16,380 runs — and tested everything with paired Wilcoxon signed-rank tests at the project level, Holm-corrected within test family. Three things came out. First, random k-fold cross-validation inflates JITLine's apparent performance by +0.137 MCC over a chronological split — it held in all 21 projects, so the exact test saturates at p = 9.5e-07. Second, evaluating a model on the same SZZ labels it was trained on inflates it by a further +0.230 MCC — a gap consistent with models fitting the heuristic's error structure rather than defects. Third, under honest streaming evaluation with real verification latency, training on the held-out oracle labels beats all six SZZ variants, every comparison significant after correction — so label quality demonstrably matters once you evaluate properly. And a correction I want to flag myself: I previously reported that latency accounts for only ~9% of the batch-to-streaming drop. That comparison was not identified — it changed the learner, the label timing and the evaluation window all at once — so I have withdrawn it and built the full 2×2 that does isolate the effects. At ten seeds the delay penalty is estimated at about +0.02 MCC for an adaptive learner, but every contrast in the 2×2 — including the interaction — has a confidence interval spanning zero, so the honest answer is that 21 paired projects cannot resolve it."

Then stop and let them ask.

---

## 2. What Phase 2 actually measured

Set this up before showing any numbers, or the numbers won't land.

**The design is a 3-way grid:**

| Dimension | Levels |
|---|---|
| **Model** | LApredict (logistic regression on `la` alone), JITLine (100-tree Random Forest + SMOTE + threshold moving), ORB (20-member online logistic ensemble) |
| **Training label source** | `label_oracle` (LLTC4J-derived — see the provenance note below) + 6 SZZ variants (BSZZ, AGSZZ, MASZZ, LSZZ, RSZZ, RASZZ) |
| **Evaluation regime** | `naive_kfold` (random 10-fold — the dishonest baseline), `chronological` (50/50 time split), `chronological_online` (ORB trained sequentially on the past, frozen, tested on the future), `prequential_latency` (test-then-train streaming with reconstructed verification latency, W=90 days) |
| **Scoring convention** | *oracle-scored* (measured against the LLTC4J-derived oracle) vs *self-scored* (measured against the same noisy SZZ labels used for training — what the literature does) |

**The critical conceptual point to make explicit:** the difference between *oracle-scored* and *self-scored* is the entire experiment. Everyone in the field trains on SZZ and tests on SZZ. That measures how well a model reproduces a heuristic, not how well it finds bugs. By keeping an independently-sourced oracle held out as the scoring key, you can measure the gap between those two things.

**Provenance, and be precise about it.** The oracle comes from the JIT-Fine replication package on Zenodo (Ni et al.), whose dataset is built on LLTC4J (Herbold et al.), in which human annotators labelled lines **within bug-fixing commits**. `label_oracle` however marks **defect-introducing** commits, and the replication package does not document how Ni et al. mapped fixes to inducing commits — it ships no construction code. So say *"human-labelled bug-fixing commits, extended to introducing commits by a method not documented in the package"*, not *"developer-verified ground truth"*. It is demonstrably not this toolchain's SZZ output (32% of oracle positives are flagged by no variant; Jaccard ≈ 0.15), but that rules out one alternative, not all of them. Full detail in `Phase1_Phase2_Master_Results.md` §0b.

**Why 21 projects × 10 seeds:** the seeds control for model initialisation and fold randomness; the projects are the unit of statistical analysis. Every test below is paired at the *project* level (n=21), averaging over seeds first. Do not let anyone think n=16,380 — that would be pseudo-replication and it is the first thing a methodologist would attack.

---

## 3. The five findings, in the order you should present them

Present them in this order. It builds from "the field has a measurement problem" to "here is a thing nobody has measured before."

### Finding 1 — Random k-fold inflates results, badly, and only for high-capacity models

JITLine oracle-trained: **0.2430** under random k-fold → **0.1016** under a chronological split. A drop of **0.141 MCC**, more than half its apparent performance.

LApredict oracle-trained: 0.2058 → 0.1734. A drop of only 0.032, not significant.

**How to explain the asymmetry:** a Random Forest with 14 features can memorise project-specific temporal patterns. When folds are shuffled, commits from 2015 help predict commits from 2012, and the model exploits autocorrelation that will not exist at deployment. A single-feature logistic regression has no capacity to memorise anything — it can only learn "bigger changes are riskier," which is equally true in both regimes. **The inflation is a function of model capacity, not of the data.** That is why weak baselines like LApredict look competitive in the literature: they were never the ones being inflated.

### Finding 2 — Self-scoring on SZZ inflates results even more

JITLine trained on BSZZ, evaluated under random k-fold:
- Scored against BSZZ's own labels: **0.4129**
- Scored against the held-out oracle: **0.1751**
- Gap: **+0.238 MCC**

**How to explain it — as an interpretation, not a demonstration:** BSZZ flags 8,060 of 27,319 commits as defect-inducing, but only 1,495 are real (18.6% precision). The gap is *compatible with* the model fitting systematic structure in BSZZ's errors rather than in defects: that structure would be learnable, and fitting it would score well against BSZZ and poorly against the oracle.

**Be careful with the wording.** The measured quantity is the self-scored-minus-oracle-scored gap. It does not by itself demonstrate that the forest "learns which commits BSZZ over-flags" — that is a mechanism the gap is consistent with, not one it establishes. Demonstrating it needs a direct analysis, e.g. whether a model trained to predict BSZZ's false positives from the Kamei features achieves above-chance accuracy. That analysis has not been run. Say "consistent with", and if a supervisor pushes, name the experiment that would settle it.

This is the largest effect in the study: matched-pairs rank-biserial **+0.991**, Hodges–Lehmann +0.2303 with a 95% CI of [+0.180, +0.270] — near-total separation between the paired distributions.

### Finding 3 — FP-heavy labels help batch learners in some projects — mechanism unresolved

Under chronological evaluation, oracle-scored: BSZZ-trained JITLine (**0.1324**) beats oracle-trained JITLine (**0.1016**), winning in 15 of 21 projects.

**The effect is real, not noise.** 97.7% of the between-project variance in the gap is genuine rather than seed variation, and 16 of 21 projects have a gap more than 2 SE from zero. Say this before anyone asks — it is the first thing a sceptic will probe.

**The likely explanation, stated as a hypothesis:** the corpus is 8.5% defective. Training on oracle labels gives a Random Forest roughly 40 positives per project split, and it starves the minority class. BSZZ labels 29.5% of commits positive, and although ~81% are false alarms, the expanded positive set gives the trees more minority mass to partition on.

**Do not present that as established, because it is not.** Two things to volunteer:

1. **No project characteristic predicts where BSZZ wins.** Nine candidates tested — project size, oracle positive count, oracle positive rate, training-half positives, BSZZ positive rate, enrichment ratio, BSZZ precision, BSZZ recall, fix_ts coverage. Not one reaches uncorrected p < 0.05 across 18 tests. The starvation hypothesis is the closest: projects with few training positives gain +0.048 versus +0.002 for positive-rich ones, but Mann-Whitney **p = 0.245**.
2. **`opennlp` contradicts the mechanism outright.** It is the second-largest BSZZ win (+0.162 ± 0.010), yet BSZZ flags a *lower* positive rate there than the oracle — 6.91% vs 8.38%, enrichment **0.82×**. No extra minority mass exists in that project, so augmentation cannot be what is happening.

**And it is a batch phenomenon only.** Under the time-averaged estimator, BSZZ beats oracle for ORB in just 3 of 21 projects. It does not survive the move to streaming — which supports reading it as "how batch learners cope with imbalance" rather than anything about label quality.

**How to say it:**

> "FP-heavy labels help batch learners in some projects, and the effect is stable across seeds. Class-imbalance relief is the natural explanation and it matches the aggregate direction, but I could not confirm it: no project-level characteristic predicts where it happens, and opennlp is a large BSZZ win where BSZZ actually supplies fewer positives than the oracle. So I am reporting the phenomenon and treating the mechanism as open."

The threshold-artifact objection is separately closed — see §10, Q3.

### Finding 4 — Under honest streaming evaluation, label quality does matter

ORB under real verification latency, oracle-scored, **time-averaged prequential MCC** (the primary estimator — see §7):

| Training labels | MCC | Oracle wins | Holm p |
|---|---|---|---|
| **oracle** | **0.0970** | — | — |
| LSZZ | 0.0582 | 16/21 | 0.0025 |
| BSZZ | 0.0578 | 18/21 | 0.0004 |
| RASZZ | 0.0395 | 18/21 | 0.0004 |
| AGSZZ | 0.0365 | 17/21 | 0.0009 |
| MASZZ | 0.0353 | 18/21 | 0.0003 |
| RSZZ | 0.0315 | 19/21 | 0.0001 |

**Oracle beats all six variants, every comparison significant after Holm correction.**

**How to explain the ordering:** the refined variants suppress false alarms by aggressive filtering, but at the cost of missing 52–73% of real defects. In a streaming setting a missed defect is not a neutral event — the model is actively trained on it as a *clean* example. Under-labelling teaches the model that buggy commits are safe. BSZZ, with 64% recall, makes the opposite trade and loses by the smallest margin.

**One caveat you must volunteer** (full detail in §7): under the *terminal* fading estimator the BSZZ comparison alone is not significant (p = 0.49). The two estimators disagree on that single row. Report both, explain that the time-averaged value is the standard prequential estimator with roughly half the variance, and treat it as primary.

### Finding 5 — WITHDRAWN: "latency is not what makes streaming hard"

**Raise this yourself, early, before anyone asks.** It is the single most important correction in the current state of the work.

**What I previously claimed:** holding the learner fixed, verification latency costs +0.009 MCC (p = 0.84, negligible) while the learner swap costs +0.096, so ~91% of the batch→stream drop is the learner and only ~9% is latency.

**Why it is wrong.** The two regimes I compared differ in *three* ways at once:

| | `chronological_online` | `prequential_latency` |
|---|---|---|
| Learning after the split | frozen | continually adapting |
| Label arrival | immediate | delayed |
| Evaluation window | 2nd half, plain MCC | whole stream, faded MCC |

The effects run in opposite directions, so they cancelled and produced a near-zero difference that looked like "latency does nothing." Matching only the evaluation window already flips the sign of that contrast, from +0.0093 to −0.0222.

**The full 2×2 that does identify them** (`experiments/run_latency_factorial.py`, all cells on an identical window, 21 projects × 10 seeds):

| MCC | Immediate labels | Delayed labels |
|---|---|---|
| **Frozen** | A 0.0827 | D 0.0781 |
| **Adaptive** | B 0.1268 | C 0.1013 |

| Contrast | HL | 95% CI | p |
|---|---|---|---|
| Adaptivity, immediate (A−B) | −0.0415 | [−0.0834, +0.0018] | 0.065 |
| Adaptivity, delayed (D−C) | −0.0146 | [−0.0440, +0.0110] | 0.393 |
| Delay, adaptive (B−C) | +0.0227 | [−0.0111, +0.0522] | 0.288 |
| Delay, frozen (A−D) | −0.0118 | [−0.0651, +0.0471] | 0.658 |
| **Interaction** | −0.0296 | [−0.0726, +0.0238] | 0.338 |

**Every interval contains zero.** Nothing here is significant.

**How to say it:**

> "I need to correct something I showed you last time. The latency decomposition wasn't identified — my two regimes differed in three ways simultaneously, not one, and the effects cancelled, which is why latency looked like nothing. I've built the full 2×2 that isolates them and run it at ten seeds. The delay penalty is estimated at about +0.02 MCC for an adaptive learner, but the interval runs from −0.01 to +0.05, and every other contrast including the interaction also spans zero. So the honest answer is that 21 paired projects cannot resolve it. That's a limitation I'll state, not a result I'll claim."

**Do not say "2.5× larger than I previously claimed."** That compares two non-significant point estimates as though the difference were informative. State the estimate with its interval and stop.

**Do not replace one unidentified claim with another.** At 10 seeds every CI crosses zero, including the interaction. The correct position is *"not resolvable at this sample size."* Offering that yourself is far stronger than being pushed to it.

**If asked what would resolve it:** more projects, not more seeds. Seed variance is already small; the limit is 21 paired observations.

## 4. The statistical tests: what they are and why these ones

Expect to be asked to justify the test choice. Here is the reasoning.

**Test: Wilcoxon signed-rank, paired at the project level (n=21).**

- *Why paired:* the same 21 projects appear in both conditions. Pairing removes between-project variance, which is enormous here (project MCCs range from −0.09 to +0.18). An unpaired test would drown the effect in that variance.
- *Why non-parametric:* MCC across 21 projects is not normally distributed — it is bounded, skewed, and has outliers (parquet-mr and commons-compress behave very differently from commons-digester). A paired t-test assumes normality of the differences; Wilcoxon assumes only symmetry, which is far safer.
- *Why the project is the unit:* seeds are not independent observations — they are repeated measurements of the same underlying project. Averaging over the 10 seeds first, then pairing on project, is the only defensible unit of analysis. **n = 21, not 210 and not 16,380.**

**Effect size: matched-pairs rank-biserial correlation**, plus the Hodges–Lehmann estimate with a bootstrap 95% CI **for that estimator** (the HL statistic is recomputed inside every resample), and the median paired difference with its own separate interval.

Earlier versions reported Cliff's δ computed all-versus-all (denominator n·m), which throws away the pairing the design deliberately preserves and the Wilcoxon test uses. The difference is large: for the regime-inflation headline, the paired rank-biserial is **+1.000** (every one of 21 projects moves the same way) where unpaired Cliff's δ read +0.74. Cliff's δ is retained in the CSV as `cliffs_delta_unpaired` so older tables stay comparable.

Thresholds for |r|: 0.1 small, 0.3 medium, 0.5 large. **Quote the Hodges–Lehmann estimate with its CI** rather than a bare mean difference — it is the location estimator that belongs with a signed-rank test. An earlier version bootstrapped the *median* difference and printed that interval beside the HL point estimate; the interval then qualified a different quantity from the one it appeared to describe. Both are now bootstrapped as themselves.

**Multiplicity: Holm-Bonferroni within test family.** See §9.

**Total: 74 tests across 5 families** (the regime-inflation family now covers all seven label sources, not a hand-picked three). **32 survive within-family Holm; 21 survive global Holm across all 74.**

**Say this unprompted: nothing was pre-registered.** The families were defined during analysis, so within-family correction is a convenience, not a principled partition. That is why a global Holm column is also reported — every headline claim survives it, which makes the family-definition question moot for the claims that matter.

---

## 5. Test family 1 — Regime inflation

**Question:** does the choice of evaluation regime change measured performance?
**Test:** naive k-fold vs chronological, paired by project, all seven label sources × two models. m = 14.

| Model | Labels | k-fold | Chrono | Hodges-Lehmann | 95% CI | rank-biserial | Holm (family) | Holm (global) |
|---|---|---|---|---|---|---|---|---|
| **JITLine** | **oracle** | 0.2430 | 0.1016 | **+0.1373** | [+0.1046, +0.1721] | **+1.000** | **1.3e-05** | **7.1e-05** |
| JITLine | LSZZ | 0.1391 | 0.0804 | +0.0667 | [+0.0149, +0.1118] | +0.792 | **0.0094** | **0.0389** |
| JITLine | RSZZ | 0.1131 | 0.0626 | +0.0515 | [+0.0287, +0.0736] | +0.706 | **0.0393** | 0.1607 |
| JITLine | BSZZ | 0.1751 | 0.1324 | +0.0549 | [+0.0248, +0.1093] | +0.558 | 0.2147 | 0.8349 |
| LApredict | oracle | 0.2058 | 0.1734 | +0.0339 | [-0.0001, +0.0856] | +0.489 | 0.4015 | 1.0000 |
| *...9 further rows, all positive* | | | | | | | | |

**How to explain this table:**

> "Three of the fourteen comparisons survive within-family correction and two survive global correction. All three are JITLine — the high-capacity model. Not one of the seven LApredict rows is significant. That is not a failure of the experiment; it *is* the result. Temporal leakage inflates models in proportion to their ability to memorise, and a one-feature logistic regression cannot memorise. The headline number is JITLine on clean oracle labels: +0.127 MCC, Cliff's delta 0.74, Holm-corrected p below 6e-06. That is as strong as a result gets at n=21."

**If asked why p = 9.5e-07 exactly:** that is the floor of the exact Wilcoxon signed-rank test at n=21 — it is 2/2²¹. The test is saturated: JITLine's k-fold score exceeded its chronological score in all 21 projects with no exceptions. Say that, it is more impressive than the p-value.

---

## 6. Test family 2 — Self-deception gap

**Question:** how much does scoring on your own noisy training labels inflate apparent performance?
**Test:** self-scored vs oracle-scored MCC, paired by project, per model × label source × regime. m = 36.

**The headline rows:**

| Model | Labels | Self | Oracle | Hodges-Lehmann | 95% CI | rank-biserial | Holm (global) |
|---|---|---|---|---|---|---|---|
| **JITLine** | **BSZZ** | 0.4129 | 0.1751 | **+0.2303** | [+0.1886, +0.2784] | +0.991 | **1.3e-04** |
| JITLine | MASZZ | 0.3295 | 0.1272 | +0.1985 | [+0.0867, +0.2720] | **+1.000** | **7.1e-05** |
| JITLine | RASZZ | 0.3070 | 0.1164 | +0.1861 | [+0.0726, +0.2666] | **+1.000** | **7.1e-05** |
| JITLine | AGSZZ | 0.3037 | 0.1164 | +0.1797 | [+0.0766, +0.2572] | **+1.000** | **7.1e-05** |
| LApredict | BSZZ | 0.3510 | 0.1941 | +0.1549 | [+0.1387, +0.2099] | +0.957 | **6.5e-04** |
| JITLine | LSZZ | 0.2434 | 0.1391 | +0.1076 | [+0.0533, +0.1572] | +0.939 | **0.0012** |

Three rows reach rank-biserial **+1.000** -- the gap held in all 21 projects.

**The critical nuance — this gap is model-dependent:**

| Variant (k-fold) | JITLine HL | JITLine Holm | LApredict HL | LApredict Holm |
|---|---|---|---|---|
| BSZZ | +0.2303 | 6.3e-05 sig | +0.1549 | 3.1e-04 sig |
| MASZZ | +0.1985 | 3.4e-05 sig | +0.0689 | 0.6439 n.s. |
| RASZZ | +0.1861 | 3.4e-05 sig | +0.0598 | 0.7110 n.s. |
| AGSZZ | +0.1797 | 3.4e-05 sig | +0.0510 | 0.9428 n.s. |
| LSZZ | +0.1076 | 5.6e-04 sig | +0.0615 | 0.5223 n.s. |
| RSZZ | +0.0647 | 0.0371 sig | **-0.0238** | 0.9714 n.s. |

**How to explain it:**

> "JITLine's self-deception gap is large and significant for all six SZZ variants. LApredict's is significant only for BSZZ. This is the same capacity story as Finding 1: memorising a heuristic's error pattern requires capacity. The Random Forest has it and uses it; the one-feature logistic regression cannot. Note the RSZZ row for LApredict is actually *negative* — training on RSZZ and scoring on RSZZ looks slightly worse than scoring on the oracle, because RSZZ's very low false-alarm rate means there is almost no systematic error pattern to exploit."

**Be prepared to volunteer this:** an earlier version of this analysis pooled JITLine and LApredict into a single test, treating the two models on the same project as independent observations. They are not — they share the project, the labels, the features and the split. Splitting the test per model both fixed the independence violation and revealed the model-dependence above, which the pooled version was hiding. Raising this yourself is much better than being asked.

---

## 7. Test family 3 — Label source gap

**Question:** under realistic streaming evaluation, does training on clean labels beat training on SZZ labels?
**Test:** ORB oracle-trained vs each SZZ-trained variant, prequential+latency, oracle-scored, paired by project. m = 6 per estimator.

**This family must be reported under both prequential estimators, because they disagree on one row.**

### Primary: time-averaged prequential MCC

| Comparison | Oracle | Variant | Δ | p | Holm p | δ | Effect | Wins |
|---|---|---|---|---|---|---|---|---|
| oracle vs RSZZ | 0.0970 | 0.0315 | +0.0655 | 0.0000 | **0.0001** | 0.710 | **large** | 19/21 |
| oracle vs MASZZ | 0.0970 | 0.0353 | +0.0617 | 0.0001 | **0.0003** | 0.674 | **large** | 18/21 |
| oracle vs AGSZZ | 0.0970 | 0.0365 | +0.0605 | 0.0004 | **0.0009** | 0.655 | **large** | 17/21 |
| oracle vs RASZZ | 0.0970 | 0.0395 | +0.0575 | 0.0001 | **0.0004** | 0.669 | **large** | 18/21 |
| **oracle vs BSZZ** | 0.0970 | 0.0578 | **+0.0392** | 0.0001 | **0.0004** | 0.451 | **medium** | **18/21** |
| oracle vs LSZZ | 0.0970 | 0.0582 | +0.0388 | 0.0025 | **0.0025** | 0.392 | medium | 16/21 |

**All six significant after Holm correction.**

### Secondary: terminal fading MCC

| Comparison | Δ | Holm p | δ | Effect |
|---|---|---|---|---|
| oracle vs MASZZ | +0.0714 | 0.0451 | 0.506 | large |
| oracle vs RSZZ | +0.0580 | 0.0426 | 0.474 | medium |
| oracle vs AGSZZ | +0.0559 | 0.0451 | 0.415 | medium |
| oracle vs RASZZ | +0.0500 | 0.0451 | 0.456 | medium |
| oracle vs LSZZ | +0.0476 | 0.0451 | 0.451 | medium |
| **oracle vs BSZZ** | +0.0118 | **0.4948** | 0.143 | **negligible** |

Five of six significant; **BSZZ is not**.

### How to explain the discrepancy — you will be asked

> "The two estimators disagree on exactly one comparison, oracle versus BSZZ. The terminal fading value is the confusion matrix at the end of the stream: with a fading factor of 0.99 the weights sum to about a hundred commits, so it summarises roughly the last hundred commits of each project — about eight positives. The time-averaged value is the mean of the metric's whole trajectory. Neither summary is canonical: MCC is not a decomposable loss, so Gama et al.'s prequential-with-fading construction does not extend to it, and of the two the terminal value is the closer analogue. The preference is empirical. Its project-level standard deviation is about half the terminal value's, 0.047 against 0.094. The BSZZ effect is real but modest, and the terminal estimator does not have the power to resolve it."

**The strongest defence is now empirical — but frame it as robustness, not as more tests.** `run_prequential_sensitivity.py` varies the fading factor across 0.90–0.999 (effective windows 10 to 1000 commits) and the warm-up skip across 0/5/10/25%.

| Across all 120 comparisons | |
|---|---|
| Hodges–Lehmann estimates with oracle ahead | **120 / 120** |
| Bootstrap CIs excluding zero | **120 / 120** |
| Surviving grid-wide Holm | **120 / 120** |

**Say "the direction and the intervals are stable across every summary choice I examined."** Do not present it as 120 new significant findings — it is one result re-examined 120 ways. Grid-wide Holm is applied and reported so the framing cannot be mistaken.

**Two further points:**

1. **It was chosen before this comparison was run under it.** The switch to time-averaging was a methodological decision made when the prequential evaluation was reviewed — the terminal value is a tail statistic — not a choice made after seeing which one gave significance.
2. **Averaging does not flatter the result.** The obvious worry is that including the model's warm-up period inflates the average. It does the opposite: mean MCC over the first 10% of the stream is **−0.039** on commons-math and **−0.012** on ant-ivy. Excluding the warm-up would push the averages *higher*. The estimator is conservative here.

Illustrative of how erratic the terminal value is: on ant-ivy it reads 0.057 against a trajectory average of 0.201, because it happened to land on a bad stretch at the end of that project's stream.

### The deliverability confound — the follow-up question

Oracle has only 67.8% `fix_ts` coverage, versus 100% for BSZZ. So does oracle win on label *quality*, or is BSZZ just handicapped by having every label delivered? Tested by imputing oracle's missing timestamps from the empirical latency distribution:

| Oracle imputed (100% fix_ts) vs BSZZ | Δ MCC | Wins | p (2-sided) | δ |
|---|---|---|---|---|
| Time-averaged estimator | **+0.0258** | **16/21** | **0.0101** | 0.293 small |
| Terminal estimator | +0.0037 | 11/21 | 0.8649 | 0.030 negligible |

> "Under the primary estimator the oracle advantage survives equalising deliverability, so the confound is bounded. Note the imputation costs the oracle something — 0.097 down to 0.084 — which makes sense: the empirical latency pool has a median of 113 days and a 90th percentile of 1,597 days, so more than half the imputed labels arrive after the 90-day window and are first delivered as *wrong clean* labels. Giving the oracle its missing labels back, at realistic delays, is close to a no-op."

### How to phrase the finding

> "Under the time-averaged prequential estimator, oracle ground truth significantly outperforms all six SZZ variants — Holm-adjusted p at most 0.0025, Cliff's delta between 0.39 and 0.71, winning 16 to 19 of 21 projects. The advantage survives equalising timestamp deliverability. We report the terminal fading value alongside, under which the BSZZ comparison alone fails to reach significance, and we treat the time-averaged value as primary because the terminal value summarises only the final hundred commits of each stream and carries roughly twice the variance."

**Why the refined variants lose by more than BSZZ:** they suppress false alarms by aggressive filtering but miss 52–73% of real defects. In a streaming setting a missed defect is not neutral — the model is actively trained on it as a *clean* example. BSZZ's high recall (64%) means it makes the opposite trade, and it loses by less.

## 8. Test families 4 & 5 — retired

These two families (`regime_effect_model_fixed`, `learner_effect_regime_fixed`) were built to decompose the batch→stream drop. They rest on the confounded contrast described in Finding 5, so **they no longer support a decomposition claim** and should not be presented as one.

They remain in `statistical_tests.csv` under `metric = mcc` because they are still valid *descriptive* comparisons between two named configurations — they simply do not isolate either effect. Their replacement is `results/phase2/latency_factorial_tests.csv`.

If asked why they are still in the CSV: they describe real configurations and removing rows after the fact is worse practice than labelling them. They are flagged exploratory like every other test.

## 9. How to explain the multiplicity correction

Expect: *"You ran 54 tests. How many would be significant by chance?"*

> "At α = 0.05 with 54 tests, you would expect about 2.7 false positives by chance. So I applied Holm-Bonferroni correction within each test family rather than across all 54 — the families answer different research questions, and correcting across unrelated questions is unnecessarily conservative. Of 54 tests, 33 are significant on raw p-values and 21 survive Holm correction. Both numbers are reported, and every table shows the raw and adjusted p side by side."

**Why within-family rather than globally:** the five families map to distinct questions — does regime matter, does scoring convention matter, does label source matter, does the learner matter, does latency matter. A finding in one family is not evidence for or against a finding in another. Correcting globally would inflate the correction for no inferential benefit. State that you also computed Benjamini-Hochberg FDR-adjusted values (`p_bh` in the CSV) and that the conclusions are the same under both.

**If challenged that even within-family is too lenient:** the two headline findings survive Holm correction applied across *all* 54 tests, not just within family. Have that ready — it makes the challenge moot.

---

## 10. Anticipated questions and honest answers

**Q1. "Your best MCC under realistic conditions is 0.07. Is JIT defect prediction useless?"**

> "0.0685 is the terminal fading-window value, which summarises only the last hundred commits or so of each stream. Using the standard time-averaged prequential estimator it is 0.097, and I report both, treating the averaged value as primary. But the more important point is the comparison, not the absolute number. Published results in the 0.35–0.45 range come from random k-fold on self-scored SZZ labels — I can reproduce those numbers exactly by evaluating dishonestly, and I show the decomposition: 0.418 self-scored k-fold, 0.170 oracle-scored k-fold, 0.103 oracle-scored chronological. The contribution is the measurement of that inflation, not a new state of the art."

**Q2. "Why does BSZZ beat the oracle for JITLine? Doesn't that undermine your whole premise?"**

> "It doesn't, but I want to be precise about what I can and can't claim. The effect is real — 97.7% of the between-project variance is genuine rather than seed noise, and it survives three threshold protocols. The natural explanation is class-imbalance relief: the corpus is 8.5% defective, oracle training leaves the forest about 40 positives per split, and BSZZ's 29.5% positive rate supplies more minority mass even though most of it is wrong. But I tested nine project-level predictors of where BSZZ wins and none is significant, and opennlp is a large BSZZ win where BSZZ actually flags *fewer* commits than the oracle — so augmentation cannot be the mechanism there. I report the phenomenon and leave the mechanism open. Critically it is batch-only: under streaming, oracle beats BSZZ in 18 of 21 projects, so it says something about how batch learners handle imbalance, not about label quality."

**Q3. "Is the JITLine anomaly just a decision-threshold artifact?"**

> "I tested exactly that. I compared three threshold-selection protocols across 21 projects × 3 seeds: the original tail-tuned one, out-of-bag tuning, and chronologically blocked cross-validation. The gap persists in all three — +0.034, +0.034, +0.028 — with BSZZ winning 13, 15 and 12 of 21 projects respectively. It is not a threshold artifact. Incidentally, out-of-bag tuning, which was my first instinct, turned out to be the worst of the three: it doubled the rate of degenerate all-one-class predictions, because OOB probabilities come from only ~63% of the trees and are miscalibrated against the full ensemble used at prediction time. I switched to blocked cross-validation on the evidence."

**Q4. "Why these three models and not DeepJIT or CC2Vec?"**

> "Recent benchmarks — Zeng et al., Zhao et al. — show deep JIT models rarely beat simple baselines once time-aware splits are enforced, and my Finding 1 shows exactly the mechanism: leakage inflates high-capacity models most. Adding a deep model would add compute and another inflation confound without changing the argument. ORB is the canonical streaming learner designed for verification latency, so it is the right choice for the online arm."

**Q5. "How do you know your ORB implementation is correct?"**

> "I replicated Cabral et al. 2019 on their own 14 datasets across 10 seeds: G-mean 0.46 to 0.93, mean 0.68, squarely in the published range. That is in `results/replication/`. One caveat I should state myself: those datasets run at 22–43% defect ratio, while my corpus is 8.5%. So the replication validates the implementation but at a very different imbalance regime."

**Q6. "n = 21 is small. Are you sure about any of this?"**

> "For the two headline findings, yes — they are saturated exact tests, meaning the effect held in all 21 projects with no exceptions, which is the strongest outcome the test can produce. For the borderline results I am explicitly not claiming significance: the oracle-versus-BSZZ comparison at p = 0.49 and the latency effect at p = 0.84 are reported as non-significant, and I describe the latency result as 'no detectable effect at this sample size' rather than 'no effect.'"

**Q7. "You report two different MCC estimators and they disagree. Isn't that convenient?"**

> "They disagree on exactly one of the 74 comparisons — oracle versus BSZZ — so it is not a case of one estimator rewriting the results. The time-averaged value is what I report as primary, but not because it is canonical: MCC is not a decomposable loss, so Gama's construction does not extend to it and neither summary is standard; the terminal fading value summarises only the last hundred commits of each stream and has about twice the project-level variance. I made that choice on methodological grounds before running this comparison under it, not after seeing which gave significance. And the obvious objection — that averaging inflates results by including the model's warm-up — is backwards: mean MCC over the first 10% of the stream is negative, around −0.04, so averaging is conservative here. I report both estimators in `statistical_tests.csv` precisely so the reader can check that."

**Q8. "Are the 21 projects comparable?"**

> "No, and that is a limitation I have not yet fully addressed. They range from 544 to 4,026 commits and 1.8% to 19.3% defect rate. commons-digester trains on five positive examples in the chronological split and contributes equally to the unweighted mean as commons-math's 196. The per-project table goes in the appendix, and a robustness check excluding projects below a positive-count floor is outstanding work."

---

## 11. What to say about the label-vintage bug

Do not hide it and do not lead with it. If Phase 2 numbers changed since the last time they saw them, explain why before they notice.

> "One thing I should flag. When I audited the pipeline I found that my Phase 2 dataset cache had gone stale relative to a Phase 1 label regeneration — Phase 2 had trained on labels one commit older than the noise rates I was reporting, affecting between 1% and 6.5% of commits per variant. The Phase 1 numbers were always correct; only the downstream dataset was stale. I traced it to an unguarded cache in the data loader, fixed it, added a provenance record and a consistency assertion that now runs in CI before any compute is spent, and re-ran the full grid. The qualitative findings all held. Two numbers moved in ways worth knowing: the self-deception gap got larger, and the oracle-versus-BSZZ comparison got weaker — which is why I am no longer claiming it."

**The framing that makes this a strength:** a thesis about how fragile SZZ label provenance is, which then ships an automated provenance assertion because its own pipeline desynchronised, is a more credible artifact than one that never hit the problem. That is not spin — it is the same failure mode the thesis studies, observed in the wild.

---

## 12. Numbers cheat-sheet

Keep this visible during the meeting.

**Scale:** 16,380 records · 21 projects · 10 seeds · 7 label sources · 3 models · 4 regime-scoring combinations · 66 statistical tests (54 terminal-estimator, 12 time-averaged)

**The four numbers to memorise:**

| | Value |
|---|---|
| Regime inflation (JITLine, oracle, k-fold → chronological) | **HL +0.137**, CI [+0.105,+0.172], rank-biserial +1.000 (21/21), global Holm 7.1e-05, δ = 0.74 |
| Self-deception gap (JITLine, BSZZ, k-fold) | **HL +0.230**, CI [+0.189,+0.278], rank-biserial +0.991, global Holm 1.3e-04, δ = 0.955 |
| Label quality (ORB, oracle vs all six variants, time-averaged) | **all six significant**, Holm p ≤ 0.0025, δ 0.39–0.71 |
| ~~Latency effect~~ | **WITHDRAWN** — contrast not identified. Preliminary 2×2: latency +0.023 (p = 0.34), adaptivity −0.046 (p = 0.11), 3 seeds, neither significant |

**Key MCCs, oracle-scored:**

| Configuration | MCC |
|---|---|
| JITLine, BSZZ labels, k-fold, **self-scored** (the literature's number) | 0.4129 |
| JITLine, oracle, k-fold | 0.2430 |
| LApredict, oracle, chronological | 0.1734 |
| JITLine, BSZZ, chronological | 0.1324 |
| JITLine, oracle, chronological | 0.1016 |
| ORB, oracle, chronological-online | 0.0777 |
| **ORB, oracle, prequential + real latency** | **0.0970 time-averaged** / 0.0685 terminal |
| ORB, BSZZ, prequential + real latency | 0.0578 time-averaged / 0.0566 terminal |
| ORB, MASZZ, prequential + real latency | 0.0353 time-averaged / −0.0030 terminal |

**Test counts:** 74 total · **32 survive within-family Holm · 21 survive global Holm** · nothing pre-registered, all exploratory

**Estimator robustness:** 20/20 fading × warm-up combinations give oracle beating all six variants, worst p = 0.0080

**Threshold protocol:** forward-chaining (only looks backwards). Anomaly survives all four protocols tried

**Effect sizes:** matched-pairs rank-biserial (|r| 0.1 small · 0.3 medium · 0.5 large), reported with Hodges–Lehmann estimate and bootstrap 95% CI. Unpaired Cliff's δ retained only for comparability with older tables.

**Latency facts:** 8,819 commits linked to a fix · median latency 113 days · p90 1,597 days · **53.0% of defect labels arrive after the W=90-day window**

**Deliverability check:** oracle has 67.8% fix_ts coverage vs BSZZ's 100%. With oracle imputed to 100% from the empirical latency distribution, oracle still wins: **+0.026 MCC, 16/21 projects, p = 0.010** (time-averaged).

**Things to say carefully:**
- ✅ "Oracle outperforms all six SZZ variants" — **true under the time-averaged estimator**, Holm p ≤ 0.0025. Add: "under the terminal fading estimator the BSZZ comparison alone is not significant; I report both and treat the averaged value as primary."
- ✗ "Latency accounts for only ~9% of the streaming drop" → **withdrawn**, the contrast changed learner + label timing + evaluation window at once
- ✗ Quoting the preliminary 2×2 numbers as results → 3 seeds, neither effect significant
- ✗ "n = 16,380" → the statistical unit is n = 21 projects
- ✗ "Self-scoring inflates all models" → it inflates JITLine for all six variants, LApredict only for BSZZ
- ✗ "FP-heavy noise acts as minority augmentation" stated as fact → the phenomenon is real (13/21, stable across seeds) but the mechanism is unconfirmed: nine predictors all non-significant, and opennlp is a large BSZZ win with *fewer* BSZZ positives than oracle. Say "consistent with class-imbalance relief, mechanism open."
- ✗ Presenting the JITLine anomaly as a general result → it is batch-only; under streaming oracle beats BSZZ 18/21
- ✗ Quoting a single MCC without naming the estimator → always say "terminal" or "time-averaged"

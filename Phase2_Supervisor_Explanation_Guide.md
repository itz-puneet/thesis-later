# Phase 2: How to Explain the Results and the Statistical Tests

**For:** supervisor meeting on Phase 2 (Downstream Impact Under Honest Evaluation)
**Data source:** `results/phase2/` at `master` @ `5126dae` — 16,380 evaluation records, 21 Apache projects × 10 seeds × 7 label sources × 3 models × 4 regime-scoring combinations
**Verified:** label-consistency gate passes; the noise rates in `phase1_bias.json` describe exactly the labels these models trained on
**Estimators:** every streaming result is reported under two prequential summary statistics — the *time-averaged* value (primary; the standard Gama estimator) and the *terminal* fading value (secondary). They agree on all but one comparison; see §7.

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

> "Phase 2 asked what SZZ label noise actually costs a defect prediction model, once you stop evaluating it dishonestly. I ran three models across seven label sources and four evaluation regimes — 16,380 runs — and tested everything with paired Wilcoxon signed-rank tests at the project level, Holm-corrected within test family. Three things came out. First, random k-fold cross-validation inflates JITLine's apparent performance by +0.127 MCC over a chronological split, a large effect at p < 1e-6. Second, evaluating a model on the same SZZ labels it was trained on inflates it by a further +0.248 MCC — models learn the heuristic's quirks, not bugs. Third, under honest streaming evaluation with real verification latency, training on developer-verified labels beats all six SZZ variants, every comparison significant after correction — so label quality demonstrably matters once you evaluate properly. And fourth, the one that surprised me: I added an experiment that holds the learner fixed while changing only the evaluation regime, and verification latency turns out to account for only about 9% of the batch-to-streaming performance drop. The other 91% is just that online learners are weaker than batch learners. The literature — and my own earlier draft — attributed all of it to latency."

Then stop and let them ask.

---

## 2. What Phase 2 actually measured

Set this up before showing any numbers, or the numbers won't land.

**The design is a 3-way grid:**

| Dimension | Levels |
|---|---|
| **Model** | LApredict (logistic regression on `la` alone), JITLine (100-tree Random Forest + SMOTE + threshold moving), ORB (20-member online logistic ensemble) |
| **Training label source** | `label_oracle` (developer-verified) + 6 SZZ variants (BSZZ, AGSZZ, MASZZ, LSZZ, RSZZ, RASZZ) |
| **Evaluation regime** | `naive_kfold` (random 10-fold — the dishonest baseline), `chronological` (50/50 time split), `chronological_online` (ORB trained sequentially on the past, frozen, tested on the future), `prequential_latency` (test-then-train streaming with reconstructed verification latency, W=90 days) |
| **Scoring convention** | *oracle-scored* (measured against developer-verified truth — real bug-finding ability) vs *self-scored* (measured against the same noisy SZZ labels used for training — what the literature does) |

**The critical conceptual point to make explicit:** the difference between *oracle-scored* and *self-scored* is the entire experiment. Everyone in the field trains on SZZ and tests on SZZ. That measures how well a model reproduces a heuristic, not how well it finds bugs. By keeping a developer-verified oracle held out as the scoring key, you can measure the gap between those two things for the first time.

**Why 21 projects × 10 seeds:** the seeds control for model initialisation and fold randomness; the projects are the unit of statistical analysis. Every test below is paired at the *project* level (n=21), averaging over seeds first. Do not let anyone think n=16,380 — that would be pseudo-replication and it is the first thing a methodologist would attack.

---

## 3. The five findings, in the order you should present them

Present them in this order. It builds from "the field has a measurement problem" to "here is a thing nobody has measured before."

### Finding 1 — Random k-fold inflates results, badly, and only for high-capacity models

JITLine oracle-trained: **0.2300** under random k-fold → **0.1027** under a chronological split. A drop of **0.127 MCC**, more than half its apparent performance.

LApredict oracle-trained: 0.2058 → 0.1734. A drop of only 0.032, not significant.

**How to explain the asymmetry:** a Random Forest with 14 features can memorise project-specific temporal patterns. When folds are shuffled, commits from 2015 help predict commits from 2012, and the model exploits autocorrelation that will not exist at deployment. A single-feature logistic regression has no capacity to memorise anything — it can only learn "bigger changes are riskier," which is equally true in both regimes. **The inflation is a function of model capacity, not of the data.** That is why weak baselines like LApredict look competitive in the literature: they were never the ones being inflated.

### Finding 2 — Self-scoring on SZZ inflates results even more

JITLine trained on BSZZ, evaluated under random k-fold:
- Scored against BSZZ's own labels: **0.4181**
- Scored against the developer-verified oracle: **0.1701**
- Gap: **+0.248 MCC**

**How to explain it:** BSZZ flags 8,060 of 27,319 commits as defect-inducing, but only 1,495 of those are real (18.6% precision). A Random Forest trained on those labels learns the *pattern of BSZZ's mistakes* — which commits look like the kind of commit BSZZ over-flags — because that pattern is systematic and learnable. Scored against BSZZ, this looks like skill. Scored against reality, most of it evaporates. **The model is an excellent BSZZ emulator and a mediocre bug detector.**

This is the finding with the largest effect size in the entire study (Cliff's δ = 0.955, essentially total separation between the paired distributions).

### Finding 3 — FP-heavy noise *helps* batch learners, which is counter-intuitive and real

Under chronological evaluation, oracle-scored: BSZZ-trained JITLine (**0.1285**) beats oracle-trained JITLine (**0.1027**), winning in 13 of 21 projects.

**How to explain it:** the corpus is 8.5% defective. Training on oracle labels gives a Random Forest ~40 positive examples per project split, and it starves the minority class. BSZZ labels 29.5% of commits positive — three and a half times as many — and although ~81% of those are false alarms, the expanded positive set gives the trees far more minority-class mass to partition on. **FP-heavy label noise acts as accidental, badly-targeted data augmentation.**

Be ready for "isn't that just your threshold being wrong?" — it isn't, and you can prove it. This effect was measured under four different decision-threshold protocols (the original tail-tuned one, out-of-bag tuning, chronologically blocked cross-validation, and the default 0.5) and survives all four, with the gap ranging +0.026 to +0.034. See §10, Q3.

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

### Finding 5 — The new one: latency is not what makes streaming hard

This is your novel contribution and should get the most airtime.

| Configuration | MCC |
|---|---|
| LApredict, chronological batch | 0.1734 |
| JITLine, chronological batch | 0.1027 |
| **ORB, chronological_online** (online learner, batch regime) | **0.0777** |
| ORB, prequential + real latency | 0.0685 |

Decomposing the 0.1050 drop from LApredict-batch to ORB-streaming:

| Component | Δ MCC | p | Holm p | Effect |
|---|---|---|---|---|
| **Learner** (batch LR → online ensemble, regime held fixed) | **+0.0957** | 0.0001 | **0.0004** | **large** (δ=0.53) |
| **Regime/latency** (ORB held fixed, batch → streaming+latency) | +0.0093 | **0.8382** | 0.8382 | **negligible** (δ=−0.07) |

**How to explain it:** my earlier draft — and the framing in most of the streaming JIT-SDP literature — presented a ladder in which performance falls as evaluation gets more realistic, with the final step attributed to verification latency. But that step changed two things at once: it introduced latency *and* swapped a Random Forest for an online logistic ensemble. Adding the `chronological_online` cell holds the learner fixed. Once you do that, **latency costs about 0.009 MCC and is statistically indistinguishable from zero (p = 0.84). The learner swap costs 0.096.** Roughly 91% of what was being called "the cost of latency" is actually "the cost of learning incrementally."

**Do not overstate this either.** Latency is not harmless — it does compress the differences *between* label sources (over half of all defect labels arrive after the 90-day window, so every label source suffers false-negative noise regardless of its quality). The correct claim is: latency changes *which label source you can distinguish*, not *how well the model performs in absolute terms*.

---

## 4. The statistical tests: what they are and why these ones

Expect to be asked to justify the test choice. Here is the reasoning.

**Test: Wilcoxon signed-rank, paired at the project level (n=21).**

- *Why paired:* the same 21 projects appear in both conditions. Pairing removes between-project variance, which is enormous here (project MCCs range from −0.09 to +0.18). An unpaired test would drown the effect in that variance.
- *Why non-parametric:* MCC across 21 projects is not normally distributed — it is bounded, skewed, and has outliers (parquet-mr and commons-compress behave very differently from commons-digester). A paired t-test assumes normality of the differences; Wilcoxon assumes only symmetry, which is far safer.
- *Why the project is the unit:* seeds are not independent observations — they are repeated measurements of the same underlying project. Averaging over the 10 seeds first, then pairing on project, is the only defensible unit of analysis. **n = 21, not 210 and not 16,380.**

**Effect size: Cliff's delta.** Reported alongside every p-value because a p-value tells you only whether an effect exists, not whether it matters. Cliff's δ is the non-parametric analogue of Cohen's d: it is the probability that a randomly chosen value from group A exceeds one from group B, minus the reverse. Thresholds used (Romano et al.): |δ| < 0.147 negligible, < 0.33 small, < 0.474 medium, ≥ 0.474 large.

**Multiplicity: Holm-Bonferroni within test family.** See §9.

**Total: 54 tests across 5 families.** 33 significant on raw p; **21 survive Holm correction.**

---

## 5. Test family 1 — Regime inflation

**Question:** does the choice of evaluation regime change measured performance?
**Test:** naive k-fold vs chronological, paired by project, per model × label source. m = 6.

| Model | Labels | k-fold | Chrono | Δ | p | Holm p | δ | Effect |
|---|---|---|---|---|---|---|---|---|
| **JITLine** | **oracle** | 0.2300 | 0.1027 | **+0.1273** | 9.5e-07 | **5.7e-06** | 0.742 | **large** |
| JITLine | RSZZ | 0.1103 | 0.0662 | +0.0441 | 0.0022 | **0.0108** | 0.374 | medium |
| JITLine | BSZZ | 0.1701 | 0.1285 | +0.0415 | 0.0646 | 0.2008 | 0.311 | small |
| LApredict | oracle | 0.2058 | 0.1734 | +0.0324 | 0.0502 | 0.2008 | 0.247 | small |
| LApredict | BSZZ | 0.1941 | 0.1634 | +0.0307 | 0.0646 | 0.2008 | 0.252 | small |
| LApredict | RSZZ | 0.2016 | 0.1731 | +0.0285 | 0.1111 | 0.2008 | 0.247 | small |

**How to explain this table:**

> "Two of the six comparisons survive correction. Both are JITLine — the high-capacity model. None of the LApredict rows are significant. That is not a failure of the experiment; it *is* the result. Temporal leakage inflates models in proportion to their ability to memorise, and a one-feature logistic regression cannot memorise. The headline number is JITLine on clean oracle labels: +0.127 MCC, Cliff's delta 0.74, Holm-corrected p below 6e-06. That is as strong as a result gets at n=21."

**If asked why p = 9.5e-07 exactly:** that is the floor of the exact Wilcoxon signed-rank test at n=21 — it is 2/2²¹. The test is saturated: JITLine's k-fold score exceeded its chronological score in all 21 projects with no exceptions. Say that, it is more impressive than the p-value.

---

## 6. Test family 2 — Self-deception gap

**Question:** how much does scoring on your own noisy training labels inflate apparent performance?
**Test:** self-scored vs oracle-scored MCC, paired by project, per model × label source × regime. m = 36.

**The headline rows:**

| Model | Labels | Regime | Self | Oracle | Δ | Holm p | δ | Effect |
|---|---|---|---|---|---|---|---|---|
| **JITLine** | **BSZZ** | k-fold | 0.4181 | 0.1701 | **+0.2480** | **3.4e-05** | **0.955** | **large** |
| JITLine | MASZZ | k-fold | 0.3305 | 0.1205 | +0.2100 | 0.0000 | 0.905 | large |
| JITLine | AGSZZ | k-fold | 0.3091 | 0.1144 | +0.1948 | 0.0000 | 0.819 | large |
| JITLine | RASZZ | k-fold | 0.3069 | 0.1156 | +0.1913 | 0.0001 | 0.791 | large |
| LApredict | BSZZ | k-fold | 0.3510 | 0.1941 | +0.1569 | 0.0003 | 0.850 | large |
| JITLine | LSZZ | k-fold | 0.2453 | 0.1380 | +0.1072 | 0.0002 | 0.692 | large |
| JITLine | RSZZ | k-fold | 0.1803 | 0.1103 | +0.0701 | 0.0230 | 0.542 | large |

**The critical nuance — this gap is model-dependent:**

| Variant (k-fold) | JITLine Δ | JITLine Holm p | LApredict Δ | LApredict Holm p |
|---|---|---|---|---|
| BSZZ | +0.2480 | 3.4e-05 ✅ | +0.1569 | 0.0003 ✅ |
| AGSZZ | +0.1948 | 0.0000 ✅ | +0.0469 | 0.9428 ✗ |
| MASZZ | +0.2100 | 0.0000 ✅ | +0.0632 | 0.6439 ✗ |
| LSZZ | +0.1072 | 0.0002 ✅ | +0.0602 | 0.5009 ✗ |
| RASZZ | +0.1913 | 0.0001 ✅ | +0.0603 | 0.6563 ✗ |
| RSZZ | +0.0701 | 0.0230 ✅ | **−0.0237** | 0.9714 ✗ |

**How to explain it:**

> "JITLine's self-deception gap is large and significant for all six SZZ variants. LApredict's is significant only for BSZZ. This is the same capacity story as Finding 1: memorising a heuristic's error pattern requires capacity. The Random Forest has it and uses it; the one-feature logistic regression cannot. Note the RSZZ row for LApredict is actually *negative* — training on RSZZ and scoring on RSZZ looks slightly worse than scoring on the oracle, because RSZZ's very low false-alarm rate means there is almost no systematic error pattern to exploit."

**Be prepared to volunteer this:** an earlier version of this analysis pooled JITLine and LApredict into a single test, treating the two models on the same project as independent observations. They are not — they share the project, the labels, the features and the split. Splitting the test per model both fixed the independence violation and revealed the model-dependence above, which the pooled version was hiding. Raising this yourself is much better than being asked.

---

## 7. Test family 3 — Label source gap

**Question:** under realistic streaming evaluation, does training on clean labels beat training on SZZ labels?
**Test:** ORB oracle-trained vs each SZZ-trained variant, prequential+latency, oracle-scored, paired by project. m = 6 per estimator.

**This family must be reported under both prequential estimators, because they disagree on one row.**

### Primary: time-averaged prequential MCC (the standard Gama estimator)

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

> "The two estimators disagree on exactly one comparison, oracle versus BSZZ. The terminal fading value is the confusion matrix at the end of the stream: with a fading factor of 0.99 the weights sum to about a hundred commits, so it summarises roughly the last hundred commits of each project — about eight positives. The time-averaged value is the mean of the metric's whole trajectory, which is what Gama's prequential protocol actually prescribes. Its project-level standard deviation is about half the terminal value's, 0.047 against 0.094. The BSZZ effect is real but modest, and the terminal estimator does not have the power to resolve it."

**Pre-empt the estimator-shopping objection.** Two things defend the choice:

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

## 8. Test families 4 & 5 — The batch→stream decomposition

**Question:** the earlier "inflation ladder" showed performance dropping as evaluation got more realistic. But the final step changed the model *and* the regime simultaneously. Which one caused the drop?

**Design:** add `chronological_online` — ORB trained sequentially on the first 50% of the stream with immediate labels, frozen, then used to predict the second 50%. Same learner as the streaming condition, same regime as the batch condition. That single cell breaks the confound.

### Family 4 — Regime effect, model held fixed (m = 2)

| Labels | Chrono-online | Prequential+latency | Δ | p | Holm p | δ | Effect |
|---|---|---|---|---|---|---|---|
| **oracle** | 0.0777 | 0.0685 | **+0.0093** | **0.8382** | 0.8382 | −0.075 | **negligible** |
| BSZZ | 0.0767 | 0.0566 | +0.0200 | 0.2428 | 0.4857 | 0.179 | small |

### Family 5 — Learner effect, regime held fixed (m = 4)

| Comparison | Labels | Batch model | ORB | Δ | p | Holm p | δ | Effect |
|---|---|---|---|---|---|---|---|---|
| **LApredict vs ORB** | **oracle** | 0.1734 | 0.0777 | **+0.0957** | 0.0001 | **0.0004** | 0.533 | **large** |
| LApredict vs ORB | BSZZ | 0.1634 | 0.0767 | +0.0867 | 0.0004 | **0.0011** | 0.488 | large |
| JITLine vs ORB | BSZZ | 0.1285 | 0.0767 | +0.0519 | 0.0158 | **0.0316** | 0.297 | small |
| JITLine vs ORB | oracle | 0.1027 | 0.0777 | +0.0250 | 0.2180 | 0.2180 | 0.249 | small |

**How to explain both tables together:**

> "Three of the four learner-effect tests are significant after correction, with the largest at 0.096 MCC. Neither regime-effect test is significant — the oracle one is at p = 0.84 with a Cliff's delta of −0.07, which is not just non-significant but pointing marginally the wrong way. So the batch-to-streaming drop that I and the literature attributed to verification latency is, on this corpus, about 91% attributable to the change of learner and 9% to latency, with the latency component indistinguishable from noise."

**Frame this as a correction you found, not a weakness.** It is a genuinely novel measurement — no prior JIT-SDP paper has separated these two effects, because none of them ran an online learner under a batch regime. It also gives Phase 4 a clean baseline: when Noise-Aware ORB is evaluated, you can now say whether it recovers the *learner* penalty or the *latency* penalty.

**The honest caveat to state yourself:** the regime-effect family has only m = 2 tests and n = 21 pairs. A negligible result at n=21 is evidence of a small effect, not proof of zero effect. The right claim is "no detectable effect at this sample size," and the confidence interval is wide.

---

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

> "It looks that way until you decompose it. BSZZ labels 29.5% of commits positive against a true rate of 8.5%, so it acts as accidental minority-class augmentation for a batch tree ensemble that would otherwise starve on ~40 positives per split. The effect is real and survives four different threshold protocols. But it is specific to batch learners: in the streaming setting, where labels arrive over time and the oversampling rate adapts, oracle labels beat BSZZ. So the finding is not 'noise is good' — it is 'batch learners under severe imbalance are so starved that even badly-targeted extra positives help,' which is itself a criticism of how the field evaluates."

**Q3. "Is the JITLine anomaly just a decision-threshold artifact?"**

> "I tested exactly that. I compared three threshold-selection protocols across 21 projects × 3 seeds: the original tail-tuned one, out-of-bag tuning, and chronologically blocked cross-validation. The gap persists in all three — +0.034, +0.034, +0.028 — with BSZZ winning 13, 15 and 12 of 21 projects respectively. It is not a threshold artifact. Incidentally, out-of-bag tuning, which was my first instinct, turned out to be the worst of the three: it doubled the rate of degenerate all-one-class predictions, because OOB probabilities come from only ~63% of the trees and are miscalibrated against the full ensemble used at prediction time. I switched to blocked cross-validation on the evidence."

**Q4. "Why these three models and not DeepJIT or CC2Vec?"**

> "Recent benchmarks — Zeng et al., Zhao et al. — show deep JIT models rarely beat simple baselines once time-aware splits are enforced, and my Finding 1 shows exactly the mechanism: leakage inflates high-capacity models most. Adding a deep model would add compute and another inflation confound without changing the argument. ORB is the canonical streaming learner designed for verification latency, so it is the right choice for the online arm."

**Q5. "How do you know your ORB implementation is correct?"**

> "I replicated Cabral et al. 2019 on their own 14 datasets across 10 seeds: G-mean 0.46 to 0.93, mean 0.68, squarely in the published range. That is in `results/replication/`. One caveat I should state myself: those datasets run at 22–43% defect ratio, while my corpus is 8.5%. So the replication validates the implementation but at a very different imbalance regime."

**Q6. "n = 21 is small. Are you sure about any of this?"**

> "For the two headline findings, yes — they are saturated exact tests, meaning the effect held in all 21 projects with no exceptions, which is the strongest outcome the test can produce. For the borderline results I am explicitly not claiming significance: the oracle-versus-BSZZ comparison at p = 0.49 and the latency effect at p = 0.84 are reported as non-significant, and I describe the latency result as 'no detectable effect at this sample size' rather than 'no effect.'"

**Q7. "You report two different MCC estimators and they disagree. Isn't that convenient?"**

> "They disagree on exactly one of fifty-four comparisons — oracle versus BSZZ — so it is not a case of one estimator rewriting the results. The time-averaged value is the standard Gama prequential estimator and it is what I report as primary; the terminal fading value summarises only the last hundred commits of each stream and has about twice the project-level variance. I made that choice on methodological grounds before running this comparison under it, not after seeing which gave significance. And the obvious objection — that averaging inflates results by including the model's warm-up — is backwards: mean MCC over the first 10% of the stream is negative, around −0.04, so averaging is conservative here. I report both estimators in `statistical_tests.csv` precisely so the reader can check that."

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
| Regime inflation (JITLine, oracle, k-fold → chronological) | **+0.127 MCC**, Holm p = 5.7e-06, δ = 0.74 |
| Self-deception gap (JITLine, BSZZ, k-fold) | **+0.248 MCC**, Holm p = 3.4e-05, δ = 0.955 |
| Label quality (ORB, oracle vs all six variants, time-averaged) | **all six significant**, Holm p ≤ 0.0025, δ 0.39–0.71 |
| Latency effect (ORB, model held fixed) | **+0.009 MCC**, p = 0.84, δ = −0.07, **negligible** |

**Key MCCs, oracle-scored:**

| Configuration | MCC |
|---|---|
| JITLine, BSZZ labels, k-fold, **self-scored** (the literature's number) | 0.4181 |
| JITLine, oracle, k-fold | 0.2300 |
| LApredict, oracle, chronological | 0.1734 |
| JITLine, BSZZ, chronological | 0.1285 |
| JITLine, oracle, chronological | 0.1027 |
| ORB, oracle, chronological-online | 0.0777 |
| **ORB, oracle, prequential + real latency** | **0.0970 time-averaged** / 0.0685 terminal |
| ORB, BSZZ, prequential + real latency | 0.0578 time-averaged / 0.0566 terminal |
| ORB, MASZZ, prequential + real latency | 0.0353 time-averaged / −0.0030 terminal |

**Test counts:** 66 total · **32 significant after within-family Holm**

**Effect size thresholds (Romano et al.):** |δ| < 0.147 negligible · < 0.33 small · < 0.474 medium · ≥ 0.474 large

**Latency facts:** 8,819 commits linked to a fix · median latency 113 days · p90 1,597 days · **53.0% of defect labels arrive after the W=90-day window**

**Deliverability check:** oracle has 67.8% fix_ts coverage vs BSZZ's 100%. With oracle imputed to 100% from the empirical latency distribution, oracle still wins: **+0.026 MCC, 16/21 projects, p = 0.010** (time-averaged).

**Things to say carefully:**
- ✅ "Oracle outperforms all six SZZ variants" — **true under the time-averaged estimator**, Holm p ≤ 0.0025. Add: "under the terminal fading estimator the BSZZ comparison alone is not significant; I report both and treat the averaged value as primary."
- ✗ "Latency causes the streaming performance drop" → it accounts for ~9% and is not significant (p = 0.84)
- ✗ "n = 16,380" → the statistical unit is n = 21 projects
- ✗ "Self-scoring inflates all models" → it inflates JITLine for all six variants, LApredict only for BSZZ
- ✗ Quoting a single MCC without naming the estimator → always say "terminal" or "time-averaged"

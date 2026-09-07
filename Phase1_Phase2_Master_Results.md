# Phase 1 & Phase 2 — Master Results

**Single source of truth for every current number.** Supersedes all earlier result tables.

| | |
|---|---|
| **Commit** | `master` @ `5126dae` |
| **Corpus** | 21 Apache Java projects, 27,319 commits, 2,332 developer-verified defective (8.54%) |
| **Phase 2 scale** | 16,380 evaluation records = 21 projects × 10 seeds × 13 label/scoring cells × 6 model-regime combinations |
| **Statistical unit** | **n = 21 projects** (seeds averaged first). Never n = 16,380. |
| **Tests** | 66 paired Wilcoxon signed-rank + Cliff's δ, Holm/BH-corrected within (family, estimator). 32 significant after Holm. |
| **Integrity** | Label-consistency gate passes — `phase1_bias.json` describes exactly the labels Phase 2 trained on. Enforced in CI before any compute. |

**Two prequential estimators are reported throughout.** *Time-averaged* (primary — the standard Gama estimator, mean of the metric's trajectory) and *terminal fading* (secondary — the fading confusion matrix at end of stream, effective window ≈ 100 commits). They agree on all but one comparison; see §6.

---

## Contents

1. [Phase 1 — SZZ label quality](#1-phase-1--szz-label-quality)
2. [Phase 2 — the full results matrix](#2-phase-2--the-full-results-matrix)
3. [The inflation ladder](#3-the-inflation-ladder)
4. [Test family 1 — regime inflation](#4-test-family-1--regime-inflation)
5. [Test family 2 — self-deception gap](#5-test-family-2--self-deception-gap)
6. [Test family 3 — label source gap](#6-test-family-3--label-source-gap)
7. [Test families 4 & 5 — batch→stream decomposition](#7-test-families-4--5--batchstream-decomposition)
8. [Verification latency and the deliverability confound](#8-verification-latency-and-the-deliverability-confound)
9. [Per-project characteristics](#9-per-project-characteristics)
10. [Headline claims, ranked by strength](#10-headline-claims-ranked-by-strength)

---

## 1. Phase 1 — SZZ label quality

Every SZZ variant scored against the developer-verified oracle over an identical 27,319-commit denominator. **These numbers are unchanged throughout the entire remediation** — Phase 1 was always correct.

| Variant | Precision | Recall | F1 | ρ₀ (FPR) | ρ₁ (FNR) | MCC | κ | TP | FP | FN | TN |
|---|---|---|---|---|---|---|---|---|---|---|---|
| **BSZZ** | 0.1855 | **0.6411** | 0.2877 | 0.2627 | **0.3589** | **0.2318** | 0.1790 | 1,495 | 6,565 | 837 | 18,422 |
| AGSZZ | 0.1855 | 0.4674 | 0.2656 | 0.1915 | 0.5326 | 0.1876 | 0.1633 | 1,090 | 4,786 | 1,242 | 20,201 |
| MASZZ | 0.1826 | 0.4820 | 0.2649 | 0.2013 | 0.5180 | 0.1877 | 0.1610 | 1,124 | 5,030 | 1,208 | 19,957 |
| **LSZZ** | **0.2720** | 0.2667 | 0.2693 | **0.0666** | 0.7333 | 0.2019 | **0.2019** | 622 | 1,665 | 1,710 | 23,322 |
| RSZZ | 0.2318 | 0.2997 | 0.2615 | 0.0927 | 0.7003 | 0.1846 | 0.1828 | 699 | 2,316 | 1,633 | 22,671 |
| RASZZ | 0.1840 | 0.4383 | 0.2592 | 0.1813 | 0.5617 | 0.1784 | 0.1580 | 1,022 | 4,531 | 1,310 | 20,456 |

![Phase 1 noise profile](reports/figures/f1_phase1_noise.png)

**Two findings:**

- **Precision ceiling.** No variant exceeds **27.2%** precision. Between 72.8% and 81.7% of everything SZZ flags is a false alarm.
- **Noise is asymmetric and bifurcated.** BSZZ is FP-heavy (ρ₀ = 26.3%, high recall 64%). LSZZ and RSZZ are FN-heavy (ρ₀ ≈ 7–9% but miss 70–73% of real defects). The refined variants sit in between. This is *not* symmetric random noise, which is why Phase 3's injection must be calibrated per-variant.

**Inter-variant agreement (Cohen's κ):** AGSZZ/MASZZ/RASZZ agree with each other at κ = 0.859–0.933, but with the oracle at only κ = 0.158–0.202. **SZZ variants share failure modes.** High inter-tool agreement in the literature was mistaken for accuracy.

---

## 2. Phase 2 — the full results matrix

Mean MCC over 21 projects × 10 seeds. **Oracle-scored** = measured against developer-verified truth (real bug-finding ability). **Self-scored** = measured against the same noisy SZZ labels used for training (what the literature does).

### Batch models

| Model | Labels | k-fold oracle-scored | k-fold **self**-scored | chrono oracle-scored | chrono **self**-scored |
|---|---|---|---|---|---|
| **JITLine** | **oracle** | **0.2300** | — | **0.1027** | — |
| JITLine | BSZZ | 0.1701 | **0.4181** | **0.1285** | 0.2176 |
| JITLine | AGSZZ | 0.1144 | 0.3091 | 0.0835 | 0.1299 |
| JITLine | MASZZ | 0.1205 | 0.3305 | 0.0752 | 0.1321 |
| JITLine | LSZZ | 0.1380 | 0.2453 | 0.0791 | 0.1509 |
| JITLine | RSZZ | 0.1103 | 0.1803 | 0.0662 | 0.0934 |
| JITLine | RASZZ | 0.1156 | 0.3069 | 0.0714 | 0.1340 |
| **LApredict** | **oracle** | **0.2058** | — | **0.1734** | — |
| LApredict | BSZZ | 0.1941 | 0.3510 | 0.1634 | 0.2918 |
| LApredict | AGSZZ | 0.2003 | 0.2472 | 0.1685 | 0.1975 |
| LApredict | MASZZ | 0.1995 | 0.2626 | 0.1664 | 0.2003 |
| LApredict | LSZZ | 0.2078 | 0.2679 | 0.1706 | 0.2174 |
| LApredict | RSZZ | 0.2016 | 0.1779 | 0.1731 | 0.1666 |
| LApredict | RASZZ | 0.2000 | 0.2603 | 0.1679 | 0.2143 |

*Oracle-trained cells have no separate self-scored value — the two conventions coincide by construction.*

### Online model (ORB)

| Labels | chrono-online oracle | chrono-online self | prequential **time-avg** | prequential terminal | prequential self (terminal) |
|---|---|---|---|---|---|
| **oracle** | **0.0777** | — | **0.0970** | 0.0685 | — |
| BSZZ | 0.0767 | 0.1613 | 0.0578 | 0.0566 | 0.1125 |
| LSZZ | 0.0082 | 0.0695 | 0.0582 | 0.0209 | 0.0682 |
| RASZZ | 0.0193 | 0.0673 | 0.0395 | 0.0184 | 0.0553 |
| AGSZZ | 0.0177 | 0.0684 | 0.0365 | 0.0125 | 0.0609 |
| MASZZ | 0.0216 | 0.0717 | 0.0353 | **−0.0030** | 0.0664 |
| RSZZ | 0.0114 | 0.0349 | 0.0315 | 0.0104 | 0.0472 |

**Note:** MASZZ's apparently *harmful* negative MCC (−0.0030) exists only under the terminal estimator. Under the primary time-averaged estimator it is +0.0353 — poor, but not harmful.

---

## 3. The inflation ladder

![Inflation ladder](reports/figures/f2_inflation_ladder.png)

| Step | Configuration | MCC | What was removed |
|---|---|---|---|
| 0 | JITLine, BSZZ labels, k-fold, self-scored | **0.4181** | — (the literature's number) |
| 1 | JITLine, BSZZ labels, k-fold, oracle-scored | 0.1701 | circular self-scoring (**−0.248**) |
| 2 | JITLine, oracle labels, chronological | 0.1027 | temporal leakage |
| 3 | ORB, oracle labels, prequential + latency | **0.0970** (time-avg) | batch→stream |

**Read the ladder carefully.** Step 3 changes the *learner* as well as the regime. §7 decomposes it — and the answer is that almost all of that step is the learner, not latency.

---

## 4. Test family 1 — regime inflation

Random k-fold vs chronological split, paired by project. m = 6.

| Model | Labels | k-fold | Chrono | Δ | p | Holm p | δ | Effect |
|---|---|---|---|---|---|---|---|---|
| **JITLine** | **oracle** | 0.2300 | 0.1027 | **+0.1273** | 9.5e-07 | **5.7e-06** | 0.742 | **large** |
| JITLine | RSZZ | 0.1103 | 0.0662 | +0.0441 | 0.0022 | **0.0108** | 0.374 | medium |
| JITLine | BSZZ | 0.1701 | 0.1285 | +0.0415 | 0.0646 | 0.2008 | 0.311 | small |
| LApredict | oracle | 0.2058 | 0.1734 | +0.0324 | 0.0502 | 0.2008 | 0.247 | small |
| LApredict | BSZZ | 0.1941 | 0.1634 | +0.0307 | 0.0646 | 0.2008 | 0.252 | small |
| LApredict | RSZZ | 0.2016 | 0.1731 | +0.0285 | 0.1111 | 0.2008 | 0.247 | small |

**p = 9.5e-07 is the floor of the exact test at n = 21** (2/2²¹). JITLine's k-fold score exceeded its chronological score in **21 of 21 projects, no exceptions**.

**Interpretation:** leakage inflates in proportion to model capacity. A 14-feature Random Forest memorises project-specific temporal patterns that shuffled folds expose; a one-feature logistic regression cannot memorise anything, so it barely moves. **This is why weak baselines look competitive in the literature — they were never the ones being inflated.**

---

## 5. Test family 2 — self-deception gap

Self-scored vs oracle-scored MCC, paired by project, **per model** (pooling the two models would treat them as independent observations on the same project — they are not). m = 36 terminal + 6 time-averaged.

![Self-deception gap](reports/figures/f3_self_deception.png)

### Naive k-fold — the headline rows

| Model | Labels | Self | Oracle | Δ | Holm p | δ | Effect |
|---|---|---|---|---|---|---|---|
| **JITLine** | **BSZZ** | 0.4181 | 0.1701 | **+0.2480** | **3.4e-05** | **0.955** | **large** |
| JITLine | MASZZ | 0.3305 | 0.1205 | +0.2100 | 0.0000 | 0.905 | large |
| JITLine | AGSZZ | 0.3091 | 0.1144 | +0.1948 | 0.0000 | 0.819 | large |
| JITLine | RASZZ | 0.3069 | 0.1156 | +0.1913 | 0.0001 | 0.791 | large |
| LApredict | BSZZ | 0.3510 | 0.1941 | +0.1569 | 0.0003 | 0.850 | large |
| JITLine | LSZZ | 0.2453 | 0.1380 | +0.1072 | 0.0002 | 0.692 | large |
| JITLine | RSZZ | 0.1803 | 0.1103 | +0.0701 | 0.0230 | 0.542 | large |

### The gap is model-dependent

| Variant (k-fold) | JITLine Δ | JITLine Holm | LApredict Δ | LApredict Holm |
|---|---|---|---|---|
| BSZZ | +0.2480 | 3.4e-05 ✅ | +0.1569 | 0.0003 ✅ |
| AGSZZ | +0.1948 | 0.0000 ✅ | +0.0469 | 0.9428 ✗ |
| MASZZ | +0.2100 | 0.0000 ✅ | +0.0632 | 0.6439 ✗ |
| LSZZ | +0.1072 | 0.0002 ✅ | +0.0602 | 0.5009 ✗ |
| RASZZ | +0.1913 | 0.0001 ✅ | +0.0603 | 0.6563 ✗ |
| RSZZ | +0.0701 | 0.0230 ✅ | **−0.0237** | 0.9714 ✗ |

**JITLine's gap is large and significant for all six variants. LApredict's only for BSZZ.** Memorising a heuristic's error pattern requires capacity. Note LApredict/RSZZ is *negative* — RSZZ's very low false-alarm rate leaves almost no systematic error pattern to exploit.

**Mechanism:** BSZZ flags 8,060 commits, only 1,495 correctly (18.6% precision). A Random Forest learns *which commits BSZZ over-flags* — a systematic, learnable pattern. Scored against BSZZ this looks like skill; scored against reality it evaporates. **The model is an excellent BSZZ emulator and a mediocre bug detector.**

---

## 6. Test family 3 — label source gap

ORB oracle-trained vs each SZZ-trained variant, prequential + real latency, oracle-scored. m = 6 per estimator.

![Label source gap](reports/figures/f4_label_source.png)

### Primary: time-averaged prequential MCC

| Comparison | Oracle | Variant | Δ | p | Holm p | δ | Effect | Wins |
|---|---|---|---|---|---|---|---|---|
| oracle vs RSZZ | 0.0970 | 0.0315 | +0.0655 | 0.0000 | **0.0001** | 0.710 | large | 19/21 |
| oracle vs MASZZ | 0.0970 | 0.0353 | +0.0617 | 0.0001 | **0.0003** | 0.674 | large | 18/21 |
| oracle vs AGSZZ | 0.0970 | 0.0365 | +0.0605 | 0.0004 | **0.0009** | 0.655 | large | 17/21 |
| oracle vs RASZZ | 0.0970 | 0.0395 | +0.0575 | 0.0001 | **0.0004** | 0.669 | large | 18/21 |
| **oracle vs BSZZ** | 0.0970 | 0.0578 | **+0.0392** | 0.0001 | **0.0004** | 0.451 | medium | **18/21** |
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

### Why the estimators disagree on BSZZ — and why time-averaged is primary

![Estimator comparison](reports/figures/f7_estimators.png)

The terminal fading value is the confusion matrix at end of stream. With `fading = 0.99` the weights sum to ≈ 100 commits, so it summarises roughly the **last hundred commits** of each project — about 8 positives. The time-averaged value is the mean of the whole trajectory, which is what Gama's prequential protocol prescribes.

| | Terminal | Time-averaged |
|---|---|---|
| Project-level sd | 0.092 | **0.051** |
| ant-ivy, oracle | 0.057 | 0.201 |

**This is not estimator-shopping, and here is the defence:**

1. **Chosen a priori.** The switch to time-averaging was a methodological decision made when the prequential evaluation was reviewed — before any label-source comparison was run under it.
2. **It does not flatter the result.** The obvious objection is that averaging includes the model's warm-up. It does — and the warm-up *depresses* the average: mean MCC over the first 10% of the stream is **−0.039** (commons-math) and **−0.012** (ant-ivy). Excluding the warm-up would push results *higher*. The estimator is conservative here.

**Report both.** `results/phase2/statistical_tests.csv` carries a `metric` column with each test computed under both.

**Why refined variants lose by more than BSZZ:** they suppress false alarms by filtering but miss 52–73% of real defects. In streaming, a missed defect is not neutral — the model is actively trained on it as *clean*. BSZZ's 64% recall makes the opposite trade and loses by the smallest margin.

---

## 7. Test families 4 & 5 — batch→stream decomposition

The ladder's third rung changed the learner *and* the regime simultaneously. Adding `chronological_online` — ORB trained sequentially on the past, frozen, tested on the future — holds the learner fixed and breaks the confound.

![Decomposition](reports/figures/f5_decomposition.png)

### Regime effect (model held fixed) — m = 2

| Labels | Chrono-online | Prequential+latency | Δ | p | Holm p | δ | Effect |
|---|---|---|---|---|---|---|---|
| **oracle** | 0.0777 | 0.0685 | **+0.0093** | **0.8382** | 0.8382 | −0.075 | **negligible** |
| BSZZ | 0.0767 | 0.0566 | +0.0200 | 0.2428 | 0.4857 | 0.179 | small |

### Learner effect (regime held fixed) — m = 4

| Comparison | Labels | Batch | ORB | Δ | p | Holm p | δ | Effect |
|---|---|---|---|---|---|---|---|---|
| **LApredict vs ORB** | **oracle** | 0.1734 | 0.0777 | **+0.0957** | 0.0001 | **0.0004** | 0.533 | **large** |
| LApredict vs ORB | BSZZ | 0.1634 | 0.0767 | +0.0867 | 0.0004 | **0.0011** | 0.488 | large |
| JITLine vs ORB | BSZZ | 0.1285 | 0.0767 | +0.0519 | 0.0158 | **0.0316** | 0.297 | small |
| JITLine vs ORB | oracle | 0.1027 | 0.0777 | +0.0250 | 0.2180 | 0.2180 | 0.249 | small |

**Three of four learner-effect tests are significant; neither regime-effect test is.** Of the 0.1050 MCC drop from LApredict-batch to ORB-streaming, **~91% is the learner swap and ~9% is latency** — and the latency component is statistically indistinguishable from zero.

**The honest caveat:** m = 2 with n = 21 pairs. A negligible result here is evidence of a *small* effect, not proof of zero. Say "no detectable effect at this sample size."

**What latency actually costs:** not absolute MCC, but *discriminability*. Over half of all defect labels arrive after the 90-day window, imposing false-negative noise on every label source and compressing the differences between them.

---

## 8. Verification latency and the deliverability confound

![Latency distribution](reports/figures/f6_latency.png)

| Statistic | Value |
|---|---|
| Commits linked to a fix | 8,819 / 27,319 |
| Median latency | **113 days** |
| p90 | 1,597 days |
| **Arriving after W = 90 d** | **53.0%** |
| Arriving after 1 year | 33.1% |
| Arriving after 3 years | 16.2% |

### fix_ts coverage by label source

| Source | Coverage | Median latency | > 90 d |
|---|---|---|---|
| **oracle** | **67.8%** | 109.4 d | 52.8% |
| BSZZ | 100.0% | 95.0 d | 50.8% |
| AGSZZ | 98.4% | 87.9 d | 49.7% |
| MASZZ | 99.1% | 91.9 d | 50.2% |
| LSZZ | 97.0% | 62.6 d | 47.3% |
| RSZZ | 98.1% | **24.7 d** | 38.0% |
| RASZZ | 95.6% | 73.7 d | 47.9% |

**Worth reporting:** RSZZ's median latency is 24.7 days against BSZZ's 95. Restricting to the single most-likely inducing commit preferentially keeps recently-touched lines. **Label quality and label timeliness are correlated across variants.**

### The confound test

Oracle has only 67.8% coverage vs BSZZ's 100%. Does oracle win on quality, or is BSZZ handicapped? Tested by imputing oracle's missing timestamps from the empirical latency distribution (seed-controlled, `impute_fix_ts`):

| Condition | Coverage | Time-avg MCC | Terminal MCC |
|---|---|---|---|
| Oracle as-is | 67.8% | 0.0970 | 0.0685 |
| Oracle imputed | 100% | **0.0835** | 0.0603 |
| BSZZ | 100% | 0.0578 | 0.0566 |

| Comparison | Estimator | Δ | Wins | p (2-sided) | δ |
|---|---|---|---|---|---|
| **Oracle imputed vs BSZZ** | **time-averaged** | **+0.0258** | **16/21** | **0.0101** | 0.293 small |
| Oracle imputed vs BSZZ | terminal | +0.0037 | 11/21 | 0.8649 | 0.030 negligible |
| Oracle as-is vs BSZZ | time-averaged | +0.0392 | 18/21 | 0.0001 | 0.451 medium |

**Under the primary estimator the confound is bounded** — the oracle advantage survives equalising deliverability.

**Why imputation costs the oracle something (0.097 → 0.084):** the empirical pool it samples from has a 113-day median and a 1,597-day p90. More than half the imputed labels arrive after the window and are first delivered as *wrong clean* labels; a third arrive after a year. Handing the oracle its missing labels at realistic delays is close to a no-op.

**Still open (disclosure):** the oracle's `fix_ts` is the union of the six SZZ variants' fix→inducing mappings, since JIT-Defects4J has no oracle-native linkage here. Imputation addresses the *coverage* half but not the *timing* half — a linked oracle commit's arrival date is still whichever SZZ variant matched it. This belongs in Threats to Validity.

---

## 9. Per-project characteristics

![JITLine anomaly](reports/figures/f8_jitline_anomaly.png)

**The JITLine anomaly:** BSZZ-trained JITLine (0.1285) beats oracle-trained (0.1027) in **13 of 21 projects** under chronological evaluation. BSZZ labels 29.5% of commits positive against a true rate of 8.5%; with only ~40 positives per oracle training split, the Random Forest starves, and BSZZ's extra minority mass — 81% of it false — acts as accidental data augmentation.

**It is not a threshold artifact.** Measured under three threshold protocols across 21 projects × 3 seeds:

| Protocol | Oracle MCC | Oracle G-mean | Degenerate runs | BSZZ−oracle gap | BSZZ wins |
|---|---|---|---|---|---|
| `tail` (original) | 0.1031 | 0.4855 | 9.5% | +0.034 | 13/21 |
| `oob` | 0.0874 | 0.3655 | **17.5%** | +0.034 | 15/21 |
| **`cv` (blocked, current)** | 0.1004 | **0.5226** | **4.8%** | +0.028 | 12/21 |

Blocked cross-validation is now the default: best G-mean, half the degenerate all-one-class rate. **Out-of-bag tuning was tried and rejected on evidence** — OOB probabilities come from only ~63% of the trees, so the threshold is miscalibrated against the full ensemble.

### Project heterogeneity — a limitation

| Project | Commits | Oracle positives | Rate | Positives in chrono training half |
|---|---|---|---|---|
| commons-digester | 1,079 | 19 | 1.8% | **5** |
| commons-validator | 598 | 36 | 6.0% | **11** |
| commons-collections | 1,823 | 50 | 2.7% | 19 |
| commons-scxml | 544 | 47 | 8.6% | 31 |
| commons-math | 4,026 | 335 | 8.3% | 196 |
| ant-ivy | 1,771 | 332 | 18.7% | 218 |
| giraph | 844 | 163 | 19.3% | 110 |

All means are **unweighted** across projects spanning 544–4,026 commits and 1.8–19.3% defect rate. commons-digester trains on five positives and counts equally with commons-math's 196. **A robustness check excluding projects below a positive-count floor is outstanding work.**

---

## 10. Headline claims, ranked by strength

### Tier 1 — bulletproof

1. **Random k-fold inflates JITLine by +0.127 MCC** over a chronological split (Holm p = 5.7e-06, δ = 0.742). Held in **21/21 projects**. Inflation scales with model capacity — LApredict barely moves.
2. **Self-scoring on SZZ inflates JITLine/BSZZ by +0.248 MCC** (Holm p = 3.4e-05, δ = 0.955, 21/21 projects). Largest effect in the study. Model-dependent: significant for all six variants under JITLine, only BSZZ under LApredict.
3. **SZZ precision never exceeds 27.2%**; noise is asymmetric and variant-dependent (ρ₀ 6.7–26.3%, ρ₁ 35.9–73.3%).
4. **SZZ variants agree with each other (κ up to 0.933) far more than with truth (κ 0.158–0.202).**

### Tier 2 — solid, with the right framing

5. **Oracle labels beat all six SZZ variants** under honest streaming evaluation (time-averaged estimator; Holm p ≤ 0.0025, δ 0.39–0.71, 16–19/21 projects). Survives 100% latency imputation (+0.026, 16/21, p = 0.010). *Must add:* under the terminal estimator the BSZZ comparison alone is not significant; report both, treat time-averaged as primary.
6. **FP-heavy noise helps batch learners.** BSZZ-trained JITLine beats oracle-trained in 13/21 projects; survives three threshold protocols.
7. **Latency is not what makes streaming hard.** Holding the learner fixed, latency costs +0.009 MCC (p = 0.84, negligible); the learner swap costs +0.096 (Holm p = 0.0004, large). ~91% of the batch→stream drop is the learner. **No prior JIT-SDP work separates these** — this is the novel contribution.

### Tier 3 — observations

8. Deployable MCC under realistic conditions is **~0.097** (time-averaged) or 0.069 (terminal). Always name the estimator.
9. Low-capacity models resist label noise — LApredict's chronological MCC varies by only 0.015 across all seven label sources.
10. **Verification latency compresses label-source differences**: 53% of defect labels arrive after the window, imposing FN noise on every source regardless of quality.

---

## Reproducing any number here

```bash
python -m experiments.check_label_consistency        # integrity gate
python -c "import pandas as pd; print(pd.read_csv('results/phase2/statistical_tests.csv').to_string())"
```

| File | Contents |
|---|---|
| `results/phase2/phase2_results.csv` | 16,380 records, both estimators |
| `results/phase2/statistical_tests.csv` | 66 tests with `metric`, `p_holm`, `p_bh` |
| `results/phase2/latency_imputation_summary.csv` | Deliverability confound, both estimators |
| `results/phase1/phase1_quality_corrected.csv` | Phase 1 table |
| `phase1_bias.json` | ρ₀/ρ₁ for Phase 3 |
| `reports/figures/` | The eight figures above |

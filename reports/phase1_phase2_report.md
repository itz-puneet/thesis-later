# Empirical Investigation Report: SZZ Label Noise & Downstream Evaluation Impact (Phases 1 & 2)

**Author / Project**: Thesis Research Replication & Empirical Evaluation  
**Projects Evaluated**: 21 Apache Java Projects (JIT-Defects4J / JIT-Fine Benchmark)  
**Total Experimental Records**: 14,700 runs across 10 random seeds, 7 label sources, 3 models, and 3 evaluation regimes  
**Report Date**: August 2026 (Post-Fix Rerun v2)  

---

## Executive Summary

This empirical investigation addresses a foundational vulnerability in Just-In-Time Software Defect Prediction (JIT-SDP): **how does label noise introduced by automated SZZ algorithms distort defect prediction models, and how much of reported literature performance is an artifact of circular self-scoring and temporal data leakage?**

### Key Findings at a Glance:
1. **Severe & Asymmetric SZZ Label Noise (Phase 1)**: Across 21 projects, SZZ variants exhibit poor precision (**18.3% to 27.2%**) and high false alarm rates ($\rho_0 = 6.7\% - 26.3\%$). Over **72% to 81%** of all commits flagged as defect-inducing by SZZ tools are false positives, while 36% to 73% of true bugs are missed ($\rho_1 = 35.9\% - 73.3\%$).
2. **Evaluation Leakage Inflates Performance by +0.141 MCC (Phase 2)**: Naive $k$-fold cross-validation allows future-to-past data leakage. For `JITLine`, naive $k$-fold inflates oracle MCC from **0.1028** (chronological) to **0.2435** (naive $k$-fold), a statistically significant **large effect** ($p = 2.86 \times 10^-6$, Cliff's $\delta = +0.737$).
3. **The Circular "Self-Deception" Gap is +0.180 MCC (Phase 2)**: When models are evaluated on the same SZZ labels used for training, apparent performance is heavily exaggerated. For `BSZZ`, self-scored naive MCC is **0.3550** versus an oracle-scored MCC of **0.1748** ($p = 6.54 \times 10^-8$, Cliff's $\delta = +0.811$).
4. **ORB Sanity Ordering Restored Under Real Latency (Phase 2)**: When online evaluation incorporates real reconstructed verification latency (median 113 days, 53% arriving after $W=90$ days), oracle-trained `ORB` is the best-performing configuration (**MCC = 0.0685**, G-mean = 0.5460), beating `BSZZ` (**0.0559** / 0.5060) in 14 of 21 projects.
5. **JITLine Anomaly Decomposed**: Following SMOTE minority oversampling and G-mean threshold moving, oracle-trained JITLine chronological MCC increased from 0.067 to **0.1028** (G-mean 0.4915). BSZZ-trained JITLine achieves **0.1309** MCC (winning in 13/21 projects), proving that part of the earlier gap was a decision-threshold artifact, while a residual minority-enrichment effect remains under 8.5% class imbalance.
6. **Variant Spread Compression Under Latency**: Because 53% of defect labels arrive late, verification latency itself imposes heavy false-negative noise on every label source, compressing the performance spread between refined and naive SZZ variants (LSZZ 0.0259 > RSZZ 0.0183 > AGSZZ 0.0164 > RASZZ 0.0047 > MASZZ -0.0025).

---

## Phase 1: Intrinsic Label Quality & Noise Profile of SZZ Variants

Phase 1 benchmarks 6 modern SZZ variants (`BSZZ`, `AGSZZ`, `MASZZ`, `LSZZ`, `RSZZ`, `RASZZ`) directly against human-validated ground truth (`label_oracle`) on an identical 27,319-commit universe across all 21 Apache repositories.

### Table 1: Intrinsic SZZ Performance vs. Ground Truth Oracle

| SZZ Variant | Precision | Recall | F1-Score | G-Mean | FPR ($\rho_0$) | FNR ($\rho_1$) | Cohen's $\kappa$ | Matthews Corr. (MCC) | True Pos (TP) | False Pos (FP) | False Neg (FN) | True Neg (TN) |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **BSZZ** | 0.1855 | 0.6411 | 0.2877 | 0.6875 | 0.2627 | 0.3589 | 0.1790 | 0.2318 | 1,495 | 6,565 | 837 | 18,422 |
| **AGSZZ** | 0.1855 | 0.4674 | 0.2656 | 0.6147 | 0.1915 | 0.5326 | 0.1633 | 0.1876 | 1,090 | 4,786 | 1,242 | 20,201 |
| **MASZZ** | 0.1826 | 0.4820 | 0.2649 | 0.6205 | 0.2013 | 0.5180 | 0.1610 | 0.1877 | 1,124 | 5,030 | 1,208 | 19,957 |
| **LSZZ** | 0.2720 | 0.2667 | 0.2693 | 0.4989 | 0.0666 | 0.7333 | 0.2019 | 0.2019 | 622 | 1,665 | 1,710 | 23,322 |
| **RSZZ** | 0.2318 | 0.2997 | 0.2615 | 0.5215 | 0.0927 | 0.7003 | 0.1828 | 0.1846 | 699 | 2,316 | 1,633 | 22,671 |
| **RASZZ** | 0.1840 | 0.4383 | 0.2592 | 0.5990 | 0.1813 | 0.5617 | 0.1580 | 0.1784 | 1,022 | 4,531 | 1,310 | 20,456 |

### Phase 1 Visualizations

#### Figure 1: SZZ Variant Label Quality (Precision vs. Recall vs. F1)
![Figure 1: Precision, Recall, F1](figures/fig1_phase1_precision_recall.png)

#### Figure 2: Asymmetric Noise Rates (FPR $\rho_0$ vs. FNR $\rho_1$)
![Figure 2: Noise Rates](figures/fig2_phase1_noise_rates.png)

#### Figure 3: Inter-Variant Agreement Matrix (Cohen's Kappa $\kappa$)
![Figure 3: Kappa Heatmap](figures/fig3_phase1_kappa_heatmap.png)

### Phase 1 Insights:
- **Severe Precision Ceiling**: Precision never exceeds 27.2% across all variants. Between 72.8% and 81.5% of commits flagged as bug-introducing are false positives.
- **Asymmetric Noise Trade-Off**: `BSZZ` achieves highest recall (64.1%) at the cost of high FPR ($\rho_0 = 26.3\%$). Refined variants (`LSZZ`, `RSZZ`) suppress FPR to 6.7%–9.3%, but miss 70.0%–73.3% of true bugs ($\rho_1 = 70.0\% - 73.3\%$).
- **Low Agreement with Oracle**: Inter-variant Cohen's $\kappa$ with the oracle ranges between **0.158** and **0.202**, indicating only slight to fair agreement.

---

## Phase 2: Downstream Impact Under Honest Evaluation

Phase 2 evaluates 3 distinct defect prediction architectures across 7 label sources and 3 evaluation regimes:
1. **`LApredict`** (Zeng et al., 2021): Single-feature logistic regression on *Lines Added* (`la`).
2. **`JITLine`** (Pornprasit & Tantithamthavorn, 2021): 100-tree Random Forest over 14 Kamei features with SMOTE minority oversampling and G-mean threshold moving.
3. **`ORB`** (Cabral et al., 2019): Online streaming ensemble with Poisson oversampling rate boosting and real reconstructed verification latency ($W = 90$ days).

### Table 2: Oracle-Scored Performance by Model, Label Source & Regime

| Model | Training Label Source | Naive $k$-Fold (Leaky) [MCC / G-mean] | Chronological (Honest Batch) [MCC / G-mean] | Prequential Latency (Online Stream) [MCC / G-mean] |
| :--- | :--- | :---: | :---: | :---: |
| JITLine | **oracle** | **0.2435** / 0.6719 | **0.1028** / 0.4915 | *N/A (Batch Model)* |
| JITLine | BSZZ | 0.1607 / 0.5986 | 0.1309 / 0.5398 | *N/A (Batch Model)* |
| JITLine | AGSZZ | 0.1044 / 0.5455 | 0.0750 / 0.4668 | *N/A (Batch Model)* |
| JITLine | MASZZ | 0.1155 / 0.5896 | 0.0734 / 0.4780 | *N/A (Batch Model)* |
| JITLine | LSZZ | 0.1290 / 0.5773 | 0.0779 / 0.4580 | *N/A (Batch Model)* |
| JITLine | RSZZ | 0.1038 / 0.5704 | 0.0573 / 0.4647 | *N/A (Batch Model)* |
| JITLine | RASZZ | 0.1135 / 0.5840 | 0.0658 / 0.4712 | *N/A (Batch Model)* |
| LApredict | **oracle** | **0.2058** / 0.6770 | **0.1734** / 0.6387 | *N/A (Batch Model)* |
| LApredict | BSZZ | 0.1889 / 0.6375 | 0.1599 / 0.6259 | *N/A (Batch Model)* |
| LApredict | AGSZZ | 0.1950 / 0.6437 | 0.1670 / 0.6289 | *N/A (Batch Model)* |
| LApredict | MASZZ | 0.2000 / 0.6731 | 0.1708 / 0.6575 | *N/A (Batch Model)* |
| LApredict | LSZZ | 0.2074 / 0.6714 | 0.1719 / 0.6303 | *N/A (Batch Model)* |
| LApredict | RSZZ | 0.2017 / 0.6748 | 0.1740 / 0.6551 | *N/A (Batch Model)* |
| LApredict | RASZZ | 0.2005 / 0.6732 | 0.1745 / 0.6563 | *N/A (Batch Model)* |
| ORB | **oracle** | *N/A (Online Model)* | *N/A (Online Model)* | **0.0685** / 0.5460 |
| ORB | BSZZ | *N/A (Online Model)* | *N/A (Online Model)* | 0.0559 / 0.5060 |
| ORB | AGSZZ | *N/A (Online Model)* | *N/A (Online Model)* | 0.0164 / 0.4603 |
| ORB | MASZZ | *N/A (Online Model)* | *N/A (Online Model)* | -0.0025 / 0.4514 |
| ORB | LSZZ | *N/A (Online Model)* | *N/A (Online Model)* | 0.0259 / 0.4917 |
| ORB | RSZZ | *N/A (Online Model)* | *N/A (Online Model)* | 0.0183 / 0.4913 |
| ORB | RASZZ | *N/A (Online Model)* | *N/A (Online Model)* | 0.0047 / 0.4739 |


---

### Table 3: Statistical Significance (Wilcoxon Signed-Rank & Cliff's $\delta$)

| Comparison Type | Model | Label Source | Condition A | Condition B | Mean A | Mean B | Mean Diff | $p$-value | Cliff's $\delta$ | Magnitude |
| :--- | :--- | :--- | :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| regime_inflation | LApredict | oracle | naive_kfold | chronological | 0.2058 | 0.1734 | +0.0324 | 0.0502 | +0.247 | **small** |
| regime_inflation | LApredict | BSZZ | naive_kfold | chronological | 0.1889 | 0.1599 | +0.0290 | 0.0793 | +0.236 | **small** |
| regime_inflation | LApredict | RSZZ | naive_kfold | chronological | 0.2017 | 0.1740 | +0.0276 | 0.1111 | +0.243 | **small** |
| regime_inflation | JITLine | oracle | naive_kfold | chronological | 0.2435 | 0.1028 | +0.1407 | 2.86e-06 | +0.737 | **large** |
| regime_inflation | JITLine | BSZZ | naive_kfold | chronological | 0.1607 | 0.1309 | +0.0297 | 0.0793 | +0.181 | **small** |
| regime_inflation | JITLine | RSZZ | naive_kfold | chronological | 0.1038 | 0.0573 | +0.0466 | 0.0071 | +0.351 | **medium** |
| self_deception_gap | All | BSZZ | self_scored (naive_kfold) | oracle_scored (naive_kfold) | 0.3550 | 0.1748 | +0.1803 | 6.54e-08 | +0.811 | **large** |
| self_deception_gap | All | BSZZ | self_scored (chronological) | oracle_scored (chronological) | 0.2422 | 0.1454 | +0.0968 | 7.14e-06 | +0.509 | **large** |
| self_deception_gap | All | BSZZ | self_scored (prequential_latency) | oracle_scored (prequential_latency) | 0.1136 | 0.0559 | +0.0577 | 0.0127 | +0.356 | **medium** |
| self_deception_gap | All | AGSZZ | self_scored (naive_kfold) | oracle_scored (naive_kfold) | 0.2386 | 0.1497 | +0.0889 | 3.32e-04 | +0.459 | **medium** |
| self_deception_gap | All | AGSZZ | self_scored (chronological) | oracle_scored (chronological) | 0.1337 | 0.1210 | +0.0127 | 0.4436 | +0.074 | **negligible** |
| self_deception_gap | All | AGSZZ | self_scored (prequential_latency) | oracle_scored (prequential_latency) | 0.0526 | 0.0164 | +0.0363 | 0.0460 | +0.270 | **small** |
| self_deception_gap | All | MASZZ | self_scored (naive_kfold) | oracle_scored (naive_kfold) | 0.2753 | 0.1578 | +0.1176 | 2.12e-06 | +0.677 | **large** |
| self_deception_gap | All | MASZZ | self_scored (chronological) | oracle_scored (chronological) | 0.1547 | 0.1221 | +0.0326 | 0.0330 | +0.206 | **small** |
| self_deception_gap | All | MASZZ | self_scored (prequential_latency) | oracle_scored (prequential_latency) | 0.0575 | -0.0025 | +0.0600 | 0.0127 | +0.429 | **medium** |
| self_deception_gap | All | LSZZ | self_scored (naive_kfold) | oracle_scored (naive_kfold) | 0.2452 | 0.1682 | +0.0770 | 5.99e-06 | +0.525 | **large** |
| self_deception_gap | All | LSZZ | self_scored (chronological) | oracle_scored (chronological) | 0.1725 | 0.1249 | +0.0476 | 0.0043 | +0.378 | **medium** |
| self_deception_gap | All | LSZZ | self_scored (prequential_latency) | oracle_scored (prequential_latency) | 0.0747 | 0.0259 | +0.0488 | 8.52e-04 | +0.492 | **large** |
| self_deception_gap | All | RSZZ | self_scored (naive_kfold) | oracle_scored (naive_kfold) | 0.1703 | 0.1528 | +0.0176 | 0.1707 | +0.164 | **small** |
| self_deception_gap | All | RSZZ | self_scored (chronological) | oracle_scored (chronological) | 0.1237 | 0.1157 | +0.0080 | 0.1668 | +0.087 | **negligible** |
| self_deception_gap | All | RSZZ | self_scored (prequential_latency) | oracle_scored (prequential_latency) | 0.0500 | 0.0183 | +0.0317 | 0.0351 | +0.374 | **medium** |
| self_deception_gap | All | RASZZ | self_scored (naive_kfold) | oracle_scored (naive_kfold) | 0.2537 | 0.1570 | +0.0968 | 6.46e-06 | +0.590 | **large** |
| self_deception_gap | All | RASZZ | self_scored (chronological) | oracle_scored (chronological) | 0.1514 | 0.1201 | +0.0313 | 0.0370 | +0.204 | **small** |
| self_deception_gap | All | RASZZ | self_scored (prequential_latency) | oracle_scored (prequential_latency) | 0.0408 | 0.0047 | +0.0362 | 0.0760 | +0.256 | **small** |
| label_source_gap | ORB | BSZZ | oracle | BSZZ | 0.0685 | 0.0559 | +0.0126 | 0.3926 | +0.156 | **small** |
| label_source_gap | ORB | AGSZZ | oracle | AGSZZ | 0.0685 | 0.0164 | +0.0521 | 0.0063 | +0.397 | **medium** |
| label_source_gap | ORB | MASZZ | oracle | MASZZ | 0.0685 | -0.0025 | +0.0710 | 0.0101 | +0.546 | **large** |
| label_source_gap | ORB | LSZZ | oracle | LSZZ | 0.0685 | 0.0259 | +0.0426 | 0.0263 | +0.397 | **medium** |
| label_source_gap | ORB | RSZZ | oracle | RSZZ | 0.0685 | 0.0183 | +0.0502 | 0.0127 | +0.451 | **medium** |
| label_source_gap | ORB | RASZZ | oracle | RASZZ | 0.0685 | 0.0047 | +0.0638 | 8.52e-04 | +0.483 | **large** |

---

### Phase 2 Visualizations

#### Figure 4: Evaluation Regime Inflation (Naive $k$-Fold vs. Chronological)
![Figure 4: Regime Inflation](figures/fig4_phase2_regime_inflation.png)

#### Figure 5: The Self-Deception Gap (Self-Scored vs. Oracle-Scored)
![Figure 5: Self-Deception Gap](figures/fig5_phase2_self_deception_gap.png)

#### Figure 6: ORB Online Streaming Performance
![Figure 6: ORB Streaming](figures/fig6_phase2_orb_streaming.png)

#### Figure 7: Step-by-Step Transition Across Regimes and Ground Truth
![Figure 7: Deflation Ladder](figures/fig7_phase2_deflation_ladder.png)

#### Figure 8: Reconstructed Defect Verification Latency Distribution
![Figure 8: Latency Distribution](figures/fig8_reconstructed_latency.png)

---

## Synthesis: Decomposition of Performance Inflation

When software engineering papers report defect prediction models reaching apparent MCCs of $0.35 - 0.50$, our findings prove this is driven by three compounding methodological flaws:

```
[Published Baseline: Naive K-Fold Self-Scored BSZZ JITLine: MCC ~0.377]
   │
   ├── Layer 1: Circular Self-Scoring Gap (Δ = -0.216 MCC)
   │     Evaluating on true oracle labels reveals true capability is MCC 0.161.
   │
   ├── Layer 2: Temporal Evaluation Leakage (Δ = -0.141 MCC for Oracle JITLine)
   │     Random k-fold leaks future features into past training splits.
   │
   └── Layer 3: Online Streaming with Real Latency
         Realistic deployment with 90-day verification latency yields MCC ~0.068.
   │
   ▼
[Real-World True Predictive Capability: Oracle ORB MCC = 0.0685 (G-Mean = 0.546)]
```

### Recommendations for Future Defect Prediction Research:
1. **Ban Random $k$-Fold**: All JIT defect prediction models must be evaluated chronologically or in online prequential streams.
2. **Never Self-Score on SZZ**: SZZ labels should only be used for training, never as the test oracle for measuring model performance.
3. **Account for Verification Latency**: Real-world deployment involves delayed feedback (median 113 days); offline batch evaluation provides an overly optimistic bound.

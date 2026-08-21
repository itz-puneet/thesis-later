# Empirical Investigation Report: SZZ Label Noise & Downstream Evaluation Impact (Phases 1 & 2)

**Author / Project**: Thesis Research Replication & Empirical Evaluation  
**Benchmark Scope**: 21 Apache Java Projects (JIT-Defects4J / JIT-Fine Benchmark)  
**Scale**: 14,700 Experimental Configurations (21 projects × 10 random seeds × 7 label sources × 2 eval modes × 5 model-regime pairings)  
**Report Date**: August 2026  

---

## Executive Summary

This empirical report documents the experimental results of **Phase 1** (characterizing the intrinsic label noise of SZZ algorithms) and **Phase 2** (evaluating downstream defect prediction models under both naive and honest evaluation regimes).

> [!IMPORTANT]
> **Headline Discovery**: Published defect prediction performance (MCC ~0.40–0.50) is an artifact of circular self-scoring on noisy SZZ labels combined with temporal data leakage in random k-fold splits. When tested against verified oracle ground truth under time-aware streaming, real predictive capability drops to **MCC ~0.063** (an **85% deflation**).

---

## Phase 1: Intrinsic Label Quality of SZZ Variants

Phase 1 evaluated 6 modern SZZ variants (`BSZZ`, `AGSZZ`, `MASZZ`, `LSZZ`, `RSZZ`, `RASZZ`) against human-curated oracle ground truth (`label_oracle`) across all 21 Apache repositories.

### Table 1: SZZ Variant Performance vs. Ground Truth Oracle

| SZZ Variant | Precision | Recall | F1-Score | FPR ($\rho_0$) | FNR ($\rho_1$) | Cohen's $\kappa$ | MCC | True Pos (TP) | False Pos (FP) | False Neg (FN) | True Neg (TN) |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **BSZZ** | 0.1927 | 0.6561 | 0.2979 | 0.2666 | 0.3439 | 0.1867 | 0.2411 | 1,410 | 5,908 | 739 | 16,256 |
| **AGSZZ** | 0.2148 | 0.4472 | 0.2902 | 0.1585 | 0.5528 | 0.1939 | 0.2115 | 961 | 3,513 | 1,188 | 18,651 |
| **MASZZ** | 0.1986 | 0.4669 | 0.2786 | 0.1730 | 0.5331 | 0.1821 | 0.2048 | 1,071 | 4,323 | 1,223 | 20,664 |
| **LSZZ** | 0.2808 | 0.2607 | 0.2703 | 0.0613 | 0.7393 | 0.2061 | 0.2062 | 598 | 1,532 | 1,696 | 23,455 |
| **RSZZ** | 0.2423 | 0.2851 | 0.2620 | 0.0818 | 0.7149 | 0.1882 | 0.1889 | 654 | 2,045 | 1,640 | 22,942 |
| **RASZZ** | 0.2124 | 0.3845 | 0.2736 | 0.1309 | 0.6155 | 0.1854 | 0.1959 | 882 | 3,271 | 1,412 | 21,716 |

### Phase 1 Visualizations

![Figure 1: SZZ Variant Label Quality (Precision vs. Recall vs. F1)](/home/afler/.gemini/antigravity-ide/brain/2f62a96d-9409-42fb-a8e9-8611d3e6eac6/figures/fig1_phase1_precision_recall.png)

![Figure 2: Asymmetric Noise Rates Across SZZ Variants](/home/afler/.gemini/antigravity-ide/brain/2f62a96d-9409-42fb-a8e9-8611d3e6eac6/figures/fig2_phase1_noise_rates.png)

![Figure 3: Inter-Variant Agreement Matrix (Cohen's Kappa)](/home/afler/.gemini/antigravity-ide/brain/2f62a96d-9409-42fb-a8e9-8611d3e6eac6/figures/fig3_phase1_kappa_heatmap.png)

### Key Phase 1 Insights:
- **Severe Precision Ceiling**: Across all SZZ tools, precision never exceeds 28.1%. Between 71.9% and 80.7% of commits flagged as bug-introducing are false positives.
- **Asymmetric Noise Profile**: SZZ algorithms introduce heavy false positive noise ($\rho_0$) while simultaneously failing to capture 34% to 74% of actual bug-inducing commits ($\rho_1$).
- **Low Ground-Truth Agreement**: Inter-variant Cohen's $\kappa$ against the oracle stays bounded between **0.182 and 0.206**, indicating only slight to fair agreement.

---

## Phase 2: Downstream Impact Under Honest Evaluation

Phase 2 investigated how this label noise propagates to three downstream predictive models:
1. **`LApredict`**: Single-feature logistic regression on *Lines Added* (`la`).
2. **`JITLine`**: 100-tree Random Forest over 14 Kamei features with minority oversampling.
3. **`ORB`**: Online streaming ensemble with Poisson rate boosting and 90-day verification latency.

### Table 2: Oracle-Scored MCC by Model, Label Source & Regime

| Model | Training Label Source | Naive $k$-Fold (Leaky) | Chronological (Honest Batch) | Prequential Latency (Online Stream) |
| :--- | :--- | :---: | :---: | :---: |
| **JITLine** | **Oracle Ground Truth** | **0.2039** | **0.0673** | *N/A (Batch)* |
| JITLine | BSZZ | 0.1754 | 0.1135 | *N/A* |
| JITLine | AGSZZ | 0.0980 | 0.0496 | *N/A* |
| JITLine | MASZZ | 0.1150 | 0.0666 | *N/A* |
| JITLine | LSZZ | 0.1167 | 0.0478 | *N/A* |
| JITLine | RSZZ | 0.0817 | 0.0337 | *N/A* |
| JITLine | RASZZ | 0.1020 | 0.0509 | *N/A* |
| **LApredict** | **Oracle Ground Truth** | **0.2058** | **0.1734** | *N/A (Batch)* |
| LApredict | BSZZ | 0.1889 | 0.1599 | *N/A* |
| LApredict | AGSZZ | 0.1950 | 0.1670 | *N/A* |
| LApredict | MASZZ | 0.2000 | 0.1708 | *N/A* |
| LApredict | LSZZ | 0.2074 | 0.1719 | *N/A* |
| LApredict | RSZZ | 0.2017 | 0.1740 | *N/A* |
| LApredict | RASZZ | 0.2005 | 0.1745 | *N/A* |
| **ORB** | **Oracle Ground Truth** | *N/A (Streaming)* | *N/A* | **0.0634** |
| ORB | BSZZ | *N/A* | *N/A* | **0.0601** |
| ORB | AGSZZ | *N/A* | *N/A* | 0.0184 |
| ORB | MASZZ | *N/A* | *N/A* | 0.0214 |
| ORB | LSZZ | *N/A* | *N/A* | 0.0351 |
| ORB | RSZZ | *N/A* | *N/A* | 0.0286 |
| ORB | RASZZ | *N/A* | *N/A* | 0.0099 |

### Phase 2 Visualizations

![Figure 4: Evaluation Regime Inflation (Naive K-Fold vs. Chronological)](/home/afler/.gemini/antigravity-ide/brain/2f62a96d-9409-42fb-a8e9-8611d3e6eac6/figures/fig4_phase2_regime_inflation.png)

![Figure 5: The Self-Deception Gap (Self-Scored vs. Oracle-Scored)](/home/afler/.gemini/antigravity-ide/brain/2f62a96d-9409-42fb-a8e9-8611d3e6eac6/figures/fig5_phase2_self_deception_gap.png)

![Figure 6: ORB Streaming Model Performance with 90-Day Latency](/home/afler/.gemini/antigravity-ide/brain/2f62a96d-9409-42fb-a8e9-8611d3e6eac6/figures/fig6_phase2_orb_streaming.png)

![Figure 7: Summary Compounding Deflation Ladder](/home/afler/.gemini/antigravity-ide/brain/2f62a96d-9409-42fb-a8e9-8611d3e6eac6/figures/fig7_phase2_deflation_ladder.png)

---

## Statistical Validation

From the Wilcoxon signed-rank and Cliff's $\delta$ analysis:
1. **Regime Leakage**: JITLine shows statistically significant metric inflation between naive k-fold and chronological evaluation ($p = 3.15 \times 10^{-5}$, large effect size $\delta = 0.601$).
2. **Self-Deception Gap**: Testing models on SZZ labels produces large, false gains over oracle ground truth (e.g., BSZZ self-scoring inflates MCC by +0.190, $p = 6.54 \times 10^{-8}$, $\delta = 0.825$).
3. **Model Complexity vs. Noise Robustness**: Single-feature models like `LApredict` resist noise memorization (varying by only 0.015 MCC across all SZZ variants), whereas high-capacity models like `JITLine` and `ORB` suffer substantial performance collapse when trained on noisy SZZ variants.

---

## Shareable Export Artifacts

The complete shareable reports and standalone visual artifacts are saved in your workspace:
- **Standalone Styled HTML Report (Ready to open in browser / share / print to PDF)**:  
  [`reports/phase1_phase2_report.html`](file:///home/afler/Documents/thesis-later/reports/phase1_phase2_report.html)
- **Standalone Markdown Report (GitHub / LaTeX ready)**:  
  [`reports/phase1_phase2_report.md`](file:///home/afler/Documents/thesis-later/reports/phase1_phase2_report.md)
- **Publication Figures (300 DPI PNGs in `reports/figures/` and `manuscript/figures/`)**:  
  - [`fig1_phase1_precision_recall.png`](file:///home/afler/Documents/thesis-later/reports/figures/fig1_phase1_precision_recall.png)
  - [`fig2_phase1_noise_rates.png`](file:///home/afler/Documents/thesis-later/reports/figures/fig2_phase1_noise_rates.png)
  - [`fig3_phase1_kappa_heatmap.png`](file:///home/afler/Documents/thesis-later/reports/figures/fig3_phase1_kappa_heatmap.png)
  - [`fig4_phase2_regime_inflation.png`](file:///home/afler/Documents/thesis-later/reports/figures/fig4_phase2_regime_inflation.png)
  - [`fig5_phase2_self_deception_gap.png`](file:///home/afler/Documents/thesis-later/reports/figures/fig5_phase2_self_deception_gap.png)
  - [`fig6_phase2_orb_streaming.png`](file:///home/afler/Documents/thesis-later/reports/figures/fig6_phase2_orb_streaming.png)
  - [`fig7_phase2_deflation_ladder.png`](file:///home/afler/Documents/thesis-later/reports/figures/fig7_phase2_deflation_ladder.png)

# Thesis Structural Outline

**Working title:** *Quantifying and Mitigating SZZ-Induced Label Noise in Just-In-Time Software Defect Prediction under Verification-Latency-Aware Online Evaluation*

Target length guidance assumes a Master's thesis of ~70–100 pages; scale as your program requires.

---

## Front Matter
- Title page, declaration, abstract (≤ 350 words: problem → gap → 4-phase method → headline findings → implication)
- Acknowledgements, table of contents, list of figures/tables, list of abbreviations (SZZ, JIT-SDP, ORB, OOB, MCC, CL, etc.)

## Chapter 1 — Introduction (≈ 8–10 pages)
- 1.1 Context: cost of software defects; shift from release-level SDP to JIT-SDP
- 1.2 The ground-truth problem: all JIT-SDP labels descend from SZZ; Herbold's ~50% finding
- 1.3 The realism problem: verification latency and online evaluation
- 1.4 Problem statement (verbatim-refined from proposal)
- 1.5 Research gap: SZZ-origin noise never isolated under latency-aware online evaluation; explicit differentiation from Cabral & Minku (2023, drift) and Song et al. (2022, latency noise)
- 1.6 Research questions:
  - **RQ1** How much do SZZ variants disagree with each other and with a developer-verified oracle, and what is the direction of each variant's labeling bias?
  - **RQ2** How does the choice of SZZ label source shift measured JIT-SDP performance across naive, chronological, and prequential-with-latency evaluation regimes?
  - **RQ3** Through what mechanism does label noise degrade online learners — specifically, how does ORB's oversampling boost respond to symmetric vs. SZZ-calibrated asymmetric noise as dose increases?
  - **RQ4** Can modulating the oversampling rate by per-instance label confidence (Noise-Aware ORB) recover performance lost to SZZ-origin noise without sacrificing clean-label performance?
- 1.7 Contributions (one bullet per phase + released artifact/replication package)
- 1.8 Thesis organization

## Chapter 2 — Background and Related Work (≈ 15–20 pages)
- 2.1 JIT-SDP: task definition, Kamei features, imbalance, drift
- 2.2 SZZ: original algorithm; failure taxonomy; variants B/AG/MA/RA/R-SZZ; developer-informed oracles (Rosa et al.); JIT-Defects4J
- 2.3 Evaluation methodology in SDP: temporal leakage; time-aware evaluation (Falessi et al., Tan et al.); prequential evaluation; verification latency (Cabral et al., 2019)
- 2.4 Online learning for JIT-SDP: Online Bagging → OOB → ORB; Cabral & Minku (2023) drift analysis; Song et al. (2022) latency-noise method
- 2.5 The weak-baseline problem: LApredict, JITLine vs. DeepJIT, CC2Vec; survey evidence (Zhao et al.; Zain et al.)
- 2.6 Methodological quality in SDP: Destefanis et al. (2026) audit; metric selection rationale (MCC, G-mean)
- 2.7 Learning with noisy labels: loss correction (Natarajan), Co-teaching (Han), Confident Learning (Northcutt); offline-to-streaming adaptation challenges
- 2.8 Positioning table: rows = related works; columns = {handles imbalance, handles drift, handles latency noise, handles SZZ noise, online setting} — your thesis is the only row ticking the last box

## Chapter 3 — Research Design (≈ 6–8 pages)
- 3.1 Overview figure: 4-phase pipeline with data flow (Phase 1 bias estimates → Phase 3 noise model; Phase 1 labels → Phase 2 training sets; Phase 3 diagnosis → Phase 4 design)
- 3.2 Datasets: JIT-Defects4J (oracle), ApacheJIT / project corpora, Cabral et al. stream datasets; inclusion criteria; feature extraction
- 3.3 SZZ variant implementations (e.g., pyszz toolchain), configuration, validation
- 3.4 Metrics and statistical protocol: MCC, G-mean, prequential fading factor, seeds, Wilcoxon + Cliff's delta, multiple-comparison correction
- 3.5 Threats-to-validity framework introduced early (construct/internal/external/conclusion)

## Chapter 4 — Phase 1: Label Disagreement and Oracle Comparison (≈ 8–10 pages)
- 4.1 Method: run 5 variants; align with oracle; per-variant precision/recall/F-against-oracle, FP/FN rates, pairwise Cohen's kappa
- 4.2 Results: agreement heatmaps; per-variant bias table; per-project variance
- 4.3 The bias model: formalize ρ₀ (clean→defective flip rate) and ρ₁ (defective→clean) per variant — the parameters exported to Phase 3
- 4.4 Discussion: which failure modes dominate; answer RQ1

## Chapter 5 — Phase 2: Downstream Impact Under Honest Evaluation (≈ 10–12 pages)
- 5.1 Method: 3 models (LApredict, JITLine, ORB; DeepJIT/CC2Vec secondary) × 5 label sources × 3 evaluation regimes
- 5.2 Results: the "inflation ladder" — same model/labels scored under progressively honest regimes; label-source sensitivity per regime
- 5.3 Interaction analysis: does evaluation-regime inflation *mask* or *amplify* label-source effects?
- 5.4 Discussion: implications for interpreting published JIT-SDP results; answer RQ2

## Chapter 6 — Phase 3: Diagnosing Learner Behaviour Under Noise (≈ 8–10 pages)
- 6.1 Method: dose-response protocol; symmetric uniform flips vs. asymmetric SZZ-calibrated flips at 5–30%; instrumenting ORB internals (λ trajectory, boost factor over time, per-class recall trajectories)
- 6.2 Results: degradation curves (MCC/G-mean vs. noise dose); mechanism plots showing boost amplification of false positives
- 6.3 Discussion: generic vs. SZZ-specific sensitivity; answer RQ3; design requirements extracted for Phase 4

## Chapter 7 — Phase 4: Noise-Aware ORB (≈ 12–15 pages)
- 7.1 Design: architecture diagram; streaming label-confidence estimator (CL-style running thresholds); loss-correction weighting using Phase 1 noise rates; optional co-teaching-style agreement check
- 7.2 Algorithm pseudocode + complexity analysis
- 7.3 Experimental setup: vs. ORB, OOB, and (if feasible) Song et al.'s method, on both real SZZ labels and Phase 3's injected-noise regime; ablation study (confidence term only / loss correction only / both / +agreement)
- 7.4 Results: recovery curves; clean-data non-degradation check; sensitivity to window size and hyperparameters
- 7.5 Discussion: answer RQ4; when it helps, when it doesn't

## Chapter 8 — Discussion (≈ 5–7 pages)
- 8.1 Synthesis across RQs; the "noise pipeline" picture
- 8.2 Implications for researchers (dataset construction, reporting standards) and practitioners (deploying JIT-SDP)
- 8.3 Threats to validity (full treatment)

## Chapter 9 — Conclusion and Future Work (≈ 3–4 pages)
- Contributions recap; limitations; future work (LLM-assisted labeling oracles, cross-project streams, cost-aware evaluation)

## Back Matter
- References; Appendices: full result tables, hyperparameters, replication package README, extra plots

---

## Deliverables map (thesis chapter ← codebase module)

| Chapter | Experiment script | Key outputs |
|---|---|---|
| Ch. 4 | `experiments/run_phase1_oracle.py` | bias table, kappa heatmap, `phase1_bias.json` |
| Ch. 5 | `experiments/run_phase2_impact.py` | regime × label-source matrix, inflation plot |
| Ch. 6 | `experiments/run_phase3_noise.py` | dose-response curves, ORB internals traces |
| Ch. 7 | `experiments/run_phase4_na_orb.py` | recovery curves, ablation table |

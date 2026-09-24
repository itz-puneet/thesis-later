## Abstract

**Most of the reported performance of just-in-time software defect prediction is an artefact of how it is measured.** On the corpus studied here, a result that reads as 0.41 MCC under the field's standard protocol is 0.10 under a defensible one — and the single largest component of that gap is circular scoring: evaluating models against the same heuristic labels that trained them.

That is possible because JIT-SDP labels almost universally descend from the SZZ algorithm, which infers defect-introducing commits by blaming the lines a bug fix modifies. The inference fails whenever bug-fixing commits are tangled, and because no independent ground truth is available, models are conventionally scored against the very labels whose errors they may have learned.

**This report covers the first two phases of that measurement**, across 21 Apache Java projects and 27,319 commits, holding out an independently constructed reference label set so that a model trained on SZZ can be scored against something other than SZZ.

**Phase 1 — label quality.** Six SZZ variants are scored over an identical denominator. No variant exceeds **27.2% precision**. Noise is class-conditional rather than symmetric (false-alarm rates 6.7–26.3%, miss rates 35.9–73.3%). Variants agree with one another at κ up to **0.933** while agreeing with the reference at κ **0.158–0.202** — they share failure modes, so mutual agreement is not evidence of correctness. Decomposing the misses shows that for the most aggressive variants, **more than half of what their filters remove is correct**: refinement has relocated error rather than reduced it.

**Phase 2 — downstream impact.** Three models across seven label sources and four evaluation regimes, 16,380 runs, tested by paired Wilcoxon at the project level with Hodges–Lehmann estimates, bootstrap intervals and Holm correction applied both within family and globally. Random *k*-fold cross-validation inflates a high-capacity model by **+0.137 MCC** (21 of 21 projects); scoring against the training labels inflates it by a further **+0.230**. The two protocol effects together are roughly **nine times** the label-source effect, and both scale with model capacity. Under honest streaming evaluation with reconstructed verification latency, training on the reference labels beats all six SZZ variants, five of six surviving global correction.

A result reading **0.41 MCC** under the field's standard configuration is **0.10** under a defensible one. Because self-scoring is only possible where labels are heuristic, the labelling failure and the evaluation failure are not independent: the first creates the second.

**Scope.** Two questions are raised here and deliberately left open: which of SZZ's two error types an online learner cannot survive, and whether a learner can be built to withstand it. Chapter 6 states both designs, together with the specific controls this report has already shown they will require, and records in advance the commitment that the mitigation phase will be pre-registered.

## Abbreviations

| | |
|---|---|
| **CI** | Confidence interval |
| **FN / FP / TN / TP** | False negative / false positive / true negative / true positive |
| **HL** | Hodges–Lehmann estimator |
| **JIT-SDP** | Just-in-time software defect prediction |
| **MCC** | Matthews correlation coefficient |
| **OOB** | Oversampling Online Bagging |
| **ORB** | Oversampling Rate Boosting |
| **SZZ** | Śliwerski–Zimmermann–Zeller algorithm (variants: B-, AG-, MA-, R-, L-, RA-) |
| **ρ₀ / ρ₁** | Class-conditional false-alarm rate / miss rate |
| **λ** | Poisson oversampling rate in online bagging |
| **W** | Verification-latency decision window (90 days) |

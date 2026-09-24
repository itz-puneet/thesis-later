## Abstract

Just-in-time software defect prediction (JIT-SDP) labels almost universally descend from the SZZ algorithm, which infers defect-introducing commits by blaming the lines a bug fix modifies. That inference fails whenever bug-fixing commits are tangled, and the field has no measurement of what the resulting noise costs a model under realistic deployment conditions — in part because models are conventionally evaluated against the same SZZ labels that trained them.

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

## A note on corrections

One finding in this report contradicts a claim made earlier in the same project: a decomposition of the verification-latency effect, withdrawn after the contrast was found not to be identified. The superseded claim is stated together with the design error that produced it, rather than removed (§5.3).

This is deliberate. The correction is part of the evidence — it records which conclusions survived contact with a control and which did not, and the control that overturned it had been built for a different purpose.

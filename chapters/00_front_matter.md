# Quantifying and Mitigating SZZ-Induced Label Noise in Just-In-Time Software Defect Prediction under Verification-Latency-Aware Online Evaluation

**Puneet Deshwani** — M.Tech Thesis

---

## Abstract

Just-in-time software defect prediction (JIT-SDP) labels almost universally descend from the SZZ algorithm, which infers defect-introducing commits by blaming the lines a bug fix modifies. That inference fails whenever bug-fixing commits are tangled, and the field has no measurement of what the resulting noise costs a model under realistic deployment conditions — in part because models are conventionally evaluated against the same SZZ labels that trained them.

This thesis separates four quantities across 21 Apache Java projects and 27,319 commits, holding out an independently constructed reference label set so that a model trained on SZZ can be scored against something other than SZZ.

**Label quality.** Six SZZ variants are scored over an identical denominator. No variant exceeds **27.2% precision**. Noise is class-conditional rather than symmetric (false-alarm rates 6.7–26.3%, miss rates 35.9–73.3%). Variants agree with one another at κ up to **0.933** while agreeing with the reference at κ **0.158–0.202** — they share failure modes, so mutual agreement is not evidence of correctness.

**Evaluation protocol.** Random *k*-fold cross-validation inflates a high-capacity model by **+0.137 MCC** (21 of 21 projects); scoring against the training labels inflates it by a further **+0.230**. The two protocol effects together are roughly nine times the label-source effect, and both scale with model capacity. A result reading 0.41 MCC under the field's standard configuration is **0.10** under a defensible one.

**Mechanism.** A controlled repair experiment shows that removing SZZ's false positives recovers **+0.040 MCC** while restoring its false negatives is statistically *equivalent to no repair*. An error-matched control establishes this as an effect of error **volume**, not per-label severity. The mechanism is measured: the online learner's oversampling rate is a near-perfect inverse of delivered defect-label supply (ρ = −1.000), so the machinery that corrects class imbalance is the machinery that amplifies wrong labels.

**Mitigation.** A pre-registered train-time false-positive filter passes its non-degradation gate but no confirmatory test survives correction. The gap between the oracle-assisted repair (+0.040) and its deployable approximation (+0.017) quantifies the price of not knowing which labels are wrong: a confidence signal cannot separate a wrong label from an unlearned pattern.

On this evidence, **improving the labels is worth more than improving the learner.**

---

## Abbreviations

| | |
|---|---|
| **AUC** | Area under the ROC curve |
| **CI** | Confidence interval |
| **CL** | Confident Learning |
| **FN / FP / TN / TP** | False negative / false positive / true negative / true positive |
| **HL** | Hodges–Lehmann estimator |
| **JIT-SDP** | Just-in-time software defect prediction |
| **MCC** | Matthews correlation coefficient |
| **ND** | Non-degradation (Phase 4 acceptance gate) |
| **OOB** | Oversampling Online Bagging |
| **ORB** | Oversampling Rate Boosting |
| **SZZ** | Śliwerski–Zimmermann–Zeller algorithm (variants: B-, AG-, MA-, R-, L-, RA-) |
| **TOST** | Two one-sided tests (equivalence testing) |
| **ρ₀ / ρ₁** | Class-conditional false-alarm rate / miss rate |
| **λ** | Poisson oversampling rate in online bagging |
| **W** | Verification-latency decision window (90 days) |

---

## A note on corrections

Several findings in this thesis contradict claims made earlier in the same project: the false-negative starvation hypothesis Phase 4 was originally designed around, a decomposition of the verification-latency effect, and a conclusion about whether latency masks label quality. In each case the superseded claim is stated together with the design error that produced it, rather than removed.

This is deliberate. The corrections are part of the evidence — they record which conclusions survived contact with a control and which did not, and in three of the four cases the control that overturned the claim had been built for a different purpose. A caveat is not a control, and most of the substantive revisions in this work exist because that distinction was eventually enforced.

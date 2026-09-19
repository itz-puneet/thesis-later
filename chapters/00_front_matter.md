# Quantifying and Mitigating SZZ-Induced Label Noise in Just-In-Time Software Defect Prediction under Verification-Latency-Aware Online Evaluation

**Puneet Deshwani** — M.Tech Thesis

---

## Abstract

Just-in-time software defect prediction (JIT-SDP) labels almost universally descend from the SZZ algorithm, which infers defect-introducing commits by blaming the lines a bug fix modifies. That inference fails whenever bug-fixing commits are tangled, and the field has no measurement of what the resulting noise costs a model under realistic deployment conditions — in part because models are conventionally evaluated against the same SZZ labels that trained them.

This thesis separates four quantities across 21 Apache Java projects and 27,319 commits, holding out an independently constructed reference label set so that a model trained on SZZ can be scored against something other than SZZ.

**Label quality.** Six SZZ variants are scored over an identical denominator. No variant exceeds **27.2% precision**. Noise is class-conditional rather than symmetric (false-alarm rates 6.7–26.3%, miss rates 35.9–73.3%). Variants agree with one another at κ up to **0.933** while agreeing with the reference at κ **0.158–0.202** — they share failure modes, so mutual agreement is not evidence of correctness.

**Evaluation protocol.** Random *k*-fold cross-validation inflates a high-capacity model by **+0.137 MCC** (21 of 21 projects); scoring against the training labels inflates it by a further **+0.230**. The two protocol effects together are roughly nine times the label-source effect, and both scale with model capacity. A result reading 0.41 MCC under the field's standard configuration is **0.10** under a defensible one.

**Mechanism.** A controlled repair experiment shows that removing SZZ's false positives recovers **+0.040 MCC** while restoring its false negatives is statistically *equivalent to no repair*. An error-matched control establishes this as an effect of error **volume**, not per-label severity. The mechanism is measured: the online learner's oversampling rate is a near-perfect inverse of delivered defect-label supply (ρ = −1.000), so the machinery that corrects class imbalance is the machinery that amplifies wrong labels.

**Mitigation.** Two pre-registered experiments. A train-time false-positive filter passes its non-degradation gate but no confirmatory test survives correction; the gap between the oracle-assisted repair (+0.040) and its deployable approximation (+0.017) is the price of not knowing which labels are wrong, since a confidence signal cannot separate a wrong label from an unlearned pattern. A second registration then confirms that confidence damping beats both baseline and filter — and a control shows the entire benefit is the **absence of oversampling-rate boosting** rather than any defence: plain online bagging matches every noise-aware variant tested and beats the boosted learner in **18 of 18 projects** under false-positive-heavy noise.

This is independent confirmation, by intervention, of the amplification mechanism established by measurement, and it yields the thesis's one actionable recommendation. **Imbalance correction and label noise interact, and the standard remedy for the first makes the second worse:** under SZZ-derived labels, do not boost the oversampling rate on prediction bias.

Improving the labels remains worth more than improving the learner — but the cheapest effective intervention is neither.

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

Several findings in this thesis contradict claims made earlier in the same project: the false-negative starvation hypothesis Phase 4 was originally designed around, a decomposition of the verification-latency effect, a conclusion about whether latency masks label quality, and the mechanism attributed to confidence damping — refuted by its own registered test. In each case the superseded claim is stated together with the design error or the control that overturned it, rather than removed.

This is deliberate. The corrections are part of the evidence — they record which conclusions survived contact with a control and which did not, and in three of the four cases the control that overturned the claim had been built for a different purpose. A caveat is not a control, and most of the substantive revisions in this work exist because that distinction was eventually enforced.

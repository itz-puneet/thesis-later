# Chapter 9 — Conclusion and Future Work

## 9.1 What this thesis set out to do

The thesis began with a question about cost: how much does SZZ label noise cost a just-in-time defect prediction model? The question presumes that the cost is the interesting quantity, and that measuring it would tell the field how much to invest in better labels.

The four phases answered that question — under realistic streaming evaluation, training on SZZ rather than the reference costs between 0.034 and 0.064 MCC against a deployable baseline near 0.097 — and in answering it exposed a larger one. **Most of what the field reports is not capability but measurement artefact**, and the artefact is created by the same labelling weakness the thesis set out to quantify.

## 9.2 Contributions

**A characterisation of SZZ noise as a class-conditional channel.** Six variants scored over an identical 27,319-commit denominator, with a precision ceiling of 27.2%, bifurcated bias (ρ₀ 0.067–0.263, ρ₁ 0.359–0.733), and inter-variant agreement up to κ 0.933 against reference agreement of κ 0.158–0.202. **Variants share failure modes; their agreement is not evidence of correctness.** The flip-rate pairs are released as a calibration artefact for downstream noise modelling.

**A quantification of evaluation-protocol inflation, separated from label effects.** Random *k*-fold inflates a high-capacity model by +0.137 MCC (21/21 projects); scoring against the training labels inflates it by a further +0.230. **The protocol effects are roughly nine times the label-source effect**, and the inflation scales with model capacity, so it flatters exactly the models the field most promotes. The inflation ladder — 0.4129 under the field's standard configuration, 0.0970 under a defensible one — is the thesis's single most consequential number.

**A controlled identification of which SZZ error costs an online learner, with its mechanism.** Repairing false positives recovers +0.040 MCC; restoring false negatives is *equivalent to no repair* (TOST *p* = 0.0008) under three delivery regimes. An error-matched control establishes that this is a **volume** effect, not a per-label one. The mechanism is measured rather than inferred: the learner's oversampling rate is a near-perfect inverse of delivered defect-label supply (ρ = −1.000), so **the machinery that corrects class imbalance is the machinery that magnifies wrong labels**.

**A pre-registered negative result, with the reason it failed.** A train-time false-positive filter is adoptable but not demonstrably effective: the non-degradation gate passes, no confirmatory test survives correction. The gap between the oracle-assisted repair (+0.040) and the deployable approximation (+0.017) is **the price of not knowing which labels are wrong** — a confidence signal cannot separate "this label is wrong" from "I have not learned this yet", and defect labels are too scarce under latency for that confusion to be cheap.

**A reproducibility apparatus.** The full pipeline runs on a continuous-integration runner from two small committed files, gated by an assertion that recomputes the training data's confusion matrix and refuses to spend compute if it disagrees with the reported noise rates. The gate exists because the study encountered exactly the label-provenance failure it was written to study.

## 9.3 Limitations

The reference is `git blame` seeded with verified fix lines, not ground truth, so all measured noise is a **lower bound** and every comparison isolates tangling rather than total labelling error. The reference condition's label *timing* is SZZ-derived, which is the study's most serious construct threat and is not bounded by any analysis performed here. The corpus is one benchmark family of 21 Apache Java repositories and excludes deletion-introduced defects by construction. At *n* = 21, effects below roughly 0.04 MCC are unresolvable, which leaves the latency decomposition unresolved rather than null. The mechanism identified in Phase 3 is specific to learners whose oversampling responds to observed class rate.

## 9.4 Future work

**Validate against a non-blame reference.** The lower-bound claim is currently an argument, not a measurement. A developer-informed oracle — one in which the *developer* named the defect-introducing commit in the commit message, with no blame step in the chain — would test it directly. Such datasets exist but contain only fix-to-inducing links and no clean commits, so they cannot train a model; they can, however, validate Phase 1 against a reference that does not share SZZ's failure mode. **A caution for anyone attempting this:** precision figures reported against such oracles are conditional on fixes already known to have an inducing commit, whereas this thesis scores over an entire project history. The two are not comparable without reconciling the denominator, and the difference is large enough to look like a contradiction.

**Resolve the rescue anomaly.** Phase 4's mechanism probe was refuted: adding model-confident defect labels helps, while restoring genuinely missing ones does not. The obvious reconciliation — that the benefit comes from label supply rather than accuracy — was tested and failed (ρ = +0.357, *p* = 0.385). This is the sharpest open question the thesis leaves, and it is well posed: two interventions that both increase positive-label supply have opposite effects, and no current account explains why.

**Pre-register the damping arm.** Confidence damping outperformed the registered primary on six of eight conditions but was not the registered primary, so only one contrast survives correction. It deserves its own registration rather than promotion on exploratory evidence — which is precisely the practice this thesis criticises elsewhere.

**Effort-aware evaluation.** JIT-SDP is deployed as an inspection-prioritisation aid, so recall at a fixed inspection budget is closer to the practitioner's objective than MCC. Whether the inflation ladder has the same shape under effort-aware metrics is unknown and directly testable from the committed predictions.

**Cross-project and cross-language streams.** Every conclusion here is within-project and within-language. Whether the amplification mechanism survives a transfer setting, where the positive rate and the feature distribution both shift, is untested.

**Latency-aware label acquisition.** If false-positive volume is what costs the learner and 53% of defect labels arrive too late to help, the highest-value intervention may be neither a better labeller nor a better learner but a *faster* one — reducing the interval between defect introduction and label availability. Nothing in this thesis tests that, and it follows more directly from the results than any method it did test.

## 9.5 Closing

The thesis asked how much SZZ label noise costs a defect prediction model. The answer turned out to be less interesting than a question it exposed along the way: **how much of what the field reports is measurement artefact rather than capability?**

On this corpus, most of it. A number that reads as 0.41 under the field's standard protocol is 0.10 once the model is scored against something other than the heuristic that trained it and evaluated in an order that time permits. That gap — roughly four-fifths of the reported signal — is quantified here, bounded by confidence intervals, corrected for multiple comparisons, stable across every analytical choice tested, and reproducible from a single commit hash.

The last two phases asked the obvious follow-up — *so fix it* — and returned something more useful than a working method. The damage is done by the sheer volume of false positives SZZ invents, not by the defects it misses; the missing defects are provably worth nothing to recover. But a learner cannot act on that knowledge, because it cannot tell a wrong label from an unlearned pattern, and verification latency leaves it too few defect labels to risk discarding any.

That is a negative result, pre-registered as such, and it is reported at full strength rather than reframed. It is also the most informative finding after the measurement critique itself, because it locates the difficulty precisely: **the problem is not that nobody has built the right defence, but that the information required to build one is not available to a learner at training time.**

Which returns the field to where the thesis began, with a clearer instruction than it started with. **Improving the labels is worth more than improving the learner.**

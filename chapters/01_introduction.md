# Chapter 1 — Introduction

## 1.1 Context

Defects are expensive in proportion to how long they survive. A fault caught at review costs a developer's attention; the same fault caught in production costs an incident, a rollback and the trust of whoever depended on the system. This asymmetry motivates *defect prediction*: statistical models that direct limited inspection effort toward the code most likely to be wrong.

Classical defect prediction operates at release granularity, predicting which files or modules will contain defects. Its practical difficulty is one of timing. A prediction about a file, delivered at release, arrives long after the change that introduced the problem, and often reaches a developer who did not write it.

**Just-in-time software defect prediction (JIT-SDP)** moves the unit of prediction from the file to the *commit*. Each change is scored as it arrives, so a risky change can be flagged while its author still has it in mind. Kamei et al. (2013) established the modern form of the task, defining a set of change-level metrics — size, diffusion, history, and developer experience — that remain the standard feature set, and reporting roughly 68% accuracy and 64% recall at predicting defect-inducing changes.

The setting is unusual in three ways that jointly shape everything in this thesis. Commits arrive as a **stream**, so any realistic evaluation is temporal. Defect-introducing commits are **rare** — 8.54% on the corpus studied here — so the task is severely imbalanced. And, critically, **the label for a commit is not available when the commit arrives.** It becomes available only when someone finds the defect, traces it to its origin, and fixes it.

## 1.2 The ground-truth problem

JIT-SDP requires a label for every commit: did this change introduce a defect? Almost no project records this directly. What projects record is which commits *fixed* defects.

The gap is bridged by the **SZZ algorithm** (Śliwerski, Zimmermann and Zeller), which works backwards: take a bug-fixing commit, identify the lines it modified, and use `git blame` to find which earlier commit last touched each of those lines. Those earlier commits are labelled defect-introducing.

The inference is only as good as its premise — that the lines a fix modifies are the lines that were wrong. **That premise fails routinely, because bug-fixing commits are tangled.** Developers reformat while fixing, rename while fixing, refactor while fixing, update comments and tests while fixing. Every such line is blamed by SZZ, and every commit that last touched one is labelled as having introduced a defect it had nothing to do with.

The magnitude is now measured rather than suspected. Herbold et al. (2022), using four annotators per line, found that **between 17% and 32% of all changes within bug-fixing commits actually address the underlying problem** — rising to 66–87% when only production code files are considered. The remainder is tangled. Roughly 11% of lines were hard enough to classify that annotators actively disagreed.

A substantial body of work has proposed refinements — AG-SZZ, MA-SZZ, R-SZZ, L-SZZ, RA-SZZ — each adding filters intended to remove the over-collection. Whether those refinements improve the labels, and at what cost, is the subject of Chapter 4.

**The consequence for the field is structural.** Essentially every JIT-SDP dataset in use descends from SZZ. Models are trained on SZZ labels, evaluated against SZZ labels, and compared with one another on SZZ labels. If those labels are systematically wrong, the entire measurement apparatus is calibrated against a biased instrument — and, because the evaluation uses the same instrument as the training, the bias is invisible from inside.

## 1.3 The realism problem

A second problem is independent of labels and compounds them.

The standard evaluation protocol in the JIT-SDP literature is random *k*-fold cross-validation: shuffle the commits, hold out a fold, train on the rest. On temporally ordered data this permits a model to train on 2020 commits and be tested on 2015 ones. The resulting estimate answers a question nobody has: how well would this model do if it could see the future?

**Verification latency** is the subtler half. Even under a correct chronological split, the assumption that a commit's label is available at training time is false. The label exists only once the defect is found and fixed, and on this corpus the median delay is 113 days, with **53% of defect labels arriving after a 90-day decision window.**

This is worse than a delay. A system with a 90-day window does not simply wait — it concludes that an unfixed commit is clean, trains on that conclusion, and is corrected months later. **A learner under verification latency is actively trained on labels it will subsequently discover were wrong**, and the wrong labels it receives are exactly the defect-introducing commits it most needs to learn from.

Cabral and Minku (2019) characterised this setting, showing that the class imbalance itself evolves over time under latency, and proposed **Oversampling Rate Boosting (ORB)** — an online ensemble that adjusts its resampling rate when predictions become biased toward one class. ORB is the online learner used throughout this thesis, and the mechanism it uses to handle imbalance turns out, in Chapter 6, to be the mechanism through which label noise does its damage.

## 1.4 Problem statement

> Just-in-time defect prediction is evaluated almost exclusively against labels produced by SZZ, using protocols that ignore both commit order and verification latency. The field therefore has **no measurement of what SZZ-induced label noise costs a model under realistic deployment conditions**, and no way to distinguish a model's ability to find defects from its ability to reproduce the heuristic that labelled them.

Four things must be separated to make progress: the noise in the labels; the inflation contributed by the evaluation protocol; the *mechanism* by which noise damages an online learner; and whether a learner can defend itself. This thesis addresses them in that order, as four phases.

## 1.5 Research gap

Three lines of work approach this territory without closing it.

**SZZ evaluation research** measures how accurately SZZ variants identify defect-introducing commits, including against developer-informed oracles. It establishes that the labels are noisy. It stops at the labels and does not measure the downstream cost.

**Online JIT-SDP research** addresses class imbalance evolution and verification latency, and Cabral and Minku's ORB includes a safety mechanism against potentially noisy minority-class examples. This work treats noise as a nuisance to be dampened rather than as a measurable quantity with a known, asymmetric structure and a known origin.

**Learning with noisy labels** provides loss correction, sample selection and confidence-based methods. These are almost entirely batch methods developed for symmetric or uniform label noise, and do not transfer directly to a stream in which labels arrive late, arrive wrong, and are later corrected.

**The gap is the intersection.** No existing work measures the cost of *SZZ-origin* noise — asymmetric, variant-dependent, with known flip rates — under *latency-aware online* evaluation, and no work isolates which of SZZ's two error types an online learner actually cannot survive. This thesis occupies that intersection, and its central methodological device is the one that makes the intersection measurable: **holding out an independently constructed reference label set so that a model trained on SZZ can be scored against something other than SZZ.**

## 1.6 Research questions

**RQ1.** How much do SZZ variants disagree with one another and with an independently constructed reference, and what is the direction of each variant's labelling bias? *(Chapter 4)*

**RQ2.** How does the choice of SZZ label source shift measured JIT-SDP performance across naive, chronological, and prequential-with-latency evaluation regimes? *(Chapter 5)*

**RQ3.** Through what mechanism does label noise degrade an online learner — specifically, how does ORB's oversampling response behave under symmetric versus SZZ-calibrated asymmetric noise as the dose increases? *(Chapter 6)*

**RQ4.** Can an online learner recover performance lost to SZZ-origin noise without access to clean labels, and without sacrificing performance when the labels are clean? *(Chapter 7)*

## 1.7 Contributions

**A class-conditional characterisation of SZZ noise.** Six variants scored over an identical 27,319-commit denominator: a precision ceiling of 27.2%, bifurcated bias (ρ₀ 0.067–0.263, ρ₁ 0.359–0.733), and inter-variant agreement of κ up to 0.933 against reference agreement of κ 0.158–0.202. **Variants share failure modes, so their mutual agreement is not evidence of correctness.** The flip-rate pairs are released as a calibration artefact.

**A separation of protocol inflation from label effects.** Random *k*-fold inflates a high-capacity model by +0.137 MCC (21 of 21 projects); self-scoring inflates it by a further +0.230. The two protocol effects together are roughly nine times the label-source effect, and the inflation scales with model capacity.

**A controlled identification of which SZZ error costs an online learner, and why.** Repairing false positives recovers +0.040 MCC; restoring false negatives is *equivalent to no repair*. An error-matched control establishes this as a volume effect rather than a per-label one, and the mechanism is measured: the learner's oversampling rate is a near-perfect inverse of delivered defect-label supply.

**A pre-registered negative result with a diagnosis.** A train-time false-positive filter is adoptable but not demonstrably effective, and the gap between the oracle-assisted repair and its deployable approximation quantifies the price of not knowing which labels are wrong.

**A reproducible pipeline with an integrity gate.** The full study runs on a continuous-integration runner from two small committed files, behind an assertion that recomputes the training data's confusion matrix and refuses to spend compute if it disagrees with the reported noise rates.

## 1.8 Thesis organisation

**Chapter 2** surveys JIT-SDP, SZZ and its variants, evaluation methodology, online learning under latency, and learning with noisy labels, and positions this work against each.

**Chapter 3** states the research design: the four-phase pipeline, the corpus and its reference labels, the SZZ toolchain, the metrics and statistical protocol, and the validity framework — stated in advance rather than assembled afterwards.

**Chapters 4 to 7** report the four phases, one research question each.

**Chapter 8** synthesises the four results into a single account and gives the full treatment of validity threats.

**Chapter 9** concludes.

**A note on how the results chapters are written.** Several findings in this thesis contradict claims made earlier in the same project — the starvation hypothesis Phase 4 was designed around, a decomposition of the latency effect, a conclusion about whether latency masks label quality. In each case the superseded claim is **stated, together with the design error that produced it**, rather than removed. The corrections are part of the evidence: they show which conclusions survived contact with a control and which did not.

# Chapter 6 — Conclusions and Planned Work

This report covers the first two phases of the project. This chapter states what they establish, what they do not, and how the remaining phases are designed — including two commitments made here, in advance, rather than after the data are seen.

---

## 6.1 What Phases 1 and 2 establish

### 6.1.1 The two research questions answered

**RQ1 — How much do SZZ variants disagree, and in which direction?** Substantially, and structurally. No variant exceeds **27.2% precision** against the reference. Variants agree with one another at κ up to **0.933** while agreeing with the reference at κ **0.158–0.202** — four to six times more strongly with each other than with the thing they are estimating. Bias is bifurcated: B-SZZ over-flags (ρ₀ = 0.263), while L-SZZ and R-SZZ under-flag (ρ₁ = 0.733 and 0.700). **Two decades of refinement have relocated error rather than reduced it**, moving it from the false-positive column to the false-negative column.

**RQ2 — How does the label source shift measured performance across regimes?** It shifts it significantly — 0.034 to 0.064 MCC under realistic streaming, against a deployable baseline near 0.097. **But the evaluation protocol shifts it far more.** Random *k*-fold inflates a high-capacity model by **+0.137 MCC**; scoring against the training labels inflates it by a further **+0.230**. The two protocol effects together are roughly nine times the label-source effect, and both scale with model capacity.

### 6.1.2 The finding that reframes the project

The project set out to measure what SZZ noise costs. It found that **the cost of SZZ noise is small relative to the cost of the field's evaluation conventions** — and that the two are not independent.

Self-scoring is only possible *because* the labels are heuristic. If the field had ground truth, it would score against it, and the +0.230 gap could not exist. **The labelling failure creates the evaluation failure.** A result reported under random *k*-fold with self-scored SZZ labels is not a measurement of defect-prediction capability, and on this corpus the difference between that protocol and a defensible one is 0.41 against 0.10 MCC.

### 6.1.3 Practical significance, stated honestly

The measurement critique is statistically overwhelming — rank-biserial +1.000 on the leakage effect, 21 of 21 projects, surviving global correction. **Practical significance is more modest and should be reported as such.** Even with the reference labels and an honest protocol, deployable MCC on this corpus is approximately **0.097**.

This report does not claim that better labels would make JIT-SDP good. It claims the field's reported numbers overstate what it currently achieves by roughly a factor of four. The low ceiling is itself a finding: a field reporting 0.41 and delivering 0.10 has a calibration problem independent of whether 0.10 is useful.

### 6.1.4 The reconciliation a reader will otherwise trip over

Studies that evaluate SZZ against developer-informed oracles report precision in the range 0.39–0.66. This report reports 0.186–0.272. **The two are not in conflict, and the difference is the denominator.**

Those studies score *conditionally* on bug-fixing commits already known to have an inducing commit: given a defect, which earlier commit introduced it? This report scores over an entire project history of 27,319 commits, the overwhelming majority of which are clean: is *this* commit, drawn from all of history, defect-introducing? A variant right two times in three on the first question can be wrong four times in five on the second. **Any comparison between the two literatures has to reconcile the denominator first.**

---

## 6.2 What Phases 1 and 2 do not establish

Three questions are raised by this report and are not answerable from its evidence. Each is stated with the design that would answer it.

### 6.2.1 Which SZZ error actually costs the learner

Phase 2 shows that label quality matters under streaming. It does **not** show whether the cost comes from the false positives SZZ invents or from the defects it misses. The simplest explanation is ruled out: the penalty does not track a variant's recall (ρ = −0.18), and L-SZZ and B-SZZ have almost identical gaps despite recalls of 0.267 and 0.641.

The question cannot be settled by comparing label sources, because whole labelling procedures differ in many ways at once. **It needs an intervention.** Phase 3's design takes real B-SZZ labels and uses the reference to correct *one error type at a time* — removing the false positives, or restoring the false negatives — holding the stream, the learner and the latency model fixed. The difference between conditions is then attributable to the repair.

**Two controls must be built into that design from the start**, because this report has already identified the confounds they would otherwise create:

- **Error matching.** B-SZZ carries 6,565 false positives against 837 false negatives, an 8:1 imbalance (§4.2.1). "Repair all of each" therefore conflates *which error is costlier per label* with *which error there is more of*. The design must include a matched-mass condition.
- **Delivery.** A restored false negative has no linked fix and so no natural arrival time. If arrival times are imputed from the empirical latency distribution, a null result cannot distinguish "these labels do not matter" from "these labels cannot arrive in time to matter". The design must include an immediate-delivery ceiling condition.

### 6.2.2 Why an online learner should be sensitive at all

ORB handles class imbalance by oversampling at a rate set from the *observed* rate of defect labels — that is, from label **quantity**. It has no access to label **quality**, so a false positive receives the same amplification as a true one.

That makes amplification a plausible route by which SZZ noise damages an online learner, and it makes a measurable prediction: the oversampling rate applied to defect-labelled arrivals should be an inverse function of how many such labels the stream delivers, *regardless of whether they are correct*. **This report does not test that.** Instrumenting the learner's internal rate across a calibrated dose grid would.

### 6.2.3 Whether the latency effect can be isolated

§5.3 shows that the batch-to-streaming drop cannot be decomposed by comparing label sources, because the contrast is not identified, and that the 2×2 which *is* identified returns no resolvable effect at *n* = 21 — every contrast, including the interaction, has an interval spanning zero.

The obstacle is that switching label sources changes the learner's training signal and its evaluation window together. A design that **holds the learner fixed by construction** — injecting controlled noise into a single label source rather than switching between sources — removes that confound. It also requires a true no-latency control: an arm in which *every* label, positive and negative, arrives immediately. A fixed-delay arm is not a no-latency arm, since it delays the 91.5% majority class as heavily as the minority.

---

## 6.3 Commitments made in advance

Two are recorded here so that they precede the data rather than follow it.

**The mitigation phase will be pre-registered.** Hypotheses, primary model, acceptance bar and multiplicity correction will be committed to version control before the first run, and the commit history will timestamp the order. Phases 1 and 2 are exploratory and are labelled as such throughout; the global Holm column is what makes their headline claims defensible without a registration.

**The non-degradation gate is the acceptance bar, not the headline test.** A mitigation that improves performance on noisy labels while damaging it on clean ones is not adoptable, because a practitioner cannot know in advance which case they are in. That gate will be applied before any effect size is examined.

---

## 6.4 Threats to validity

**The reference is not ground truth.** It is `git blame` seeded with human-verified fix lines (§3.2.2). Comparisons against it isolate the cost of tangled commits, not total labelling error, and **all measured noise is therefore a lower bound**: blame error is present on both sides of every comparison and cancels.

**The reference condition's label timing is SZZ-derived.** This is the most serious threat in the study. The published labels carry no native fix-to-inducing linkage, so arrival times were reconstructed from the union of SZZ mappings. The reference is blame-derived in construction *and* SZZ-derived in timing. A coverage sensitivity analysis (67.8% → 100%) bounds part of the exposure; the timing itself is not bounded, and every streaming result inherits it.

**The corpus is SZZ-shaped.** Changes adding no new lines were excluded by the dataset authors, so defects introduced purely by deletion cannot appear. Because the reference is itself blame output, blame-unreachability is not an available explanation for any measured false negative.

**Project heterogeneity is measured and does not drive the results.** Projects span 544–4,026 commits and 19–335 defects and are weighted equally. Excluding those below a 25-defect floor moves no headline estimate by more than 0.002 MCC, and all headline claims still survive correction (§5.4).

**Effects below roughly 0.04 MCC are not resolvable at *n* = 21.** This is load-bearing for the latency decomposition, which is reported as unresolved rather than as null.

**Nothing here is pre-registered**, which is why global multiplicity correction is reported alongside the within-family correction, and why the headline claims are those surviving the global column.

**One benchmark family.** Twenty-one Apache Java repositories of a single dataset lineage.

---

## 6.5 Closing

The report began by asking how much SZZ label noise costs a defect prediction model. The answer — between a third and two-thirds of the available signal under realistic streaming — turned out to be less interesting than a question it exposed along the way: **how much of what the field reports is measurement artefact rather than capability?**

On this corpus, most of it. A number that reads as 0.41 under the field's standard protocol is 0.10 once the model is scored against something other than the heuristic that trained it and evaluated in an order that time permits. That gap — roughly four-fifths of the reported signal — is quantified here, bounded by confidence intervals, corrected for multiple comparisons, stable across every analytical choice tested, and reproducible from a single commit hash.

What the report cannot yet say is *why*: which of SZZ's two errors an online learner cannot survive, and whether a learner can be built to withstand it. Those are the next two phases, and §6.2 states both the designs and the controls that this report has already shown they will need.

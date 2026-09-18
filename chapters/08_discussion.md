# Chapter 8 — Discussion

The four phases were designed to answer four questions in sequence. In the event, two of them returned answers the design did not anticipate, and one returned a negative. This chapter reads the four results as a single argument, states what follows for researchers and for practitioners, and gives the full treatment of validity threats.

---

## 8.1 Synthesis across the research questions

### 8.1.1 The four answers

**RQ1 — How much do SZZ variants disagree, and in which direction?** Substantially, and structurally. No variant exceeds **27.2% precision** against the reference. Variants agree with one another at κ up to **0.933** while agreeing with the reference at κ **0.158–0.202** — four to six times more strongly with each other than with the thing they are estimating. Bias is bifurcated: B-SZZ over-flags (ρ₀ = 0.263), L-SZZ and R-SZZ under-flag (ρ₁ = 0.733, 0.700). **Two decades of refinement have relocated error rather than reduced it**, moving it from the false-positive column to the false-negative column.

**RQ2 — How does label source shift measured performance across regimes?** It shifts it significantly — 0.034 to 0.064 MCC under realistic streaming, against a deployable baseline near 0.097. **But the evaluation protocol shifts it far more.** Random *k*-fold inflates a random forest by **+0.137 MCC**; scoring against the training labels inflates it by a further **+0.230**. The two protocol effects together are roughly nine times the label-source effect.

**RQ3 — Through what mechanism does noise degrade an online learner?** Through amplification rather than starvation. Repairing B-SZZ's false positives recovers **+0.040 MCC**; restoring its false negatives is *equivalent to no repair* (TOST *p* = 0.0008) under realistic, immediate and at-window delivery alike. The mechanism is measurable: ORB's oversampling rate is a near-perfect inverse of delivered defect-label supply (**ρ = −1.000**). The boost compensates for label *scarcity* and cannot distinguish a scarce-but-correct stream from a scarce-and-wrong one.

**RQ4 — Can a learner recover that loss without the reference?** Not demonstrably. The pre-registered non-degradation gate passes, so the intervention is adoptable; every confirmatory test points the predicted way and **none survives correction**. The oracle-assisted repair recovers +0.040; the deployable approximation recovers +0.017 and is not significant.

### 8.1.2 The noise pipeline, read end to end

The four results compose into one account of how a number becomes untrustworthy.

**Stage 1 — The labels are wrong, asymmetrically.** Tangled commits cause SZZ to blame lines that fix nothing. Filters remove some of that over-collection and, for the aggressive variants, more than half of what they remove is correct.

**Stage 2 — The evaluation hides it.** Because the labels are heuristic, models are scored against the same heuristic that trained them. A high-capacity model that fits the heuristic's error structure is rewarded for doing so. **This is only possible because the labels are wrong**: with ground truth there would be nothing to score against but truth, and the +0.230 gap could not exist. The two problems are not independent — the labelling failure creates the evaluation failure.

**Stage 3 — Deployment removes the protections.** Under streaming with verification latency, the learner's imbalance machinery amplifies whatever defect labels arrive. Most of the surviving labels are false positives, and they are amplified hardest exactly when defect labels are scarcest — which, given that 53% arrive after the decision window, is always.

**Stage 4 — Knowing this is not sufficient to fix it.** Identifying *which kind* of error hurts does not confer the ability to identify *which instances* are that error. A confidence signal cannot separate "this label is wrong" from "I have not learned this pattern yet", and under an 8.5% positive rate the second case is common.

**The unifying quantity is deliverable precision.** What an online learner needs is not correct labels in the abstract but correct labels that *arrive* — and among those that arrive, false positives are the error it cannot defend against, because its own imbalance mechanism amplifies them. Every result in this thesis is a corollary of that sentence, including the retirement of the starvation hypothesis it began with.

### 8.1.3 Statistical significance and practical significance

The measurement critique is statistically overwhelming: rank-biserial +1.000 on the leakage effect (21 of 21 projects), +0.991 on the self-scoring gap, intervals excluding zero by wide margins, survival under global correction.

**Practical significance is more modest and should be stated as such.** Even with perfect labels and an honest protocol, deployable MCC on this corpus is approximately **0.097**. Repairing every false positive raises it to 0.096 from 0.058 — a 66% relative gain on a small absolute base. **This thesis does not claim that better labels would make JIT-SDP good.** It claims they would make it measurably less self-sabotaging, and that the field's reported numbers overstate what it currently achieves by roughly a factor of four.

The low ceiling is itself a finding. A field reporting 0.41 and delivering 0.10 has a calibration problem independent of whether 0.10 is useful.

---

## 8.2 Implications

### 8.2.1 For researchers building datasets

**Stop treating inter-tool agreement as validation.** Variants agreeing at κ 0.93 while agreeing with the reference at κ 0.16 is the clearest result in Chapter 4. Agreement between procedures that share a blame step and a set of assumptions measures shared failure modes.

**Report the denominator.** A variant scored on the candidates it emits will appear more precise than one scored on the whole corpus. Chapter 4's comparison is only interpretable because every variant was scored over an identical 27,319-commit population.

**Report both flip rates, not a single noise rate.** ρ₀ and ρ₁ differ by a factor of eleven across the variants studied here. Any downstream noise model calibrated on a single scalar will be wrong for five of the six.

**Distinguish rate from volume.** At an 8.5% positive rate, a ρ₀ of 0.263 produces 6,565 wrong labels while a ρ₁ of 0.733 produces 1,710. Chapter 6's central finding turns entirely on this distinction, and the error-matched control that established it is cheap to run.

### 8.2.2 For researchers reporting results

**Random *k*-fold on temporally ordered data is not defensible**, and the inflation it produces is *larger for models with more capacity to exploit it*. Comparisons between model families measured this way are confounded, and the confound flatters exactly the models the field most wants to promote.

**Score against something other than the labels you trained on**, or state plainly that the number measures fidelity to a heuristic. Where no independent reference exists, the honest description of a self-scored result is "reproduces SZZ at MCC *x*", not "detects defects at MCC *x*".

**Name the prequential estimator.** A terminal fading value and a trajectory mean disagree on the sign of one comparison in this thesis and would have supported a claim that had to be withdrawn. Neither is canonical for MCC, which is not a decomposable loss.

**Report multiplicity correction globally when families were not pre-declared.** The distinction costs one column and removes an entire class of objection.

### 8.2.3 For practitioners

**Expect roughly 0.10 MCC, not 0.40.** If a JIT-SDP tool is evaluated on your own repository under an honest protocol and returns something near 0.10, it is performing as well as the state of the practice on this corpus — not failing.

**Label quality is worth more than model sophistication.** Reference labels beat every SZZ variant under streaming; a single-feature logistic regression beats a 100-tree forest under a chronological split. Investment in knowing which commits actually introduced defects dominates investment in the learner.

**If you must use SZZ, prefer the permissive variant and accept the false positives** — B-SZZ carries the smallest penalty of the six under streaming, and the aggressive filters discard more correct answers than incorrect ones. This runs against the direction of variant development and is stated because the data support it.

**Do not deploy a confidence-based label filter on the strength of this work.** Chapter 7 tested one, it passed the non-degradation gate, and it did not demonstrably help. A fixed-threshold variant was actively harmful on clean labels.

---

## 8.3 Threats to validity

### 8.3.1 Construct validity

**The reference is not ground truth, and every comparison inherits that.** It is `git blame` seeded with human-verified fix lines. Comparisons against it isolate the cost of tangled commits, not total labelling error. **All measured noise is therefore a lower bound**: blame error is present on both sides and cancels.

**The reference condition's label timing is SZZ-derived.** This is the most serious threat in the study. The published labels carry no native fix-to-inducing linkage, so arrival times were reconstructed from the union of SZZ mappings. The reference is blame-derived in construction *and* SZZ-derived in timing. A coverage sensitivity analysis (67.8% → 100%) bounds part of the exposure; the timing itself is not bounded, and every streaming result in Chapters 5–7 inherits it.

**The corpus is SZZ-shaped.** Changes adding no new lines were excluded by the dataset authors, so defects introduced purely by deletion cannot appear. Separately, because the reference is blame output, every reference positive is blame-reachable by construction, so blame-unreachability is not an available explanation for any measured false negative. This limit was declared before Phase 3 ran.

### 8.3.2 Internal validity

**Phase 3's repair conditions are not error-matched, and the matched control changed the claim.** Repairing "all of each" compares 6,565 corrections against 837. At equal mass the two error types are indistinguishable. The supported claim is about error *volume*; the per-label claim is explicitly disclaimed.

**Phase 3's dose parameterisation is not class-balanced.** Dose is a fraction of all commits, so the FN-heavy profile strips far more of the minority class at equal dose, and at the highest dose leaves a stream whose defect labels are *all false*. Slopes are fitted only on cells retaining genuine defect labels.

**One published conclusion was wrong and is corrected rather than removed.** An earlier version reported that latency does not compress sensitivity to label quality. That comparison ran between two uniformly delayed arms and could not test the question; against a true no-latency control the conclusion reverses.

**The latency decomposition is unresolved, not null.** A full 2×2 was built after the original decomposition was found to be unidentified. Every contrast, including the interaction, has an interval spanning zero.

**A label-vintage defect was found and fixed mid-study.** Models had trained on labels one commit older than the noise rates reported, affecting 1.0–6.5% of commits per variant. The remediation ships as an executable gate that runs before any compute.

**Phase 4's held-out projects were not randomly assigned.** They were chosen after Phases 1–3 were analysed. Nothing in Phase 4's reported numbers depends on them, but the assignment was purposive.

### 8.3.3 External validity

**One benchmark family.** Twenty-one Apache Java repositories of a single dataset lineage. Java-specific idioms, Apache-specific review culture and the dataset's own inclusion criteria are all uncontrolled.

**Project heterogeneity is real but does not drive the results.** Projects span 544–4,026 commits and 19–335 defects and are weighted equally. Excluding those below a 25-defect floor moves no headline estimate by more than 0.002 MCC and all four Tier 1/Tier 2 claims still survive correction.

**The mechanism is architecture-specific.** The amplification account applies to learners whose oversampling responds to observed class rate. A learner without that machinery would have a different failure mode, and Chapter 6's conclusions should not be transferred to one.

### 8.3.4 Conclusion validity

**Effects below roughly 0.04 MCC are not resolvable at *n* = 21.** This is load-bearing for the latency decomposition and for Phase 4's H1 (+0.017), and both are reported as unresolved rather than as null.

**The exploratory comparison count is large**, which is why global correction is reported alongside within-family correction and why headline claims are those surviving the global column.

**Phase 4's negative could be a power failure rather than an absence.** Four registered tests agreeing in direction, with H1's interval barely excluding zero, is consistent with a real effect too small to resolve at *n* = 18. The chapter says "not demonstrated to work", not "shown not to work", and the distinction is deliberate.

### 8.3.5 Threats that were anticipated versus discovered

Anticipated in Chapter 3 and unchanged: the reference's construct limits, the single benchmark family, the equal weighting of unequal projects, the resolution floor.

**Discovered during the work**, and recorded because the pattern is itself informative: the error-matching confound, the dose parameterisation trap, the degenerate quantile rule, the label-vintage cache defect, the unidentified latency decomposition, and the no-latency arm that was not one. Every one of these was found by a control that had been built for a different purpose, or by a reviewer asking what a caveat was doing in place of an experiment. **A caveat is not a control**, and five of the six corrections in this thesis exist because that distinction was eventually enforced.

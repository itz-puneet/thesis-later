# Chapter 7 — Phase 4: Noise-Aware ORB

Chapter 6 established what an online learner cannot survive: the volume of false positives SZZ invents, amplified by the very mechanism that corrects class imbalance. It also showed what recovering from that is worth — **+0.040 MCC** — using the reference labels to remove exactly the wrong ones.

This chapter answers **RQ4**: can a learner approximate that repair *without* the reference, and without sacrificing performance when the labels are clean?

**The answer is no, and this chapter reports that at full strength.** The intervention is adoptable — it does not damage clean labels — but no confirmatory test survives multiplicity correction. This is a **pre-registered characterised negative**, and the chapter is organised to explain not merely that it failed but *why*, because the reason is more informative than a success would have been.

---

## 7.1 Pre-registration, and a registration that was rewritten

### 7.1.1 Why Phase 4 is pre-registered and Phases 1–3 are not

Phases 1–3 are exploratory. Their hypotheses were formed during analysis, their test families were defined after seeing the data, and every result is labelled accordingly, with a conservative global multiplicity correction applied so that no claim depends on how the families were drawn.

Phase 4 is different in kind. It proposes a method and asks whether it works — a question that invites the analytic flexibility pre-registration exists to constrain. Its hypotheses, its primary model, its acceptance bar and its multiplicity correction were therefore committed to version control **before the first Phase 4 run**, and the commit history timestamps that claim independently of this chapter's narration.

### 7.1.2 The registration was revised once, and the revision is part of the record

The original registration made a **false-negative rescue** mechanism the headline: when the ensemble confidently disagrees with a clean label, train the commit as a provisional positive. That design followed directly from the starvation hypothesis Phase 4 was planned under.

Chapter 6 refuted that hypothesis. Restoring genuinely missing defect labels is *equivalent to no repair* (TOST *p* = 0.0008). A mechanism that manufactures positives therefore targets an error shown to cost nothing — and worse, every incorrect rescue manufactures exactly the error type Chapter 6 showed to be costly.

Because Phase 4 had produced **zero results** at that point, the registration was rewritten and re-committed. **That is the only moment at which revising a pre-registration is legitimate**: before any outcome is visible. Revising afterwards is the practice pre-registration exists to prevent, and the distinction between the two is entirely a matter of timing, which is why the timing is recorded rather than asserted.

The rescue mechanism was not discarded. It was **demoted to a mechanism probe carrying a predicted sign**, so that it would test Chapter 6's account rather than merely be excluded by it.

### 7.1.3 The registered tests

| Tag | Test | Prediction |
|---|---|---|
| **ND** | Filter vs baseline on reference labels | **No significant drop** (TOST, ±0.02). The acceptance bar |
| **H1** | Filter beats baseline on B-SZZ | Positive (6,565 false positives — the most available) |
| **H2a/b** | Filter beats baseline on MA-SZZ and AG-SZZ | Positive (5,030 and 4,786) |
| **H3** | Benefit rank-correlates with each variant's false-positive count | ρ > 0, one-sided |
| **MP** | Rescue vs baseline on every SZZ source | **≤ 0** on all six |
| **R1** | λ self-antagonism arm | `suppress` underperforms `observed` |

**H3 is the sharpest test in the chapter**, and it exists because of Chapter 6's error-matched control. If the benefit is driven by false-positive *volume*, it should track how many false positives each source contains — a predicted ordering over six variants whose counts were fixed in advance (6565, 5030, 4786, 4531, 2316, 1665). An ordering is far harder to satisfy by chance than a binary comparison.

**ND is the acceptance bar, not H1.** A filter that wins on noisy labels and damages clean ones is not deployable, because a practitioner cannot know in advance which case they are in.

---

## 7.2 Design

### 7.2.1 The intervention

`FPFilterORB` extends ORB with train-time false-positive suppression. A defect-labelled arrival that the ensemble confidently contradicts is treated as a suspected SZZ false positive: trained at weight ε (with ε = 0 discarding it) and excluded from the boost. **Clean-labelled arrivals are untouched**, since Chapter 6 showed that intervening on the negative side recovers nothing.

### 7.2.2 Two decision rules, and why the obvious one fails

The natural rule — and the one originally specified — is a running quantile: suppress a positive whose probability falls in the lowest *q* of recently delivered positives. It requires no calibration, which is its appeal.

**Measured on this corpus that rule is degenerate.** The ensemble's members agree almost completely, so the predicted probability is bimodal at 0 and 1, and the 10th percentile of a trailing window is **0.0000 in nearly every segment of every stream**. A strict comparison against a threshold of zero can never fire: on opennlp/B-SZZ it suppressed **0 of 75** positive arrivals. The rule was not wrong in conception; it was wrong in its comparison operator, and a non-strict comparison repairs it.

The alternative is a fixed threshold τ. §7.4.1 shows it fails for a deeper reason.

```
FPFilterORB.learn_one(x, y):
    if y == 0:
        ORB.learn_one(x, y);  return          # negatives untouched

    p1  ← ensemble_probability(x)
    thr ← τ                    if mode = fixed
          quantile(window, q)  if mode = quantile and |window| ≥ min_pos
          ⊥                    otherwise      # inert during warm-up
    suspect ← (thr ≠ ⊥) and (p1 < thr  if fixed  else  p1 ≤ thr)
    window.append(p1)

    if suspect:
        if rate_update = "observed":
            r₁ ← decay·r₁ + (1−decay)·1       # distrust the LABEL, not the class rate
        if ε > 0:
            k ~ Poisson(ε);  update_members(x, 1, k)
        return                                 # no boost, no full-weight update

    ORB.learn_one(x, y)
```

**Complexity.** One additional ensemble forward pass per defect-labelled arrival and one quantile over a bounded window, so *O*(*M* + log *W*) per positive with *M* ensemble members and window *W*, against ORB's *O*(*M*·λ) update. Since positives are 8.5% of arrivals and λ routinely exceeds 20, the filter's cost is negligible.

**Warm-up is counted in positive labels, not arrivals.** Positives are what is scarce: under realistic latency some projects deliver fewer than 30 across an entire stream, and a quantile over an empty window is undefined. Below `min_pos` the filter is inert and the model is plain ORB — the safe direction.

### 7.2.3 The registered risk: λ self-antagonism

Chapter 6 measured ORB's oversampling rate to be a near-perfect inverse of delivered defect-label supply (ρ = −1.000), and the mechanism is explicit in the update: λ₁ = (1 − r₁)/r₁. **Every positive this filter suppresses therefore raises λ for the positives that survive it.** The filter works against the machinery it is bolted onto.

The `rate_update` switch controls whether it does:

- **`observed`** — r₁ is updated as though the label had been accepted. Suppressing a label expresses distrust of *that label* without telling the ensemble the defect class is rarer than it is. λ is left alone.
- **`suppress`** — the arrival is skipped entirely, r₁ drifts down, λ rises.

**Registered prediction: `suppress` underperforms `observed`, with the gap widening as filter rate rises.** A second risk — that a suppressed positive is never learned, so its probability stays low and it is suppressed again — is instrumented rather than assumed: every decision is traced.

---

## 7.3 Experimental setup

**Models.** OOB and ORB as baselines; `NA(fp_filter)` as the registered primary; `NA(fp_filter/suppress)` as the R1 arm, carrying identical hyperparameters with only the switch flipped; `NA(damp)`, the prior confidence-damping defence, for comparison; `NA(rescue)` as the MP probe.

A composed `NA(fp_filter+damp)` arm appeared in the first draft of the registration but was **never implemented** — the placeholder returned a duplicate of the primary, which would have reported one model under two names and made the ablation look richer than it is. It was dropped before any Phase 4 run, at the same moment and for the same reason the registration itself could legitimately be revised.

**Conditions.** Reference labels (the ND gate), all six SZZ variants, and a 20% injected-noise condition bridging to Chapter 6.

**Held-out projects.** `commons-scxml`, `opennlp` and `commons-math` are excluded from every reported number. Hyperparameters were chosen by looking at them, so including them would leak the tuning set into the results. Reporting is therefore on **18 projects**.

**Statistics.** Project-paired Wilcoxon on `mcc_avg`, Hodges–Lehmann with bootstrap interval, matched-pairs rank-biserial, Holm within the registered family. Both estimators recorded.

---

## 7.4 Results

### 7.4.1 Tuning, and what the acceptance bar caught

Forty-two configurations were evaluated on the held-out projects under a selection rule declared before the sweep: apply the ND gate **first**, then maximise gain on B-SZZ, then prefer the more conservative filter. `rate_update` was deliberately **not** tuned — it is the R1 arm, and optimising it would convert a registered prediction into a fit.

**Twenty-four configurations passed the gate, and every one of them uses the quantile rule.** Every fixed-threshold configuration failed, several catastrophically: on the reference arm, where every positive label is correct and there is nothing to remove, τ = 0.35 suppressed 57% of defect labels and cost **−0.0989** MCC.

> **The reason generalises well beyond this model.** A fixed confidence threshold suppresses however many positives the model happens to be unsure about, with no reference to how many false positives the source actually contains. It cannot distinguish *"this label is probably wrong"* from *"my model has not learned this pattern yet."* A quantile rule removes about *q* by construction, so its worst case is bounded. **An intervention on scarce labels must be bounded in size, not in confidence.**

The frozen configuration is quantile with *q* = 0.30, ε = 0.1, `min_pos` = 30, `rate_update` = `observed`. Extending the sweep to *q* = 0.40 and 0.50 lowered the B-SZZ gain to 0.0402 and 0.0288, confirming *q* = 0.30 as an interior optimum rather than a grid edge.

### 7.4.2 The registered verdict

Eighteen reporting projects.

| Test | HL | 95% CI | Projects | *p* | **Holm** |
|---|---|---|---|---|---|
| **ND** — non-degradation on reference labels | −0.0001 | [−0.0091, +0.0081] | 5/18 | 0.807 | **PASS** |
| H1 — filter beats baseline on B-SZZ | +0.0166 | [+0.0009, +0.0328] | 12/18 | 0.054 | 0.215 ✗ |
| H2a — on MA-SZZ | +0.0110 | [−0.0005, +0.0235] | 13/18 | 0.074 | 0.221 ✗ |
| H2b — on AG-SZZ | +0.0072 | [−0.0075, +0.0221] | 12/18 | 0.246 | 0.492 ✗ |
| H3 — benefit tracks false-positive count | ρ = 0.714 | — | 6 variants | 0.055 | ✗ |

**The gate passes; nothing else does.** Every confirmatory test points in the predicted direction and not one survives correction.

The honest reading is narrow. The filter is **adoptable** — it does not damage clean labels, which is the property that gates deployment — but it is **not demonstrated to work**. Four independent tests agreeing in direction is worth a sentence; it is not a result, and this thesis does not treat it as one. H1's interval barely excludes zero and its raw *p* of 0.054 would not have survived even without correction.

**The hold-out protocol paid for itself.** On the three tuning projects the filter gained **+0.045** on B-SZZ. On the 18 reporting projects it gains **+0.017** — an optimism factor of **2.7×**. Had the hyperparameters been selected on the reporting set, this chapter would have claimed an effect nearly three times its real size, and would have been wrong.

### 7.4.3 The mechanism probe was refuted, 0 for 6

Rescue was registered with an explicit prediction that it would be **at or below zero** on every SZZ source. It is **positive on all six**:

| Source | Rescue − baseline | 95% CI | Projects | *p* |
|---|---|---|---|---|
| L-SZZ | **+0.0166** | [+0.0057, +0.0289] | 13/18 | 0.006 |
| MA-SZZ | **+0.0142** | [+0.0013, +0.0266] | 12/18 | 0.027 |
| AG-SZZ | +0.0117 | [−0.0007, +0.0270] | 13/18 | 0.090 |
| B-SZZ | **+0.0116** | [+0.0033, +0.0262] | 13/18 | 0.024 |
| R-SZZ | +0.0068 | [−0.0033, +0.0202] | 12/18 | 0.246 |
| RA-SZZ | +0.0002 | [−0.0164, +0.0213] | 8/18 | 1.000 |

The registration stated that if rescue helped, the mechanism account would need revision. **It helps, and the revision is owed.**

**The candidate reconciliation, and why it is not yet a claim.** Chapter 6 restored the *reference-known* missing positives; rescue adds *model-confident* ones. These are different sets — rescue is closer to self-training on high-confidence commits than to label correction. So "restoring what SZZ missed recovers nothing" and "adding confidently-predicted defects helps" are not contradictory, **provided** the benefit comes from label *supply* rather than label *accuracy*.

That explanation was tested directly. The Spearman correlation between a condition's delivered positive supply and the filter-minus-rescue advantage is **ρ = +0.357, *p* = 0.385**. **The supply account is not supported**, and it is recorded here as an open question rather than presented as an explanation.

### 7.4.4 R1: a clean null in both directions

| Condition | observed − suppress | 95% CI | *p* |
|---|---|---|---|
| B-SZZ | −0.0016 | [−0.0075, +0.0045] | 0.61 |
| Reference | +0.0002 | [−0.0018, +0.0031] | 0.51 |

The registered prediction is not supported, and neither is its converse. λ *does* rise when positives are suppressed — the coupling is real and was measured at ρ = −1.000 — but at this filter rate it has no detectable effect on performance. The trace confirms the feedback loop exists: the two settings produce *different filter rates on identical inputs*. It simply does not matter at this magnitude.

### 7.4.5 An uncomfortable finding, reported rather than smoothed

The prior confidence-damping arm — the one the re-registration demoted — **outperforms the new primary on six of eight conditions**, including B-SZZ (0.0874 against the baseline's 0.0551).

Because damping was not the registered primary, every such contrast is exploratory. Corrected across the 21 exploratory contrasts, only damping-beats-baseline on B-SZZ survives global Holm: +0.0329, CI [+0.0194, +0.0456], 15/18, *p* = 0.0040. **The defensible statement is that damping leads numerically and is established on one label source.**

The re-registration was correctly motivated by Chapter 6 and correctly timed before any run, and it still bet on the wrong arm. The commit history records this either way, so the thesis states it.

---

## 7.5 Discussion — answering RQ4

**Can a learner recover performance lost to SZZ noise without reference labels?** Not demonstrably, on this corpus, with this intervention.

| | Recovers |
|---|---|
| Chapter 6 FP-repair, using the reference to remove exactly the wrong labels | **+0.040** |
| Chapter 7 filter, approximating it without the reference | +0.017 (not significant) |

**The gap between those numbers is the price of not knowing which labels are wrong**, and it is the most informative quantity in this chapter. Two things make it large.

**A confidence signal cannot separate the two cases that matter.** At its tuned setting the filter suppresses 30% of defect labels on B-SZZ — and still **15% on reference labels, where there is nothing to remove.** Low predicted probability means "this label disagrees with what I have learned", which is equally consistent with a wrong label and with a correct label describing a pattern not yet learned. Under an 8.5% positive rate with a model still learning, the second case is common.

**Defect labels are too scarce for the intervention to be cheap.** Under realistic latency a project delivers a mean of **75 defect labels across an entire stream**, with ORB's λ climbing to 62 to compensate. Every suppressed label is drawn from that budget. Chapter 6's repair could afford to remove 6,565 labels because it removed only wrong ones; a heuristic filter pays for its precision in correct labels discarded.

**When it helps and when it does not.** The direction is consistent — positive on all four registered tests and ordered roughly by false-positive count — so the mechanism identified in Chapter 6 is not contradicted. The effect is simply smaller than the design can resolve at *n* = 18. On the most false-positive-heavy source the point estimate is +0.017 against a baseline near 0.055, which would be practically meaningful if it were established; on the cleanest sources it is indistinguishable from zero, exactly as the volume account predicts.

**What the negative result is worth.** More, in this case, than a positive one. A working filter would have shown that this particular heuristic recovers some of this particular loss. The negative shows something more general: **the information required to build the defence is not available to a learner at training time.** Knowing *which kind* of error hurts — Chapter 6's contribution — does not confer the ability to identify *which instances* are that error. The repair experiment's +0.040 is an upper bound requiring knowledge no deployed system has.

The practical implication is the thesis's, not a hedge: **on this evidence, improving the labels is worth more than improving the learner.**

### 7.5.1 What this chapter licenses, and what it does not

**Licensed.** That train-time false-positive filtering is adoptable but not demonstrated effective on this corpus; that a fixed confidence threshold is actively harmful on clean labels and the failure mode is understood; that the rescue mechanism helps, contradicting a prediction derived from Chapter 6; that held-out tuning was necessary, with a measured optimism factor of 2.7×.

**Not licensed.** That confidence-based filtering cannot work in principle — one design was tested at one operating point. That damping is superior to filtering; it leads numerically but is established on one source and was not pre-registered. Any explanation of why rescue helps: the supply account was tested and failed, and no replacement has been tested.

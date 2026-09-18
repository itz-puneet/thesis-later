# Chapter 3 — Research Design

This chapter states the design of the study as a whole: how the four phases fit together, what data they run on, how the SZZ variants were produced, what is measured and with what statistical protocol, and which validity threats were anticipated in advance rather than discovered afterwards.

The design has one organising commitment. **Every claim is a paired comparison at the project level, and every reported number is regenerable from committed inputs by a named script.** The remainder of this chapter is largely an elaboration of what that commitment required.

---

## 3.1 The four-phase pipeline

Each phase consumes the previous phase's output, and the dependencies are data dependencies rather than narrative ones.

```
                 JIT-Defects4J reference labels
                              │
        ┌─────────────────────┴──────────────────────┐
        │                                            │
   [PHASE 1] ── six SZZ variants ──────────┐         │
   label quality                           │         │
        │                                  │         │
        ├── ρ₀, ρ₁ per variant ────────────┼─────────┼──► [PHASE 3]
        │   (phase1_bias.json)             │         │    noise injection
        │                                  ▼         ▼    + repair
        └── per-commit labels ────────► [PHASE 2] ───────► mechanism
                                        downstream              │
                                        impact                  │
                                                                ▼
                                                          [PHASE 4]
                                                          noise-aware
                                                          method
```

- **Phase 1** measures how far each SZZ variant departs from the reference, and in which direction. Output: per-commit labels, and the flip-rate pair (ρ₀, ρ₁) per variant.
- **Phase 2** trains models on each label source and evaluates them under four regimes of increasing realism, against two scoring conventions. Output: the inflation ladder and the label-source penalty.
- **Phase 3** uses Phase 1's flip rates to inject calibrated noise into clean labels, and separately repairs real SZZ labels one error type at a time. Output: which error type costs the learner, and the mechanism.
- **Phase 4** builds and pre-registers a method targeting whatever Phase 3 identifies.

**The dependency from Phase 3 to Phase 4 is genuine and was exercised.** Phase 4's original design targeted false negatives. Phase 3 showed that error costs nothing, and Phase 4's registration was rewritten before its first run. Had the phases been planned in parallel rather than in sequence, that correction could not have happened.

---

## 3.2 Data

### 3.2.1 Corpus

| | |
|---|---|
| Projects | 21 Apache Java repositories |
| Commits | 27,319 |
| Reference defect-introducing | 2,332 (**8.54%**) |
| Range per project | 544–4,026 commits; 19–335 defects; 1.8%–19.3% defect rate |
| Features | The 14 Kamei change-level metrics |

Projects were not selected by us. The corpus is JIT-Defects4J as published, adopted whole so that the selection cannot be tuned to the results. Its consequences for external validity are stated in §3.5 and Chapter 8.

### 3.2.2 The reference labels

`label_oracle` derives from JIT-Defects4J (Ni et al., ESEC/FSE 2022), an extension of LLTC4J (Herbold et al.). Its provenance was traced through the repository and confirmed against the source paper rather than assumed:

| Step | Evidence |
|---|---|
| `label_oracle` | = `is_buggy_commit` in the published feature pickles |
| The pickles | from the JIT-Fine replication package on Zenodo |
| Corpus check | the paper's own table reports 2,332 / 27,319 = 8.54% and matches this corpus **project by project** |

**Construction, stated precisely because every downstream claim depends on it.** Lines within bug-fixing commits were annotated manually, retained only where at least three participants agreed; `git blame` was then applied to those verified lines to identify the introducing commit; everything else is clean by residual.

The reference is therefore **`git blame` seeded with human-verified fix lines**, not manually verified ground truth for defect-introducing commits. The phrase "developer-verified ground truth" is inaccurate and is not used in this thesis. Chapter 4 §4.1.1 develops the three consequences; the most important is that all measured noise is a **lower bound**, because blame error is present on both sides of every comparison and cancels.

### 3.2.3 Features and preprocessing

The 14 Kamei metrics are taken as published rather than recomputed, so that feature extraction cannot differ between the reference and the variants. Commits are deduplicated on (project, commit hash) and sorted by author timestamp, which defines the stream order for every temporal regime.

The pipeline was restructured so that two bulky inputs — a 101 MB archive and 830 MB of cloned repositories — are replaced by two small committed derived files (4.2 MB and 0.37 MB). The entire study therefore runs on a continuous-integration runner from committed inputs, which is what makes the reproducibility claim in §3.6 checkable rather than aspirational.

### 3.2.4 Verification latency

Reconstructing when a defect label would actually have become known requires the author date of each bug-fixing commit. These were extracted once from the cloned repositories and committed as a small table. For each variant, a commit's arrival time is the date of the fix that blamed it; the union across variants supplies the reference condition's arrival times.

**This is the study's central construct-validity threat and is declared here rather than in a footnote.** The published reference labels carry no native fix-to-inducing linkage, so the reference condition is blame-derived in *construction* and **SZZ-derived in *timing***. A coverage sensitivity analysis (67.8% → 100% linkage) bounds part of the exposure; it does not address the timing itself. Every streaming result in Chapters 5–7 inherits this threat.

---

## 3.3 SZZ variant implementations

Six variants were produced with **PySZZ v2** (Rosa et al., JSS 2023), the reference implementation released with the developer-informed-oracle study. Using the authors' own implementation rather than a reimplementation removes one source of unexplained variation, at the cost of inheriting whatever its defaults encode — a trade recorded here as a decision rather than left implicit.

Each variant was run on the same fix-commit set, and its output aligned to the reference over an **identical 27,319-commit denominator**. Partial denominators are a known source of incomparability: a variant emitting fewer candidates can appear more precise merely by being scored on a smaller population.

### 3.3.1 The label-consistency gate

Mid-project it emerged that the Phase 2 dataset cache had gone stale relative to a Phase 1 label regeneration. Models had been trained on labels one commit older than the noise rates being reported, affecting 1.0–6.5% of commits per variant. The root cause was an unguarded cache keyed on modification time.

The remediation was three-part: a **content-hash staleness guard**, a **provenance sidecar** recording the SHA-256 of every label file used to build the dataset, and an automated **consistency gate** that recomputes the confusion matrix from the training data and asserts it matches the reported noise rates for all six variants. The gate runs in CI **before any compute is spent**, so a mismatch costs two minutes rather than several hours. It was verified in both directions: it fails on the stale data and passes on the corrected data.

This is recorded in the thesis rather than quietly fixed. A study about label-provenance fragility encountered exactly that fragility in its own pipeline, and now ships an executable assertion against its recurrence.

---

## 3.4 Metrics and statistical protocol

### 3.4.1 Metric selection

**MCC is primary.** At an 8.54% positive rate, accuracy is uninformative: a model predicting "clean" for every commit scores 91.5% accuracy and 0.0 MCC. MCC uses all four confusion-matrix cells and is near zero for any uninformed strategy, which makes it the appropriate primary under this imbalance. **G-mean** is reported alongside as the geometric mean of per-class recalls, since it is sensitive to abandoning the minority class in a way MCC partially shares but expresses differently. **Cohen's κ** is used for agreement between labelling procedures, where the question is concordance rather than prediction.

### 3.4.2 The prequential estimator

Under streaming evaluation the metric is a trajectory, not a scalar, and summarising it requires a choice. Two summaries are computed throughout:

- **Terminal fading** — a confusion matrix with exponential forgetting (fading 0.99, effective window ≈ 100 commits), read at end of stream.
- **Time-averaged** — the mean of the MCC trajectory over the stream.

**Neither is canonical, and this thesis does not claim otherwise.** MCC is not a decomposable loss, so the prequential-with-fading construction does not extend to it directly; of the two, the terminal value is the closer analogue. The time-averaged value is treated as **primary on a measured basis** — roughly half the project-level variance (0.051 against 0.092) — not by appeal to a standard. An earlier version of this work described it as "the standard estimator", which was wrong and is corrected.

Both are reported for every streaming result. They agree on every comparison in this thesis except one, which is named where it occurs.

### 3.4.3 The unit of analysis

**Every test is paired at the project level, *n* = 21 (or 18 in Phase 4, after held-out exclusion), with seeds averaged before pairing.** Seeds control model initialisation and fold randomness; they are not independent observations. Pooling over the full record count would be pseudo-replication, and is the first objection a methodologist would raise.

### 3.4.4 Effect sizes

Each comparison reports:

- **Wilcoxon signed-rank *p*** — paired, distribution-free.
- **Matched-pairs rank-biserial correlation** — derived from the same signed ranks as the *p*-value, so the effect size and the test agree by construction. It reads as *consistency*: +1.000 means every project moved in the same direction.
- **Hodges–Lehmann estimator** — the median of pairwise Walsh averages, the location estimate that accompanies the signed-rank test.
- **Percentile bootstrap confidence interval**, computed **for the Hodges–Lehmann statistic itself**, with the statistic recomputed inside every resample.

Two of these are corrections to an earlier protocol and are recorded as such. Cliff's δ was initially computed *unpaired*, all-versus-all with denominator *n*·*m*, discarding the pairing the design exists to preserve; on the headline comparison it reported 0.74 where the paired statistic reports +1.000. Separately, the bootstrap originally resampled the median while the Hodges–Lehmann estimate was reported beside it — an interval for a different quantity than the point estimate.

### 3.4.5 Multiplicity

Seventy-four tests are run in Phase 2 alone. Multiplicity is corrected **twice**:

- **Holm within test family** — families grouped by the comparison being made.
- **Holm globally across all tests** — no family argument required.

The global column exists because the families were defined *during* analysis, not declared in advance. A sceptic can reasonably argue the grouping was chosen to help the results; **a claim surviving global Holm needs no defence of how families were drawn.** Every headline claim in this thesis survives the global column, and where a claim survives only within-family correction, that is stated.

### 3.4.6 Pre-registration

**Phases 1–3 are exploratory.** Their hypotheses were formed during analysis and every result is labelled accordingly; the global multiplicity correction is the sensitivity analysis that makes them defensible without a pre-registration.

**Phase 4 alone is pre-registered**, with hypotheses, primary model, acceptance bar and correction committed to version control before its first run. Its registration was revised once, after Phase 3 refuted the hypothesis it was built on and while Phase 4 still had zero results — the only point at which revision is legitimate. Chapter 7 §7.1 gives the full account.

---

## 3.5 Threats to validity, framed in advance

Stating the framework before the results appear is deliberate: it prevents the threat list from being assembled to fit whatever was found.

**Construct validity.** The reference is `git blame` seeded with verified fix lines, not ground truth, so comparisons isolate tangling rather than total labelling error and measured noise is a lower bound. Arrival times for the reference condition are SZZ-derived (§3.2.4) — the single most serious threat in the study.

**Internal validity.** Temporal leakage is the threat the design exists to expose, and is therefore a *manipulated variable* rather than a defect. Cache staleness is addressed by the gate (§3.3.1). Repair and injection experiments are oracle-assisted by construction and are labelled as upper bounds, not methods.

**External validity.** One benchmark family: 21 Apache Java repositories of a single dataset lineage. The corpus is SZZ-shaped, since changes adding no new lines were excluded by the dataset authors, so defects introduced purely by deletion cannot appear. Projects are weighted equally despite an eighteen-fold range in defect count.

**Conclusion validity.** With 21 paired projects, effects below roughly 0.04 MCC are not resolvable — a limit that becomes load-bearing for the latency decomposition, which is reported as unresolved rather than as null. Multiplicity is corrected twice. The number of exploratory comparisons is large, which is precisely why the global correction is reported.

**One scope limit declared before Phase 3 ran.** Because the reference labels are themselves blame output, every reference positive is blame-reachable by construction. **No false negative measured against this reference can be attributed to blame's structural inability to trace a defect.** Phase 3 can therefore study false-negative noise arising from over-filtering and seed-line divergence — the two mechanisms Chapter 4 shows are actually operating — but can make no claim about blame-unreachability. Declaring this in advance prevents an unavailable explanation from being offered afterwards.

---

## 3.6 Reproducibility

Every number in Chapters 4–7 is regenerable from committed inputs by a named script, and the chapter-to-artefact mapping is explicit:

| Chapter | Script | Principal outputs |
|---|---|---|
| 4 | `experiments/evaluate_confusion_matrix.py` | quality table, κ matrix, `phase1_bias.json` |
| 5 | `experiments/run_phase2_impact.py` | regime × label-source matrix, 74 tests |
| 6 | `experiments/run_phase3_noise.py`, `run_phase3_addendum.py` | dose curves, repair statistics, λ traces |
| 7 | `experiments/run_phase4_tuning.py`, `run_phase4_na_orb.py` | frozen configuration, registered tests |
| Appendix | `experiments/run_robustness_checks.py` | project table, floor sensitivity, mechanism test |

Runtime dependencies are pinned to the exact versions every result was computed with, so a runner reproduces the local environment rather than approximating it. The label-consistency gate runs before every experiment in CI.

The next four chapters report what these scripts produce.

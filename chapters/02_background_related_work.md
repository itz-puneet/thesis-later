# Chapter 2 — Background and Related Work

> **Citation status.** §2.9 classifies every reference in this chapter as **[V]** — bibliographic details and the specific claim attributed to it were verified against the source or its publisher record during preparation — or **[C]** — the work is correctly identified but the attributed detail has **not** been re-verified and must be checked against the original before submission. No claim marked [C] should be quoted without that check.

---

## 2.1 Just-in-time software defect prediction

### 2.1.1 Task definition

JIT-SDP predicts, for each incoming commit, whether it introduces a defect. Formally, given a commit *c* with feature vector *x* ∈ ℝ^d available at commit time, predict *y* ∈ {0, 1}.

The task's appeal is timing. A prediction available at commit time reaches the developer who wrote the change while the change is still current, which is the difference between a useful signal and a retrospective one.

### 2.1.2 The Kamei feature set

Kamei et al. [V] established the modern formulation, together with the change-level metrics that remain standard. The 14 features group into five families:

| Family | Features | Intuition |
|---|---|---|
| **Diffusion** | NS, ND, NF, Entropy | A change spread across many subsystems, directories and files is harder to reason about |
| **Size** | LA, LD, LT | Large changes carry more opportunity for error |
| **Purpose** | FIX | Changes that fix defects are themselves defect-prone |
| **History** | NDEV, AGE, NUC | Code touched by many developers, recently, and often |
| **Experience** | EXP, REXP, SEXP | Author familiarity with the code being changed |

Kamei et al. report approximately **68% accuracy and 64% recall** on defect-inducing changes [V]. These features are used throughout this thesis, taken as published rather than recomputed so that feature extraction cannot differ between the reference labels and the SZZ variants.

### 2.1.3 Class imbalance and concept drift

Defect-introducing commits are a small minority — **8.54%** on the corpus studied here. Two consequences run through this thesis.

**Accuracy is uninformative.** A model predicting "clean" for every commit scores 91.5% accuracy on this corpus. §2.6 covers metric selection.

**Oversampling is standard, and it is not free.** Rebalancing methods increase the influence of minority examples, which is exactly what is wanted when those examples are correct. Chapter 6 shows what happens when they are not.

Projects also change over time — team composition, architecture, process — so the relationship between features and defect-proneness is not stationary. Concept drift in this setting is addressed by Cabral and Minku [V] and subsequent work [C].

---

## 2.2 SZZ and its variants

### 2.2.1 The original algorithm

Śliwerski, Zimmermann and Zeller [C] introduced the procedure now universally called SZZ. Given a commit identified as fixing a defect, it:

1. Extracts the lines modified by the fix;
2. Applies `git blame` (or equivalent) to find, for each line, the most recent prior commit to have modified it;
3. Labels those prior commits defect-introducing.

The algorithm is an inference, and it rests on two premises: that the lines a fix modifies are the lines that were defective, and that the last commit to touch a line is the commit that made it wrong.

### 2.2.2 The failure taxonomy

**Tangled commits** violate the first premise. Bug-fixing commits routinely contain reformatting, renaming, comment updates and test changes alongside the fix. Herbold et al. [V], using four annotators per line, found that **between 17% and 32% of all changes in bug-fixing commits address the underlying problem**, rising to **66–87%** when only production-code files are considered; about **11%** of lines produced active annotator disagreement. Every tangled line is blamed, and every commit that last touched one is mislabelled.

**Blame attribution error** violates the second premise. `git blame` identifies the last commit to *touch* a line, which need not be the commit that made it *wrong*. A later cosmetic edit takes the blame from the change that introduced the fault. This thesis refers to this as the **syntactic line-blame fallacy**, and §2.2.4 explains why it is not measurable in this study's design.

**Structural invisibility.** A defect introduced by omission — code that was never written — has no line for blame to find. This mechanism is real in general but, as Chapter 4 explains, is *not available* as an explanation within this thesis's corpus.

### 2.2.3 The variants

Each variant adds filtering or selection intended to remove B-SZZ's over-collection:

| Variant | Mechanism | Attribution |
|---|---|---|
| **B-SZZ** | The original | Śliwerski et al. [C] |
| **AG-SZZ** | Annotation-graph filtering; excludes cosmetic and format-only changes | Kim et al. [C] |
| **MA-SZZ** | Additionally excludes meta-changes (branch changes, property changes) | da Costa et al. [C] |
| **R-SZZ** | Retains only the most recent candidate | Davies et al. [C] |
| **L-SZZ** | Retains only the largest candidate | Davies et al. [C] |
| **RA-SZZ** | Refactoring-aware; removes refactoring-attributable candidates | Neto et al. [C] |

The progression assumes that B-SZZ's dominant error is over-collection and that filtering it out improves the labels. **Chapter 4 tests that assumption directly and finds that for the most aggressive variants, more than half of what the filters remove is correct.**

### 2.2.4 Developer-informed oracles

Evaluating SZZ requires a reference that does not itself use SZZ. Rosa et al. [V] constructed one by mining commit messages in which developers *explicitly name* the commit that introduced the defect being fixed — yielding **1,930 fix-to-inducing links across eight programming languages**, extended in the journal version to an evaluation of nine variants over **2,304 instances**. Against that oracle, **R-SZZ performed best (F-measure ≈ 61%, precision ≈ 66%)** while B-SZZ achieved higher recall (≈ 0.69) at markedly lower precision (≈ 0.39) [V].

**Two points about this dataset matter for the present work.**

First, it **cannot train a JIT-SDP model.** It contains fix-to-inducing links and no clean commits, so there is no negative class and no complete labelling of project history.

Second, **its precision figures are not comparable to this thesis's without reconciling the denominator.** Rosa et al. score *conditionally* on bug-fixing commits already known to have an inducing commit. This thesis scores over an entire project history of 27,319 commits, the overwhelming majority of which are clean. A variant that is right two times in three when asked "which earlier commit introduced this known defect?" can still be wrong four times in five when asked "is this commit, drawn from all of history, defect-introducing?" **The difference is large enough to read as a contradiction, and Chapter 8 addresses it explicitly.**

### 2.2.5 JIT-Defects4J and the reference labels

Ni et al. [V] published **JIT-Defects4J**, an extension of LLTC4J [V], comprising **27,319 commits from 21 Java projects, of which 2,332 (8.54%) are labelled defect-introducing**. Its construction is two-stage: lines within bug-fixing commits were annotated manually, retained where at least three participants agreed; `git blame` was then applied to those verified lines.

**The labels are therefore `git blame` seeded with human-verified fix lines — not manually verified ground truth for defect-introducing commits.** This thesis uses them as its reference precisely because the distinction is tractable: they control for tangling, the dominant false-positive mechanism, while sharing SZZ's blame step. Comparisons against them isolate the cost of tangled commits, and blame error, being common to both sides, cancels. Chapter 3 §3.2.2 develops the consequences.

### 2.2.6 Other JIT-SDP datasets

| Dataset | Scale | Labels | Relevance here |
|---|---|---|---|
| **ApacheJIT** [V] | 106,674 commits (28,239 bug-inducing), 14 Apache projects | SZZ-derived | Larger, but cannot serve as an oracle for a study of SZZ noise |
| **Defectors** [V] | ~213K files, 24 Python projects, 18 domains | SZZ-derived | File-level; same objection |
| **ReDef** [V] | 3,164 defective / 10,268 clean functions, 22 C/C++ projects | **Revert-anchored**, LLM-triaged, ~92% audited precision | Non-blame labels, but function-level, C/C++, no Kamei features, no fix dates |

**Scale is not the binding constraint for this thesis; label provenance is.** A study measuring what SZZ noise costs cannot use SZZ labels as its reference, which excludes the two largest datasets available.

---

## 2.3 Evaluation methodology in defect prediction

### 2.3.1 Temporal leakage

Random *k*-fold cross-validation on temporally ordered data allows a model to train on future commits and be tested on past ones. Time-aware evaluation has been advocated repeatedly [C], yet random *k*-fold remains widespread in the JIT-SDP literature.

**Chapter 5 measures the consequence rather than restating the argument.** The inflation is +0.137 MCC on a high-capacity model and it scales with model capacity, which means comparisons *between* model families under this protocol are confounded in a direction that favours larger models.

### 2.3.2 Prequential evaluation

For streams, the standard protocol is *test-then-train*: each example is first predicted, then used for learning. Summarising a metric over a stream requires a forgetting mechanism, conventionally a fading factor applied to the error estimate [C].

**An important caveat for this thesis.** The prequential-with-fading construction is defined for decomposable losses that can be accumulated example by example. **MCC is not decomposable**, so the construction does not extend to it directly. This thesis therefore reports two ad-hoc summaries of the MCC trajectory — a terminal fading value and a trajectory mean — treats the trajectory mean as primary **on measured variance rather than by appeal to a standard**, and states explicitly that neither is canonical. An earlier version of this work described one of them as "the standard estimator"; that was incorrect and is corrected in Chapter 3 §3.4.2.

### 2.3.3 Verification latency

Cabral and Minku [V] identified verification latency as a first-class concern in JIT-SDP: labels arrive with a delay, and the delay differs systematically between classes, since a clean commit is only ever *presumed* clean while a defective one must be discovered. Their framing of latency and of the resulting **class imbalance evolution** is the setting this thesis adopts.

On the corpus studied here the median latency is **113 days**, with **53% of defect labels arriving after a 90-day window**. Under a fixed window, a defect label that arrives late is delivered first as a *wrong clean label* and corrected later — so latency is not merely delay but active misinformation, and the misinformation concerns exactly the minority class.

---

## 2.4 Online learning for JIT-SDP

**Online Bagging** [C] adapts bagging to streams by presenting each arriving example to each ensemble member *k* ~ Poisson(λ) times.

**Oversampling Online Bagging (OOB)** [C] handles imbalance by setting λ from the running observed class ratio, so minority examples are presented more often as the imbalance grows.

**Oversampling Rate Boosting (ORB)** [V] extends OOB by monitoring the model's own recent predictions: when predictions are considerably biased toward one class, the resampling rate of the opposite class is boosted. Cabral and Minku also adopt a safety mechanism intended to avoid training on potentially noisy or outlier minority-class examples [V].

> **This machinery is the subject of Chapter 6's central finding.** ORB's λ is a function of the *observed rate* of defect labels — that is, of label **quantity**. It has no access to label **quality**. Chapter 6 measures the coupling directly (Spearman ρ = −1.000 between delivered defect-label supply and applied λ) and shows that the mechanism correcting class imbalance is the mechanism that amplifies false positives, hardest exactly when defect labels are scarcest.

Subsequent work addresses concept drift in online JIT-SDP [C] and label noise arising from latency [C]. **The distinction from the present work is the origin of the noise.** Latency-induced noise is a timing artefact: the label is correct but late. SZZ-induced noise is a *labelling* artefact: the label is wrong and will never be corrected. This thesis addresses the second, under conditions that include the first.

---

## 2.5 The weak-baseline problem

Deep learning approaches to JIT-SDP — DeepJIT and CC2Vec [C] — reported substantial gains over feature-based models. Two subsequent results complicate that picture.

Zeng et al. [V], evaluating on over **310,370 changes**, found that CC2Vec could not consistently outperform DeepJIT and that neither consistently outperformed traditional feature-based JIT prediction. They then constructed **LApredict** — logistic regression on the added-lines feature alone — which outperformed both deep models while being roughly **81,000–120,000× faster** to train and test [V].

Pornprasit and Tantithamthavorn [V] reported **JITLine**, a simpler feature-based approach that was **26–38% better in F-measure, 17–51% more cost-effective, and 70–100× faster** than CC2Vec and DeepJIT.

**Both models are used in this thesis, and the reason is methodological rather than deferential.** LApredict has minimal capacity; JITLine has a great deal. Chapter 5 shows that the inflation attributable to evaluation protocol is **+0.137 MCC for JITLine and +0.034 for LApredict**, and that the self-scoring gap is significant for all six SZZ variants under JITLine but only one under LApredict. **Capacity is not incidental to the measurement problem — it is the variable that determines its size**, which offers an alternative reading of why simple baselines have proven so hard to beat.

---

## 2.6 Metric selection

Under an 8.54% positive rate, accuracy is uninformative. This thesis uses:

**Matthews Correlation Coefficient (MCC)** [C] as primary. It incorporates all four confusion-matrix cells and is near zero for any uninformed strategy. A majority-class predictor scores 0.0 MCC and 91.5% accuracy on this corpus.

**G-mean**, the geometric mean of per-class recalls, which collapses toward zero if either class is abandoned.

**Cohen's κ** [C] for agreement between labelling procedures, where the question is concordance rather than prediction quality.

Effort-aware metrics — recall at a fixed inspection budget — arguably match the practitioner's objective more closely and are identified as future work in Chapter 9, not reported here.

---

## 2.7 Learning with noisy labels

**Loss correction.** Natarajan et al. [C] showed that under class-conditional noise with known rates ρ₀ and ρ₁, an unbiased estimator of the clean risk can be constructed by reweighting. The correction becomes numerically unstable as ρ₀ + ρ₁ → 1. **This matters directly here**: Chapter 4 measures ρ₀ + ρ₁ approaching 0.8 for the conservative variants, which is why the loss-correction arm evaluated in this thesis is capped.

**Sample selection.** Co-teaching [C] trains two networks that exchange small-loss examples, on the premise that mislabelled examples exhibit higher loss early in training. It assumes a batch setting with multiple epochs.

**Confident Learning** [C] estimates the joint distribution of noisy and true labels using model confidences and prunes suspected errors. It is a batch method requiring cross-validated out-of-sample predictions over a fixed dataset.

**Why these do not transfer directly.** Each assumes a fixed dataset, repeated passes, and labels that are wrong but *stable*. A JIT-SDP stream offers none of these: a single pass, labels arriving late, and labels that are **wrong and then corrected**. Chapter 7 adapts the confidence-based idea to the streaming setting, and its central negative result is informative about the whole family: a confidence signal cannot distinguish *"this label is wrong"* from *"my model has not learned this pattern yet"*, and the second case is common under severe imbalance with a still-learning model.

---

## 2.8 Positioning

| Work | Imbalance | Drift | Latency | SZZ noise **measured** | Online |
|---|---|---|---|---|---|
| Kamei et al. [V] | ○ | ○ | ○ | ○ | ○ |
| Cabral & Minku (ORB) [V] | ● | ● | ● | ○ | ● |
| Rosa et al. (oracle) [V] | ○ | ○ | ○ | ● *(labels only)* | ○ |
| Herbold et al. (tangling) [V] | ○ | ○ | ○ | ● *(labels only)* | ○ |
| Zeng et al. / Pornprasit et al. [V] | ● | ○ | ○ | ○ | ○ |
| Natarajan / Co-teaching / CL [C] | ● | ○ | ○ | ◐ *(assumed, not measured)* | ○ |
| **This thesis** | ● | ● | ● | ● **downstream cost** | ● |

*(● addressed · ◐ partially · ○ not addressed)*

**The distinguishing cell is the fourth.** SZZ evaluation work measures the noise and stops at the labels. Online JIT-SDP work operates under latency but treats label noise as a nuisance to dampen rather than a quantity to measure. Noisy-label learning assumes a noise model rather than estimating one, and assumes a batch setting. This thesis measures **what SZZ-origin noise costs downstream, under latency-aware online evaluation**, and then tests whether that cost can be recovered.

The methodological device that makes this possible is small and worth naming: **an independently constructed reference label set, held out from training and used only for scoring.** Without it, a model trained on SZZ can only be evaluated against SZZ, and the largest effect in this thesis — the +0.230 MCC self-scoring gap — is invisible by construction.

---

## 2.9 Citation verification status

**[V] — verified during preparation.** Bibliographic details and the specific attributed claim were checked against the source or publisher record.

| Work | Verified detail |
|---|---|
| Kamei et al., *IEEE TSE* 39(6):757–773, 2013 | Task formulation; ~68% accuracy, 64% recall |
| Cabral & Minku, *ICSE* 2019 | Class imbalance evolution, verification latency, ORB, safety mechanism |
| Herbold et al., *EMSE*, 2022 | 17–32% of changes / 66–87% production code; four annotators; ~11% disagreement |
| Ni et al., *ESEC/FSE* 2022 | JIT-Defects4J; 27,319 commits / 2,332 defective / 21 projects; two-stage construction |
| Rosa et al., *ICSE* 2021; *JSS* 202:111729, 2023 | 1,930 links, 8 languages, 2,304 instances; R-SZZ best (F ≈ 61%, P ≈ 66%); B-SZZ recall ≈ 0.69, precision ≈ 0.39; PySZZ |
| Zeng et al., *ISSTA* 2021 | 310,370 changes; LApredict; 81k–120k× speedup |
| Pornprasit & Tantithamthavorn, *MSR* 2021, pp. 369–379 | JITLine; 26–38% F-measure, 17–51% cost-effectiveness, 70–100× faster |
| Keshavarz & Nagappan, *MSR* 2022 | ApacheJIT; 106,674 commits, 28,239 bug-inducing, 14 projects |
| Mahbub, Shuvo & Rahman, *MSR* 2023 | Defectors; ~213K files, 24 Python projects, 18 domains |
| ReDef (preprint, 2025) | 3,164 / 10,268 function-level changes, 22 C/C++ projects, revert-anchored, ~92% precision |

**[C] — correctly identified, detail not re-verified. Check each against the original before submission:**

Śliwerski, Zimmermann & Zeller (original SZZ) · Kim et al. (AG-SZZ) · da Costa et al. (MA-SZZ) · Davies et al. (R-SZZ, L-SZZ) · Neto et al. (RA-SZZ) · time-aware evaluation advocacy (Falessi et al.; Tan et al.) · Gama et al. (prequential evaluation with fading factors) · Oza & Russell (Online Bagging) · Wang, Minku & Yao (OOB) · Cabral & Minku (2023 drift analysis) · Song et al. (2022, latency noise) · Hoang et al. (DeepJIT, CC2Vec) · Matthews (MCC) · Cohen (κ) · Natarajan et al. (loss correction) · Han et al. (Co-teaching) · Northcutt et al. (Confident Learning) · Zhao et al., Zain et al. (JIT-SDP surveys) · Destefanis et al. (methodological audit).

> **One correction to the project's own planning documents.** An earlier outline attributed to Herbold et al. a finding that "~50%" of SZZ labels are wrong. The verified figures are **17–32% of all changes in bug-fixing commits** addressing the underlying problem, rising to **66–87%** for production-code files only — a different quantity, measured at line rather than commit level. The "~50%" figure does not appear in the source and must not be cited.

# Chapter 2 — Background and Related Work

> **Citation status.** Every reference in this chapter was checked against its publisher record or the source itself during preparation; §2.9 records the outcome. **One cited work could not be located and has been removed** — see §2.9. Page-level details (exact page numbers, section numbers) should still be confirmed against the PDFs when the bibliography is typeset.

---

## 2.1 Just-in-time software defect prediction

### 2.1.1 Task definition

JIT-SDP predicts, for each incoming commit, whether it introduces a defect. Formally, given a commit *c* with feature vector *x* ∈ ℝ^d available at commit time, predict *y* ∈ {0, 1}.

The task's appeal is timing. A prediction available at commit time reaches the developer who wrote the change while the change is still current, which is the difference between a useful signal and a retrospective one.

### 2.1.2 The Kamei feature set

Kamei et al. established the modern formulation, together with the change-level metrics that remain standard. The 14 features group into five families:

| Family | Features | Intuition |
|---|---|---|
| **Diffusion** | NS, ND, NF, Entropy | A change spread across many subsystems, directories and files is harder to reason about |
| **Size** | LA, LD, LT | Large changes carry more opportunity for error |
| **Purpose** | FIX | Changes that fix defects are themselves defect-prone |
| **History** | NDEV, AGE, NUC | Code touched by many developers, recently, and often |
| **Experience** | EXP, REXP, SEXP | Author familiarity with the code being changed |

Kamei et al. report approximately **68% accuracy and 64% recall** on defect-inducing changes. These features are used throughout this thesis, taken as published rather than recomputed so that feature extraction cannot differ between the reference labels and the SZZ variants.

### 2.1.3 Class imbalance and concept drift

Defect-introducing commits are a small minority — **8.54%** on the corpus studied here. Two consequences run through this thesis.

**Accuracy is uninformative.** A model predicting "clean" for every commit scores 91.5% accuracy on this corpus. §2.6 covers metric selection.

**Oversampling is standard, and it is not free.** Rebalancing methods increase the influence of minority examples, which is exactly what is wanted when those examples are correct. Chapter 6 shows what happens when they are not.

Projects also change over time — team composition, architecture, process — so the relationship between features and defect-proneness is not stationary. Concept drift in this setting is addressed by Cabral and Minku and by subsequent work; §2.4 returns to it.

---

## 2.2 SZZ and its variants

### 2.2.1 The original algorithm

Śliwerski, Zimmermann and Zeller, in *When Do Changes Induce Fixes?* (MSR 2005), introduced the procedure now universally called SZZ after their initials. Given a commit identified as fixing a defect, it:

1. Extracts the lines modified by the fix;
2. Applies `git blame` (or equivalent) to find, for each line, the most recent prior commit to have modified it;
3. Labels those prior commits defect-introducing.

The algorithm is an inference, and it rests on two premises: that the lines a fix modifies are the lines that were defective, and that the last commit to touch a line is the commit that made it wrong.

### 2.2.2 The failure taxonomy

**Tangled commits** violate the first premise. Bug-fixing commits routinely contain reformatting, renaming, comment updates and test changes alongside the fix. Herbold et al., using four annotators per line, found that **between 17% and 32% of all changes in bug-fixing commits address the underlying problem**, rising to **66–87%** when only production-code files are considered; about **11%** of lines produced active annotator disagreement. Every tangled line is blamed, and every commit that last touched one is mislabelled.

**Blame attribution error** violates the second premise. `git blame` identifies the last commit to *touch* a line, which need not be the commit that made it *wrong*. A later cosmetic edit takes the blame from the change that introduced the fault. This thesis refers to this as the **syntactic line-blame fallacy**, and §2.2.4 explains why it is not measurable in this study's design.

**Structural invisibility.** A defect introduced by omission — code that was never written — has no line for blame to find. This mechanism is real in general but, as Chapter 4 explains, is *not available* as an explanation within this thesis's corpus.

### 2.2.3 The variants

Each variant adds filtering or selection intended to remove B-SZZ's over-collection:

| Variant | Mechanism | Attribution |
|---|---|---|
| **B-SZZ** | The original | Śliwerski et al., MSR 2005 |
| **AG-SZZ** | Annotation graphs for precise line tracing; filters cosmetic changes such as blank lines and comments | Kim et al., 2006 |
| **MA-SZZ** | Additionally excludes meta-changes — branch merges, property changes — that do not alter program behaviour | da Costa et al., 2017 |
| **R-SZZ** | Retains only the most recent candidate commit | Davies et al., 2014 |
| **L-SZZ** | Retains only the candidate with the most changed lines | Davies et al., 2014 |
| **RA-SZZ** | Refactoring-aware; detects and filters refactorings via RefDiff and RefactoringMiner (Java only) | Neto et al., 2018 |

The progression assumes that B-SZZ's dominant error is over-collection and that filtering it out improves the labels. **Chapter 4 tests that assumption directly and finds that for the most aggressive variants, more than half of what the filters remove is correct.**

### 2.2.4 Developer-informed oracles

Evaluating SZZ requires a reference that does not itself use SZZ. Rosa et al. constructed one by mining commit messages in which developers *explicitly name* the commit that introduced the defect being fixed — yielding **1,930 fix-to-inducing links across eight programming languages**, extended in the journal version to an evaluation of nine variants over **2,304 instances**. Against that oracle, **R-SZZ performed best (F-measure ≈ 61%, precision ≈ 66%)** while B-SZZ achieved higher recall (≈ 0.69) at markedly lower precision (≈ 0.39).

**Two points about this dataset matter for the present work.**

First, it **cannot train a JIT-SDP model.** It contains fix-to-inducing links and no clean commits, so there is no negative class and no complete labelling of project history.

Second, **its precision figures are not comparable to this thesis's without reconciling the denominator.** Rosa et al. score *conditionally* on bug-fixing commits already known to have an inducing commit. This thesis scores over an entire project history of 27,319 commits, the overwhelming majority of which are clean. A variant that is right two times in three when asked "which earlier commit introduced this known defect?" can still be wrong four times in five when asked "is this commit, drawn from all of history, defect-introducing?" **The difference is large enough to read as a contradiction, and Chapter 8 addresses it explicitly.**

### 2.2.5 JIT-Defects4J and the reference labels

Ni et al. published **JIT-Defects4J**, an extension of LLTC4J, comprising **27,319 commits from 21 Java projects, of which 2,332 (8.54%) are labelled defect-introducing**. Its construction is two-stage: lines within bug-fixing commits were annotated manually, retained where at least three participants agreed; `git blame` was then applied to those verified lines.

**The labels are therefore `git blame` seeded with human-verified fix lines — not manually verified ground truth for defect-introducing commits.** This thesis uses them as its reference precisely because the distinction is tractable: they control for tangling, the dominant false-positive mechanism, while sharing SZZ's blame step. Comparisons against them isolate the cost of tangled commits, and blame error, being common to both sides, cancels. Chapter 3 §3.2.2 develops the consequences.

### 2.2.6 Other JIT-SDP datasets

| Dataset | Scale | Labels | Relevance here |
|---|---|---|---|
| **ApacheJIT** | 106,674 commits (28,239 bug-inducing), 14 Apache projects | SZZ-derived | Larger, but cannot serve as an oracle for a study of SZZ noise |
| **Defectors** | ~213K files, 24 Python projects, 18 domains | SZZ-derived | File-level; same objection |
| **ReDef** | 3,164 defective / 10,268 clean functions, 22 C/C++ projects | **Revert-anchored**, LLM-triaged, ~92% audited precision | Non-blame labels, but function-level, C/C++, no Kamei features, no fix dates |

**Scale is not the binding constraint for this thesis; label provenance is.** A study measuring what SZZ noise costs cannot use SZZ labels as its reference, which excludes the two largest datasets available.

---

## 2.3 Evaluation methodology in defect prediction

### 2.3.1 Temporal leakage

Random *k*-fold cross-validation on temporally ordered data allows a model to train on future commits and be tested on past ones. Time-aware evaluation — training only on the past and evaluating only on the future — has been advocated repeatedly, notably by Falessi and colleagues, who caution researchers against "time travel" and against generalising beyond the evaluation context. The reported effect is consistent in direction with this thesis's: in-sample performance is systematically inflated relative to time-aware performance. Random *k*-fold nonetheless remains widespread in the JIT-SDP literature.

**Chapter 5 measures the consequence rather than restating the argument.** The inflation is +0.137 MCC on a high-capacity model and it scales with model capacity, which means comparisons *between* model families under this protocol are confounded in a direction that favours larger models.

### 2.3.2 Prequential evaluation

For streams, the standard protocol is *test-then-train*: each example is first predicted, then used for learning. Summarising a metric over a stream requires a forgetting mechanism, conventionally a fading factor applied to the error estimate. Gama, Sebastião and Rodrigues (*On Evaluating Stream Learning Algorithms*, Machine Learning, 2013) defend prequential error with forgetting and prove that, **for consistent learning algorithms on stationary data, the prequential error computed with fading factors converges to the Bayes error**.

**An important caveat for this thesis.** That convergence result is established for an *error rate* — a decomposable loss accumulated example by example. **MCC is not decomposable**, being a non-linear function of all four confusion-matrix cells, so neither the construction nor its convergence guarantee extends to it directly. This thesis therefore reports two ad-hoc summaries of the MCC trajectory — a terminal fading value and a trajectory mean — treats the trajectory mean as primary **on measured variance rather than by appeal to a standard**, and states explicitly that neither is canonical. An earlier version of this work described one of them as "the standard estimator"; that was incorrect and is corrected in Chapter 3 §3.4.2.

### 2.3.3 Verification latency

Cabral and Minku identified verification latency as a first-class concern in JIT-SDP: labels arrive with a delay, and the delay differs systematically between classes, since a clean commit is only ever *presumed* clean while a defective one must be discovered. Their framing of latency and of the resulting **class imbalance evolution** is the setting this thesis adopts.

On the corpus studied here the median latency is **113 days**, with **53% of defect labels arriving after a 90-day window**. Under a fixed window, a defect label that arrives late is delivered first as a *wrong clean label* and corrected later — so latency is not merely delay but active misinformation, and the misinformation concerns exactly the minority class.

---

## 2.4 Online learning for JIT-SDP

**Online Bagging** (Oza and Russell, AISTATS 2001) adapts bagging to streams by presenting each arriving example to each ensemble member *k* ~ Poisson(λ) times, achieving performance comparable to batch bagging without storing the dataset.

**Oversampling Online Bagging (OOB)** (Wang, Minku and Yao) handles imbalance by setting λ from the running observed class ratio — tracked with time-decayed metrics — so minority examples are presented more often as the imbalance grows. OOB and its undersampling counterpart UOB are the standard data-level approaches for class-imbalanced streams.

**Oversampling Rate Boosting (ORB)** extends OOB by monitoring the model's own recent predictions: when predictions are considerably biased toward one class, the resampling rate of the opposite class is boosted. Cabral and Minku also adopt a safety mechanism intended to avoid training on potentially noisy or outlier minority-class examples.

> **This machinery is the subject of Chapter 6's central finding.** ORB's λ is a function of the *observed rate* of defect labels — that is, of label **quantity**. It has no access to label **quality**. Chapter 6 measures the coupling directly (Spearman ρ = −1.000 between delivered defect-label supply and applied λ) and shows that the mechanism correcting class imbalance is the mechanism that amplifies false positives, hardest exactly when defect labels are scarcest.

Cabral and Minku's later work (*Towards Reliable Online Just-in-Time Software Defect Prediction*) analyses concept drift in JIT-SDP across p(y), p(x|y) and p(x), reports **defect discovery delays ranging from one day to more than eleven years**, and proposes a drift-adaptive method that monitors predictions on unlabelled data rather than waiting for labels. **Their finding that medians are typically at or below 90 days, and that a 90-day waiting period trades off correct labelling against drift, is the basis for this thesis's choice of *W* = 90 days.** **The distinction from the present work is the origin of the noise.** Latency-induced noise is a timing artefact: the label is correct but late. SZZ-induced noise is a *labelling* artefact: the label is wrong and will never be corrected. This thesis addresses the second, under conditions that include the first.

---

## 2.5 The weak-baseline problem

Deep learning approaches to JIT-SDP — **DeepJIT** (Hoang et al., MSR 2019), which encodes commits hierarchically from line to hunk to file to commit using a convolutional text model, and **CC2Vec** (Hoang et al., ICSE 2020), which learns code-change representations supervised by commit logs via a hierarchical attention network — reported substantial gains over feature-based models. Two subsequent results complicate that picture.

Zeng et al., evaluating on over **310,370 changes**, found that CC2Vec could not consistently outperform DeepJIT and that neither consistently outperformed traditional feature-based JIT prediction. They then constructed **LApredict** — logistic regression on the added-lines feature alone — which outperformed both deep models while being roughly **81,000–120,000× faster** to train and test.

Pornprasit and Tantithamthavorn reported **JITLine**, a simpler feature-based approach that was **26–38% better in F-measure, 17–51% more cost-effective, and 70–100× faster** than CC2Vec and DeepJIT.

**Both models are used in this thesis, and the reason is methodological rather than deferential.** LApredict has minimal capacity; JITLine has a great deal. Chapter 5 shows that the inflation attributable to evaluation protocol is **+0.137 MCC for JITLine and +0.034 for LApredict**, and that the self-scoring gap is significant for all six SZZ variants under JITLine but only one under LApredict. **Capacity is not incidental to the measurement problem — it is the variable that determines its size**, which offers an alternative reading of why simple baselines have proven so hard to beat.

---

## 2.6 Metric selection

Under an 8.54% positive rate, accuracy is uninformative. This thesis uses:

**Matthews Correlation Coefficient (MCC)** — introduced by Matthews (1975) for protein secondary-structure prediction and since adopted widely for imbalanced binary classification — as primary. It incorporates all four confusion-matrix cells and is near zero for any uninformed strategy. A majority-class predictor scores 0.0 MCC and 91.5% accuracy on this corpus.

**G-mean**, the geometric mean of per-class recalls, which collapses toward zero if either class is abandoned.

**Cohen's κ** (Cohen, 1960), the proportion of agreement corrected for chance, for agreement between labelling procedures, where the question is concordance rather than prediction quality.

Effort-aware metrics — recall at a fixed inspection budget — arguably match the practitioner's objective more closely and are identified as future work in Chapter 9, not reported here.

---

## 2.7 Learning with noisy labels

**Loss correction.** Natarajan et al. (*Learning with Noisy Labels*, NIPS 2013) study binary classification under random classification noise whose **flip probability is class-conditional** — precisely the noise model Chapter 4 measures — and construct a simple **unbiased estimator of any loss**, with performance bounds for empirical risk minimisation on noisily labelled i.i.d. data. The correction becomes numerically unstable as ρ₀ + ρ₁ → 1. **This matters directly here**: Chapter 4 measures ρ₀ + ρ₁ approaching 0.8 for the conservative variants, which is why the loss-correction arm evaluated in this thesis is capped.

**Sample selection.** Co-teaching (Han et al., NeurIPS 2018) trains two networks simultaneously; on each mini-batch, each selects the examples it considers clean and back-propagates only the examples selected by its peer, on the premise that mislabelled examples exhibit higher loss early in training. It assumes a batch setting with multiple epochs and two models.

**Confident Learning** (Northcutt, Jiang and Chuang, JAIR 2021) assumes a **class-conditional** noise process and directly estimates the joint distribution between noisy and true labels, then prunes, counts with probabilistic thresholds, and ranks examples by confidence. It is a batch method requiring cross-validated out-of-sample predictions over a fixed dataset.

**Why these do not transfer directly.** Each assumes a fixed dataset, repeated passes, and labels that are wrong but *stable*. A JIT-SDP stream offers none of these: a single pass, labels arriving late, and labels that are **wrong and then corrected**. Chapter 7 adapts the confidence-based idea to the streaming setting, and its central negative result is informative about the whole family: a confidence signal cannot distinguish *"this label is wrong"* from *"my model has not learned this pattern yet"*, and the second case is common under severe imbalance with a still-learning model.

---

## 2.8 Positioning

| Work | Imbalance | Drift | Latency | SZZ noise **measured** | Online |
|---|---|---|---|---|---|
| Kamei et al. | ○ | ○ | ○ | ○ | ○ |
| Cabral & Minku (ORB; drift work) | ● | ● | ● | ○ | ● |
| Rosa et al. (developer-informed oracle) | ○ | ○ | ○ | ● *(labels only)* | ○ |
| Herbold et al. (tangling) | ○ | ○ | ○ | ● *(labels only)* | ○ |
| Zeng et al. / Pornprasit & Tantithamthavorn | ● | ○ | ○ | ○ | ○ |
| Natarajan / Co-teaching / Confident Learning | ● | ○ | ○ | ◐ *(noise model assumed, not measured)* | ○ |
| **This thesis** | ● | ● | ● | ● **downstream cost** | ● |

*(● addressed · ◐ partially · ○ not addressed)*

**The distinguishing cell is the fourth.** SZZ evaluation work measures the noise and stops at the labels. Online JIT-SDP work operates under latency but treats label noise as a nuisance to dampen rather than a quantity to measure. Noisy-label learning assumes a noise model rather than estimating one, and assumes a batch setting. This thesis measures **what SZZ-origin noise costs downstream, under latency-aware online evaluation**, and then tests whether that cost can be recovered.

The methodological device that makes this possible is small and worth naming: **an independently constructed reference label set, held out from training and used only for scoring.** Without it, a model trained on SZZ can only be evaluated against SZZ, and the largest effect in this thesis — the +0.230 MCC self-scoring gap — is invisible by construction.

---

## 2.9 Citation verification status

Every work cited in this chapter was checked against its publisher record or the source during preparation. The table records what was confirmed.

| Work | Venue | Confirmed |
|---|---|---|
| Śliwerski, Zimmermann & Zeller, *When Do Changes Induce Fixes?* | MSR 2005 | Original SZZ; fix-inducing change analysis over CVS archives |
| Kim et al. | 2006 | AG-SZZ: annotation graphs, cosmetic-change filtering |
| da Costa et al. | 2017 | MA-SZZ: excludes meta-changes (branch merges, property changes) |
| Davies et al. | 2014 | R-SZZ (most recent candidate), L-SZZ (most changed lines) |
| Neto et al. | 2018 | RA-SZZ: refactoring-aware via RefDiff / RefactoringMiner, Java only |
| Rosa et al. | ICSE 2021; *JSS* 202:111729, 2023 | 1,930 links, 8 languages, 2,304 instances; R-SZZ best (F ≈ 61%, P ≈ 66%); B-SZZ recall ≈ 0.69, precision ≈ 0.39; PySZZ |
| Herbold et al. | *EMSE*, 2022 | 17–32% of changes / 66–87% production code; four annotators per line; ~11% disagreement |
| Ni et al. | *ESEC/FSE* 2022 | JIT-Defects4J; 27,319 commits / 2,332 defective / 21 projects; two-stage construction |
| Kamei et al. | *IEEE TSE* 39(6):757–773, 2013 | Task formulation, change-level metrics; ~68% accuracy, 64% recall |
| Cabral & Minku | *ICSE* 2019 | Class imbalance evolution, verification latency, ORB, safety mechanism |
| Cabral & Minku, *Towards Reliable Online JIT-SDP* | — | Drift across p(y), p(x\|y), p(x); delays from 1 day to >11 years; medians at or below 90 days; 90-day waiting time as the trade-off |
| Oza & Russell, *Online Bagging and Boosting* | AISTATS 2001, PMLR R3:229–236 | Poisson(λ) online bagging matching batch performance |
| Wang, Minku & Yao | — | OOB / UOB; time-decayed class-imbalance tracking |
| Gama, Sebastião & Rodrigues, *On Evaluating Stream Learning Algorithms* | *Machine Learning*, 2013 | Prequential error with fading factors converges to Bayes error for consistent learners on stationary data |
| Hoang et al., *DeepJIT* | MSR 2019 | Hierarchical line→hunk→file→commit encoding, textCNN |
| Hoang et al., *CC2Vec* | ICSE 2020 | Code-change representations supervised by commit logs, hierarchical attention |
| Zeng et al. | *ISSTA* 2021 | 310,370 changes; LApredict; 81k–120k× speedup |
| Pornprasit & Tantithamthavorn, *JITLine* | *MSR* 2021, pp. 369–379 | 26–38% F-measure, 17–51% cost-effectiveness, 70–100× faster |
| Keshavarz & Nagappan, *ApacheJIT* | *MSR* 2022 | 106,674 commits, 28,239 bug-inducing, 14 projects |
| Mahbub, Shuvo & Rahman, *Defectors* | *MSR* 2023 | ~213K files, 24 Python projects, 18 domains |
| ReDef | preprint, 2025 | 3,164 / 10,268 function-level changes, 22 C/C++ projects, revert-anchored, ~92% precision |
| Matthews | *BBA* 405(2):442–451, 1975 | MCC, originally for protein secondary-structure prediction |
| Cohen | *Educ. Psychol. Meas.* 20:37–46, 1960 | κ as agreement corrected for chance |
| Natarajan et al., *Learning with Noisy Labels* | NIPS 2013 | Class-conditional flip probability; unbiased loss estimator; ERM bounds |
| Han et al., *Co-teaching* | NeurIPS 2018 | Two networks exchanging small-loss examples per mini-batch |
| Northcutt, Jiang & Chuang, *Confident Learning* | *JAIR* 70, 2021 | Class-conditional noise; joint distribution estimation; prune, count, rank |
| Zhao, Damevski & Chen | *ACM CSUR* 55(10):1–35, 2023 | Systematic survey of JIT-SDP; 67 studies |
| Destefanis et al., *An Audit of ML Experiments on Software Defect Prediction* | *EMSE*, 2026 | 101 audited papers; SCOPUS 2019–2023; design, analysis and reporting practice |
| Falessi et al. | — | Time-aware evaluation; caution against "time travel"; in-sample performance systematically inflated |

### Two notes on the bibliography

**One cited work was removed.** The project's planning documents referenced "Song et al. (2022)" as a method addressing latency-induced label noise in JIT-SDP. **That work could not be located.** Searching the area returns Cabral and Minku on verification latency and Tabassum, Minku and colleagues on waiting-time labelling, either of which may have been what was intended. The reference is therefore omitted rather than guessed at, and §2.4's claim about latency-noise methods is attributed only to work that was confirmed. **If a specific Song et al. paper was intended, locate it before reinstating the citation.**

**One attribution needs confirming.** A deep-learning-in-SDP systematic review and meta-analysis exists (*Information and Software Technology*, 2023) and is the work the planning documents meant by "Zain et al.", but the first-author attribution was not confirmed. It is not cited in this chapter; if it is added, check the author list.

**One correction to the project's own outline.** An earlier outline attributed to Herbold et al. a finding that "~50%" of SZZ labels are wrong. The verified figures are **17–32% of all changes in bug-fixing commits** addressing the underlying problem, rising to **66–87%** for production-code files only — a different quantity, measured at line rather than commit level. The "~50%" figure does not appear in the source and must not be cited.

**Remaining work for the bibliography.** Page numbers and DOIs should be taken from the publisher records when the reference list is typeset; a few entries above carry venue and year but not pagination. Nothing in the chapter's prose depends on those details.

# Learning Guide: SZZ Label Noise in Just-In-Time Defect Prediction

A concept-by-concept study guide for your thesis. Each section gives (a) an intuitive explanation, (b) the precise technical definition, and (c) how it connects to your four phases — so you can move between "explain it to anyone" and "defend it to your supervisor" fluently.

---

## Part A — The Problem Domain

### 1. Software Defect Prediction (SDP)

**Intuition.** Testing and code review effort is finite. If you could rank the parts of a codebase by "probability this contains a bug," you'd spend reviewer attention where it matters most. SDP is the field of building models that produce exactly that ranking.

**Technical.** A supervised classification problem: given features of a software artifact (a file, module, or commit), predict a binary label — *defective* or *clean*. Classic granularity was file- or module-level, predicted per release.

**Connection to thesis.** Your thesis lives in the modern, finer-grained version of this problem: commit-level prediction.

### 2. Just-In-Time Software Defect Prediction (JIT-SDP)

**Intuition.** Instead of asking "which files are risky?" after a release, ask "is *this commit I'm pushing right now* likely to introduce a bug?" — at the exact moment the developer still has full context. That's the "just-in-time" part: prediction at commit time, when fixing is cheapest.

**Technical.** Each software change (commit) is represented by change-level features — commonly the 14 Kamei et al. (2013) metrics, grouped as:
- **Diffusion:** number of subsystems/directories/files touched (NS, ND, NF), entropy of changes.
- **Size:** lines added (LA), lines deleted (LD), lines total before change (LT).
- **Purpose:** whether the change is a fix (FIX).
- **History:** number of prior developers of touched files (NDEV), average time since last change (AGE), unique prior changes (NUC).
- **Experience:** developer experience (EXP), recent experience (REXP), subsystem experience (SEXP).

The model outputs P(defect-inducing | commit features).

**Why it's hard.** (1) Severe class imbalance — typically <10–20% of commits induce defects. (2) It's inherently a *data stream*: commits arrive in temporal order, the project evolves, and the data distribution shifts (concept drift). (3) You don't learn a commit's true label until much later (verification latency, below).

**Connection to thesis.** JIT-SDP is your entire evaluation setting. Every experimental choice you make (online evaluation, ORB, MCC/G-mean) is a response to those three hardness properties.

### 3. Where labels come from: the SZZ algorithm

**Intuition.** To train a defect predictor, someone must label historical commits as "induced a bug" or not. Nobody labels this by hand at scale — instead, an algorithm walks backwards through version-control history. SZZ (named for Śliwerski, Zimmermann, Zeller, 2005) is that algorithm, and *virtually every JIT-SDP dataset was labeled with some version of it.*

**How it works, step by step.**
1. **Find bug-fixing commits.** Link the issue tracker to the version history — e.g., a commit whose message mentions "Fixes JIRA-1234" where JIRA-1234 is a closed bug report.
2. **Identify the fixed lines.** Diff the fixing commit against its parent: the lines that were *deleted or modified* are assumed to be the buggy lines.
3. **Blame backwards.** Use `git blame` (originally `cvs annotate`) to find which earlier commit last touched those lines. Those earlier commits are labeled **bug-inducing**.

**Why it breaks.** Every step has failure modes:
- Step 1: commit messages are noisy; issue trackers misclassify features as bugs (and vice versa); many fixes are never linked.
- Step 2: fixing commits contain *tangled changes* — formatting, refactoring, unrelated edits — so "changed lines" ≠ "buggy lines."
- Step 3: blame lands on cosmetic changes (whitespace, renames, refactorings) that merely *touched* a line last, not the commit that introduced the logic error. Bugs can also exist from a file's first version, or be induced by changes elsewhere entirely.

**The headline number for your thesis.** Herbold et al. (2022), auditing 398 releases of 38 Apache projects, found roughly **only half of the commits SZZ flags as bug-fixing actually are** — meaning datasets built on SZZ are trained *and evaluated* against substantially wrong ground truth.

### 4. The SZZ variant family (your Phase 1 toolkit)

Each variant patches a specific failure mode of the original:

| Variant | Full idea | What it fixes |
|---|---|---|
| **B-SZZ** | The original 2005 heuristic | Nothing — it's the baseline |
| **AG-SZZ** | Annotation-graph based (Kim et al., 2006) | Skips blank lines, comment-only lines, and cosmetic changes when blaming backwards |
| **MA-SZZ** | Meta-change aware | Excludes "meta-changes" — branch changes, merges, property/permission changes — that can't introduce bugs |
| **RA-SZZ** | Refactoring-aware | Uses refactoring-detection tools (e.g., RefDiff/RefactoringMiner) so pure refactorings aren't blamed as bug-inducing |
| **R-SZZ** | Rosa et al.'s refinement | Selects only the *latest* commit that modified the buggy lines rather than all of them; best performer against the developer-informed oracle |

**Key vocabulary:** the *developer-informed oracle* (Rosa et al., 2021) is a ground-truth dataset where the bug-inducing commit is explicitly identified by the developers themselves (e.g., in the fix's commit message), removing the guesswork. **JIT-Defects4J** gives you manually validated commit-level labels to benchmark against in Phase 1.

**Talking point for your supervisor.** The variants don't just differ in *accuracy* — they differ in *bias direction*. B-SZZ over-blames (many false positives from cosmetic blame); R-SZZ is conservative (fewer, more precise inducements). This asymmetry is exactly what your Phase 3 asymmetric noise model is calibrated to.

---

## Part B — Honest Evaluation

### 5. Why naive evaluation lies: temporal leakage

**Intuition.** If you shuffle commits from 2015–2020 into random train/test folds, your model trains on 2019 commits to "predict" 2016 ones. In production, no model sees the future. Random k-fold on temporal data systematically inflates performance.

**Three evaluation regimes (your Phase 2 axis):**
1. **Naive k-fold:** random shuffling, ignores time. Upper bound of self-deception.
2. **Chronological (time-aware) split:** train on the first X% of commits by date, test on the rest. Honest about ordering, but still a *batch* view — trains once, never updates.
3. **Prequential (online) evaluation:** the gold standard for streams. Each arriving commit is first *predicted* (test), and only later — once its true label becomes known — *used for training*. "Test-then-train," one instance at a time, typically with a fading factor to emphasize recent performance.

### 6. Verification latency (label delay)

**Intuition.** A commit made today might be discovered as buggy eight months from now, when someone finally hits the bug and fixes it. So at prediction time, recent history is full of commits whose labels you *cannot know yet*.

**Technical.** In a temporally honest online setup, a commit's defect label only becomes available at the time of its *fixing commit* (the label arrival time). Until then it is unlabeled — or worse, tentatively treated as "clean." Common protocol (Cabral et al., 2019): a commit is assumed clean if no fix has linked to it within a waiting window **W** (e.g., 90 days); if a fix arrives later, a corrected "defective" training example is issued at that point.

**Two distinct noise sources — memorize this distinction, it IS your gap statement:**
- **Latency-induced noise:** commits temporarily mislabeled clean because their bug hasn't surfaced yet. *This is what Song et al. (2022) tackle.*
- **SZZ-induced noise:** commits permanently mislabeled because the labeling algorithm itself is wrong — even after infinite waiting time. *This is what nobody has isolated under online evaluation, and it's your thesis.*
- (And **concept drift** — the data distribution changing over time — is what Cabral & Minku (2023) study. Also not your gap.)

### 7. Class imbalance evolution

**Intuition.** Not only are defect-inducing commits rare, their *rate changes over time* — a project might have 25% defective commits during a rushed release and 5% during maintenance. A model tuned for one imbalance ratio degrades when the ratio drifts.

**Connection.** This is precisely the problem ORB was invented for.

---

## Part C — The Algorithms

### 8. Online Bagging and Oversampling Online Bagging (OOB)

**Online Bagging (Oza & Russell).** Classic bagging trains each ensemble member on a bootstrap sample. In a stream you can't bootstrap — you see each instance once. Trick: presenting an instance to each ensemble member **k ~ Poisson(1)** times is statistically equivalent to bootstrap sampling as the stream grows.

**OOB.** To fight imbalance, inflate the Poisson rate for the minority class: minority instances are shown **k ~ Poisson(λ)** times with λ > 1 (proportional to the current imbalance ratio), majority instances with λ ≤ 1. Online oversampling without storing data.

### 9. ORB — Oversampling Rate Boosting (your core baseline and the thing you'll extend)

**Intuition.** OOB's λ depends only on the *class imbalance* it has observed. But under verification latency, observed imbalance is itself wrong (recent defective commits still look clean). ORB's insight: don't just watch the class ratio — watch the *model's own prediction bias*. If the model has recently been predicting "clean" far too often relative to a target rate, crank up the oversampling of defective examples; if it over-predicts "defective," damp it down.

**Technical.** ORB (Cabral et al., 2019) extends OOB with a dynamic boosting factor applied to λ. It tracks a moving average of the model's recent predictions (the "bias signal"), compares it to the expected defect rate, and multiplies the minority-class Poisson rate by a boost function **obf(bias)** — typically an exponential-shaped curve so correction is gentle near balance and aggressive when the model has collapsed to the majority class.

**Why noise wrecks it (your Phase 3 hypothesis).** ORB assumes the labels arriving in the stream are trustworthy. Feed it SZZ false positives and the boost function sees "the model keeps missing defects!" — and amplifies *mislabeled* examples with extra Poisson weight. The mechanism designed to fix imbalance becomes a **noise amplifier**. Demonstrating this dose-response relationship is Phase 3's contribution.

### 10. The offline baselines: LApredict and JITLine

- **LApredict (Zeng et al., 2021):** logistic regression using essentially a single feature — lines added (LA). Embarrassingly simple, yet it *beat* deep models (DeepJIT, CC2Vec) across large benchmarks. It exists in your thesis as the "weak baseline" cautionary tale: any proposed method must beat this or it's noise.
- **JITLine (Pornprasit & Tantithamthavorn, 2021):** random forest over change features + token features, with SMOTE for imbalance and line-level defect localization via model-agnostic explanation (LIME). Faster and better than DeepJIT/CC2Vec.
- **DeepJIT / CC2Vec:** CNN- and hierarchical-attention-based deep models over commit messages and code changes. Retained as secondary baselines; the surveys (Zhao et al., 2023; Zain et al., 2023) show deep SDP models plateauing and often losing to simple ones.

---

## Part D — Metrics (and why yours are non-negotiable)

### 11. Why not accuracy or F1?

With 10% defective commits, "always predict clean" scores 90% accuracy. F1 is threshold-dependent, ignores true negatives entirely, and its value under imbalance is hard to compare across datasets with different defect rates. The Destefanis et al. (2026) audit found problematic metrics in ~two-thirds of 101 SDP studies — the single most common methodological flaw. Using MCC/G-mean is your preemptive defense against that criticism.

### 12. Matthews Correlation Coefficient (MCC)

**Intuition.** A correlation coefficient between predicted and true labels: +1 perfect, 0 no better than chance, −1 perfectly wrong. It only scores high if the model does well on *all four* confusion-matrix cells — you can't cheat it with class imbalance.

**Formula.**
MCC = (TP·TN − FP·FN) / √((TP+FP)(TP+FN)(TN+FP)(TN+FN))

**Key phrase for meetings:** "chance-anchored" — 0 always means chance-level, regardless of imbalance.

### 13. G-mean

**Formula.** G-mean = √(Recall₁ · Recall₀) = √(TPR · TNR)

**Intuition.** Geometric mean of per-class recalls. If the model abandons either class, one factor → 0 and the whole score collapses. Standard in the online JIT-SDP literature (it's what the ORB papers optimize), which makes your results directly comparable.

### 14. Precision, recall, and labeling bias (Phase 1 metrics)

Evaluated *for the SZZ variant itself* against the oracle: of commits a variant flags as inducing, how many truly are (precision)? Of the truly inducing commits, how many does it find (recall)? **Labeling bias** = the direction and rate of its errors (false-positive rate vs. false-negative rate) — this pair of numbers is what parameterizes your Phase 3 asymmetric noise model. Also useful: Cohen's kappa between variants (how much they even agree with each other).

---

## Part E — Learning with Noisy Labels (Phase 4 foundations)

### 15. The noisy-label problem in one paragraph

If a fraction of training labels are flipped, empirical risk minimization converges to the wrong classifier — the model literally learns the noise. Three families of countermeasures exist, and your Noise-Aware ORB borrows one idea from each.

### 16. Loss correction (Natarajan et al., 2013)

**Intuition.** If you *know the noise rates* (probability a clean commit is labeled defective, ρ₀, and vice versa, ρ₁), you can algebraically "un-bias" the loss function so that minimizing the corrected loss on noisy data is equivalent, in expectation, to minimizing the true loss on clean data.

**Mechanics.** Each example's loss is rewritten as a weighted combination:
ℓ̃(y, ŷ) = [(1 − ρ_{−y}) ℓ(y, ŷ) − ρ_y ℓ(−y, ŷ)] / (1 − ρ₀ − ρ₁)

**Your twist.** Phase 1 gives you *measured* SZZ noise rates per variant — you don't have to estimate them blindly. That's an unusually strong position for applying loss correction.

### 17. Co-teaching (Han et al., 2018)

**Intuition.** Neural nets memorize clean patterns before noisy ones ("memorization effect"). So early in training, *low-loss* examples are probably correctly labeled. Co-teaching runs two networks in parallel; each selects its lowest-loss instances in a batch and hands them to *the other* network for training. Using two networks prevents a single model's errors from self-reinforcing.

**Your adaptation.** An "agreement check" between two ensemble members (or two ORB ensembles): instances where both confidently disagree with the incoming label get down-weighted or flagged.

### 18. Confident Learning (Northcutt et al., 2021)

**Intuition.** Use the model's own predicted probabilities to find label errors — no known noise rate required. If a commit is labeled "defective" but the model (via cross-validated, out-of-sample probabilities) assigns it a very high probability of "clean" — higher than the class's *self-confidence threshold* (the average predicted probability of examples genuinely in that class) — it's probably mislabeled.

**Mechanics.** (1) Get out-of-sample predicted probabilities for every instance. (2) Compute per-class confidence thresholds. (3) Build the *confident joint* — a matrix counting instances whose predicted class (above threshold) disagrees with the given label. (4) Prune/rank the most likely label errors.

**Your adaptation challenge (be ready to discuss this).** Confident Learning is defined for offline, i.i.d. data with cross-validation. Your setting is streaming and non-stationary. The adaptation: maintain *running* per-class confidence thresholds over a sliding window, and compute a per-instance label-confidence score at the moment its (possibly noisy) label arrives — then feed that score into ORB's boost function so low-confidence "defective" labels receive less oversampling. This is the intellectual core of Noise-Aware ORB.

---

## Part F — One-Paragraph Thesis Elevator Pitch (memorize this)

> "JIT-SDP models are trained and judged against labels produced by SZZ, an algorithm we know is wrong about half the time. Prior online JIT-SDP work has handled noise from *verification latency* (Song et al., 2022) and instability from *concept drift* (Cabral & Minku, 2023), but nobody has isolated the noise SZZ itself injects upstream — under a realistic, latency-aware online evaluation. I first *measure* that noise against a human-verified oracle (Phase 1), then show how it *distorts* reported performance across evaluation regimes (Phase 2), then *diagnose the mechanism* by which ORB's oversampling boost amplifies it (Phase 3), and finally *fix it* with Noise-Aware ORB, which modulates oversampling by per-instance label confidence rather than only imbalance or drift signals (Phase 4)."

---

## Part G — Rapid-fire Q&A prep (questions your supervisor may ask)

1. **"Why not just use R-SZZ everywhere and call it a day?"** Even the best variant is imperfect; and more importantly, the field's *existing* datasets and benchmarks were built with weaker variants. Quantifying the downstream damage is necessary to interpret a decade of published results.
2. **"How is Phase 3 different from generic label-noise studies?"** The asymmetric noise model is *calibrated to measured SZZ bias* from Phase 1 — it simulates the specific error structure SZZ produces, not textbook uniform flips; the uniform-flip arm exists only as a control.
3. **"What if Noise-Aware ORB doesn't beat ORB?"** A well-executed negative result is still a contribution: it would show label-confidence signals are insufficient under non-stationarity, and Phases 1–3 stand alone as an empirical contribution. (Also see the Alternatives document — there are backup designs.)
4. **"Which datasets?"** JIT-Defects4J for oracle comparison (manually validated labels); large SZZ-labeled corpora such as ApacheJIT for scale; the classic Cabral et al. (2019) ten-project stream datasets for online evaluation comparability.
5. **"How do you handle statistical significance in a stream?"** Prequential metrics with fading factors, multiple runs with different seeds, and non-parametric tests (Wilcoxon signed-rank across projects) with effect sizes (Cliff's delta) — never a single-run comparison.

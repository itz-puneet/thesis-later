# Alternative Execution Options

Backup plans per phase, with the deepest treatment on Phase 4 as requested. Each alternative lists: the idea, why it's easier/safer than the primary plan, and what you give up.

---

## Phase 1 alternatives

**Primary plan:** run pyszz_v2 (5 variants) yourself, benchmark against JIT-Defects4J.

- **Alt 1A — Use precomputed labels.** Several replication packages (Rosa et al.'s oracle repo, Herbold et al.'s data, ApacheJIT) ship SZZ outputs. Merge published label sets instead of re-running SZZ. *Saves:* weeks of tooling pain (especially RA-SZZ's refactoring-miner dependency). *Costs:* less control over configs; you must document version/parameter provenance carefully.
- **Alt 1B — Reduce the variant set.** If RA-SZZ tooling fails, a {B-SZZ, MA-SZZ, R-SZZ} triad still spans the naive→refined spectrum and preserves the bias-gradient story. Justify as "worst / mainstream / best-known" endpoints.
- **Alt 1C — Add an LLM-assisted mini-oracle.** If oracle coverage is too small for per-project bias estimates, manually validate a stratified sample of ~200–300 SZZ-flagged commits yourself (with an LLM as a second annotator, you as adjudicator; report inter-annotator agreement). This is a defensible, publishable oracle-extension protocol.

## Phase 2 alternatives

**Primary plan:** 3 models × 6 label sources × 3 regimes.

- **Alt 2A — Drop deep baselines entirely.** Zeng et al. (2021) already established DeepJIT/CC2Vec underperform LApredict; citing that and scoping deep models out is legitimate and saves GPU time. Get supervisor sign-off in Meeting 0.
- **Alt 2B — Two regimes instead of three.** If prequential infrastructure slips, {naive k-fold vs chronological} still demonstrates temporal-leakage inflation; add latency only for ORB. Weakens RQ2 but keeps the chapter.
- **Alt 2C — Use `river` instead of custom online code.** The `river` library provides tested online learners, prequential evaluation, and Hoeffding trees. Swap the base learner in `online/orb.py` for `river.tree.HoeffdingTreeClassifier` (the codebase is structured so only `_OnlineBase` changes).

## Phase 3 alternatives

**Primary plan:** synthetic dose-response with symmetric + SZZ-calibrated asymmetric noise.

- **Alt 3A — Natural-experiment design.** Instead of injecting noise, exploit the real label sources: treat R-SZZ as "low noise" and B-SZZ as "high noise" and compare ORB behavior directly. *Saves:* the calibration machinery. *Costs:* no dose control; confounded by which commits differ.
- **Alt 3B — Pair-flip noise model.** If calibrating asymmetric rates proves unstable across projects, use the standard class-conditional "pair flip" model at fixed ρ₀:ρ₁ = 2:1 (justified by Phase 1's typical direction). Less precise, fully standard in the noisy-labels literature.

---

## Phase 4 — Backup designs for Noise-Aware ORB (the main event)

**Primary plan:** ORB + streaming Confident-Learning confidence term + Natarajan loss correction (+ optional co-teaching agreement check).

**Failure modes to watch for:** (i) the confidence estimator is unreliable early-stream / after drift (the model's own probabilities are exactly wrong when they're most needed); (ii) loss-correction weights destabilize SGD under imbalance; (iii) the combined system has too many interacting hyperparameters to tune honestly.

### Backup A — Filtering-ORB (self-cleaning stream, simplest possible mechanism)

**Idea.** Instead of *weighting* by continuous confidence, make a binary keep/discard (or keep/down-weight-to-ε) decision per arriving label using a simple disagreement rule: if the ensemble's out-of-model probability contradicts the arriving label beyond a threshold τ for k consecutive checks, don't let that instance trigger the boost. This is the streaming analogue of classic *filter-then-train* noise handling (Brodley & Friedl's classification filtering), and needs exactly two hyperparameters.

**Why it's a safe fallback.** No probability calibration needed (only a threshold on disagreement), no noise-rate estimates, trivially explainable, and cheap. If full NA-ORB fails from estimator unreliability, filtering usually still works because it only acts on *high-confidence* contradictions.

**What you give up.** Discards information (a 55%-suspicious label is treated same as certain-clean); a fixed τ can be wrong after drift — pair it with a drift detector (e.g., ADWIN) that resets τ's statistics.

### Backup B — Robust-loss ORB (change the loss, not the pipeline)

**Idea.** Keep ORB's architecture untouched and replace the base learners' log-loss with a *noise-robust loss*: Generalized Cross-Entropy (Zhang & Sabuncu, 2018 — a tunable bridge between MAE and CE), or the symmetric/reverse cross-entropy family. Theory says MAE-like losses are inherently tolerant to class-conditional label noise without knowing noise rates.

**Why it's a safe fallback.** Zero new streaming machinery — it's a one-line change in the SGD gradient. No estimates, no windows, no thresholds beyond the single q parameter of GCE. If the *interaction complexity* of the primary design is what kills you, this is the minimal-moving-parts answer.

**What you give up.** Robust losses slow down learning on clean data (flatter gradients), which can hurt precisely in the online, drift-prone setting where fast adaptation matters — this trade-off itself is a nice experiment (plot adaptation speed after the drift point vs. noise robustness).

### Backup C — Label-smoothing / soft-label ORB with importance reweighting

**Idea.** Convert arriving hard labels into *soft targets* using the measured Phase 1 noise rates: an arriving "defective" label becomes target P(defective) = 1 − ρ̂₀·prior-adjustment (a streaming form of backward correction via the noise-transition matrix, Patrini et al., 2017). Train members on soft targets; ORB's boost is computed from the soft target mass rather than the hard label.

**Why it's a safe fallback.** Uses only Phase 1's *fixed, measured* noise matrix — no per-instance estimation at all, so it cannot be destabilized by the model's own miscalibration. Deterministic, easy to analyze, and directly showcases Phase 1's bias measurements as an input (nice narrative closure).

**What you give up.** Assumes noise is class-conditional and stationary — instance-dependent SZZ errors (e.g., large tangled commits are more mislabeled) violate this. Report it as a limitation; optionally test it by stratifying error rates by commit size in Phase 1.

### Backup D (architectural pivot, if ORB extension itself proves brittle) — Two-model cascade

**Idea.** Decouple entirely: an unchanged, stock ORB does the predicting; a separate lightweight "label auditor" (e.g., an online isolation forest or a second small classifier trained with delayed, higher-quality R-SZZ labels) sits in front of the training stream and assigns each arriving label a trust score that scales its Poisson weight. Because the auditor is outside ORB, you can validate it independently (does its trust score correlate with true mislabeling in Phase 3's injected-noise data? — an AUC you can report before ever touching prequential results).

**Why it's the strategic reserve.** It converts one hard problem ("modify ORB safely") into two easy, separately-testable ones. Even if end-to-end gains are small, the auditor's mislabel-detection AUC is a standalone result.

### Decision rule (bring this to your supervisor)

1. Build the primary NA-ORB *ablation-first* (Phase 4 plan step 1).
2. If the **confidence term** alone underperforms plain ORB on clean data → estimator unreliability → pivot to **Backup A** (filtering) as the per-instance mechanism.
3. If **loss correction** destabilizes training → pivot to **Backup B** (robust loss) or **Backup C** (soft labels) as the noise-rate-using mechanism.
4. If ORB modification is brittle across projects regardless of mechanism → **Backup D** (cascade), and reframe the chapter as "auditing the label stream" rather than "modifying the learner."
5. Whatever happens, the thesis is safe: Phases 1–3 are self-contained empirical contributions, and a rigorous negative result in Phase 4 with a mechanism explanation is still a defensible chapter.

---

## Tooling alternatives (cross-phase)

| Need | Primary | Alternative |
|---|---|---|
| SZZ | pyszz_v2 | SZZ Unleashed; precomputed labels (Alt 1A) |
| Mining | pydriller | git log parsing; dataset-provided features |
| Online learning | custom numpy ensemble (this codebase) | `river` (Hoeffding trees, prequential built-in) |
| Confident learning reference | custom streaming version | `cleanlab` offline on sliding windows (batchified) |
| Stats | scipy Wilcoxon + custom Cliff's delta | `autorank` package (does the full ranking pipeline + plots) |

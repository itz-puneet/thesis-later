# Phase-Wise Execution & Supervisor Review Plan

Each phase below has: step-by-step tasks, a **"ready-for-meeting" checklist** (what must exist before you book the meeting), and **presentation tips** for that specific meeting. Assume 4 supervisor checkpoints (one per phase) plus a kickoff.

---

## Meeting 0 — Kickoff (before any experiments)

**Bring:** the proposal, the thesis outline (`02_Thesis_Outline.md`), the RQ list, and a dataset shortlist.
**Goal:** lock scope. Get explicit sign-off on: (a) the four RQs, (b) datasets, (c) MCC + G-mean as primary metrics, (d) which SZZ variants are in scope, (e) whether DeepJIT/CC2Vec are required or optional.
**Tip:** bring the positioning table (Section 2.8 of the outline) — one slide showing Cabral & Minku 2023, Song et al. 2022, and your thesis as three rows with different checkmarks. This single visual defends your novelty claim for the entire project.

---

## Phase 1 — Label Disagreement and Oracle Comparison (≈ 3–4 weeks)

### Steps
1. **Acquire data.** Clone JIT-Defects4J (oracle labels) and the subject repositories. Verify you can reproduce the paper's commit counts — a sanity check supervisors love.
2. **Set up pyszz_v2.** Get one variant (B-SZZ) running end-to-end on ONE small repository first. Only then scale to all five variants × all projects. (Budget real time here: SZZ tooling is fiddly — Java/tooling deps for RA-SZZ's refactoring detection are a known pain point.)
3. **Generate labels.** Run all five variants; store per-variant label columns keyed by commit hash (`szz/variants.py` interface).
4. **Compute quality metrics.** `python -m experiments.run_phase1 --data ...` → precision, recall, FP-rate (ρ₀), FN-rate (ρ₁), MCC-vs-oracle per variant; pairwise Cohen's kappa between variants.
5. **Export the bias model.** `phase1_bias.json` — this file is a *deliverable*, not a by-product: it parameterizes Phase 3.
6. **Slice the analysis.** Per-project breakdown; check whether bias direction is stable across projects (if it isn't, that's a finding — Phase 3 then needs per-project calibration).

### Ready-for-meeting checklist
- [ ] Table: 5 variants × {precision, recall, ρ₀, ρ₁, kappa-vs-oracle, N}
- [ ] Heatmap: pairwise variant agreement (Cohen's kappa)
- [ ] Bar chart: FP-rate vs FN-rate per variant (the "bias direction" picture)
- [ ] One paragraph: "does our data replicate Herbold's ~50% and Rosa's R-SZZ-is-best findings?" (agreement with published numbers = credibility)
- [ ] `phase1_bias.json` committed

### Presentation tips
- Lead with the replication check ("our numbers are consistent with Herbold/Rosa"), *then* show what's new (the per-variant ρ₀/ρ₁ decomposition).
- Frame every plot with the sentence it will caption in the thesis. If you can't caption it, cut it.
- Anticipated question: *"why these five variants?"* Answer: they're the Rosa et al. lineage with a developer-informed evaluation history, spanning the naive-to-refined spectrum.

---

## Phase 2 — Downstream Impact Under Honest Evaluation (≈ 4–5 weeks)

### Steps
1. **Feature extraction.** Compute the 14 Kamei features per commit (pydriller or reuse dataset-provided features). Validate distributions against published summaries.
2. **Freeze the grid.** 3 models × 6 label sources (oracle + 5 variants) × 3 regimes. Decide *before running* which cells you'll report — no post-hoc cherry-picking.
3. **Decide the scoring convention and state it loudly:** train on each label source, but *score everything against the oracle* (isolates label-quality effects). Also run the field-standard self-scored version (train and test on same SZZ labels) — the *difference between the two* is itself a headline result.
4. **Run.** `run_phase2.py` with 10 seeds; store per-seed results, never just means.
5. **Statistics.** Wilcoxon signed-rank + Cliff's delta across projects for each pairwise regime comparison; Holm–Bonferroni for the multiple comparisons.

### Ready-for-meeting checklist
- [ ] The "inflation ladder" figure: same model+labels, MCC under naive → chronological → prequential-latency (expect a staircase downward)
- [ ] Label-source sensitivity figure: per regime, the spread of MCC across the 6 label sources (does honest evaluation widen or narrow the spread?)
- [ ] Self-scored vs oracle-scored comparison table
- [ ] Statistical test table with effect sizes
- [ ] 3 bullet answers to RQ2, each tied to one figure

### Presentation tips
- Open with the single most surprising number (e.g., "naive k-fold overstates MCC by X points on average").
- Keep LApredict visible in every figure — the "a one-feature logistic regression does *this* well" framing lands strongly and shields you from "why no deep models front-and-center" questions.
- Anticipated question: *"is the ORB row comparable to the batch rows?"* Prepared answer: no regime is comparable *across* rows by design — the comparison is within-model, across regimes and label sources.

---

## Phase 3 — Diagnosing Learner Behaviour Under Noise (≈ 3–4 weeks)

### Steps
1. **Wire Phase 1's bias into the noise model** (`noise/injection.py` reads `phase1_bias.json`).
2. **Dose-response runs:** {symmetric, asymmetric-SZZ} × {5,10,15,20,25,30}% × 10 seeds, ORB under prequential-latency, scored on clean oracle labels.
3. **Instrument the mechanism.** From `orb.trace`, extract: boost factor over time; effective λ received by (a) true-defective, (b) false-positive-labeled, (c) clean commits; per-class recall trajectories.
4. **The money analysis:** show that mislabeled "defective" commits receive systematically inflated λ (the boost amplifies noise), and quantify the gap between symmetric and asymmetric degradation curves at matched dose.
5. **Robustness:** repeat on ≥3 projects; report whether the mechanism is consistent.

### Ready-for-meeting checklist
- [ ] Dose-response curves: MCC & G-mean vs. dose, one line per noise model, shaded CI bands over seeds
- [ ] Mechanism figure: mean λ (or boost) received by falsely-labeled vs correctly-labeled minority instances
- [ ] Time-series exhibit: one project's prequential G-mean trajectory at 0% vs 20% noise, annotated where the model collapses
- [ ] A one-sentence causal claim you're willing to defend: "ORB's bias-corrective boost preferentially amplifies SZZ false positives, because [mechanism]"

### Presentation tips
- This is your most "scientific" chapter — present it like an experiment: hypothesis → intervention → measured mechanism → conclusion.
- Show the symmetric (control) curve first, then overlay the asymmetric curve. The *divergence* is the finding.
- Anticipated question: *"is 30% noise realistic?"* Answer: Phase 1 measured real SZZ error rates of [your number]% — the dose range brackets reality, it doesn't exaggerate it.

---

## Phase 4 — Noise-Aware ORB (≈ 5–6 weeks)

### Steps
1. **Implement incrementally, ablation-first.** Ship and test the three components separately (confidence term / loss correction / agreement check) before combining — the ablation table is then free.
2. **Hyperparameter protocol.** Fix the confidence window and min-confidence floor on a *held-out project*, never tuned on reporting projects. Document every value.
3. **Evaluation grid:** {OOB, ORB, NA-ORB ablations} × {real SZZ labels per variant, injected 20% asymmetric noise, clean oracle} × 10 seeds.
4. **The two claims to establish:** (a) recovery under noise (NA-ORB > ORB on noisy labels, with effect size), and (b) *non-degradation* on clean labels (NA-ORB ≈ ORB when noise is absent). Claim (b) is what makes the method adoptable.
5. **Compare against Song et al. (2022)'s method if implementable** — even a partial comparison preempts the obvious reviewer question.
6. **Failure analysis.** Where NA-ORB doesn't help, characterize why (cold-start? drift interacting with the confidence window?). This becomes Discussion material either way.

### Ready-for-meeting checklist
- [ ] Ablation table: 6 model configs × label sources, MCC/G-mean, mean ± sd
- [ ] Recovery curve: Phase 3's dose-response re-plotted with NA-ORB added
- [ ] Non-degradation check on clean labels (explicit, even if boring)
- [ ] Wilcoxon + Cliff's delta for the headline comparison
- [ ] Pseudocode of the final algorithm (1 slide/page)
- [ ] Honest limitations list

### Presentation tips
- Lead with the recovery curve — it visually completes the Phase 3 story.
- Present the ablation *before* the full method: "here's what each ingredient buys" is far more persuasive than "here's my big combined thing."
- If results are mixed, say so first and frame it: a rigorous characterization of *when* label-confidence signals work in streams is a contribution. Supervisors punish spin, not mixed results.

---

## Cross-cutting habits (apply to every meeting)

1. **Send a 1-page pre-read 48h before:** what I did / what I found (3 bullets) / what I need decided (max 2 decisions). Meetings where the supervisor decides things go well; meetings where they watch you scroll through plots do not.
2. **Every figure carries its thesis caption already.** You're building the document as you go, not "at the end."
3. **Version everything.** One git repo; results CSVs tagged with commit hash and seed; a `results/README` mapping every figure in your drafts to the script + commit that produced it.
4. **Keep a decision log** (date, decision, rationale, who approved). It writes your methodology chapter for you and protects you if scope questions arise at the defense.
5. **End each meeting by stating what the next checkpoint's deliverable is** and get verbal agreement — this prevents scope drift between meetings.

## Suggested timeline (adapt to your program calendar)

| Weeks | Milestone |
|---|---|
| 1–2 | Kickoff, environment + data acquisition, pyszz working on one repo |
| 3–6 | Phase 1 complete → **Meeting 1** |
| 7–11 | Phase 2 complete → **Meeting 2**; start drafting Ch. 2 & 4 in parallel |
| 12–15 | Phase 3 complete → **Meeting 3**; Ch. 5 draft |
| 16–21 | Phase 4 complete → **Meeting 4**; Ch. 6–7 drafts |
| 22–26 | Full draft, revision cycles, defense prep |

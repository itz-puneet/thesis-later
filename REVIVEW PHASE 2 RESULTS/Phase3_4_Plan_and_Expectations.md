# Phases 3 & 4: Execution Plan and What to Expect

Grounded in your *measured* Phase 1/2 numbers, not the original proposal's assumptions. The provided code was installed into a clone of your repo and smoke-tested on real projects — everything below is runnable today.

---

## Installation (5 minutes)

```
codebase_noise_injection.py      -> codebase/noise/injection.py   (+ empty codebase/noise/__init__.py)
codebase_noise_aware_orb.py      -> codebase/online/noise_aware_orb.py
run_phase3_noise.py              -> experiments/run_phase3_noise.py
run_phase4_na_orb.py             -> experiments/run_phase4_na_orb.py
pip install imbalanced-learn     (optional, JITLine SMOTE already handles absence)
```
Smoke: `python -m experiments.run_phase3_noise --fast` (~30–60 min), same for phase 4.

---

## Phase 3 (≈ 3 weeks): Diagnosing learner behaviour under noise

### What the code runs

**A. Dose-response** — 4 noise profiles × 6 doses (5–30%) × seeds × projects, ORB scored on clean oracle:
- `symmetric` (control), `fp_heavy` (BSZZ bias 0.263/0.359), `mid` (RASZZ 0.181/0.562), `fn_heavy` (LSZZ 0.067/0.733) — all read from your regenerated `phase1_bias.json`.
- **Two latency arms**, and this is the part to understand deeply: under `real` latency, an injected FP flip on an unlinked commit (71% of clean commits) would *never deliver its poisoned label* — the noise silently self-filters and FP sensitivity is understated. So the **primary arm is `uniform`** (isolates noise mechanics), and the `real` arm uses `impute_fix_ts()` (empirical-latency sampling, seed-controlled) as the realism check. Write this interaction up as its own methodology paragraph — it's a genuinely non-obvious finding about how the two noise sources interact.

**B. Mechanism instrumentation** — per run, from `orb.trace`: mean boost/λ received by positive-labeled vs negative-labeled arrivals, FP/FN label rates, final bias signal. This is the evidence layer for *why* curves bend, not just that they do.

**C. Repair experiment (the chapter's strongest claim)** — on **real** BSZZ labels under real latency: {BSZZ as-is, FPs surgically removed, FNs restored, oracle}. Which repair recovers more ORB performance is a *causal* test of FP-amplification vs FN-starvation on real data — no synthetic assumptions.

### What to expect (and what each outcome means)

1. **Degradation curves will be flatter than the literature's offline noise studies** — your Phase 2 already showed real latency compresses label-source differences (53% of labels arrive late, imposing FN-like noise on *everything*). Expect the uniform-arm curves to separate profiles clearly and the real-arm curves to compress them. The *gap between arms* is itself a result: "latency masks label-quality differences."
2. **Under uniform latency, expect fn_heavy to hurt more than fp_heavy at matched dose** (minority starvation at 8.5% base rate) — but treat it as a hypothesis; your Phase 2 rerun already humbled the earlier ordering claim once.
3. **Repair experiment:** my single-project smoke run (commons-codec, 1 seed) showed FP-repair ≈ FN-repair ≈ BSZZ, oracle *worst* — expect wild per-project variance like this; small projects have so few delivered positives that repairs barely register. Aggregate over all 21 × 10 seeds and report per-project heterogeneity honestly. If aggregate FN-repair > FP-repair, the starvation story wins; the reverse resurrects boost-amplification; a wash means latency dominates both — every branch is a publishable answer.
4. **Meeting-3 checklist:** dose curves per profile with CI bands (both arms), the two-arm compression figure, repair bar chart with paired tests, and one written causal sentence you'll defend.

---

## Phase 4 (≈ 5 weeks): Noise-Aware ORB

### Design changes from the original proposal (forced by your data)

1. **A RESCUE path was added, and it's likely where the gains live.** The original design only *damped* suspicious positive labels — that fights FP noise, the smaller measured error mass. Your Phase 1 shows FN rates of 0.36–0.73 and your latency data adds 53% late arrivals: the dominant failure is defect labels *missing or late*, not false alarms. The rescue path trains high-confidence "clean"-labeled arrivals as low-weight provisional positives. Ablate damp-only / rescue-only / both — the ablation IS the chapter.
2. **Loss correction demoted to a capped ablation arm.** With measured ρ₀+ρ₁ of 0.62 (BSZZ) to 0.80 (LSZZ), vanilla Natarajan weights are 3–5× and unstable; the implementation caps at 2.0 and defaults OFF. Tell your supervisor this as a decision made from measurement.
3. **Pre-registered headline tests** (already coded in the runner, so there's no post-hoc fishing): H1 = NA(damp+rescue) vs ORB on BSZZ; H2 = same on LSZZ; plus a **non-degradation check on oracle** — a significant drop there kills adoptability regardless of H1/H2.

### What to expect

- **My smoke run says tuning is the real work, honestly:** on commons-net (1 seed), NA(rescue) was *identical* to ORB — the rescue path never fired because the class-1 confidence window never reached warmup (30 positive arrivals) on a small project. And NA(damp) *hurt* on clean oracle labels (damping legitimate positives early). Neither is a bug; both are the expected cold-start behaviour of confidence estimators — the exact failure mode flagged in the alternatives doc. Your tuning agenda, in order: (1) `warmup` and `confidence_window` sized to per-project positive counts (consider warmup as a fraction of arrivals, not a constant); (2) `rescue_margin` sweep {1.1, 1.25, 1.5}; (3) `min_confidence` floor for the damp path. Tune on 2–3 held-out projects, freeze, then run the grid.
- **Expected outcome pattern if the method works:** rescue drives gains on FN-heavy conditions (LSZZ, injected_fn20), damp adds a little on BSZZ, oracle stays flat. Expected pattern if it doesn't: gains vanish under real latency because imputed/late confidence signals are too weak — in which case pivot to **Backup A (filtering-ORB)** for the damp side and keep rescue (it's threshold-simple and doesn't need calibrated probabilities). Either way Phases 1–3 stand alone, and a characterized negative is a defensible chapter.
- **Power:** ORB's per-project seed σ ≈ 0.026 MCC (measured from your Phase 2), so with 21 project-pairs and 10 seeds, effects of ~0.03+ MCC are detectable at the project-paired Wilcoxon level. Don't chase anything smaller.

### Timeline

| Weeks | Milestone |
|---|---|
| 1 | Install modules; Phase 3 `--fast`; fix_ts imputation sensitivity for Finding 3a (cheap, closes the confound) |
| 2–3 | Full Phase 3; figures; **Meeting 3** (dose curves + repair verdict + Phase 4 design sign-off incl. rescue path & capped LC) |
| 4 | Phase 4 hyperparameter tuning on held-out projects; freeze protocol |
| 5–7 | Full Phase 4 grid (use your GitHub Actions runner — the grid is 7 conditions × 6 models × 21 × 10); headline tests |
| 8 | **Meeting 4**: ablation table, recovery curves, non-degradation check, limitations |
| 9+ | Write Ch. 6–7 from the CSVs (every figure already has a generating script — keep that invariant) |

One last framing point: you now have a complete causal chain — measured noise (P1) → measured downstream distortion (P2) → mechanism isolation (P3) → targeted intervention (P4) — with the intervention's design *derived from* the measurements (rescue from FN dominance, capped LC from measured ρ sums, dual latency arms from the self-filtering interaction). That derivation story is what elevates this from "we tried a method" to a thesis.

# Phase 3 & Phase 4 — Execution Plan

**Status:** code installed and smoke-tested against `master`. No Phase 3 or Phase 4 experiment has been run yet.
**Reading order:** `Phase1_Phase2_Master_Results.md` for what Phases 1–2 established, then this.

| Installed | Location |
|---|---|
| Noise-Aware ORB (Phase 4 model) | `codebase/online/noise_aware_orb.py` |
| Phase 3 runner (dose-response, mechanism, repair) | `experiments/run_phase3_noise.py` |
| Phase 4 runner (ablation grid) | `experiments/run_phase4_na_orb.py` |
| Phase 3/4 figure pipeline | `scripts/make_phase34_figures.py` |
| Noise injection primitives (pre-existing) | `codebase/noise/injection.py` |

---

## ⚠️ Correction carried forward from Phase 2

The review package these files arrived in was written against commit `05a8b3a` and led with this claim:

> *"oracle-trained ORB significantly beats ORB trained on every refined variant — but NOT BSZZ, the crudest, most FP-heavy, highest-recall variant. Under verification latency, what hurts an online learner is not the false positives a noisy labeler adds, but the true positives a precise labeler withholds. Lead your next supervisor meeting with it."*

**That claim does not survive.** It rested on the *terminal fading* prequential estimator, which summarises only the last ~100 commits of each stream and carries roughly twice the project-level variance of the time-averaged estimator (0.092 vs 0.051). Under the time-averaged value — the standard Gama estimator, and the one now treated as primary — oracle beats **all six** variants including BSZZ:

| Oracle vs | Δ MCC | Holm p | Cliff's δ | Recall of variant |
|---|---|---|---|---|
| LSZZ | +0.0388 | 0.0025 | 0.392 | 0.267 |
| **BSZZ** | **+0.0392** | **0.0004** | 0.451 | **0.641** |
| RASZZ | +0.0575 | 0.0004 | 0.669 | 0.438 |
| AGSZZ | +0.0605 | 0.0009 | 0.655 | 0.467 |
| MASZZ | +0.0617 | 0.0003 | 0.674 | 0.482 |
| RSZZ | +0.0655 | 0.0001 | 0.710 | 0.300 |

**And the gap does not track recall** — correlation between the oracle-vs-variant gap and the variant's recall is **−0.18**. LSZZ (lowest recall, 0.267) and BSZZ (highest, 0.641) have almost identical gaps. So "FN-starvation confirmed at the label-source level" is *not* established by Phase 2.

**What this means for Phase 3.** FN-dominance is now a **hypothesis to test**, not a result to corroborate. That is a cleaner scientific position than the review implied — Phase 3 is a genuine test rather than a confirmation exercise. Do not pre-commit to the direction in your meeting; §Step 2 below states the question neutrally.

---

## Step 0 — Done

Files installed at the locations in the table above. Two fixes were needed on the way in:

1. **`NA(rescue)` was inert.** The confidence windows were only populated inside `_confidence()`, which was gated on `use_damp`. With `use_damp=False`, `win[1]` stayed empty, `_class_threshold(1)` always returned `None`, and no commit was ever rescued — making the rescue-only ablation arm byte-identical to plain ORB. Window maintenance is now unconditional; the damping switch only decides whether the confidence is *used*. Verified: on commons-math/LSZZ, `NA(rescue)` now performs 1,025 rescues and reaches MCC_avg **+0.1355** against ORB's **+0.0900**.
2. **Staleness guard switched from mtimes to content hashes.** As the review noted, mtime comparison false-positives on fresh clones and CI checkouts where git assigns checkout-time mtimes. `load_or_build_dataset()` now compares the label-file SHA-256s recorded in `phase2_commits.provenance.json` against the files on disk. Verified both ways: a clean cache loads without complaint, and tampering with a stored digest raises.

Also from the review's nit list: `support_codebase/` no longer exists, and `scripts/generate_report.py` has been retired in favour of `Phase1_Phase2_Master_Results.md` + `scripts/make_figures.py`.

**Exit criterion met:** `python -m experiments.check_label_consistency` passes.

## Step 1 — Phase 3 fast pass (½ day)

```bash
python -m experiments.run_phase3_noise --fast
python scripts/make_phase34_figures.py --phase 3
```

**Exit:** dose curves render, repair bars render, no crashes. Skim shapes only — **do not interpret 3-seed/5-project numbers.**

## Step 2 — Phase 3 full run (2–4 days compute — use the Actions runner)

Full grid: 21 projects × 10 seeds × 4 profiles × 6 doses × 2 latency arms, plus 21 × 10 × 4 repair runs. Wire it into `.github/workflows/phase2_experiment.yml` the way Phase 2 is, and run it there rather than locally.

**The three questions Phase 3 must answer:**

1. **Dose-response (uniform arm).** Does `fn_heavy` noise degrade ORB faster than `fp_heavy` at matched dose? `phase3_slopes.csv` gives MCC-per-10%-dose per profile. *Stated neutrally on purpose* — see the correction above; Phase 2 does not predict the answer.
2. **Compression.** Are real-arm slopes flatter than uniform-arm slopes? This is the quantitative form of "latency masks label quality." Phase 2 supports this one: 53% of defect labels arrive after the W=90d window, imposing FN-like noise on every source regardless of quality.
3. **Repair verdict.** FN-restoration vs FP-removal on real BSZZ labels; `phase3_repair_stats.csv` carries the paired tests. If FN-repair > FP-repair, Phase 3 establishes FN-dominance through a controlled design — which Phase 2 could not.

**Report both prequential estimators**, as Phase 2 now does. The runner records `mcc` and `mcc_avg`; treat `mcc_avg` as primary. This matters most here: dose-response slopes on the noisier terminal estimator will be harder to separate.

## Step 3 — Supervisor Meeting 3 (before touching Phase 4)

Bring exactly five artifacts:
1. The `label_source_gap` table **under both estimators**, with the estimator disagreement explained (`Phase2_Supervisor_Explanation_Guide.md` §7 has the wording).
2. The arm-compression figure.
3. The repair bar chart with paired stats.
4. The dose-slope table.
5. The one-paragraph Phase 4 design: rescue-path rationale, capped loss-correction decision, and pre-registered H1/H2/non-degradation.

**Exit:** sign-off on the Phase 4 protocol *before* running it. That is what makes "pre-registered" true.

## Step 4 — Phase 4 tuning, on held-out projects only (2–3 days)

Pick 3 projects spanning sizes (smallest, median, largest by positive count), **exclude them from all reporting**, and sweep only on them:

- `warmup` — {30, 50, or 5% of arrivals}. Confirmed necessary: on commons-scxml (544 commits) the rescue path fires **zero** times with `warmup=30`, because fewer than 30 class-1 labels ever deliver under real latency. A fraction-of-arrivals rule is the obvious fix.
- `rescue_margin` {1.1, 1.25, 1.5}; `rescue_weight` {0.3, 0.5}
- `min_confidence` {0.05, 0.2} — the damp path hurt clean labels in smoke tests. In the install smoke test `NA(damp)` scored **below** plain ORB on commons-scxml (+0.1414 vs +0.1911), so a higher floor or a damp-warmup is the first thing to try.

Freeze one config. Record the sweep in the decision log.

**Exit:** frozen hyperparameters committed to `codebase/config.py` as `NA_ORB_CONFIG`, with the held-out project names listed beside them.

## Step 5 — Phase 4 full grid (3–5 days compute)

```bash
python -m experiments.run_phase4_na_orb
python scripts/make_phase34_figures.py --phase 4
```

7 conditions × 6 models × 18 reporting projects × 10 seeds. Checkpointed per project, so Actions restarts are safe.

**Exit — read `phase4_headline_tests.csv` first:** H1 (vs ORB on BSZZ), H2 (vs ORB on LSZZ), non-degradation (oracle).

| H1 | H2 | Non-degr. | Meaning / action |
|---|---|---|---|
| ✓ | ✓ | flat | Full win — write Ch. 7 as designed |
| ✗ | ✓ | flat | Rescue works, damp doesn't — report the ablation honestly |
| ✓/✗ | ✓/✗ | **drop** | Adoptability fails — raise `min_confidence`/warmup, rerun the oracle arm only; if it persists, the damp path goes to Backup A (filtering) |
| ✗ | ✗ | flat | Characterised negative: confidence signals too weak under latency. Phases 1–3 stand alone; Ch. 7 becomes "when and why label-confidence fails in streams" |

## Step 6 — Meeting 4 + write-up (2–3 weeks)

Ablation table, paired scatter, recovery framing against Phase 3's dose curves, limitations (fix_ts coverage confound + imputation bound, single benchmark family, LC cap, and **the estimator-dependence of the Phase 2 BSZZ comparison**). Then Ch. 6–7 straight from the CSVs.

---

## Design notes on the installed code

**Noise-Aware ORB** extends the validated ORB with two independently switchable defences:

- **DAMP** (Confident-Learning-style, streaming): each arriving label gets a confidence `c ∈ (0,1]` from running per-class self-confidence thresholds. `c` modulates **only the boost amplification**, so a suspicious minority label falls back to plain OOB weight rather than being amplified. Targets FP noise.
- **RESCUE**: when a commit arrives labelled *clean* but the ensemble confidently disagrees, it is trained as a provisional positive at reduced weight. Targets FN noise and late-arriving labels. Motivated by measured FN rates of 0.36–0.73 and the 53% of labels arriving after the window.
- **Capped loss correction** (optional): Natarajan-style reweighting using the Phase 1 ρ₀/ρ₁, bounded by `lc_cap` to avoid the blow-up when ρ₀ + ρ₁ → 1.

`ablation_grid()` returns the six-model set — OOB, ORB, NA(damp), NA(rescue), NA(damp+rescue), NA(damp+rescue+lc) — so every arm is attributable.

**Phase 3 runner** injects noise into `label_oracle` under four profiles (symmetric control, FP-heavy/BSZZ, mid/RASZZ, FN-heavy/LSZZ) at doses 5–30%, in two latency arms:
- **uniform** — PRIMARY, isolates noise mechanics from latency effects
- **real** — sensitivity arm, uses `impute_fix_ts()` so injected FP flips do not silently self-filter. Without imputation, a clean commit flipped to "defective" usually has no `fix_ts`, so its poisoned label never reaches training and the injected noise disappears. This two-arm design exists specifically to close that trap.

---

## Standing rules

- **Never interpret `--fast` numbers.** They exist to catch crashes.
- Every reported figure regenerable by one script plus one commit hash.
- Anything surprising gets a per-project breakdown before it gets a sentence in the thesis.
- The pre-registered tests are the only Phase 4 hypothesis tests; everything else is exploratory and labelled as such.
- **Always name the prequential estimator** when quoting an MCC. The Phase 2 correction above is what happens when you do not.

---

## Smoke-test provenance

The Phase 3/4 code was executed against this repo before being committed, not merely reviewed:

| Check | Result |
|---|---|
| All four files import against current APIs | ✅ |
| `ablation_grid` runs end-to-end on real data | ✅ 6 models, commons-scxml + commons-math |
| Rescue path fires after the fix | ✅ 1,025 rescues on commons-math |
| Noise injection | ✅ symmetric 20% → 122/544 flips; asymmetric(LSZZ) → 310/544 |
| Consistency gate after install | ✅ passes |

Earlier smoke results reported by the review at `05a8b3a` (single seed, single project — **not results**): Phase 3 repair ran on commons-codec; Phase 4 `NA(damp+rescue)` reached MCC 0.161 vs ORB 0.067 on commons-codec/LSZZ/seed 42.

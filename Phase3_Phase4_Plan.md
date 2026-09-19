# Phase 3 & Phase 4 — Execution Plan

**Status:** Phase 3 is wired and smoke-tested end to end; the full grid has **not** been run yet. Phase 4 is installed but not wired.
**Trigger:** `.github/workflows/phase3_experiment.yml` (`stage=smoke` | `full`).
**Reading order:** `Phase1_Phase2_Master_Results.md` for what Phases 1–2 established, then this.

| Installed | Location |
|---|---|
| Noise-Aware ORB (Phase 4 model) | `codebase/online/noise_aware_orb.py` |
| Phase 3 runner (dose-response, mechanism, repair) | `experiments/run_phase3_noise.py` |
| Phase 4 runner (ablation grid) | `experiments/run_phase4_na_orb.py` |
| Phase 3/4 figure pipeline | `scripts/make_phase34_figures.py` |
| Noise injection primitives (pre-existing) | `codebase/noise/injection.py` |
| Phase 3 CI workflow | `.github/workflows/phase3_experiment.yml` |

---

## ⚠️ Correction carried forward from Phase 2

The review package these files arrived in was written against commit `05a8b3a` and led with this claim:

> *"oracle-trained ORB significantly beats ORB trained on every refined variant — but NOT BSZZ, the crudest, most FP-heavy, highest-recall variant. Under verification latency, what hurts an online learner is not the false positives a noisy labeler adds, but the true positives a precise labeler withholds. Lead your next supervisor meeting with it."*

**That claim does not survive.** It rested on the *terminal fading* prequential estimator, which summarises only the last ~100 commits of each stream and carries roughly twice the project-level variance of the time-averaged estimator (0.092 vs 0.051). Under the time-averaged value — the one now treated as primary, preferred on measured variance rather than as a canonical standard — oracle beats **all six** variants including BSZZ:

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

> **Phase 3 has now run, and the hypothesis is refuted.** The controlled repair
> experiment on real BSZZ labels finds that removing false positives recovers
> **+0.0402 MCC** (17/21 projects, global Holm 0.0019) while restoring false
> negatives recovers **nothing** (−0.0012, CI [−0.0093, +0.0080], 8/21). See
> §Phase 3 results below. The review package's "FN-starvation" framing should
> not appear anywhere in the thesis.
>
> **The addendum then qualified this — read §Phase 3 addendum before quoting the
> number.** At *matched label mass* the FP advantage disappears, so this is a
> claim about how many errors SZZ makes, not about which error is worse per
> label.

---

## Step 0 — Done

Files installed at the locations in the table above. Two fixes were needed on the way in:

1. **`NA(rescue)` was inert.** The confidence windows were only populated inside `_confidence()`, which was gated on `use_damp`. With `use_damp=False`, `win[1]` stayed empty, `_class_threshold(1)` always returned `None`, and no commit was ever rescued — making the rescue-only ablation arm byte-identical to plain ORB. Window maintenance is now unconditional; the damping switch only decides whether the confidence is *used*. Verified: on commons-math/LSZZ, `NA(rescue)` now performs 1,025 rescues and reaches MCC_avg **+0.1355** against ORB's **+0.0900**.
2. **Staleness guard switched from mtimes to content hashes.** As the review noted, mtime comparison false-positives on fresh clones and CI checkouts where git assigns checkout-time mtimes. `load_or_build_dataset()` now compares the label-file SHA-256s recorded in `phase2_commits.provenance.json` against the files on disk. Verified both ways: a clean cache loads without complaint, and tampering with a stored digest raises.

Also from the review's nit list: `support_codebase/` no longer exists, and `scripts/generate_report.py` has been retired in favour of `Phase1_Phase2_Master_Results.md` + `scripts/make_figures.py`.

**Exit criterion met:** `python -m experiments.check_label_consistency` passes.

### Two further defects found when Phase 3 was actually wired up

3. **The runner recorded only the terminal estimator.** `dose_response()` and
   `repair_experiment()` wrote `mcc=r["mcc"]` and nothing else, even though
   `prequential_latency()` has returned `mcc_avg`/`gmean_avg` since the Phase 2
   remediation. Every dose curve, every slope and every repair test would have
   been computed on the *terminal fading* value alone — the estimator whose
   roughly-doubled variance produced the withdrawn BSZZ claim at the top of this
   document. Phase 3 would have reproduced the exact error Phase 2 was corrected
   for. Both estimators are now recorded and every artefact carries both.

4. **The repair tests were a bare Wilcoxon statistic** — no effect size, no
   confidence interval, no multiplicity correction. Phase 2's review required
   paired effect sizes and Holm correction; `repair_stats()` now reports
   matched-pairs rank-biserial, Hodges–Lehmann with a bootstrap CI, and Holm
   both within estimator and globally, matching the Phase 2 standard.

**Also corrected:** `.github/workflows/phase2_experiment.yml` set
`timeout-minutes: 420`. GitHub-hosted runners hard-cap a job at 360 minutes, so
that value was silently unreachable. Now 350.

## Step 1 — Phase 3 fast pass — DONE

```bash
python -m experiments.run_phase3_noise --fast
python scripts/make_phase34_figures.py --phase 3
```

Ran in **36 s** on 5 projects × 3 seeds. Dose curves, repair bars and the paired
statistics table all render. Smoke figures were deleted rather than committed, so
5-project output can never be mistaken for a result.

Two defects were fixed on the way through — see §Step 0.

## Step 2 — Phase 3 full run — DONE (17 minutes, not 2–4 days)

Full grid: 21 projects × 10 seeds × 4 profiles × 6 doses × 2 latency arms, plus
21 × 10 × 4 repair runs.

**The "2–4 days" estimate in the original plan was wrong.** Measured cost is
**≈ 4 s per project-seed** (one ORB prequential pass over the median 1,086-commit
project takes 0.07 s), which puts the whole grid around twenty minutes. No
sharding, no per-project checkpointing and no matrix build are needed; the
single-job workflow is sufficient.

Trigger `.github/workflows/phase3_experiment.yml` with `stage=full`. It rebuilds
the same data chain as Phase 2 and runs the **same label-consistency gate before
any compute** — which matters more here than in Phase 2, because Phase 3 injects
noise calibrated from `phase1_bias.json`. If that file and the dataset disagree,
every dose on every curve is calibrated against labels the experiment is not
using.

**The three questions Phase 3 must answer:**

1. **Dose-response (uniform arm).** Does `fn_heavy` noise degrade ORB faster than `fp_heavy` at matched dose? `phase3_slopes.csv` gives MCC-per-10%-dose per profile. *Stated neutrally on purpose* — see the correction above; Phase 2 does not predict the answer.
2. **Compression.** Are real-arm slopes flatter than uniform-arm slopes? This is the quantitative form of "latency masks label quality." Phase 2 supports the *premise* — 53% of defect labels arrive after the W=90d window — but note that Phase 2's attempt to size the latency effect was withdrawn as unidentified (see `Phase1_Phase2_Master_Results.md` §7). Phase 3's uniform-vs-real arms are a cleaner test of compression than anything Phase 2 produced, because the learner is held fixed by construction.
3. **Repair verdict.** FN-restoration vs FP-removal on real BSZZ labels; `phase3_repair_stats.csv` carries the paired tests. If FN-repair > FP-repair, Phase 3 establishes FN-dominance through a controlled design — which Phase 2 could not.

**Report both prequential estimators**, as Phase 2 now does. The runner **now** records `mcc` and `mcc_avg` — it did not when this plan was written, see §Step 0 — and `mcc_avg` is primary. This matters most here: dose-response slopes on the noisier terminal estimator will be harder to separate.

## Phase 3 results — run `34912399232`, commit `1efdbe8`

Full grid: 21 projects x 10 seeds x 4 profiles x 6 doses x 2 latency arms
(10,080 dose-response records) plus 21 x 10 x 4 repair runs. Wall clock **17
minutes**. Label-consistency gate passed before compute.

### Q3 — Repair verdict: FP-dominance, not FN-dominance

Real BSZZ labels, paired at project level (n = 21), primary estimator `mcc_avg`:

| Comparison | Hodges-Lehmann | 95% CI | rank-biserial | Projects | Holm (global) |
|---|---|---|---|---|---|
| **BSZZ with FPs removed vs BSZZ** | **+0.0402** | [+0.0217, +0.0520] | +0.844 | **17/21** | **0.0019** |
| BSZZ with FNs restored vs BSZZ | −0.0012 | [−0.0093, +0.0080] | −0.091 | 8/21 | 1.000 |
| **FP-repair vs FN-repair** | **+0.0413** | [+0.0180, +0.0575] | −0.732 | 17/21 | **0.0151** |
| Oracle vs BSZZ | +0.0270 | [+0.0084, +0.0459] | +0.628 | 16/21 | 0.0608 |

Removing false positives recovers performance; restoring false negatives
recovers nothing, and that null has a tight interval — it is an informative
null, not low power. FP-repaired BSZZ (0.0962) even outscores the oracle
(0.0835): under verification latency, precision beats recall for ORB.

**State the limitation with the result.** The repair conditions are not
error-matched. BSZZ carries 6,565 false positives against 837 false negatives,
so FP-repair touches roughly eight times more labels. The defensible claim is
*"on real BSZZ labels, in the quantities these errors actually occur, FP
removal is what recovers performance"* — not that one FP outweighs one FN.

**Under the terminal estimator every repair comparison is null** (all Holm
p = 1.000, all CIs spanning zero). This is why the runner had to be fixed to
record both estimators before the run; on the terminal value alone Phase 3
would have produced a chapter of nulls.

### Q2 — Compression: WITHDRAWN as stated; the addendum reverses it

The original conclusion read: *"real-arm and uniform-arm slopes are within noise
of each other, so the latency-masking premise does not survive."* **That was
wrong, and the error was in the design, not the arithmetic.** The `uniform` arm
delays *every* label by the full 90-day window; it removes schedule variation,
not delay. Comparing it against the `real` arm tests sensitivity to the arrival
*schedule* and cannot test masking at all. See §Phase 3 addendum, Q2.

### Q1 — Dose-response, with a design caveat that must be stated

Non-degenerate fit, `mcc_avg`, per 10% dose:

| Profile | real | uniform |
|---|---|---|
| fn_heavy | −0.0363 | −0.0370 |
| mid | −0.0247 | −0.0225 |
| symmetric | −0.0222 | −0.0177 |
| fp_heavy | −0.0204 | −0.0197 |

FN-heavy noise degrades ORB fastest at matched dose — which sits oddly beside
the repair verdict, and the reason is the dose parameterisation, not a
contradiction. **Dose is the expected flipped fraction over all commits**, so
at matched dose the FN-heavy profile strips far more of the 8.5% minority
class. `phase3_minority_survival.csv` measures it:

| Profile | 0.05 | 0.10 | 0.15 | 0.20 | 0.25 | 0.30 |
|---|---|---|---|---|---|---|
| fn_heavy | 0.720 | 0.440 | 0.183 | 0.056 | 0.010 | **0.000** |
| fp_heavy | 0.938 | 0.868 | 0.804 | 0.739 | 0.669 | 0.601 |

At dose 0.30 the FN-heavy arm has **no positive labels left at all**. Slopes are
therefore fitted only on cells retaining positives, and the full-range fit is
kept beside them under `scope="all_doses"`. Cells at dose 0.20-0.25 still retain
only 5.6% and 1.0% of positives, so a stricter re-fit is defensible; the
survival table is committed precisely so anyone can redo it. The ordering is
unchanged under every criterion tried.

**The two results are reconciled by the denominator, and the reconciliation is
the interesting part:** per *label flipped*, FN noise is more damaging, because
positives are scarce; per *error actually present in real SZZ output*, FP noise
dominates, because BSZZ produces eight times more of them. Both belong in the
chapter.

---

## Phase 3 addendum — run `35306571919`, commit `3d1a6f1`

Four causal conditions from the supervisor's `Deep_Review_Phase3.md`, plus a
pre-declared equivalence test. **Two of the three headline Phase 3 conclusions
are changed by it.** Implementation notes and the four corrections made to the
shipped script are in the module docstring of `experiments/run_phase3_addendum.py`.

### A. Error-matched repair — the FP advantage is a MASS effect

BSZZ carries 6,565 false positives against 837 false negatives. Correcting the
same label mass on both sides:

| Contrast | HL | 95% CI | Projects | Holm (family) |
|---|---|---|---|---|
| FP-repair (matched, ~40/project) vs BSZZ | +0.0024 | [−0.0045, +0.0089] | 11/21 | 0.864 |
| FP-repair (matched) vs FN-repair (all) | +0.0050 | [−0.0093, +0.0176] | 14/21 | 0.864 |
| *(reference)* FP-repair (all 6,565) vs BSZZ | +0.0402 | [+0.0217, +0.0520] | 17/21 | 0.0010 |

**Removing 837 false positives does nothing. Removing 6,565 recovers +0.04.**
At equal corrected mass the two error types are statistically indistinguishable.

The marginal-value curves agree: FP-repair is roughly linear at
**+0.147 MCC per 1,000 labels corrected**, so the ~40 FPs per project that
FN-repair could ever match predicts ≈ +0.006 — within noise of the +0.0024
measured. Nothing is inconsistent; the effect is simply proportional to volume.

**What survives and what does not.** "SZZ's false positives are what cost the
learner performance, because there are eight times more of them" — supported.
"A false positive is individually more harmful than a false negative" — **not
supported**, and it must not be written. The supervisor's §1.1 was right that a
flag is not a control.

### C. Delivery ceiling — the FN null is about content, not scheduling

Each ceiling condition against its own anchor, so the contrast isolates the
restoration rather than the acceleration:

| Contrast | HL | 95% CI | Projects |
|---|---|---|---|
| FN-repair immediate vs BSZZ immediate | +0.0037 | [−0.0032, +0.0106] | 12/21 |
| FN-repair at t+W vs BSZZ at t+W | −0.0016 | [−0.0073, +0.0043] | 6/21 |
| BSZZ immediate vs BSZZ realistic | +0.0140 | [−0.0006, +0.0334] | 14/21 |

**Even delivered instantly, restoring the false negatives recovers nothing.**
Three independent delivery regimes, three nulls. §1.2's alternative explanation
— that the labels cannot arrive in time to matter — is ruled out. The claim is
about the content of those labels, not their schedule.

### TOST — the null is now evidence of absence

Pre-declared margin ±0.02 MCC (half the measured FP-repair effect), Wilcoxon
TOST on the original FN-repair contrast: **p = 0.0008, n = 21, equivalent.**
FN-restoration is statistically *equivalent to no repair*. This is the
affirmative form the conclusion needs, and it is what §1.4 asked for.

### D. No-latency arm — latency DOES compress, by roughly a third

`regimes.py` gained a real `latency_mode="none"` that delivers every label
immediately after scoring. Dose slopes, `mcc_avg` per 10% dose, non-degenerate
cells:

| Profile | **none** | uniform | real |
|---|---|---|---|
| fn_heavy | **−0.0553** | −0.0370 | −0.0363 |
| mid | **−0.0384** | −0.0225 | −0.0247 |
| fp_heavy | **−0.0313** | −0.0196 | −0.0205 |
| symmetric | **−0.0286** | −0.0177 | −0.0222 |
| *fn_heavy − fp_heavy separation* | **−0.0240** | −0.0174 | −0.0158 |

Slopes are ~50% steeper without latency and the profiles separate ~40% more
widely. Mean `mcc_avg` at the lowest dose is 0.0995 with no latency against
0.0596 uniform and 0.0525 real. **Verification latency both lowers the ceiling
and flattens the response to label quality** — the masking premise holds. The
supervisor registered this prediction in §1.3 and it was confirmed.

### The mechanism figure

`fig_p3_lambda_compensation.png`, with `phase3_lambda_compensation.csv`.
ORB's Poisson boost rate to positive-labelled arrivals is a near-perfect
inverse of how many positives the stream still delivers: **Spearman ρ = −1.000**
across profiles at matched dose, −0.70 to −0.87 within each.

State it as scarcity, not as FN compensation:

> **ORB's boost compensates for positive-label scarcity, not for false
> negatives — it cannot tell the difference.** It amplifies whatever positives
> arrive, and amplifies them hardest exactly when they are rarest. That is why
> false-positive mass is what the learner cannot survive: the mechanism that
> corrects imbalance is the mechanism that magnifies wrong positives.

One correction to the earlier write-up of the dose grid. At `fn_heavy` dose 0.30
the stream does **not** run out of positive labels — it carries ~204 of them,
**every one false**, because the LSZZ profile's ρ₀ = 0.067 also flips negatives
upward and the majority class is large enough to supply plenty. The learner in
that regime is poisoned, not starved, and it receives the *highest* boost rate
in the entire grid. `n_pos_retained` (true positives kept) is what goes to zero;
`n_pos_noisy` rises.

### Risk this creates for Phase 4

Because λ is a strict inverse of delivered positive supply, **`fp_filter` fights
its own mechanism**: every positive it suppresses lowers the delivered positive
rate, which raises λ for the survivors. With filtered positives never learned,
their p₁ stays low and they are filtered again. Register this as a named risk
with an instrumented prediction before the grid runs, not after.

---

## Step 3 — Supervisor Meeting 3 (before touching Phase 4)

Bring exactly five artifacts:
1. The `label_source_gap` table **under both estimators**, with the estimator disagreement explained (`Phase2_Supervisor_Explanation_Guide.md` §7 has the wording).
2. The arm-compression figure.
3. The repair bar chart with paired stats.
4. The dose-slope table.
5. The one-paragraph Phase 4 design: rescue-path rationale, capped loss-correction decision, and pre-registered H1/H2/non-degradation.

**Exit:** sign-off on the Phase 4 protocol *before* running it. That is what makes "pre-registered" true.

## Step 3b — Phase 4 RE-REGISTERED (v2), commit pending

Done before any Phase 4 run, so nothing is chosen with knowledge of a result.
The full rationale is the module docstring of `experiments/run_phase4_na_orb.py`.

| | v1 (retired unrun) | v2 |
|---|---|---|
| Headline | NA(damp+rescue) | **NA(fp_filter)** |
| H2 source | LSZZ (FN-heavy) | **MASZZ, AGSZZ** (mid-FP) |
| Rescue | headline component | **demoted to a registered probe**, predicted ≤ 0 |
| New | — | **H3**: gain rank-correlates with the variant's FP count |
| New | — | **R1**: λ self-antagonism, with `rate_update` as the arm |
| Estimator | `mcc` (terminal) | **`mcc_avg`**, both recorded |
| Stats | `wilcoxon_with_cliffs` (unpaired δ) | `paired_effect` + Holm |

**H3 is the sharpest test in Phase 4.** Because Phase 3 showed the effect is
volume-driven, the benefit of filtering should track how many false positives
the label source actually contains — a predicted *ordering* over six variants
with counts fixed in advance (BSZZ 6565, MASZZ 5030, AGSZZ 4786, RASZZ 4531,
RSZZ 2316, LSZZ 1665), which is far harder to satisfy by chance than a binary
"filter beats ORB".

**Held-out projects: `commons-scxml`, `opennlp`, `commons-math`** — excluded
from every reported number, because the `fp_filter` defaults were chosen by
looking at them.

**Two implementation findings already recorded in the model docstring.** The
review's running-quantile decision rule is degenerate on this corpus: the
ensemble's members agree almost completely, p1 is bimodal at 0 and 1, and the
10th percentile of a trailing window is 0.0000 in nearly every segment, so a
strict comparison never fires — 0 of 75 positive arrivals on opennlp/BSZZ. A
fixed threshold is the default instead, with the quantile retained for
comparison. And `tau = 0.5` is catastrophic on both held-out projects tried
(filter rate 96–97%, MCC driven negative); `tau = 0.25` roughly doubled ORB's
`mcc_avg` on both. Neither observation may be quoted as a result.

## Step 4 — Phase 4 tuning, on the three held-out projects only (2–3 days)

Sweep only on `commons-scxml`, `opennlp`, `commons-math`:

- `mode` {fixed, quantile} and `tau` {0.15, 0.25, 0.35} — the dominant knob.
- `eps` {0, 0.1} — whether a suspected FP is discarded or residually weighted.
- `min_pos_for_threshold` {20, 30, 50} — warm-up counted in *positive labels*,
  which is the scarce currency: under real latency some projects deliver fewer
  than 30 positives in an entire stream, and the filter is correctly inert
  below that.
- `rate_update` {observed, suppress} — this is R1, not a hyperparameter. Record
  it; do not optimise it.

Acceptance bar is the ND gate, not H1: a filter that wins on BSZZ and degrades
the oracle arm is not adoptable.

### Step C results — run `35317549121`, frozen in `codebase/config.py`

42 configurations on the registered arm; **24 passed the ND gate, and every
one of them uses the quantile rule.** All fixed-threshold configurations
failed, several catastrophically.

```python
FP_FILTER_CONFIG = {"mode": "quantile", "q": 0.30, "eps": 0.1,
                    "min_pos_for_threshold": 30, "rate_update": "observed"}
NA_ORB_HELD_OUT_PROJECTS = ("commons-scxml", "opennlp", "commons-math")
```

Held-out gains — **tuning-set numbers, never quotable as findings**: BSZZ
+0.0451, MASZZ +0.0232, LSZZ +0.0131, oracle +0.0072, filter rate on BSZZ 0.24.
`q = 0.30` is an interior optimum, not a grid edge: extending to 0.40 and 0.50
lowered the BSZZ gain to 0.0402 and 0.0288.

**Why every fixed-threshold configuration failed — put this in Chapter 7.**
On the oracle arm, where every positive is correct and there is nothing to
remove, `tau = 0.35` suppressed 57% of positives and cost **−0.0989** MCC. A
fixed confidence threshold filters however many positives the model happens to
be unsure about, with no reference to how many false positives the source
contains. It cannot distinguish *"this label is probably wrong"* from *"my
model has not learned this pattern yet"*. The quantile rule removes about `q`
by construction, so its worst case is bounded. **The intervention has to be
bounded in size, not in confidence** — which is a design lesson beyond this
model.

**The filter is only partly adaptive**, and this is the honest limitation.
At the frozen setting it filters 24% of positives on BSZZ (81% of whose flags
are false) against 12% on the oracle (0% false) — twice as often where the
noise is, but still discarding roughly one correct label in eight when there
is nothing to find. That residual cost is what the ND gate measures, and why
the gate rather than H1 is the acceptance bar.

### R1 — the registered prediction FAILED

`mean(observed − suppress) = −0.0020`, favouring `observed` in only **54 of 168**
configuration-condition cells. The prediction was that suppressing positives
would lower `rate1`, raise λ for the survivors, and cost performance. λ does
rise — that mechanism is real and was measured at Spearman ρ = −1.000 — but the
*sign of its effect* is the opposite of predicted.

The coherent reading, offered as exploratory rather than established: once the
filter has removed the suspected false positives, amplifying the survivors
harder is **correct**, because the surviving positives are more trustworthy
than the stream average. Filtering and boosting compose rather than conflict.
Phase 3's account said the boost amplifies whatever arrives; the filter changes
what arrives, and the boost then does the right thing with it.

The frozen config still takes `observed`, exactly as the selection rule
declared in advance. Not tuning the R1 arm is what keeps it a test. The
difference is small (−0.0020) and close to null in either direction, so the
defensible claim is that **the prediction is not supported**, not that
`suppress` is better.

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

## Phase 4 results — run `35320110525`, commit `f70884a`

18 reporting projects (commons-scxml, opennlp and commons-math held out),
6 models x 8 label conditions x 10 seeds, at the Step C frozen configuration.

### The pre-registered verdict: ND passes, everything else does not

| Test | HL | 95% CI | Projects | p | **Holm** |
|---|---|---|---|---|---|
| **ND** oracle, non-degradation | −0.0001 | [−0.0091, +0.0081] | 5/18 | 0.807 | **PASS** |
| H1 fp_filter > ORB on BSZZ | +0.0166 | [+0.0009, +0.0328] | 12/18 | 0.054 | 0.215 ✗ |
| H2a on MASZZ | +0.0110 | [−0.0005, +0.0235] | 13/18 | 0.074 | 0.221 ✗ |
| H2b on AGSZZ | +0.0072 | [−0.0075, +0.0221] | 12/18 | 0.246 | 0.492 ✗ |
| H3 gain ~ FP count | ρ = 0.714 | — | 6 variants | 0.055 | ✗ |

**This is the plan's "characterised negative" branch.** Every confirmatory test
points the predicted way and not one reaches significance after correction. The
filter is *adoptable* — it does not damage clean labels, which is the bar that
actually gates deployment — but it is **not demonstrated to work**. Write it
that way; the direction-consistency across four independent tests is worth a
sentence, and it is not a substitute for a result.

**Held-out optimism, measured.** The tuning set gave BSZZ +0.0451; the
reporting projects give **+0.0167** — an optimism factor of 2.7x. This is the
cleanest possible justification for having held three projects out, and it
belongs in the methodology chapter as evidence the protocol worked.

### MP probe: the registered prediction is REFUTED, 0/6

Rescue was predicted to be ≤ 0 on every SZZ source. It is **positive on all
six**, and significant on three:

| Source | NA(rescue) − ORB | 95% CI | Projects | p |
|---|---|---|---|---|
| LSZZ | **+0.0166** | [+0.0057, +0.0289] | 13/18 | 0.006 |
| MASZZ | **+0.0142** | [+0.0013, +0.0266] | 12/18 | 0.027 |
| BSZZ | **+0.0116** | [+0.0033, +0.0262] | 13/18 | 0.024 |
| AGSZZ | +0.0117 | [−0.0007, +0.0270] | 13/18 | 0.090 |
| RSZZ | +0.0068 | [−0.0033, +0.0202] | 12/18 | 0.246 |
| RASZZ | +0.0002 | [−0.0164, +0.0213] | 8/18 | 1.000 |

The registration said plainly: *if rescue helps, the mechanism account needs
revision.* It helps. **The revision is owed and must be written.**

**The candidate reconciliation, and why it is not yet a claim.** Phase 3's
FN-repair restored the *oracle-known* missing positives. Rescue adds
*model-confident* positives, which are a different set: it is closer to
self-training on high-confidence commits than to label correction. So "restoring
the labels SZZ missed does nothing" and "adding confidently-predicted positives
helps" are not in contradiction — but they are only reconciled if the benefit
comes from positive *supply* rather than positive *accuracy*.

**That explanation was tested and did not hold.** Spearman between a
condition's delivered positive supply and the filter-minus-rescue advantage is
**ρ = +0.357, p = 0.385** over 8 conditions. The supply account is a hypothesis
for Phase 5, not a finding. Say so.

### Exploratory: NA(damp) leads, but mostly not significantly

NA(damp) is numerically best on 6 of 8 conditions, including BSZZ (0.0874 vs
ORB 0.0551) and oracle (0.1082). It was **not** the registered primary, so
every one of these contrasts is exploratory.

Corrected across the 21 exploratory contrasts, **NA(damp) > ORB survives global
Holm on 1 of 7 sources** — BSZZ, HL +0.0329, CI [+0.0194, +0.0456], 15/18,
p_holm 0.0040. No NA(damp)-vs-NA(fp_filter) contrast survives. The honest
statement is that damp leads numerically and is established only on BSZZ.

**The uncomfortable part, stated plainly.** The v2 registration moved the
headline to fp_filter on the strength of Phase 3's repair result, and the
pre-existing damp arm from the retired v1 outperforms it on every source. The
re-registration was correctly motivated and correctly timed; it still bet on
the wrong arm. Chapter 7 should say that, because the commit history shows it
either way and the reasoning was sound at the time.

### Why the oracle-assisted repair did not transfer

Phase 3's FP-repair used oracle knowledge to remove exactly the wrong labels
and recovered +0.0402. The train-time heuristic that approximates it recovers
+0.0167 and does not survive correction. The gap is the cost of not knowing
which positives are wrong: at the frozen setting the filter removes 30% of
positives on BSZZ, and it cannot tell a false positive from a commit the model
has not learned yet. `phase4_filter_stats.csv` shows it filtering 15% even on
the oracle arm, where there is nothing to remove.

**Positive labels are desperately scarce under latency** — a mean of **75 per
project** on the oracle arm across an entire stream. Any intervention that
removes positives is working against that scarcity, and ORB's boost rate rises
to compensate: mean λ reaches **62** on the oracle arm against 13 on BSZZ.

### R1: null, in both directions

observed − suppress: BSZZ HL −0.0016, CI [−0.0075, +0.0045], p = 0.61; oracle
HL +0.0002, p = 0.51. The registered prediction is not supported, and neither
is its converse. λ does rise when positives are suppressed — that coupling is
real and measured — but it has no detectable effect on performance at this
filter rate. Report as a clean null.

---

## Phase 5 — pre-registered damping test, run `35452244070`

Registration committed in `8482778` with **no results in the commit**; the
workflow and the run follow it. 34,560 records: 18 reporting projects × 10
seeds × 4 profiles × 6 doses × 2 latency arms × 4 models.

### The registered scorecard

| Test | Prediction | Result | Verdict |
|---|---|---|---|
| **H1** damp > ORB (fp_heavy) | positive | **+0.0168** [+0.0092, +0.0272], 15/18, Holm **0.0021** | ✅ **passes** |
| **H4** damp > filter (fp_heavy) | positive | **+0.0081** [+0.0022, +0.0141], 15/18, Holm **0.018** | ✅ **passes** |
| **ND** no degradation | no drop | **+0.0193** [+0.0092, +0.0299], Holm 0.0039 | ✅ **passes** (see note) |
| **H3** fn_heavy advantage > fp_heavy | positive | **−0.0217** [−0.0341, −0.0118], **2/18**, Holm **0.0021** | ❌ **refuted, opposite direction** |
| **H2** advantage grows with dose | ρ > 0 | ρ = **−0.486**, *p* = 0.84 | ❌ **fails** |

Two pass, two fail, and **the two that fail are the ones that were about the
mechanism.**

**A defect in my own registration, recorded rather than quietly fixed.** The ND
gate was registered as a TOST for *equivalence* at ±0.02. It returns
"not equivalent" — because damping is **better** than ORB by more than the
margin, not worse. The gate's intent (no degradation) is met decisively; the
registered statistic was the wrong one, and the right test for a
non-degradation gate is **non-inferiority**, a one-sided test against −margin.
The direction is unambiguous either way, so nothing is salvaged by the
substitution; the mis-specification is reported because it was registered.

### H3's refutation is the informative part

The prediction was that damping should shine under `fn_heavy` at doses ≥ 0.20,
where Chapter 6 measured that the stream retains no genuine defect labels while
still carrying ~204 positive labels, **all of them false**. If damping
suppresses wrong positives, that is where it should help most.

It helps **least** there — significantly so, with only 2 of 18 projects moving
the predicted way. Two candidate explanations, neither tested:

1. **No discriminative signal.** Confidence damping needs a *mixture* of correct
   and incorrect positives to separate. When every positive is wrong there is no
   reference class for "what a trustworthy positive looks like".
2. **A lower ceiling.** All models score ≈ 0.02 under `fn_heavy` against ≈ 0.05
   under `fp_heavy`, leaving less room for any advantage. The relative gap
   (1.19× against 1.57×) suggests this is contributory rather than sufficient.

### The exploratory control that explains H1 away

ORB = OOB + prediction-bias boost. NA(damp) = ORB + confidence damping. Adding
plain OOB to the grid separates the two:

| Profile | NA(damp) − ORB | **OOB − ORB** | **NA(damp) − OOB** |
|---|---|---|---|
| fp_heavy | +0.0168 (Holm 0.0047) | **+0.0172 (18/18, Holm 0.0001)** | +0.0019 (9/18, Holm 1.00) |
| symmetric | +0.0181 (Holm 0.0014) | **+0.0199 (17/18, Holm 0.0002)** | +0.0005 (8/18, Holm 1.00) |
| mid | +0.0139 (Holm 0.0023) | **+0.0139 (15/18, Holm 0.0026)** | +0.0020 (10/18, Holm 1.00) |
| fn_heavy | +0.0028 (n.s.) | +0.0075 (15/18, Holm 0.109) | −0.0050 (6/18, Holm 1.00) |

> **Damping adds nothing over simply not boosting.** Against plain OOB it is a
> coin flip in every profile — 8 to 10 wins out of 18, every interval spanning
> zero, every corrected *p* at 1.000. The entire H1 effect is reproduced by
> removing ORB's boost and adding no noise-awareness at all.

**H1 passes and is explained away by the control.** This is what a
pre-registration is for: the registered test confirmed the effect and the
registered mechanism test refuted the explanation, and an exploratory control
identified the actual cause.

### What this establishes

**ORB's prediction-bias boost is what costs performance under label noise** —
18 of 18 projects on `fp_heavy`, the strongest single result in Phases 4–5.
This is independent confirmation of Chapter 6's amplification account, arrived
at by intervention rather than by measuring λ.

It is consistent with, though not established by, the clean-label comparison:
on reference labels in Phase 4, OOB − ORB was +0.0050 (*p* = 0.47, not
significant), against +0.0172 under injected FP-heavy noise here. **The boost
appears roughly neutral on correct labels and harmful on incorrect ones**,
which is what the amplification account predicts. The interaction was not
formally tested and should not be claimed.

### What to write

The deployable recommendation from Phases 4 and 5 is **not** a noise-aware
learner. It is: *under SZZ-derived labels, do not boost the oversampling rate
on prediction bias.* Plain OOB matches every noise-aware variant tested and
beats ORB in 18 of 18 projects on the FP-heavy profile. Both confidence-based
defences — filtering in Phase 4 and damping here — were adoptable and neither
improved on removing the boost.

---

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

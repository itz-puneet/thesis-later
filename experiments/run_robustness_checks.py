"""Three outstanding analyses, closing the open items in the Phase 2 audit.

  A. Project characteristics table (audit 5b, part 1). Every reported figure in
     this thesis is an UNWEIGHTED mean over projects spanning 544 to 4,026
     commits and 1.8% to 19.3% defect rate. The appendix owes the reader the
     table that makes that visible.

  B. Positive-count sensitivity (audit 5b, part 2). Re-runs the headline
     contrasts on subsets that exclude projects below a positive-count floor,
     and reports whether any conclusion changes. Pure re-analysis of committed
     per-run CSVs -- no experiment is re-executed, so nothing here can drift
     from the numbers already published.

  C. False-positive predictability (the self-deception MECHANISM). Phase 2
     measures a +0.230 MCC self-scoring gap and three documents currently say
     the gap is "consistent with" a model fitting SZZ's error structure rather
     than defects -- explicitly NOT that it demonstrates it. The direct test is
     whether BSZZ's false positives are separable from its true positives using
     the same Kamei features the models see. Restricted to BSZZ-flagged
     commits, split chronologically per project, with a label-permutation
     control so "above chance" means above a measured null rather than above
     a nominal 0.5.

Outputs (results/appendix/): project_characteristics.csv,
headline_sensitivity.csv, fp_predictability.csv

Usage:
  python -m experiments.run_robustness_checks
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import roc_auc_score

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.append(str(BASE_DIR))

from codebase.config import KAMEI_FEATURES, RANDOM_SEEDS
from codebase.data.loader import load_or_build_dataset, get_all_projects, get_project_dataset
from codebase.evaluation.metrics import paired_effect
from experiments.run_phase2_impact import _holm

OUT = BASE_DIR / "results" / "appendix"
OUT.mkdir(parents=True, exist_ok=True)
P2 = BASE_DIR / "results" / "phase2"
P3 = BASE_DIR / "results" / "phase3"
P4 = BASE_DIR / "results" / "phase4"
FLOORS = [0, 25, 50]


# --------------------------------------------------------------- A
def project_characteristics(df: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for p in get_all_projects(df):
        d = get_project_dataset(p, df).sort_values("author_ts")
        n = len(d)
        pos = int(d["label_oracle"].sum())
        cut = n // 2
        rows.append(dict(
            project=p, n_commits=n, n_oracle_positives=pos,
            oracle_positive_rate=round(pos / n, 4),
            n_positives_train_half=int(d["label_oracle"].iloc[:cut].sum()),
            n_positives_test_half=int(d["label_oracle"].iloc[cut:].sum()),
            n_bszz_flagged=int(d["label_BSZZ"].sum()),
            span_years=round((d["author_ts"].max() - d["author_ts"].min())
                             / (365.25 * 86400), 1),
        ))
    out = pd.DataFrame(rows).sort_values("n_oracle_positives").reset_index(drop=True)
    out.to_csv(OUT / "project_characteristics.csv", index=False)
    return out


# --------------------------------------------------------------- B
def _contrast(piv: pd.DataFrame, a: str, b: str, keep: list[str]) -> dict | None:
    sub = piv.loc[piv.index.intersection(keep), [a, b]].dropna()
    if len(sub) < 6:
        return None
    e = paired_effect(sub[a].to_numpy(), sub[b].to_numpy())
    return dict(n=len(sub), mean_a=float(sub[a].mean()), mean_b=float(sub[b].mean()),
                hodges_lehmann=e["hodges_lehmann"], ci_low=e["ci_low"],
                ci_high=e["ci_high"], rank_biserial=e["rank_biserial"],
                n_favouring_a=int((sub[a] > sub[b]).sum()), p=e["p_value"])


def headline_sensitivity(chars: pd.DataFrame) -> pd.DataFrame:
    p2 = pd.read_csv(P2 / "phase2_results.csv")
    rows = []

    for floor in FLOORS:
        keep = chars.loc[chars.n_positives_test_half >= floor, "project"].tolist()

        # Family 1: k-fold vs chronological inflation (JITLine, oracle labels)
        sub = p2[(p2.model == "JITLine") & (p2.train_label == "oracle")
                 & (p2.eval_mode == "oracle")]
        piv = sub.groupby(["project", "regime"])["mcc"].mean().unstack()
        if {"naive_kfold", "chronological"} <= set(piv.columns):
            r = _contrast(piv, "naive_kfold", "chronological", keep)
            if r:
                rows.append(dict(family="regime_inflation",
                                 claim="JITLine/oracle: k-fold > chronological",
                                 floor=floor, **r))

        # Family 2: the self-deception gap. The headline claim (+0.2303) is the
        # k-fold one; the chronological contrast is reported beside it because
        # it is the deployment-relevant regime and behaves differently.
        for regime, tag in [("naive_kfold", "k-fold"),
                            ("chronological", "chronological")]:
            sub = p2[(p2.model == "JITLine") & (p2.train_label == "BSZZ")
                     & (p2.regime == regime)]
            piv = sub.groupby(["project", "eval_mode"])["mcc"].mean().unstack()
            if {"self", "oracle"} <= set(piv.columns):
                r = _contrast(piv, "self", "oracle", keep)
                if r:
                    rows.append(dict(
                        family="self_deception",
                        claim=f"JITLine/BSZZ {tag}: self-scored > oracle-scored",
                        floor=floor, **r))

        # Family 3: label-source gap (ORB, prequential, oracle vs BSZZ)
        sub = p2[(p2.model == "ORB") & (p2.regime.str.contains("prequential", na=False))
                 & (p2.eval_mode == "oracle")]
        piv = sub.groupby(["project", "train_label"])["mcc_avg"].mean().unstack()
        if {"oracle", "BSZZ"} <= set(piv.columns):
            r = _contrast(piv, "oracle", "BSZZ", keep)
            if r:
                rows.append(dict(family="label_source",
                                 claim="ORB prequential: oracle > BSZZ labels",
                                 floor=floor, **r))

        # Phase 3: the repair verdict
        f = P3 / "phase3_repair.csv"
        if f.exists():
            piv = (pd.read_csv(f).groupby(["project", "condition"])["mcc_avg"]
                     .mean().unstack())
            for a, b, name in [("BSZZ_fp_repaired", "BSZZ", "FP-repair > BSZZ"),
                               ("BSZZ_fn_repaired", "BSZZ", "FN-repair > BSZZ")]:
                r = _contrast(piv, a, b, keep)
                if r:
                    rows.append(dict(family="phase3_repair", claim=name,
                                     floor=floor, **r))

        # Phase 4: H1, on reporting projects only
        f = P4 / "phase4_results.csv"
        if f.exists():
            p4 = pd.read_csv(f)
            p4 = p4[~p4.held_out] if "held_out" in p4.columns else p4
            piv = (p4[p4.condition == "BSZZ"]
                   .groupby(["project", "model"])["mcc_avg"].mean().unstack())
            r = _contrast(piv, "NA(fp_filter)", "ORB", keep)
            if r:
                rows.append(dict(family="phase4_H1",
                                 claim="H1: fp_filter > ORB on BSZZ",
                                 floor=floor, **r))

    out = pd.DataFrame(rows)
    if not out.empty:
        out["p_holm_within_floor"] = np.nan
        for _, g in out.groupby("floor"):
            out.loc[g.index, "p_holm_within_floor"] = _holm(g["p"].to_numpy())
    out.to_csv(OUT / "headline_sensitivity.csv", index=False)
    return out


# --------------------------------------------------------------- C
def fp_predictability(df: pd.DataFrame) -> pd.DataFrame:
    """Among BSZZ-flagged commits, are false positives separable from true ones?"""
    rows = []
    for p in get_all_projects(df):
        d = get_project_dataset(p, df).sort_values("author_ts").reset_index(drop=True)
        flagged = d[d["label_BSZZ"] == 1]
        if len(flagged) < 40:
            continue
        y = (flagged["label_oracle"] == 0).astype(int).to_numpy()   # 1 == false positive
        X = flagged[KAMEI_FEATURES].to_numpy(dtype=float)
        cut = len(flagged) // 2
        ytr, yte = y[:cut], y[cut:]
        if len(np.unique(ytr)) < 2 or len(np.unique(yte)) < 2:
            continue
        for seed in RANDOM_SEEDS[:5]:
            rng = np.random.default_rng(seed)
            clf = RandomForestClassifier(n_estimators=100, random_state=seed, n_jobs=1)
            clf.fit(X[:cut], ytr)
            auc = roc_auc_score(yte, clf.predict_proba(X[cut:])[:, 1])
            # permutation control: same pipeline, labels shuffled in training
            clf_p = RandomForestClassifier(n_estimators=100, random_state=seed, n_jobs=1)
            clf_p.fit(X[:cut], rng.permutation(ytr))
            auc_perm = roc_auc_score(yte, clf_p.predict_proba(X[cut:])[:, 1])
            rows.append(dict(project=p, seed=seed, n_flagged=len(flagged),
                             fp_rate=float(y.mean()), auc=auc, auc_permuted=auc_perm))
    out = pd.DataFrame(rows)
    out.to_csv(OUT / "fp_predictability.csv", index=False)
    return out


def main():
    df = load_or_build_dataset()
    pd.set_option("display.width", 220)

    print("=== A. Project characteristics ===")
    chars = project_characteristics(df)
    print(chars.to_string(index=False))
    print(f"\n  commits {chars.n_commits.min()}-{chars.n_commits.max()}; "
          f"oracle positives {chars.n_oracle_positives.min()}-{chars.n_oracle_positives.max()}; "
          f"rate {chars.oracle_positive_rate.min():.1%}-{chars.oracle_positive_rate.max():.1%}")
    print(f"  projects with < 25 positives in the chronological test half: "
          f"{(chars.n_positives_test_half < 25).sum()}/{len(chars)}")

    print("\n=== B. Headline sensitivity to a positive-count floor ===")
    sens = headline_sensitivity(chars)
    cols = ["family", "claim", "floor", "n", "hodges_lehmann", "ci_low", "ci_high",
            "n_favouring_a", "p", "p_holm_within_floor"]
    print(sens[cols].round(4).to_string(index=False))

    print("\n=== C. Are BSZZ's false positives predictable from the Kamei features? ===")
    fp = fp_predictability(df)
    if fp.empty:
        print("  (insufficient data)")
        return
    per = fp.groupby("project")[["auc", "auc_permuted"]].mean()
    e = paired_effect(per["auc"].to_numpy(), per["auc_permuted"].to_numpy())
    print(per.round(4).to_string())
    print(f"\n  mean AUC {per['auc'].mean():.4f} vs permuted {per['auc_permuted'].mean():.4f}")
    print(f"  paired HL {e['hodges_lehmann']:+.4f} CI [{e['ci_low']:+.4f}, {e['ci_high']:+.4f}]"
          f"  rank-biserial {e['rank_biserial']:+.3f}"
          f"  {int((per['auc'] > per['auc_permuted']).sum())}/{len(per)} projects"
          f"  p {e['p_value']:.2e}")
    pd.DataFrame([dict(mean_auc=float(per["auc"].mean()),
                       mean_auc_permuted=float(per["auc_permuted"].mean()),
                       hodges_lehmann=e["hodges_lehmann"], ci_low=e["ci_low"],
                       ci_high=e["ci_high"], rank_biserial=e["rank_biserial"],
                       n_projects=len(per), p_value=e["p_value"])]
                ).to_csv(OUT / "fp_predictability_summary.csv", index=False)
    print(f"\nSaved to {OUT}/")


if __name__ == "__main__":
    main()

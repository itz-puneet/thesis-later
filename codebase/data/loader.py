"""Dataset loading and preprocessing for JIT-SDP experiments.

Combines 14 Kamei et al. (2013) change-level features with human oracle
ground truth and 6 Phase 1 SZZ variant labels.

Two-layer design (see Phase2_Audit_Findings_and_Remediation_Plan.md):

  * BASE FEATURES are stable. Kamei features, author_ts and label_oracle never
    change, so they are extracted once from the 101 MB JIT-Fine zip into the
    small, committed `data/processed/phase2_features.csv`. Reruns and CI read
    that file and never touch the zip.
  * SZZ LABELS are volatile. They are re-merged from `results/phase1/*_labels.csv`
    on every build, so regenerating Phase 1 always propagates to Phase 2.

The separation exists because Phase 2 once trained on a label vintage one commit
older than the one Phase 1 reported: the cached CSV was never invalidated when
the label files changed. `load_or_build_dataset` now refuses to serve a cache
that is older than the label files it was built from.
"""
from __future__ import annotations

import gc
import glob
import hashlib
import json
import pickle
import shutil
import subprocess
import tempfile
import zipfile
from pathlib import Path
import numpy as np
import pandas as pd

from codebase.config import (
    KAMEI_FEATURES,
    SZZ_VARIANTS,
    RAW_DATA_DIR,
    PROCESSED_DATA_DIR,
    PHASE1_RESULTS_DIR,
)

# The stable half of the schema: everything not derived from an SZZ run.
BASE_FEATURE_COLUMNS = ["project", "commit_id", "author_ts"] + KAMEI_FEATURES + ["label_oracle"]

FEATURES_CSV = PROCESSED_DATA_DIR / "phase2_features.csv"
DATASET_CSV = PROCESSED_DATA_DIR / "phase2_commits.csv"
PROVENANCE_JSON = PROCESSED_DATA_DIR / "phase2_commits.provenance.json"

ZIP_PATH = RAW_DATA_DIR / "JIT-Fine-replication.zip"
INNER_ZIP = "JIT-Fine-replication-zenodo/data.zip"
SPLIT_PKLS = ["train", "valid", "test"]


def normalize_base_features(df: pd.DataFrame) -> pd.DataFrame:
    """Rename JIT-Fine columns to our schema and coerce dtypes.

    Shared by the zip extraction path and scripts/extract_base_features.py so
    the two can never drift.
    """
    df = df.rename(
        columns={
            "commit_hash": "commit_id",
            "author_date_unix_timestamp": "author_ts",
            "is_buggy_commit": "label_oracle",
        }
    )

    # Standardize 'fix' feature to integer 0/1
    df["fix"] = df["fix"].apply(lambda x: 1 if str(x).lower() == "true" or x is True else 0)
    df["label_oracle"] = df["label_oracle"].astype(int)
    df["author_ts"] = df["author_ts"].astype(float)

    # Ensure all 14 Kamei features are numeric and finite
    for feat in KAMEI_FEATURES:
        df[feat] = pd.to_numeric(df[feat], errors="coerce").fillna(0.0)

    return df[BASE_FEATURE_COLUMNS].copy()


def extract_base_features_from_zip(zip_path: Path = ZIP_PATH) -> pd.DataFrame:
    """Extract the stable feature table from the JIT-Fine replication zip.

    Memory-safe: the 75 MB inner zip is streamed to a temp file rather than
    read into a bytes object and copied into a BytesIO, and each split pickle
    is loaded, subset to the 18 kept columns, and released before the next one.
    The previous implementation peaked near 1 GB and could OOM a small machine.
    """
    if not zip_path.exists():
        raise FileNotFoundError(
            f"JIT-Fine replication zip not found at {zip_path}. "
            f"If you only need to rebuild labels, commit {FEATURES_CSV.name} instead "
            f"(see scripts/extract_base_features.py)."
        )

    tmp_path = None
    try:
        with zipfile.ZipFile(zip_path, "r") as z1:
            with tempfile.NamedTemporaryFile(suffix=".zip", delete=False) as tmp:
                tmp_path = Path(tmp.name)
                with z1.open(INNER_ZIP) as src:
                    shutil.copyfileobj(src, tmp, length=1 << 20)   # 1 MB chunks

        parts = []
        with zipfile.ZipFile(tmp_path, "r") as z2:
            for split in SPLIT_PKLS:
                with z2.open(f"data/jitfine/features_{split}.pkl") as fh:
                    df_split = pickle.load(fh)
                parts.append(normalize_base_features(df_split))
                del df_split
                gc.collect()
                print(f"  extracted split '{split}': {len(parts[-1])} rows")
    finally:
        if tmp_path is not None and tmp_path.exists():
            tmp_path.unlink()

    full = pd.concat(parts, ignore_index=True)
    del parts
    gc.collect()
    full = full.drop_duplicates(subset=["project", "commit_id"]).reset_index(drop=True)
    return full


def load_base_features() -> pd.DataFrame:
    """Prefer the committed feature CSV; fall back to the zip when it is absent."""
    if FEATURES_CSV.exists():
        df = pd.read_csv(FEATURES_CSV)
        missing = [c for c in BASE_FEATURE_COLUMNS if c not in df.columns]
        if missing:
            raise ValueError(f"{FEATURES_CSV} is missing columns: {missing}")
        print(f"Loaded base features from {FEATURES_CSV} ({len(df)} rows).")
        return df[BASE_FEATURE_COLUMNS].copy()

    print(f"{FEATURES_CSV} not found -- extracting base features from {ZIP_PATH.name}...")
    df = extract_base_features_from_zip()
    print(f"Extracted {len(df)} commits from the replication package.")
    return df


def load_variant_labels(variant: str) -> pd.DataFrame | None:
    """Concatenate the per-project Phase 1 label files for one SZZ variant."""
    pred_col = f"label_{variant}"
    pattern = str(PHASE1_RESULTS_DIR / f"{variant.lower()}_*_labels.csv")
    pred_files = sorted(glob.glob(pattern))
    if not pred_files:
        print(f"Warning: No prediction files found for {variant} with pattern {pattern}")
        return None

    var_dfs = []
    for f in pred_files:
        try:
            df_f = pd.read_csv(f)
        except Exception as e:
            print(f"Error reading {f}: {e}")
            continue
        # Always derive the project from the filename. Trusting an in-file
        # 'project' column here would silently break the (project, commit_id)
        # merge if the two ever disagreed.
        df_f["project"] = Path(f).stem.replace(f"{variant.lower()}_", "").replace("_labels", "")
        var_dfs.append(df_f)

    if not var_dfs:
        return None

    var_df = pd.concat(var_dfs, ignore_index=True)
    if pred_col not in var_df.columns:
        match_cols = [c for c in var_df.columns if c.lower() == pred_col.lower()]
        if match_cols:
            var_df = var_df.rename(columns={match_cols[0]: pred_col})
        else:
            print(f"Warning: {variant} label files have no '{pred_col}' column")
            return None

    # NaN means "SZZ made no determination" -> not flagged. This must match
    # experiments/evaluate_confusion_matrix.py exactly or Phase 1 and Phase 2
    # will measure different label sets.
    var_df[pred_col] = var_df[pred_col].fillna(0).astype(int)
    return var_df.drop_duplicates(subset=["project", "commit_id"])


def _label_file_digests() -> dict[str, str]:
    """SHA-256 of every Phase 1 label file, for the provenance sidecar."""
    digests = {}
    for f in sorted(glob.glob(str(PHASE1_RESULTS_DIR / "*_labels.csv"))):
        h = hashlib.sha256()
        with open(f, "rb") as fh:
            for chunk in iter(lambda: fh.read(1 << 20), b""):
                h.update(chunk)
        digests[Path(f).name] = h.hexdigest()
    return digests


def _git_commit() -> str:
    try:
        return subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True, text=True, check=True,
        ).stdout.strip()
    except Exception:
        return "unknown"


def _newest_label_mtime() -> float:
    return max(
        (p.stat().st_mtime for p in PHASE1_RESULTS_DIR.glob("*_labels.csv")),
        default=0.0,
    )


def build_unified_dataset() -> pd.DataFrame:
    """Merge stable base features with the CURRENT Phase 1 SZZ labels."""
    final_df = load_base_features()

    print("Merging Phase 1 SZZ predictions...")
    for variant in SZZ_VARIANTS:
        pred_col = f"label_{variant}"
        var_df = load_variant_labels(variant)
        if var_df is None:
            final_df[pred_col] = 0
            continue
        final_df = final_df.merge(
            var_df[["project", "commit_id", pred_col]],
            on=["project", "commit_id"],
            how="left",
        )
        final_df[pred_col] = final_df[pred_col].fillna(0).astype(int)
        print(f"  {variant}: {int(final_df[pred_col].sum())} commits flagged")

    # Carry fix_ts forward. It is reconstructed by scripts/build_fix_ts.py from
    # git history + pyszz mappings and is NOT recoverable from the feature
    # source, so a rebuild that dropped it would silently degrade every
    # prequential run to a uniform delay.
    carried = _carry_forward_fix_ts(final_df)

    final_df = final_df.sort_values(["project", "author_ts"]).reset_index(drop=True)

    PROCESSED_DATA_DIR.mkdir(parents=True, exist_ok=True)
    final_df.to_csv(DATASET_CSV, index=False)

    with open(PROVENANCE_JSON, "w") as f:
        json.dump(
            {
                "built_at_git_commit": _git_commit(),
                "n_rows": int(len(final_df)),
                "base_features_source": FEATURES_CSV.name if FEATURES_CSV.exists() else ZIP_PATH.name,
                "label_positives": {
                    v: int(final_df[f"label_{v}"].sum()) for v in SZZ_VARIANTS
                },
                "oracle_positives": int(final_df["label_oracle"].sum()),
                "fix_ts_columns_carried": carried,
                "label_file_sha256": _label_file_digests(),
            },
            f,
            indent=2,
        )

    print(f"Successfully constructed and saved unified dataset to {DATASET_CSV} ({len(final_df)} rows).")
    if not carried:
        print(
            "\n  *** fix_ts is ABSENT from the rebuilt dataset. ***\n"
            "  Run `python scripts/build_fix_ts.py --mode real` before Phase 2,\n"
            "  or prequential_latency will refuse to run in 'real' mode.\n"
        )
    return final_df


def _carry_forward_fix_ts(final_df: pd.DataFrame) -> list[str]:
    """Re-merge fix_ts* columns from the previous dataset build, if any.

    Returns the list of columns carried over (empty if none were available).
    """
    if not DATASET_CSV.exists():
        return []
    try:
        prev = pd.read_csv(DATASET_CSV)
    except Exception as e:
        print(f"  [fix_ts] could not read previous dataset ({e}); skipping carry-forward")
        return []

    fix_cols = [c for c in prev.columns if c.startswith("fix_ts")]
    if not fix_cols:
        return []

    merged = final_df.merge(
        prev[["project", "commit_id"] + fix_cols],
        on=["project", "commit_id"],
        how="left",
    )
    final_df[fix_cols] = merged[fix_cols].to_numpy()
    covered = int(final_df["fix_ts"].notna().sum()) if "fix_ts" in fix_cols else 0
    print(f"  [fix_ts] carried forward {len(fix_cols)} columns ({covered} commits with a union fix_ts)")
    print("  [fix_ts] NOTE: labels changed, so re-run scripts/build_fix_ts.py --mode real")
    return fix_cols


def load_or_build_dataset(force_rebuild: bool = False) -> pd.DataFrame:
    """Load the cached dataset, refusing to serve one that predates its labels."""
    if DATASET_CSV.exists() and not force_rebuild:
        if _newest_label_mtime() > DATASET_CSV.stat().st_mtime:
            raise RuntimeError(
                f"{DATASET_CSV} is older than results/phase1/*_labels.csv.\n"
                "Phase 1 labels changed since this cache was built, so Phase 2 would "
                "train on a stale label vintage (this exact bug invalidated the first "
                "Phase 2 run). Rebuild in this order:\n"
                "  python -c 'from codebase.data.loader import build_unified_dataset; build_unified_dataset()'\n"
                "  python scripts/build_fix_ts.py --mode real\n"
                "  python -m experiments.check_label_consistency"
            )
        return pd.read_csv(DATASET_CSV)
    return build_unified_dataset()


def get_all_projects(df: pd.DataFrame | None = None) -> list[str]:
    """Return sorted list of unique project names."""
    if df is None:
        df = load_or_build_dataset()
    return sorted(df["project"].unique().tolist())


def get_project_dataset(project_name: str, df: pd.DataFrame | None = None) -> pd.DataFrame:
    """Return chronologically sorted slice for a single project."""
    if df is None:
        df = load_or_build_dataset()
    sub = df[df["project"] == project_name].copy()
    return sub.sort_values("author_ts").reset_index(drop=True)

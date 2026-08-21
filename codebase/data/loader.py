"""Dataset loading and preprocessing for JIT-SDP experiments.

Combines 14 Kamei et al. (2013) change-level features with human oracle
ground truth and 6 Phase 1 SZZ variant labels.
"""
from __future__ import annotations

import io
import glob
import pickle
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


def build_unified_dataset() -> pd.DataFrame:
    """Extract features from JIT-Fine replication package and merge with Phase 1 SZZ predictions."""
    zip_path = RAW_DATA_DIR / "JIT-Fine-replication.zip"
    if not zip_path.exists():
        raise FileNotFoundError(f"JIT-Fine replication zip not found at {zip_path}")

    print("Extracting feature pickles from JIT-Fine replication package...")
    with zipfile.ZipFile(zip_path, "r") as z1:
        data_zip_bytes = z1.read("JIT-Fine-replication-zenodo/data.zip")
        with zipfile.ZipFile(io.BytesIO(data_zip_bytes), "r") as z2:
            dfs = []
            for split in ["train", "valid", "test"]:
                raw_pkl = z2.read(f"data/jitfine/features_{split}.pkl")
                df_split = pickle.loads(raw_pkl)
                dfs.append(df_split)
            full_df = pd.concat(dfs, ignore_index=True)

    print(f"Loaded base features dataframe with {len(full_df)} commits.")

    # Rename columns to standard schema
    full_df = full_df.rename(
        columns={
            "commit_hash": "commit_id",
            "author_date_unix_timestamp": "author_ts",
            "is_buggy_commit": "label_oracle",
        }
    )

    # Standardize 'fix' feature to integer 0/1
    full_df["fix"] = full_df["fix"].apply(
        lambda x: 1 if str(x).lower() == "true" or x is True else 0
    )
    full_df["label_oracle"] = full_df["label_oracle"].astype(int)
    full_df["author_ts"] = full_df["author_ts"].astype(float)

    # Ensure all 14 Kamei features are numeric and finite
    for feat in KAMEI_FEATURES:
        full_df[feat] = pd.to_numeric(full_df[feat], errors="coerce").fillna(0.0)

    # Deduplicate by (project, commit_id) keeping first
    full_df = full_df.drop_duplicates(subset=["project", "commit_id"]).reset_index(drop=True)

    # Merge Phase 1 SZZ predictions for all variants
    print("Merging Phase 1 SZZ predictions...")
    for variant in SZZ_VARIANTS:
        pattern = str(PHASE1_RESULTS_DIR / f"{variant.lower()}_*_labels.csv")
        pred_files = glob.glob(pattern)
        if not pred_files:
            print(f"Warning: No prediction files found for {variant} with pattern {pattern}")
            full_df[f"label_{variant}"] = 0
            continue

        var_dfs = []
        for f in pred_files:
            try:
                var_dfs.append(pd.read_csv(f))
            except Exception as e:
                print(f"Error reading {f}: {e}")

        if var_dfs:
            var_df = pd.concat(var_dfs, ignore_index=True)
            var_df = var_df.drop_duplicates(subset=["commit_id"])
            pred_col = f"label_{variant}"
            if pred_col not in var_df.columns:
                # Try finding alternative column name
                match_cols = [c for c in var_df.columns if c.lower() == pred_col.lower()]
                if match_cols:
                    var_df = var_df.rename(columns={match_cols[0]: pred_col})
            
            full_df = pd.merge(
                full_df,
                var_df[["commit_id", pred_col]],
                on="commit_id",
                how="left",
            )
            full_df[pred_col] = full_df[pred_col].fillna(0).astype(int)

    # Reorder columns
    meta_cols = ["project", "commit_id", "author_ts"]
    label_cols = ["label_oracle"] + [f"label_{v}" for v in SZZ_VARIANTS]
    selected_cols = meta_cols + KAMEI_FEATURES + label_cols

    # Keep any extra relevant columns if needed
    final_df = full_df[selected_cols].copy()
    final_df = final_df.sort_values(["project", "author_ts"]).reset_index(drop=True)

    # Save processed CSV for quick reuse
    PROCESSED_DATA_DIR.mkdir(parents=True, exist_ok=True)
    out_csv = PROCESSED_DATA_DIR / "phase2_commits.csv"
    final_df.to_csv(out_csv, index=False)
    print(f"Successfully constructed and saved unified dataset to {out_csv} ({len(final_df)} rows).")

    return final_df


def load_or_build_dataset(force_rebuild: bool = False) -> pd.DataFrame:
    """Load cached dataset or build it if missing."""
    out_csv = PROCESSED_DATA_DIR / "phase2_commits.csv"
    if out_csv.exists() and not force_rebuild:
        df = pd.read_csv(out_csv)
        return df
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

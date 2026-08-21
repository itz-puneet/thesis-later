"""Build real `fix_ts` columns for phase2_commits.csv from Defects4J bug fixes and git history.

Reconstructs verification latency timestamps:
1. Fix commit author timestamps extracted from git log of cloned repos in data/raw/<project>/
2. Fix -> inducing mappings from results/phase1_raw/<variant>_<project>.json
3. Adds fix_ts_<VARIANT> and unified fix_ts to data/processed/phase2_commits.csv

Usage:
  python scripts/build_fix_ts.py --mode real      # build fix_ts, update CSV
  python scripts/build_fix_ts.py --mode uniform   # keep NaN for fixed-delay evaluation
"""
from __future__ import annotations

import argparse
import glob
import json
import subprocess
from pathlib import Path

import numpy as np
import pandas as pd

RAW = Path("data/raw")
PROCESSED = Path("data/processed/phase2_commits.csv")
MAPPING_DIR = Path("results/phase1_raw")   # fix->inducing JSONs per variant/project
FIX_CSV = RAW / "jit_defects4j.csv"


def git_commit_dates(repo_dir: Path, hashes: set[str]) -> dict[str, float]:
    """Author timestamps (unix) for the given commit hashes in one repo."""
    out = subprocess.run(
        ["git", "log", "--all", "--pretty=%H %at"],
        cwd=repo_dir, capture_output=True, text=True, check=True,
    ).stdout
    dates = {}
    for line in out.splitlines():
        try:
            h, ts = line.split()
        except ValueError:
            continue
        if h in hashes:
            dates[h] = float(ts)
    return dates


def load_mappings() -> pd.DataFrame:
    """All fix->inducing pairs from every mapping JSON.

    Expected JSON schema (pyszz output / base.py results_df):
      [{"fix_commit_hash": "...", "inducing_commit_hash": ["...", ...]}, ...]
    Filenames: <variant>_<project>.json
    """
    rows = []
    for f in glob.glob(str(MAPPING_DIR / "*.json")):
        stem = Path(f).stem
        variant, _, project = stem.partition("_")
        with open(f) as fh:
            data = json.load(fh)
        for rec in data:
            inducing = rec.get("inducing_commit_hash") or rec.get("inducing_commits") or []
            if isinstance(inducing, str):
                inducing = json.loads(inducing)
            for ind in inducing:
                rows.append(dict(variant=variant.upper(), project=project,
                                 fix_commit_hash=rec["fix_commit_hash"],
                                 commit_id=ind))
    if not rows:
        raise FileNotFoundError(
            f"No mapping JSONs in {MAPPING_DIR}. Run Phase 1 pipeline "
            f"(python -m experiments.run_phase1_oracle) to emit them.")
    return pd.DataFrame(rows)


def main(mode: str):
    df = pd.read_csv(PROCESSED)

    # Drop existing fix_ts columns to ensure idempotency across runs
    existing_fix_cols = [c for c in df.columns if c.startswith("fix_ts")]
    if existing_fix_cols:
        df = df.drop(columns=existing_fix_cols)

    if mode == "uniform":
        df["fix_ts"] = np.nan
        df.to_csv(PROCESSED, index=False)
        print("fix_ts set to NaN for all commits. Prequential evaluation will use "
              "a uniform W-day delay. DOCUMENT THIS as 'fixed-delay online "
              "evaluation', not 'verification latency'.")
        return

    # 1) fix-commit dates per project
    fixes = pd.read_csv(FIX_CSV)
    fix_dates: dict[tuple[str, str], float] = {}
    for project, g in fixes.groupby("project"):
        repo_dir = RAW / project.replace("/", "_")
        if not repo_dir.exists():
            print(f"  [skip] repo not cloned: {repo_dir}")
            continue
        dates = git_commit_dates(repo_dir, set(g["fix_commit_hash"]))
        for h, ts in dates.items():
            fix_dates[(project, h)] = ts
        print(f"  {project}: dated {len(dates)}/{len(g)} fix commits")

    # 2) mapping -> earliest fix date per inducing commit (per variant + union)
    mapping = load_mappings()
    mapping["fix_ts"] = mapping.apply(
        lambda r: fix_dates.get((r["project"], r["fix_commit_hash"]), np.nan), axis=1)
    mapping = mapping.dropna(subset=["fix_ts"])

    # per-variant fix_ts columns (fix_ts_BSZZ, ...) + union column fix_ts
    for variant, g in mapping.groupby("variant"):
        earliest = g.groupby(["project", "commit_id"])["fix_ts"].min().rename(
            f"fix_ts_{variant}").reset_index()
        df = df.merge(earliest, on=["project", "commit_id"], how="left")

    union = mapping.groupby(["project", "commit_id"])["fix_ts"].min().rename(
        "fix_ts").reset_index()
    df = df.merge(union, on=["project", "commit_id"], how="left")

    # sanity: fix must postdate the inducing commit
    for c in [c for c in df.columns if c.startswith("fix_ts")]:
        bad = (df[c] <= df["author_ts"]).sum()
        df.loc[df[c] <= df["author_ts"], c] = np.nan
        if bad:
            print(f"  [{c}] {bad} fix dates <= author date -> NaN (clock skew / bad link)")

    df.to_csv(PROCESSED, index=False)
    linked = df["fix_ts"].notna().sum()
    lat_days = ((df["fix_ts"] - df["author_ts"]) / 86400).dropna()
    print(f"\nfix_ts built: {linked}/{len(df)} commits linked to a fix.")
    if len(lat_days) > 0:
        print(f"Latency days -- median {lat_days.median():.0f}, "
              f"p90 {lat_days.quantile(.9):.0f}, share > 90d: {(lat_days > 90).mean():.1%}")
        print("Report that '> 90d' share in the thesis: it is the fraction of defect "
              "labels that a W=90 protocol first sees as (wrong) clean labels.")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=["real", "uniform"], default="real")
    main(ap.parse_args().mode)

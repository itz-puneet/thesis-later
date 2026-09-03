"""One-time extraction of the stable feature table from the JIT-Fine zip.

Writes data/processed/phase2_features.csv (~4 MB, committed) so that every
later dataset rebuild -- including on a CI runner, where the 101 MB zip is not
available -- can run without it.

The Kamei features, author timestamps and oracle labels never change; only the
SZZ label columns do. Splitting the two lets CI re-merge labels cheaply and
removes the one step that could OOM a small machine.

Memory: streams the inner zip to a temp file and releases each split pickle
before loading the next (peak ~200 MB rather than ~1 GB).

Usage:
  python scripts/extract_base_features.py

  # with a hard cap, so a miss fails cleanly instead of freezing the machine:
  systemd-run --user --scope -p MemoryMax=2G -p MemorySwapMax=0 \
      venv/bin/python scripts/extract_base_features.py
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent))

from codebase.data.loader import (  # noqa: E402
    BASE_FEATURE_COLUMNS,
    FEATURES_CSV,
    PROCESSED_DATA_DIR,
    extract_base_features_from_zip,
)

EXPECTED_ROWS = 27319
EXPECTED_ORACLE_POSITIVES = 2332


def main(overwrite: bool) -> int:
    if FEATURES_CSV.exists() and not overwrite:
        print(f"{FEATURES_CSV} already exists. Re-run with --overwrite to regenerate.")
        return 0

    print("Extracting base features (streaming; this takes a minute)...")
    df = extract_base_features_from_zip()

    print(f"\nExtracted {len(df)} commits, {df['project'].nunique()} projects.")
    print(f"Oracle positives: {int(df['label_oracle'].sum())} "
          f"({df['label_oracle'].mean():.2%})")

    problems = []
    if len(df) != EXPECTED_ROWS:
        problems.append(f"expected {EXPECTED_ROWS} rows, got {len(df)}")
    if int(df["label_oracle"].sum()) != EXPECTED_ORACLE_POSITIVES:
        problems.append(
            f"expected {EXPECTED_ORACLE_POSITIVES} oracle positives, "
            f"got {int(df['label_oracle'].sum())}"
        )
    missing = [c for c in BASE_FEATURE_COLUMNS if c not in df.columns]
    if missing:
        problems.append(f"missing columns: {missing}")
    if df[["project", "commit_id"]].duplicated().any():
        problems.append("duplicate (project, commit_id) keys")

    if problems:
        print("\nREFUSING TO WRITE -- extraction does not match the known corpus:")
        for p in problems:
            print(f"  - {p}")
        print("\nEverything downstream depends on this file being correct.")
        return 1

    PROCESSED_DATA_DIR.mkdir(parents=True, exist_ok=True)
    df.to_csv(FEATURES_CSV, index=False)
    size_mb = FEATURES_CSV.stat().st_size / 1e6
    print(f"\n[OK] Wrote {FEATURES_CSV} ({size_mb:.2f} MB). Commit this file.")
    return 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--overwrite", action="store_true", help="regenerate even if the CSV exists")
    sys.exit(main(ap.parse_args().overwrite))

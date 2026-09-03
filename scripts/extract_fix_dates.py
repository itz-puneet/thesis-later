"""One-time extraction of fix-commit author dates from the cloned repos.

Writes data/raw/fix_commit_dates.csv (~0.3 MB, committed) so that
scripts/build_fix_ts.py can reconstruct verification latency without the
830 MB of cloned Apache repositories -- which is what lets the whole
fix_ts step run on a CI runner.

The only thing build_fix_ts.py takes from the repos is the author timestamp of
each of the 5,453 Defects4J fix commits. That is a small table, so we cache it
rather than the repositories.

Cost: `git log --all` is ~0.1 s per repo, so this is a couple of seconds total.

Usage:
  python scripts/extract_fix_dates.py
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

sys.path.append(str(Path(__file__).resolve().parent.parent))

from scripts.build_fix_ts import FIX_CSV, RAW, git_commit_dates  # noqa: E402

OUT_CSV = RAW / "fix_commit_dates.csv"


def main(overwrite: bool) -> int:
    if OUT_CSV.exists() and not overwrite:
        print(f"{OUT_CSV} already exists. Re-run with --overwrite to regenerate.")
        return 0

    if not FIX_CSV.exists():
        print(f"ERROR: {FIX_CSV} not found.")
        return 1

    fixes = pd.read_csv(FIX_CSV)
    print(f"{len(fixes)} fix commits across {fixes['project'].nunique()} projects.")

    rows, missing_repos = [], []
    for project, g in fixes.groupby("project"):
        repo_dir = RAW / str(project).replace("/", "_")
        if not repo_dir.exists():
            missing_repos.append(str(project))
            print(f"  [skip] repo not cloned: {repo_dir}")
            continue
        dates = git_commit_dates(repo_dir, set(g["fix_commit_hash"]))
        for h, ts in dates.items():
            rows.append(dict(project=project, fix_commit_hash=h, fix_author_ts=ts))
        print(f"  {project}: dated {len(dates)}/{len(g)} fix commits")

    if not rows:
        print("\nERROR: no fix dates extracted. Are the repos cloned under data/raw/?")
        return 1

    out = pd.DataFrame(rows).drop_duplicates(subset=["project", "fix_commit_hash"])
    out.to_csv(OUT_CSV, index=False)

    coverage = len(out) / len(fixes)
    print(f"\n[OK] Wrote {OUT_CSV} ({OUT_CSV.stat().st_size / 1e6:.2f} MB)")
    print(f"     {len(out)}/{len(fixes)} fix commits dated ({coverage:.1%}).")
    if missing_repos:
        print(f"     WARNING: {len(missing_repos)} projects had no local clone: {missing_repos}")
        print("     Those projects' defect labels will never arrive in prequential runs.")
    print("     Commit this file.")
    return 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--overwrite", action="store_true", help="regenerate even if the CSV exists")
    sys.exit(main(ap.parse_args().overwrite))

"""Phase 1 SZZ pipeline: run PySZZ variants against Defects4J bug fixes across 21 projects.

Generates:
1. Raw fix -> inducing JSON mappings: results/phase1_raw/{variant}_{project}.json
2. Per-commit binary label CSVs: results/phase1/{variant}_{project}_labels.csv
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import pandas as pd

# Add our local srcML installation to PATH and LD_LIBRARY_PATH so PySZZ can find it
SRCML_DIR = Path(__file__).resolve().parent.parent / "tools" / "srcml"
if SRCML_DIR.exists():
    bin_dir = str(SRCML_DIR / "usr" / "bin")
    lib_dir = str(SRCML_DIR / "usr" / "lib")
    os.environ["PATH"] = f"{bin_dir}{os.pathsep}{os.environ.get('PATH', '')}"
    os.environ["LD_LIBRARY_PATH"] = f"{lib_dir}{os.pathsep}{os.environ.get('LD_LIBRARY_PATH', '')}"

# Add parent directory to Python path
sys.path.append(str(Path(__file__).resolve().parent.parent))

from codebase.szz.bszz import BSZZ
from codebase.szz.agszz import AGSZZ
from codebase.szz.maszz import MASZZ
from codebase.szz.lszz import LSZZ
from codebase.szz.rszz import RSZZ
from codebase.szz.raszz import RASZZ

ALL_VARIANTS = {
    "bszz": BSZZ,
    "agszz": AGSZZ,
    "maszz": MASZZ,
    "lszz": LSZZ,
    "rszz": RSZZ,
    "raszz": RASZZ,
}


def setup_repository(repo_url: str, target_dir: Path):
    """Clones the repository if it doesn't exist."""
    if not target_dir.exists():
        print(f"Cloning {repo_url} into {target_dir}...")
        subprocess.run(["git", "clone", repo_url, str(target_dir)], check=True)
    else:
        print(f"Repository already exists at {target_dir}")


def get_unique_projects(csv_path: Path) -> list[str]:
    """Extracts all unique projects from the dataset."""
    df = pd.read_csv(csv_path)
    return df["project"].unique().tolist()


def load_defects4j_dataset(csv_path: Path, target_repo: str) -> pd.DataFrame:
    """Loads the real JIT-Defects4J dataset and filters it for the target repository."""
    if not csv_path.exists():
        raise FileNotFoundError(f"Dataset not found at {csv_path}. Please download it.")

    df = pd.read_csv(csv_path)
    repo_df = df[df["project"] == target_repo].copy()

    if repo_df.empty:
        raise ValueError(f"No commits found for project '{target_repo}' in the dataset.")

    return repo_df


def extract_repo_commits(repo_dir: Path) -> list[str]:
    """Extract all commit hashes from repository git log."""
    out = subprocess.run(
        ["git", "log", "--all", "--pretty=%H"],
        cwd=str(repo_dir), capture_output=True, text=True, check=True
    ).stdout
    return [line.strip() for line in out.splitlines() if line.strip()]


def main():
    parser = argparse.ArgumentParser(description="Run Phase 1 PySZZ pipeline.")
    parser.add_argument("--variants", nargs="+", default=list(ALL_VARIANTS.keys()),
                        choices=list(ALL_VARIANTS.keys()), help="SZZ variants to run")
    parser.add_argument("--projects", nargs="+", default=None,
                        help="Specific project names to run (default: all 21)")
    parser.add_argument("--overwrite", action="store_true",
                        help="Overwrite existing output files instead of skipping")
    args = parser.parse_args()

    base_dir = Path(__file__).resolve().parent.parent
    raw_data_dir = base_dir / "data" / "raw"
    dataset_csv = raw_data_dir / "jit_defects4j.csv"
    pyszz_dir = base_dir / "tools" / "pyszz_v2"
    results_dir = base_dir / "results" / "phase1"
    raw_mapping_dir = base_dir / "results" / "phase1_raw"

    raw_data_dir.mkdir(parents=True, exist_ok=True)
    results_dir.mkdir(parents=True, exist_ok=True)
    raw_mapping_dir.mkdir(parents=True, exist_ok=True)

    all_projects = get_unique_projects(dataset_csv)
    projects = args.projects if args.projects else all_projects
    print(f"Target projects ({len(projects)}): {projects}")
    print(f"Target variants ({len(args.variants)}): {args.variants}")
    print("=" * 60)

    for project_name in projects:
        print(f"\n>>> Processing Project: {project_name}")
        repo_url = f"https://github.com/{project_name}.git"
        safe_project_name = project_name.replace("/", "_")
        repo_dir = raw_data_dir / safe_project_name

        setup_repository(repo_url, repo_dir)
        fixes_df = load_defects4j_dataset(dataset_csv, project_name)
        print(f"Loaded {len(fixes_df)} known bug-fixing commits for {project_name}.")

        # Get all commits in repo for binary labeling
        all_repo_commits = extract_repo_commits(repo_dir)

        for variant_name in args.variants:
            adapter_class = ALL_VARIANTS[variant_name]
            raw_json_file = raw_mapping_dir / f"{variant_name}_{safe_project_name}.json"
            labels_csv_file = results_dir / f"{variant_name}_{safe_project_name}_labels.csv"

            if not args.overwrite and raw_json_file.exists() and labels_csv_file.exists():
                print(f"[-] Skipping {variant_name.upper()} for {project_name} (outputs already exist)")
                continue

            print(f"\n--- Running {variant_name.upper()} on {project_name} ---")
            try:
                adapter = adapter_class(pyszz_dir=str(pyszz_dir))
                results_df = adapter.label(repo_path=str(repo_dir), fixes=fixes_df)

                # 1. Save raw fix -> inducing mapping JSON
                mapping_records = results_df.to_dict(orient="records")
                with open(raw_json_file, "w") as fh:
                    json.dump(mapping_records, fh, indent=2)
                print(f"[OK] Saved raw mappings to {raw_json_file.name}")

                # 2. Extract inducing commits set
                inducing_set = set()
                for rec in mapping_records:
                    ind = rec.get("inducing_commit_hash") or rec.get("inducing_commits") or []
                    if isinstance(ind, str):
                        try:
                            ind = json.loads(ind)
                        except Exception:
                            ind = [ind]
                    if isinstance(ind, list):
                        inducing_set.update(ind)

                # 3. Create per-commit binary labels CSV
                labels = [1 if c in inducing_set else 0 for c in all_repo_commits]
                labels_df = pd.DataFrame({
                    "commit_id": all_repo_commits,
                    f"label_{variant_name.upper()}": labels,
                })
                labels_df.to_csv(labels_csv_file, index=False)
                print(f"[OK] Saved binary labels to {labels_csv_file.name} "
                      f"({len(inducing_set)} unique inducing commits found).")

            except Exception as e:
                print(f"[ERROR] Failed to run {variant_name.upper()} on {project_name}: {e}")
                continue


if __name__ == "__main__":
    main()

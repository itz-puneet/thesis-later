import os
import subprocess
import pandas as pd
from pathlib import Path
import sys

# Add our local srcML installation to PATH and LD_LIBRARY_PATH so PySZZ can find it
SRCML_DIR = Path(__file__).parent.parent / "tools" / "srcml"
if SRCML_DIR.exists():
    os.environ["PATH"] = f"{SRCML_DIR / 'usr' / 'bin'}:{os.environ.get('PATH', '')}"
    os.environ["LD_LIBRARY_PATH"] = f"{SRCML_DIR / 'usr' / 'lib'}:{os.environ.get('LD_LIBRARY_PATH', '')}"

# Add the parent directory to the Python path so we can import 'codebase'
sys.path.append(str(Path(__file__).resolve().parent.parent))

from codebase.szz.bszz import BSZZ
from codebase.szz.agszz import AGSZZ
from codebase.szz.maszz import MASZZ
from codebase.szz.lszz import LSZZ
from codebase.szz.rszz import RSZZ
from codebase.szz.raszz import RASZZ

def setup_repository(repo_url, target_dir):
    """Clones the repository if it doesn't exist."""
    if not os.path.exists(target_dir):
        print(f"Cloning {repo_url} into {target_dir}...")
        subprocess.run(["git", "clone", repo_url, target_dir], check=True)
    else:
        print(f"Repository already exists at {target_dir}")

def get_unique_projects(csv_path) -> list:
    """Extracts all unique projects from the dataset."""
    df = pd.read_csv(csv_path)
    return df['project'].unique().tolist()

def load_defects4j_dataset(csv_path, target_repo) -> pd.DataFrame:
    """
    Loads the real JIT-Defects4J dataset and filters it for the target repository.
    Expected CSV columns: 'project', 'fix_commit_hash'
    """
    if not os.path.exists(csv_path):
        raise FileNotFoundError(f"Dataset not found at {csv_path}. Please download it.")
        
    df = pd.read_csv(csv_path)
    repo_df = df[df['project'] == target_repo].copy()
    
    if repo_df.empty:
        raise ValueError(f"No commits found for project '{target_repo}' in the dataset.")
        
    return repo_df

def main():
    # 1. Configuration Paths
    base_dir = Path(__file__).resolve().parent.parent
    raw_data_dir = base_dir / "data" / "raw"
    dataset_csv = raw_data_dir / "jit_defects4j.csv"
    pyszz_dir = base_dir / "tools" / "pyszz_v2"
    results_dir = base_dir / "results" / "phase1"
    
    # Create directories if they don't exist
    raw_data_dir.mkdir(parents=True, exist_ok=True)
    results_dir.mkdir(parents=True, exist_ok=True)

    # 2. Extract all 21 projects from the CSV
    projects = get_unique_projects(str(dataset_csv))
    print(f"Found {len(projects)} unique projects in the dataset.")
    
    # 3. Define the SZZ variants to evaluate using individual adapters
    szz_variants = {
        # 'bszz': BSZZ, # Already completed
        'agszz': AGSZZ,
        'maszz': MASZZ,
        'lszz': LSZZ,
        'rszz': RSZZ,
        'raszz': RASZZ
    }
    
    print(f"Variants to evaluate: {list(szz_variants.keys())}")
    print("=" * 60)
    
    # 4. Batch Execution
    for project_name in projects:
        print(f"\n>>> Processing Project: {project_name}")
        repo_url = f"https://github.com/apache/{project_name}.git"
        repo_dir = raw_data_dir / project_name
        
        # Ensure project is cloned
        setup_repository(repo_url, str(repo_dir))
        
        # Load the bug-fixing commits for this specific project
        fixes_df = load_defects4j_dataset(str(dataset_csv), project_name)
        print(f"Loaded {len(fixes_df)} known bug-fixing commits for {project_name}.")
        
        for variant, adapter_class in szz_variants.items():
            output_file = results_dir / f"{variant}_{project_name}_labels.csv"
            
            # Checkpointing logic: Skip if already processed
            if output_file.exists():
                print(f"[-] Skipping {variant.upper()} for {project_name} (File already exists: {output_file.name})")
                continue
                
            print(f"\n--- Running {variant.upper()} on {project_name} ---")
            
            try:
                adapter = adapter_class(pyszz_dir=str(pyszz_dir))
                results_df = adapter.label(repo_path=str(repo_dir), fixes=fixes_df)
                
                # Save Results
                results_df.to_csv(output_file, index=False)
                
                inducing_count = results_df[f'label_{variant.upper()}'].sum()
                print(f"✅ Success! Saved to {output_file.name}")
                print(f"Found {inducing_count} bug-inducing commits using {variant.upper()}.")
                
            except Exception as e:
                print(f"❌ ERROR: Failed to run {variant.upper()} on {project_name}: {e}")
                # Continue with the next variant instead of stopping the whole batch
                continue

if __name__ == "__main__":
    main()

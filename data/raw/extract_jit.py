import pandas as pd
import os
from pathlib import Path

def main():
    base_dir = Path("data/raw/JIT-Fine-replication-zenodo/data/jitfine")
    pkl_files = ["features_train.pkl", "features_test.pkl", "features_valid.pkl"]
    
    all_dfs = []
    for pkl in pkl_files:
        path = base_dir / pkl
        if path.exists():
            df = pd.read_pickle(path)
            # Filter only bug-fixing commits
            bug_fixes = df[df['fix'] == 'True'].copy()
            # We only need the project and the commit hash
            bug_fixes = bug_fixes[['project', 'commit_hash']]
            all_dfs.append(bug_fixes)
            
    if not all_dfs:
        print("Error: Could not find pickle files.")
        return
        
    combined_df = pd.concat(all_dfs, ignore_index=True)
    
    # Rename columns to match what our pipeline expects
    combined_df = combined_df.rename(columns={'commit_hash': 'fix_commit_hash'})
    
    # Drop duplicates just in case
    combined_df = combined_df.drop_duplicates()
    
    output_path = Path("data/raw/jit_defects4j.csv")
    combined_df.to_csv(output_path, index=False)
    
    print(f"Successfully extracted {len(combined_df)} bug-fixing commits from JIT-Fine replication package.")
    print(f"Saved to {output_path}")
    
    # Print a breakdown by project
    print("\nBreakdown by project:")
    print(combined_df['project'].value_counts())

if __name__ == "__main__":
    main()

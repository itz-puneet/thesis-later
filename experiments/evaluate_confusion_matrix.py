import pandas as pd
from pathlib import Path
import os
from sklearn.metrics import confusion_matrix, classification_report

def main():
    base_dir = Path("data/raw/JIT-Fine-replication-zenodo/data/jitfine")
    pkl_files = ["features_train.pkl", "features_test.pkl", "features_valid.pkl"]
    
    # 1. Extract Ground Truth from JIT-Fine
    print("Extracting ground truth from JIT-Fine...")
    all_dfs = []
    for pkl in pkl_files:
        path = base_dir / pkl
        if path.exists():
            df = pd.read_pickle(path)
            # We only need the project, the commit hash, and the ground truth label
            subset = df[['project', 'commit_hash', 'is_buggy_commit']].copy()
            all_dfs.append(subset)
            
    if not all_dfs:
        print("Error: Could not find pickle files.")
        return
        
    ground_truth_df = pd.concat(all_dfs, ignore_index=True)
    ground_truth_df = ground_truth_df.rename(columns={
        'commit_hash': 'commit_id',
        'is_buggy_commit': 'label_oracle'
    })
    # Ensure labels are integers
    ground_truth_df['label_oracle'] = ground_truth_df['label_oracle'].fillna(0).astype(int)
    
    # Save the ground truth for their records
    gt_output_path = Path("data/raw/jit_ground_truth.csv")
    ground_truth_df.to_csv(gt_output_path, index=False)
    print(f"Saved ground truth to {gt_output_path}")

    # 2. Compare against BSZZ predictions
    results_dir = Path("results/phase1")
    projects = ground_truth_df['project'].unique()
    
    total_y_true = []
    total_y_pred = []
    
    print("\n--- Confusion Matrices per Project ---")
    for project in projects:
        bszz_file = results_dir / f"bszz_{project}_labels.csv"
        if not bszz_file.exists():
            continue
            
        bszz_df = pd.read_csv(bszz_file)
        
        # Merge Ground Truth with BSZZ Predictions
        project_gt = ground_truth_df[ground_truth_df['project'] == project]
        merged = pd.merge(project_gt, bszz_df, on='commit_id', how='inner')
        
        if merged.empty:
            continue
            
        y_true = merged['label_oracle']
        if 'label_BSZZ' in merged.columns:
            y_pred = merged['label_BSZZ']
        else:
            y_pred = bszz_df.iloc[:, 1] # fallback to the second column
            y_pred = merged.merge(bszz_df, on='commit_id').iloc[:, -1] # ensure it's aligned
        
        total_y_true.extend(y_true)
        total_y_pred.extend(y_pred)
        
        tn, fp, fn, tp = confusion_matrix(y_true, y_pred).ravel()
        print(f"Project: {project:20} | TP: {tp:4} | TN: {tn:4} | FP: {fp:4} | FN: {fn:4}")

    # 3. Overall Results
    print("\n--- Overall Confusion Matrix ---")
    tn, fp, fn, tp = confusion_matrix(total_y_true, total_y_pred).ravel()
    print(f"Total TP: {tp}")
    print(f"Total TN: {tn}")
    print(f"Total FP: {fp}")
    print(f"Total FN: {fn}")
    print("\nOverall Classification Report:")
    print(classification_report(total_y_true, total_y_pred))

if __name__ == "__main__":
    main()

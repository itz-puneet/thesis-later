import pandas as pd
from pathlib import Path
import os
import json

def main():
    # 1. Load Ground Truth (Oracle)
    gt_file = Path("data/raw/jit_defects4j_oracle.csv")
    if not gt_file.exists():
        print(f"Error: Oracle dataset not found at {gt_file}")
        print("Please provide the true JIT-Defects4J dataset with mapping: fix_commit_hash -> true_inducing_commit_hash (as json list).")
        return
        
    ground_truth_df = pd.read_csv(gt_file)
    # Ensure it parses json lists for true inducing commits if stored as strings
    if 'true_inducing_commit_hash' in ground_truth_df.columns:
        ground_truth_df['true_inducing_commit_hash'] = ground_truth_df['true_inducing_commit_hash'].apply(
            lambda x: json.loads(x) if isinstance(x, str) else x
        )
    else:
        print("Error: Missing column 'true_inducing_commit_hash' in oracle dataset.")
        return

    # 2. Compare against SZZ predictions
    results_dir = Path("results/phase1_defect_level")
    projects = ground_truth_df['project'].unique()
    
    variants = ['bszz', 'agszz', 'maszz', 'lszz', 'rszz', 'raszz']
    
    overall_metrics = {}

    for variant in variants:
        total_tp = 0
        total_fp = 0
        total_fn = 0
        
        for project in projects:
            safe_project = project.replace('/', '_')
            res_file = results_dir / f"{variant}_{safe_project}_labels.csv"
            if not res_file.exists():
                continue
                
            res_df = pd.read_csv(res_file)
            if 'inducing_commit_hash' in res_df.columns:
                res_df['inducing_commit_hash'] = res_df['inducing_commit_hash'].apply(
                    lambda x: set(json.loads(x)) if isinstance(x, str) else set(x) if isinstance(x, list) else set()
                )
            else:
                continue
            
            # Merge Ground Truth with SZZ Predictions per project
            project_gt = ground_truth_df[ground_truth_df['project'] == project]
            merged = pd.merge(project_gt, res_df, on='fix_commit_hash', how='inner')
            
            for _, row in merged.iterrows():
                true_inducing = set(row['true_inducing_commit_hash'])
                pred_inducing = row['inducing_commit_hash']
                
                tp = len(true_inducing.intersection(pred_inducing))
                fp = len(pred_inducing - true_inducing)
                fn = len(true_inducing - pred_inducing)
                
                total_tp += tp
                total_fp += fp
                total_fn += fn
        
        # Skip if no data
        if total_tp == 0 and total_fp == 0 and total_fn == 0:
            continue
            
        print(f"\n=== Evaluating {variant.upper()} ===")
        if (total_tp + total_fp) == 0:
            precision = 0.0
        else:
            precision = total_tp / (total_tp + total_fp)
            
        if (total_tp + total_fn) == 0:
            recall = 0.0
        else:
            recall = total_tp / (total_tp + total_fn)
            
        f1 = 2 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 0.0
        
        print(f"Total TP: {total_tp}")
        print(f"Total FP: {total_fp}")
        print(f"Total FN: {total_fn}")
        print(f"Precision: {precision:.4f}")
        print(f"Recall: {recall:.4f}")
        print(f"F1-Score: {f1:.4f}")
        
        overall_metrics[variant] = {
            'TP': total_tp, 'FP': total_fp, 'FN': total_fn,
            'Precision': precision, 'Recall': recall, 'F1': f1
        }
        
    if overall_metrics:
        # Save bias metrics for phase 3
        bias_output = Path("phase1_defect_level_bias.json")
        with open(bias_output, 'w') as f:
            json.dump(overall_metrics, f, indent=4)
            print(f"\nSaved overall metrics to {bias_output}")

if __name__ == "__main__":
    main()

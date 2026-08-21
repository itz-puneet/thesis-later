import pandas as pd
from pathlib import Path
import json

def main():
    # 1. Load Ground Truth (JIT-Fine)
    gt_file = Path("data/raw/jit_ground_truth.csv")
    if not gt_file.exists():
        print(f"Error: Ground truth dataset not found at {gt_file}")
        return
        
    gt_df = pd.read_csv(gt_file)
    if 'label_oracle' not in gt_df.columns or 'commit_id' not in gt_df.columns:
        print("Error: Missing 'label_oracle' or 'commit_id' in ground truth dataset.")
        return

    print(f"Loaded ground truth with {len(gt_df)} commits.")
    
    variants = ['BSZZ', 'AGSZZ', 'MASZZ', 'LSZZ', 'RSZZ', 'RASZZ']
    overall_metrics = {}
    results_dir = Path("results/phase1")

    for variant in variants:
        print(f"\n=== Evaluating {variant} ===")
        
        # Load all prediction files for this variant
        pred_files = list(results_dir.glob(f"{variant.lower()}_*_labels.csv"))
        if not pred_files:
            print(f"No prediction files found for {variant}")
            continue
            
        dfs = []
        for f in pred_files:
            try:
                dfs.append(pd.read_csv(f))
            except Exception as e:
                pass
                
        if not dfs:
            continue
            
        pred_df = pd.concat(dfs, ignore_index=True)
        label_col = f'label_{variant}'
        
        if label_col not in pred_df.columns:
            print(f"Missing {label_col} in predictions")
            continue
            
        # Merge with ground truth
        merged = pd.merge(gt_df, pred_df, on='commit_id', how='inner')
        if len(merged) == 0:
            print("No matching commits between ground truth and predictions.")
            continue
            
        # Calculate confusion matrix components
        tp = len(merged[(merged['label_oracle'] == 1) & (merged[label_col] == 1)])
        fp = len(merged[(merged['label_oracle'] == 0) & (merged[label_col] == 1)])
        fn = len(merged[(merged['label_oracle'] == 1) & (merged[label_col] == 0)])
        tn = len(merged[(merged['label_oracle'] == 0) & (merged[label_col] == 0)])

        precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        f1 = 2 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 0.0

        print(f"Total Evaluated Commits: {len(merged)}")
        print(f"Total TP: {tp}")
        print(f"Total FP: {fp}")
        print(f"Total FN: {fn}")
        print(f"Total TN: {tn}")
        print(f"Precision: {precision:.4f}")
        print(f"Recall: {recall:.4f}")
        print(f"F1-Score: {f1:.4f}")
        
        overall_metrics[variant] = {
            'TP': tp, 'FP': fp, 'FN': fn, 'TN': tn,
            'Precision': precision, 'Recall': recall, 'F1': f1
        }
        
    if overall_metrics:
        # Save bias metrics
        bias_output = Path("phase1_bias.json")
        with open(bias_output, 'w') as f:
            json.dump(overall_metrics, f, indent=4)
            print(f"\nSaved overall metrics to {bias_output}")

if __name__ == "__main__":
    main()

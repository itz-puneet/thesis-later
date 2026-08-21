#!/usr/bin/env python3
"""Replication experiment: Run ORB across all 14 datasets from Cabral et al. (ICSE 2019).

Evaluates across 10 random seeds with Prequential Streaming and 90-day verification latency.
"""
import glob
import os
from pathlib import Path
import sys
from pathlib import Path
import heapq
import numpy as np
import pandas as pd
from tqdm import tqdm

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.append(str(BASE_DIR))

from codebase.online.orb import ORB
from codebase.evaluation.metrics import PrequentialTracker
from codebase.config import ORB_CONFIG, RANDOM_SEEDS

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data" / "raw" / "cabral2019" / "extracted" / "geocabral-spdisc-icse19-0a7955c" / "datasets"
OUT_DIR = BASE_DIR / "results" / "replication"
OUT_DIR.mkdir(parents=True, exist_ok=True)

def parse_arff(path):
    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        lines = f.readlines()
    data_idx = 0
    attr_names = []
    for i, line in enumerate(lines):
        line_clean = line.strip()
        if line_clean.lower().startswith("@attribute"):
            parts = line_clean.split()
            attr_names.append(parts[1])
        elif line_clean.lower() == "@data":
            data_idx = i + 1
            break
    
    rows = []
    for line in lines[data_idx:]:
        line_clean = line.strip()
        if not line_clean or line_clean.startswith("%"):
            continue
        parts = [p.strip() for p in line_clean.split(",")]
        if len(parts) == len(attr_names):
            rows.append(parts)
    
    df = pd.DataFrame(rows, columns=attr_names)
    df["fix"] = df["fix"].apply(lambda x: 1 if str(x).lower() == "true" else 0)
    for c in ["ns", "nd", "nf", "entrophy", "la", "ld", "lt", "ndev", "age", "nuc", "exp", "rexp", "sexp"]:
        df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0.0)
    df = df.rename(columns={"entrophy": "entropy"})
    df["contains_bug"] = df["contains_bug"].apply(lambda x: 1 if str(x).lower() == "true" else 0)
    df["author_date_unix_timestamp"] = pd.to_numeric(df["author_date_unix_timestamp"], errors="coerce").fillna(0.0)
    df["commit_type"] = pd.to_numeric(df["commit_type"], errors="coerce").fillna(0).astype(int)
    return df

def run_project(arff_path, seed):
    features = ["ns", "nd", "nf", "entropy", "la", "ld", "lt", "fix", "ndev", "age", "nuc", "exp", "rexp", "sexp"]
    df = parse_arff(arff_path)
    df = df.sort_values("author_date_unix_timestamp").reset_index(drop=True)
    
    X = df[features].to_numpy(dtype=float)
    y = df["contains_bug"].to_numpy(dtype=int)
    t = df["author_date_unix_timestamp"].to_numpy(dtype=float)
    c_type = df["commit_type"].to_numpy(dtype=int)
    
    orb = ORB(seed=seed, **ORB_CONFIG)
    tracker = PrequentialTracker(fading=0.99)
    pending = []
    W = 90 * 86400.0
    
    for i in range(len(df)):
        now = t[i]
        while pending and pending[0][0] <= now:
            _, j, lab = heapq.heappop(pending)
            orb.learn_one(X[j], lab)
        
        pred = orb.predict_one(X[i])
        tracker.update(y[i], pred, ts=now)
        
        if y[i] == 1:
            if c_type[i] == 2:
                heapq.heappush(pending, (now + 1.0, i, 1))
            else:
                heapq.heappush(pending, (now + W, i, 0))
                heapq.heappush(pending, (now + W + 1000.0, i, 1))
        else:
            heapq.heappush(pending, (now + W, i, 0))
            
    return {
        "project": os.path.basename(arff_path).replace(".arff", ""),
        "seed": seed,
        "n_commits": len(df),
        "defect_ratio": float(y.mean()),
        "gmean": tracker.gmean(),
        "mcc": tracker.mcc(),
    }

def main():
    arff_files = sorted(glob.glob(str(DATA_DIR / "*.arff")))
    print(f"Found {len(arff_files)} Cabral et al. (2019) project datasets.")
    
    records = []
    for arff_path in tqdm(arff_files, desc="Projects"):
        for seed in RANDOM_SEEDS:
            rec = run_project(arff_path, seed)
            records.append(rec)
            
    df_res = pd.DataFrame(records)
    out_csv = OUT_DIR / "cabral2019_orb_replication.csv"
    df_res.to_csv(out_csv, index=False)
    print(f"\nSaved replication results to {out_csv}")
    
    summary = df_res.groupby("project").agg({
        "n_commits": "first",
        "defect_ratio": "first",
        "gmean": ["mean", "std"],
        "mcc": ["mean", "std"]
    }).reset_index()
    
    print("\n" + "=" * 80)
    print("CABRAL ET AL. (ICSE 2019) DATASET — ORB REPLICATION RESULTS (10 SEEDS)")
    print("=" * 80)
    for _, row in summary.iterrows():
        p = row['project'].iloc[0] if isinstance(row['project'], pd.Series) else row['project']
        n = int(row[('n_commits', 'first')])
        dr = row[('defect_ratio', 'first')] * 100
        gm_m = row[('gmean', 'mean')]
        gm_s = row[('gmean', 'std')]
        mcc_m = row[('mcc', 'mean')]
        mcc_s = row[('mcc', 'std')]
        print(f"  {p:20s} | N={n:5d} | Buggy={dr:4.1f}% | G-Mean = {gm_m:.4f} (±{gm_s:.3f}) | MCC = {mcc_m:.4f} (±{mcc_s:.3f})")
    
    print("-" * 80)
    overall_gm = df_res['gmean'].mean()
    overall_mcc = df_res['mcc'].mean()
    overall_dr = df_res['defect_ratio'].mean() * 100
    print(f"OVERALL MEAN (14 Projects × 10 Seeds):")
    print(f"  Defect Rate: {overall_dr:.1f}%")
    print(f"  G-Mean:      {overall_gm:.4f}")
    print(f"  MCC:         {overall_mcc:.4f}")
    print("=" * 80)

if __name__ == "__main__":
    main()

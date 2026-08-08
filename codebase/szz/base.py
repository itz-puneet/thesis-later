import json
import subprocess
from pathlib import Path
import pandas as pd
import tempfile
import sys
import shutil

class BaseSZZ:
    """
    Base SZZ Implementation wrapping pyszz_v2.
    """
    def __init__(self, pyszz_dir: str, algorithm: str):
        self.algorithm = algorithm.lower()
        self.name = self.algorithm.upper()
        self.pyszz_dir = Path(pyszz_dir).resolve()
        self.conf_file = self.pyszz_dir / "conf" / f"{self.algorithm}.yml"

    def _get_all_commits(self, repo_path: str) -> pd.DataFrame:
        cmd = ["git", "-C", repo_path, "log", "--format=%H"]
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        commits = result.stdout.strip().split('\n')
        return pd.DataFrame({'commit_id': [c for c in commits if c]})

    def label(self, repo_path: str, fixes: pd.DataFrame) -> pd.DataFrame:
        repo_path_obj = Path(repo_path).resolve()
        
        if not self.conf_file.exists():
            raise FileNotFoundError(f"Configuration file not found for variant '{self.algorithm}': {self.conf_file}")

        bugfix_list = []
        hash_col = 'fix_commit_hash' if 'fix_commit_hash' in fixes.columns else fixes.columns[0]
        
        for _, row in fixes.iterrows():
            bugfix_list.append({
                "fix_commit_hash": str(row[hash_col]),
                "repo_name": repo_path_obj.name
            })
            
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json') as tmp_json:
            json.dump(bugfix_list, tmp_json)
            tmp_json_path = Path(tmp_json.name)

        try:
            out_dir = self.pyszz_dir / "out"
            if out_dir.exists():
                for old_file in out_dir.glob("*.json"):
                    old_file.unlink()

            cmd = [
                sys.executable, "main.py",
                str(tmp_json_path),
                str(self.conf_file),
                str(repo_path_obj.parent) 
            ]
            
            print(f"Running pyszz_v2 for {self.name}...")
            result = subprocess.run(cmd, cwd=self.pyszz_dir, capture_output=True, text=True)
            
            if result.returncode != 0:
                raise RuntimeError(f"PySZZ failed for {self.name}.\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}")

            inducing_commits = set()
            if out_dir.exists():
                for result_file in out_dir.glob("*.json"):
                    with open(result_file, 'r') as f:
                        data = json.load(f)
                        for bug in data:
                            if bug.get("repo_name") != repo_path_obj.name:
                                continue
                            inducing_list = bug.get('inducing_commit_hash', bug.get('inducing_commits', []))
                            for inducing in inducing_list:
                                inducing_commits.add(inducing)

            df_all = self._get_all_commits(repo_path)
            df_all[f'label_{self.name}'] = df_all['commit_id'].apply(lambda x: 1 if x in inducing_commits else 0)
            
            return df_all

        finally:
            tmp_json_path.unlink(missing_ok=True)

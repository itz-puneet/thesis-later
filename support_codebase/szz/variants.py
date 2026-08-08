"""SZZ variant labeling.

For real experiments use pyszz_v2 (https://github.com/grosa1/pyszz_v2), which
implements B/AG/MA/RA/R-SZZ. This module defines the uniform interface the rest
of the pipeline expects, plus adapters. Each variant maps a set of bug-fixing
commits to the commits it blames as bug-inducing; we then project that onto a
per-commit binary label column: label_<VARIANT>.
"""
from __future__ import annotations

import subprocess
from abc import ABC, abstractmethod
from pathlib import Path

import pandas as pd


class SZZVariant(ABC):
    name: str = "abstract"

    @abstractmethod
    def label(self, repo_path: str, fixes: pd.DataFrame) -> pd.DataFrame:
        """Return DataFrame[commit_id, inducing(0/1)] for all commits in repo.

        Parameters
        ----------
        repo_path : local clone of the subject project
        fixes     : DataFrame[fix_commit_id, issue_id] linking fixes to bugs
        """


class PySZZAdapter(SZZVariant):
    """Adapter that shells out to pyszz_v2 with the matching YAML config.

    pyszz config names: 'b' -> B-SZZ, 'ag' -> AG-SZZ, 'ma' -> MA-SZZ,
    'ra' -> RA-SZZ, 'r' -> R-SZZ (see pyszz conf/ directory).
    """

    CONF = {"B-SZZ": "bszz", "AG-SZZ": "agszz", "MA-SZZ": "maszz",
            "RA-SZZ": "raszz", "R-SZZ": "rszz"}

    def __init__(self, name: str, pyszz_dir: str):
        self.name = name
        self.pyszz_dir = Path(pyszz_dir)

    def label(self, repo_path: str, fixes: pd.DataFrame) -> pd.DataFrame:
        conf = self.pyszz_dir / "conf" / f"{self.CONF[self.name]}.yml"
        # 1) write fixes to the JSON format pyszz expects
        # 2) run: python main.py <bugfix_json> <conf> <repos_dir>
        # 3) parse pyszz output JSON -> inducing commit set
        raise NotImplementedError(
            f"Wire pyszz here, e.g.:\n"
            f"  subprocess.run(['python', 'main.py', bugfix_json, '{conf}', repos_dir], "
            f"cwd='{self.pyszz_dir}')\n"
            f"then map inducing commit hashes -> label_{self.name}=1."
        )


def attach_precomputed_labels(commits: pd.DataFrame,
                              labels_csv: str,
                              variant: str) -> pd.DataFrame:
    """Merge precomputed SZZ output (commit_id, inducing) as label_<variant>."""
    lab = pd.read_csv(labels_csv)[["commit_id", "inducing"]]
    out = commits.merge(lab, on="commit_id", how="left")
    out[f"label_{variant}"] = out.pop("inducing").fillna(0).astype(int)
    return out

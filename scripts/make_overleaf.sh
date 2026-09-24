#!/usr/bin/env bash
# Package the Phase 1-2 interim report as a self-contained Overleaf project.
#
#   ./scripts/make_overleaf.sh
#     -> overleaf_report/      folder (diffable, committed)
#     -> overleaf_report.zip   upload this to Overleaf
#
# Regenerates the LaTeX from report/*.md first, so the package never lags the
# markdown. Paths are flattened: chapters/ and figures/ sit beside main.tex,
# and nothing points outside the folder.
set -euo pipefail
cd "$(dirname "$0")/.."

./scripts/md_to_tex.sh report

rm -rf overleaf_report overleaf_report.zip
mkdir -p overleaf_report/chapters overleaf_report/figures

for f in $(grep -oh "reports/figures/[a-z0-9_]*\.png" tex_report/*.tex | sort -u); do
  cp "$f" overleaf_report/figures/
done
for f in tex_report/*.tex; do
  sed 's|{reports/figures/|{figures/|g' "$f" > "overleaf_report/chapters/$(basename "$f")"
done
sed -e 's|\\input{tex_report/|\\input{chapters/|g' \
    -e 's|\\graphicspath{{\./}{reports/figures/}}|\\graphicspath{{./}{figures/}}|' \
    report_main.tex > overleaf_report/main.tex

# The header comment in report_main.tex describes the repository layout, which
# is wrong once the folder stands alone.
python3 - <<'PY'
from pathlib import Path
p = Path("overleaf_report/main.tex"); s = p.read_text()
a, b = s.index("%  SOURCES report/*.md"), s.index("%  ENGINE")
s = s[:a] + """%  LAYOUT  main.tex          this file -- all document-level formatting
%          chapters/*.tex    chapter bodies, generated from markdown
%          figures/*.png     the nine figures, referenced by bare filename
%
%          The chapter bodies are GENERATED. If you edit them here, keep a
%          note of what you changed: regenerating from the source markdown
%          will overwrite them.
%
""" + s[b:]
s = s.replace("%  BUILD   latexmk -pdf report_main.tex",
              "%  BUILD   Overleaf: set main.tex as the main document, compiler pdfLaTeX.\n"
              "%          Locally:  latexmk -pdf main.tex")
p.write_text(s)
PY

cp references.bib overleaf_report/
[ -f README_overleaf.md ] && cp README_overleaf.md overleaf_report/README.md

# Refuse to ship a package that references anything outside itself.
python3 - <<'PY'
import re, pathlib, sys
root = pathlib.Path("overleaf_report"); ok = True
s = (root / "main.tex").read_text()
for i in re.findall(r"^\\input\{(.*?)\}", s, re.M):
    if not (root / (i + ".tex")).exists():
        print("MISSING input:", i); ok = False
for t in root.glob("chapters/*.tex"):
    for g in re.findall(r"\\includegraphics\[[^\]]*\]\{(.*?)\}", t.read_text()):
        if not (root / "figures" / pathlib.Path(g).name).exists():
            print("MISSING figure:", g); ok = False
bib = set(re.findall(r"^@\w+\{([^,]+),", (root / "references.bib").read_text(), re.M))
cited = set()
for t in root.glob("chapters/*.tex"):
    for c in re.findall(r"\\cite[tp]?\{([^}]*)\}", t.read_text()):
        cited |= {k.strip() for k in c.split(",")}
missing = sorted(cited - bib)
if missing:
    print("CITED BUT NOT IN references.bib:", missing); ok = False
else:
    print(f"bibliography: {len(bib)} entries, {len(cited)} cited, all resolve")
n = sum(sum(1 for c in p.read_text() if ord(c) > 127) for p in root.rglob("*.tex"))
if n: print(f"WARNING: {n} non-ASCII characters remain; pdfLaTeX may fail")
if not ok: sys.exit("package is not self-contained")
print("package verified: all inputs and figures resolve inside the folder")
PY

( cd overleaf_report && zip -qr ../overleaf_report.zip . )
echo "overleaf_report.zip  $(du -h overleaf_report.zip | cut -f1)"

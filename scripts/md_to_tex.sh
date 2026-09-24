#!/usr/bin/env bash
# Regenerate LaTeX bodies from markdown.
#   ./scripts/md_to_tex.sh            chapters/ -> tex/          (thesis_main.tex)
#   ./scripts/md_to_tex.sh report     report/   -> tex_report/   (report_main.tex)
#
# The generated files are overwritten every run -- edit the markdown, not the
# LaTeX. Unicode is mapped to LaTeX commands here so the document builds under
# pdfLaTeX without fontspec.
set -euo pipefail
cd "$(dirname "$0")/.."
if [ "${1:-}" = "report" ]; then SRC=report; OUT=tex_report; else SRC=chapters; OUT=tex; fi
mkdir -p "$OUT"
for f in "$SRC"/0[1-9]_*.md; do
  pandoc "$f" -f markdown -t latex --top-level-division=chapter --natbib \
    -o "$OUT/$(basename "$f" .md).tex"
done
export SRC OUT
python3 - <<'PY'
import re, pathlib, subprocess
MATH = {"ρ":r"\rho","κ":r"\kappa","λ":r"\lambda","δ":r"\delta","₀":"_0","₁":"_1",
        "×":r"\times","≈":r"\approx","≥":r"\geq","≤":r"\leq","±":r"\pm","÷":r"\div",
        "−":"-","∈":r"\in","→":r"\rightarrow","ℝ":r"\mathbb{R}","·":r"\cdot",
        "●":r"\bullet","○":r"\circ","◐":r"\odot"}
# Box-drawing goes to ASCII: pdfLaTeX has no glyphs for it, and the only use
# is the pipeline diagram inside a verbatim block.
TEXT = {"§":r"\S{}","Ś":r"\'{S}","ã":r"\~{a}","─":"-","│":"|","┼":"+","┐":"+",
        "┴":"+","├":"+","└":"+","┌":"+","►":">","▼":"v","✅":r"\textbf{pass}",
        "❌":r"\textbf{fail}","➖":"--","✓":r"\checkmark","✗":"x"}

def clean(s):
    s = re.sub(r"\\begin\{center\}\s*\\rule\{0\.5\\linewidth\}\{0\.5pt\}\s*\\end\{center\}\s*","",s)
    s = s.replace("{../reports/figures/", "{reports/figures/")
    s = re.sub(r"\\pandocbounded\{\\includegraphics\[keepaspectratio,alt=\{.*?\}\]\{(.*?)\}\}",
               lambda m: f"\\includegraphics[width=\\linewidth,keepaspectratio]{{{m.group(1)}}}",
               s, flags=re.S)
    s = re.sub(r"\\includegraphics\[width=\\linewidth,keepaspectratio\]\{(.*?)\}",
               lambda m: m.group(0) + f"\n\\label{{fig:{pathlib.Path(m.group(1)).stem}}}", s)
    for u,t in MATH.items(): s = s.replace(u, f"\\ensuremath{{{t}}}")
    for u,t in TEXT.items(): s = s.replace(u, t)
    return s

import os
OUT = os.environ.get("OUT", "tex"); SRC = os.environ.get("SRC", "chapters")
for p in sorted(pathlib.Path(OUT).glob("0[1-9]*.tex")):
    p.write_text(clean(p.read_text()))

src = pathlib.Path(f"{SRC}/00_front_matter.md").read_text()
# Split the front matter on its section headings. The trailing section is
# optional, so an absent end marker means "to the end of the file" rather
# than an error -- the two trees do not carry identical front matter.
for name, start, end in [("00_abstract", "## Abstract", "## Abbreviations"),
                         ("00_abbreviations", "## Abbreviations", None)]:
    if start not in src:
        continue
    a = src.index(start)
    b = src.index(end) if (end and end in src) else len(src)
    md = src[a:b].replace(start, "").strip().rstrip("-").strip()
    out = subprocess.run(["pandoc","-f","markdown","-t","latex"],
                         input=md, text=True, capture_output=True).stdout
    pathlib.Path(f"{OUT}/{name}.tex").write_text(clean(out))

bad = {p.name: sum(1 for c in p.read_text() if ord(c) > 127)
       for p in pathlib.Path(OUT).glob("*.tex")}
left = {k: v for k, v in bad.items() if v}
print(f"regenerated {OUT}/ ;", "non-ASCII remaining:", left if left else "none")
PY

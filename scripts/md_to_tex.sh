#!/usr/bin/env bash
# Regenerate tex/*.tex from chapters/*.md for thesis_main.tex.
#
# The generated files are overwritten every run -- edit the markdown, not the
# LaTeX. Unicode is mapped to LaTeX commands here so the document builds under
# pdfLaTeX without fontspec.
set -euo pipefail
cd "$(dirname "$0")/.."
mkdir -p tex
for f in chapters/0[1-9]_*.md; do
  pandoc "$f" -f markdown -t latex --top-level-division=chapter \
    -o "tex/$(basename "$f" .md).tex"
done
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

for p in sorted(pathlib.Path("tex").glob("0[1-9]*.tex")):
    p.write_text(clean(p.read_text()))

src = pathlib.Path("chapters/00_front_matter.md").read_text()
for name, start, end in [("00_abstract","## Abstract","## Abbreviations"),
                         ("00_abbreviations","## Abbreviations","## A note on corrections")]:
    md = src[src.index(start):src.index(end)].replace(start,"").strip().rstrip("-").strip()
    out = subprocess.run(["pandoc","-f","markdown","-t","latex"],
                         input=md, text=True, capture_output=True).stdout
    pathlib.Path(f"tex/{name}.tex").write_text(clean(out))

bad = {p.name: sum(1 for c in p.read_text() if ord(c) > 127)
       for p in pathlib.Path("tex").glob("*.tex")}
left = {k: v for k, v in bad.items() if v}
print("regenerated tex/ ;", "non-ASCII remaining:", left if left else "none")
PY

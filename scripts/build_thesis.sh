#!/usr/bin/env bash
# Assemble chapters/ into Thesis_Draft.pdf, and rebuild the synthesis PDF.
# Fails loudly if pandoc or Chrome is missing, and verifies the page count --
# a silent one-page PDF is the failure mode this script exists to prevent.
set -euo pipefail
cd "$(dirname "$0")/.."
OUT="${TMPDIR:-/tmp}/thesis-build"; mkdir -p "$OUT"
CSS="scripts/thesis_style.css"
[ -f "$CSS" ] || { echo "missing $CSS" >&2; exit 1; }

build() {  # build <source.md> <output.pdf> [--toc]
  local src="$1" pdf="$2"; shift 2
  pandoc "$src" -f markdown -t html5 --standalone --embed-resources "$@" \
    --resource-path=.:chapters:reports/figures -c "$CSS" -o "$OUT/page.html"
  google-chrome --headless --disable-gpu --no-sandbox --no-pdf-header-footer \
    --print-to-pdf="$OUT/page.pdf" "file://$OUT/page.html" 2>/dev/null
  cp "$OUT/page.pdf" "$pdf"
  python3 - "$pdf" <<'PY'
import re, sys
d = open(sys.argv[1], "rb").read()
pages = len(re.findall(rb"/Type\s*/Page[^s]", d))
imgs  = len(re.findall(rb"/Subtype\s*/Image", d))
print(f"{sys.argv[1]}: {pages} pages, {imgs} images")
if pages < 5:
    sys.exit(f"ERROR: {sys.argv[1]} has only {pages} pages -- build failed silently")
PY
}

cat chapters/00_front_matter.md > "$OUT/thesis.md"
for f in chapters/0[1-9]_*.md; do printf '\n\n---\n\n' >> "$OUT/thesis.md"; cat "$f" >> "$OUT/thesis.md"; done
build "$OUT/thesis.md" Thesis_Draft.pdf --toc --toc-depth=2
build Thesis_Comprehensive_Synthesis.md Thesis_Comprehensive_Synthesis.pdf

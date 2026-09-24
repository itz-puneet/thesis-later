# Interim Report — Phases 1 and 2

Upload this folder (or the accompanying `.zip`) to Overleaf.

## Settings

| | |
|---|---|
| **Main document** | `main.tex` |
| **Compiler** | **pdfLaTeX** |

Overleaf usually detects both automatically. If the build fails immediately,
check them first under *Menu → Settings*.

pdfLaTeX is deliberate rather than incidental: every Unicode character in the
source — Greek letters, mathematical symbols, the box-drawing in the Chapter 3
pipeline diagram — was mapped to a LaTeX command when these files were
generated, so no `fontspec` and no XeLaTeX are required.

## Layout

```
main.tex            all document-level formatting; hand-written
chapters/*.tex      chapter bodies (generated — see below)
figures/*.png       the nine figures, referenced by bare filename
references.bib      33 entries, all cited
```

## Bibliography

Citations use `natbib` with `plainnat`, which ships with natbib, so nothing
extra needs installing. Overleaf runs BibTeX automatically; locally you need
the usual `pdflatex → bibtex → pdflatex → pdflatex` cycle, or just `latexmk`.

**Seven entries carry a `NEEDS-CHECK` note** naming a field that could not be
confirmed — usually a page range, a volume, or an author list abbreviated to
`and others`. Search the file for `NEEDS-CHECK` and complete those against the
publisher records before submission. Everything else was verified against a
publisher record or the source.

## Editing

`main.tex` is the place to change margins, fonts, spacing, the title page and
anything else document-wide.

**The files in `chapters/` are generated** from markdown held in the project
repository. Editing them here works, but a regeneration upstream will discard
the change, so note anything you alter.

## Packages used

All are standard on Overleaf's TeX Live: `geometry`, `setspace`, `microtype`,
`footmisc`, `amsmath`, `amssymb`, `longtable`, `booktabs`, `array`, `calc`,
`etoolbox`, `graphicx`, `caption`, `fancyhdr`, `xcolor`, `framed`, `hyperref`,
`url`, `lmodern`, `textcomp`.

## Two things to expect

**Wide tables.** The Phase 2 results matrix in Chapter 5 runs to six columns.
All `longtable` environments are set to `\footnotesize` globally in `main.tex`;
if a table still overruns the margin, either drop that one to
`\scriptsize` or transpose it.

**No List of Tables.** It is commented out in `main.tex` because the generated
tables carry no `\caption`, so the list would come out empty. If your
submission requires one, the tables need captions adding first.

## Scope

This report covers Phase 1 (SZZ label quality) and Phase 2 (downstream impact
under honest evaluation) only. Chapter 6 states what is deliberately left open
and gives the design for the remaining phases. It is not a truncated thesis —
the forward references have been rewritten throughout, so nothing here cites a
result it does not present.

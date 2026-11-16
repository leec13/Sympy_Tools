# Changelog

## v0.1.0 — 2026-11-16
First version, specified with the user before development (`docs/spec_v0.1.md`).
- Input: one expression, or an equation (lhs, rhs). Pasting `a = b` into Expression splits it.
- Checked reading through the model: invalid moment names are errors, codes are reordered,
  symbols outside the model are accepted and listed, non-numeric exponents give a warning
  (`a** + b`), `^` is read as `**`, `dX/dt` as `dX_dt`. SymPy's own names are never used.
- Operations: Simplify, Factor, Expand, Collect by (one symbol, or all moments: one
  coefficient per product of moments), Compare
  (equal / different / undetermined, with lhs − rhs grouped by moment). The SymPy code
  that runs is shown.
- Output: Python text, LaTeX code, LaTeX rendered with TeX Live (breqn); copy as Python,
  LaTeX for Keynote, LaTeX for Overleaf (dmath*) or image. "Use as input" chains operations.
- Model: latex-preview `.ini` (French or English names) + optional `[hypotheses]` section
  (SymPy assumptions). Edit, Load and Save as.
- Computations run in a separate process (Stop button, 60 s limit).

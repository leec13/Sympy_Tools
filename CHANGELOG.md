# Changelog

## v0.2.0 — 2026-11-16
Specified with the user before development (`docs/spec_v0.2.md`, cases 16 to 26).
- **Isserlis (order 3)**: third-order moments T_… replaced by
  <ab><c> + <ac><b> + <bc><a> - 2<a><b><c> (= moment_closure.py level 2).
- **Substitute definitions**: r_A1… replaced by their formula from [definitions]
  (nested definitions are followed, circular ones are an error).
- **Recognize definitions**: the formulas rewritten with r_A1…, coefficient by coefficient
  (one per product of moments), only where the decomposition is exact and unique;
  other coefficients are kept and listed; the result is checked.
- The three buttons are greyed out when they have nothing to do.
- Dark theme (always on); the LaTeX preview stays a white sheet with black text.
- SymPy code pane: three lines.

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

# Changelog

## v0.5.0 — 2026-11-17
Specified with the user before development (`docs/spec_v0.5.md`, cases 46 to 53).
- Default model: omega_A1… = s*(x - th)**2 (death rate by selection, same LaTeX as
  latex-preview), r_A1 = rmaxA - omega_A1, deaths written with omega. Symmetries swap
  the omegas (derived from the definitions). Older saved defaults (v0.1-v0.4) are updated.
- Compare always substitutes the definitions first ("after substituting definitions").
- Recognize definitions: substitutes everything, then the shortest exact writing per
  coefficient; rmaxA may stay with its own coefficient, never added nor changed. With
  overlapping definitions (r = rmax - omega) birth + death reads rmaxA + omega_A1; with
  the r only, results are those of v0.2.
- Substitute definitions: everything at once, down to the base parameters (unchanged).

## v0.4.1 — 2026-11-17
- Tests are isolated from the user's preferences (`SYMPY_TOOLS_SETTINGS`, set in
  `tests/conftest.py`). On macOS they used to read, and write, the real preferences, so
  a model saved before v0.4 (no events) made Generate fail during the tests.
- A message box can no longer block a test without a display: it is recorded and the
  test fails with its text.
- A copy of an older default model saved in the preferences (v0.1-v0.3, no events) is
  replaced by the current default at start-up; Edit model… keeps "default" when the text
  is the default.
- A model without [evenements] is reported in the status bar (Generate and Events… need
  it; Edit model… → Reset to default adds them).

## v0.4.0 — 2026-11-17
Specified with the user before development (`docs/spec_v0.4.md`, cases 36 to 45).
- The model declares the stochastic process, `[evenements]` (one line per event: rate | jump),
  and its symmetries, `[symetries]` (swaps of codes and parameters). The default model has
  the 12 events of moment_closure.py and the phenotypes / niches symmetries; combinations
  are added; r_A1… follow from their definitions. Rates and jumps are checked on loading.
- **Events…**: compiled table of every event and its image by each symmetry, ✓ / ✗.
- **Generate d/dt**: equation of a moment event by event, E(w·Δf, event), as the input;
  LaTeX labels each term with its event.
- **Take moments**: E(…) -> moments, grouped by event.
- **Symmetry ▾ Apply**: swaps moments, variables, parameters, r_… and event names;
  says when an equation is invariant; warns when the symmetry does not hold for the events.
- Checked: Generate -> Take moments -> Isserlis = moment_closure.py level 2, for its 14 equations.

## v0.3.0 — 2026-11-17
Specified with the user before development (`docs/spec_v0.3.md`, cases 27 to 35).
- **Chained operations**: each operation applies to the result shown, not to the input.
  Before, Isserlis then Collect by all moments brought the T_… back, because Collect
  started again from the input.
- The input is never changed; **↺ Back to input** forgets the chain (as do editing the
  input, or changing the mode or the model).
- Title and SymPy code show every step; the code pane grows up to 7 lines.
- The Collect by list and the Isserlis / definitions buttons follow the current result.
- Compare checks the current equation without replacing it.
- No Undo button (decision of 17/11/2026).

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
- Visual identity: light, with a teal band at the top, a tinted background and a tinted
  SymPy code pane (a dark theme was tried and dropped: too dark). The LaTeX preview stays
  a white sheet with black text.
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

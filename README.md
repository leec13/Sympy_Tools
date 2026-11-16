# Sympy Tools

A small macOS app to **apply SymPy operations to population-dynamics expressions**, mainly moment equations. You paste an expression, or the two sides of an equation, as Python-like text (for example the output of latex-preview's Translation panel). The app checks how it read the input and applies Simplify, Factor, Expand, Collect by or Compare. You copy the result as Python (for VS Code or a notebook) or as LaTeX (for Overleaf or Keynote).

It follows on from [latex-preview](https://github.com/leec13/latex-preview): it uses the same model file (`.ini`) and the same TeX Live rendering.

## Installation (macOS, once)

Prerequisites: conda, TeX Live / MacTeX, and a clone of **latex-preview next to this folder**.

**Simplest: reuse the latex-preview environment.** It already contains everything:

```bash
cd Sympy_Tools
conda activate latex-preview
pip install -e .
```

**Or create a separate environment:**

```bash
cd Sympy_Tools
conda env create -f environment.yml
conda activate sympy-tools
pip install -e ../latex-preview
pip install -e .
```

## Launch

```bash
sympy-tools            # or: python -m sympy_tools
```

## Input

- **Expression**: one field, e.g. `2*M_A1_A1 + M_A1_A2/KA`.
- **Equation**: two fields, `lhs` and `rhs`. If you paste a text containing `=` into the Expression field (`dM_A1_A1_dt = …`), the app splits it and switches to Equation mode.

Names come from the model (default: two niches A, B and two phenotypes x1, x2):

| Written | Meaning |
|---|---|
| `NA1, NA2, NB1, NB2` | state variables N{code} |
| `n_A1`, `M_A1_A2`, `T_A1_A1_B2`, `Q_…` | moments of order 1, 2, 3, 4, with codes in the order A1, A2, B1, B2 |
| `dM_A1_A2_dt` | derivative d⟨…⟩/dt (`dM_A1_A2/dt` is accepted too) |
| `m, s, x1, thA, rmaxA, KA, r_A1…` | model parameters |
| `exp, log, sqrt, sin, cos, tan, Abs…`, `pi` | functions and constant |

**The reading is checked**, and the "Read as" line always shows the result:

| You write | The app |
|---|---|
| `M_A1_MA1`, `n_total` | ✗ error: unknown code |
| `M_A1_A1_A2` | ✗ error: 3 indices, so `T_A1_A1_A2` |
| `M_A2_A1` | reads `M_A1_A2` (ⓘ reordered) |
| `delta*n_A1` | accepts `delta` (ⓘ not in model) |
| `2*M_A1_A1** + M_A1_A1` | ⚠ non-numeric exponent: Python reads `a** + b` as a**(+b) |
| `n_A1^2` | reads `n_A1**2` |
| `s(x1 - thA)**2` | ✗ `s` is not a function: did you mean `s*(…)`? |
| `lambda`, LaTeX, `;`… | ✗ clear error |

SymPy's own names (`N`, `S`, `E`, `I`, `Q`, `gamma`…) are never used: here they are ordinary symbols.

## Operations

On an equation, each operation is applied to each side. The **SymPy code** pane shows the line that really ran.

| Button | SymPy | Shortcut |
|---|---|---|
| Simplify | `sp.simplify(expr)` | ⌘1 |
| Factor | `sp.factor(expr)` | ⌘2 |
| Expand | `sp.expand(expr)` | ⌘3 |
| Collect by ▾ | `sp.collect(sp.expand(expr), v)`; the list contains every symbol read, grouped, plus *all moments* | ⌘4 |
| Compare | `sp.cancel(lhs - rhs) == 0`, or `sp.simplify` with exp, sqrt… | ⌘5 |

- **Collect by** expands first, so a factored form is lost. With *all moments*, it collects by every product of moments present (`n_A1*M_A1_B1`, …, then `n_A1`, `M_A1_A1`…). Each product of moments therefore gets a single coefficient, which is how closed moment equations are read.
- **Compare** gives one of three verdicts:
  - **Equal (proved)**.
  - **Different**, with `lhs − rhs` grouped by moment. For polynomials and fractions in moments and parameters, `cancel` is a proof. Otherwise a non-zero value at a test point proves the difference.
  - **Undetermined**: SymPy cannot conclude. lhs − rhs is evaluated at random points, which is not a proof.
- **↑ Use as input**: the result becomes the input, to chain operations.

Note: Factor and Simplify put everything over a common denominator as soon as there is a `1/KA`. This is SymPy's behaviour.

## Output and copy

- The result as Python text is always shown.
- **Show LaTeX: code / rendered**. Rendering uses TeX Live, as in latex-preview, and long lines are broken with breqn.
- **Copy** (click = Python; the arrow gives the other formats):
  - Python (⇧⌘C);
  - LaTeX for Keynote: the bare equation (⇧⌘K);
  - LaTeX for Overleaf: `dmath*` (⇧⌘L). Add `\usepackage{breqn}` after amsmath in the preamble;
  - Image, 300 dpi (⇧⌘I).

## Model

**Edit model…**, **Load model…** and **Save model as…** work on the latex-preview `.ini` file. To use the model of latex-preview, save it there with « Enregistrer sous… », then load it here.

- Section and key names can be French or English: `[parametres]` / `[parameters]`, `separateur` / `separator`, `derivee` / `derivative`…
- The optional section `[hypotheses]` (or `[assumptions]`) gives SymPy assumptions. latex-preview ignores it:
  ```ini
  [hypotheses]
  positive = rmaxA, rmaxB, s, KA, KB, m
  real = x1, x2, thA, thB
  ```
  Assumptions change what Simplify and Compare can prove. For example `sqrt(KA**2)` = `KA` because KA > 0, but `sqrt(x1**2)` = `Abs(x1)` because x1 is only real.

## Tests

```bash
python -m pytest
```

The tests contain the examples of the v0.1 specification (`docs/spec_v0.1.md`). They also include two real cases: the 14 equations printed by `moment_closure.py --print-eqs 2`, and the latex-preview translation of d⟨(N_A¹)²⟩/dt, which must equal moment_closure's equation. They were validated with SymPy 1.14. Another SymPy version may order terms differently.

## Structure

```
sympy_tools/
  core/            # no GUI, usable from a notebook
    model.py       # .ini model (FR/EN keys), assumptions, one SymPy symbol per name
    reading.py     # Python-like text -> checked expression, notes, symbol list
    operations.py  # Simplify, Factor, Expand, Collect by, Compare (+ SymPy code shown)
    output.py      # Python text, LaTeX with the model's names, Overleaf export
    jobs.py        # string-in / string-out entry point, run in a separate process
  ui/              # PySide6 interface
```

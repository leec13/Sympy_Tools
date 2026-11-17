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

Operations **chain**: each one applies to the result shown (or to the input when nothing has been computed yet), and the input itself is never changed.
- The title shows the chain, e.g. *Result — Isserlis (order 3) → Collect by all moments*.
- The **SymPy code** pane shows every step that really ran, one per line, each named in a comment.
- The Collect by list and the Isserlis / definitions buttons follow the current result.
- **↺ Back to input** forgets the chain. Editing the input, or changing the mode or the model, does the same.
- **↑ Use as input** copies the current result into the input fields.
- **Compare** checks the current equation without replacing it.

On an equation, each operation is applied to each side.

| Button | SymPy | Shortcut |
|---|---|---|
| Simplify | `sp.simplify(expr)` | ⌘1 |
| Factor | `sp.factor(expr)` | ⌘2 |
| Expand | `sp.expand(expr)` | ⌘3 |
| Collect by ▾ | `sp.collect(sp.expand(expr), v)`; the list contains every symbol read, grouped, plus *all moments* | ⌘4 |
| Compare | `sp.cancel(lhs - rhs) == 0`, or `sp.simplify` with exp, sqrt… | ⌘5 |
| Isserlis (order 3) | `expr.xreplace({T_A1_A1_A2: M_A1_A1*n_A2 + 2*M_A1_A2*n_A1 - 2*n_A1**2*n_A2, …})` | ⌘6 |
| Substitute definitions | `expr.xreplace({r_A1: rmaxA - s*(x1 - thA)**2, …})` | ⌘7 |
| Recognize definitions | the formulas become `r_A1`…, coefficient by coefficient (see below) | ⌘8 |
| Take moments | inside each `E(…)`, products of N become moments | ⌘9 |
| Symmetry ▾ Apply | `expr.xreplace({M_A1_A1: M_A2_A2, …, x1: x2, x2: x1})` | ⌘0 |

The Isserlis and definitions buttons are greyed out when they have nothing to do (no `T_…`, no `r_…`, no `rmaxA`…).

- **Collect by** expands first, so a factored form is lost. With *all moments*, it collects by every product of moments present (`n_A1*M_A1_B1`, …, then `n_A1`, `M_A1_A1`…). Each product of moments therefore gets a single coefficient, which is how closed moment equations are read.
- **Compare** gives one of three verdicts:
  - **Equal (proved)**.
  - **Different**, with `lhs − rhs` grouped by moment. For polynomials and fractions in moments and parameters, `cancel` is a proof. Otherwise a non-zero value at a test point proves the difference.
  - **Undetermined**: SymPy cannot conclude. lhs − rhs is evaluated at random points, which is not a proof.
- **Isserlis (order 3)**: ⟨abc⟩ ≈ ⟨ab⟩⟨c⟩ + ⟨ac⟩⟨b⟩ + ⟨bc⟩⟨a⟩ − 2⟨a⟩⟨b⟩⟨c⟩ for every `T_…`.
  - This is exactly the level-2 closure of `moment_closure.py`, which sets third-order cumulants to zero. A test checks it on d⟨(N_A¹)²⟩/dt.
  - Moments of order 4 or more are not touched.
  - The result is not expanded: use Collect by *all moments* afterwards.
- **Recognize definitions**: the expression is grouped by products of moments. Each coefficient is rewritten as α·r_A1 + β·r_A2 + … + rest **only if** the rest no longer contains any symbol of the formulas (rmaxA, s, x1, thA…).
  - Such a decomposition is unique, so there is no ambiguity.
  - Other coefficients are kept as they are and listed. For example, the birth + death coefficient rmaxA + s(x1−θA)² is not an r_A1.
  - The result is checked: substituting the definitions back gives the input exactly.
  - `docs/v0.2_cas_22_25.pdf` shows four cases before and after.
- **↑ Use as input**: the current result becomes the input (to edit it by hand, for example).

Note: Factor and Simplify put everything over a common denominator as soon as there is a `1/KA`. This is SymPy's behaviour.

## Process, events and symmetries

The model can declare the stochastic process, one explicit line per event (`name = rate | jump`), and its symmetries:

```ini
[evenements]
naissance_A1 = rmaxA*NA1 | NA1+1
mort_A1 = (s*(x1 - thA)**2 + (NA1 + NA2)/KA)*NA1 | NA1-1
migration_A1_B1 = m*NA1 | NA1-1, NB1+1
…
[symetries]
phenotypes = A1<->A2, B1<->B2, x1<->x2
niches = A1<->B1, A2<->B2, rmaxA<->rmaxB, KA<->KB, thA<->thB
```

The default model contains the 12 events of `moment_closure.py` and these two symmetries. Their combination is added automatically, and the r_A1… follow from their definitions. When the model is loaded, rates and jumps are checked: for instance, a rate must vanish when the population that decreases is 0.

- **Events…** shows, compiled in LaTeX, every event with its image by each symmetry, ✓ or ✗. A symmetry is valid when the events are mapped onto themselves; then every moment equation is symmetric, at every order, before and after closure. This is where symmetries can be checked by eye.
- **Process: Generate d/dt** writes the equation of a moment event by event, `E(w·Δf, event)` for ⟨w·[f(N+J)−f(N)]⟩, and puts it in the input. In LaTeX, each term is labelled with its event.
- **Take moments** turns E(…) into moments (⟨NA1·NA2⟩ → `M_A1_A2`), grouped by event: rmaxA·(…), s(x−θ)²·(…), m·(…), (…)/K.
- **Symmetry ▾ Apply** swaps moments, variables, parameters, r_… and events, on the result shown. It tells when the equation is invariant, and warns when the symmetry does not hold for the events.

For example, Generate `M_A1_A1`, then Take moments, then Isserlis gives exactly the level-2 equation of `moment_closure.py`. This is checked for its 14 equations.

## Look

The window is light, like latex-preview, with its own identity so that it is easy to tell apart: a teal band at the top, a lightly tinted background, and the SymPy code pane tinted with a teal border. The colours are in `sympy_tools/ui/theme.py`. The LaTeX preview keeps a white sheet with black text, and copied images are black on white.

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
  The `[definitions]` section (`r_A1 = rmaxA - s*(x1 - thA)**2` …) is used by Substitute and Recognize definitions. A definition may use another one; circular definitions are an error.

  Assumptions change what Simplify and Compare can prove. For example `sqrt(KA**2)` = `KA` because KA > 0, but `sqrt(x1**2)` = `Abs(x1)` because x1 is only real.

## Tests

```bash
python -m pytest
```

The tests contain the examples of the specifications (`docs/spec_v0.1.md` to `docs/spec_v0.4.md`). They also include two real cases: the 14 equations printed by `moment_closure.py --print-eqs 2`, and the latex-preview translation of d⟨(N_A¹)²⟩/dt, which must equal moment_closure's equation. They were validated with SymPy 1.14. Another SymPy version may order terms differently.

## Structure

```
sympy_tools/
  core/            # no GUI, usable from a notebook
    model.py       # .ini model (FR/EN keys), assumptions, one SymPy symbol per name
    reading.py     # Python-like text -> checked expression, notes, symbol list
    operations.py  # all operations (+ SymPy code shown), which buttons are useful
    closure.py     # Isserlis / Wick on third-order moments
    definitions.py # [definitions]: substitute, and recognize (exact, unique)
    process.py     # [evenements], [symetries]: checks, Generate, Take moments, symmetry maps
    events_doc.py  # LaTeX document of the events and symmetries
    output.py      # Python text, LaTeX with the model's names, Overleaf export
    jobs.py        # string-in / string-out entry point, run in a separate process
  ui/              # PySide6 interface
```

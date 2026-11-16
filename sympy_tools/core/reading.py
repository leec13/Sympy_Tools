"""Reading a Python-like text into a SymPy expression, with checks.

SymPy's own parser accepts too much: ``2*M_A1_A1** + M_A1_MA1`` is read, without
any error, as ``2*M_A1_A1**M_A1_MA1`` (Python reads ``a** + b`` as a**(+b)), and
``M_A1_MA1`` becomes an ordinary symbol. So the text is checked before and after
parsing, and every name is resolved through the model:

* moments ``n_A1``, ``M_A1_A2``, ``T_…`` must use known codes and the right prefix
  (error otherwise); codes out of order are put back in order (info);
* derivatives ``dM_A1_A2_dt`` (``dM_A1_A2/dt`` is accepted and rewritten);
* model parameters, state variables (``NA1``), model functions;
* a few mathematical functions (exp, log, sqrt…) and the constant ``pi``;
* any other name is accepted as a symbol "not in model" (info).

No name is ever looked up in SymPy's namespace: ``N``, ``S``, ``E``, ``I``, ``Q``,
``gamma``… are ordinary symbols here.
"""

from __future__ import annotations

import ast
import difflib
import io
import keyword
import re
import tokenize
from dataclasses import dataclass, field

import sympy as sp
from sympy.parsing.sympy_parser import parse_expr, standard_transformations

from .model import (KIND_DERIVATIVE, KIND_FUNCTION, KIND_MOMENT, KIND_PARAMETER, KIND_STATE,
                    KIND_UNKNOWN, SymbolInfo, ToolModel)

ERROR, WARNING, INFO = "error", "warning", "info"

FUNCTIONS = {
    "exp": sp.exp, "log": sp.log, "ln": sp.log, "sqrt": sp.sqrt,
    "sin": sp.sin, "cos": sp.cos, "tan": sp.tan,
    "sinh": sp.sinh, "cosh": sp.cosh, "tanh": sp.tanh,
    "Abs": sp.Abs, "abs": sp.Abs,
}
CONSTANTS = {"pi": sp.pi}
_ALLOWED = re.compile(r"[A-Za-z0-9_\s+\-*/^().,]")
_GLOBALS = {"Integer": sp.Integer, "Float": sp.Float, "Rational": sp.Rational, "Symbol": sp.Symbol}


@dataclass
class Note:
    level: str      # error, warning, info
    text: str

    def __str__(self) -> str:
        return {"error": "✗ ", "warning": "⚠ ", "info": "ⓘ "}[self.level] + self.text


@dataclass
class Reading:
    """Result of reading one expression (or both sides of an equation)."""

    source: str = ""
    expr: sp.Expr | None = None
    notes: list[Note] = field(default_factory=list)
    symbols: dict[str, SymbolInfo] = field(default_factory=dict)   # canonical name -> info
    written: dict[str, str] = field(default_factory=dict)         # canonical -> as written (if corrected)

    @property
    def ok(self) -> bool:
        return self.expr is not None and not any(n.level == ERROR for n in self.notes)

    @property
    def empty(self) -> bool:
        return not self.source.strip()

    @property
    def text(self) -> str:
        return sp.sstr(self.expr) if self.expr is not None else ""


@dataclass
class EquationReading:
    lhs: Reading
    rhs: Reading

    @property
    def ok(self) -> bool:
        return self.lhs.ok and self.rhs.ok

    @property
    def empty(self) -> bool:
        return self.lhs.empty and self.rhs.empty

    @property
    def notes(self) -> list[Note]:
        out: list[Note] = []
        for side, r in (("lhs", self.lhs), ("rhs", self.rhs)):
            for n in r.notes:
                note = Note(n.level, f"{side}: {n.text}")
                if all(o.text != note.text for o in out):
                    out.append(note)
        return out

    @property
    def symbols(self) -> dict[str, SymbolInfo]:
        return {**self.lhs.symbols, **self.rhs.symbols}

    @property
    def written(self) -> dict[str, str]:
        return {**self.lhs.written, **self.rhs.written}

    @property
    def text(self) -> str:
        return f"{self.lhs.text} = {self.rhs.text}"


# ---------------------------------------------------------------- equations
def split_equation(text: str) -> tuple[str, str] | None:
    """'a = b' -> ('a', 'b') when the text has exactly one '=' (not ==, <=, >=, !=)."""
    pos = [m.start() for m in re.finditer(r"(?<![=<>!])=(?!=)", text)]
    if len(pos) != 1 or "==" in text:
        return None
    i = pos[0]
    return text[:i].strip(), text[i + 1:].strip()


# ---------------------------------------------------------------- names
@dataclass
class _Resolved:
    canonical: str = ""
    info: SymbolInfo | None = None
    notes: list[Note] = field(default_factory=list)
    error: str = ""


def _known_names(model: ToolModel) -> list[str]:
    return model.parameter_names + list(model.state_names) + model.function_names


def resolve_name(name: str, model: ToolModel) -> _Resolved:
    """Name as written -> canonical name and kind, with notes or an error."""
    r = _Resolved()
    info = model.classify(name)
    if info.kind in (KIND_PARAMETER, KIND_STATE, KIND_FUNCTION):
        r.canonical, r.info = name, info
        return r

    sep = model.lp.separator
    parts = name.split(sep)
    if len(parts) > 1 and model.is_prefix(parts[0]):
        codes = parts[1:]
        known = ", ".join(model.codes)
        bad = [c for c in codes if c not in model.lp.var_order]
        if bad:
            what = "code" if len(bad) == 1 else "codes"
            shown = ", ".join(repr(c) if c else "(empty)" for c in bad)
            r.error = f"{name}: unknown {what} {shown} (codes: {known})"
            return r
        canonical = model.moment_name(model.sort_codes(codes))
        if parts[0] != model.lp.prefix(len(codes)):
            r.error = f"{name}: {len(codes)} indices, so {canonical}"
            return r
        r.canonical = canonical
        r.info = SymbolInfo(canonical, KIND_MOMENT, model.sort_codes(codes))
        if canonical != name:
            r.notes.append(Note(INFO, f"{name} → {canonical} (codes in the order {', '.join(model.codes)})"))
        return r

    inner = model.split_derivative(name)
    if inner is not None:
        sub = resolve_name(inner, model)
        if sub.error:
            r.error = f"{name}: {sub.error}"
            return r
        r.canonical = model.derivative_name(sub.canonical)
        r.info = SymbolInfo(r.canonical, KIND_DERIVATIVE, inner=sub.canonical)
        r.notes += sub.notes
        if r.canonical != name:
            r.notes.append(Note(INFO, f"{name} → {r.canonical}"))
        return r

    r.canonical, r.info = name, SymbolInfo(name, KIND_UNKNOWN)
    known = {n.lower(): n for n in _known_names(model)}
    hint = difflib.get_close_matches(name.lower(), list(known), n=1, cutoff=0.8)
    extra = f" (did you mean {known[hint[0]]}?)" if hint else ""
    r.notes.append(Note(INFO, f"{name}: not in model{extra}"))
    return r


# ---------------------------------------------------------------- text checks
def _rewrite_slash_derivatives(text: str, model: ToolModel, notes: list[Note]) -> str:
    """dM_A1_A2/dt and d(M_A1_A2)/dt -> dM_A1_A2_dt (only for known or moment-like names)."""
    pat = re.compile(r"(?<![\w.])d(?:\(\s*([A-Za-z]\w*)\s*\)|([A-Za-z]\w*))\s*/\s*dt\b")

    def repl(m: re.Match) -> str:
        inner = m.group(1) or m.group(2)
        res = resolve_name(inner, model)
        if res.info is None or res.info.kind == KIND_UNKNOWN:
            return m.group(0)
        new = model.derivative_name(res.canonical)
        notes.append(Note(INFO, f"{m.group(0).replace(' ', '')} → {new}"))
        return new

    return pat.sub(repl, text)


def _check_parentheses(text: str) -> str:
    depth = 0
    for i, c in enumerate(text):
        if c == "(":
            depth += 1
        elif c == ")":
            depth -= 1
            if depth < 0:
                return f"unexpected ')' at position {i + 1}"
    if depth > 0:
        return f"missing ')': {depth} '(' not closed"
    return ""


def _syntax_error(text: str) -> str:
    try:
        ast.parse(text, mode="eval")
    except SyntaxError as exc:
        col = (exc.offset or 1) - 1
        start = max(0, col - 25)
        excerpt = text[start:col + 15]
        caret = " " * (col - start) + "^"
        msg = (exc.msg or "invalid syntax").replace("invalid syntax. Perhaps you forgot a comma?",
                                                   "invalid syntax")
        return f"syntax error at position {col + 1}: {msg}\n    {excerpt}\n    {caret}"
    return ""


def _names(text: str) -> list[tuple[str, bool]]:
    """NAME tokens in order of appearance: (name, followed by '(')."""
    toks = [t for t in tokenize.generate_tokens(io.StringIO(text).readline)
            if t.type not in (tokenize.NL, tokenize.NEWLINE, tokenize.ENDMARKER, tokenize.INDENT,
                              tokenize.DEDENT)]
    out = []
    for k, t in enumerate(toks):
        if t.type == tokenize.NAME:
            called = k + 1 < len(toks) and toks[k + 1].string == "("
            out.append((t.string, called))
    return out


# ---------------------------------------------------------------- reading
def read_expression(text: str, model: ToolModel) -> Reading:
    r = Reading(source=text)
    src = re.sub(r"\\\s*\n", " ", text)
    src = " ".join(src.split())
    if not src:
        return r
    if "\\" in src:
        r.notes.append(Note(ERROR, "this looks like LaTeX: paste the Python text "
                                   "(for example from latex-preview's Translation panel)"))
        return r
    if "=" in src:
        r.notes.append(Note(ERROR, "'=' found: use Equation mode (lhs and rhs)"))
        return r
    bad = sorted({c for c in src if not _ALLOWED.fullmatch(c)})
    if bad:
        r.notes.append(Note(ERROR, "character(s) not allowed: " + " ".join(repr(c) for c in bad)))
        return r
    if "^" in src:
        src = src.replace("^", "**")
        r.notes.append(Note(INFO, "^ read as **"))
    src = _rewrite_slash_derivatives(src, model, r.notes)

    kw = [w for w in dict.fromkeys(re.findall(r"[A-Za-z_]\w*", src))
          if keyword.iskeyword(w) or w in ("None", "True", "False")]
    if kw:
        r.notes += [Note(ERROR, f"'{w}' is a Python keyword: rename it (for example {w[:3]}_)")
                    for w in kw]
        return r
    err = _check_parentheses(src) or _syntax_error(src)
    if err:
        r.notes.append(Note(ERROR, err))
        return r

    local: dict[str, object] = {}
    errors: list[str] = []
    seen: set[str] = set()
    for name, called in _names(src):
        key = (name, called)
        if key in seen:
            continue
        seen.add(key)
        if name in FUNCTIONS:
            if not called:
                errors.append(f"'{name}' is a function: write {name}(…)")
            local[name] = FUNCTIONS[name]
            continue
        if name in CONSTANTS and not called:
            local[name] = CONSTANTS[name]
            continue
        if name in model.function_names:
            if not called:
                errors.append(f"'{name}' is a function of the model: write {name}(…)")
            local[name] = model.function(name)
            r.symbols[name] = SymbolInfo(name, KIND_FUNCTION)
            continue
        if called:
            errors.append(f"'{name}(' : {name} is not a function. Did you mean {name}*(…)?")
            continue
        res = resolve_name(name, model)
        if res.error:
            errors.append(res.error)
            continue
        for n in res.notes:
            if all(o.text != n.text for o in r.notes):
                r.notes.append(n)
        local[name] = model.symbol(res.canonical)
        r.symbols[res.canonical] = res.info
        if res.canonical != name:
            r.written[res.canonical] = name
    if errors:
        r.notes += [Note(ERROR, e) for e in errors]
        return r

    try:
        expr = parse_expr(src, local_dict=local, global_dict=dict(_GLOBALS),
                          transformations=standard_transformations, evaluate=True)
    except Exception as exc:  # noqa: BLE001 - any SymPy failure is reported, not raised
        r.notes.append(Note(ERROR, f"SymPy could not read this ({type(exc).__name__}: {exc})"))
        return r
    if not isinstance(expr, sp.Expr):
        r.notes.append(Note(ERROR, f"not an expression ({type(expr).__name__})"))
        return r
    if expr.has(sp.zoo, sp.nan, sp.oo, -sp.oo):
        r.notes.append(Note(ERROR, "division by zero (or infinite value)"))
        return r
    for p in sorted(expr.atoms(sp.Pow), key=sp.default_sort_key):
        if not p.exp.is_number:
            r.notes.append(Note(WARNING, f"non-numeric exponent: {sp.sstr(p)}  "
                                         "(note: Python reads a** + b as a**(+b))"))
    if expr.atoms(sp.Float):
        r.notes.append(Note(INFO, "decimal numbers kept as decimals "
                                  "(Compare turns them into exact fractions)"))
    r.expr = expr
    return r


def read_equation(lhs: str, rhs: str, model: ToolModel) -> EquationReading:
    return EquationReading(read_expression(lhs, model), read_expression(rhs, model))


# ---------------------------------------------------------------- symbol list
def categories(symbols: dict[str, SymbolInfo], model: ToolModel) -> list[tuple[str, list[str]]]:
    """Symbols grouped for display: [(label, [names])], in a stable order."""
    order = {c: k for k, c in enumerate(model.codes)}
    params = {n: k for k, n in enumerate(model.parameter_names)}
    groups: dict[str, list[SymbolInfo]] = {}
    for info in symbols.values():
        if info.kind == KIND_MOMENT:
            label = f"Moments of order {info.order}"
        else:
            label = {KIND_DERIVATIVE: "Derivatives", KIND_STATE: "State variables",
                     KIND_PARAMETER: "Parameters", KIND_FUNCTION: "Functions",
                     KIND_UNKNOWN: "Not in model"}[info.kind]
        groups.setdefault(label, []).append(info)

    def rank(label: str) -> tuple:
        m = re.match(r"Moments of order (\d+)", label)
        if m:
            return (0, int(m.group(1)))
        return (1, ["Derivatives", "State variables", "Parameters", "Functions",
                    "Not in model"].index(label))

    out = []
    for label in sorted(groups, key=rank):
        infos = groups[label]
        if label.startswith("Moments"):
            infos.sort(key=lambda i: [order[c] for c in i.codes])
        elif label == "Parameters":
            infos.sort(key=lambda i: params.get(i.name, 0))
        else:
            infos.sort(key=lambda i: i.name)
        out.append((label, [i.name for i in infos]))
    return out


def moment_symbols(symbols: dict[str, SymbolInfo], model: ToolModel) -> list[sp.Symbol]:
    """Moments present, in canonical order (order, then codes)."""
    order = {c: k for k, c in enumerate(model.codes)}
    ms = [i for i in symbols.values() if i.kind == KIND_MOMENT]
    ms.sort(key=lambda i: (i.order, [order[c] for c in i.codes]))
    return [model.symbol(i.name) for i in ms]

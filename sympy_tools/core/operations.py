"""Operations: Simplify, Factor, Expand, Collect by, Compare.

Each operation returns its result *and* the SymPy line(s) it really ran, shown in
the interface for information. On an equation, every operation except Compare is
applied to each side separately.

Compare decides whether lhs - rhs is identically zero:

* rational functions (polynomials in moments, with 1/KA…): ``cancel`` gives a
  canonical form, so the answer is a proof either way;
* otherwise (exp, sqrt…): ``simplify``; if it does not give 0, lhs - rhs is
  evaluated at random rational points (respecting the model's assumptions). A
  clearly non-zero value proves the sides differ; values that are all ~0 leave
  the question undetermined (not a proof).
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field

import sympy as sp
from sympy.core.function import AppliedUndef

from .model import ToolModel
from .reading import EquationReading, Reading, moment_symbols

SIMPLIFY, FACTOR, EXPAND, COLLECT, COMPARE = "simplify", "factor", "expand", "collect", "compare"
OPERATIONS = {SIMPLIFY: "Simplify", FACTOR: "Factor", EXPAND: "Expand",
              COLLECT: "Collect by", COMPARE: "Compare"}
ALL_MOMENTS = "*all moments*"

EQUAL, DIFFERENT, UNDETERMINED = "equal", "different", "undetermined"
_N_POINTS = 6


@dataclass
class OpResult:
    op: str
    ok: bool = True
    error: str = ""
    code: list[str] = field(default_factory=list)
    expr: sp.Expr | None = None      # expression mode; Compare: lhs - rhs (shown)
    lhs: sp.Expr | None = None       # equation mode
    rhs: sp.Expr | None = None
    verdict: str = ""                # Compare only
    verdict_text: str = ""
    notes: list[str] = field(default_factory=list)

    @property
    def is_equation(self) -> bool:
        return self.lhs is not None

    @property
    def text(self) -> str:
        if self.is_equation:
            return f"{sp.sstr(self.lhs)} = {sp.sstr(self.rhs)}"
        return sp.sstr(self.expr) if self.expr is not None else ""


def _list(syms) -> str:
    return "[" + ", ".join(sp.sstr(s) for s in syms) + "]"


def moment_monomials(exprs, moments: list[sp.Symbol]) -> list[sp.Expr]:
    """Products of moments present (n_A1*M_A1_B1, …), highest degree first, then the moments.

    Collecting by these keeps one coefficient per product of moments, which is how
    closed moment equations are read. Falls back to the moments themselves when the
    expression is not a polynomial in the moments (moment in a denominator, in exp…)."""
    found: set = set()
    for e in exprs:
        try:
            poly = sp.Poly(sp.expand(e), *moments)
        except sp.PolynomialError:
            return list(moments)
        for mon in poly.monoms():
            if any(mon):
                found.add(sp.Mul(*[g ** k for g, k in zip(moments, mon)]))
    def key(t):
        powers = t.as_powers_dict()
        exps = tuple(int(powers.get(m, 0)) for m in moments)
        return (-sum(exps), tuple(-k for k in exps))   # degree, then exponents (deterministic)

    return sorted(found, key=key)


def _transform(op: str, syms) -> tuple:
    """(function, code template '{x}' = argument)."""
    if op == SIMPLIFY:
        return sp.simplify, "sp.simplify({x})"
    if op == FACTOR:
        return sp.factor, "sp.factor({x})"
    if op == EXPAND:
        return sp.expand, "sp.expand({x})"
    if op == COLLECT:
        arg = sp.sstr(syms[0]) if len(syms) == 1 else _list(syms)
        target = syms[0] if len(syms) == 1 else list(syms)
        return (lambda e: sp.collect(sp.expand(e), target)), "sp.collect(sp.expand({x}), " + arg + ")"
    raise ValueError(f"unknown operation: {op}")


def _collect_symbols(var: str | None, reading, model: ToolModel) -> list[sp.Expr]:
    if not var:
        raise ValueError("Choose a variable for Collect by.")
    if var == ALL_MOMENTS:
        syms = moment_symbols(reading.symbols, model)
        if not syms:
            raise ValueError("There is no moment to collect by.")
        exprs = ([reading.lhs.expr, reading.rhs.expr] if isinstance(reading, EquationReading)
                 else [reading.expr])
        return moment_monomials(exprs, syms)
    if var not in reading.symbols:
        raise ValueError(f"'{var}' does not appear in the input.")
    return [model.symbol(var)]


def apply(op: str, reading: Reading | EquationReading, model: ToolModel,
          var: str | None = None) -> OpResult:
    res = OpResult(op)
    if not reading.ok:
        res.ok, res.error = False, "The input has errors: correct them first."
        return res
    try:
        if op == COMPARE:
            if not isinstance(reading, EquationReading):
                raise ValueError("Compare needs an equation: switch to Equation mode.")
            return compare(reading.lhs.expr, reading.rhs.expr, reading, model)
        syms = _collect_symbols(var, reading, model) if op == COLLECT else []
        fn, tpl = _transform(op, syms)
        if isinstance(reading, EquationReading):
            res.lhs, res.rhs = fn(reading.lhs.expr), fn(reading.rhs.expr)
            res.code = [f"lhs = {tpl.format(x='lhs')}", f"rhs = {tpl.format(x='rhs')}"]
        else:
            res.expr = fn(reading.expr)
            res.code = [f"result = {tpl.format(x='expr')}"]
        if op == COLLECT:
            res.notes.append("Collect by expands first: a factored form is not kept.")
    except ValueError as exc:
        res.ok, res.error = False, str(exc)
    except Exception as exc:  # noqa: BLE001 - SymPy failures are reported
        res.ok, res.error = False, f"SymPy error ({type(exc).__name__}): {exc}"
    return res


# ---------------------------------------------------------------- compare
def _test_value(sym: sp.Symbol, rng: random.Random) -> sp.Rational:
    v = sp.Rational(rng.randint(1, 29), rng.randint(1, 11))
    if sym.is_negative or sym.is_nonpositive:
        return -v
    if sym.is_positive or sym.is_nonnegative:
        return v
    if sym.is_real:
        return v if rng.random() < 0.5 else -v
    return v   # moments, unknown symbols: positive test values


def _numeric_check(d: sp.Expr, lhs: sp.Expr, rhs: sp.Expr) -> tuple[str, str]:
    """('different', point) / ('zero', '') / ('unknown', why)."""
    rng = random.Random(12345)
    free = sorted(d.free_symbols, key=lambda s: s.name)
    if d.atoms(AppliedUndef):
        return "unknown", "it contains functions without a formula"
    for _ in range(_N_POINTS):
        vals = {s: _test_value(s, rng) for s in free}
        try:
            v = complex(d.xreplace(vals).evalf(50))
            scale = max(1.0, abs(complex(lhs.xreplace(vals).evalf(30))),
                        abs(complex(rhs.xreplace(vals).evalf(30))))
        except (TypeError, ValueError, ZeroDivisionError):
            continue
        if abs(v) > 1e-25 * scale:
            point = ", ".join(f"{s.name}={vals[s]}" for s in free)
            return "different", point
    return "zero", ""


def compare(lhs: sp.Expr, rhs: sp.Expr, reading, model: ToolModel) -> OpResult:
    res = OpResult(COMPARE)
    if lhs.atoms(sp.Float) or rhs.atoms(sp.Float):
        lhs, rhs = sp.nsimplify(lhs, rational=True), sp.nsimplify(rhs, rational=True)
        res.notes.append("Decimal numbers were turned into exact fractions before comparing.")
    d = lhs - rhs
    moments = [m for m in moment_symbols(reading.symbols, model) if d.has(m)]
    if d.is_rational_function(*d.free_symbols):
        res.code = ["equal = sp.cancel(lhs - rhs) == 0"]
        c = sp.cancel(d)
        if c == 0:
            res.verdict, res.verdict_text, res.expr = EQUAL, "Equal (proved)", sp.Integer(0)
            return res
        res.verdict, res.verdict_text = DIFFERENT, "Different (proved)"
        if moments:
            res.expr = sp.collect(sp.expand(d), moments, sp.factor)
            res.code.append(f"diff = sp.collect(sp.expand(lhs - rhs), {_list(moments)}, sp.factor)")
        else:
            res.expr = sp.factor(c)
            res.code.append("diff = sp.factor(lhs - rhs)")
        return res

    res.code = ["equal = sp.simplify(lhs - rhs) == 0"]
    s = sp.simplify(d)
    if s == 0:
        res.verdict, res.verdict_text, res.expr = EQUAL, "Equal (proved by simplify)", sp.Integer(0)
        return res
    res.expr = s
    kind, info = _numeric_check(d, lhs, rhs)
    if kind == "different":
        res.verdict, res.verdict_text = DIFFERENT, "Different (proved: lhs − rhs ≠ 0 at a test point)"
        res.notes.append(f"Test point: {info}")
    elif kind == "zero":
        res.verdict = UNDETERMINED
        res.verdict_text = (f"Undetermined: SymPy cannot prove it, but lhs − rhs = 0 at "
                            f"{_N_POINTS} random points (not a proof)")
    else:
        res.verdict = UNDETERMINED
        res.verdict_text = f"Undetermined: SymPy cannot prove it, and {info}"
    return res

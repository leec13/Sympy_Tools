"""Operations: Simplify, Factor, Expand, Collect by, Compare, Isserlis, definitions.

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
import re
from dataclasses import dataclass, field

import sympy as sp
from sympy.core.function import AppliedUndef

from . import closure
from . import definitions as defs_mod
from . import process as proc_mod
from .model import KIND_MOMENT, ModelError, ToolModel
from .reading import EquationReading, Reading, moment_monomials, moment_symbols

SIMPLIFY, FACTOR, EXPAND, COLLECT, COMPARE = "simplify", "factor", "expand", "collect", "compare"
ISSERLIS, SUBSTITUTE, RECOGNIZE = "isserlis", "substitute", "recognize"
TAKE_MOMENTS, SYMMETRY = "moments", "symmetry"
OPERATIONS = {SIMPLIFY: "Simplify", FACTOR: "Factor", EXPAND: "Expand",
              COLLECT: "Collect by", COMPARE: "Compare", ISSERLIS: "Isserlis (order 3)",
              SUBSTITUTE: "Substitute definitions", RECOGNIZE: "Recognize definitions",
              TAKE_MOMENTS: "Take moments", SYMMETRY: "Symmetry"}
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
        if op in (ISSERLIS, SUBSTITUTE, RECOGNIZE):
            return _model_operation(op, reading, model)
        if op == TAKE_MOMENTS:
            return _take_moments(reading, model)
        if op == SYMMETRY:
            return _symmetry(reading, model, var)
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


# ---------------------------------------------------------------- chains
def chain_code(code: list[str], label: str, first: bool) -> list[str]:
    """Code lines of one step of a chain: the first step starts from expr (or lhs, rhs),
    the next ones from result; the step's name is added as a comment."""
    lines = list(code) if first else [re.sub(r"\bexpr\b", "result", c) for c in code]
    if lines:
        head = lines[0]
        if "   # " in head:
            lines[0] = head.replace("   # ", f"   # {label}: ", 1)
        elif head.startswith("#"):
            lines[0] = f"# {label}: " + head[1:].lstrip()
        else:
            lines[0] = f"{head}   # {label}"
    return lines


# ---------------------------------------------------------------- Isserlis, definitions
def _rules_code(rules: dict) -> str:
    return "rules = {" + ", ".join(f"{sp.sstr(k)}: {sp.sstr(v)}" for k, v in rules.items()) + "}"


def _sides(reading) -> list[sp.Expr]:
    if isinstance(reading, EquationReading):
        return [reading.lhs.expr, reading.rhs.expr]
    return [reading.expr]


def _model_operation(op: str, reading, model: ToolModel) -> OpResult:
    res = OpResult(op)
    sides = _sides(reading)
    equation = isinstance(reading, EquationReading)
    try:
        if op == ISSERLIS:
            rules = closure.isserlis_rules(sides, model)
            if not rules:
                raise ValueError("There is no third-order moment (T_…) in the input.")
            new = [e.xreplace(rules) for e in sides]
            res.code = [_rules_code(rules)]
            if any(closure.moments_of_order(sides, model, k) for k in range(4, 9)):
                res.notes.append("Moments of order 4 or more are not closed.")
            res.notes.append("The result is not expanded: use Collect by all moments to group it.")
        elif op == SUBSTITUTE:
            d = defs_mod.definitions(model)
            rules = defs_mod.used_rules(sides, d)
            if not rules:
                names = ", ".join(sorted(d.names)) or "none in the model"
                raise ValueError(f"No defined symbol in the input (definitions: {names}).")
            new = [e.xreplace(d.full) for e in sides]
            res.code = [_rules_code(rules)]
        else:   # RECOGNIZE
            d = defs_mod.definitions(model)
            present = set().union(*[e.free_symbols for e in sides])
            if not d.rules or not (present & set(d.symbols)):
                shown = ", ".join(s.name for s in d.symbols[:6]) or "none"
                raise ValueError(f"None of the symbols of the definitions ({shown}…) is in the input.")
            outs = [defs_mod.recognize(e, d, model) for e in sides]
            new = [o.expr for o in outs]
            kept = [k for o in outs for k in o.kept]
            if sum(o.found for o in outs) == 0:
                res.notes.append("No definition recognized.")
            if kept:
                shown = ", ".join(dict.fromkeys(sp.sstr(k) for k in kept))
                res.notes.append("Kept as it is (not a combination of "
                                 + ", ".join(sorted(d.names)) + "): coefficient of " + shown + ".")
            first = next(iter(d.rules.items()))
            res.code = ["terms = sp.collect(sp.expand(expr), monomials, evaluate=False)"
                        "   # one coefficient c per product of moments",
                        f"# each c: sp.solve(sp.Poly(c - α·({sp.sstr(first[1])}) - …, "
                        + ", ".join(s.name for s in d.symbols) + ").coeffs(), α)  ->  c = α·"
                        + first[0].name + " + … + c0"]
            if equation:
                res.code[0] = ("terms = sp.collect(sp.expand(side), monomials, evaluate=False)"
                               "   # lhs and rhs: one coefficient c per product of moments")
            res.lhs, res.rhs = (new if equation else (None, None))
            if not equation:
                res.expr = new[0]
            return res
        if equation:
            res.lhs, res.rhs = new
            res.code.append("lhs, rhs = lhs.xreplace(rules), rhs.xreplace(rules)")
        else:
            res.expr = new[0]
            res.code.append("result = expr.xreplace(rules)")
    except ValueError as exc:
        res.ok, res.error = False, str(exc)
    except Exception as exc:  # noqa: BLE001 - SymPy failures are reported
        res.ok, res.error = False, f"SymPy error ({type(exc).__name__}): {exc}"
    return res


def _finish(res: OpResult, new: list, equation: bool) -> OpResult:
    if equation:
        res.lhs, res.rhs = new
        res.code.append("lhs, rhs = lhs.xreplace(rules), rhs.xreplace(rules)")
    else:
        res.expr = new[0]
        res.code.append("result = expr.xreplace(rules)")
    return res


def _take_moments(reading, model: ToolModel) -> OpResult:
    res = OpResult(TAKE_MOMENTS)
    sides = _sides(reading)
    equation = isinstance(reading, EquationReading)
    try:
        values, monos = {}, {}
        for e in sides:
            v, mo = proc_mod.moments_rules(e, model)
            values.update(v)
            monos.update(mo)
        if not values:
            raise ValueError("There is no E(…) in the input.")
        new = [e.xreplace(values) for e in sides]
        ordered = sorted(monos.items(), key=lambda kv: (sp.Poly(kv[0]).total_degree(), sp.default_sort_key(kv[0])))
        res.code = ["rules = {" + ", ".join(f"{sp.sstr(k)}: {v.name}" for k, v in ordered) + "}"
                    "   # inside each E(…), expanded, every product of N becomes its moment",
                    ("lhs, rhs = [s.replace(E, lambda body, *event: sp.expand(body).xreplace(rules)) "
                     "for s in (lhs, rhs)]") if equation else
                    "result = expr.replace(E, lambda body, *event: sp.expand(body).xreplace(rules))"]
        stray = sorted({n for e in sides for n in proc_mod.state_symbols_outside_e(e, model)})
        if stray:
            res.notes.append(f"{', '.join(stray)} outside E(…): left as is.")
        if equation:
            res.lhs, res.rhs = new
        else:
            res.expr = new[0]
    except ValueError as exc:
        res.ok, res.error = False, str(exc)
    return res


def _symmetry(reading, model: ToolModel, name: str | None) -> OpResult:
    res = OpResult(SYMMETRY)
    sides = _sides(reading)
    equation = isinstance(reading, EquationReading)
    try:
        proc = proc_mod.process(model)
        if not proc.symmetries:
            raise ValueError("The model declares no symmetry ([symetries] section).")
        if not name:
            raise ValueError("Choose a symmetry.")
        sym = proc.symmetry(name)
        present = set().union(*[e.free_symbols for e in sides])
        rules = {}
        for s in sorted(present, key=lambda x: x.name):
            img = proc_mod.symbol_map(sym, s.name, model)
            if img != s.name:
                rules[s] = model.symbol(img)
        new = [e.xreplace(rules) for e in sides]
        res.code = [_rules_code(rules) if rules else "rules = {}"]
        if not sym.checked:
            res.notes.append("No events in the model: this symmetry cannot be checked.")
        elif sym.failures:
            res.notes.append(f"⚠ {name} is not a symmetry of the events ({len(sym.failures)} events ✗: "
                             f"{', '.join(sym.failures)}). The result may not be the equation of the "
                             "image moment.")
        if all(sp.expand(a - b) == 0 for a, b in zip(new, sides)):
            res.notes.append(f"Invariant under {name}: the equation does not change.")
        _finish(res, new, equation)
    except (ValueError, ModelError) as exc:
        res.ok, res.error = False, str(exc)
    return res


def available(reading, model: ToolModel) -> dict[str, bool]:
    """Which of Isserlis / Substitute / Recognize make sense for this input (for the buttons)."""
    out = {ISSERLIS: False, SUBSTITUTE: False, RECOGNIZE: False, TAKE_MOMENTS: False,
           SYMMETRY: False}
    if reading is None or not reading.ok:
        return out
    out[TAKE_MOMENTS] = any(e.atoms(proc_mod.E) for e in _sides(reading))
    try:
        out[SYMMETRY] = bool(proc_mod.process(model).symmetries)
    except ModelError:
        pass
    names = set(reading.symbols)
    out[ISSERLIS] = any(i.kind == KIND_MOMENT and i.order == 3 for i in reading.symbols.values())
    try:
        d = defs_mod.definitions(model)
    except ValueError:
        return out
    out[SUBSTITUTE] = bool(names & d.names)
    out[RECOGNIZE] = bool(d.rules) and bool(names & {s.name for s in d.symbols})
    return out


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

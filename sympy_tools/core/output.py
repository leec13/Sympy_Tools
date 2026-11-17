"""Outputs: Python text, LaTeX (names from the model), LaTeX for Keynote / Overleaf."""

from __future__ import annotations

import sympy as sp
from latex_preview.core.document import overleaf_export
from sympy.printing.latex import LatexPrinter

from .model import ToolModel
from .process import E
from .operations import COMPARE, OpResult
from .reading import EquationReading, Reading


class _Printer(LatexPrinter):
    """SymPy's LaTeX printer, with the model's LaTeX for its functions (R1 = R_1)."""

    def __init__(self, model: ToolModel, settings: dict) -> None:
        super().__init__(settings)
        self._model = model

    def _print_Function(self, expr, exp=None):
        lat = self._model.lp.function_latex.get(expr.func.__name__)
        if lat is None:
            return super()._print_Function(expr, exp)
        args = ", ".join(self._print(a) for a in expr.args)
        s = rf"{lat}\left({args}\right)"
        return s if exp is None else rf"\left({s}\right)^{{{exp}}}"


    def _print_Add(self, expr, order=None):
        """Sums of E(…, event) terms: in the order of the model's events (birth, death…)."""
        terms = list(expr.args)
        rank = {n: k for k, (n, _) in enumerate(self._model.events_raw)}

        def key(t):
            tags = [e.tag.name for e in t.atoms(E) if e.tag is not None]
            return (min((rank.get(n, len(rank)) for n in tags), default=len(rank) + 1),
                    sp.default_sort_key(t))

        if not any(t.atoms(E) for t in terms):
            return super()._print_Add(expr, order)
        terms.sort(key=key)
        tex = ""
        for i, term in enumerate(terms):
            if i and term.could_extract_minus_sign():
                tex += " - "
                term = -term
            elif i:
                tex += " + "
            t = self._print(term)
            if self._needs_add_brackets(term):
                t = rf"\left({t}\right)"
            tex += t
        return tex

    def _print_E(self, expr, exp=None):
        body = rf"\left\langle {self._print(expr.body)} \right\rangle"
        if expr.tag is not None:
            body = rf"\underbrace{{{body}}}_{{{event_label_math(expr.tag.name, self._model)}}}"
        return body if exp is None else rf"\left({body}\right)^{{{exp}}}"


def event_label(name: str, model: ToolModel) -> str:
    """migration_A1_B1 -> 'migration A1$\to$B1', naissance_A1 -> 'naissance A1'."""
    parts = name.split("_")
    if len(parts) >= 3 and parts[-1] in model.lp.var_order and parts[-2] in model.lp.var_order:
        return " ".join(parts[:-2]) + f" {parts[-2]}$\\to${parts[-1]}"
    return " ".join(parts).replace("&", "")


def event_label_math(name: str, model: ToolModel) -> str:
    """The same label, for math mode (no $ inside: breqn does not accept it)."""
    parts = name.split("_")
    if len(parts) >= 3 and parts[-1] in model.lp.var_order and parts[-2] in model.lp.var_order:
        return (rf"\text{{{' '.join(parts[:-2])} {parts[-2]}}}{{\to}}"
                rf"\text{{{parts[-1]}}}")
    return rf"\text{{{' '.join(parts)}}}"


def symbol_names(expr: sp.Expr, model: ToolModel) -> dict:
    names = {}
    for s in expr.free_symbols:
        info = model.classify(s.name)
        lat = model.latex_name(info) if info else None
        if lat:
            names[s] = lat
    return names


def latex(expr: sp.Expr, model: ToolModel) -> str:
    return _Printer(model, {"symbol_names": symbol_names(expr, model)}).doprint(expr)


def reading_latex(reading: Reading | EquationReading, model: ToolModel) -> str:
    if isinstance(reading, EquationReading):
        return f"{latex(reading.lhs.expr, model)} = {latex(reading.rhs.expr, model)}"
    return latex(reading.expr, model)


def result_latex(res: OpResult, model: ToolModel) -> str:
    if res.op == COMPARE:
        return rf"\mathrm{{lhs}} - \mathrm{{rhs}} = {latex(res.expr, model)}"
    if res.is_equation:
        return f"{latex(res.lhs, model)} = {latex(res.rhs, model)}"
    return latex(res.expr, model)


def overleaf(snippet: str) -> str:
    """LaTeX for Overleaf: dmath* (breqn) as latex-preview's « Copy for Overleaf »."""
    out = overleaf_export(snippet)
    return out[0] if out else snippet

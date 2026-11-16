"""Outputs: Python text, LaTeX (names from the model), LaTeX for Keynote / Overleaf."""

from __future__ import annotations

import sympy as sp
from latex_preview.core.document import overleaf_export
from sympy.printing.latex import LatexPrinter

from .model import ToolModel
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

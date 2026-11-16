"""Moment closure: Isserlis / Wick approximation of third-order moments.

    <abc> ≈ <ab><c> + <ac><b> + <bc><a> - 2<a><b><c>

This is the closure of moment_closure.py at level 2 (third-order cumulants set to
zero). Fourth-order moments (Q_…) are left untouched.
"""

from __future__ import annotations

import sympy as sp

from .model import KIND_MOMENT, ToolModel


def _moment(model: ToolModel, *codes: str) -> sp.Symbol:
    return model.symbol(model.moment_name(model.sort_codes(codes)))


def isserlis3(codes, model: ToolModel) -> sp.Expr:
    """Isserlis formula of the third-order moment with codes (a, b, c)."""
    a, b, c = codes
    n = lambda x: _moment(model, x)          # noqa: E731
    M = lambda x, y: _moment(model, x, y)    # noqa: E731
    return M(a, b) * n(c) + M(a, c) * n(b) + M(b, c) * n(a) - 2 * n(a) * n(b) * n(c)


def moments_of_order(exprs, model: ToolModel, order: int) -> list[sp.Symbol]:
    """Moments of a given order present in the expressions, in canonical order."""
    rank = {c: k for k, c in enumerate(model.codes)}
    found = {}
    for e in exprs:
        for s in e.free_symbols:
            info = model.classify(s.name)
            if info.kind == KIND_MOMENT and info.order == order:
                found[s] = info
    return sorted(found, key=lambda s: [rank[c] for c in found[s].codes])


def isserlis_rules(exprs, model: ToolModel) -> dict[sp.Symbol, sp.Expr]:
    """{T_…: formula} for every third-order moment present."""
    return {t: isserlis3(model.classify(t.name).codes, model)
            for t in moments_of_order(exprs, model, 3)}

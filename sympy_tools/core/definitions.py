"""Model definitions ([definitions]: r_A1 = rmaxA - s*(x1 - thA)**2 …), both ways.

* Substitute: r_A1 -> rmaxA - s*(x1 - thA)**2 (repeated until no defined name is left).
* Recognize: the formulas -> r_A1…, wherever this is exact and unambiguous.

Recognize works coefficient by coefficient (one coefficient per product of moments,
as "Collect by all moments"). A coefficient c is rewritten only if

    c = α1·r1 + α2·r2 + … + c0

where c0 and the α's no longer contain any symbol of the formulas (rmaxA, s, x1,
thA…). Since each formula has a term of its own (s·x1·thA for r_A1), such a
decomposition is unique when it exists. Otherwise the coefficient is kept as it is
and reported. The result is checked: substituting the definitions back gives the
input exactly.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import sympy as sp

from .model import KIND_MOMENT, ToolModel
from .reading import moment_monomials, read_expression


@dataclass
class Definitions:
    rules: dict[sp.Symbol, sp.Expr]          # r_A1 -> formula, as written in the model
    full: dict[sp.Symbol, sp.Expr]           # formulas with every definition substituted
    symbols: list[sp.Symbol] = field(default_factory=list)   # symbols of the formulas (rmaxA, s…)

    @property
    def names(self) -> set[str]:
        return {s.name for s in self.rules}


def definitions(model: ToolModel) -> Definitions:
    """Read the [definitions] section with the same checks as the input (cached on the model)."""
    cached = getattr(model, "_definitions_cache", None)
    if cached is not None:
        return cached
    rules: dict[sp.Symbol, sp.Expr] = {}
    for name, text in model.lp.definitions.items():
        r = read_expression(text, model)
        if not r.ok:
            errs = "; ".join(n.text for n in r.notes if n.level == "error") or "empty"
            raise ValueError(f"Definition {name} = {text}: {errs}")
        rules[model.symbol(name)] = r.expr
    full = dict(rules)
    for _ in range(len(rules) + 1):
        new = {k: v.xreplace(full) for k, v in full.items()}
        if new == full:
            break
        full = new
    else:
        loop = [k.name for k, v in full.items() if v.free_symbols & set(full)]
        raise ValueError("Circular definitions: " + ", ".join(sorted(loop)))
    syms = sorted(set().union(*[v.free_symbols for v in full.values()]) if full else set(),
                  key=lambda s: s.name)
    out = Definitions(rules, full, syms)
    object.__setattr__(model, "_definitions_cache", out)
    return out


# ---------------------------------------------------------------- substitute
def substitute(expr: sp.Expr, defs: Definitions) -> sp.Expr:
    return expr.xreplace(defs.full)


def used_rules(exprs, defs: Definitions) -> dict[sp.Symbol, sp.Expr]:
    present = set().union(*[e.free_symbols for e in exprs])
    return {k: v for k, v in defs.full.items() if k in present}


# ---------------------------------------------------------------- recognize
def _decompose(c: sp.Expr, defs: Definitions) -> sp.Expr | None:
    """c = Σ α_k·r_k + c0 (exact, unique), or None."""
    keys = list(defs.full)
    alphas = sp.symbols(f"_alpha0:{len(keys)}")
    try:
        poly = sp.Poly(sp.expand(c - sum(a * defs.full[k] for a, k in zip(alphas, keys))),
                       *defs.symbols)
    except sp.PolynomialError:
        return None
    equations = [co for mon, co in poly.terms() if any(mon)]
    sol = sp.solve(equations, alphas, dict=True)
    if len(sol) != 1 or set(sol[0]) != set(alphas):
        return None                       # no exact decomposition, or not unique
    s = sol[0]
    if any(s[a].free_symbols & set(defs.symbols) for a in alphas):
        return None
    if all(s[a] == 0 for a in alphas):
        return None
    c0 = sp.expand(c - sum(s[a] * defs.full[k] for a, k in zip(alphas, keys)))
    return sum(s[a] * k for a, k in zip(alphas, keys)) + c0


def _tidy(c: sp.Expr, defs: Definitions) -> sp.Expr:
    """A kept coefficient, readable: collect by the symbols that enter the formulas
    linearly (rmaxA, s…) and factor what multiplies them (s*(x1 - thA)**2)."""
    lead = []
    for v in defs.symbols:
        try:
            if all(sp.Poly(f, v).degree() <= 1 for f in defs.full.values()):
                lead.append(v)
        except sp.PolynomialError:
            pass
    return sp.collect(sp.expand(c), lead, sp.factor) if lead else c


@dataclass
class Recognized:
    expr: sp.Expr
    kept: list[sp.Expr]       # products of moments whose coefficient was kept as it is
    found: int                # number of coefficients rewritten


def recognize(expr: sp.Expr, defs: Definitions, model: ToolModel) -> Recognized:
    e = sp.expand(expr)
    rank = {c: k for k, c in enumerate(model.codes)}
    infos = {s: model.classify(s.name) for s in e.free_symbols}
    moments = sorted((s for s, i in infos.items() if i.kind == KIND_MOMENT),
                     key=lambda s: (infos[s].order, [rank[c] for c in infos[s].codes]))
    monomials = moment_monomials([e], moments) if moments else []
    terms = sp.collect(e, monomials, evaluate=False) if monomials else {sp.S.One: e}
    dsyms = set(defs.symbols)
    out, kept, found = sp.S.Zero, [], 0
    for mon in monomials + [sp.S.One]:
        if mon not in terms:
            continue
        c = terms[mon]
        new = _decompose(c, defs) if c.free_symbols & dsyms else None
        if new is None:
            if c.free_symbols & dsyms:
                kept.append(mon)
            new = _tidy(c, defs)
        else:
            found += 1
        out += mon * new
    if sp.expand(out.xreplace(defs.full) - expr.xreplace(defs.full)) != 0:
        raise ValueError("Internal check failed: Recognize changed the expression.")
    return Recognized(out, kept, found)

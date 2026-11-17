"""Model definitions ([definitions]: r_A1 = rmaxA - s*(x1 - thA)**2 …), both ways.

* Substitute: r_A1 -> rmaxA - s*(x1 - thA)**2 (repeated until no defined name is left).
* Recognize: the formulas -> r_A1…, wherever this is exact and unambiguous.

Recognize works coefficient by coefficient (one coefficient per product of moments,
as "Collect by all moments"), after substituting every definition. A coefficient c is
rewritten with its shortest exact writing

    c = α1·d1 + α2·d2 + … (+ rmaxA, with its own coefficient) + c0

where c0 and the α's no longer contain any symbol of the formulas (rmaxA, s, x1,
thA…). A symbol that appears alone in a formula (rmaxA) may stay as it was, but is
never added nor changed. With overlapping definitions (r_A1 = rmaxA - omega_A1),
several writings exist: the fewest terms win, then the smallest coefficients
(rmaxA + omega_A1 rather than r_A1 + 2*omega_A1). Without such a writing the
coefficient is kept as it is and reported. The result is checked: substituting the
definitions back gives the input exactly.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import itertools

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
def _lone_symbols(defs: Definitions) -> list[sp.Symbol]:
    """Symbols that appear alone, as a term of their own, in a formula (rmaxA in
    rmaxA - s*(x1 - thA)**2). They may stay in a result, with their own coefficient."""
    out = []
    for v in defs.symbols:
        mono = tuple(1 if x == v else 0 for x in defs.symbols)
        for f in defs.full.values():
            if sp.Poly(sp.expand(f), *defs.symbols).coeff_monomial(mono) != 0:
                out.append(v)
                break
    return out


def _decompose(c: sp.Expr, defs: Definitions) -> sp.Expr | None:
    """Shortest exact writing of c with the definitions, or None.

    c = Σ α_k·def_k + Σ β·lone + c0, where c0 no longer contains any symbol of the
    formulas; a lone symbol (rmaxA) may only keep its own coefficient in c; among the
    writings with the fewest terms, the one with the smallest coefficients."""
    D = defs.symbols
    lone = getattr(defs, "_lone", None)
    if lone is None:
        lone = _lone_symbols(defs)
        object.__setattr__(defs, "_lone", lone)
    poly = sp.Poly(sp.expand(c), *D)
    c0 = poly.coeff_monomial(tuple(0 for _ in D))
    cD = sp.expand(c - c0)
    if cD == 0:
        return None
    present = cD.free_symbols & set(D)
    gens = [(k, sp.expand(f)) for k, f in defs.full.items()] + [(v, v) for v in lone]
    gens = [(k, g) for k, g in gens if (g.free_symbols & set(D)) <= present]
    for size in range(1, len(gens) + 1):
        best = None
        for subset in itertools.combinations(gens, size):
            beta = sp.symbols(f"_beta0:{size}")
            rest = sp.Poly(sp.expand(cD - sum(b * g for b, (_, g) in zip(beta, subset))), *D)
            sol = sp.solve(rest.coeffs(), beta, dict=True)
            if len(sol) != 1 or set(sol[0]) != set(beta):
                continue
            s = sol[0]
            if any(s[b] == 0 or s[b].free_symbols & set(D) for b in beta):
                continue
            ok = True
            for b, (name, _) in zip(beta, subset):
                if name in lone:      # rmaxA: only with its own coefficient, never created
                    mono = tuple(1 if x == name else 0 for x in D)
                    if sp.simplify(s[b] - poly.coeff_monomial(mono)) != 0:
                        ok = False
            if not ok:
                continue
            cost = sum(abs(v) if v.is_number else 1 for v in s.values())
            if best is None or cost < best[0]:
                best = (cost, sum(s[b] * name for b, (name, _) in zip(beta, subset)))
        if best is not None:
            return sp.expand(best[1]) + sp.expand(c0)
    return None


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
    e = sp.expand(expr.xreplace(defs.full))       # first, everything with the base parameters
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

"""The stochastic process of the model: events, symmetries, moment equations by event.

[evenements] (or [events]): one explicit line per event, ``name = rate | jump``::

    naissance_A1 = rmaxA*NA1 | NA1+1
    mort_A1 = (s*(x1 - thA)**2 + (NA1 + NA2)/KA)*NA1 | NA1-1
    migration_A1_B1 = m*NA1 | NA1-1, NB1+1

[symetries] (or [symmetries]): swaps of variable codes and of parameters::

    phenotypes = A1<->A2, B1<->B2, x1<->x2
    niches = A1<->B1, A2<->B2, rmaxA<->rmaxB, KA<->KB, thA<->thB

Anything not listed is unchanged; the defined r_A1… follow from their formulas; the
combinations of the declared symmetries are added. A symmetry is *valid* when it maps
the set of events onto itself (same rates, same jumps): then every moment equation is
symmetric, at every order, before and after closure.

Moment equations (jump process):  d<f>/dt = Σ_e < w_e(N) [f(N + J_e) - f(N)] >,
written with E(body, event) for the expectation of one event's term.
"""

from __future__ import annotations

import itertools
import re
from dataclasses import dataclass, field

import sympy as sp

from .model import (KIND_DERIVATIVE, KIND_MOMENT, KIND_PARAMETER, KIND_STATE, KIND_UNKNOWN,
                    ModelError, ToolModel)


class E(sp.Function):
    """Expectation <body>; optional second argument: the event the term comes from."""

    nargs = (1, 2)

    @property
    def body(self) -> sp.Expr:
        return self.args[0]

    @property
    def tag(self) -> sp.Symbol | None:
        return self.args[1] if len(self.args) > 1 else None


@dataclass
class Event:
    name: str
    rate: sp.Expr
    jump: dict[str, int]          # state variable name (NA1) -> change


@dataclass
class Symmetry:
    name: str
    codes: dict[str, str]                       # A1 -> A2 … (complete permutation)
    params: dict[str, str]                      # x1 -> x2, x2 -> x1 … (parameters and r_…)
    events: dict[str, str] = field(default_factory=dict)   # event -> image event
    failures: list[str] = field(default_factory=list)     # events whose image is not an event
    checked: bool = False                       # False: no events declared

    @property
    def valid(self) -> bool:
        return self.checked and not self.failures


@dataclass
class Process:
    events: list[Event]
    symmetries: list[Symmetry]

    def symmetry(self, name: str) -> Symmetry:
        for s in self.symmetries:
            if s.name == name:
                return s
        raise ValueError(f"Unknown symmetry: {name}")


# ---------------------------------------------------------------- parsing
_JUMP = re.compile(r"^\s*([A-Za-z]\w*)\s*([+-])\s*(\d+)\s*$")


def _read_rate(name: str, text: str, model: ToolModel) -> sp.Expr:
    from .reading import read_expression
    r = read_expression(text, model)
    if not r.ok:
        errs = "; ".join(n.text for n in r.notes if n.level == "error") or "empty"
        raise ModelError(f"Event {name}: rate '{text}': {errs}")
    bad = [s for s, i in r.symbols.items()
           if i.kind not in (KIND_STATE, KIND_PARAMETER)]
    if bad:
        raise ModelError(f"Event {name}: the rate may only use variables NA1… and parameters "
                         f"(not {', '.join(sorted(bad))}).")
    return r.expr


def _read_jump(name: str, text: str, model: ToolModel) -> dict[str, int]:
    jump: dict[str, int] = {}
    for part in text.split(","):
        m = _JUMP.match(part)
        if not m or m.group(1) not in model.state_names:
            raise ModelError(f"Event {name}: jump '{part.strip()}' should look like NA1+1 or NA1-1 "
                             f"(variables: {', '.join(model.state_names)}).")
        var, sign, k = m.group(1), m.group(2), int(m.group(3))
        if var in jump:
            raise ModelError(f"Event {name}: {var} appears twice in the jump.")
        if k == 0:
            raise ModelError(f"Event {name}: a jump of 0 on {var}.")
        jump[var] = k if sign == "+" else -k
    return jump


def _parse_events(raw: list[tuple[str, str]], model: ToolModel) -> list[Event]:
    events: list[Event] = []
    taken = set(model.parameter_names) | set(model.state_names) | set(model.function_names)
    for name, value in raw:
        if not re.fullmatch(r"[A-Za-z]\w*", name):
            raise ModelError(f"Event name '{name}': letters, digits and _ only.")
        if name in taken or any(e.name == name for e in events):
            raise ModelError(f"Event name '{name}' is already used.")
        if "|" not in value:
            raise ModelError(f"Event {name}: write 'rate | jump', e.g. rmaxA*NA1 | NA1+1.")
        rate_text, jump_text = value.split("|", 1)
        rate = _read_rate(name, rate_text, model)
        jump = _read_jump(name, jump_text, model)
        for var, d in jump.items():
            if d < 0 and sp.simplify(rate.xreplace({model.symbol(var): 0})) != 0:
                raise ModelError(f"Event {name}: the rate does not vanish when {var} = 0 "
                                 f"(the population could become negative).")
        events.append(Event(name, rate, jump))
    return events


def _parse_symmetry(name: str, value: str, model: ToolModel) -> Symmetry:
    codes: dict[str, str] = {}
    params: dict[str, str] = {}
    for part in value.split(","):
        if not part.strip():
            continue
        m = re.fullmatch(r"\s*([A-Za-z]\w*)\s*<->\s*([A-Za-z]\w*)\s*", part)
        if not m:
            raise ModelError(f"Symmetry {name}: '{part.strip()}' should look like A1<->A2 or x1<->x2.")
        a, b = m.groups()
        is_code = [x in model.lp.var_order for x in (a, b)]
        if all(is_code):
            target = codes
        elif not any(is_code):
            for x in (a, b):
                if x not in model.parameter_names:
                    raise ModelError(f"Symmetry {name}: '{x}' is neither a variable code nor a parameter.")
            target = params
        else:
            raise ModelError(f"Symmetry {name}: '{part.strip()}' swaps a code with a parameter.")
        for x, y in ((a, b), (b, a)):
            if x in target and target[x] != y:
                raise ModelError(f"Symmetry {name}: {x} is swapped twice.")
            target[x] = y
    full = {c: codes.get(c, c) for c in model.codes}
    if sorted(full.values()) != sorted(full):
        raise ModelError(f"Symmetry {name}: the codes do not form a permutation.")
    return Symmetry(name, full, params)


def _derive_definitions(sym: Symmetry, model: ToolModel) -> None:
    """r_A1 -> r_A2 … from the formulas (error if an image is not a definition)."""
    from .definitions import definitions
    try:
        defs = definitions(model)
    except ValueError:
        return
    sub = {model.symbol(a): model.symbol(b) for a, b in sym.params.items()}
    for k, f in defs.full.items():
        img = f.xreplace(sub)
        hits = [k2 for k2, f2 in defs.full.items() if sp.expand(f2 - img) == 0]
        if len(hits) != 1:
            raise ModelError(f"Symmetry {sym.name}: the image of {k.name} = {sp.sstr(f)} is "
                             f"{sp.sstr(img)}, which is not a definition of the model.")
        if hits[0] != k:
            sym.params[k.name] = hits[0].name


def _compose(s1: Symmetry, s2: Symmetry, model: ToolModel) -> Symmetry:
    codes = {c: s2.codes[s1.codes[c]] for c in model.codes}
    names = set(s1.params) | set(s2.params)
    params = {}
    for n in names:
        img = s2.params.get(s1.params.get(n, n), s1.params.get(n, n))
        if img != n:
            params[n] = img
    return Symmetry(f"{s1.name} + {s2.name}", codes, params)


def symbol_map(sym: Symmetry, name: str, model: ToolModel) -> str:
    """Image of a (canonical) name by the symmetry."""
    info = model.classify(name)
    if info.kind == KIND_MOMENT:
        return model.moment_name(model.sort_codes([sym.codes[c] for c in info.codes]))
    if info.kind == KIND_STATE:
        return model.lp.variable_format.format(code=sym.codes[model.state_names[name]])
    if info.kind == KIND_DERIVATIVE:
        return model.derivative_name(symbol_map(sym, info.inner, model))
    if name in sym.params:
        return sym.params[name]
    if name in sym.events:
        return sym.events[name]
    return name


def _check_events(sym: Symmetry, events: list[Event], model: ToolModel) -> None:
    if not events:
        return
    sub = {}
    for e in events:
        for s in e.rate.free_symbols:
            sub[s] = model.symbol(symbol_map(sym, s.name, model))
    for e in events:
        rate = e.rate.xreplace(sub)
        jump = {symbol_map(sym, v, model): d for v, d in e.jump.items()}
        hit = [f for f in events if f.jump == jump and sp.cancel(f.rate - rate) == 0]
        if hit:
            sym.events[e.name] = hit[0].name
        else:
            sym.failures.append(e.name)
    sym.checked = True


def process(model: ToolModel) -> Process:
    """Events and symmetries of the model, checked (cached on the model)."""
    cached = getattr(model, "_process_cache", None)
    if cached is not None:
        return cached
    events = _parse_events(model.events_raw, model)
    base = [_parse_symmetry(n, v, model) for n, v in model.symmetries_raw]
    names = [s.name for s in base]
    if len(set(names)) != len(names):
        raise ModelError("Two symmetries have the same name.")
    for s in base:
        _derive_definitions(s, model)
    syms = list(base)
    ordered = sorted(base, key=lambda s: s.name)
    for k in range(2, len(ordered) + 1):
        for combo in itertools.combinations(ordered, k):
            c = combo[0]
            for nxt in combo[1:]:
                c = _compose(c, nxt, model)
            if all(c.codes != s.codes or c.params != s.params for s in syms):
                syms.append(c)
    for s in syms:
        _check_events(s, events, model)
    out = Process(events, syms)
    object.__setattr__(model, "_process_cache", out)
    return out


# ---------------------------------------------------------------- generate, take moments
def _state(model: ToolModel, code: str) -> sp.Symbol:
    return model.symbol(model.lp.variable_format.format(code=code))


def generate(moment: str, model: ToolModel) -> tuple[str, str]:
    """d<moment>/dt written event by event: (lhs text, rhs text)."""
    from .reading import resolve_name
    proc = process(model)
    if not proc.events:
        raise ValueError("The model has no events ([evenements] section).")
    res = resolve_name(moment.strip(), model)
    if res.error or res.info is None or res.info.kind != KIND_MOMENT:
        raise ValueError(res.error or f"'{moment}' is not a moment (n_A1, M_A1_A2, T_…).")
    f = sp.Mul(*[_state(model, c) for c in res.info.codes])
    terms = []
    for e in proc.events:
        sub = {model.symbol(v): model.symbol(v) + d for v, d in e.jump.items()}
        df = sp.factor_terms(sp.expand(f.xreplace(sub) - f))
        if df != 0:
            terms.append(E(e.rate * df, model.symbol(e.name)))
    lhs = model.derivative_name(res.canonical)
    return lhs, " + ".join(sp.sstr(t) for t in terms) if terms else "0"


def moments_rules(expr: sp.Expr, model: ToolModel) -> dict:
    """{E(…): its value in moments} for every E in the expression, and the monomial rules used."""
    states = [_state(model, c) for c in model.codes]
    code_of = {s: c for s, c in zip(states, model.codes)}
    out, monos = {}, {}
    for t in sorted(expr.atoms(E), key=sp.default_sort_key):
        # State-free pieces (rmaxA, s*(x1 - thA)**2, 1/KA…) are kept whole: they become
        # placeholders, the body is expanded in the variables only, then they come back.
        holders: dict = {}

        def atomize(x):
            if not (x.free_symbols & set(states)):
                if x.is_Number:
                    return x
                if x not in holders:
                    holders[x] = sp.Dummy(f"c{len(holders)}")
                return holders[x]
            if x.is_Add or x.is_Mul or x.is_Pow:
                return x.func(*[atomize(a) for a in x.args])
            return x

        body = sp.expand(atomize(t.body))
        try:
            poly = sp.Poly(body, *states)
        except sp.PolynomialError:
            raise ValueError(f"{sp.sstr(t)}: not a polynomial in {', '.join(map(str, states))}.")
        back = {d: x for x, d in holders.items()}
        groups: dict = {}          # product of state-free pieces -> Σ number·moment
        for mon, c in poly.terms():
            codes = [code_of[s] for s, k in zip(states, mon) for _ in range(k)]
            if codes:
                mono = sp.Mul(*[s ** k for s, k in zip(states, mon)])
                mom = model.symbol(model.moment_name(model.sort_codes(codes)))
                monos[mono] = mom
            else:
                mom = sp.S.One
            for term in sp.Add.make_args(sp.expand(c)):
                num, rest = term.as_coeff_Mul()
                groups[rest] = groups.get(rest, 0) + num * mom
        parts = []
        for rest, total in groups.items():
            r = rest.xreplace(back)
            negative = all(a.could_extract_minus_sign() for a in sp.Add.make_args(total))
            parts.append(-(r * -total) if negative and r != 1 else r * total)
        out[t] = sp.Add(*parts)
    return out, monos


def state_symbols_outside_e(expr: sp.Expr, model: ToolModel) -> list[str]:
    inside = set()
    for t in expr.atoms(E):
        inside |= t.free_symbols
    rest = expr.xreplace({t: sp.S.Zero for t in expr.atoms(E)})
    return sorted(s.name for s in rest.free_symbols if model.classify(s.name).kind == KIND_STATE)


def is_event_name(name: str, model: ToolModel) -> bool:
    return name in {n for n, _ in model.events_raw}


__all__ = ["E", "Event", "Symmetry", "Process", "process", "generate", "moments_rules",
           "symbol_map", "KIND_UNKNOWN"]

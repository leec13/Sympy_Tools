"""Model: the latex-preview .ini file, plus SymPy assumptions and a symbol registry.

The file format is the one of latex-preview (``latex_preview.core.model``), read
with French *or* English section and key names, plus an optional section
``[hypotheses]`` (or ``[assumptions]``) that latex-preview ignores::

    [hypotheses]
    positive = rmaxA, rmaxB, s, KA, KB, m
    real = x1, x2, thA, thB

Every symbol used by the application is created here, from its name, so that
one name always gives the same SymPy symbol (same assumptions). Comparing two
expressions read separately is reliable only under that condition.
"""

from __future__ import annotations

import configparser
import re
from dataclasses import dataclass, field

import sympy as sp
from latex_preview.core.model import DEFAULT_MODEL as LP_DEFAULT_MODEL
from latex_preview.core.model import Model, ModelError, parse_model

__all__ = ["DEFAULT_MODEL", "ModelError", "ToolModel", "load_model", "SymbolInfo"]

DEFAULT_MODEL = LP_DEFAULT_MODEL.rstrip("\n") + """

[hypotheses]
# SymPy assumptions (ignored by latex-preview): positive, nonnegative, negative,
# nonpositive, real. They change what Simplify can do: sqrt(x**2) -> Abs(x) only if x is real.
positive = rmaxA, rmaxB, s, KA, KB, m
real = x1, x2, thA, thB

[evenements]
# The stochastic process (ignored by latex-preview), one line per event:
#   name = rate | jump
# Each individual of (niche i, phenotype k): birth at rate rmax_i, death at rate
# s*(x_k - th_i)**2 + N_i/K_i (N_i = total of niche i), migration to the other niche at rate m.
naissance_A1 = rmaxA*NA1 | NA1+1
mort_A1 = (s*(x1 - thA)**2 + (NA1 + NA2)/KA)*NA1 | NA1-1
migration_A1_B1 = m*NA1 | NA1-1, NB1+1
naissance_A2 = rmaxA*NA2 | NA2+1
mort_A2 = (s*(x2 - thA)**2 + (NA1 + NA2)/KA)*NA2 | NA2-1
migration_A2_B2 = m*NA2 | NA2-1, NB2+1
naissance_B1 = rmaxB*NB1 | NB1+1
mort_B1 = (s*(x1 - thB)**2 + (NB1 + NB2)/KB)*NB1 | NB1-1
migration_B1_A1 = m*NB1 | NB1-1, NA1+1
naissance_B2 = rmaxB*NB2 | NB2+1
mort_B2 = (s*(x2 - thB)**2 + (NB1 + NB2)/KB)*NB2 | NB2-1
migration_B2_A2 = m*NB2 | NB2-1, NA2+1

[symetries]
# Swaps of variable codes and of parameters; anything not listed is unchanged,
# r_A1… follow from their definitions, combinations are added automatically.
phenotypes = A1<->A2, B1<->B2, x1<->x2
niches = A1<->B1, A2<->B2, rmaxA<->rmaxB, KA<->KB, thA<->thB
"""

# English name -> French name used by latex-preview.
_SECTION_ALIASES = {
    "variables": "variables",
    "moments": "moments",
    "parametres": "parametres", "parameters": "parametres",
    "fonctions": "fonctions", "functions": "fonctions",
    "definitions": "definitions",
    "hypotheses": "hypotheses", "assumptions": "hypotheses",
    "evenements": "evenements", "events": "evenements",
    "symetries": "symetries", "symmetries": "symetries",
}
_MOMENT_KEY_ALIASES = {
    "prefixes": "prefixes",
    "separateur": "separateur", "separator": "separateur",
    "derivee": "derivee", "derivative": "derivee",
    "variable": "variable",
}
ASSUMPTIONS = ("positive", "nonnegative", "negative", "nonpositive", "real")

# Symbol kinds, in display order.
KIND_MOMENT = "moment"
KIND_DERIVATIVE = "derivative"
KIND_STATE = "state"
KIND_PARAMETER = "parameter"
KIND_FUNCTION = "function"
KIND_EVENT = "event"
KIND_UNKNOWN = "unknown"


@dataclass(frozen=True)
class SymbolInfo:
    """What a (canonical) name stands for."""

    name: str
    kind: str
    codes: tuple[str, ...] = ()     # moment: variable codes, in canonical order
    inner: str = ""                 # derivative: name of the differentiated symbol

    @property
    def order(self) -> int:
        return len(self.codes)


def _configparser() -> configparser.ConfigParser:
    cp = configparser.ConfigParser(interpolation=None, delimiters=("=",),
                                   comment_prefixes=("#",), inline_comment_prefixes=None,
                                   strict=False, empty_lines_in_values=False)
    cp.optionxform = str  # keep case (KA != ka)
    return cp


def normalize_ini(text: str) -> tuple[str, dict[str, list[str]], list, list]:
    """French/English names -> the French text latex-preview reads, and our own sections.

    Returns (text for latex_preview.parse_model, {assumption: [names]},
    [(event, "rate | jump")], [(symmetry, "A1<->A2, …")])."""
    src = _configparser()
    try:
        src.read_string(text)
    except configparser.Error as exc:
        raise ModelError(f"Unreadable model file: {exc}") from exc
    out = _configparser()
    hyp: dict[str, list[str]] = {}
    events: list[tuple[str, str]] = []
    symmetries: list[tuple[str, str]] = []
    seen: set[str] = set()
    for section in src.sections():
        target = _SECTION_ALIASES.get(section.strip().lower())
        if target is None:
            raise ModelError(f"Unknown section [{section}].")
        if target in ("evenements", "symetries"):
            if target in seen:
                raise ModelError(f"Section [{section}] is given twice (French and English names).")
            seen.add(target)
            (events if target == "evenements" else symmetries).extend(
                (k.strip(), v.strip()) for k, v in src.items(section))
            continue
        if target == "hypotheses":
            for key, value in src.items(section):
                k = key.strip().lower()
                if k not in ASSUMPTIONS:
                    raise ModelError(f"[{section}] '{key}': unknown assumption "
                                     f"(use {', '.join(ASSUMPTIONS)}).")
                names = [n for n in re.split(r"[,\s]+", value) if n]
                hyp.setdefault(k, []).extend(names)
            continue
        if out.has_section(target):
            raise ModelError(f"Section [{section}] is given twice (French and English names).")
        out.add_section(target)
        for key, value in src.items(section):
            if target == "moments":
                k = _MOMENT_KEY_ALIASES.get(key.strip().lower())
                if k is None:
                    raise ModelError(f"[moments] '{key}': unknown key.")
                key = k
            out.set(target, key, value)
    lines = []
    for section in out.sections():
        lines.append(f"[{section}]")
        lines += [f"{k} = {v}" for k, v in out.items(section)]
        lines.append("")
    return "\n".join(lines), hyp, events, symmetries


@dataclass
class ToolModel:
    """latex-preview model + symbol registry."""

    lp: Model
    assumptions: dict[str, dict[str, bool]] = field(default_factory=dict)  # name -> {real: True}
    events_raw: list[tuple[str, str]] = field(default_factory=list)       # [(name, "rate | jump")]
    symmetries_raw: list[tuple[str, str]] = field(default_factory=list)   # [(name, "A1<->A2, …")]
    _symbols: dict[str, sp.Symbol] = field(default_factory=dict, repr=False)
    _functions: dict[str, type] = field(default_factory=dict, repr=False)

    # ------------------------------------------------------------ contents
    @property
    def codes(self) -> list[str]:
        return [c for c, _ in self.lp.variables]

    @property
    def parameter_names(self) -> list[str]:
        return [n for n, _ in self.lp.parameters]

    @property
    def function_names(self) -> list[str]:
        return [n for n, _ in self.lp.functions]

    @property
    def state_names(self) -> dict[str, str]:
        """{'NA1': 'A1', …}"""
        return dict(self.lp.var_python)

    def summary(self) -> str:
        codes = ", ".join(self.codes)
        return f"{len(self.codes)} variables ({codes}), {len(self.lp.parameters)} parameters"

    # ------------------------------------------------------------ names
    def moment_name(self, codes) -> str:
        return self.lp.moment_name(list(codes))

    def sort_codes(self, codes) -> tuple[str, ...]:
        return tuple(sorted(codes, key=lambda c: self.lp.var_order[c]))

    def derivative_name(self, inner: str) -> str:
        return self.lp.derivative_name(inner)

    def split_derivative(self, name: str) -> str | None:
        """'dM_A1_A2_dt' -> 'M_A1_A2' (format of the model), else None."""
        pat = re.escape(self.lp.derivative).replace(r"\{nom\}", r"(?P<n>[A-Za-z]\w*?)")
        m = re.fullmatch(pat, name)
        return m.group("n") if m else None

    def is_prefix(self, head: str) -> bool:
        return head in self.lp.prefixes or re.fullmatch(r"X\d+", head) is not None

    # ------------------------------------------------------------ symbols
    def symbol(self, name: str) -> sp.Symbol:
        s = self._symbols.get(name)
        if s is None:
            s = sp.Symbol(name, **self.assumptions.get(name, {}))
            self._symbols[name] = s
        return s

    def function(self, name: str):
        f = self._functions.get(name)
        if f is None:
            f = sp.Function(name)
            self._functions[name] = f
        return f

    # ------------------------------------------------------------ LaTeX
    def latex_name(self, info: SymbolInfo) -> str | None:
        """LaTeX of a symbol according to the model (None: let SymPy write it)."""
        if info.kind == KIND_MOMENT:
            return self.lp.moment_latex(list(info.codes))
        if info.kind == KIND_PARAMETER:
            return self.lp.param_latex.get(info.name)
        if info.kind == KIND_STATE:
            return self.lp.var_latex.get(self.state_names[info.name])
        if info.kind == KIND_FUNCTION:
            return self.lp.function_latex.get(info.name)
        if info.kind == KIND_DERIVATIVE:
            inner = self.classify(info.inner)
            body = self.latex_name(inner) if inner else None
            if body is None:
                body = sp.latex(sp.Symbol(info.inner))
            return r"\frac{d}{d t} " + body
        return None

    # ------------------------------------------------------------ classification
    def classify(self, name: str) -> SymbolInfo | None:
        """Kind of a *valid canonical* name (no checks, no corrections)."""
        if name in self.parameter_names:
            return SymbolInfo(name, KIND_PARAMETER)
        if name in self.state_names:
            return SymbolInfo(name, KIND_STATE)
        if name in self.function_names:
            return SymbolInfo(name, KIND_FUNCTION)
        if any(name == n for n, _ in self.events_raw):
            return SymbolInfo(name, KIND_EVENT)
        codes = self.lp.parse_moment_name(name)
        if codes is not None and tuple(codes) == self.sort_codes(codes):
            return SymbolInfo(name, KIND_MOMENT, tuple(codes))
        inner = self.split_derivative(name)
        if inner is not None:
            return SymbolInfo(name, KIND_DERIVATIVE, inner=inner)
        return SymbolInfo(name, KIND_UNKNOWN)


def load_model(text: str | None = None) -> ToolModel:
    """Read a model (.ini text). None or empty: the default model."""
    if not text or not text.strip():
        text = DEFAULT_MODEL
    lp_text, hyp, events, symmetries = normalize_ini(text)
    lp = parse_model(lp_text)
    assumptions: dict[str, dict[str, bool]] = {}
    for key, names in hyp.items():
        for n in names:
            if not re.fullmatch(r"[A-Za-z]\w*", n):
                raise ModelError(f"[hypotheses] '{n}' is not a valid name.")
            assumptions.setdefault(n, {})[key] = True
    model = ToolModel(lp=lp, assumptions=assumptions, events_raw=events, symmetries_raw=symmetries)
    from .process import process      # checks events and symmetries (ModelError if wrong)
    process(model)
    return model

"""Entry points "strings in, strings out", run in a separate (interruptible) process."""

from __future__ import annotations

from functools import lru_cache

from .model import load_model
from .operations import apply
from .output import overleaf, result_latex
from .reading import read_equation, read_expression

EXPRESSION, EQUATION = "expression", "equation"


@lru_cache(maxsize=4)
def _model(text: str):
    return load_model(text)


def run_operation(model_text: str, mode: str, text: str = "", lhs: str = "", rhs: str = "",
                  op: str = "", var: str = "") -> dict:
    """Read the input, apply the operation, return everything the interface shows."""
    try:
        model = _model(model_text)
        reading = (read_equation(lhs, rhs, model) if mode == EQUATION
                   else read_expression(text, model))
        res = apply(op, reading, model, var or None)
        if not res.ok:
            return {"ok": False, "error": res.error}
        lat = result_latex(res, model)
        out = {
            "ok": True, "error": "", "op": op,
            "code": "\n".join(res.code),
            "python": res.text,
            "latex": lat,
            "overleaf": overleaf(lat),
            "verdict": res.verdict, "verdict_text": res.verdict_text,
            "notes": res.notes,
            "is_equation": res.is_equation,
        }
        if res.is_equation:
            import sympy as sp
            out["lhs"], out["rhs"] = sp.sstr(res.lhs), sp.sstr(res.rhs)
        return out
    except Exception as exc:  # noqa: BLE001 - reported in the interface
        return {"ok": False, "error": f"Internal error ({type(exc).__name__}): {exc}"}


def warm_up() -> bool:
    run_operation("", EXPRESSION, text="x + 1", op="expand")
    return True

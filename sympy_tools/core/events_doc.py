"""LaTeX document "events and symmetries": one table per symmetry, ✓ / ✗ per event."""

from __future__ import annotations

import shutil
import subprocess
import tempfile
from pathlib import Path

import sympy as sp

from .model import ToolModel
from .output import event_label, latex
from .process import process, symbol_map

COLORS = {"KA": "red", "KB": "blue"}   # carrying capacities: niche A in red, niche B in blue

_PREAMBLE = r"""\documentclass[11pt]{article}
\usepackage[a4paper,margin=1.5cm]{geometry}
\usepackage[T1]{fontenc}\usepackage[utf8]{inputenc}
\usepackage{amsmath,amssymb,xcolor,array}
\setlength{\parindent}{0pt}
\begin{document}
"""


def _coloured(model: ToolModel) -> ToolModel:
    """Same model, with coloured LaTeX names for the carrying capacities."""
    saved = dict(model.lp.param_latex)
    for name, colour in COLORS.items():
        if name in saved:
            model.lp.param_latex[name] = rf"\textcolor{{{colour}}}{{{saved[name]}}}"
    return saved


def events_document(model: ToolModel) -> str:
    proc = process(model)
    saved = _coloured(model)
    try:
        out = [_PREAMBLE, r"{\Large\bfseries Events and symmetries}\par\medskip"]
        if not proc.events:
            out.append(r"The model has no events (section \texttt{[evenements]}).")
            return "\n".join(out) + "\n\\end{document}\n"
        out.append(r"A symmetry is valid when the image of every event is an event of the process, "
                   r"with the same rate and the same jump. Then every moment equation is symmetric, "
                   r"at every order, before and after closure.")
        if not proc.symmetries:
            out.append(r"\par\medskip The model declares no symmetry (section \texttt{[symetries]}).")
        for sym in proc.symmetries:
            n_bad = len(sym.failures)
            verdict = (r"\textcolor{green!50!black}{valid}" if not n_bad else
                       rf"\textcolor{{red}}{{not valid: {n_bad} event{'s' if n_bad > 1 else ''} \texttimes}}")
            out.append(rf"\section*{{Symmetry {sym.name} --- {verdict}}}")
            out.append(r"{\small\renewcommand{\arraystretch}{1.5}"
                       r"\begin{tabular}{p{3.0cm} >{$}l<{$} c p{3.0cm} >{$}l<{$} c}")
            out.append(r"\textbf{Event} & \textbf{rate} & & \textbf{Image} & \textbf{rate of the image} & \\ \hline")
            for e in proc.events:
                sub = {s: model.symbol(symbol_map(sym, s.name, model)) for s in e.rate.free_symbols}
                img_rate = e.rate.xreplace(sub)
                image = sym.events.get(e.name)
                ok = image is not None
                mark = r"\textcolor{green!50!black}{\checkmark}" if ok else r"\textcolor{red}{$\times$}"
                img_label = event_label(image, model) if ok else r"\textit{no such event}"
                out.append(rf"{event_label(e.name, model)} & {latex(e.rate, model)} & $\mapsto$ & "
                           rf"{img_label} & {latex(img_rate, model)} & {mark} \\")
            out.append(r"\end{tabular}}")
        return "\n".join(out) + "\n\\end{document}\n"
    finally:
        model.lp.param_latex.clear()
        model.lp.param_latex.update(saved)


def compile_document(tex: str, timeout: float = 60.0) -> tuple[bytes | None, str]:
    """(pdf bytes, error message)."""
    engine = shutil.which("pdflatex")
    if engine is None:
        from latex_preview.core.compiler import find_engine
        engine = find_engine("pdflatex")
    if engine is None:
        return None, "pdflatex not found: install TeX Live / MacTeX."
    with tempfile.TemporaryDirectory(prefix="sympy_tools_") as d:
        path = Path(d) / "events.tex"
        path.write_text(tex, encoding="utf-8")
        try:
            proc = subprocess.run([str(engine), "-interaction=nonstopmode", "-halt-on-error", path.name],
                                  cwd=d, capture_output=True, text=True, timeout=timeout)
        except subprocess.TimeoutExpired:
            return None, "LaTeX took too long."
        pdf = Path(d) / "events.pdf"
        if proc.returncode != 0 or not pdf.exists():
            lines = [l for l in proc.stdout.splitlines() if l.startswith("!")]
            return None, "LaTeX error: " + (lines[0] if lines else "see the log")
        return pdf.read_bytes(), ""


__all__ = ["events_document", "compile_document", "sp"]

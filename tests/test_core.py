"""Core tests (python -m pytest tests).

Cases "VALIDATED n" are the examples of the v0.1 specification, agreed with the
user on 16/11/2026: they are expected behaviours, not internal choices.
"""
import pathlib

import pytest
import sympy as sp

from sympy_tools.core.jobs import EQUATION, EXPRESSION, run_operation
from sympy_tools.core.model import DEFAULT_MODEL, ModelError, load_model
from sympy_tools.core.operations import (ALL_MOMENTS, COLLECT, COMPARE, DIFFERENT, EQUAL, EXPAND,
                                         FACTOR, SIMPLIFY, UNDETERMINED, apply)
from sympy_tools.core.output import latex, overleaf, result_latex
from sympy_tools.core.reading import (INFO, WARNING, categories, read_equation,
                                      read_expression, split_equation)

DATA = pathlib.Path(__file__).parent / "data"
M = load_model()


def read(t):
    return read_expression(t, M)


def levels(r):
    return [n.level for n in r.notes]


def texts(r):
    return " | ".join(n.text for n in r.notes)


def ok(r):
    assert r.ok, texts(r)
    return r


# ------------------------------------------------------------------ model
def test_default_model():
    assert M.codes == ["A1", "A2", "B1", "B2"]
    assert M.symbol("KA").is_positive and M.symbol("x1").is_real
    assert M.symbol("M_A1_A1") is M.symbol("M_A1_A1")      # one name, one symbol


def test_model_english_keys_and_assumptions():
    text = """
[variables]
A1 = N_{A}^{x_1}
B1 = N_{B}^{x_1}
[moments]
prefixes = n, M, T
separator = _
derivative = d{nom}_dt
[parameters]
KA = K_A
[assumptions]
positive = KA, delta
"""
    m = load_model(text)
    assert m.parameter_names == ["KA"]
    assert m.symbol("delta").is_positive        # assumption on a symbol outside the model
    assert m.derivative_name("n_A1") == "dn_A1_dt"


@pytest.mark.parametrize("bad, msg", [
    ("[variables]\nA1 = N\n[bogus]\nx = 1\n", "Unknown section"),
    ("[variables]\nA1 = N\n[hypotheses]\nbig = KA\n", "unknown assumption"),
    ("[variables]\nA1 = N\n[parametres]\nKA = K\n[parameters]\nKB = K\n", "twice"),
])
def test_model_errors(bad, msg):
    with pytest.raises(ModelError, match=msg):
        load_model(bad)


def test_default_model_still_read_by_latex_preview():
    from latex_preview.core.model import parse_model
    assert parse_model(DEFAULT_MODEL).var_order["A1"] == 0


# ------------------------------------------------------------------ VALIDATED 1-6: reading
def test_validated_1_non_numeric_exponent():
    r = ok(read("2*M_A1_A1** + M_A1_A1"))
    assert r.text == "2*M_A1_A1**M_A1_A1"
    assert WARNING in levels(r) and "non-numeric exponent" in texts(r)


def test_validated_1b_unknown_code():
    r = read("2*M_A1_A1** + M_A1_MA1")
    assert not r.ok and "M_A1_MA1: unknown code 'MA1' (codes: A1, A2, B1, B2)" in texts(r)


def test_validated_2_prefix_and_order():
    r = read("M_A1_A1_A2")
    assert not r.ok and "3 indices, so T_A1_A1_A2" in texts(r)


def test_validated_3_reordered():
    r = ok(read("M_A2_A1"))
    assert r.text == "M_A1_A2" and levels(r) == [INFO] and "M_A2_A1 → M_A1_A2" in texts(r)
    assert r.written == {"M_A1_A2": "M_A2_A1"}


def test_validated_4_not_in_model():
    r = ok(read("delta*n_A1"))
    assert r.text == "delta*n_A1" and "delta: not in model" in texts(r)
    assert ("Not in model", ["delta"]) in categories(r.symbols, M)


def test_validated_5_caret():
    r = ok(read("n_A1^2"))
    assert r.text == "n_A1**2" and "^ read as **" in texts(r)


def test_validated_6_equation_split_and_derivative():
    lhs, rhs = split_equation("dM_A1_A1_dt = 2*M_A1_A1*rmaxA")
    e = read_equation(lhs, rhs, M)
    assert e.ok and e.text == "dM_A1_A1_dt = 2*M_A1_A1*rmaxA"
    assert ("Derivatives", ["dM_A1_A1_dt"]) in categories(e.symbols, M)
    assert split_equation("a == b") is None and split_equation("a = b = c") is None


@pytest.mark.parametrize("text, msg", [
    ("s(x1 - thA)**2", "s is not a function. Did you mean s*(…)?"),
    ("2*(n_A1 + n_A2", "missing ')'"),
    ("lambda*n_A1", "'lambda' is a Python keyword"),
    ("exp*2", "'exp' is a function"),
    (r"\frac{1}{2}", "looks like LaTeX"),
    ("n_A1 = 2", "use Equation mode"),
    ("n_A1 ; 2", "not allowed"),
    ("1/(n_A1 - n_A1)", "division by zero"),
    ("n_total", "unknown code 'total'"),
])
def test_reading_errors(text, msg):
    r = read(text)
    assert not r.ok and msg in texts(r)


def test_sympy_names_are_plain_symbols():
    r = ok(read("N*E + S + I + Q + gamma"))
    assert all(isinstance(s, sp.Symbol) for s in r.expr.free_symbols)
    assert len(r.expr.free_symbols) == 6


def test_slash_derivative_and_suggestion():
    r = ok(read("dM_A2_A1/dt + rmaxa"))
    assert r.text == "dM_A1_A2_dt + rmaxa"
    assert "dM_A2_A1/dt → dM_A1_A2_dt" in texts(r) and "did you mean rmaxA?" in texts(r)


# ------------------------------------------------------------------ VALIDATED 7-15: operations
def op(name, text, var=None):
    res = apply(name, ok(read(text)), M, var)
    assert res.ok, res.error
    return res


def cmp(a, b):
    res = apply(COMPARE, read_equation(a, b, M), M)
    assert res.ok, res.error
    return res


def test_validated_7_expand():
    r = op(EXPAND, "(n_A1 + n_A2)**2")
    assert r.text == "n_A1**2 + 2*n_A1*n_A2 + n_A2**2" and r.code == ["result = sp.expand(expr)"]


def test_validated_8_factor():
    assert op(FACTOR, "M_A1_A1*m - M_A1_A1*rmaxA").text == "M_A1_A1*(m - rmaxA)"


def test_validated_9_collect():
    r = op(COLLECT, "M_A1_A1*m + 2*M_A1_A1*rmaxA + n_A1*m", "M_A1_A1")
    assert r.text == "M_A1_A1*(m + 2*rmaxA) + m*n_A1"
    assert r.code == ["result = sp.collect(sp.expand(expr), M_A1_A1)"]


EX10 = "m*(n_A1 + n_B1 + 2*M_A1_B1 - 2*M_A1_A1) + rmaxA*(n_A1 + 2*M_A1_A1) + (M_A1_A1 + M_A1_A2)/KA"


def test_validated_10_collect_all_moments():
    r = op(COLLECT, EX10, ALL_MOMENTS)
    assert r.text == ("M_A1_A1*(-2*m + 2*rmaxA + 1/KA) + 2*M_A1_B1*m + m*n_B1 "
                      "+ n_A1*(m + rmaxA) + M_A1_A2/KA")
    assert r.code == ["result = sp.collect(sp.expand(expr), [n_A1, n_B1, M_A1_A1, M_A1_A2, M_A1_B1])"]


def test_validated_11_compare_equal():
    r = cmp("(M_A1_A1 + M_A1_A2)/KA", "M_A1_A1/KA + M_A1_A2/KA")
    assert r.verdict == EQUAL and r.verdict_text == "Equal (proved)"
    assert r.code == ["equal = sp.cancel(lhs - rhs) == 0"]


def test_validated_12_compare_different():
    r = cmp("M_A1_A1 + M_A1_A2/KA", "(M_A1_A1 + M_A1_A2)/KA")
    assert r.verdict == DIFFERENT and r.text == "M_A1_A1*(KA - 1)/KA"


def test_validated_13_compare_with_simplify():
    r = cmp("exp(x1)*exp(s)", "exp(x1 + s)")
    assert r.verdict == EQUAL and r.code == ["equal = sp.simplify(lhs - rhs) == 0"]


def test_validated_14_simplify_each_side():
    factored = sp.sstr(sp.factor(ok(read(EX10)).expr))
    e = read_equation(EX10, factored, M)
    r = apply(SIMPLIFY, e, M)
    assert r.is_equation and r.code == ["lhs = sp.simplify(lhs)", "rhs = sp.simplify(rhs)"]
    assert apply(COMPARE, e, M).verdict == EQUAL


def test_validated_15_result_can_be_read_again():
    r = op(COLLECT, EX10, ALL_MOMENTS)
    again = ok(read(r.text))
    assert sp.expand(again.expr - r.expr) == 0


def test_compare_assumptions_and_numeric_check():
    assert cmp("sqrt(KA**2)", "KA").verdict == EQUAL                     # KA > 0
    r = cmp("sqrt(x1**2)", "x1")                                        # x1 real: |x1| != x1
    assert r.verdict == DIFFERENT and "Test point" in r.notes[0]
    assert cmp("sqrt(delta**2)", "delta").verdict == UNDETERMINED       # no assumption on delta
    assert cmp("0.5*n_A1", "n_A1/2").verdict == EQUAL


def test_compare_needs_equation():
    r = apply(COMPARE, read("n_A1"), M)
    assert not r.ok and "Equation mode" in r.error


# ------------------------------------------------------------------ real equations
def _closure_lines():
    return [split_equation(l) for l in (DATA / "moment_closure_L2.txt").read_text().splitlines()]


def test_moment_closure_output_reads_without_unknown_names():
    lines = _closure_lines()
    assert len(lines) == 14
    for lhs, rhs in lines:
        e = read_equation(lhs, rhs, M)
        assert e.ok, e.notes
        assert not any(i.kind == "unknown" for i in e.symbols.values())


def test_latex_preview_translation_equals_moment_closure():
    """latex-preview's translation of the LaTeX equation == moment_closure.py output."""
    from latex_preview.core.translate import latex_to_python
    tex = (DATA / "script_M_A1_A1.tex").read_text()
    lp = latex_to_python(tex, DEFAULT_MODEL)
    assert lp["ok"], lp["error"]
    _, lp_rhs = split_equation(lp["python"])
    mc_rhs = dict(_closure_lines())["dM_A1_A1/dt"]
    assert cmp(lp_rhs, mc_rhs).verdict == EQUAL


def test_script_2_error_is_found():
    """d<(N_A^1)^2>/dt of Sympy_moments_python_code.py (before closure) vs the exact equation."""
    script2 = ("-2*M_A1_A1*s*(-thA + x1)**2 + n_A1*s*(-thA + x1)**2 + rmaxA*(2*M_A1_A1 + n_A1)"
               " + (M_A1_A1 + M_A1_A2/KA - 2*(T_A1_A1_A1 + T_A1_A1_A2)/KA)")
    exact = ("m*(-2*M_A1_A1 + 2*M_A1_B1 + n_A1 + n_B1) + rmaxA*(2*M_A1_A1 + n_A1)"
             " + s*(x1 - thA)**2*(n_A1 - 2*M_A1_A1)"
             " + (M_A1_A1 + M_A1_A2 - 2*T_A1_A1_A1 - 2*T_A1_A1_A2)/KA")
    r = cmp(script2, exact)
    assert r.verdict == DIFFERENT
    expected = read("M_A1_A1*(KA - 1)/KA - m*(-2*M_A1_A1 + 2*M_A1_B1 + n_A1 + n_B1)").expr
    assert sp.expand(r.expr - expected) == 0


# ------------------------------------------------------------------ outputs
def test_latex_names_from_model():
    lat = latex(ok(read("M_A1_A1 + NA1**2 + dM_A1_A2_dt + thA")).expr, M)
    assert r"\langle (N_{A}^{x_1})^{2} \rangle" in lat
    assert r"\left(N_{A}^{x_1}\right)^{2}" in lat           # no double superscript
    assert r"\frac{d}{d t} \langle N_{A}^{x_1} N_{A}^{x_2} \rangle" in lat
    assert r"\theta_A" in lat


def test_overleaf_uses_dmath():
    code = overleaf(r"\frac{d}{d t} x = x")
    assert code.startswith(r"\begin{dmath*}") and code.endswith(r"\end{dmath*}")


def test_compare_latex():
    r = cmp("M_A1_A1 + M_A1_A2/KA", "(M_A1_A1 + M_A1_A2)/KA")
    assert result_latex(r, M).startswith(r"\mathrm{lhs} - \mathrm{rhs} = ")


def test_job_strings_in_strings_out():
    out = run_operation("", EQUATION, lhs="dM_A1_A1_dt", rhs="M_A1_A1*m + n_A1*m", op=COLLECT,
                        var="M_A1_A1")
    assert out["ok"] and out["lhs"] == "dM_A1_A1_dt" and out["rhs"] == "M_A1_A1*m + m*n_A1"
    assert "dmath*" in out["overleaf"]
    bad = run_operation("", EXPRESSION, text="M_A1_MA1", op=EXPAND)
    assert not bad["ok"] and "correct them first" in bad["error"]

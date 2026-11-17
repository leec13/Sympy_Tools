"""Core tests (python -m pytest tests).

Cases "VALIDATED n" are the examples of the v0.1 specification, agreed with the
user on 16/11/2026: they are expected behaviours, not internal choices.
"""
import pathlib
import re

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


def test_collect_all_moments_by_products_of_moments():
    """Closed equations: one coefficient per product of moments (n_A1*M_A1_B1…)."""
    lines = dict(_closure_lines())
    rhs = lines["dM_A1_B1/dt"]
    r = op(COLLECT, rhs, ALL_MOMENTS)
    assert "M_A1_B1*(-2*m + rmaxA + rmaxB" in r.text
    assert "- 2*M_A1_B1*n_B1/KB" in r.text            # a product of moments kept as one term
    code = r.code[0]
    assert code.startswith("result = sp.collect(sp.expand(expr), [n_A1**2*n_B1, ")
    assert "M_A1_B1*n_A1" in code and code.endswith("M_A1_B1, M_B1_B1])")
    assert sp.expand(r.expr - read(rhs).expr) == 0


# ------------------------------------------------------------------ v0.2 (VALIDATED 16-26, 16/11/2026)
from sympy_tools.core.operations import ISSERLIS, RECOGNIZE, SUBSTITUTE, available  # noqa: E402


@pytest.mark.parametrize("num, text, expected", [
    (16, "T_A1_A1_A1", "3*M_A1_A1*n_A1 - 2*n_A1**3"),
    (17, "T_A1_A1_A2", "M_A1_A1*n_A2 + 2*M_A1_A2*n_A1 - 2*n_A1**2*n_A2"),
    (18, "T_A1_A2_B1", "M_A1_A2*n_B1 + M_A1_B1*n_A2 + M_A2_B1*n_A1 - 2*n_A1*n_A2*n_B1"),
])
def test_validated_16_18_isserlis(num, text, expected):
    r = op(ISSERLIS, text)
    assert r.text == expected
    assert r.code == [f"rules = {{{text}: {expected}}}", "result = expr.xreplace(rules)"]


EXACT_A1A1 = ("m*(-2*M_A1_A1 + 2*M_A1_B1 + n_A1 + n_B1) + rmaxA*(2*M_A1_A1 + n_A1)"
              " + s*(x1 - thA)**2*(n_A1 - 2*M_A1_A1)"
              " + (M_A1_A1 + M_A1_A2 - 2*T_A1_A1_A1 - 2*T_A1_A1_A2)/KA")


def test_validated_19_isserlis_equals_moment_closure_level_2():
    closed = op(ISSERLIS, EXACT_A1A1)
    mc = dict(_closure_lines())["dM_A1_A1/dt"]
    assert cmp(closed.text, mc).verdict == EQUAL


def test_isserlis_leaves_fourth_order_and_equation_sides():
    r = op(ISSERLIS, "T_A1_A1_A1 + Q_A1_A1_A1_A1")
    assert "Q_A1_A1_A1_A1" in r.text and "order 4 or more are not closed" in " ".join(r.notes)
    e = apply(ISSERLIS, read_equation("dT_A1_A1_A1_dt", "T_A1_A1_A1*m", M), M)
    assert e.text == "dT_A1_A1_A1_dt = m*(3*M_A1_A1*n_A1 - 2*n_A1**3)"
    assert e.code[-1] == "lhs, rhs = lhs.xreplace(rules), rhs.xreplace(rules)"


def test_validated_20_substitute_definitions():
    r = op(SUBSTITUTE, "n_A1*(r_A1 - (n_A1 + n_A2)/KA) - m*(n_A1 - n_B1)")
    assert r.text == "-m*(n_A1 - n_B1) + n_A1*(rmaxA - s*(-thA + x1)**2 - (n_A1 + n_A2)/KA)"
    assert r.code == ["rules = {r_A1: rmaxA - s*(-thA + x1)**2}", "result = expr.xreplace(rules)"]


def test_validated_21_buttons_only_when_useful():
    a = available(read("n_A1*m"), M)
    assert (a[ISSERLIS], a[SUBSTITUTE], a[RECOGNIZE]) == (False, False, False)
    a = available(read("T_A1_A1_A2 + r_A1"), M)
    assert (a[ISSERLIS], a[SUBSTITUTE], a[RECOGNIZE]) == (True, True, False)
    assert available(read("rmaxA*n_A1"), M)[RECOGNIZE]
    for name, text in ((ISSERLIS, "n_A1"), (SUBSTITUTE, "n_A1"), (RECOGNIZE, "n_A1*m")):
        assert not apply(name, read(text), M).ok


def recognize_line(key):
    rhs = dict(_closure_lines())[key]
    return op(RECOGNIZE, rhs), rhs


def test_validated_22_recognize_dn_A1():
    r, _ = recognize_line("dn_A1/dt")
    assert r.text == "m*n_B1 + n_A1*(-m + r_A1) - M_A1_A1/KA - M_A1_A2/KA"
    assert not r.notes


def test_validated_23_without_omega_keeps_birth_plus_death():
    """v0.2 rule, still true with a model that only defines the r (no omega)."""
    from sympy_tools.core.model import DEFAULT_MODEL_V04
    m4 = load_model(DEFAULT_MODEL_V04)
    rhs = dict(_closure_lines())["dM_A1_A1/dt"]
    r = apply(RECOGNIZE, read_expression(rhs, m4), m4)
    assert "M_A1_A1*(-2*m + 2*r_A1 + 1/KA)" in r.text
    assert "n_A1*(m + rmaxA + s*(-thA + x1)**2)" in r.text
    assert r.notes == ["Kept as it is (not a combination of r_A1, r_A2, r_B1, r_B2): "
                       "coefficient of n_A1."]


def test_validated_52_recognize_with_omega():
    """v0.5: birth + death in front of <N_A1> is written rmaxA + omega_A1."""
    r, _ = recognize_line("dM_A1_A1/dt")
    assert "M_A1_A1*(-2*m + 2*r_A1 + 1/KA)" in r.text
    assert "n_A1*(m + omega_A1 + rmaxA)" in r.text
    assert not r.notes


def test_validated_24_recognize_two_r_in_one_coefficient():
    r, _ = recognize_line("dM_A1_B1/dt")
    assert "M_A1_B1*(-2*m + r_A1 + r_B1)" in r.text


def test_validated_25_recognize_rmax_split_between_two_r():
    assert op(RECOGNIZE, "2*rmaxA - s*(x1 - thA)**2 - s*(x2 - thA)**2").text == "r_A1 + r_A2"


def test_validated_26_recognize_then_substitute_gives_back_the_input():
    for key, rhs in _closure_lines():
        rec = op(RECOGNIZE, rhs)
        back = op(SUBSTITUTE, rec.text) if available(read(rec.text), M)[SUBSTITUTE] else rec
        assert cmp(back.text, rhs).verdict == EQUAL, key


def test_definitions_errors():
    from sympy_tools.core.definitions import definitions
    bad = load_model(DEFAULT_MODEL.replace("r_A1 = rmaxA - omega_A1", "r_A1 = r_A2 + 1")
                     .replace("r_A2 = rmaxA - omega_A2", "r_A2 = r_A1 * 2"))
    with pytest.raises(ValueError, match="Circular definitions: r_A1, r_A2"):
        definitions(bad)
    bad2 = load_model(DEFAULT_MODEL.replace("r_A1 = rmaxA - omega_A1", "r_A1 = M_A1_MA1"))
    r = apply(SUBSTITUTE, read_expression("r_A1", bad2), bad2)
    assert not r.ok and "Definition r_A1 = M_A1_MA1" in r.error


# ------------------------------------------------------------------ v0.4 (VALIDATED 36-45, 17/11/2026)
from sympy_tools.core.operations import SYMMETRY, TAKE_MOMENTS  # noqa: E402
from sympy_tools.core.process import generate, process  # noqa: E402


def test_validated_36_default_model_process():
    p = process(M)
    assert len(p.events) == 12
    assert [s.name for s in p.symmetries] == ["phenotypes", "niches", "niches + phenotypes"]
    assert all(s.valid for s in p.symmetries)
    from latex_preview.core.model import parse_model
    assert parse_model(DEFAULT_MODEL).var_order == {"A1": 0, "A2": 1, "B1": 2, "B2": 3}


def test_validated_37_events_document():
    from sympy_tools.core.events_doc import events_document
    tex = events_document(M)
    assert tex.count(r"\checkmark") == 36 and r"\times$}" not in tex
    assert r"\textcolor{red}{K_{A}}" in tex or r"\textcolor{red}{K_A}" in tex
    assert M.lp.param_latex["KA"] in ("K_{A}", "K_A")        # colours do not leak into the model


def test_validated_38_symmetry_not_respecting_the_events():
    bad = load_model(DEFAULT_MODEL.replace(", KA<->KB", ""))
    niches = process(bad).symmetry("niches")
    assert niches.checked and sorted(niches.failures) == ["mort_A1", "mort_A2", "mort_B1", "mort_B2"]
    r = apply(SYMMETRY, read_expression("n_A1", bad), bad, "niches")
    assert r.ok and "not a symmetry of the events (4 events" in " ".join(r.notes)


def test_validated_39_rate_must_vanish():
    with pytest.raises(ModelError, match="mort_A1: the rate does not vanish when NA1 = 0"):
        load_model(DEFAULT_MODEL.replace("mort_A1 = (omega_A1 + (NA1 + NA2)/KA)*NA1 | NA1-1",
                                         "mort_A1 = omega_A1 | NA1-1"))


@pytest.mark.parametrize("bad, msg", [
    ("naissance_A1 = rmaxA*NA1 | NA1+1", None),
    ("naissance_A1 = rmaxA*NA1 | NX1+1", "should look like NA1+1"),
    ("naissance_A1 = rmaxA*M_A1_A1 | NA1+1", "only use variables"),
    ("naissance_A1 = rmaxA*NA1", "write 'rate | jump'"),
])
def test_event_declaration_errors(bad, msg):
    text = DEFAULT_MODEL.replace("naissance_A1 = rmaxA*NA1 | NA1+1", bad)
    if msg is None:
        load_model(text)
    else:
        with pytest.raises(ModelError, match=re.escape(msg)):
            load_model(text)


def test_symmetry_declaration_errors():
    with pytest.raises(ModelError, match="neither a variable code nor a parameter"):
        load_model(DEFAULT_MODEL.replace("x1<->x2", "x1<->y2"))
    with pytest.raises(ModelError, match="swaps a code with a parameter"):
        load_model(DEFAULT_MODEL.replace("x1<->x2", "A1<->x2"))


GEN = ("E(NA1*rmaxA*(2*NA1 + 1), naissance_A1) "
       "+ E(NA1*(1 - 2*NA1)*(omega_A1 + (NA1 + NA2)/KA), mort_A1) "
       "+ E(NA1*m*(1 - 2*NA1), migration_A1_B1) + E(NB1*m*(2*NA1 + 1), migration_B1_A1)")


def test_validated_40_generate():
    lhs, rhs = generate("M_A1_A1", M)
    assert lhs == "dM_A1_A1_dt" and rhs == GEN
    e = read_equation(lhs, rhs, M)
    assert e.ok and ("Events", ["migration_A1_B1", "migration_B1_A1", "mort_A1", "naissance_A1"]) \
        in categories(e.symbols, M)
    lat = latex(e.rhs.expr, M)
    assert lat.startswith(r"\underbrace{\left\langle N_{A}^{x_1} r_{\max,A}")        # birth first
    assert r"_{\text{migration A1}{\to}\text{B1}}" in lat


def test_validated_41_take_moments():
    lhs, rhs = generate("M_A1_A1", M)
    r = apply(TAKE_MOMENTS, read_equation(lhs, rhs, M), M)
    assert r.text == ("dM_A1_A1_dt = m*(-2*M_A1_A1 + n_A1) + m*(2*M_A1_B1 + n_B1) "
                      "+ omega_A1*(-2*M_A1_A1 + n_A1) + rmaxA*(2*M_A1_A1 + n_A1) "
                      "+ (M_A1_A1 + M_A1_A2 - 2*T_A1_A1_A1 - 2*T_A1_A1_A2)/KA")
    assert cmp(r.text.split(" = ")[1], EXACT_A1A1).verdict == EQUAL


def test_validated_42_generate_take_moments_isserlis_equals_moment_closure_all_14():
    for key, mc_rhs in _closure_lines():
        name = key[1:-3]                         # dM_A1_A1/dt -> M_A1_A1
        lhs, rhs = generate(name, M)
        t = apply(TAKE_MOMENTS, read_equation(lhs, rhs, M), M)
        closed = t.rhs
        if "T_" in t.text:
            closed = apply(ISSERLIS, read_equation(*t.text.split(" = "), M), M).rhs
        assert cmp(sp.sstr(closed), mc_rhs).verdict == EQUAL, key          # omega substituted


def test_validated_43_symmetry_of_a_generated_equation():
    lhs, rhs = generate("M_A1_A1", M)
    r = apply(SYMMETRY, read_equation(lhs, rhs, M), M, "phenotypes")
    direct = read_equation(*generate("M_A2_A2", M), M)
    assert r.lhs == direct.lhs.expr and r.rhs == direct.rhs.expr
    assert "naissance_A2" in r.text and not r.notes


def test_validated_44_invariant_equation():
    mc = dict(_closure_lines())["dM_A1_B1/dt"]
    r = apply(SYMMETRY, read(mc), M, "niches")
    assert sp.expand(r.expr - read(mc).expr) == 0
    assert r.notes == ["Invariant under niches: the equation does not change."]


def test_validated_45_combined_symmetry():
    lines = dict(_closure_lines())
    r = apply(SYMMETRY, read_equation("dn_A1_dt", lines["dn_A1/dt"], M), M, "niches + phenotypes")
    assert sp.sstr(r.lhs) == "dn_B2_dt"
    assert sp.cancel(r.rhs - read(lines["dn_B2/dt"]).expr) == 0
    assert r.code[0].startswith("rules = {") and r.code[-1] == "lhs, rhs = lhs.xreplace(rules), rhs.xreplace(rules)"


def test_e_reading_errors():
    for text, msg in (("E(n_A1, naissance_A1)", "not moments"), ("E(NA1, delta)", "event of the model"),
                      ("2*naissance_A1", "second argument of E")):
        r = read(text)
        assert not r.ok and msg in texts(r)


# ------------------------------------------------------------------ v0.5 (VALIDATED 46-53, 17/11/2026)
def test_validated_46_default_model_with_omega():
    from sympy_tools.core.definitions import definitions
    d = definitions(M)
    assert sp.sstr(d.rules[M.symbol("r_A1")]) == "-omega_A1 + rmaxA"           # r defined from omega
    assert sp.sstr(d.full[M.symbol("r_A1")]) == "rmaxA - s*(-thA + x1)**2"
    assert "omega_A1" in sp.sstr(process(M).events[1].rate)                    # death with omega
    syms = {s.name: s for s in process(M).symmetries}
    assert all(s.valid for s in syms.values())
    assert syms["phenotypes"].params["omega_A1"] == "omega_A2"
    assert syms["niches"].params["omega_A1"] == "omega_B1"
    from latex_preview.core.model import parse_model
    assert parse_model(DEFAULT_MODEL).param_latex["omega_A1"] == r"\omega_A^{1}"


def test_validated_49_compare_substitutes_definitions():
    lhs, rhs = generate("M_A1_A1", M)
    t = apply(TAKE_MOMENTS, read_equation(lhs, rhs, M), M)
    closed = apply(ISSERLIS, read_equation(*t.text.split(" = "), M), M)
    r = cmp(sp.sstr(closed.rhs), dict(_closure_lines())["dM_A1_A1/dt"])
    assert r.verdict == EQUAL and r.verdict_text == "Equal (proved, after substituting definitions)"
    assert r.code[1] == "lhs, rhs = lhs.xreplace(rules), rhs.xreplace(rules)   # definitions first"


def test_validated_50_recognize_after_take_moments():
    lhs, rhs = generate("M_A1_A1", M)
    t = apply(TAKE_MOMENTS, read_equation(lhs, rhs, M), M)
    r = apply(RECOGNIZE, read_equation(*t.text.split(" = "), M), M)
    assert "M_A1_A1*(-2*m + 2*r_A1 + 1/KA)" in r.text and "n_A1*(m + omega_A1 + rmaxA)" in r.text


def test_validated_51_symmetry_maps_omega():
    lhs, rhs = generate("M_A1_A1", M)
    r = apply(SYMMETRY, read_equation(lhs, rhs, M), M, "phenotypes")
    assert "omega_A2" in r.text and "omega_A1" not in r.text


def test_validated_53_substitute_all_the_way():
    assert op(SUBSTITUTE, "r_A1*n_A1").text == "n_A1*(rmaxA - s*(-thA + x1)**2)"


def test_old_default_v04_is_recognised():
    from sympy_tools.core.model import DEFAULT_MODEL_V04, is_default
    assert is_default(DEFAULT_MODEL_V04) and is_default(DEFAULT_MODEL) and not is_default("[variables]\nA1 = N")

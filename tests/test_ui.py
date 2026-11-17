"""Smoke test of the window, without a display (QT_QPA_PLATFORM=offscreen)."""
import os
import time

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
QtWidgets = pytest.importorskip("PySide6.QtWidgets")
from PySide6.QtCore import QStandardPaths  # noqa: E402

QStandardPaths.setTestModeEnabled(True)    # do not touch the user's preferences


@pytest.fixture(scope="module")
def win():
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    from sympy_tools.ui.main_window import MainWindow
    w = MainWindow()
    w.cb_render.setChecked(False)          # no TeX needed for this test
    w.show()
    yield w, app
    w.close()


def _wait(app, cond, timeout=60):
    end = time.time() + timeout
    while time.time() < end:
        app.processEvents()
        if cond():
            return True
        time.sleep(0.02)
    return False


def test_expression_expand_and_use_as_input(win):
    w, app = win
    w.rb_expr.setChecked(True)
    w.expr_edit.setPlainText("(n_A1 + n_A2)**2")
    w._read_input()
    assert w.read_label.text() == "(n_A1 + n_A2)**2"
    w.run("expand")
    assert _wait(app, lambda: w._shown.is_result)
    assert w._shown.python == "n_A1**2 + 2*n_A1*n_A2 + n_A2**2"
    assert w.code_view.toPlainText() == "result = sp.expand(expr)   # Expand"
    w.use_as_input()
    assert w.expr_edit.toPlainText() == "n_A1**2 + 2*n_A1*n_A2 + n_A2**2"


def test_symbol_list_and_errors(win):
    w, app = win
    w.rb_expr.setChecked(True)
    w.expr_edit.setPlainText("delta*M_A2_A1 + n_A1")
    w._read_input()
    items = [w.collect_combo.itemText(i) for i in range(w.collect_combo.count())]
    assert items[0] == "all moments"
    assert "Not in model" in items and any("M_A1_A2   ← M_A2_A1" in t for t in items)
    w.expr_edit.setPlainText("M_A1_MA1")
    w._read_input()
    assert "unknown code" in w.notes_label.text()
    assert not w.op_buttons["expand"].isEnabled()


def test_paste_equation_switches_mode(win):
    w, app = win
    w.rb_expr.setChecked(True)
    w.expr_edit.setPlainText("dM_A1_A1_dt = 2*M_A1_A1*rmaxA")
    w._on_expr_pasted()
    assert w.mode == "equation" and w.lhs_edit.toPlainText() == "dM_A1_A1_dt"


def test_compare(win):
    w, app = win
    w.rb_eq.setChecked(True)
    w.lhs_edit.setPlainText("(M_A1_A1 + M_A1_A2)/KA")
    w.rhs_edit.setPlainText("M_A1_A1/KA + M_A1_A2/KA")
    w._read_input()
    w._shown.is_result = False
    w.run("compare")
    assert _wait(app, lambda: w._shown.is_result)
    assert w._shown.verdict == "equal"


def test_v02_buttons_and_recognize(win):
    w, app = win
    w.rb_expr.setChecked(True)
    w.expr_edit.setPlainText("2*rmaxA - s*(x1 - thA)**2 - s*(x2 - thA)**2")
    w._read_input()
    assert w.op_buttons["recognize"].isEnabled()
    assert not w.op_buttons["isserlis"].isEnabled() and not w.op_buttons["substitute"].isEnabled()
    w._shown.is_result = False
    w.run("recognize")
    assert _wait(app, lambda: w._shown.is_result)
    assert w._shown.python == "r_A1 + r_A2"
    w.use_as_input()
    assert w.op_buttons["substitute"].isEnabled()


def test_visual_identity(win):
    w, app = win
    assert w.centralWidget().objectName() == "central"
    assert w.findChild(QtWidgets.QWidget, "band").height() == 5
    assert w.code_view.objectName() == "codeView"


# ------------------------------------------------------------------ v0.3: chains (VALIDATED 27-35, 17/11/2026)
def _run(w, app, op, var=None):
    n = len(w._chain)
    compare = op == "compare"
    if var is not None:
        w.collect_combo.setCurrentIndex(w.collect_combo.findData(var))
    w._compare = None if not compare else w._compare
    w.run(op)
    assert _wait(app, lambda: (w._compare is not None) if compare else len(w._chain) == n + 1)


def _combo(w):
    return [w.collect_combo.itemData(i) for i in range(w.collect_combo.count())
            if w.collect_combo.itemData(i)]


SRC = "m*n_A1 + T_A1_A1_A2/KA"


def _chain_27(w, app):
    w.rb_expr.setChecked(True)
    w.expr_edit.setPlainText(SRC)
    w._read_input()
    _run(w, app, "isserlis")
    assert w._shown.python == "m*n_A1 + (M_A1_A1*n_A2 + 2*M_A1_A2*n_A1 - 2*n_A1**2*n_A2)/KA"
    _run(w, app, "collect", "*all moments*")


def test_validated_27_chain_isserlis_then_collect(win):
    w, app = win
    _chain_27(w, app)
    assert w._shown.python == "m*n_A1 + M_A1_A1*n_A2/KA + 2*M_A1_A2*n_A1/KA - 2*n_A1**2*n_A2/KA"
    assert "Isserlis (order 3) → Collect by all moments" in w.result_title.text()
    assert w.code_view.toPlainText().splitlines() == [
        "rules = {T_A1_A1_A2: M_A1_A1*n_A2 + 2*M_A1_A2*n_A1 - 2*n_A1**2*n_A2}   # Isserlis (order 3)",
        "result = expr.xreplace(rules)",
        "result = sp.collect(sp.expand(result), [n_A1**2*n_A2, M_A1_A2*n_A1, M_A1_A1*n_A2, n_A1])"
        "   # Collect by all moments"]


def test_validated_28_29_input_kept_symbols_from_result(win):
    w, app = win
    _chain_27(w, app)
    assert w.expr_edit.toPlainText() == SRC                       # 28
    assert w.read_label.text() == "m*n_A1 + T_A1_A1_A2/KA"
    names = _combo(w)                                             # 29
    assert {"n_A1", "n_A2", "M_A1_A1", "M_A1_A2", "m", "KA"} <= set(names)
    assert "T_A1_A1_A2" not in names
    assert not w.op_buttons["isserlis"].isEnabled()


def test_validated_30_31_back_to_input_and_edit(win):
    w, app = win
    _chain_27(w, app)
    w.back_to_input()                                             # 30
    assert w._chain == [] and "input as read" in w.result_title.text()
    assert "T_A1_A1_A2" in _combo(w) and w.op_buttons["isserlis"].isEnabled()
    assert not w.back_button.isEnabled()
    _chain_27(w, app)
    w.expr_edit.setPlainText(SRC + " + n_B1")                     # 31
    w._read_input()
    assert w._chain == [] and "T_A1_A1_A2" in _combo(w)


EXACT = ("m*(-2*M_A1_A1 + 2*M_A1_B1 + n_A1 + n_B1) + rmaxA*(2*M_A1_A1 + n_A1)"
         " + s*(x1 - thA)**2*(n_A1 - 2*M_A1_A1)"
         " + (M_A1_A1 + M_A1_A2 - 2*T_A1_A1_A1 - 2*T_A1_A1_A2)/KA")


def test_validated_32_33_compare_in_a_chain(win):
    import pathlib
    from sympy_tools.core.reading import split_equation
    data = pathlib.Path(__file__).parent / "data" / "moment_closure_L2.txt"
    mc = dict(split_equation(l) for l in data.read_text().splitlines())["dM_A1_A1/dt"]
    w, app = win
    w.rb_eq.setChecked(True)
    w.lhs_edit.setPlainText(EXACT)
    w.rhs_edit.setPlainText(mc)
    w._read_input()
    _run(w, app, "compare")
    assert w._shown.verdict == "different" and w._chain == []      # 32: with T
    _run(w, app, "isserlis")
    _run(w, app, "compare")
    assert w._shown.verdict == "equal"                             # 32: after Isserlis
    assert "Isserlis (order 3) → Compare: lhs − rhs" in w.result_title.text()
    closed = w._current["lhs"]
    _run(w, app, "simplify")                                       # 33
    assert w._compare is None and len(w._chain) == 2
    assert "Isserlis (order 3) → Simplify" in w.result_title.text()
    assert "T_A1" not in closed and w.code_view.toPlainText().splitlines()[-1] == "rhs = sp.simplify(rhs)"


def test_validated_34_35_use_as_input_and_mode_change(win):
    w, app = win
    _chain_27(w, app)
    result = w._shown.python
    w.use_as_input()                                               # 34
    assert w.expr_edit.toPlainText() == result and w._chain == []
    _chain_27(w, app)
    w.rb_eq.setChecked(True)                                       # 35
    assert w._chain == [] and w._current is None


# ------------------------------------------------------------------ v0.4: process, symmetries
def test_v04_generate_take_moments_isserlis_symmetry(win):
    w, app = win
    w.moment_field.setText("M_A1_A1")
    w.generate()
    assert w.mode == "equation" and w.lhs_edit.toPlainText() == "dM_A1_A1_dt"
    assert w.rhs_edit.toPlainText().startswith("E(NA1*rmaxA*(2*NA1 + 1), naissance_A1)")
    assert w.op_buttons["moments"].isEnabled() and not w.op_buttons["isserlis"].isEnabled()
    assert [w.symmetry_combo.itemData(i) for i in range(w.symmetry_combo.count())] == \
        ["phenotypes", "niches", "niches + phenotypes"]
    _run(w, app, "moments")
    assert "T_A1_A1_A1" in w._shown.python and w.op_buttons["isserlis"].isEnabled()
    _run(w, app, "isserlis")
    w.symmetry_combo.setCurrentIndex(w.symmetry_combo.findData("phenotypes"))
    _run(w, app, "symmetry")
    assert w._current["lhs"] == "dM_A2_A2_dt"
    assert "Take moments → Isserlis (order 3) → Symmetry phenotypes" in w.result_title.text()


def test_v04_events_dialog_and_generate_error(win, monkeypatch):
    w, app = win
    from sympy_tools.ui.events_dialog import EventsDialog
    d = EventsDialog(w.model, w)
    assert d.tex.count(r"\checkmark") == 36
    shown = []
    monkeypatch.setattr(QtWidgets.QMessageBox, "warning", lambda *a: shown.append(a[2]))
    w.moment_field.setText("M_A1_XX")
    w.generate()
    assert shown and "unknown code" in shown[0]

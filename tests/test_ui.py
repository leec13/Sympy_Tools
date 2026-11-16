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
    assert w.code_view.toPlainText() == "result = sp.expand(expr)"
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

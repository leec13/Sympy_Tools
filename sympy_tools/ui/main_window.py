"""Main window: input, reading, operations, SymPy code, result, LaTeX."""

from __future__ import annotations

import atexit
import html
import os
import threading
from dataclasses import dataclass

from latex_preview.core.compiler import TexCompiler, find_engine
from latex_preview.core.pipeline import render_snippet
from latex_preview.ui.preview import PreviewArea, cropped_to_qimage
from latex_preview.ui.worker import Runner
from PySide6.QtCore import QByteArray, QObject, Qt, QTimer, Signal
from PySide6.QtGui import (QAction, QFont, QFontDatabase, QKeySequence, QStandardItem,
                           QStandardItemModel, QTextCursor)
from PySide6.QtWidgets import (QApplication, QButtonGroup, QCheckBox, QComboBox, QFileDialog,
                               QFormLayout, QHBoxLayout, QLabel, QLineEdit, QMainWindow, QMenu,
                               QMessageBox,
                               QPlainTextEdit, QPushButton, QRadioButton, QToolButton, QVBoxLayout, QWidget)

from ..core import jobs
from ..core.jobs import EQUATION, EXPRESSION
from ..core.model import ModelError, load_model
from ..core.operations import (ALL_MOMENTS, COLLECT, COMPARE, EXPAND, FACTOR,
                               ISSERLIS, OPERATIONS, RECOGNIZE, SIMPLIFY, SUBSTITUTE, SYMMETRY,
                               TAKE_MOMENTS, available, chain_code)
from ..core.process import generate as generate_equation
from ..core.process import process as model_process
from ..core.output import overleaf, reading_latex
from ..core.reading import ERROR, WARNING, categories, read_equation, read_expression, split_equation
from ..settings import Settings
from . import theme

_COLORS = theme.NOTE_COLORS
_VERDICT_COLORS = theme.VERDICT_COLORS


def _mono(size: int = 12) -> QFont:
    f = QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont)
    f.setPointSize(size)
    return f


class InputEdit(QPlainTextEdit):
    """Plain-text input; tells the window when something was pasted."""

    pasted = Signal()

    def __init__(self, lines: int, parent=None) -> None:
        super().__init__(parent)
        self.setFont(_mono(13))
        self.setTabChangesFocus(True)
        h = self.fontMetrics().lineSpacing() * lines + 14
        self.setFixedHeight(h)

    def insertFromMimeData(self, source) -> None:  # noqa: N802 - Qt API
        super().insertFromMimeData(source)
        self.pasted.emit()


class _Bridge(QObject):
    rendered = Signal(object)   # (latex, outcome)


@dataclass
class _Shown:
    """What the Result area shows (the input as read, or an operation result)."""

    python: str = ""
    latex: str = ""
    code: str = ""
    title: str = "Result"
    verdict: str = ""
    verdict_text: str = ""
    notes: tuple = ()
    lhs: str | None = None
    rhs: str | None = None
    is_result: bool = False


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Sympy Tools")
        self.s = Settings()
        self._model_text = self.s.get("model_text")
        self._model_path = self.s.get("model_path")
        self._model_edited = False
        try:
            self.model = load_model(self._model_text)
        except ModelError:
            self._model_text, self._model_path = "", ""
            self.model = load_model("")
        self._reading = None
        # chain of operations: each one applies to the result shown (v0.3)
        self._chain: list[tuple[str, list[str]]] = []   # (label, code lines)
        self._current: dict | None = None               # last result (python, lhs, rhs, latex, notes)
        self._current_reading = None                     # that result, read again (symbols, buttons)
        self._compare: dict | None = None                # Compare shown (does not change _current)
        self._version = 0                                # changes whenever the chain is reset
        self._pending: tuple | None = None
        self._shown = _Shown()
        self._request = 0
        self._request_input = None
        self._rendered_latex = None
        self._cropped = None
        self._copy_image_pending = False
        self._render_busy = False
        self._render_pending = None
        self.compiler = TexCompiler()
        atexit.register(self.compiler.cleanup)
        self._bridge = _Bridge()
        self._bridge.rendered.connect(self._on_rendered)
        self.runner = Runner(warm_up=jobs.warm_up, parent=self)
        self.runner.finished.connect(self._on_operation_done)

        self._read_timer = QTimer(self)
        self._read_timer.setSingleShot(True)
        self._read_timer.setInterval(250)
        self._read_timer.timeout.connect(self._read_input)
        self._render_timer = QTimer(self)
        self._render_timer.setSingleShot(True)
        self._render_timer.setInterval(300)
        self._render_timer.timeout.connect(self._render)
        self._build()
        self._load_state()
        self._read_input()

    # ================================================================ layout
    def _build(self) -> None:
        central = QWidget(objectName="central")
        self.setCentralWidget(central)
        self.setStyleSheet(theme.window_stylesheet())
        outer = QVBoxLayout(central)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        band = QWidget(objectName="band")
        band.setFixedHeight(5)
        outer.addWidget(band)
        body = QWidget()
        outer.addWidget(body, 1)
        root = QVBoxLayout(body)

        # --- model
        row = QHBoxLayout()
        row.addWidget(QLabel(theme.title("Model:")))
        self.model_label = QLabel()
        self.model_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        row.addWidget(self.model_label, 1)
        for label, slot in (("Events…", self.show_events),
                            ("Edit model…", self.edit_model), ("Load model…", self.load_model_file),
                            ("Save model as…", self.save_model_file)):
            b = QPushButton(label)
            b.clicked.connect(slot)
            row.addWidget(b)
        root.addLayout(row)

        # --- mode + input
        row = QHBoxLayout()
        self.rb_expr = QRadioButton("Expression")
        self.rb_eq = QRadioButton("Equation")
        self.mode_group = QButtonGroup(self)
        self.mode_group.addButton(self.rb_expr)
        self.mode_group.addButton(self.rb_eq)
        row.addWidget(self.rb_expr)
        row.addWidget(self.rb_eq)
        row.addStretch(1)
        root.addLayout(row)

        self.expr_edit = InputEdit(4)
        self.expr_edit.setPlaceholderText("Python-like expression, e.g.  2*M_A1_A1 + M_A1_A2/KA")
        root.addWidget(self.expr_edit)
        eq = self.eq_widget = QWidget()
        form = QFormLayout(eq)
        form.setContentsMargins(0, 0, 0, 0)
        self.lhs_edit = InputEdit(2)
        self.lhs_edit.setPlaceholderText("left-hand side, e.g.  dM_A1_A1_dt")
        self.rhs_edit = InputEdit(4)
        self.rhs_edit.setPlaceholderText("right-hand side")
        form.addRow("lhs", self.lhs_edit)
        form.addRow("rhs", self.rhs_edit)
        root.addWidget(eq)

        # --- reading
        row = QHBoxLayout()
        lab = QLabel(theme.title("Read as:"))
        lab.setAlignment(Qt.AlignmentFlag.AlignTop)
        row.addWidget(lab)
        col = QVBoxLayout()
        self.read_label = QLabel()
        self.read_label.setFont(_mono(12))
        self.read_label.setWordWrap(True)
        self.read_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        col.addWidget(self.read_label)
        self.notes_label = QLabel()
        self.notes_label.setWordWrap(True)
        self.notes_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        col.addWidget(self.notes_label)
        row.addLayout(col, 1)
        self.split_button = QPushButton("Split into lhs / rhs")
        self.split_button.clicked.connect(self.split_expression)
        self.split_button.setVisible(False)
        row.addWidget(self.split_button, 0, Qt.AlignmentFlag.AlignTop)
        root.addLayout(row)

        # --- operations
        row = QHBoxLayout()
        self.op_buttons = {}
        keys = {SIMPLIFY: "Ctrl+1", FACTOR: "Ctrl+2", EXPAND: "Ctrl+3", COLLECT: "Ctrl+4",
                COMPARE: "Ctrl+5"}
        tips = {SIMPLIFY: "sp.simplify", FACTOR: "sp.factor", EXPAND: "sp.expand",
                COLLECT: "sp.collect(sp.expand(…), variable)",
                COMPARE: "Is lhs - rhs identically 0? (sp.cancel, or sp.simplify)"}
        for op in (SIMPLIFY, FACTOR, EXPAND, COLLECT):
            b = QPushButton(OPERATIONS[op])
            b.setShortcut(QKeySequence(keys[op]))
            b.setToolTip(f"{tips[op]}   ({QKeySequence(keys[op]).toString(QKeySequence.SequenceFormat.NativeText)})")
            b.clicked.connect(lambda _=False, op=op: self.run(op))
            self.op_buttons[op] = b
            row.addWidget(b)
        self.collect_combo = QComboBox()
        self.collect_combo.setMinimumContentsLength(16)
        self.collect_combo.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
        self.collect_combo.setToolTip("Variable for Collect by; also the list of all symbols read, "
                                      "to check the input")
        self.collect_combo.setModel(QStandardItemModel(self.collect_combo))
        self.collect_combo.activated.connect(
            lambda _: self.s.set("collect_var", self.collect_combo.currentData() or ""))
        row.addWidget(self.collect_combo)
        b = QPushButton(OPERATIONS[COMPARE])
        b.setShortcut(QKeySequence(keys[COMPARE]))
        b.setToolTip(f"{tips[COMPARE]}   ({QKeySequence(keys[COMPARE]).toString(QKeySequence.SequenceFormat.NativeText)})")
        b.clicked.connect(lambda: self.run(COMPARE))
        self.op_buttons[COMPARE] = b
        row.addWidget(b)
        self.stop_button = QPushButton("Stop")
        self.stop_button.setVisible(False)
        self.stop_button.clicked.connect(self.stop)
        row.addWidget(self.stop_button)
        row.addStretch(1)
        root.addLayout(row)

        # --- process: generate from the events, take moments, symmetries
        row = QHBoxLayout()
        row.addWidget(QLabel("Process:"))
        self.moment_field = QLineEdit()
        self.moment_field.setPlaceholderText("M_A1_A1")
        self.moment_field.setText(self.s.get("generate_moment"))
        self.moment_field.setFixedWidth(130)
        self.moment_field.setToolTip("Moment whose equation is generated from the events (n_A1, M_A1_A2, T_…)")
        self.moment_field.returnPressed.connect(self.generate)
        row.addWidget(self.moment_field)
        self.generate_button = QPushButton("Generate d/dt")
        self.generate_button.setToolTip("Write d<moment>/dt event by event, as the input (Equation mode)")
        self.generate_button.clicked.connect(self.generate)
        row.addWidget(self.generate_button)
        b = QPushButton(OPERATIONS[TAKE_MOMENTS])
        b.setShortcut(QKeySequence("Ctrl+9"))
        b.setToolTip("E(…): expand, and each product of N becomes its moment (⟨NA1·NA1⟩ → M_A1_A1)   "
                     f"({QKeySequence('Ctrl+9').toString(QKeySequence.SequenceFormat.NativeText)})")
        b.clicked.connect(lambda: self.run(TAKE_MOMENTS))
        self.op_buttons[TAKE_MOMENTS] = b
        row.addWidget(b)
        row.addSpacing(16)
        row.addWidget(QLabel("Symmetry:"))
        self.symmetry_combo = QComboBox()
        self.symmetry_combo.setMinimumContentsLength(18)
        self.symmetry_combo.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
        row.addWidget(self.symmetry_combo)
        b = QPushButton("Apply")
        b.setShortcut(QKeySequence("Ctrl+0"))
        b.setToolTip("Apply the symmetry (moments, parameters, r_… and events swapped)   "
                     f"({QKeySequence('Ctrl+0').toString(QKeySequence.SequenceFormat.NativeText)})")
        b.clicked.connect(lambda: self.run(SYMMETRY))
        self.op_buttons[SYMMETRY] = b
        row.addWidget(b)
        row.addStretch(1)
        root.addLayout(row)

        # --- moments and definitions
        row = QHBoxLayout()
        more = {ISSERLIS: ("Ctrl+6", "Third-order moments T_… replaced by Isserlis / Wick: "
                                     "<ab><c> + <ac><b> + <bc><a> - 2<a><b><c>"),
                SUBSTITUTE: ("Ctrl+7", "r_A1… replaced by their formula ([definitions] of the model)"),
                RECOGNIZE: ("Ctrl+8", "Formulas rewritten with r_A1…, coefficient by coefficient, "
                                      "only where exact and unambiguous")}
        row.addWidget(QLabel("Moments:"))
        for op in (ISSERLIS, SUBSTITUTE, RECOGNIZE):
            if op == SUBSTITUTE:
                row.addSpacing(16)
                row.addWidget(QLabel("Definitions:"))
            key, tip = more[op]
            b = QPushButton(OPERATIONS[op])
            b.setShortcut(QKeySequence(key))
            b.setToolTip(f"{tip}   ({QKeySequence(key).toString(QKeySequence.SequenceFormat.NativeText)})")
            b.clicked.connect(lambda _=False, op=op: self.run(op))
            self.op_buttons[op] = b
            row.addWidget(b)
        row.addStretch(1)
        root.addLayout(row)

        # --- lower part: code, result, LaTeX
        lower = QWidget()
        lay = QVBoxLayout(lower)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.addWidget(QLabel(theme.title("SymPy code")))
        self.code_view = QPlainTextEdit(readOnly=True)
        self.code_view.setFont(_mono(12))
        self.code_view.setFixedHeight(self.code_view.fontMetrics().lineSpacing() * 3 + 14)
        self.code_view.setObjectName("codeView")
        lay.addWidget(self.code_view)

        row = QHBoxLayout()
        self.result_title = QLabel(theme.title("Result"))
        row.addWidget(self.result_title)
        self.verdict_label = QLabel()
        row.addWidget(self.verdict_label, 1)
        self.copy_button = QToolButton()
        self.copy_button.setText("Copy")
        self.copy_button.setPopupMode(QToolButton.ToolButtonPopupMode.MenuButtonPopup)
        self.copy_button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextOnly)
        menu = QMenu(self.copy_button)
        self.a_copy_py = self._action(menu, "Copy Python", self.copy_python, "Ctrl+Shift+C")
        self._action(menu, "Copy LaTeX (Keynote)", self.copy_latex, "Ctrl+Shift+K")
        self._action(menu, "Copy LaTeX for Overleaf", self.copy_overleaf, "Ctrl+Shift+L")
        self._action(menu, "Copy image", self.copy_image, "Ctrl+Shift+I")
        self.copy_button.setMenu(menu)
        self.copy_button.setDefaultAction(self.a_copy_py)
        self.copy_button.setText("Copy")
        self.copy_button.setToolTip("Copy the result (arrow: other formats)")
        row.addWidget(self.copy_button)
        self.use_button = QPushButton("↑ Use as input")
        self.use_button.setToolTip("The result becomes the input, to chain operations")
        self.use_button.clicked.connect(self.use_as_input)
        row.addWidget(self.use_button)
        self.back_button = QPushButton("↺ Back to input")
        self.back_button.setToolTip("Forget the chain of operations and start again from the input")
        self.back_button.clicked.connect(self.back_to_input)
        row.addWidget(self.back_button)
        lay.addLayout(row)

        self.result_view = QPlainTextEdit(readOnly=True)
        self.result_view.setFont(_mono(13))
        self.result_view.setMinimumHeight(self.result_view.fontMetrics().lineSpacing() * 3 + 14)
        lay.addWidget(self.result_view, 1)
        self.result_notes = QLabel()
        self.result_notes.setWordWrap(True)
        self.result_notes.setStyleSheet(f"color:{_COLORS['info']};")
        lay.addWidget(self.result_notes)

        row = QHBoxLayout()
        row.addWidget(QLabel("Show LaTeX:"))
        self.cb_code = QCheckBox("code")
        self.cb_render = QCheckBox("rendered")
        self.cb_code.toggled.connect(self._on_show_toggled)
        self.cb_render.toggled.connect(self._on_show_toggled)
        row.addWidget(self.cb_code)
        row.addWidget(self.cb_render)
        row.addStretch(1)
        lay.addLayout(row)
        self.latex_view = QPlainTextEdit(readOnly=True)
        self.latex_view.setFont(_mono(12))
        self.latex_view.setMaximumHeight(self.latex_view.fontMetrics().lineSpacing() * 5 + 14)
        lay.addWidget(self.latex_view)
        self.preview = PreviewArea(zoom=self.s.get("zoom"))
        self.preview.setMinimumHeight(120)
        self.preview.show_placeholder("Nothing to show yet.")
        self.preview.widthChanged.connect(lambda: self._render_timer.start())
        self.preview.zoomChanged.connect(self._on_zoom)
        lay.addWidget(self.preview, 2)
        root.addWidget(lower, 1)

        # --- signals
        self.rb_expr.toggled.connect(self._on_mode_toggled)
        for e in (self.expr_edit, self.lhs_edit, self.rhs_edit):
            e.textChanged.connect(self._on_input_changed)
        self.expr_edit.pasted.connect(self._on_expr_pasted)
        self.statusBar()
        self.resize(980, 860)

    def _action(self, menu: QMenu, text: str, slot, key: str) -> QAction:
        a = QAction(text, self)
        a.setShortcut(QKeySequence(key))
        a.triggered.connect(slot)
        menu.addAction(a)
        self.addAction(a)   # shortcut active everywhere in the window
        return a

    # ================================================================ state
    def _load_state(self) -> None:
        self.expr_edit.setPlainText(self.s.get("expr_text"))
        self.lhs_edit.setPlainText(self.s.get("lhs_text"))
        self.rhs_edit.setPlainText(self.s.get("rhs_text"))
        eq = self.s.get("mode") == EQUATION
        (self.rb_eq if eq else self.rb_expr).setChecked(True)
        self._show_mode()
        self.cb_code.setChecked(self.s.get("show_latex_code"))
        self.cb_render.setChecked(self.s.get("show_latex_rendered"))
        self._on_show_toggled()
        geo = self.s.get("geometry")
        if geo:
            self.restoreGeometry(QByteArray(geo))
        self._update_model_label()

    def closeEvent(self, event) -> None:  # noqa: N802 - Qt API
        self.s.set("expr_text", self.expr_edit.toPlainText())
        self.s.set("lhs_text", self.lhs_edit.toPlainText())
        self.s.set("rhs_text", self.rhs_edit.toPlainText())
        self.s.set("mode", self.mode)
        self.s.set("geometry", bytes(self.saveGeometry()))
        self.runner.shutdown()
        self.compiler.cleanup()
        super().closeEvent(event)

    @property
    def mode(self) -> str:
        return EQUATION if self.rb_eq.isChecked() else EXPRESSION

    def _inputs(self) -> tuple:
        return (self.mode, self.expr_edit.toPlainText(), self.lhs_edit.toPlainText(),
                self.rhs_edit.toPlainText(), self._model_text)

    # ================================================================ model
    def _fill_symmetry_combo(self) -> None:
        previous = self.symmetry_combo.currentData()
        self.symmetry_combo.clear()
        try:
            syms = model_process(self.model).symmetries
        except Exception:  # noqa: BLE001 - the model was checked when loaded
            syms = []
        for sym in syms:
            text = sym.name if (sym.valid or not sym.checked) else f"{sym.name}  ✗"
            self.symmetry_combo.addItem(text, sym.name)
        if not syms:
            self.symmetry_combo.addItem("(none in the model)", None)
        k = self.symmetry_combo.findData(previous)
        if k >= 0:
            self.symmetry_combo.setCurrentIndex(k)

    def _update_model_label(self) -> None:
        self._fill_symmetry_combo()
        name = os.path.basename(self._model_path) if self._model_path else "default"
        if self._model_edited:
            name += " (edited)"
        self.model_label.setText(f"{html.escape(name)} — {html.escape(self.model.summary())}")

    def _set_model(self, text: str, path: str, edited: bool) -> bool:
        try:
            model = load_model(text)
        except ModelError as exc:
            QMessageBox.warning(self, "Invalid model", str(exc))
            return False
        self.model, self._model_text, self._model_path = model, text, path
        self._model_edited = edited
        self.s.set("model_text", text)
        self.s.set("model_path", path)
        self._update_model_label()
        self._read_input()
        return True

    def edit_model(self) -> None:
        from .model_dialog import ModelDialog
        dlg = ModelDialog(self._model_text, self)
        if dlg.exec():
            if dlg.text != self._model_text:
                self._set_model(dlg.text, self._model_path, edited=True)

    def load_model_file(self) -> None:
        start = os.path.dirname(self._model_path) if self._model_path else (
            self.s.get("last_dir") or os.path.expanduser("~"))
        path, _ = QFileDialog.getOpenFileName(self, "Load model", start, "Model (*.ini);;All files (*)")
        if not path:
            return
        try:
            with open(path, encoding="utf-8") as f:
                text = f.read()
        except OSError as exc:
            QMessageBox.warning(self, "Load model", str(exc))
            return
        self.s.set("last_dir", os.path.dirname(path))
        if self._set_model(text, path, edited=False):
            self.statusBar().showMessage(f"Model loaded: {path}", 5000)

    def save_model_file(self) -> None:
        from ..core.model import DEFAULT_MODEL
        start = self._model_path or os.path.join(self.s.get("last_dir") or os.path.expanduser("~"),
                                                 "model.ini")
        path, _ = QFileDialog.getSaveFileName(self, "Save model as", start, "Model (*.ini)")
        if not path:
            return
        if not path.lower().endswith(".ini"):
            path += ".ini"
        try:
            with open(path, "w", encoding="utf-8") as f:
                f.write(self._model_text or DEFAULT_MODEL)
        except OSError as exc:
            QMessageBox.warning(self, "Save model", str(exc))
            return
        self.s.set("last_dir", os.path.dirname(path))
        self._model_path, self._model_edited = path, False
        self.s.set("model_path", path)
        self._update_model_label()
        self.statusBar().showMessage(f"Model saved: {path}", 5000)

    # ================================================================ input
    def _show_mode(self) -> None:
        eq = self.mode == EQUATION
        self.eq_widget.setVisible(eq)
        self.expr_edit.setVisible(not eq)

    def _on_mode_toggled(self) -> None:
        self._show_mode()
        self.s.set("mode", self.mode)
        self._read_input()

    def _on_input_changed(self) -> None:
        self._read_timer.start()

    def _on_expr_pasted(self) -> None:
        parts = split_equation(self.expr_edit.toPlainText())
        if parts:
            self._split(parts, "Pasted text has '=': switched to Equation mode.")

    def split_expression(self) -> None:
        parts = split_equation(self.expr_edit.toPlainText())
        if parts:
            self._split(parts, "Split into lhs and rhs.")

    def _split(self, parts, message: str) -> None:
        self.lhs_edit.setPlainText(parts[0])
        self.rhs_edit.setPlainText(parts[1])
        self.rb_eq.setChecked(True)
        self.statusBar().showMessage(message, 5000)

    def _reset_chain(self) -> None:
        self._chain, self._current, self._current_reading, self._compare = [], None, None, None
        self._version += 1

    def _active(self):
        """What the next operation applies to: the current result, or else the input."""
        return self._current_reading if self._current is not None else self._reading

    def back_to_input(self) -> None:
        self._reset_chain()
        self._fill_collect_combo()
        self._update_buttons()
        self._show_reading()
        self.statusBar().showMessage("Back to the input.", 3000)

    def _read_input(self) -> None:
        self._read_timer.stop()
        self._reset_chain()
        if self.mode == EQUATION:
            r = read_equation(self.lhs_edit.toPlainText(), self.rhs_edit.toPlainText(), self.model)
            missing = [s for s, x in (("lhs", r.lhs), ("rhs", r.rhs)) if x.empty]
        else:
            r = read_expression(self.expr_edit.toPlainText(), self.model)
            missing = ["expression"] if r.empty else []
        self._reading = r
        self.split_button.setVisible(self.mode == EXPRESSION and
                                     split_equation(self.expr_edit.toPlainText()) is not None)

        if missing and r.empty:
            self.read_label.setText("<span style='color:#888'>(empty)</span>")
        elif r.ok:
            self.read_label.setText(html.escape(r.text))
        else:
            self.read_label.setText("<span style='color:#888'>—</span>")
        rank = {ERROR: 0, WARNING: 1}
        notes = sorted(r.notes, key=lambda n: rank.get(n.level, 2))
        lines = [f"<span style='color:{_COLORS[n.level]}'>{html.escape(str(n))}</span>" for n in notes]
        if missing and not r.empty:
            lines.append(f"<span style='color:{_COLORS['error']}'>✗ {', '.join(missing)} empty</span>")
        self.notes_label.setText("<br>".join(lines))
        self.notes_label.setVisible(bool(lines))
        self._fill_collect_combo()
        self._update_buttons()
        self._show_reading()

    def _fill_collect_combo(self) -> None:
        previous = self.collect_combo.currentData() or self.s.get("collect_var")
        model: QStandardItemModel = self.collect_combo.model()
        model.clear()
        r = self._active()
        if r is None or not r.ok:
            item = QStandardItem("(no symbols)")
            item.setEnabled(False)
            model.appendRow(item)
            return
        cats = categories(r.symbols, self.model)
        written = r.written
        select = None
        if any(label.startswith("Moments") for label, _ in cats):
            item = QStandardItem("all moments")
            item.setData(ALL_MOMENTS, Qt.ItemDataRole.UserRole)
            model.appendRow(item)
        for label, names in cats:
            head = QStandardItem(label)
            head.setEnabled(False)
            f = head.font()
            f.setBold(True)
            head.setFont(f)
            model.appendRow(head)
            for name in names:
                text = "    " + name
                if name in written:
                    text += f"   ← {written[name]}"
                if label == "Not in model":
                    text += "   (not in model)"
                item = QStandardItem(text)
                item.setData(name, Qt.ItemDataRole.UserRole)
                if label in ("Functions", "Events"):
                    item.setEnabled(False)
                model.appendRow(item)
        for row in range(model.rowCount()):
            it = model.item(row)
            if not it.isEnabled():
                continue
            if select is None:
                select = row            # default: first selectable entry
            if it.data(Qt.ItemDataRole.UserRole) == previous:
                select = row
                break
        if select is not None:
            self.collect_combo.setCurrentIndex(select)

    def _update_buttons(self) -> None:
        active = self._active()
        ok = active is not None and active.ok
        busy = self.runner.busy
        for op, b in self.op_buttons.items():
            b.setEnabled(ok and not busy and (op != COMPARE or self.mode == EQUATION))
        self.op_buttons[COLLECT].setEnabled(ok and not busy and self.collect_combo.currentData() is not None)
        self.op_buttons[COMPARE].setToolTip(
            "Is lhs - rhs identically 0?" if self.mode == EQUATION else "Compare needs Equation mode")
        useful = available(active, self.model)
        for op, can in useful.items():
            self.op_buttons[op].setEnabled(ok and not busy and can)
        self.stop_button.setVisible(busy)
        self.back_button.setEnabled(bool(self._chain) or self._compare is not None)
        self.use_button.setEnabled(bool(self._chain))

    # ================================================================ result
    def _show_reading(self) -> None:
        """No operation yet (or the input changed): the result area shows the input as read."""
        r = self._reading
        if r is None or not r.ok:
            self._show(_Shown(title="Result", code=""))
            return
        try:
            lat = reading_latex(r, self.model)
        except Exception:  # noqa: BLE001 - display only
            lat = ""
        self._show(_Shown(python=r.text, latex=lat, title="Result — input as read (no operation yet)",
                          code="# no operation yet: this is the input as read"))

    def _show(self, shown: _Shown) -> None:
        self._shown = shown
        self.result_title.setText(theme.title(html.escape(shown.title)))
        self.code_view.setPlainText(shown.code)
        QTimer.singleShot(0, self._fit_code_view)
        self.result_view.setPlainText(shown.python)
        if shown.verdict_text:
            color = _VERDICT_COLORS.get(shown.verdict, "#333333")
            self.verdict_label.setText(f"<b style='color:{color}'>{html.escape(shown.verdict_text)}</b>")
        else:
            self.verdict_label.setText("")
        self.result_notes.setText("<br>".join(html.escape(n) for n in shown.notes))
        self.result_notes.setVisible(bool(shown.notes))
        self.use_button.setEnabled(bool(self._chain))
        self.back_button.setEnabled(bool(self._chain) or self._compare is not None)
        has = bool(shown.python)
        self.copy_button.setEnabled(has)
        self.latex_view.setPlainText(shown.latex)
        self._render_timer.start(150)

    def generate(self) -> None:
        name = self.moment_field.text().strip() or "M_A1_A1"
        try:
            lhs, rhs = generate_equation(name, self.model)
        except (ValueError, ModelError) as exc:
            QMessageBox.warning(self, "Generate", str(exc))
            return
        self.s.set("generate_moment", name)
        self.lhs_edit.setPlainText(lhs)
        self.rhs_edit.setPlainText(rhs)
        self.rb_eq.setChecked(True)
        self._read_input()
        self.statusBar().showMessage(f"{lhs}: generated from the events (now the input).", 5000)

    def show_events(self) -> None:
        from .events_dialog import EventsDialog
        EventsDialog(self.model, self, self.s.get("last_dir")).exec()

    def _fit_code_view(self) -> None:
        """The SymPy code pane grows with the chain (3 to 7 lines), then scrolls."""
        v = self.code_view
        lines = max(3, min(7, round(v.document().size().height())))
        v.setFixedHeight(v.fontMetrics().lineSpacing() * lines + 14)
        v.moveCursor(QTextCursor.MoveOperation.End)
        v.ensureCursorVisible()

    def run(self, op: str) -> None:
        active = self._active()
        if active is None or not active.ok or self.runner.busy:
            return
        var = self.collect_combo.currentData() if op == COLLECT else ""
        if op == COLLECT and not var:
            self.statusBar().showMessage("Choose a variable for Collect by.", 4000)
            return
        if op == SYMMETRY:
            var = self.symmetry_combo.currentData() or ""
            if not var:
                self.statusBar().showMessage("The model declares no symmetry.", 4000)
                return
        mode, text, lhs, rhs, model_text = self._inputs()
        if self._current is not None:          # chain: start from the result shown
            if mode == EQUATION:
                lhs, rhs = self._current["lhs"], self._current["rhs"]
            else:
                text = self._current["python"]
        label = OPERATIONS[op]
        if op == COLLECT:
            label += " all moments" if var == ALL_MOMENTS else f" {var}"
        if op == SYMMETRY:
            label += f" {var}"
        self._pending = (op, label, self._version)
        self._request_input = self._inputs()
        self._request = self.runner.submit(jobs.run_operation, timeout_s=60.0, model_text=model_text,
                                           mode=mode, text=text, lhs=lhs, rhs=rhs, op=op, var=var or "")
        self.statusBar().showMessage(f"{OPERATIONS[op]}…")
        self._update_buttons()

    def stop(self) -> None:
        self.runner.restart()
        self._request = -1
        self.statusBar().showMessage("Stopped.", 4000)
        self._update_buttons()

    def _on_operation_done(self, rid: int, res: dict) -> None:
        self._update_buttons()
        if rid != self._request:
            return
        if self._request_input != self._inputs():
            self.statusBar().showMessage("The input changed during the computation: result discarded.", 5000)
            return
        if not res.get("ok"):
            self.statusBar().clearMessage()
            QMessageBox.warning(self, "Operation", res.get("error", "Unknown error"))
            return
        if self._pending is None or self._pending[2] != self._version:
            return
        op, label, _ = self._pending
        code = res["code"].splitlines()
        if op == COMPARE:
            self._compare = res
        else:
            self._chain.append((label, chain_code(code, label, first=not self._chain)))
            self._current = {"python": res["python"], "lhs": res.get("lhs"), "rhs": res.get("rhs"),
                             "latex": res["latex"], "notes": tuple(res.get("notes", ()))}
            self._compare = None
            if self.mode == EQUATION:
                self._current_reading = read_equation(res["lhs"], res["rhs"], self.model)
            else:
                self._current_reading = read_expression(res["python"], self.model)
            self._fill_collect_combo()
        self._show_current()
        self._update_buttons()
        self.statusBar().showMessage(f"{label}: done.", 3000)

    def _show_current(self) -> None:
        """Show the last result of the chain, or the last Compare."""
        labels = [lab for lab, _ in self._chain]
        code = [line for _, lines in self._chain for line in lines]
        if self._compare is not None:
            c = self._compare
            code += chain_code(c["code"].splitlines(), OPERATIONS[COMPARE], first=True)
            title = "Result — " + " → ".join(labels + ["Compare: lhs − rhs"])
            self._show(_Shown(python=c["python"], latex=c["latex"], code="\n".join(code), title=title,
                              verdict=c.get("verdict", ""), verdict_text=c.get("verdict_text", ""),
                              notes=tuple(c.get("notes", ())), is_result=True))
            return
        cur = self._current
        self._show(_Shown(python=cur["python"], latex=cur["latex"], code="\n".join(code),
                          title="Result — " + " → ".join(labels), notes=cur["notes"],
                          lhs=cur["lhs"], rhs=cur["rhs"], is_result=True))

    def use_as_input(self) -> None:
        cur = self._current
        if cur is None:
            return
        if cur["lhs"] is not None:
            self.lhs_edit.setPlainText(cur["lhs"])
            self.rhs_edit.setPlainText(cur["rhs"])
            self.rb_eq.setChecked(True)
        else:
            self.expr_edit.setPlainText(cur["python"])
            self.rb_expr.setChecked(True)
        self._read_input()
        self.statusBar().showMessage("Result moved to the input.", 3000)

    # ================================================================ copy
    def _copy_text(self, text: str, message: str) -> None:
        if not text:
            self.statusBar().showMessage("Nothing to copy.", 3000)
            return
        QApplication.clipboard().setText(text)
        self.statusBar().showMessage(message, 6000)

    def copy_python(self) -> None:
        self._copy_text(self._shown.python, "Python copied.")

    def copy_latex(self) -> None:
        self._copy_text(self._shown.latex, "LaTeX copied (plain equation, e.g. for Keynote).")

    def copy_overleaf(self) -> None:
        if not self._shown.latex:
            self.statusBar().showMessage("Nothing to copy.", 3000)
            return
        self._copy_text(overleaf(self._shown.latex),
                        "Copied for Overleaf. Add \\usepackage{breqn} to the preamble, after amsmath.")

    def copy_image(self) -> None:
        if not self._shown.latex:
            self.statusBar().showMessage("Nothing to copy.", 3000)
            return
        if self._cropped is not None and self._rendered_latex == self._shown.latex:
            self._put_image()
        else:
            self._copy_image_pending = True
            self._render(force=True)

    def _put_image(self) -> None:
        dpi = 300
        img = cropped_to_qimage(self._cropped, dpi / 72.0, transparent=False)
        dpm = round(dpi / 0.0254)
        img.setDotsPerMeterX(dpm)
        img.setDotsPerMeterY(dpm)
        QApplication.clipboard().setImage(img)
        self.statusBar().showMessage(f"Image copied ({img.width()}×{img.height()} px, {dpi} dpi).", 5000)

    # ================================================================ LaTeX
    def _on_show_toggled(self) -> None:
        self.s.set("show_latex_code", self.cb_code.isChecked())
        self.s.set("show_latex_rendered", self.cb_render.isChecked())
        self.latex_view.setVisible(self.cb_code.isChecked())
        self.preview.setVisible(self.cb_render.isChecked())
        if self.cb_render.isChecked():
            self._render_timer.start(0)

    def _on_zoom(self, z: float) -> None:
        self.s.set("zoom", z)
        self._render_timer.start()

    def _render(self, force: bool = False) -> None:
        lat = self._shown.latex
        if not (self.cb_render.isChecked() or force):
            return
        if not lat:
            self._cropped, self._rendered_latex = None, None
            self.preview.show_placeholder("Nothing to show yet.")
            return
        if find_engine("pdflatex") is None:
            self.preview.show_placeholder("pdflatex not found: install TeX Live / MacTeX.")
            return
        width = round(self.preview.available_width_pt() / 6.0) * 6.0
        job = (lat, width)
        if self._render_busy:
            self._render_pending = job
            return
        if not force and self._rendered_latex == lat and getattr(self, "_rendered_width", None) == width:
            return
        self._render_busy = True

        def work():
            out = render_snippet(self.compiler, lat, auto_break=True, line_width_pt=width, suggest=False)
            try:
                self._bridge.rendered.emit((lat, width, out))
            except RuntimeError:   # window closed
                pass

        threading.Thread(target=work, daemon=True).start()

    def _on_rendered(self, payload) -> None:
        lat, width, out = payload
        self._render_busy = False
        if lat == self._shown.latex:
            if out.ok and out.cropped is not None:
                self._cropped, self._rendered_latex, self._rendered_width = out.cropped, lat, width
                self.preview.set_document(out.cropped)
                if self._copy_image_pending:
                    self._copy_image_pending = False
                    self._put_image()
            else:
                self._cropped = None
                msg = out.result.errors[0].describe() if out.result.errors else "LaTeX error"
                self.preview.show_placeholder(f"LaTeX does not compile: {msg}")
                self._copy_image_pending = False
        pending, self._render_pending = self._render_pending, None
        if pending is not None and pending[0] == self._shown.latex:
            self._render()

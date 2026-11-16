"""Model editor (the .ini file shared with latex-preview)."""

from __future__ import annotations

from PySide6.QtGui import QFontDatabase
from PySide6.QtWidgets import (QDialog, QDialogButtonBox, QHBoxLayout, QLabel, QMessageBox,
                               QPlainTextEdit, QPushButton, QVBoxLayout)

from ..core.model import DEFAULT_MODEL, ModelError, load_model


class ModelDialog(QDialog):
    def __init__(self, text: str, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Edit model")
        self.resize(760, 640)
        lay = QVBoxLayout(self)
        intro = QLabel(
            "Variables, moments, parameters and assumptions. Same .ini format as latex-preview "
            "(French or English section names). Variables are written N{code} (NA1…), "
            "moments n_A1, M_A1_A2, T_… in the order of [variables].")
        intro.setWordWrap(True)
        lay.addWidget(intro)
        self.edit = QPlainTextEdit(text or DEFAULT_MODEL)
        font = QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont)
        font.setPointSize(12)
        self.edit.setFont(font)
        lay.addWidget(self.edit, 1)
        self.info = QLabel()
        self.info.setWordWrap(True)
        lay.addWidget(self.info)
        row = QHBoxLayout()
        reset = QPushButton("Reset to default")
        reset.clicked.connect(lambda: self.edit.setPlainText(DEFAULT_MODEL))
        row.addWidget(reset)
        row.addStretch(1)
        lay.addLayout(row)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok
                                   | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self._accept)
        buttons.rejected.connect(self.reject)
        lay.addWidget(buttons)
        self.edit.textChanged.connect(self._check)
        self._check()

    @property
    def text(self) -> str:
        return self.edit.toPlainText()

    def _check(self) -> bool:
        try:
            m = load_model(self.text)
        except ModelError as exc:
            self.info.setStyleSheet("color:#ff7b72;")
            self.info.setText(str(exc))
            return False
        n_hyp = len(m.assumptions)
        self.info.setStyleSheet("color:#7ee787;")
        self.info.setText(f"Valid model: {m.summary()}, {len(m.lp.definitions)} definitions, "
                          f"assumptions on {n_hyp} symbols.")
        return True

    def _accept(self) -> None:
        if not self._check():
            QMessageBox.warning(self, "Invalid model", self.info.text())
            return
        self.accept()

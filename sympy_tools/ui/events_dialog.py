"""Window "Events…": the events of the model and the check of each symmetry (compiled LaTeX)."""

from __future__ import annotations

import os

import pymupdf
from PySide6.QtCore import Qt
from PySide6.QtGui import QGuiApplication, QImage, QPixmap
from PySide6.QtWidgets import (QApplication, QDialog, QFileDialog, QHBoxLayout, QLabel, QPushButton,
                               QScrollArea, QVBoxLayout, QWidget)

from ..core.events_doc import compile_document, events_document
from .theme import dialog_stylesheet


class EventsDialog(QDialog):
    def __init__(self, model, parent=None, last_dir: str = "") -> None:
        super().__init__(parent)
        self.setWindowTitle("Events and symmetries")
        self.setStyleSheet(dialog_stylesheet())
        self.resize(880, 900)
        self._last_dir = last_dir or os.path.expanduser("~")
        QGuiApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        try:
            self.tex = events_document(model)
            self.pdf, error = compile_document(self.tex)
        finally:
            QGuiApplication.restoreOverrideCursor()

        lay = QVBoxLayout(self)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { background: #ffffff; }")
        pages = QWidget()
        pages.setStyleSheet("background: #ffffff;")
        col = QVBoxLayout(pages)
        if self.pdf is None:
            col.addWidget(QLabel(error))
        else:
            doc = pymupdf.open(stream=self.pdf, filetype="pdf")
            for page in doc:
                pix = page.get_pixmap(dpi=98)
                img = QImage(pix.samples, pix.width, pix.height, pix.stride, QImage.Format.Format_RGB888)
                label = QLabel()
                label.setPixmap(QPixmap.fromImage(img.copy()))
                label.setAlignment(Qt.AlignmentFlag.AlignHCenter)
                col.addWidget(label)
        col.addStretch(1)
        scroll.setWidget(pages)
        lay.addWidget(scroll, 1)

        row = QHBoxLayout()
        save = QPushButton("Save PDF…")
        save.clicked.connect(self.save_pdf)
        save.setEnabled(self.pdf is not None)
        copy = QPushButton("Copy LaTeX")
        copy.clicked.connect(lambda: QApplication.clipboard().setText(self.tex))
        close = QPushButton("Close")
        close.clicked.connect(self.accept)
        row.addWidget(save)
        row.addWidget(copy)
        row.addStretch(1)
        row.addWidget(close)
        lay.addLayout(row)

    def save_pdf(self) -> None:
        path, _ = QFileDialog.getSaveFileName(self, "Save PDF",
                                              os.path.join(self._last_dir, "events_symmetries.pdf"),
                                              "PDF (*.pdf)")
        if path:
            if not path.lower().endswith(".pdf"):
                path += ".pdf"
            with open(path, "wb") as f:
                f.write(self.pdf)

"""Entry point: `sympy-tools` or `python -m sympy_tools`."""

from __future__ import annotations

import importlib.util
import multiprocessing
import sys

from PySide6.QtWidgets import QApplication


def main() -> None:
    multiprocessing.freeze_support()
    if importlib.util.find_spec("latex_preview") is None:
        sys.exit("Sympy Tools needs latex-preview: run  pip install -e ../latex-preview  "
                 "(github.com/leec13/latex-preview).")
    app = QApplication(sys.argv)
    app.setApplicationName("Sympy Tools")
    app.setOrganizationName("SympyTools")
    from .ui.main_window import MainWindow
    win = MainWindow()
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()

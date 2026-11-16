"""Dark theme (always on), so that the window is easy to tell from latex-preview.

The LaTeX preview keeps a white sheet with black text (latex-preview's widget), and
copied images stay black on white, as in presentations.
"""

from __future__ import annotations

from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QApplication

_COLORS = {
    QPalette.ColorRole.Window: "#1f2329",
    QPalette.ColorRole.WindowText: "#d7dce2",
    QPalette.ColorRole.Base: "#15181d",
    QPalette.ColorRole.AlternateBase: "#22262c",
    QPalette.ColorRole.Text: "#e6e9ee",
    QPalette.ColorRole.Button: "#2b3038",
    QPalette.ColorRole.ButtonText: "#e6e9ee",
    QPalette.ColorRole.BrightText: "#ffffff",
    QPalette.ColorRole.Highlight: "#3a6ea5",
    QPalette.ColorRole.HighlightedText: "#ffffff",
    QPalette.ColorRole.ToolTipBase: "#2b3038",
    QPalette.ColorRole.ToolTipText: "#e6e9ee",
    QPalette.ColorRole.PlaceholderText: "#7d8590",
    QPalette.ColorRole.Link: "#58a6ff",
    QPalette.ColorRole.Light: "#3a404a",
    QPalette.ColorRole.Midlight: "#30353d",
    QPalette.ColorRole.Mid: "#262a31",
    QPalette.ColorRole.Dark: "#121418",
    QPalette.ColorRole.Shadow: "#000000",
}
_DISABLED = "#6b7280"


def apply_dark_theme(app: QApplication) -> None:
    app.setStyle("Fusion")          # the same look on every system, and it follows the palette
    pal = QPalette()
    for role, color in _COLORS.items():
        pal.setColor(role, QColor(color))
    for role in (QPalette.ColorRole.Text, QPalette.ColorRole.ButtonText,
                 QPalette.ColorRole.WindowText):
        pal.setColor(QPalette.ColorGroup.Disabled, role, QColor(_DISABLED))
    pal.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.Button, QColor("#23272e"))
    app.setPalette(pal)

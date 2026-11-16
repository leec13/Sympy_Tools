"""Visual identity: light, like latex-preview, but easy to tell apart.

- a coloured band at the top of the window;
- a lightly tinted window background;
- the SymPy code pane tinted, with a coloured left border;
- section titles in the accent colour.

The LaTeX preview keeps a white sheet with black text, and copied images are black
on white. The system style (macOS) is kept.
"""

from __future__ import annotations

ACCENT = "#2a9d8f"        # teal
ACCENT_DARK = "#1f6f66"   # titles
TINT = "#eef6f4"          # window background
CODE_BG = "#e3f1ee"
CODE_FG = "#17403b"

# notes and verdicts (readable on a light background)
NOTE_COLORS = {"error": "#b00020", "warning": "#a35a00", "info": "#5f6b6a"}
VERDICT_COLORS = {"equal": "#2e7d32", "different": "#b00020", "undetermined": "#a35a00"}


def window_stylesheet() -> str:
    return (f"#central {{ background: {TINT}; }} QStatusBar {{ background: {TINT}; }}"
            f"#band {{ background: {ACCENT}; }}"
            f"QLabel[section=\"true\"] {{ color: {ACCENT_DARK}; font-weight: bold; }}"
            f"#codeView {{ background: {CODE_BG}; color: {CODE_FG};"
            f" border: none; border-left: 4px solid {ACCENT}; }}")


def dialog_stylesheet() -> str:
    return f"QDialog {{ background: {TINT}; }}"


def title(text: str) -> str:
    """Section title (HTML) in the accent colour."""
    return f"<b style='color:{ACCENT_DARK}'>{text}</b>"

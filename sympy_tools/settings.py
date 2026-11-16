"""Persistent preferences (QSettings: ~/Library/Preferences on macOS)."""

from __future__ import annotations

from PySide6.QtCore import QSettings

WELCOME_RHS = ("m*(n_A1 + n_B1 + 2*M_A1_B1 - 2*M_A1_A1) + rmaxA*(n_A1 + 2*M_A1_A1)"
               " + (M_A1_A1 + M_A1_A2)/KA")

DEFAULTS = {
    "model_text": "",          # empty: default model
    "model_path": "",
    "mode": "equation",
    "expr_text": "2*M_A1_A1 + M_A2_A1",
    "lhs_text": "dM_A1_A1_dt",
    "rhs_text": WELCOME_RHS,
    "collect_var": "",
    "show_latex_code": False,
    "show_latex_rendered": True,
    "zoom": 1.6,
    "last_dir": "",
    "geometry": b"",
}

_TYPES = {k: type(v) for k, v in DEFAULTS.items()}


class Settings:
    def __init__(self) -> None:
        self._q = QSettings("SympyTools", "SympyTools")

    def get(self, key: str):
        default = DEFAULTS[key]
        value = self._q.value(key, default)
        t = _TYPES[key]
        try:
            if t is bool:
                return value if isinstance(value, bool) else str(value).lower() in ("1", "true", "yes")
            if t is bytes:
                return bytes(value) if value else b""
            return t(value)
        except (TypeError, ValueError):
            return default

    def set(self, key: str, value) -> None:
        self._q.setValue(key, value)

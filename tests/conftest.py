"""Test isolation: never read nor change the user's preferences, never open a real window."""
import os
import tempfile

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
_settings = os.path.join(tempfile.mkdtemp(prefix="sympy_tools_tests_"), "settings.ini")
os.environ["SYMPY_TOOLS_SETTINGS"] = _settings      # see sympy_tools/settings.py

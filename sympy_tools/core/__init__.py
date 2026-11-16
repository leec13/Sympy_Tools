"""Core, without any GUI: usable from a script or a notebook.

- model: the .ini model (shared with latex-preview), assumptions, symbol registry
- reading: Python-like text -> checked SymPy expression
- operations: Simplify, Factor, Expand, Collect by, Compare
- output: Python text and LaTeX
- jobs: string-in / string-out entry points for the worker process
"""

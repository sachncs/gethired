"""Text normalization helpers used by the renderer.

Re-exports ``strip_latex_commands`` from ``normalize`` for renderer use.
"""

from gethired.normalize import strip_latex_commands

__all__ = ["strip_latex_commands"]

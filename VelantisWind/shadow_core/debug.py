# -*- coding: utf-8 -*-
"""Debug helpers for the shadow-flicker module.

Console diagnostics are useful while validating geometry and DEM behaviour,
but they should not clutter the QGIS Python console during normal use.
Set VELANTISWIND_DEBUG=1 before launching QGIS to enable these messages.
"""

from __future__ import annotations

import os


def is_debug_enabled() -> bool:
    """Return True when verbose shadow diagnostics should be printed."""

    value = os.environ.get("VELANTISWIND_DEBUG", "").strip().lower()
    return value in {"1", "true", "yes", "on", "debug"}


def debug_print(*args, **kwargs) -> None:
    """Print only when VELANTISWIND_DEBUG is enabled."""

    if is_debug_enabled():
        print(*args, **kwargs)

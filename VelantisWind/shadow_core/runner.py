# -*- coding: utf-8 -*-
"""Runner façade for shadow-flicker calculations.

The runner preserves the current point-receptor physics implementation while
giving the module the same UI -> controller -> runner shape used by Energy and
Noise.
"""

from __future__ import annotations

from .domain import ShadowRunConfig


class ShadowRunner:
    """Execute a shadow-flicker calculation from a validated configuration."""

    def run_from_dialog(self, dialog, config: ShadowRunConfig):
        point_runner = getattr(dialog, "_run_shadow_point_calculation", None)
        if point_runner is None:
            raise RuntimeError("ShadowPage point-receptor calculation entry point is missing.")
        return point_runner()

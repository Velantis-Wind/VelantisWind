# -*- coding: utf-8 -*-
"""Runner façade for shadow-flicker calculations.

The runner preserves the current point-receptor physics implementation while
giving the module the same UI -> controller -> runner shape used by Energy and
Noise.
"""

from __future__ import annotations

try:
    from ..i18n import current_language
except Exception:
    def current_language(): return "fr"

def _is_de():
    return str(current_language()).lower().startswith("de")

from .domain import ShadowRunConfig


class ShadowRunner:
    """Execute a shadow-flicker calculation from a validated configuration."""

    def run_from_dialog(self, dialog, config: ShadowRunConfig):
        point_runner = getattr(dialog, "_run_shadow_point_calculation", None)
        if point_runner is None:
            raise RuntimeError("Der Einstiegspunkt der Rezeptorberechnung im Schattenwurfmodul fehlt." if _is_de() else "Le point d’entrée du calcul par récepteurs du module d’ombres est manquant.")
        return point_runner()

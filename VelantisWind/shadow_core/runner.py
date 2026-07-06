# -*- coding: utf-8 -*-
"""Runner façade for shadow-flicker calculations."""

from __future__ import annotations

from .domain import ShadowRunConfig
from .i18n_local import tr4 as _ml


class ShadowRunner:
    """Execute a shadow-flicker calculation from a validated configuration."""

    def run_from_dialog(self, dialog, config: ShadowRunConfig):
        point_runner = getattr(dialog, "_run_shadow_point_calculation", None)
        if point_runner is None:
            raise RuntimeError(_ml(
                "Falta el punto de entrada del cálculo por receptores del módulo de sombras.",
                "The receiver-calculation entry point is missing in the shadow module.",
                "Le point d’entrée du calcul par récepteurs du module d’ombres est manquant.",
                "Der Einstiegspunkt der Rezeptorberechnung im Schattenwurfmodul fehlt.",
            ))
        return point_runner()

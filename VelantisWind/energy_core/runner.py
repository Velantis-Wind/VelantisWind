# -*- coding: utf-8 -*-
"""Runner del módulo de energía.

Este servicio concentra la llamada al motor ``ag_core``. Así la UI no necesita
importar directamente el cálculo PyWake y mantiene separada la lógica de
ejecución del módulo.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from .domain import EnergyRunConfig, ProgressCallback
from .validation import ValidationIssue, format_validation_issues, validate_energy_config


class EnergyValidationError(ValueError):
    """Error de validación previo a cálculo."""

    def __init__(self, issues: list[ValidationIssue]):
        self.issues = issues
        super().__init__(format_validation_issues(issues))


class EnergyRunner:
    """Ejecuta el cálculo AEP validando antes la configuración."""

    def run(self, config: EnergyRunConfig, progress_callback: Optional[ProgressCallback] = None) -> Dict[str, Any]:
        issues = validate_energy_config(config)
        errors = [i for i in issues if i.is_error]
        if errors:
            raise EnergyValidationError(errors)

        # Import local para que abrir el plugin/hub no fuerce PyWake hasta que
        # el usuario lance un cálculo de energía. El primer import es el normal
        # dentro del paquete QGIS; el segundo facilita pruebas aisladas.
        try:
            from ..ag_core.aep_compute import compute_and_update
        except Exception:  # pragma: no cover - standalone fallback
            from ag_core.aep_compute import compute_and_update  # type: ignore

        return compute_and_update(**config.to_compute_kwargs(progress_callback=progress_callback))

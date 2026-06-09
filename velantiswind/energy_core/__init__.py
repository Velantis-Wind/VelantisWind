# -*- coding: utf-8 -*-
"""Arquitectura limpia del módulo de energía.

El paquete ``energy_core`` es una capa nueva y estable alrededor del código
histórico ``ag_core``. La migración es progresiva: ``ag_core`` sigue calculando,
pero la UI ya puede trabajar con objetos de dominio y un runner desacoplado.
"""

from .domain import EnergyRunConfig, TurbineModelInput
from .runner import EnergyRunner, EnergyValidationError
from .validation import ValidationIssue, format_validation_issues, validate_energy_config
from .dialog_state import DialogStateError, DialogStateMessage, EnergyDialogState

__all__ = [
    "EnergyRunConfig",
    "TurbineModelInput",
    "EnergyRunner",
    "EnergyValidationError",
    "ValidationIssue",
    "format_validation_issues",
    "validate_energy_config",
    "DialogStateError",
    "DialogStateMessage",
    "EnergyDialogState",
]

# NOTE: dialog_controller is intentionally not imported here because it depends
# on QGIS/Qt objects. Import it lazily from the UI action when needed.

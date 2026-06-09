# -*- coding: utf-8 -*-
"""Small orchestration helpers for the Energy/AEP calculation flow.

These helpers keep :mod:`ag_core.aep_compute` focused on the simulation flow,
while preserving its public API and numerical behaviour.
"""

from .resource_loader import (
    normalize_resource_inputs,
    load_energy_site,
    ensure_ti_available,
)
from .layout_builder import build_layout_arrays
from .model_config import build_physical_model_config
from .result_builder import build_energy_result_payload

__all__ = [
    "normalize_resource_inputs",
    "load_energy_site",
    "ensure_ti_available",
    "build_layout_arrays",
    "build_physical_model_config",
    "build_energy_result_payload",
]

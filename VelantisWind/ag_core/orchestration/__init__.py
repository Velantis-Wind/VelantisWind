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
from .resource_settings import (
    check_speedup, effective_turbines, turbine_speed_grid, resolve_resource_settings, resource_log_line,
    resource_note,
)

__all__ = [
    "normalize_resource_inputs",
    "load_energy_site",
    "ensure_ti_available",
    "build_layout_arrays",
    "check_speedup",
    "effective_turbines",
    "turbine_speed_grid",
    "resolve_resource_settings",
    "resource_log_line",
    "resource_note",
]

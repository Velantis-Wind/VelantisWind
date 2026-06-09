# -*- coding: utf-8 -*-
"""Utilities for AEP result extraction and table assembly."""

from .aep_arrays import aep_per_turb, extract_directional_breakdown
from .tables import build_per_turbine_table
from .summary import (
    aggregate_by_model,
    build_model_geometry_and_power,
    build_names_by_type,
    compute_global_losses,
    log_result_summary,
)

__all__ = [
    "aep_per_turb",
    "extract_directional_breakdown",
    "build_per_turbine_table",
    "aggregate_by_model",
    "build_model_geometry_and_power",
    "build_names_by_type",
    "compute_global_losses",
    "log_result_summary",
]

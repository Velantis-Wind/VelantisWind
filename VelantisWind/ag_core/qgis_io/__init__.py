# -*- coding: utf-8 -*-
"""QGIS-facing IO helpers for AEP and wake-raster results.

The package intentionally avoids importing QGIS layer writers eagerly. This
keeps worker-safe modules such as ``wake_raster`` importable without pulling
live QGIS classes into a background calculation thread.
"""
from __future__ import annotations

from importlib import import_module

__all__ = [
    "update_layers_from_results",
    "push_results_to_point_layer",
    "create_summary_layer",
    "export_per_turbine_to_csv",
]


def __getattr__(name: str):
    if name in {"update_layers_from_results", "push_results_to_point_layer"}:
        module = import_module(f"{__name__}.layers")
        return getattr(module, name)
    if name in {"create_summary_layer", "export_per_turbine_to_csv"}:
        module = import_module(f"{__name__}.export")
        return getattr(module, name)
    raise AttributeError(name)

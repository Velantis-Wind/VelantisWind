# -*- coding: utf-8 -*-
"""Domain objects for the Velantis Wind noise module.

This module intentionally contains no UI code. It is the stable boundary between
``noise_page.py`` and the calculation engine.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any

try:
    from qgis.core import QgsRasterLayer, QgsVectorLayer
except Exception:  # pragma: no cover - allows static checks outside QGIS
    QgsRasterLayer = Any
    QgsVectorLayer = Any


@dataclass
class NoiseRunConfig:
    """Complete configuration needed to run one noise calculation."""

    receiver_layer: QgsVectorLayer
    model_cfg: Dict[str, Dict[str, Any]]
    source_layer_ids: List[str] = field(default_factory=list)

    receiver_height_m: float = 4.0
    max_radius_m: float = 5000.0
    dem_layer: Optional[QgsRasterLayer] = None
    alpha_db_per_m: float = 0.005
    ground_factor_g: float = 0.5
    ground_mode: str = "global"
    landuse_layer: Optional[QgsVectorLayer] = None

    receiver_limit_dba: float = 45.0
    receiver_limit_mode: str = "global"
    receiver_limit_scenario: str = "custom"
    receiver_limit_field_day: Optional[str] = None
    receiver_limit_field_night: Optional[str] = None
    receiver_limit_field_custom: Optional[str] = None
    receiver_type_field: Optional[str] = None
    receiver_height_field: Optional[str] = None
    receiver_source_field: Optional[str] = None

    min_distance_m: float = 25.0
    result_layer_name: str = "Noise · Receivers"
    sources_layer_name: str = "Noise · Sources"
    links_layer_name: str = "Noise · Dominant links"
    grid_layer_name: str = "Noise · Map"
    iso_layer_name: str = "Noise · Isophones"
    uncovered_layer_name: str = "Noise · Receivers outside radius"

    create_sources_layer: bool = True
    create_links_layer: bool = True
    create_grid_layer: bool = False
    create_iso_layer: bool = False
    iso_levels: List[float] = field(default_factory=lambda: [35.0, 40.0, 45.0, 50.0])
    grid_resolution_m: float = 100.0

    calculation_engine: str = "fast"
    temperature_c: float = 15.0
    humidity_percent: float = 70.0
    pressure_kpa: float = 101.325


@dataclass
class NoiseRunResult:
    """Thin wrapper around the current result dictionary.

    The calculation engine returns a rich dictionary used by the results
    dialog. Keeping it wrapped lets us evolve the internals later without
    changing the UI again.
    """

    raw: Dict[str, Any]

    @property
    def n_receivers(self) -> int:
        try:
            return int(self.raw.get("n_receivers", 0))
        except Exception:
            return 0

    @property
    def max_noise_dba(self) -> float:
        try:
            return float(self.raw.get("max_noise_dba", 0.0))
        except Exception:
            return 0.0

    @property
    def n_exceedances(self) -> int:
        try:
            return int(self.raw.get("n_receivers_exceeding_limit", 0))
        except Exception:
            return 0

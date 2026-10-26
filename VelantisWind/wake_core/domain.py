# -*- coding: utf-8 -*-
"""Primitive configuration objects for the wake-raster workflow."""
from __future__ import annotations

import copy
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from ..ag_core.wake_setup.config import WakeConfig, default_config


@dataclass
class WakeRasterTaskConfig:
    """Inputs captured on QGIS' main thread before the worker starts: the wake configuration of the AEP and its
    resource inputs (#46 P5b; the raster's physical inputs are the AEP's, #75 rows 5.1-5.6)."""

    models: List[Dict[str, Any]]
    wasp_dir: str
    wake_config: WakeConfig = field(default_factory=default_config)
    # The provenance of a predefined model (``presets.provenance``), captured with the configuration; ``None`` else.
    wake_provenance: Optional[Dict[str, Any]] = None
    resolution_m: float = 300.0
    wrg_paths: List[str] = field(default_factory=list)
    ws_plot: float = 10.0
    wd_target: Optional[float] = None
    output_dir: str = ""
    crs_wkt: str = ""
    crs_authid: str = ""
    # Tratamiento de la densidad del aire leído del diálogo de energía, el mismo que usa el AEP.
    air_density: Dict[str, Any] = field(default_factory=lambda: {"mode": "off"})
    # Parámetros del recurso de un WRG y su TI, los del AEP.
    wd_interp: str = "nearest"
    wrg_direction_count: Optional[int] = None
    wrg_ti_paths: Optional[List[str]] = None
    wrg_ti_heights_m: Optional[List[Optional[float]]] = None
    fixed_ti: Optional[float] = None
    project_crs_authid: Optional[str] = None
    # The explicit scenario without blockage, another product (row 5.3).
    without_blockage: bool = False
    # How its inputs compare with the last AEP of the project (#36), recorded in the JSON.
    aep_comparison: Optional[Dict[str, Any]] = None

    def __post_init__(self) -> None:
        # Shallow-copy turbine objects but detach all mutable container state
        # from the live dialog. Coordinates and metadata are plain snapshots.
        self.models = [dict(model or {}) for model in (self.models or [])]
        for model in self.models:
            if model.get("coords_xy") is not None:
                model["coords_xy"] = [
                    (float(point[0]), float(point[1]))
                    for point in (model.get("coords_xy") or [])
                ]
            if isinstance(model.get("meta"), dict):
                model["meta"] = dict(model.get("meta") or {})
        self.wrg_paths = [str(path) for path in (self.wrg_paths or []) if str(path).strip()]
        self.wrg_ti_paths = list(self.wrg_ti_paths) if self.wrg_ti_paths else None
        self.wrg_ti_heights_m = list(self.wrg_ti_heights_m) if self.wrg_ti_heights_m else None
        self.air_density = dict(self.air_density or {"mode": "off"})
        self.wake_provenance = copy.deepcopy(self.wake_provenance)
        self.aep_comparison = copy.deepcopy(self.aep_comparison)

    def to_engine_kwargs(self) -> Dict[str, Any]:
        """The arguments of ``wake_core.raster.compute_wake_raster_config``."""
        return {
            "models": self.models,
            "wake_config": self.wake_config,
            "wake_provenance": self.wake_provenance,
            "wasp_dir": "" if self.wrg_paths else str(self.wasp_dir or ""),
            "wrg_paths": list(self.wrg_paths) or None,
            "wrg_wd_interp": self.wd_interp,
            "wrg_direction_count": self.wrg_direction_count,
            "wrg_ti_paths": self.wrg_ti_paths,
            "wrg_ti_heights_m": self.wrg_ti_heights_m,
            "fixed_ti": self.fixed_ti,
            "project_crs_authid": self.project_crs_authid,
            "resolution_m": float(self.resolution_m),
            "ws_plot": float(self.ws_plot),
            "wd_target": self.wd_target,
            "output_dir": str(self.output_dir or ""),
            "crs_wkt": str(self.crs_wkt or ""),
            "crs_authid": str(self.crs_authid or ""),
            "air_density": dict(self.air_density),
            "without_blockage": bool(self.without_blockage),
            "aep_comparison": copy.deepcopy(self.aep_comparison),
        }

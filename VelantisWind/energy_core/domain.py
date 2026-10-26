# -*- coding: utf-8 -*-
"""Dominio del módulo de energía.

Estas clases aíslan la configuración de cálculo de la UI de QGIS y del motor
PyWake. Mantienen compatibilidad con el contrato actual de cálculo de ``ag_core`` para
permitir una migración progresiva sin romper el plugin.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple

from ..ag_core.wake_setup.api import LEGACY_FIELDS, NOT_SET

Coordinate = Tuple[float, float]
ProgressCallback = Callable[[int, str], None]


@dataclass
class TurbineModelInput:
    """Entrada normalizada de un modelo de aerogenerador y su layout."""

    name: str
    wt: Any
    meta: Optional[Dict[str, Any]] = None
    coords_csv: str = ""
    coords_xy: Optional[Sequence[Coordinate]] = None
    source_row_index: Optional[int] = None
    source_type_index: Optional[int] = None
    # Capa del proyecto de la que salen las coordenadas: el volcado de resultados escribe en ella.
    source_layer_id: str = ""
    source_layer_name: str = ""

    def to_compute_model_dict(self) -> Dict[str, Any]:
        """Devuelve el formato de modelo esperado por ``ag_core.aep_compute``."""
        return {
            "name": self.name or "Custom WT",
            "wt": self.wt,
            "meta": self.meta,
            "coords_csv": self.coords_csv or "",
            "coords_xy": list(self.coords_xy) if self.coords_xy else None,
            "source_row_index": self.source_row_index,
            "source_type_index": self.source_type_index,
            "source_layer_id": self.source_layer_id or "",
            "source_layer_name": self.source_layer_name or "",
        }


@dataclass
class EnergyRunConfig:
    """Configuración completa de un cálculo AEP.

    No contiene widgets Qt ni objetos de QGIS. La UI debe construir este objeto y
    delegar la ejecución en ``EnergyRunner``.
    """

    models: List[TurbineModelInput] = field(default_factory=list)
    wasp_dir: str = ""
    wrg_paths: Optional[List[str]] = None
    # Parámetros del recurso de un WRG: número de direcciones de cálculo (None = la selección
    # inicial), interpolación direccional, Speedup (solo "none") y paso de las velocidades de
    # cálculo (None = el inicial de las curvas). Un GRD usa los de su Site.
    wrg_direction_count: Optional[int] = None
    wrg_wd_interp: str = "nearest"
    wrg_speedup_method: str = "none"
    energy_ws_step: Optional[float] = None
    compute_variants: bool = True
    # The wake physics (ag_core/wake_setup/api.py): ``wake_physics``, or the fields of the previous schema, each
    # «not indicated» (NOT_SET) by default and passed as given, never converted (#46, P5 a-b).
    wake_physics: Any = NOT_SET
    # The provenance of a predefined model of the dialog (``presets.provenance``); ``None`` for any other physics.
    wake_provenance: Optional[Dict[str, Any]] = None
    include_turbulence: Any = NOT_SET
    include_blockage: Any = NOT_SET
    include_rotor_avg: Any = NOT_SET
    rotor_avg_model: Any = NOT_SET
    superposition_model: Any = NOT_SET
    wfm_engine: Any = NOT_SET
    wake_deficit_model: Any = NOT_SET
    wake_deficit_kwargs: Any = NOT_SET
    turbulence_model: Any = NOT_SET
    blockage_deficit_model: Any = NOT_SET
    fixed_ti: Optional[float] = None
    wrg_ti_paths: Optional[List[str]] = None
    wrg_ti_heights_m: Optional[List[Optional[float]]] = None
    project_crs_authid: Optional[str] = None
    tol_m: float = 30.0
    # Densidad del aire: "off" (cada curva por densidad a su densidad por defecto),
    # "uniform" (la de referencia en todo el parque) o "per_turbine" (ISA calibrado
    # en la referencia, a la cota de cada buje).
    air_density_mode: str = "off"
    air_density_ref_kg_m3: Optional[float] = None
    air_density_ref_altitude_m: Optional[float] = None
    update_project_layers: bool = True

    @property
    def use_wrg(self) -> bool:
        return bool(self.wrg_paths)

    def to_compute_kwargs(self, progress_callback: Optional[ProgressCallback] = None) -> Dict[str, Any]:
        """Convierte la configuración al contrato actual de ``compute_and_update``."""
        return {
            "wasp_dir": "" if self.use_wrg else (self.wasp_dir or ""),
            "models": [m.to_compute_model_dict() for m in self.models],
            "wrg_paths": self.wrg_paths if self.use_wrg else None,
            "wrg_speedup_method": self.wrg_speedup_method,
            "wrg_direction_count": self.wrg_direction_count,
            "wrg_wd_interp": self.wrg_wd_interp,
            "energy_ws_step": self.energy_ws_step,
            "compute_variants": bool(self.compute_variants),
            "wake_physics": self.wake_physics,
            "wake_provenance": self.wake_provenance,
            **{name: getattr(self, name) for name in LEGACY_FIELDS if name != "wake_model"},
            "fixed_ti": self.fixed_ti,
            "wrg_ti_paths": self.wrg_ti_paths if self.use_wrg and self.wrg_ti_paths else None,
            "wrg_ti_heights_m": self.wrg_ti_heights_m if self.use_wrg and self.wrg_ti_paths else None,
            "project_crs_authid": self.project_crs_authid,
            "air_density_mode": self.air_density_mode,
            "air_density_ref_kg_m3": self.air_density_ref_kg_m3,
            "air_density_ref_altitude_m": self.air_density_ref_altitude_m,
            "update_project_layers": bool(self.update_project_layers),
            "tol_m": float(self.tol_m),
            "progress_callback": progress_callback,
        }

# -*- coding: utf-8 -*-
"""Dominio del módulo de energía.

Estas clases aíslan la configuración de cálculo de la UI de QGIS y del motor
PyWake. Mantienen compatibilidad con el contrato actual de cálculo de ``ag_core`` para
permitir una migración progresiva sin romper el plugin.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple

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

    def to_compute_model_dict(self) -> Dict[str, Any]:
        """Devuelve el formato de modelo esperado por ``ag_core.aep_compute``."""
        return {
            "name": self.name or "Custom WT",
            "wt": self.wt,
            "meta": self.meta,
            "coords_csv": self.coords_csv or "",
            "coords_xy": list(self.coords_xy) if self.coords_xy else None,
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
    compute_variants: bool = True
    include_turbulence: bool = False
    include_blockage: bool = False
    include_rotor_avg: bool = False
    rotor_avg_model: str = "NONE"
    superposition_model: str = "AUTO"
    wfm_engine: str = "PDW"
    wake_deficit_model: str = "BG"
    wake_deficit_kwargs: Dict[str, Any] = field(default_factory=dict)
    turbulence_model: str = "NONE"
    blockage_deficit_model: str = "NONE"
    fixed_ti: Optional[float] = None
    wrg_ti_paths: Optional[List[str]] = None
    wrg_ti_heights_m: Optional[List[Optional[float]]] = None
    project_crs_authid: Optional[str] = None
    tol_m: float = 30.0

    @property
    def use_wrg(self) -> bool:
        return bool(self.wrg_paths)

    def to_compute_kwargs(self, progress_callback: Optional[ProgressCallback] = None) -> Dict[str, Any]:
        """Convierte la configuración al contrato actual de ``compute_and_update``."""
        return {
            "wasp_dir": "" if self.use_wrg else (self.wasp_dir or ""),
            "models": [m.to_compute_model_dict() for m in self.models],
            "wrg_paths": self.wrg_paths if self.use_wrg else None,
            "compute_variants": bool(self.compute_variants),
            "include_turbulence": bool(self.include_turbulence),
            "include_blockage": bool(self.include_blockage),
            "include_rotor_avg": bool(self.include_rotor_avg),
            "rotor_avg_model": self.rotor_avg_model,
            "superposition_model": self.superposition_model,
            "wfm_engine": self.wfm_engine,
            "wake_deficit_model": self.wake_deficit_model,
            "wake_deficit_kwargs": dict(self.wake_deficit_kwargs or {}),
            "turbulence_model": self.turbulence_model,
            "blockage_deficit_model": self.blockage_deficit_model,
            "fixed_ti": self.fixed_ti,
            "wrg_ti_paths": self.wrg_ti_paths if self.use_wrg and self.wrg_ti_paths else None,
            "wrg_ti_heights_m": self.wrg_ti_heights_m if self.use_wrg and self.wrg_ti_paths else None,
            "project_crs_authid": self.project_crs_authid,
            "tol_m": float(self.tol_m),
            "progress_callback": progress_callback,
        }

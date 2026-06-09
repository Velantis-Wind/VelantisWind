# -*- coding: utf-8 -*-
"""Validaciones desacopladas para el módulo de energía."""

from __future__ import annotations

from dataclasses import dataclass
from typing import List
import os

from .domain import EnergyRunConfig, TurbineModelInput


@dataclass(frozen=True)
class ValidationIssue:
    severity: str  # "error" | "warning"
    message: str

    @property
    def is_error(self) -> bool:
        return self.severity.lower() == "error"


def _has_live_points(model: TurbineModelInput) -> bool:
    try:
        return bool(model.coords_xy) and len(model.coords_xy or []) > 0
    except Exception:
        return False


def validate_energy_config(config: EnergyRunConfig) -> List[ValidationIssue]:
    """Valida configuración antes de invocar PyWake/ag_core.

    La idea es fallar pronto con mensajes claros de usuario, en vez de dejar que
    PyWake falle varios niveles más abajo con trazas difíciles de interpretar.
    """
    issues: List[ValidationIssue] = []

    if not config.models:
        issues.append(ValidationIssue("error", "No se ha definido ningún modelo de aerogenerador."))

    for idx, model in enumerate(config.models, start=1):
        label = model.name or f"Modelo {idx}"
        if model.wt is None:
            issues.append(ValidationIssue("error", f"{label}: falta definir la turbina/curva de potencia."))
        if not _has_live_points(model):
            csv_path = (model.coords_csv or "").strip()
            if not csv_path:
                issues.append(ValidationIssue("error", f"{label}: faltan coordenadas. Selecciona CSV o añade puntos en el mapa."))
            elif not os.path.isfile(csv_path):
                issues.append(ValidationIssue("error", f"{label}: el CSV de coordenadas no existe: {csv_path}"))

    wrg_paths = [p for p in (config.wrg_paths or []) if str(p).strip()]
    if wrg_paths:
        for p in wrg_paths:
            if not os.path.isfile(p):
                issues.append(ValidationIssue("error", f"WRG/ZIP no existe: {p}"))
            elif not str(p).lower().endswith((".wrg", ".zip")):
                issues.append(ValidationIssue("error", f"Extensión WRG no soportada. Usa .wrg o .zip: {p}"))
    else:
        if not config.wasp_dir or not os.path.isdir(config.wasp_dir):
            issues.append(ValidationIssue("error", "Selecciona una carpeta WAsP válida o un WRG/ZIP."))

    for p in (config.wrg_ti_paths or []):
        if p and not os.path.isfile(p):
            issues.append(ValidationIssue("error", f"Raster TI no existe: {p}"))

    engine = (config.wfm_engine or "").upper()
    if engine == "PDW" and (config.blockage_deficit_model or "").upper() not in ("", "NONE", "NINGUNO"):
        issues.append(ValidationIssue("warning", "PropagateDownwind no aplica bloqueo; el cálculo lo desactivará automáticamente."))

    if config.use_wrg and not config.wrg_ti_paths and config.include_turbulence:
        issues.append(ValidationIssue("warning", "No se ha seleccionado raster TI para WRG; se usará TI fija/fallback si el modelo lo necesita."))

    return issues


def format_validation_issues(issues: List[ValidationIssue]) -> str:
    if not issues:
        return ""
    lines = []
    for issue in issues:
        prefix = "ERROR" if issue.is_error else "AVISO"
        lines.append(f"[{prefix}] {issue.message}")
    return "\n".join(lines)

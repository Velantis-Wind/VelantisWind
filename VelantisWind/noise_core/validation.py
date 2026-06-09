# -*- coding: utf-8 -*-
"""Validation helpers for the noise module."""
from __future__ import annotations

import math
import os
from typing import Dict, List, Tuple, Any

try:
    from qgis.core import QgsProject, QgsRasterLayer, QgsVectorLayer, QgsWkbTypes
except Exception:  # pragma: no cover
    QgsProject = None
    QgsRasterLayer = object
    QgsVectorLayer = object
    QgsWkbTypes = None

from .domain import NoiseRunConfig


def is_finite_positive(value: Any, *, allow_zero: bool = False) -> bool:
    try:
        v = float(value)
        if not math.isfinite(v):
            return False
        return v >= 0.0 if allow_zero else v > 0.0
    except Exception:
        return False


def validate_model_config(model_cfg: Dict[str, Dict[str, Any]]) -> List[str]:
    errors: List[str] = []
    if not isinstance(model_cfg, dict) or not model_cfg:
        return ["No hay configuración acústica de modelos."]

    seen_groups = set()
    for model_name, cfg in model_cfg.items():
        name = str(model_name or "Modelo sin nombre")
        cfg = cfg or {}
        source_group = str(cfg.get("source_group_name") or name).strip()
        if not source_group:
            errors.append(f"{name}: falta nombre de grupo fuente.")
        else:
            key = source_group.lower()
            if key in seen_groups:
                errors.append(f"{name}: nombre de grupo fuente duplicado '{source_group}'.")
            seen_groups.add(key)

        mode = str(cfg.get("acoustic_mode") or "fixed").strip().lower()
        lwa = cfg.get("lwa")
        if lwa is None or not is_finite_positive(lwa):
            errors.append(f"{name}: LwA fijo no válido.")

        if mode == "curve":
            curve_path = str(cfg.get("curve_path") or "").strip()
            if not curve_path:
                errors.append(f"{name}: modo curva activo pero sin CSV de curva acústica.")
            elif not os.path.exists(curve_path):
                errors.append(f"{name}: no existe la curva acústica '{curve_path}'.")

        hh = cfg.get("hub_height", 100.0)
        if not is_finite_positive(hh):
            errors.append(f"{name}: altura de buje no válida.")
    return errors


def _same_crs(layer: Any, project: Any) -> bool:
    try:
        return bool(layer.crs().isValid()) and layer.crs() == project.crs()
    except Exception:
        return False


def validate_run_config(config: NoiseRunConfig) -> Tuple[List[str], List[str]]:
    """Return ``(errors, warnings)`` for a calculation config."""
    errors: List[str] = []
    warnings: List[str] = []

    prj = QgsProject.instance() if QgsProject is not None else None
    receiver_layer = config.receiver_layer
    if not isinstance(receiver_layer, QgsVectorLayer):
        errors.append("Selecciona una capa válida de receptores.")
    else:
        try:
            if int(receiver_layer.featureCount()) <= 0:
                errors.append(f"La capa de receptores '{receiver_layer.name()}' está vacía.")
        except Exception:
            pass
        if prj is not None and not _same_crs(receiver_layer, prj):
            errors.append("La capa de receptores no está en el mismo CRS que el proyecto.")

    if config.dem_layer is not None:
        if not isinstance(config.dem_layer, QgsRasterLayer):
            warnings.append("El MDT/DSM seleccionado no es raster válido y se ignorará.")
        elif prj is not None and not _same_crs(config.dem_layer, prj):
            errors.append("El MDT/DSM no está en el mismo CRS que el proyecto.")

    if config.landuse_layer is not None:
        if not isinstance(config.landuse_layer, QgsVectorLayer):
            warnings.append("La capa de suelo no es vectorial válida y se ignorará.")
        else:
            try:
                if QgsWkbTypes is not None and QgsWkbTypes.geometryType(config.landuse_layer.wkbType()) != QgsWkbTypes.PolygonGeometry:
                    errors.append("La capa de uso del suelo debe ser poligonal.")
            except Exception:
                pass
            if prj is not None and not _same_crs(config.landuse_layer, prj):
                errors.append("La capa de uso del suelo no está en el mismo CRS que el proyecto.")

    if not is_finite_positive(config.max_radius_m):
        errors.append("El radio máximo debe ser mayor que 0.")
    if not is_finite_positive(config.grid_resolution_m):
        errors.append("La resolución del raster debe ser mayor que 0.")
    if not is_finite_positive(config.min_distance_m):
        errors.append("La distancia mínima debe ser mayor que 0.")
    if not is_finite_positive(config.receiver_height_m, allow_zero=True):
        errors.append("La altura de receptor no es válida.")
    if not is_finite_positive(config.receiver_limit_dba, allow_zero=True):
        errors.append("El límite acústico no es válido.")
    if not is_finite_positive(config.alpha_db_per_m, allow_zero=True):
        errors.append("El coeficiente α no es válido.")
    if not (0.0 <= float(config.ground_factor_g) <= 1.0):
        errors.append("El factor de suelo G debe estar entre 0 y 1.")

    errors.extend(validate_model_config(config.model_cfg)[:12])
    return errors, warnings

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

from ..i18n import tr_text
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
        return [tr_text("No hay configuración acústica de modelos.")]

    seen_groups = set()
    for model_name, cfg in model_cfg.items():
        name = str(model_name or tr_text("Modelo sin nombre"))
        cfg = cfg or {}
        source_group = str(cfg.get("source_group_name") or name).strip()
        if not source_group:
            errors.append(tr_text("{name}: falta nombre de grupo fuente.").format(name=name))
        else:
            key = source_group.lower()
            if key in seen_groups:
                errors.append(tr_text("{name}: nombre de grupo fuente duplicado '{group}'.").format(name=name, group=source_group))
            seen_groups.add(key)

        mode = str(cfg.get("acoustic_mode") or "fixed").strip().lower()
        lwa = cfg.get("lwa")
        if lwa is None or not is_finite_positive(lwa):
            errors.append(tr_text("{name}: LwA fijo no válido.").format(name=name))

        if mode == "curve":
            curve_path = str(cfg.get("curve_path") or "").strip()
            if not curve_path:
                errors.append(tr_text("{name}: modo curva activo pero sin CSV de curva acústica.").format(name=name))
            elif not os.path.exists(curve_path):
                errors.append(tr_text("{name}: no existe la curva acústica '{path}'.").format(name=name, path=curve_path))

        hh = cfg.get("hub_height", 100.0)
        if not is_finite_positive(hh):
            errors.append(tr_text("{name}: altura de buje no válida.").format(name=name))
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
        errors.append(tr_text("Selecciona una capa válida de receptores."))
    else:
        try:
            if int(receiver_layer.featureCount()) <= 0:
                errors.append(tr_text("La capa de receptores '{layer}' está vacía.").format(layer=receiver_layer.name()))
        except Exception:  # nosec B110
            pass
        if prj is not None and not _same_crs(receiver_layer, prj):
            errors.append(tr_text("La capa de receptores no está en el mismo CRS que el proyecto."))

    # The turbine layers the calculation takes (the chosen ones, or all of them): one in another CRS would be left out
    # of it without a word. Energy's selector lets a row take a layer in any CRS.
    if prj is not None:
        try:
            from .qgis_io.common import _layer_crs_matches
            from .sources.collector import _iter_model_layers
            for lyr in _iter_model_layers(prj, source_layer_ids=list(config.source_layer_ids or [])):
                if not _layer_crs_matches(lyr, prj.crs()):
                    # Translated here: the name of the layer keeps the message from matching a translation later.
                    errors.append(tr_text("La capa de turbinas «{layer}» no está en el sistema de coordenadas del proyecto: reproyéctala.").format(layer=lyr.name()))
        except Exception:  # nosec B110
            pass

    if config.dem_layer is not None:
        if not isinstance(config.dem_layer, QgsRasterLayer):
            warnings.append("El MDT/DSM seleccionado no es un ráster válido y se ignorará.")
        elif prj is not None and not _same_crs(config.dem_layer, prj):
            errors.append(tr_text("El MDT/DSM no está en el mismo CRS que el proyecto."))

    if config.landuse_layer is not None:
        if not isinstance(config.landuse_layer, QgsVectorLayer):
            warnings.append("La capa de suelo no es vectorial válida y se ignorará.")
        else:
            try:
                if QgsWkbTypes is not None and QgsWkbTypes.geometryType(config.landuse_layer.wkbType()) != QgsWkbTypes.PolygonGeometry:
                    errors.append(tr_text("La capa de uso del suelo debe ser poligonal."))
            except Exception:  # nosec B110
                pass
            if prj is not None and not _same_crs(config.landuse_layer, prj):
                errors.append(tr_text("La capa de uso del suelo no está en el mismo CRS que el proyecto."))

    if not is_finite_positive(config.max_radius_m):
        errors.append(tr_text("El radio máximo debe ser mayor que 0."))
    if not is_finite_positive(config.grid_resolution_m):
        errors.append(tr_text("La resolución del ráster debe ser mayor que 0."))
    if not is_finite_positive(config.min_distance_m):
        errors.append(tr_text("La distancia mínima debe ser mayor que 0."))
    if not is_finite_positive(config.receiver_height_m, allow_zero=True):
        errors.append(tr_text("La altura de receptor no es válida."))
    if not is_finite_positive(config.receiver_limit_dba, allow_zero=True):
        errors.append(tr_text("El límite acústico no es válido."))
    if not is_finite_positive(config.alpha_db_per_m, allow_zero=True):
        errors.append(tr_text("El coeficiente α no es válido."))
    if not (0.0 <= float(config.ground_factor_g) <= 1.0):
        errors.append(tr_text("El factor de suelo G debe estar entre 0 y 1."))

    errors.extend(validate_model_config(config.model_cfg)[:12])
    return errors, warnings

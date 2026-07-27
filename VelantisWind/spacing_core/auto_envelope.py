# -*- coding: utf-8 -*-
"""Creación automática de envolventes al importar layouts CSV.

El helper funciona aunque el dock o el diálogo de spacing no estén abiertos.
Crea/reutiliza la capa vinculada y reconstruye conjuntamente todas las capas de
turbinas conocidas para que la validación multimodelo quede coherente desde la
propia importación.
"""
from __future__ import annotations

from typing import List, Optional

from qgis.PyQt import QtCore
from qgis.core import QgsProject, QgsVectorLayer, QgsWkbTypes

from .envelope_manager import (
    EnvelopeManager,
    MODEL_ANGLE_PROP,
    MODEL_LONG_D_PROP,
    MODEL_MODE_PROP,
    MODEL_TRANS_D_PROP,
)
from .geometry import MODE_AUTO, SHAPE_ELLIPTICAL, SpacingSpec
from .orientation import most_energetic_angle

_ORG = "VelantisWind"
_APP = "VelantisWindPlugin"
_TURBINE_ROLES = {"energy_turbines", "turbine_layout"}


def _settings_spec() -> SpacingSpec:
    settings = QtCore.QSettings(_ORG, _APP)
    try:
        long_d = float(settings.value("spacing/long_d", 7.0))
    except Exception:
        long_d = 7.0
    try:
        trans_d = float(settings.value("spacing/trans_d", 4.0))
    except Exception:
        trans_d = 4.0
    try:
        angle = float(settings.value("spacing/angle_deg", 0.0))
    except Exception:
        angle = 0.0
    mode = str(settings.value("spacing/mode", MODE_AUTO) or MODE_AUTO)
    return SpacingSpec(long_d, trans_d, angle, mode, SHAPE_ELLIPTICAL)


def _ensure_properties(layer: QgsVectorLayer, defaults: SpacingSpec) -> None:
    try:
        if layer.customProperty(MODEL_LONG_D_PROP, None) in (None, ""):
            layer.setCustomProperty(MODEL_LONG_D_PROP, float(defaults.long_d))
        if layer.customProperty(MODEL_TRANS_D_PROP, None) in (None, ""):
            layer.setCustomProperty(MODEL_TRANS_D_PROP, float(defaults.trans_d))
        if not str(layer.customProperty(MODEL_MODE_PROP, "") or "").strip():
            layer.setCustomProperty(MODEL_MODE_PROP, str(defaults.mode))
        if layer.customProperty(MODEL_ANGLE_PROP, None) in (None, ""):
            layer.setCustomProperty(MODEL_ANGLE_PROP, float(defaults.angle_deg))
    except Exception:
        pass


def _project_turbine_layers(primary: QgsVectorLayer) -> List[QgsVectorLayer]:
    layers: List[QgsVectorLayer] = []
    seen = set()
    try:
        candidates = list(QgsProject.instance().mapLayers().values())
    except Exception:
        candidates = []
    candidates.insert(0, primary)
    for candidate in candidates:
        if not isinstance(candidate, QgsVectorLayer):
            continue
        try:
            if not candidate.isValid() or candidate.geometryType() != QgsWkbTypes.PointGeometry:
                continue
            role = str(candidate.customProperty("velantis/layer_role", "") or "")
            # La capa primaria se acepta aunque proceda de una integración
            # antigua que aún no haya fijado el rol.
            if candidate is not primary and role not in _TURBINE_ROLES:
                continue
            layer_id = candidate.id()
        except Exception:
            continue
        if layer_id in seen:
            continue
        seen.add(layer_id)
        layers.append(candidate)
    return layers


def ensure_spacing_envelope_for_layer(
    layer: QgsVectorLayer,
    *,
    auto_angle_deg: Optional[float] = None,
    wrg_path: Optional[str] = None,
) -> Optional[QgsVectorLayer]:
    """Crea/actualiza la envolvente de un CSV y las del resto de modelos.

    Si se facilita un WRG y no se ha pasado un ángulo explícito, intenta usar
    directamente su sector más energético; en caso contrario conserva el
    ángulo de respaldo de cada modelo hasta que el controlador se refresque.
    """
    if not isinstance(layer, QgsVectorLayer) or not layer.isValid():
        return None
    defaults = _settings_spec()
    sources = _project_turbine_layers(layer)
    for source in sources:
        _ensure_properties(source, defaults)
    try:
        settings = QtCore.QSettings(_ORG, _APP)
        settings.setValue("spacing/enabled", True)
        settings.setValue("spacing/shape", SHAPE_ELLIPTICAL)
    except Exception:
        pass
    if auto_angle_deg is None and wrg_path:
        try:
            auto_angle_deg = most_energetic_angle(str(wrg_path))
        except Exception:
            auto_angle_deg = None
    manager = EnvelopeManager()
    manager.rebuild_many(sources, defaults, auto_angle_deg, fallback_diameter_m=120.0)
    return manager.envelope_layer(layer)


__all__ = ["ensure_spacing_envelope_for_layer"]

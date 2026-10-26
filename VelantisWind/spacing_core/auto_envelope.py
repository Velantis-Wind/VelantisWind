# -*- coding: utf-8 -*-
"""Creación automática de envolventes al importar layouts CSV.

El helper funciona aunque el dock o el diálogo de spacing no estén abiertos.
Crea/reutiliza la capa vinculada y la reconstruye junto con las capas del parque
que le pasa quien lo llama: las de las filas de Energía, o solo la capa
importada desde Ruido o Sombras. Nunca reúne otras capas del proyecto (#96).
"""
from __future__ import annotations

from typing import List, Optional

from qgis.PyQt import QtCore
from qgis.core import QgsVectorLayer

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
    except Exception:  # nosec B110
        pass


def ensure_spacing_envelope_for_layer(
    layer: QgsVectorLayer,
    *,
    park_layers: Optional[List[QgsVectorLayer]] = None,
    auto_angle_deg: Optional[float] = None,
    wrg_path: Optional[str] = None,
    existing_only: bool = False,
) -> Optional[QgsVectorLayer]:
    """Crea/actualiza la envolvente de la capa de turbinas recibida y las de ``park_layers``.

    ``park_layers`` son las capas del parque con las que se compara (las de las
    filas de Energía); sin ellas, solo ``layer``.
    Si se facilita un WRG y no se ha pasado un ángulo explícito, intenta usar
    directamente su sector más energético; en caso contrario conserva el
    ángulo de respaldo de cada modelo hasta que el controlador se refresque.
    Con ``existing_only`` solo rehace las envolventes que ya existen, frente a
    todas las capas del parque, y no toca las preferencias de separaciones.
    """
    if not isinstance(layer, QgsVectorLayer) or not layer.isValid():
        return None
    defaults = _settings_spec()
    sources = [layer] + [source for source in park_layers or [] if source.id() != layer.id()]
    manager = EnvelopeManager()
    for source in sources:
        # Con ``existing_only``, una capa del parque sin envolvente cuenta en los conflictos, pero no se toca.
        if not existing_only or manager._find_existing_layer(source) is not None:
            _ensure_properties(source, defaults)
    if not existing_only:
        try:
            settings = QtCore.QSettings(_ORG, _APP)
            settings.setValue("spacing/enabled", True)
            settings.setValue("spacing/shape", SHAPE_ELLIPTICAL)
        except Exception:  # nosec B110
            pass
    if auto_angle_deg is None and wrg_path:
        try:
            auto_angle_deg = most_energetic_angle(str(wrg_path))
        except Exception:
            auto_angle_deg = None
    manager.rebuild_many(sources, defaults, auto_angle_deg, fallback_diameter_m=120.0, create_missing=not existing_only)
    return manager.envelope_layer(layer)


def has_spacing_envelope(layer: QgsVectorLayer) -> bool:
    """Si la capa de turbinas tiene envolvente, por su asociación o por la de la envolvente (también guardada en fichero)."""
    return EnvelopeManager()._find_existing_layer(layer) is not None


def drop_spacing_envelope_for_layer(layer: QgsVectorLayer, manager: Optional[EnvelopeManager] = None) -> None:
    """Retira la envolvente temporal de una capa que ha salido de las filas, aunque la creara otro gestor (#96).

    Una guardada en fichero se conserva. ``manager`` es el gestor vivo que puede conocerla (el del controlador de
    separaciones): la retira él, para que no guarde una referencia a una capa borrada.
    """
    (manager or EnvelopeManager())._drop_envelope(layer)


__all__ = ["drop_spacing_envelope_for_layer", "ensure_spacing_envelope_for_layer", "has_spacing_envelope"]

# -*- coding: utf-8 -*-
"""Small, QGIS-only CRS helpers for preserving user-defined and WKT2 CRS."""
from __future__ import annotations

from qgis.core import QgsCoordinateReferenceSystem, QgsVectorLayer

from .i18n import tr_text
from .crs_translations import register_crs_translations

register_crs_translations()


def portable_crs_definition(crs: QgsCoordinateReferenceSystem) -> str:
    """Return an EPSG authority id or portable WKT2; never persist a local USER id."""
    if crs is None or not crs.isValid():
        return ""
    authid = str(crs.authid() or "")
    if authid and not authid.upper().startswith("USER:"):
        return authid
    return str(crs.toWkt(QgsCoordinateReferenceSystem.WKT_PREFERRED) or "")


def preferred_wkt(crs: QgsCoordinateReferenceSystem) -> str:
    """Keep WKT2 constructs (DERIVEDPROJCRS, etc.) that WKT1 cannot represent."""
    if crs is None or not crs.isValid():
        return ""
    return str(crs.toWkt(QgsCoordinateReferenceSystem.WKT_PREFERRED) or "")


def memory_layer_with_crs(geometry: str, name: str, crs: QgsCoordinateReferenceSystem) -> QgsVectorLayer:
    """Set the CRS object directly: memory provider URI authority ids lose custom CRS."""
    if crs is None or not crs.isValid():
        raise ValueError(tr_text(
            "No se puede crear una capa georreferenciada sin un CRS válido: {name}"
        ).format(name=name))
    layer = QgsVectorLayer(geometry, name, "memory")
    if not layer.isValid():
        raise RuntimeError(tr_text("No se pudo crear la capa en memoria de QGIS: {name}").format(name=name))
    layer.setCrs(crs)
    return layer

# -*- coding: utf-8 -*-
"""Simplified source-receiver propagation and ground-effect helpers."""
from __future__ import annotations

import math
from typing import Optional, Tuple

from qgis.core import QgsFeatureRequest, QgsGeometry, QgsPointXY, QgsRectangle, QgsVectorLayer, QgsWkbTypes

from ..noise_common import NoiseSource, NoiseReceiver

def _bbox_from_point(x: float, y: float, radius: float):
    return QgsRectangle(x - radius, y - radius, x + radius, y + radius)



def _ground_g_from_attributes(feat, default_g: float) -> float:
    candidates = ['g_factor', 'g', 'ground_g', 'g_value', 'G']
    for name in candidates:
        try:
            v = feat[name]
            if v is not None and str(v) != '':
                gv = float(v)
                if math.isfinite(gv):
                    return max(0.0, min(1.0, gv))
        except Exception:
            pass
    txt_names = ['uso_suelo', 'uso', 'clase', 'landuse', 'cover', 'type']
    txt = ''
    for name in txt_names:
        try:
            v = feat[name]
            if v is not None and str(v).strip():
                txt = str(v).strip().lower()
                break
        except Exception:
            pass
    if txt:
        if any(k in txt for k in ['urb', 'asfalt', 'roca', 'duro', 'edif', 'industrial']):
            return 0.0
        if any(k in txt for k in ['mixto', 'mosaico', 'semi']):
            return 0.5
        if any(k in txt for k in ['cult', 'agr', 'prado', 'past', 'forest', 'veg', 'poroso', 'suelo']):
            return 1.0
    return max(0.0, min(1.0, float(default_g)))


def _effective_ground_g(src: NoiseSource, rec: NoiseReceiver, landuse_layer: Optional[QgsVectorLayer], default_g: float) -> float:
    g0 = max(0.0, min(1.0, float(default_g)))
    if landuse_layer is None or not isinstance(landuse_layer, QgsVectorLayer):
        return g0
    try:
        if QgsWkbTypes.geometryType(landuse_layer.wkbType()) != QgsWkbTypes.PolygonGeometry:
            return g0
        line = QgsGeometry.fromPolylineXY([QgsPointXY(float(src.x), float(src.y)), QgsPointXY(float(rec.x), float(rec.y))])
        if line is None or line.isEmpty():
            return g0
        bbox = line.boundingBox()
        total_len = float(line.length())
        if total_len <= 0:
            return g0
        weighted = 0.0
        used = 0.0
        for feat in landuse_layer.getFeatures(QgsFeatureRequest().setFilterRect(bbox)):
            try:
                geom = feat.geometry()
                if geom is None or geom.isEmpty():
                    continue
                if not geom.intersects(line):
                    continue
                inter = geom.intersection(line)
                ilen = float(inter.length()) if inter and not inter.isEmpty() else 0.0
                if ilen <= 0:
                    continue
                gv = _ground_g_from_attributes(feat, g0)
                weighted += gv * ilen
                used += ilen
            except Exception:
                continue
        if used > 0:
            return max(0.0, min(1.0, weighted / used))
        # fallback: midpoint inside polygon
        mid = QgsGeometry.fromPointXY(QgsPointXY((float(src.x)+float(rec.x))/2.0, (float(src.y)+float(rec.y))/2.0))
        for feat in landuse_layer.getFeatures(QgsFeatureRequest().setFilterRect(bbox)):
            try:
                geom = feat.geometry()
                if geom and geom.contains(mid):
                    return _ground_g_from_attributes(feat, g0)
            except Exception:
                continue
    except Exception:
        return g0
    return g0

def _lp_from_source(
    src: NoiseSource,
    rec: NoiseReceiver,
    alpha_db_per_m: float,
    ground_factor_g: float,
    min_distance_m: float,
    landuse_layer: Optional[QgsVectorLayer] = None,
) -> Optional[Tuple[float, float, float, float, float, float, float]]:
    dx = src.x - rec.x
    dy = src.y - rec.y
    dist_xy = math.hypot(dx, dy)
    if dist_xy <= 0.0:
        dist_xy = min_distance_m
    z_src = (src.z_ground or 0.0) + float(src.hub_height)
    z_rec = (rec.z_ground or 0.0) + float(rec.receiver_height)
    dz = z_src - z_rec
    dist_3d = math.sqrt(max(min_distance_m ** 2, dist_xy * dist_xy + dz * dz))
    # Adiv ISO 9613-2: divergencia geométrica esférica (4π, fuente en aire libre).
    # El efecto del suelo se captura por separado en `aground`, no aquí.
    # Antes (v0.1.0 y anteriores): 10*log10(2*pi*d^2) ≈ 20*log10(d) + 8
    # (hemisferio 2π). Sobreestimaba en ~3 dB y no coincidía con el motor fast
    # de receptores (noise_engine_fast.calculate_adiv).
    adiv = 20.0 * math.log10(max(dist_3d, 1.0)) + 11.0
    aatm = float(alpha_db_per_m) * dist_3d
    # V2.3.1: término simplificado de efecto suelo/terreno para consultoría eólica.
    # G=0 suelo duro; G=1 suelo poroso. El efecto aumenta con la distancia y se reduce
    # con alturas fuente/receptor grandes (turbinas altas tienen menor interacción con suelo).
    g = _effective_ground_g(src, rec, landuse_layer, float(ground_factor_g))
    base = 3.0 * math.log10(1.0 + max(dist_xy, 1.0) / 100.0)
    height_factor = 1.0 / (1.0 + ((float(src.hub_height) + float(rec.receiver_height)) / 80.0))
    aground = max(0.0, min(6.0, g * base * height_factor))
    lp = float(src.lwa) - adiv - aatm - aground
    return lp, dist_xy, dist_3d, adiv, aatm, aground, g

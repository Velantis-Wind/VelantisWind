# -*- coding: utf-8 -*-
"""spacing_core/geometry.py — Geometría de la envolvente de separación.

Convenciones
------------
- El ángulo de orientación es un AZIMUT: grados desde el Norte, en sentido
  horario (convención GIS/meteorológica). El eje mayor de la elipse es
  bidireccional, por lo que ``angle`` y ``angle + 180`` producen la misma
  envolvente.
- Las separaciones se expresan en múltiplos del diámetro de rotor ``D`` y se
  interpretan como DISTANCIA MÍNIMA ENTRE CENTROS. Por eso cada envolvente
  individual usa semiejes = separación/2: si dos centros están más cerca del
  umbral, sus envolventes se solapan.

Este módulo no toca la UI ni el proyecto: sólo geometría y evaluación.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, asdict
from typing import Dict, Iterable, List, Optional, Tuple

from qgis.core import QgsGeometry, QgsPointXY, QgsSpatialIndex, QgsFeature

# Modos de definición de la envolvente
MODE_AUTO = "auto_energy"        # sector más energético (WRG)
MODE_MANUAL_ANGLE = "manual_angle"    # ángulo numérico introducido en el panel
MODE_MANUAL_SCREEN = "manual_screen"  # definida interactivamente en pantalla

# Tipo de envolvente. SHAPE_CIRCULAR se conserva únicamente para leer
# proyectos antiguos; toda especificación se migra a elipse al cargarla.
SHAPE_ELLIPTICAL = "elliptical"
SHAPE_CIRCULAR = "circular"

# Estados de validación
STATUS_OK = "ok"
STATUS_NEAR = "near"
STATUS_CONFLICT = "conflict"

# Margen relativo para el estado "cerca del límite" (10 % del umbral)
NEAR_MARGIN = 0.10

# Nº de vértices del polígono que aproxima la elipse
ELLIPSE_VERTICES = 64


@dataclass
class SpacingSpec:
    """Parámetros de una envolvente de separación.

    ``long_d`` / ``trans_d``: separación longitudinal/transversal en
    múltiplos de D (distancia mínima entre centros).
    ``angle_deg``: azimut del eje mayor (0 = Norte, horario).
    ``mode``: uno de MODE_AUTO / MODE_MANUAL_ANGLE / MODE_MANUAL_SCREEN.
    """

    long_d: float = 7.0
    trans_d: float = 4.0
    angle_deg: float = 0.0
    mode: str = MODE_AUTO
    shape: str = SHAPE_ELLIPTICAL

    def to_dict(self) -> Dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: Optional[Dict]) -> "SpacingSpec":
        if not isinstance(d, dict):
            return cls()
        out = cls()
        try:
            out.long_d = max(0.1, float(d.get("long_d", out.long_d)))
        except Exception:
            pass
        try:
            out.trans_d = max(0.1, float(d.get("trans_d", out.trans_d)))
        except Exception:
            pass
        try:
            out.angle_deg = normalize_azimuth(float(d.get("angle_deg", out.angle_deg)))
        except Exception:
            pass
        mode = str(d.get("mode", out.mode) or out.mode)
        if mode in (MODE_AUTO, MODE_MANUAL_ANGLE, MODE_MANUAL_SCREEN):
            out.mode = mode
        # La interfaz y el motor trabajan exclusivamente con
        # elipses. Los valores ``circular`` de proyectos anteriores se aceptan
        # al leer el JSON, pero se migran de forma transparente.
        out.shape = SHAPE_ELLIPTICAL
        return out

    def semi_axes_m(self, diameter_m: float) -> Tuple[float, float]:
        """Semiejes elípticos (a, b) para un diámetro de rotor dado."""
        d = max(1.0, float(diameter_m))
        a = 0.5 * self.long_d * d
        b = 0.5 * self.trans_d * d
        # El semieje mayor siempre es el longitudinal; si el usuario invierte
        # los valores en pantalla, respetamos lo que dibujó.
        return a, b


def normalize_azimuth(angle_deg: float) -> float:
    """Normaliza un azimut a [0, 360)."""
    a = float(angle_deg) % 360.0
    return a if a >= 0.0 else a + 360.0


def azimuth_between(p0: QgsPointXY, p1: QgsPointXY) -> float:
    """Azimut (desde el Norte, horario) del vector p0 -> p1 en coords de mapa."""
    dx = float(p1.x()) - float(p0.x())
    dy = float(p1.y()) - float(p0.y())
    if abs(dx) < 1e-12 and abs(dy) < 1e-12:
        return 0.0
    return normalize_azimuth(math.degrees(math.atan2(dx, dy)))


def ellipse_polygon(
    cx: float,
    cy: float,
    a_m: float,
    b_m: float,
    angle_deg: float,
    n_vertices: int = ELLIPSE_VERTICES,
) -> QgsGeometry:
    """Construye la elipse como polígono aproximado.

    ``a_m`` es el semieje alineado con el azimut ``angle_deg`` (eje mayor,
    longitudinal); ``b_m`` el semieje perpendicular (transversal).
    """
    a = max(0.01, float(a_m))
    b = max(0.01, float(b_m))
    theta = math.radians(normalize_azimuth(angle_deg))
    # Vector unitario del eje mayor en coords de mapa (azimut: sin/cos)
    ux, uy = math.sin(theta), math.cos(theta)
    # Perpendicular (90° horario)
    vx, vy = math.cos(theta), -math.sin(theta)

    n = max(12, int(n_vertices))
    pts: List[QgsPointXY] = []
    for i in range(n):
        t = 2.0 * math.pi * i / n
        ca, sb = a * math.cos(t), b * math.sin(t)
        pts.append(QgsPointXY(cx + ca * ux + sb * vx, cy + ca * uy + sb * vy))
    pts.append(pts[0])
    return QgsGeometry.fromPolygonXY([pts])


def evaluate_conflicts(
    envelopes: Dict[int, QgsGeometry],
    near_margin: float = NEAR_MARGIN,
) -> Dict[int, str]:
    """Evalúa el estado de cada envolvente frente al resto.

    ``envelopes``: {fid_turbina: geometría de su elipse}.

    Estados:
      - STATUS_CONFLICT: la elipse intersecta (con área) otra envolvente,
        es decir, la separación entre centros incumple el umbral.
      - STATUS_NEAR: sin solape, pero la distancia libre entre envolventes es
        menor que ``near_margin`` veces el "radio" característico.
      - STATUS_OK: resto.

    Usa QgsSpatialIndex para no comparar cada turbina contra todas.
    """
    fids = list(envelopes.keys())
    status: Dict[int, str] = {fid: STATUS_OK for fid in fids}
    if len(fids) < 2:
        return status

    # Índice espacial sobre bounding boxes de las elipses
    index = QgsSpatialIndex()
    feats: Dict[int, QgsFeature] = {}
    for fid in fids:
        f = QgsFeature(int(fid))
        f.setGeometry(QgsGeometry(envelopes[fid]))
        feats[fid] = f
        try:
            index.addFeature(f)
        except Exception:
            # QGIS < 3.30 API antigua
            try:
                index.insertFeature(f)
            except Exception:
                pass

    # Radio característico por envolvente (semieje mayor aprox. desde bbox)
    char_r: Dict[int, float] = {}
    for fid in fids:
        bb = envelopes[fid].boundingBox()
        char_r[fid] = 0.5 * max(bb.width(), bb.height())

    eps_area = 1e-6
    for fid in fids:
        g = envelopes[fid]
        near_tol = near_margin * char_r.get(fid, 0.0)
        # Consultamos el índice con la bbox inflada por la tolerancia "near"
        rect = g.boundingBox()
        rect.grow(max(near_tol, 0.0))
        for other in index.intersects(rect):
            other = int(other)
            if other == int(fid):
                continue
            og = envelopes.get(other)
            if og is None:
                continue
            try:
                inter = g.intersection(og)
                if inter is not None and not inter.isEmpty() and inter.area() > eps_area:
                    status[fid] = STATUS_CONFLICT
                    break
                if status[fid] != STATUS_CONFLICT:
                    d = g.distance(og)
                    if 0.0 <= d < near_tol:
                        status[fid] = STATUS_NEAR
            except Exception:
                continue
    return status


def snap_angle(angle_deg: float, step: float = 5.0, magnets: Optional[Iterable[float]] = None,
               magnet_tol: float = 3.0) -> float:
    """Ajusta un azimut a incrementos de ``step`` y, opcionalmente, a una lista
    de ángulos "imán" (p. ej. centros de sectores de la rosa de vientos) si el
    ángulo cae a menos de ``magnet_tol`` grados de alguno de ellos.
    """
    a = normalize_azimuth(angle_deg)
    if magnets:
        for m in magnets:
            m = normalize_azimuth(m)
            diff = abs((a - m + 180.0) % 360.0 - 180.0)
            if diff <= magnet_tol:
                return m
    if step and step > 0:
        return normalize_azimuth(round(a / step) * step)
    return a


def snap_length(value_m: float, diameter_m: float, step_d: float = 0.5) -> float:
    """Ajusta una longitud en metros a múltiplos de ``step_d`` · D."""
    d = max(1.0, float(diameter_m))
    step = max(0.01, float(step_d)) * d
    return max(step, round(float(value_m) / step) * step)

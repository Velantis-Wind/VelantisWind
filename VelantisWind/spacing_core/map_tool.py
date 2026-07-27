# -*- coding: utf-8 -*-
"""spacing_core/map_tool.py — Definición de la elipse en pantalla.

Herramienta de mapa (QgsMapTool) para definir las CARACTERÍSTICAS COMPLETAS
de la envolvente de una turbina directamente sobre el canvas, en tres clics
con preview continua:

  1) Clic sobre una turbina existente  -> se ancla el centro (snap a la
     turbina más cercana dentro de la tolerancia).
  2) Mover el ratón                    -> el cursor arrastra el SEMIEJE MAYOR:
     orientación (azimut) y separación longitudinal a la vez.
     Clic para confirmar eje mayor + ángulo.
  3) Mover el ratón                    -> el cursor controla el SEMIEJE MENOR
     (distancia perpendicular al eje mayor).
     Clic para confirmar. Se emite el resultado.

Modificadores durante el arrastre:
  - Ctrl : snap angular a incrementos de 5° y a los centros de sector del
           WRG si hay recurso cargado (imán a ±3°).
  - Shift: snap dimensional a múltiplos de 0.5·D.
  - Esc / clic derecho: vuelve al paso anterior; desde el paso 1, cancela.

La herramienta NO escribe en capas: entrega el resultado por callback
(``on_defined(fid, spec)``) y publica texto de estado en vivo por
``on_status(text)`` (ángulo, separaciones en D y en metros).
"""

from __future__ import annotations

import math
from typing import Callable, List, Optional

from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtGui import QColor
from qgis.core import QgsGeometry, QgsPointXY, QgsVectorLayer, QgsWkbTypes
from qgis.gui import QgsMapTool, QgsRubberBand, QgsVertexMarker

from .geometry import (
    MODE_MANUAL_SCREEN,
    SpacingSpec,
    azimuth_between,
    ellipse_polygon,
    normalize_azimuth,
    snap_angle,
    snap_length,
)

# Estados de la máquina
_ST_CENTER = 0   # esperando clic sobre una turbina
_ST_MAJOR = 1    # arrastrando eje mayor (ángulo + longitudinal)
_ST_MINOR = 2    # arrastrando eje menor (transversal)


class EllipseDefineTool(QgsMapTool):
    """Define en pantalla la envolvente de una turbina existente."""

    def __init__(
        self,
        canvas,
        turbine_layer: QgsVectorLayer,
        diameter_m: float,
        defaults: SpacingSpec,
        on_defined: Callable[[int, SpacingSpec], None],
        on_status: Optional[Callable[[str], None]] = None,
        on_cancelled: Optional[Callable[[], None]] = None,
        sector_magnets_deg: Optional[List[float]] = None,
        pick_tol_m: float = 120.0,
    ):
        super().__init__(canvas)
        self.canvas = canvas
        self.layer = turbine_layer
        self.diameter_m = max(1.0, float(diameter_m))
        self.defaults = defaults
        self.on_defined = on_defined
        self.on_status = on_status or (lambda _t: None)
        self.on_cancelled = on_cancelled or (lambda: None)
        self.magnets = list(sector_magnets_deg or [])
        self.pick_tol_m = float(pick_tol_m)

        self.setCursor(Qt.CrossCursor)

        self._state = _ST_CENTER
        self._fid: Optional[int] = None
        self._center: Optional[QgsPointXY] = None  # coords de MAPA
        self._angle_deg: float = normalize_azimuth(defaults.angle_deg)
        self._a_m: float = 0.5 * defaults.long_d * self.diameter_m
        self._b_m: float = 0.5 * defaults.trans_d * self.diameter_m

        # Preview: elipse + eje mayor + marcador central
        self._rb_ellipse = QgsRubberBand(canvas, QgsWkbTypes.PolygonGeometry)
        self._rb_ellipse.setColor(QColor(42, 168, 168, 70))
        self._rb_ellipse.setStrokeColor(QColor(31, 127, 127, 220))
        self._rb_ellipse.setWidth(2)

        self._rb_axis = QgsRubberBand(canvas, QgsWkbTypes.LineGeometry)
        self._rb_axis.setColor(QColor(31, 127, 127, 200))
        self._rb_axis.setWidth(2)
        try:
            self._rb_axis.setLineStyle(Qt.DashLine)
        except Exception:
            pass

        self._marker = QgsVertexMarker(canvas)
        self._marker.setIconType(QgsVertexMarker.ICON_CIRCLE)
        self._marker.setColor(QColor(20, 90, 90))
        self._marker.setFillColor(QColor(42, 168, 168))
        self._marker.setIconSize(12)
        self._marker.setPenWidth(2)
        self._marker.hide()

        self._push_status()

    # ------------------------------------------------------------- helpers
    def _to_layer_point(self, map_point: QgsPointXY) -> QgsPointXY:
        try:
            return self.toLayerCoordinates(self.layer, map_point)
        except Exception:
            return map_point

    def _to_map_point(self, layer_point: QgsPointXY) -> QgsPointXY:
        try:
            return self.toMapCoordinates(self.layer, layer_point)
        except Exception:
            return layer_point

    def _nearest_turbine(self, map_point: QgsPointXY):
        """(fid, punto_capa) de la turbina más cercana dentro de tolerancia."""
        lp = self._to_layer_point(map_point)
        best = None
        best_d2 = None
        for f in self.layer.getFeatures():
            try:
                p = f.geometry().asPoint()
            except Exception:
                continue
            d2 = (lp.x() - p.x()) ** 2 + (lp.y() - p.y()) ** 2
            if best_d2 is None or d2 < best_d2:
                best_d2 = d2
                best = (int(f.id()), QgsPointXY(p))
        if best is None or best_d2 is None:
            return None
        if math.sqrt(best_d2) > self.pick_tol_m:
            return None
        return best

    def _fmt_d(self, meters: float) -> str:
        return f"{meters / self.diameter_m * 2.0:.1f} D ({meters * 2.0:,.0f} m)".replace(",", " ")

    def _push_status(self):
        try:
            if self._state == _ST_CENTER:
                self.on_status("Clic sobre una turbina para definir su envolvente · Esc cancela")
            elif self._state == _ST_MAJOR:
                self.on_status(
                    f"Eje mayor · Ángulo: {self._angle_deg:.1f}° · "
                    f"Long: {self._fmt_d(self._a_m)} · Ctrl=snap 5°/sector, Shift=snap 0.5D"
                )
            else:
                self.on_status(
                    f"Eje menor · Ángulo: {self._angle_deg:.1f}° · "
                    f"Long: {self._fmt_d(self._a_m)} · Trans: {self._fmt_d(self._b_m)} · "
                    f"Clic para confirmar"
                )
        except Exception:
            pass

    def _redraw(self):
        if self._center is None:
            return
        c = self._center
        try:
            geom = ellipse_polygon(c.x(), c.y(), self._a_m, self._b_m, self._angle_deg)
            self._rb_ellipse.setToGeometry(geom, None)
        except Exception:
            pass
        try:
            th = math.radians(self._angle_deg)
            ux, uy = math.sin(th), math.cos(th)
            p0 = QgsPointXY(c.x() - self._a_m * ux, c.y() - self._a_m * uy)
            p1 = QgsPointXY(c.x() + self._a_m * ux, c.y() + self._a_m * uy)
            self._rb_axis.setToGeometry(QgsGeometry.fromPolylineXY([p0, p1]), None)
        except Exception:
            pass

    def _reset_preview(self):
        try:
            self._rb_ellipse.reset(QgsWkbTypes.PolygonGeometry)
            self._rb_axis.reset(QgsWkbTypes.LineGeometry)
            self._marker.hide()
        except Exception:
            pass

    # ------------------------------------------------------------- eventos
    def canvasMoveEvent(self, e):
        if self._center is None:
            return
        mp = e.mapPoint()
        mods = e.modifiers() if hasattr(e, "modifiers") else Qt.KeyboardModifiers()
        ctrl = bool(mods & Qt.ControlModifier)
        shift = bool(mods & Qt.ShiftModifier)

        if self._state == _ST_MAJOR:
            ang = azimuth_between(self._center, mp)
            dist = math.hypot(mp.x() - self._center.x(), mp.y() - self._center.y())
            if ctrl:
                ang = snap_angle(ang, 5.0, self.magnets)
            if shift:
                dist = snap_length(dist, self.diameter_m, 0.5)
            self._angle_deg = normalize_azimuth(ang)
            self._a_m = max(0.05 * self.diameter_m, dist)
            # b provisional conserva la proporción por defecto
            ratio = self.defaults.trans_d / max(0.1, self.defaults.long_d)
            self._b_m = max(0.05 * self.diameter_m, self._a_m * ratio)
        elif self._state == _ST_MINOR:
            # distancia perpendicular al eje mayor
            th = math.radians(self._angle_deg)
            ux, uy = math.sin(th), math.cos(th)
            dx, dy = mp.x() - self._center.x(), mp.y() - self._center.y()
            perp = abs(dx * uy - dy * ux)  # componente perpendicular
            if shift:
                perp = snap_length(perp, self.diameter_m, 0.5)
            self._b_m = max(0.05 * self.diameter_m, perp)
        else:
            return
        self._redraw()
        self._push_status()

    def canvasPressEvent(self, e):
        if e.button() == Qt.RightButton:
            self._step_back()
            return
        if e.button() != Qt.LeftButton:
            return

        if self._state == _ST_CENTER:
            hit = self._nearest_turbine(e.mapPoint())
            if hit is None:
                self.on_status("No hay turbina cerca del clic · pincha sobre un aerogenerador")
                return
            self._fid, layer_pt = hit
            self._center = self._to_map_point(layer_pt)
            try:
                self._marker.setCenter(self._center)
                self._marker.show()
            except Exception:
                pass
            self._state = _ST_MAJOR
            self._redraw()
            self._push_status()
        elif self._state == _ST_MAJOR:
            self._state = _ST_MINOR
            self._push_status()
        elif self._state == _ST_MINOR:
            self._finish()

    def keyPressEvent(self, e):
        try:
            if e.key() == Qt.Key_Escape:
                self._step_back()
                return
        except Exception:
            pass
        try:
            super().keyPressEvent(e)
        except Exception:
            pass

    # ------------------------------------------------------------- flujo
    def _step_back(self):
        if self._state == _ST_MINOR:
            self._state = _ST_MAJOR
            self._push_status()
        elif self._state == _ST_MAJOR:
            self._state = _ST_CENTER
            self._fid = None
            self._center = None
            self._reset_preview()
            self._push_status()
        else:
            self.cancel()

    def _finish(self):
        fid = self._fid
        if fid is None or self._center is None:
            self.cancel()
            return
        # metros -> múltiplos de D (separación total entre centros = 2·semieje)
        long_d = 2.0 * self._a_m / self.diameter_m
        trans_d = 2.0 * self._b_m / self.diameter_m
        spec = SpacingSpec(
            long_d=round(long_d, 2),
            trans_d=round(trans_d, 2),
            angle_deg=round(self._angle_deg, 1),
            mode=MODE_MANUAL_SCREEN,
        )
        self._reset_preview()
        self._state = _ST_CENTER
        self._fid = None
        self._center = None
        try:
            self.on_defined(int(fid), spec)
        except Exception:
            pass
        self._push_status()

    def cancel(self):
        self._reset_preview()
        self._state = _ST_CENTER
        self._fid = None
        self._center = None
        try:
            self.on_cancelled()
        except Exception:
            pass

    def deactivate(self):
        self._reset_preview()
        try:
            scene = self.canvas.scene()
            for item in (self._rb_ellipse, self._rb_axis, self._marker):
                try:
                    scene.removeItem(item)
                except Exception:
                    pass
        except Exception:
            pass
        try:
            super().deactivate()
        except Exception:
            pass

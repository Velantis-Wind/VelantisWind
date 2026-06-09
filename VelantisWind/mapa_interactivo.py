# -*- coding: utf-8 -*-
"""VelantisWind/mapa_interactivo.py

Herramienta de mapa interactiva para editar (añadir/borrar) turbinas sobre
una capa de puntos.

- Click izquierdo: añade turbina (con snap a 50 m delegando en el diálogo).
- Click derecho: elimina la turbina más cercana dentro de una tolerancia.

La herramienta espera que el controlador (ctl) exponga:
  - _get_interactive_target_layer() -> QgsVectorLayer | None
  - _snap50(x: float) -> float
  - _mark_turbines_layer_dirty(layer)
  - _exit_map_interactive_via_esc()
"""

from qgis.gui import QgsMapTool
from qgis.core import QgsPointXY, QgsGeometry, QgsFeature, QgsVectorLayer, QgsWkbTypes
from qgis.utils import iface
from qgis.PyQt.QtCore import Qt


class _TurbineInteractiveTool(QgsMapTool):
    """Click izq = añadir turbina | Click der = borrar turbina cercana"""

    def __init__(self, ctl, canvas, tol_m=120.0):
        super().__init__(canvas)
        self.ctl = ctl              # AEPSetupDialog
        self.canvas = canvas
        self.tol_m = float(tol_m)
        self.setCursor(Qt.CrossCursor)

    # ---------------- mouse ----------------
    def canvasPressEvent(self, e):
        if e.button() == Qt.LeftButton:
            self._handle_add(e)
        elif e.button() == Qt.RightButton:
            self._handle_remove(e)

    def keyPressEvent(self, e):
        """ESC: salir del modo interactivo (delegado en el diálogo)."""
        try:
            if e.key() == Qt.Key_Escape:
                self.ctl._exit_map_interactive_via_esc()
                return
        except Exception:
            pass

        try:
            super().keyPressEvent(e)
        except Exception:
            pass

    # ---------------- helpers ----------------
    def _get_layer(self) -> QgsVectorLayer:
        lyr = None
        try:
            lyr = self.ctl._get_interactive_target_layer()
        except Exception:
            lyr = None

        if lyr is None:
            raise RuntimeError("No hay una capa de turbinas válida activa para el mapa interactivo.")
        if not isinstance(lyr, QgsVectorLayer):
            raise RuntimeError("La capa activa no es vectorial.")
        if QgsWkbTypes.geometryType(lyr.wkbType()) != QgsWkbTypes.PointGeometry:
            raise RuntimeError("La capa activa no es de puntos.")
        return lyr

    def _to_layer_xy(self, layer, map_point):
        try:
            p = self.toLayerCoordinates(layer, map_point)
        except Exception:
            p = map_point
        return float(p.x()), float(p.y())

    def _nearest_feature(self, layer: QgsVectorLayer, map_point):
        px, py = self._to_layer_xy(layer, map_point)
        best_id = None
        best_d2 = None

        for f in layer.getFeatures():
            try:
                p = f.geometry().asPoint()
            except Exception:
                continue
            d2 = (px - p.x()) ** 2 + (py - p.y()) ** 2
            if best_d2 is None or d2 < best_d2:
                best_d2 = d2
                best_id = f.id()

        if best_id is None or best_d2 is None:
            return None

        import math

        return best_id if math.sqrt(best_d2) <= self.tol_m else None

    def _exists_at(self, layer: QgsVectorLayer, x: float, y: float, eps: float = 1e-6) -> bool:
        for f in layer.getFeatures():
            try:
                p = f.geometry().asPoint()
            except Exception:
                continue
            if abs(p.x() - x) <= eps and abs(p.y() - y) <= eps:
                return True
        return False

    # ---------------- actions ----------------
    def _handle_add(self, e):
        try:
            layer = self._get_layer()
        except Exception as ex:
            try:
                iface.messageBar().pushWarning("Mapa interactivo", str(ex))
            except Exception:
                pass
            return

        mx = e.mapPoint()
        x, y = self._to_layer_xy(layer, mx)

        # Snap a 50 m usando el diálogo
        try:
            x = self.ctl._snap50(x)
            y = self.ctl._snap50(y)
        except Exception:
            pass

        if self._exists_at(layer, x, y):
            try:
                iface.messageBar().pushInfo("Mapa interactivo", "Ya existe una turbina en ese punto.")
            except Exception:
                pass
            return

        try:
            f = QgsFeature(layer.fields())
            f.setGeometry(QgsGeometry.fromPointXY(QgsPointXY(x, y)))
            # Para capas "memory" esto suele funcionar sin startEditing.
            layer.dataProvider().addFeatures([f])
            layer.updateExtents()
            layer.triggerRepaint()
        except Exception as ex:
            try:
                iface.messageBar().pushWarning("Mapa interactivo", f"No se pudo añadir turbina: {ex}")
            except Exception:
                pass
            return

        try:
            self.ctl._mark_turbines_layer_dirty(layer)
        except Exception:
            pass

    def _handle_remove(self, e):
        try:
            layer = self._get_layer()
        except Exception as ex:
            try:
                iface.messageBar().pushWarning("Mapa interactivo", str(ex))
            except Exception:
                pass
            return

        fid = self._nearest_feature(layer, e.mapPoint())
        if fid is None:
            try:
                iface.messageBar().pushInfo("Mapa interactivo", "No hay turbina cerca del clic.")
            except Exception:
                pass
            return

        try:
            layer.dataProvider().deleteFeatures([fid])
            layer.updateExtents()
            layer.triggerRepaint()
        except Exception as ex:
            try:
                iface.messageBar().pushWarning("Mapa interactivo", f"No se pudo borrar turbina: {ex}")
            except Exception:
                pass
            return

        try:
            self.ctl._mark_turbines_layer_dirty(layer)
        except Exception:
            pass

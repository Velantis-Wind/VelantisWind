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

try:
    from .i18n import tr_text
except Exception:  # pragma: no cover
    def tr_text(text):
        return text
try:
    from . import interactive_i18n
    interactive_i18n.register()
except Exception:
    pass


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
            raise RuntimeError(tr_text("No hay una capa de turbinas válida activa para el mapa interactivo."))
        if not isinstance(lyr, QgsVectorLayer):
            raise RuntimeError(tr_text("La capa activa no es vectorial."))
        if QgsWkbTypes.geometryType(lyr.wkbType()) != QgsWkbTypes.PointGeometry:
            raise RuntimeError(tr_text("La capa activa no es de puntos."))
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
                iface.messageBar().pushWarning(tr_text("Mapa interactivo"), str(ex))
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
                iface.messageBar().pushInfo(tr_text("Mapa interactivo"), tr_text("Ya existe una turbina en ese punto."))
            except Exception:
                pass
            return

        # Pre-chequeo opcional de spacing (spacing_core, validación "bloquear").
        # Si el módulo no está activo, el getattr devuelve None y no bloquea.
        try:
            check = getattr(self.ctl, "_spacing_check_candidate", None)
            if callable(check) and check(layer, x, y) is False:
                return
        except Exception:
            pass

        try:
            f = QgsFeature(layer.fields())
            f.setGeometry(QgsGeometry.fromPointXY(QgsPointXY(x, y)))
            # Para capas "memory" esto suele funcionar sin startEditing.
            layer.dataProvider().addFeatures([f])
            layer.updateExtents()
            layer.triggerRepaint()
        except Exception as ex:
            try:
                iface.messageBar().pushWarning(tr_text("Mapa interactivo"), f"{tr_text('No se pudo añadir turbina:')} {ex}")
            except Exception:
                pass
            return

        try:
            self.ctl._mark_turbines_layer_dirty(layer)
        except Exception:
            pass

        self._notify_spacing(layer)

    def _handle_remove(self, e):
        try:
            layer = self._get_layer()
        except Exception as ex:
            try:
                iface.messageBar().pushWarning(tr_text("Mapa interactivo"), str(ex))
            except Exception:
                pass
            return

        fid = self._nearest_feature(layer, e.mapPoint())
        if fid is None:
            try:
                iface.messageBar().pushInfo(tr_text("Mapa interactivo"), tr_text("No hay turbina cerca del clic."))
            except Exception:
                pass
            return

        try:
            layer.dataProvider().deleteFeatures([fid])
            layer.updateExtents()
            layer.triggerRepaint()
        except Exception as ex:
            try:
                iface.messageBar().pushWarning(tr_text("Mapa interactivo"), f"{tr_text('No se pudo borrar turbina:')} {ex}")
            except Exception:
                pass
            return

        try:
            self.ctl._mark_turbines_layer_dirty(layer)
        except Exception:
            pass

        self._notify_spacing(layer)

    def _notify_spacing(self, layer):
        """Hook opcional: refresca las envolventes de separación si el módulo
        spacing_core está activo (el dock publica el callback en el ctl).

        Mantiene mapa_interactivo desacoplado de spacing_core: si el módulo
        no está cargado, el getattr devuelve None y no pasa nada.
        """
        try:
            cb = getattr(self.ctl, "_spacing_notify_layout_changed", None)
            if callable(cb):
                cb(layer)
        except Exception:
            pass

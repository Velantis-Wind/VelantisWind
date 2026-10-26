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
from qgis.core import (
    QgsCoordinateTransform,
    QgsCsException,
    QgsFeature,
    QgsGeometry,
    QgsPointXY,
    QgsProject,
    QgsVectorDataProvider,
    QgsVectorLayer,
    QgsWkbTypes,
)
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
except Exception:  # nosec B110
    pass
try:
    from .wake_core.controller import is_projected_in_metres
except Exception:  # pragma: no cover
    from wake_core.controller import is_projected_in_metres  # type: ignore


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
        except Exception:  # nosec B110
            pass

        try:
            super().keyPressEvent(e)
        except Exception:  # nosec B110
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
        # Redondea a 50 y mide la distancia de borrado en unidades de la capa: tienen que ser metros.
        if not is_projected_in_metres(lyr.crs()):
            raise RuntimeError(tr_text("El mapa interactivo solo edita capas en un sistema de coordenadas proyectado y en metros."))
        return lyr

    def _to_layer_xy(self, layer, map_point):
        """El clic en el sistema de la capa; lanza RuntimeError si no se puede transformar."""
        try:
            transform = QgsCoordinateTransform(
                self.canvas.mapSettings().destinationCrs(), layer.crs(), QgsProject.instance().transformContext()
            )
            # Una transformación no válida (por ejemplo, el mapa sin sistema) devolvería el clic sin transformar.
            if not transform.isValid():
                raise QgsCsException(tr_text("el mapa o la capa no tienen un sistema de coordenadas válido"))
            p = transform.transform(QgsPointXY(map_point))
        except QgsCsException as exc:
            raise RuntimeError(tr_text("No se pudo pasar el clic al sistema de coordenadas de la capa: {error}").format(error=exc))
        return float(p.x()), float(p.y())

    def _can_edit(self, layer, capability, text) -> bool:
        # El mapa escribe directamente en la capa: no en una marcada como de solo lectura, ni en una con la edición
        # abierta, porque el cambio quedaría fuera de esa edición y descartarla o deshacer no lo quitaría.
        if layer.readOnly():
            self._warn(tr_text("La capa «{layer}» es de solo lectura.").format(layer=layer.name()))
            return False
        if layer.isEditable():
            self._warn(tr_text(
                "La capa «{layer}» está en modo edición: guarda o descarta sus cambios para editarla desde el mapa."
            ).format(layer=layer.name()))
            return False
        if layer.dataProvider().capabilities() & capability:
            return True
        self._warn(tr_text(text).format(layer=layer.name()))
        return False

    def _warn(self, text):
        try:
            iface.messageBar().pushWarning(tr_text("Mapa interactivo"), text)
        except Exception:  # nosec B110
            pass

    def _nearest_feature(self, layer: QgsVectorLayer, map_point):
        px, py = self._to_layer_xy(layer, map_point)
        best_id = None
        best_d2 = None

        for f in layer.getFeatures():
            try:
                p = f.geometry().asPoint()
            except Exception:  # nosec B112
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
            except Exception:  # nosec B112
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
            except Exception:  # nosec B110
                pass
            return

        if not self._can_edit(layer, QgsVectorDataProvider.AddFeatures, "La capa «{layer}» no admite añadir turbinas."):
            return
        try:
            x, y = self._to_layer_xy(layer, e.mapPoint())
        except RuntimeError as ex:
            self._warn(str(ex))
            return

        # Snap a 50 m usando el diálogo
        try:
            x = self.ctl._snap50(x)
            y = self.ctl._snap50(y)
        except Exception:  # nosec B110
            pass

        if self._exists_at(layer, x, y):
            try:
                iface.messageBar().pushInfo(tr_text("Mapa interactivo"), tr_text("Ya existe una turbina en ese punto."))
            except Exception:  # nosec B110
                pass
            return

        # Pre-chequeo opcional de spacing (spacing_core, validación "bloquear").
        # Si el módulo no está activo, el getattr devuelve None y no bloquea.
        try:
            check = getattr(self.ctl, "_spacing_check_candidate", None)
            if callable(check) and check(layer, x, y) is False:
                return
        except Exception:  # nosec B110
            pass

        try:
            f = QgsFeature(layer.fields())
            f.setGeometry(QgsGeometry.fromPointXY(QgsPointXY(x, y)))
            # Para capas "memory" esto suele funcionar sin startEditing.
            ok, _ = layer.dataProvider().addFeatures([f])
            if not ok:
                raise RuntimeError(tr_text("la capa no ha guardado el cambio."))
            layer.updateExtents()
            layer.triggerRepaint()
        except Exception as ex:
            try:
                iface.messageBar().pushWarning(tr_text("Mapa interactivo"), f"{tr_text('No se pudo añadir turbina:')} {ex}")
            except Exception:  # nosec B110
                pass
            return

        try:
            self.ctl._mark_turbines_layer_dirty(layer)
        except Exception:  # nosec B110
            pass

        self._notify_spacing(layer)

    def _handle_remove(self, e):
        try:
            layer = self._get_layer()
        except Exception as ex:
            try:
                iface.messageBar().pushWarning(tr_text("Mapa interactivo"), str(ex))
            except Exception:  # nosec B110
                pass
            return

        if not self._can_edit(layer, QgsVectorDataProvider.DeleteFeatures, "La capa «{layer}» no admite borrar turbinas."):
            return
        try:
            fid = self._nearest_feature(layer, e.mapPoint())
        except RuntimeError as ex:
            self._warn(str(ex))
            return
        if fid is None:
            try:
                iface.messageBar().pushInfo(tr_text("Mapa interactivo"), tr_text("No hay turbina cerca del clic."))
            except Exception:  # nosec B110
                pass
            return

        try:
            if not layer.dataProvider().deleteFeatures([fid]):
                raise RuntimeError(tr_text("la capa no ha guardado el cambio."))
            layer.updateExtents()
            layer.triggerRepaint()
        except Exception as ex:
            try:
                iface.messageBar().pushWarning(tr_text("Mapa interactivo"), f"{tr_text('No se pudo borrar turbina:')} {ex}")
            except Exception:  # nosec B110
                pass
            return

        try:
            self.ctl._mark_turbines_layer_dirty(layer)
        except Exception:  # nosec B110
            pass

        self._notify_spacing(layer)

    def _notify_spacing(self, layer):
        """Hook opcional: refresca las envolventes de separación si el módulo
        spacing_core está activo (el dock publica el callback en el ctl).

        Mantiene mapa_interactivo desacoplado de spacing_core: si el módulo
        no está cargado, el getattr devuelve None y no pasa nada. El diálogo de
        Energía pone al día también las envolventes que ya existen con las
        separaciones desactivadas, sin activarlas (#96).
        """
        try:
            sync = getattr(self.ctl, "_sync_spacing_envelopes", None)
            cb = sync if callable(sync) else getattr(self.ctl, "_spacing_notify_layout_changed", None)
            if callable(cb):
                cb(layer)
        except Exception:  # nosec B110
            pass

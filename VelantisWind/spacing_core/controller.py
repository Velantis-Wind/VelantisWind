# -*- coding: utf-8 -*-
"""spacing_core/controller.py — Pegamento del módulo de envolventes.

El controller mantiene una capa de envolventes independiente por cada capa de
turbinas elegida en las filas del diálogo de Energía: el parque que calculan el
AEP y el ráster (#96). El modelo seleccionado es el que se edita, pero el
refresco, la validación y la exportación abarcan todas las capas de las filas, y
ninguna otra capa del proyecto.
"""

from __future__ import annotations

from ..number_format import format_number
from typing import Dict, List, Optional

from qgis.PyQt import QtCore
from qgis.core import QgsCoordinateTransform, QgsGeometry, QgsPointXY, QgsProject, QgsVectorLayer, QgsWkbTypes
from qgis.utils import iface

try:
    from ..i18n import tr_text
except Exception:  # pragma: no cover
    def tr_text(text):
        return text

from .envelope_manager import (
    EnvelopeManager,
    MODEL_ANGLE_PROP,
    MODEL_LONG_D_PROP,
    MODEL_MODE_PROP,
    MODEL_TRANS_D_PROP,
    layer_diameter_m,
    layer_model_name,
    layer_spacing_spec,
    read_overrides,
    write_overrides,
    set_spacing_property,
)
from .geometry import MODE_AUTO, SpacingSpec, ellipse_polygon
from .map_tool import EllipseDefineTool
from .orientation import most_energetic_angle, sector_centers
from .panel import VALIDATE_BLOCK, VALIDATE_VIEW, SpacingEnvelopePanel

try:
    from . import i18n_spacing
    i18n_spacing.register()
except Exception:  # nosec B110
    pass

try:
    from ..wake_core.controller import is_projected_in_metres
except Exception:  # pragma: no cover
    from wake_core.controller import is_projected_in_metres  # type: ignore

_HOOK_ATTR = "_spacing_notify_layout_changed"
_CHECK_ATTR = "_spacing_check_candidate"
_ROW_KEY_PREFIX = "row:"
_DEFINE_RULE_STATUS = (
    "«Definir elipse en pantalla» solo funciona con la capa de turbinas y el mapa en el mismo sistema de "
    "coordenadas, proyectado y en metros."
)


def _row_key(index: int) -> str:
    return f"{_ROW_KEY_PREFIX}{int(index)}"


def _row_index_from_key(key: str) -> Optional[int]:
    text = str(key or "")
    if not text.startswith(_ROW_KEY_PREFIX):
        return None
    try:
        return int(text[len(_ROW_KEY_PREFIX):])
    except Exception:
        return None


def _crosses_a_cut(geometry: QgsGeometry, transform: QgsCoordinateTransform) -> bool:
    """Si algún lado del polígono salta, al transformarse, un corte del sistema de destino (el antimeridiano, un polo):
    el punto medio del lado no cae cerca del medio del lado transformado, aunque la geometría transformada sea válida
    y no tenga el interior de la original. Es una heurística: en los usos normales la desviación es minúscula, pero
    una curvatura extrema (a metros de un polo) también puede superar el umbral y bloquear sin conflicto."""
    points = [QgsPointXY(p.x(), p.y()) for p in geometry.vertices()]
    for p, q in zip(points, points[1:]):
        tp, tq = transform.transform(p), transform.transform(q)
        tm = transform.transform(QgsPointXY((p.x() + q.x()) / 2.0, (p.y() + q.y()) / 2.0))
        middle = QgsPointXY((tp.x() + tq.x()) / 2.0, (tp.y() + tq.y()) / 2.0)
        if tm.distance(middle) > 0.25 * tp.distance(tq):
            return True
    return False


class SpacingController(QtCore.QObject):
    """Orquesta las envolventes de las capas de las filas del diálogo de Energía."""

    tool_started = QtCore.pyqtSignal()
    tool_finished = QtCore.pyqtSignal()

    def __init__(self, ctl, canvas, parent=None):
        super().__init__(parent)
        self.ctl = ctl
        self.canvas = canvas
        self.panel = SpacingEnvelopePanel()
        self.manager = EnvelopeManager()
        self._tool: Optional[EllipseDefineTool] = None
        self._define_crs_signals: list = []
        self._prev_tool = None
        self._torn_down = False
        self._selected_layer_id = ""
        self._fallback_spec = self.panel.defaults_spec()

        self.panel.changed.connect(self._on_panel_changed)
        self.panel.apply_configuration.connect(self._apply_selected_configuration)
        self.panel.toggled_envelopes.connect(self._on_toggled)
        self.panel.define_on_screen.connect(self._start_define_tool)
        self.panel.reset_overrides.connect(self._reset_overrides)
        self.panel.export_requested.connect(self._export_envelopes)
        self.panel.model_selected.connect(self._on_model_selected)
        self.panel.models_refresh_requested.connect(self._on_models_refresh_requested)

        try:
            setattr(self.ctl, _HOOK_ATTR, self._on_layout_changed)
        except Exception:  # nosec B110
            pass
        try:
            setattr(self.ctl, _CHECK_ATTR, self.check_candidate)
        except Exception:  # nosec B110
            pass

        self._refresh_model_selector(sync_fields=True)
        if self.panel.is_enabled():
            self.refresh()

    # --------------------------------------------------------------- datos
    def _turbine_layer(self) -> Optional[QgsVectorLayer]:
        """Capa del modelo seleccionado, si ya existe.

        El selector también admite definiciones de modelo todavía sin capa,
        representadas por ``row:<índice>``. En ese caso no se toma por error la
        capa activa de otro modelo.
        """
        key = str(self._selected_layer_id or "")
        if key:
            row_idx = _row_index_from_key(key)
            if row_idx is not None:
                finder = getattr(self.ctl, "_find_interactive_layer_for_row", None)
                if callable(finder):
                    try:
                        layer = finder(int(row_idx))
                    except Exception:
                        layer = None
                    if isinstance(layer, QgsVectorLayer) and layer.isValid():
                        return layer
                return None
            # Solo la capa de una fila: una seleccionada antes puede haber salido de ellas.
            return next((layer for layer in self._turbine_layers() if layer.id() == key), None)
        try:
            return self.ctl._get_interactive_target_layer()
        except Exception:
            return None

    def _turbine_layers(self) -> List[QgsVectorLayer]:
        """Las capas elegidas en las filas del diálogo, sin repetir y en su orden.

        Son el parque de Energía: ni las capas del proyecto marcadas como turbinas por otro uso (otra
        fila antes, una importación) ni la seleccionada antes entran en las separaciones (#96).
        """
        layers: List[QgsVectorLayer] = []
        seen = set()
        rows = list(getattr(self.ctl, "_rows", []) or [])
        finder = getattr(self.ctl, "_find_interactive_layer_for_row", None)
        if callable(finder):
            for idx, row in enumerate(rows):
                # Una fila sin modelo ni capa no representa todavía un modelo
                # utilizable. Si la capa existe, sí se conserva aunque esté vacía.
                try:
                    layer = finder(idx)
                except Exception:
                    layer = None
                if not isinstance(layer, QgsVectorLayer):
                    continue
                try:
                    layer_id = layer.id()
                except Exception:  # nosec B112
                    continue
                if layer_id in seen:
                    continue
                seen.add(layer_id)
                layers.append(layer)
        return layers

    def _wrg_path(self) -> Optional[str]:
        for getter in (
            lambda: self.ctl.ed_wrg.text(),
            lambda: self.ctl._last_wrg_path,
        ):
            try:
                path = str(getter() or "").strip()
                if path:
                    return path
            except Exception:  # nosec B112
                continue
        return None

    def _ensure_model_properties(self, layer: QgsVectorLayer) -> None:
        """Migra capas antiguas a una configuración elíptica por modelo."""
        defaults = self._fallback_spec
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

    def _selected_row_index(self, layer: Optional[QgsVectorLayer] = None) -> Optional[int]:
        row_idx = _row_index_from_key(self._selected_layer_id)
        if row_idx is not None:
            return row_idx
        target = layer if isinstance(layer, QgsVectorLayer) else self._turbine_layer()
        if target is None:
            return None
        # La fila la da el selector del diálogo, no los metadatos de la capa, que pueden ser de otra fila.
        finder = getattr(self.ctl, "_row_index_for_layer", None)
        try:
            return finder(target) if callable(finder) else None
        except Exception:
            return None

    def _row_spacing_spec(self, row_idx: int) -> SpacingSpec:
        defaults = self._fallback_spec
        try:
            row = list(getattr(self.ctl, "_rows", []) or [])[int(row_idx)]
            meta = row.get("meta") if isinstance(row, dict) else None
        except Exception:
            meta = None
        if not isinstance(meta, dict):
            meta = {}
        try:
            long_d = float(meta.get("spacing_long_d", defaults.long_d))
        except Exception:
            long_d = float(defaults.long_d)
        try:
            trans_d = float(meta.get("spacing_trans_d", defaults.trans_d))
        except Exception:
            trans_d = float(defaults.trans_d)
        try:
            angle = float(meta.get("spacing_angle_deg", defaults.angle_deg))
        except Exception:
            angle = float(defaults.angle_deg)
        mode = str(meta.get("spacing_mode") or defaults.mode)
        return SpacingSpec(long_d, trans_d, angle, mode, "elliptical")

    def _write_row_spacing_spec(self, row_idx: int, spec: SpacingSpec) -> None:
        try:
            rows = getattr(self.ctl, "_rows", []) or []
            row = rows[int(row_idx)]
            if not isinstance(row, dict):
                return
            meta = row.get("meta")
            if not isinstance(meta, dict):
                meta = {}
                row["meta"] = meta
            meta["spacing_long_d"] = float(spec.long_d)
            meta["spacing_trans_d"] = float(spec.trans_d)
            meta["spacing_mode"] = str(spec.mode)
            meta["spacing_angle_deg"] = float(spec.angle_deg)
            refresh_header = getattr(self.ctl, "_refresh_model_row_header", None)
            if callable(refresh_header):
                refresh_header(int(row_idx))
        except Exception:  # nosec B110
            pass

    def _refresh_model_selector(self, sync_fields: bool = True, *, migrate: bool = True) -> None:
        layers = self._turbine_layers()
        if migrate:
            for layer in layers:
                self._ensure_model_properties(layer)

        rows = list(getattr(self.ctl, "_rows", []) or [])
        finder = getattr(self.ctl, "_find_interactive_layer_for_row", None)
        labels = []
        used_layer_ids = set()
        row_primary_layer = {}

        # Primero se muestran todos los modelos definidos en el diálogo, aunque
        # todavía no tengan capa. Esto permite configurar su elipse antes
        # de cargar las coordenadas.
        for idx, row in enumerate(rows):
            if not isinstance(row, dict):
                continue
            model_name = str(row.get("name") or "").strip()
            layer = None
            if callable(finder):
                try:
                    layer = finder(idx)
                except Exception:
                    layer = None
            has_layer = isinstance(layer, QgsVectorLayer) and layer.isValid()
            # Una fila sin modelo se muestra si tiene capa, como su fila: no con el modelo que la capa guarde de otra
            # fila, porque se edita en esta (#96).
            if not model_name and row.get("wt") is None and not has_layer:
                continue
            model_name = model_name or tr_text("Modelo {n}").format(n=idx + 1)
            if has_layer:
                key = layer.id()
                row_primary_layer[idx] = key
                # Una capa elegida en varias filas es de la primera, como en el diálogo: se muestra y se edita en ella,
                # una sola vez (#96).
                owner = getattr(self.ctl, "_row_index_for_layer", None)
                if callable(owner) and owner(layer) not in (None, idx):
                    continue
                used_layer_ids.add(key)
                try:
                    count = int(layer.featureCount())
                except Exception:
                    count = 0
                try:
                    layer_name = str(layer.name() or "")
                except Exception:
                    layer_name = ""
                label = model_name
                if layer_name and layer_name != model_name:
                    label = f"{model_name} · {layer_name}"
                label += f" ({count})"
            else:
                key = _row_key(idx)
                label = f"{model_name} · {tr_text('sin capa')}"
            labels.append((label, key))

        # Después, cualquier capa de las filas que el bucle anterior no haya mostrado.
        for layer in layers:
            try:
                layer_id = layer.id()
            except Exception:  # nosec B112
                continue
            if layer_id in used_layer_ids:
                continue
            used_layer_ids.add(layer_id)
            try:
                count = int(layer.featureCount())
            except Exception:
                count = 0
            model = layer_model_name(layer)
            try:
                layer_name = str(layer.name() or "")
            except Exception:
                layer_name = ""
            label = model
            if layer_name and layer_name != model:
                label = f"{model} · {layer_name}"
            label += f" ({count})"
            labels.append((label, layer_id))

        valid_keys = {key for _label, key in labels}
        preferred = str(self._selected_layer_id or "")
        current_row = _row_index_from_key(preferred)
        if current_row is not None and current_row in row_primary_layer:
            preferred = row_primary_layer[current_row]
        if preferred not in valid_keys:
            preferred = ""
        if not preferred:
            try:
                active = self.ctl._get_interactive_target_layer()
            except Exception:
                active = None
            if isinstance(active, QgsVectorLayer) and active.id() in valid_keys:
                preferred = active.id()
        if not preferred and labels:
            preferred = labels[0][1]

        self.panel.set_models(labels, preferred)
        self._selected_layer_id = self.panel.selected_model_id()
        if sync_fields:
            self._reflect_selected_model()

    def _reflect_selected_model(self) -> None:
        layer = self._turbine_layer()
        if layer is not None:
            self._ensure_model_properties(layer)
            spec = layer_spacing_spec(layer, self._fallback_spec)
            try:
                count = int(layer.featureCount())
            except Exception:
                count = None
            self.panel.reflect_model_spec(
                spec,
                model_name=layer_model_name(layer),
                diameter_m=layer_diameter_m(layer, 120.0),
                turbine_count=count,
            )
            return

        row_idx = self._selected_row_index()
        rows = list(getattr(self.ctl, "_rows", []) or [])
        if row_idx is not None and 0 <= row_idx < len(rows):
            row = rows[row_idx] if isinstance(rows[row_idx], dict) else {}
            meta = row.get("meta") if isinstance(row, dict) else None
            model_name = str(row.get("name") or tr_text("Modelo {n}").format(n=row_idx + 1))
            diameter = None
            try:
                if isinstance(meta, dict) and meta.get("diam") is not None:
                    diameter = float(meta.get("diam"))
            except Exception:
                diameter = None
            self.panel.reflect_model_spec(
                self._row_spacing_spec(row_idx),
                model_name=f"{model_name} · {tr_text('sin capa')}",
                diameter_m=diameter,
                turbine_count=0,
            )
            self.panel.set_status(
                "Modelo definido sin capa de turbinas. Elige una capa en su fila, o usa «Cargar nueva capa» o «Generar capas de puntos», para crear sus elipses."
            )
            return

        self.panel.set_status("No hay modelos de aerogenerador definidos.")

    def _activate_selected_layer(self, layer: QgsVectorLayer) -> None:
        try:
            fn = getattr(self.ctl, "_set_interactive_edit_layer", None)
            if callable(fn) and fn(layer.id()):
                return
        except Exception:  # nosec B110
            pass
        try:
            iface.setActiveLayer(layer)
        except Exception:  # nosec B110
            pass

    def _on_model_selected(self, layer_id: str) -> None:
        self._selected_layer_id = str(layer_id or "")
        layer = self._turbine_layer()
        if layer is not None:
            self._activate_selected_layer(layer)
        self._reflect_selected_model()
        self.refresh()

    def _on_models_refresh_requested(self) -> None:
        self._refresh_model_selector(sync_fields=True)
        self.refresh()

    def _persist_selected_model_spec(self) -> None:
        layer = self._turbine_layer()
        spec = self.panel.defaults_spec()
        row_idx = self._selected_row_index(layer)
        if layer is None:
            if row_idx is not None:
                self._write_row_spacing_spec(row_idx, spec)
            else:
                self._fallback_spec = spec
            return
        try:
            set_spacing_property(layer, MODEL_LONG_D_PROP, float(spec.long_d))
            set_spacing_property(layer, MODEL_TRANS_D_PROP, float(spec.trans_d))
            set_spacing_property(layer, MODEL_MODE_PROP, str(spec.mode))
            set_spacing_property(layer, MODEL_ANGLE_PROP, float(spec.angle_deg))
        except Exception:  # nosec B110
            pass
        if row_idx is not None:
            self._write_row_spacing_spec(row_idx, spec)

    def _on_panel_changed(self) -> None:
        """Compatibilidad con integraciones antiguas de actualización inmediata."""
        if self._torn_down:
            return
        self._persist_selected_model_spec()
        self.refresh()

    def _apply_selected_configuration(self) -> None:
        """Guarda explícitamente la plantilla y reconstruye sus elipses."""
        if self._torn_down:
            return
        if not self.panel.selected_model_id():
            self.panel.set_status(
                "No hay un modelo seleccionado al que aplicar la configuración."
            )
            return

        spec = self.panel.defaults_spec()
        layer = self._turbine_layer()
        row_idx = self._selected_row_index(layer)
        self._persist_selected_model_spec()

        # Aplicar implica activar la visualización. Se evita emitir la señal de
        # toggle para realizar un único rebuild controlado a continuación.
        if not self.panel.is_enabled():
            self.panel.set_enabled(True, emit=False)

        self.refresh()

        if layer is not None:
            model_name = layer_model_name(layer)
            self.panel.set_status(
                "Configuración aplicada al modelo «{model_name}» · {spacing_dims} · capa de elipses actualizada.",
                model_name=model_name, spacing_dims=f"{format_number(spec.long_d, 'g')}D×{format_number(spec.trans_d, 'g')}D",
            )
            return

        rows = list(getattr(self.ctl, "_rows", []) or [])
        model_name = ""
        if row_idx is not None and 0 <= row_idx < len(rows):
            row = rows[row_idx] if isinstance(rows[row_idx], dict) else {}
            model_name = str(row.get("name") or tr_text("Modelo {n}").format(n=row_idx + 1))
        if not model_name:
            self.panel.set_status(
                "Configuración guardada para el modelo «seleccionado» · "
                "se utilizará automáticamente al elegir su capa de turbinas."
            )
            return
        self.panel.set_status(
            "Configuración guardada para el modelo «{model_name}» · "
            "se utilizará automáticamente al elegir su capa de turbinas.",
            model_name=model_name,
        )

    def retranslate(self):
        """Refresh text only; keep pending dimensions and do not rebuild map layers."""
        if self._torn_down:
            return
        self._refresh_model_selector(sync_fields=False, migrate=False)
        self.panel.retranslate()
        summary = getattr(self, "_last_summary", None)
        if not self.panel.is_enabled():
            self.panel.set_status("—")
        elif self._tool is not None and self.canvas.mapTool() is self._tool:
            self._tool._push_status()
        elif summary is not None and self.panel._status_source is None:
            self._summarize(*summary, notify=False)

    # ------------------------------------------------------------- refresco
    def refresh(self):
        """Reconstruye una capa de envolventes por cada capa de las filas de Energía."""
        if self._torn_down:
            return
        if not self.panel.is_enabled():
            self.manager.remove()
            self.panel.set_status("—")
            return

        self._refresh_model_selector(sync_fields=False)
        layers = self._turbine_layers()
        if not layers:
            self.manager.clear()
            if self._selected_row_index() is not None:
                self.panel.set_status(
                    "Modelo definido sin capa de turbinas. Elige una capa en su fila, o usa «Cargar nueva capa» o «Generar capas de puntos», para crear sus elipses."
                )
            else:
                self.panel.set_status("No hay modelos de aerogenerador definidos.")
            return

        defaults = self._fallback_spec
        auto_angle = None
        if any(layer_spacing_spec(layer, defaults).mode == MODE_AUTO for layer in layers):
            auto_angle = most_energetic_angle(self._wrg_path())
            if auto_angle is None:
                self.panel.set_status(
                    "No se pudo determinar automáticamente el sector más energético · "
                    "se utilizará el ángulo de respaldo guardado en cada modelo."
                )

        status = self.manager.rebuild_many(
            layers,
            defaults,
            auto_angle,
            fallback_diameter_m=120.0,
        )
        self._summarize(status, auto_angle, defaults)

    def _summarize(
        self,
        status_by_layer: Dict[str, Dict[int, str]],
        auto_angle,
        defaults: SpacingSpec,
        notify: bool = True,
    ):
        self._last_summary = (status_by_layer, auto_angle, defaults)
        model_count = len(status_by_layer)
        statuses = [status for per_layer in status_by_layer.values() for status in per_layer.values()]
        n = len(statuses)
        n_conf = sum(1 for status in statuses if status == "conflict")
        n_near = sum(1 for status in statuses if status == "near")

        parts = [
            tr_text("{n} modelo" if model_count == 1 else "{n} modelos").format(n=model_count),
            tr_text("{n} envolvente(s)").format(n=n),
        ]
        model_specs = []
        for source in self._turbine_layers():
            try:
                spec = layer_spacing_spec(source, defaults)
                token = f"{format_number(spec.long_d, 'g')}D×{format_number(spec.trans_d, 'g')}D"
                if token not in model_specs:
                    model_specs.append(token)
            except Exception:  # nosec B112
                continue
        if model_specs:
            parts.append(tr_text("dimensiones: {spacing_dims}").format(spacing_dims=", ".join(model_specs)))
        if auto_angle is not None:
            parts.append(tr_text("sector más energético: {angle_deg}°").format(angle_deg=format_number(auto_angle, ".0f")))
        if n_conf:
            parts.append(tr_text("⚠ {n} conflicto(s) de separación").format(n=n_conf))
        if n_near:
            parts.append(tr_text("{n} cerca del límite").format(n=n_near))
        if not n_conf and not n_near and n:
            parts.append(tr_text("sin conflictos"))
        self.panel.set_status(" · ".join(parts), translated=True)

        if notify and n_conf and self.panel.validation_mode() != VALIDATE_VIEW:
            try:
                iface.messageBar().pushWarning(
                    tr_text("Envolvente de separación"),
                    tr_text(
                        "La disposición multimodelo incumple la separación mínima en {n} turbina(s)."
                    ).format(n=n_conf),
                )
            except Exception:  # nosec B110
                pass

    def _on_toggled(self, checked: bool):
        if not checked:
            self._stop_define_tool(restore=True)
            self.manager.remove()
        else:
            self._refresh_model_selector(sync_fields=True)
            self.refresh()

    @staticmethod
    def _prune_overrides(layer: QgsVectorLayer) -> None:
        try:
            overrides = read_overrides(layer)
            if not overrides:
                return
            alive = {int(feature.id()) for feature in layer.getFeatures()}
            pruned = {fid: spec for fid, spec in overrides.items() if fid in alive}
            if len(pruned) != len(overrides):
                write_overrides(layer, pruned)
        except Exception:  # nosec B110
            pass

    def _on_layout_changed(self, layer=None):
        """Hook tras crear, recargar, añadir o borrar turbinas, o tras cambiar las capas de las filas.

        Selecciona la capa si es de una fila. No activa las separaciones: con ellas desactivadas no se
        crea ninguna envolvente (#96).
        """
        if isinstance(layer, QgsVectorLayer) and layer.id() in {source.id() for source in self._turbine_layers()}:
            self._prune_overrides(layer)
            self._ensure_model_properties(layer)
            self._selected_layer_id = layer.id()
        else:
            for source in self._turbine_layers():
                self._prune_overrides(source)
        self._refresh_model_selector(sync_fields=True)
        self.refresh()

    # -------------------------------------------------- definir en pantalla
    def _start_define_tool(self):
        if self._torn_down:
            return
        layer = self._turbine_layer()
        if layer is None:
            if self._selected_row_index() is not None:
                self.panel.set_status(
                    "El modelo seleccionado todavía no tiene una capa de turbinas para dibujar."
                )
            else:
                self.panel.set_status("Ninguna fila tiene una capa de turbinas para dibujar.")
            return
        if self._tool is not None:
            return
        if not self._can_define_on(layer):
            self.panel.set_status(_DEFINE_RULE_STATUS)
            return

        # El dibujo en pantalla es una excepción individual y se mantiene
        # separado del botón que aplica la plantilla completa al modelo. Usa
        # los valores visibles como punto de partida, sin persistirlos.
        defaults = self.panel.defaults_spec()
        diameter = layer_diameter_m(layer, 120.0)
        magnets = sector_centers(self._wrg_path())

        try:
            self._prev_tool = self.canvas.mapTool()
        except Exception:
            self._prev_tool = None

        self._tool = EllipseDefineTool(
            self.canvas,
            layer,
            diameter,
            defaults,
            on_defined=self._on_ellipse_defined,
            on_status=lambda text: self.panel.set_status(text, translated=True),
            on_cancelled=lambda: self._stop_define_tool(restore=True),
            sector_magnets_deg=magnets,
        )
        try:
            self.canvas.setMapTool(self._tool)
        except Exception:
            self._tool = None
            return
        # La herramienta mide en el sistema del mapa y en el de la capa: si cambia alguno, se cancela.
        self._define_crs_signals = [self.canvas.destinationCrsChanged, layer.crsChanged]
        for signal in self._define_crs_signals:
            signal.connect(self._cancel_define_on_crs_change)
        try:
            self.panel.btn_define.setEnabled(False)
        except Exception:  # nosec B110
            pass
        self.tool_started.emit()

    def _can_define_on(self, layer: Optional[QgsVectorLayer]) -> bool:
        """La capa y el mapa, en el mismo sistema (comparando sistemas, no identificadores), proyectado en metros."""
        try:
            return bool(
                layer is not None
                and layer.crs() == self.canvas.mapSettings().destinationCrs()
                and is_projected_in_metres(layer.crs())
            )
        except Exception:
            return False

    def cancel_definition(self, layer_id: str) -> None:
        """Cancela la definición en pantalla en curso si es sobre la capa ``layer_id``."""
        try:
            on_layer = self._tool is not None and self._tool.layer.id() == layer_id
        except RuntimeError:  # la capa ya no existe
            on_layer = True
        if on_layer:
            self._stop_define_tool(restore=True)

    def _cancel_define_on_crs_change(self, *_args):
        self._stop_define_tool(restore=True)
        self.panel.set_status("Definición cancelada: ha cambiado el sistema de coordenadas del mapa o de la capa.")

    def _on_ellipse_defined(self, fid: int, spec: SpacingSpec):
        # Solo guarda la herramienta activa, y en la capa en la que se empezó a definir, no en la
        # seleccionada al terminar.
        if self._tool is None:
            return
        layer = self._tool.layer
        if layer is None or layer.id() not in {source.id() for source in self._turbine_layers()}:
            # La capa ha salido de las filas mientras se dibujaba: la excepción no se guarda en ella.
            self._stop_define_tool(restore=True)
            return
        if not self._can_define_on(layer):
            self._stop_define_tool(restore=True)
            self.panel.set_status(_DEFINE_RULE_STATUS)
            return
        if layer is not None:
            overrides = read_overrides(layer)
            overrides[int(fid)] = spec
            write_overrides(layer, overrides)
        self.refresh()
        self.panel.set_status(
            "Excepción guardada para la turbina {turbine_id} del modelo «{model_name}».",
            turbine_id=int(fid), model_name=layer_model_name(layer),
        )

    def _stop_define_tool(self, restore: bool = True):
        tool, self._tool = self._tool, None
        for signal in self._define_crs_signals:
            try:
                signal.disconnect(self._cancel_define_on_crs_change)
            except Exception:  # nosec B110
                pass
        self._define_crs_signals = []
        if tool is not None:
            try:
                tool.deactivate()
            except Exception:  # nosec B110
                pass
        if restore:
            try:
                if self._prev_tool is not None:
                    self.canvas.setMapTool(self._prev_tool)
            except Exception:  # nosec B110
                pass
        self._prev_tool = None
        try:
            self.panel.btn_define.setEnabled(
                self.panel.is_enabled() and bool(self.panel.selected_model_id())
            )
        except Exception:  # nosec B110
            pass
        if not self._torn_down:
            self.refresh()
        try:
            self.tool_finished.emit()
        except Exception:  # nosec B110
            pass

    @property
    def alive(self) -> bool:
        return not self._torn_down

    def _reset_overrides(self):
        """Restablece únicamente el modelo activo, no los demás modelos."""
        layer = self._turbine_layer()
        if layer is not None:
            write_overrides(layer, {})
        self.refresh()
        if layer is None:
            self.panel.set_status("Excepciones del modelo «activo» eliminadas · usando su plantilla de modelo.")
            return
        self.panel.set_status(
            "Excepciones del modelo «{model_name}» eliminadas · usando su plantilla de modelo.",
            model_name=layer_model_name(layer),
        )

    # ------------------------------------------------ bloqueo de inserción
    def check_candidate(self, layer, x: float, y: float) -> bool:
        """Comprueba el candidato frente a las envolventes de las capas de las filas."""
        try:
            if not self.panel.is_enabled():
                return True
            if self.panel.validation_mode() != VALIDATE_BLOCK:
                return True
            defaults = layer_spacing_spec(layer, self.panel.defaults_spec())
            angle = defaults.angle_deg
            if defaults.mode == MODE_AUTO:
                auto = most_energetic_angle(self._wrg_path())
                if auto is not None:
                    angle = auto
            diameter = layer_diameter_m(layer, 120.0)
            a_m, b_m = defaults.semi_axes_m(diameter)
            candidate = ellipse_polygon(float(x), float(y), a_m, b_m, angle)

            envelope_layers = self.manager.envelope_layers()
            if not envelope_layers:
                return True
            eps = 1e-6
            for envelope_layer in envelope_layers:
                # La capa de una fila puede estar en cualquier sistema: el candidato se compara en el de la envolvente.
                # Si algo de la comparación falla, se bloquea y se avisa, en vez de dejar pasar una turbina sin
                # comprobarla.
                try:
                    here = candidate
                    if layer is not None and envelope_layer.crs() != layer.crs():
                        here = QgsGeometry(candidate)
                        to_envelope = QgsCoordinateTransform(layer.crs(), envelope_layer.crs(), QgsProject.instance())
                        # Una transformación que funciona puede dar, al cruzar un corte del destino, una elipse no
                        # válida o una válida que no tiene su interior.
                        if (
                            not to_envelope.isValid()
                            or _crosses_a_cut(candidate, to_envelope)
                            or here.transform(to_envelope) != 0
                            or not here.isGeosValid()
                        ):
                            raise ValueError(envelope_layer.name())
                    for feature in envelope_layer.getFeatures():
                        intersection = here.intersection(feature.geometry())
                        # GEOS puede fallar sin excepción: un resultado nulo con su error. Uno vacío es que no hay solape.
                        if intersection is None or intersection.isNull() or intersection.lastError():
                            return self._block_uncompared()
                        if (
                            intersection is not None
                            and not intersection.isEmpty()
                            and intersection.area() > eps
                        ):
                            try:
                                other_model = str(feature["model_name"] or "")
                            except Exception:
                                other_model = ""
                            if other_model:
                                text = tr_text(
                                    "La turbina invade la envolvente de una turbina del modelo «{model_name}» · "
                                    "inserción bloqueada."
                                ).format(model_name=other_model)
                            else:
                                text = tr_text(
                                    "La turbina invade la envolvente de una turbina del modelo «otro modelo» · "
                                    "inserción bloqueada."
                                )
                            try:
                                iface.messageBar().pushWarning(tr_text("Envolvente de separación"), text)
                            except Exception:  # nosec B110
                                pass
                            return False
                except Exception:
                    return self._block_uncompared()
            return True
        except Exception:
            return True

    def _block_uncompared(self) -> bool:
        """Bloquea, con un aviso, una inserción que no se pudo comparar con una envolvente: nunca pasa sin comprobar."""
        try:
            iface.messageBar().pushWarning(
                tr_text("Envolvente de separación"),
                tr_text("No se pudo comparar la turbina con las envolventes de separación · inserción bloqueada."),
            )
        except Exception:  # nosec B110
            pass
        return False

    # ------------------------------------------------------------ export
    def _export_envelopes(self):
        """Exporta una tabla GeoPackage independiente por modelo."""
        from qgis.PyQt import QtWidgets as _QtW

        layers = [layer for layer in self.manager.envelope_layers() if layer.featureCount() > 0]
        if not layers:
            self.panel.set_status("No hay envolventes que exportar.")
            return
        try:
            path, _filter = _QtW.QFileDialog.getSaveFileName(
                None,
                tr_text("Exportar envolventes de separación por modelo"),
                "envolventes_separacion_modelos.gpkg",
                tr_text("GeoPackage (*.gpkg)"),
            )
        except Exception:
            path = ""
        if not path:
            return
        if not path.lower().endswith(".gpkg"):
            path += ".gpkg"
        ok, error, count = self.manager.export_all_to_gpkg(path)
        if ok:
            self.panel.set_status(
                "{layer_count} capa(s) de modelo exportadas: {file_path}",
                layer_count=count, file_path=path,
            )
            try:
                iface.messageBar().pushSuccess(
                    tr_text("Envolvente de separación"),
                    tr_text("Se exportaron {layer_count} capas de modelo a {file_path}").format(
                        layer_count=count, file_path=path
                    ),
                )
            except Exception:  # nosec B110
                pass
        else:
            self.panel.set_status(
                "No se pudo exportar: {error_text}", error_text=error
            )

    # ------------------------------------------------------------- limpieza
    def teardown(self):
        if self._torn_down:
            return
        self._torn_down = True
        self._stop_define_tool(restore=True)
        # Las capas permanecen en el proyecto con sus geometrías; solo se
        # liberan las referencias Python del controller que se está cerrando.
        self.manager.detach()
        try:
            if getattr(self.ctl, _HOOK_ATTR, None) == self._on_layout_changed:
                delattr(self.ctl, _HOOK_ATTR)
        except Exception:  # nosec B110
            pass
        try:
            if getattr(self.ctl, _CHECK_ATTR, None) == self.check_candidate:
                delattr(self.ctl, _CHECK_ATTR)
        except Exception:  # nosec B110
            pass


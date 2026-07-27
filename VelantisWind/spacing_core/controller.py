# -*- coding: utf-8 -*-
"""spacing_core/controller.py — Pegamento del módulo de envolventes.

El controller mantiene una capa de envolventes independiente por cada
capa/modelo de turbinas del proyecto. El modelo activo sigue siendo el que se
edita en pantalla, pero el refresco, la validación y la exportación abarcan
todos los modelos definidos que tengan una capa de puntos asociada.
"""

from __future__ import annotations

from typing import Dict, List, Optional

from qgis.PyQt import QtCore
from qgis.core import QgsProject, QgsVectorLayer, QgsWkbTypes
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
)
from .geometry import MODE_AUTO, SpacingSpec, ellipse_polygon
from .map_tool import EllipseDefineTool
from .orientation import most_energetic_angle, sector_centers
from .panel import VALIDATE_BLOCK, VALIDATE_VIEW, SpacingEnvelopePanel

try:
    from . import i18n_spacing
    i18n_spacing.register()
except Exception:
    pass

_HOOK_ATTR = "_spacing_notify_layout_changed"
_CHECK_ATTR = "_spacing_check_candidate"
_ROW_KEY_PREFIX = "row:"


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


class SpacingController(QtCore.QObject):
    """Orquesta las envolventes de todos los modelos del proyecto."""

    tool_finished = QtCore.pyqtSignal()

    def __init__(self, ctl, canvas, parent=None):
        super().__init__(parent)
        self.ctl = ctl
        self.canvas = canvas
        self.panel = SpacingEnvelopePanel()
        self.manager = EnvelopeManager()
        self._tool: Optional[EllipseDefineTool] = None
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
        except Exception:
            pass
        try:
            setattr(self.ctl, _CHECK_ATTR, self.check_candidate)
        except Exception:
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
            try:
                layer = QgsProject.instance().mapLayer(key)
            except Exception:
                layer = None
            if isinstance(layer, QgsVectorLayer) and layer.isValid():
                return layer
            return None
        try:
            return self.ctl._get_interactive_target_layer(allow_auto_pick=True)
        except TypeError:
            try:
                return self.ctl._get_interactive_target_layer()
            except Exception:
                return None
        except Exception:
            return None

    def _turbine_layers(self) -> List[QgsVectorLayer]:
        """Una capa de puntos representativa por cada modelo definido.

        Usa la asociación oficial fila/modelo del diálogo. Como fallback,
        conserva la capa activa para mantener compatibilidad con integraciones
        antiguas o capas cargadas manualmente.
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
                except Exception:
                    continue
                if layer_id in seen:
                    continue
                seen.add(layer_id)
                layers.append(layer)

        # Capas importadas directamente desde CSV en Energía/Ruido/Sombras.
        # Esto permite que el selector funcione aunque la capa no esté ligada a
        # una fila del diálogo de Energía.
        try:
            project_layers = QgsProject.instance().mapLayers().values()
        except Exception:
            project_layers = []
        for layer in project_layers:
            if not isinstance(layer, QgsVectorLayer):
                continue
            try:
                if layer.geometryType() != QgsWkbTypes.PointGeometry:
                    continue
                role = str(layer.customProperty("velantis/layer_role", "") or "")
                if role not in {"energy_turbines", "turbine_layout"}:
                    continue
                layer_id = layer.id()
            except Exception:
                continue
            if layer_id in seen:
                continue
            seen.add(layer_id)
            layers.append(layer)

        active = self._turbine_layer()
        if isinstance(active, QgsVectorLayer):
            try:
                active_id = active.id()
            except Exception:
                active_id = None
            if active_id and active_id not in seen:
                layers.append(active)

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
            except Exception:
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
        except Exception:
            pass

    def _selected_row_index(self, layer: Optional[QgsVectorLayer] = None) -> Optional[int]:
        row_idx = _row_index_from_key(self._selected_layer_id)
        if row_idx is not None:
            return row_idx
        target = layer if isinstance(layer, QgsVectorLayer) else self._turbine_layer()
        if target is None:
            return None
        for prop in ("velantis/row_index", "velantis/model_index"):
            try:
                raw = target.customProperty(prop, None)
                if raw not in (None, ""):
                    return int(raw)
            except Exception:
                continue
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
        except Exception:
            pass

    def _refresh_model_selector(self, sync_fields: bool = True) -> None:
        layers = self._turbine_layers()
        for layer in layers:
            self._ensure_model_properties(layer)

        rows = list(getattr(self.ctl, "_rows", []) or [])
        finder = getattr(self.ctl, "_find_interactive_layer_for_row", None)
        labels = []
        used_layer_ids = set()
        row_primary_layer = {}

        # Primero se muestran todos los modelos definidos en el diálogo, aunque
        # todavía no tengan una capa/CSV. Esto permite configurar su elipse antes
        # de cargar las coordenadas.
        for idx, row in enumerate(rows):
            if not isinstance(row, dict):
                continue
            model_name = str(row.get("name") or "").strip()
            if not model_name and row.get("wt") is None:
                continue
            model_name = model_name or f"Modelo {idx + 1}"
            layer = None
            if callable(finder):
                try:
                    layer = finder(idx)
                except Exception:
                    layer = None
            if isinstance(layer, QgsVectorLayer) and layer.isValid():
                key = layer.id()
                row_primary_layer[idx] = key
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

        # Después se añaden capas directas o generaciones alternativas que no
        # sean la capa primaria ya representada por una fila.
        for layer in layers:
            try:
                layer_id = layer.id()
            except Exception:
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
                active = self.ctl._get_interactive_target_layer(allow_auto_pick=False)
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
            model_name = str(row.get("name") or f"Modelo {row_idx + 1}")
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
                "Modelo definido sin capa de turbinas. Carga un CSV o genera la capa de puntos para crear sus elipses."
            )
            return

        self.panel.set_status("No hay modelos de aerogenerador definidos.")

    def _activate_selected_layer(self, layer: QgsVectorLayer) -> None:
        try:
            fn = getattr(self.ctl, "_set_interactive_edit_layer", None)
            if callable(fn) and fn(layer.id()):
                return
        except Exception:
            pass
        try:
            iface.setActiveLayer(layer)
        except Exception:
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
            layer.setCustomProperty(MODEL_LONG_D_PROP, float(spec.long_d))
            layer.setCustomProperty(MODEL_TRANS_D_PROP, float(spec.trans_d))
            layer.setCustomProperty(MODEL_MODE_PROP, str(spec.mode))
            layer.setCustomProperty(MODEL_ANGLE_PROP, float(spec.angle_deg))
        except Exception:
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
                f"Configuración aplicada al modelo «{model_name}» · "
                f"{spec.long_d:g}D×{spec.trans_d:g}D · capa de elipses actualizada."
            )
            return

        rows = list(getattr(self.ctl, "_rows", []) or [])
        model_name = ""
        if row_idx is not None and 0 <= row_idx < len(rows):
            row = rows[row_idx] if isinstance(rows[row_idx], dict) else {}
            model_name = str(row.get("name") or f"Modelo {row_idx + 1}")
        self.panel.set_status(
            f"Configuración guardada para el modelo «{model_name or 'seleccionado'}» · "
            "se utilizará automáticamente al cargar su CSV."
        )

    # ------------------------------------------------------------- refresco
    def refresh(self):
        """Reconstruye una capa de envolventes por cada modelo del proyecto."""
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
                    "Modelo definido sin capa de turbinas. Carga un CSV o genera la capa de puntos para crear sus elipses."
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
    ):
        model_count = len(status_by_layer)
        statuses = [status for per_layer in status_by_layer.values() for status in per_layer.values()]
        n = len(statuses)
        n_conf = sum(1 for status in statuses if status == "conflict")
        n_near = sum(1 for status in statuses if status == "near")

        model_word = "modelo" if model_count == 1 else "modelos"
        parts = [f"{model_count} {model_word}", f"{n} envolvente(s)"]
        model_specs = []
        for source in self._turbine_layers():
            try:
                spec = layer_spacing_spec(source, defaults)
                token = f"{spec.long_d:g}D×{spec.trans_d:g}D"
                if token not in model_specs:
                    model_specs.append(token)
            except Exception:
                continue
        if model_specs:
            parts.append("dimensiones: " + ", ".join(model_specs))
        if auto_angle is not None:
            parts.append(f"sector más energético: {auto_angle:.0f}°")
        if n_conf:
            parts.append(f"⚠ {n_conf} conflicto(s) de spacing")
        if n_near:
            parts.append(f"{n_near} cerca del límite")
        if not n_conf and not n_near and n:
            parts.append("sin conflictos")
        self.panel.set_status(" · ".join(parts))

        if n_conf and self.panel.validation_mode() != VALIDATE_VIEW:
            try:
                iface.messageBar().pushWarning(
                    tr_text("Envolvente de separación"),
                    tr_text(f"La disposición multimodelo incumple la separación mínima en {n_conf} turbina(s)."),
                )
            except Exception:
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
        except Exception:
            pass

    def _on_layout_changed(self, layer=None):
        """Hook tras crear, recargar, añadir o borrar turbinas."""
        if isinstance(layer, QgsVectorLayer):
            self._prune_overrides(layer)
            self._ensure_model_properties(layer)
            self._selected_layer_id = layer.id()
            if not self.panel.is_enabled():
                self.panel.set_enabled(True, emit=False)
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
                self.panel.set_status("No hay capa de turbinas activa para dibujar.")
            return
        if self._tool is not None:
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
            on_status=self.panel.set_status,
            on_cancelled=lambda: self._stop_define_tool(restore=True),
            sector_magnets_deg=magnets,
        )
        try:
            self.canvas.setMapTool(self._tool)
        except Exception:
            self._tool = None
            return
        try:
            self.panel.btn_define.setEnabled(False)
        except Exception:
            pass

    def _on_ellipse_defined(self, fid: int, spec: SpacingSpec):
        layer = self._turbine_layer()
        if layer is not None:
            overrides = read_overrides(layer)
            overrides[int(fid)] = spec
            write_overrides(layer, overrides)
        self.refresh()
        self.panel.set_status(
            f"Excepción guardada para la turbina {int(fid)} del modelo «{layer_model_name(layer)}»."
            if layer is not None else "Excepción de envolvente guardada."
        )

    def _stop_define_tool(self, restore: bool = True):
        tool, self._tool = self._tool, None
        if tool is not None:
            try:
                tool.deactivate()
            except Exception:
                pass
        if restore:
            try:
                if self._prev_tool is not None:
                    self.canvas.setMapTool(self._prev_tool)
            except Exception:
                pass
        self._prev_tool = None
        try:
            self.panel.btn_define.setEnabled(
                self.panel.is_enabled() and bool(self.panel.selected_model_id())
            )
        except Exception:
            pass
        if not self._torn_down:
            self.refresh()
        try:
            self.tool_finished.emit()
        except Exception:
            pass

    @property
    def alive(self) -> bool:
        return not self._torn_down

    def _reset_overrides(self):
        """Restablece únicamente el modelo activo, no los demás modelos."""
        layer = self._turbine_layer()
        if layer is not None:
            write_overrides(layer, {})
            model_name = layer_model_name(layer)
        else:
            model_name = "activo"
        self.refresh()
        self.panel.set_status(
            f"Excepciones del modelo «{model_name}» eliminadas · usando su plantilla de modelo."
        )

    # ------------------------------------------------ bloqueo de inserción
    def check_candidate(self, layer, x: float, y: float) -> bool:
        """Comprueba el candidato frente a las envolventes de todos los modelos."""
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
                # Las capas generadas por el diálogo comparten CRS. Si aparece
                # una capa externa en otro CRS, se omite para evitar comparar
                # coordenadas incompatibles (fail-open).
                try:
                    if layer is not None and envelope_layer.crs() != layer.crs():
                        continue
                except Exception:
                    pass
                for feature in envelope_layer.getFeatures():
                    try:
                        intersection = candidate.intersection(feature.geometry())
                        if (
                            intersection is not None
                            and not intersection.isEmpty()
                            and intersection.area() > eps
                        ):
                            try:
                                other_model = str(feature["model_name"] or "otro modelo")
                            except Exception:
                                other_model = "otro modelo"
                            try:
                                iface.messageBar().pushWarning(
                                    tr_text("Envolvente de separación"),
                                    tr_text("La turbina invade la envolvente de una turbina "
                                    f"del modelo «{other_model}» · inserción bloqueada."),
                                )
                            except Exception:
                                pass
                            return False
                    except Exception:
                        continue
            return True
        except Exception:
            return True

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
            self.panel.set_status(f"{count} capa(s) de modelo exportadas: {path}")
            try:
                iface.messageBar().pushSuccess(
                    tr_text("Envolvente de separación"),
                    tr_text(f"Se exportaron {count} capas de modelo a {path}"),
                )
            except Exception:
                pass
        else:
            self.panel.set_status(f"No se pudo exportar: {error}")

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
        except Exception:
            pass
        try:
            if getattr(self.ctl, _CHECK_ATTR, None) == self.check_candidate:
                delattr(self.ctl, _CHECK_ATTR)
        except Exception:
            pass

# -*- coding: utf-8 -*-
"""spacing_core/envelope_manager.py — Capas de envolventes + simbología.

Mantiene una capa poligonal en memoria por cada capa/modelo de turbinas:
``Envolventes de separación · <modelo>``. La asociación es bidireccional y se
persiste mediante custom properties, de modo que cambiar el modelo activo no
elimina ni reutiliza la capa de otro modelo.

Cada capa de envolventes guarda, además del ``fid`` de la turbina, el ID de la
capa fuente y los metadatos de modelo. Los conflictos se calculan de forma
conjunta entre las capas que recibe ``rebuild_many`` y comparten CRS.
"""

from __future__ import annotations

import json
import re
from contextlib import contextmanager
from typing import Callable, Dict, Iterable, List, Optional, Tuple

from qgis.PyQt.QtCore import QVariant
from ..crs_utils import portable_crs_definition
from qgis.PyQt.QtGui import QColor
from qgis.core import (
    QgsCategorizedSymbolRenderer,
    QgsCoordinateTransformContext,
    QgsFeature,
    QgsField,
    QgsFillSymbol,
    QgsGeometry,
    QgsProject,
    QgsRendererCategory,
    QgsVectorFileWriter,
    QgsVectorLayer,
)

try:
    from ..i18n import tr_text
except Exception:  # pragma: no cover
    def tr_text(text):
        return text

try:
    from ..wake_core.controller import is_projected_in_metres
except Exception:  # pragma: no cover
    from wake_core.controller import is_projected_in_metres  # type: ignore

from .geometry import (
    MODE_AUTO,
    STATUS_CONFLICT,
    STATUS_NEAR,
    STATUS_OK,
    SpacingSpec,
    ellipse_polygon,
    evaluate_conflicts,
    normalize_azimuth,
)

OVERRIDES_PROP = "velantis/spacing_overrides"
DIAMETER_PROP = "velantis/diameter_m"
MODEL_LONG_D_PROP = "velantis/spacing_long_d"
MODEL_TRANS_D_PROP = "velantis/spacing_trans_d"
MODEL_MODE_PROP = "velantis/spacing_mode"
MODEL_ANGLE_PROP = "velantis/spacing_angle_deg"
MODEL_NAME_PROP = "velantis/model_name"
MODEL_INDEX_PROP = "velantis/model_index"
ROW_INDEX_PROP = "velantis/row_index"

# Asociación persistente turbinas <-> envolventes
TURBINE_ENVELOPE_LAYER_PROP = "velantis/spacing_envelope_layer_id"
ENVELOPE_ROLE_PROP = "velantis/layer_role"
ENVELOPE_ROLE = "spacing_envelopes"
ENVELOPE_SOURCE_LAYER_PROP = "velantis/source_turbine_layer_id"
ENVELOPE_MODEL_NAME_PROP = "velantis/source_model_name"
ENVELOPE_MODEL_INDEX_PROP = "velantis/source_model_index"

LAYER_PREFIX = "Envolventes de separación"

_STYLE = {
    STATUS_OK: dict(fill="#2aa8a8", fill_alpha=70, line="#1f7f7f", width="0.35"),
    STATUS_NEAR: dict(fill="#f5a623", fill_alpha=95, line="#c77d00", width="0.45"),
    STATUS_CONFLICT: dict(fill="#e04b3a", fill_alpha=110, line="#b02a1c", width="0.6"),
}

_STATUS_LABELS = {
    STATUS_OK: "Sin conflicto",
    STATUS_NEAR: "Cerca del límite",
    STATUS_CONFLICT: "Conflicto de separación",
}

_REQUIRED_FIELDS = (
    ("turbine_fid", QVariant.Int),
    ("turbine_layer_id", QVariant.String),
    ("model_index", QVariant.Int),
    ("model_name", QVariant.String),
    ("spacing_long_d", QVariant.Double),
    ("spacing_trans_d", QVariant.Double),
    ("spacing_angle_deg", QVariant.Double),
    ("spacing_mode", QVariant.String),
    ("spacing_status", QVariant.String),
)


def read_overrides(turbine_layer: QgsVectorLayer) -> Dict[int, SpacingSpec]:
    """Lee los overrides por turbina de la custom property de la capa."""
    out: Dict[int, SpacingSpec] = {}
    try:
        raw = turbine_layer.customProperty(OVERRIDES_PROP, "") or ""
        if not raw:
            return out
        data = json.loads(str(raw))
        for k, v in (data or {}).items():
            try:
                out[int(k)] = SpacingSpec.from_dict(v)
            except Exception:  # nosec B112
                continue
    except Exception:  # nosec B110
        pass
    return out


def set_spacing_property(layer: QgsVectorLayer, key: str, value) -> bool:
    """Persist an actual configuration change and request project saving."""
    if layer.customProperty(key, None) == value:
        return False
    layer.setCustomProperty(key, value)
    QgsProject.instance().setDirty(True)
    return True


def write_overrides(turbine_layer: QgsVectorLayer, overrides: Dict[int, SpacingSpec]) -> None:
    try:
        data = {str(int(k)): v.to_dict() for k, v in (overrides or {}).items()}
        if read_overrides(turbine_layer) != (overrides or {}):
            set_spacing_property(turbine_layer, OVERRIDES_PROP, json.dumps(data))
    except Exception:  # nosec B110
        pass


def layer_diameter_m(turbine_layer: Optional[QgsVectorLayer], fallback: float = 120.0) -> float:
    try:
        v = turbine_layer.customProperty(DIAMETER_PROP, None) if turbine_layer else None
        if v is not None:
            f = float(v)
            if f > 0:
                return f
    except Exception:  # nosec B110
        pass
    return float(fallback)




def layer_spacing_spec(
    turbine_layer: Optional[QgsVectorLayer],
    defaults: SpacingSpec,
) -> SpacingSpec:
    """Return the effective model template stored on the turbine layer.

    Las dimensiones, el modo de orientación y el ángulo de respaldo son
    específicos de cada modelo. La forma se fuerza a elíptica; los proyectos
    antiguos que guardasen una forma circular se migran de manera transparente.
    Los overrides dibujados por turbina mantienen la máxima prioridad.
    """
    long_d = float(defaults.long_d)
    trans_d = float(defaults.trans_d)
    angle_deg = float(defaults.angle_deg)
    mode = str(defaults.mode)
    if turbine_layer is not None:
        try:
            raw = turbine_layer.customProperty(MODEL_LONG_D_PROP, None)
            value = float(raw)
            if value > 0:
                long_d = value
        except Exception:  # nosec B110
            pass
        try:
            raw = turbine_layer.customProperty(MODEL_TRANS_D_PROP, None)
            value = float(raw)
            if value > 0:
                trans_d = value
        except Exception:  # nosec B110
            pass
        try:
            raw = str(turbine_layer.customProperty(MODEL_MODE_PROP, "") or "").strip()
            if raw:
                mode = raw
        except Exception:  # nosec B110
            pass
        try:
            raw = turbine_layer.customProperty(MODEL_ANGLE_PROP, None)
            if raw is not None and raw != "":
                angle_deg = float(raw)
        except Exception:  # nosec B110
            pass
    return SpacingSpec(
        long_d=long_d,
        trans_d=trans_d,
        angle_deg=angle_deg,
        mode=mode,
        shape="elliptical",
    )

def layer_model_name(turbine_layer: Optional[QgsVectorLayer]) -> str:
    """Nombre de modelo persistido, con fallback al nombre visible de capa."""
    if turbine_layer is None:
        return "Modelo"
    try:
        name = str(turbine_layer.customProperty(MODEL_NAME_PROP, "") or "").strip()
    except Exception:
        name = ""
    if name:
        return name
    try:
        name = str(turbine_layer.name() or "").strip()
    except Exception:
        name = "Modelo"
    try:
        name = re.sub(
            r"\s*\(CSV\)\s*(#\d+)?\s*$",
            lambda match: f" {match.group(1)}" if match.group(1) else "",
            name,
        ).strip()
    except Exception:  # nosec B110
        pass
    return name or "Modelo"


def layer_model_index(turbine_layer: Optional[QgsVectorLayer]) -> int:
    if turbine_layer is None:
        return -1
    for key in (MODEL_INDEX_PROP, ROW_INDEX_PROP):
        try:
            raw = turbine_layer.customProperty(key, None)
            if raw is not None and raw != "":
                return int(raw)
        except Exception:  # nosec B112
            continue
    return -1


# Las capas que QGIS está quitando del proyecto mientras el diálogo de Energía reacciona a esa retirada. Al reaccionar
# (filas que salen del parque, el gancho de las separaciones) puede pedir retirar una envolvente que está en la misma
# lista: quitarla otra vez desde dentro rompe QGIS.
_BEING_REMOVED: set = set()


@contextmanager
def layers_being_removed(layer_ids):
    """Mientras dura, no se quita del proyecto ninguna de ``layer_ids``: QGIS ya las está quitando."""
    ids = {str(layer_id) for layer_id in layer_ids or []}
    _BEING_REMOVED.update(ids)
    try:
        yield
    finally:
        _BEING_REMOVED.difference_update(ids)


def _remove_from_project(layer: QgsVectorLayer) -> None:
    if layer.id() not in _BEING_REMOVED:
        QgsProject.instance().removeMapLayer(layer.id())


class EnvelopeManager:
    """Gestiona una capa de envolventes por capa/modelo de turbinas."""

    def __init__(self):
        self._layers: Dict[str, QgsVectorLayer] = {}
        self._sources: Dict[str, QgsVectorLayer] = {}
        self._last_source_id: Optional[str] = None
        self.last_status: Dict[str, Dict[int, str]] = {}

    # ------------------------------------------------------------ utilidades
    @staticmethod
    def _layer_alive(layer: Optional[QgsVectorLayer]) -> bool:
        try:
            return bool(
                layer is not None
                and layer.isValid()
                and QgsProject.instance().mapLayer(layer.id()) is not None
            )
        except Exception:
            return False

    @staticmethod
    def _is_regenerable(layer: Optional[QgsVectorLayer]) -> bool:
        # Provider identity, not the URI: saved memory layers can keep their ID.
        return layer is not None and layer.providerType() == "memory"

    def _find_existing_layer(self, turbine_layer: QgsVectorLayer) -> Optional[QgsVectorLayer]:
        source_id = turbine_layer.id()

        # 1) Asociación directa guardada en la capa de turbinas.
        try:
            env_id = str(turbine_layer.customProperty(TURBINE_ENVELOPE_LAYER_PROP, "") or "")
        except Exception:
            env_id = ""
        if env_id:
            try:
                layer = QgsProject.instance().mapLayer(env_id)
            except Exception:
                layer = None
            if isinstance(layer, QgsVectorLayer) and self._layer_alive(layer):
                try:
                    linked = str(layer.customProperty(ENVELOPE_SOURCE_LAYER_PROP, "") or "")
                except Exception:
                    linked = ""
                if not linked or linked == source_id:
                    return layer

        # 2) Recuperación por propiedad de la capa de envolventes.
        try:
            project_layers = QgsProject.instance().mapLayers().values()
        except Exception:
            project_layers = []
        for layer in project_layers:
            if not isinstance(layer, QgsVectorLayer) or not self._layer_alive(layer):
                continue
            try:
                role = str(layer.customProperty(ENVELOPE_ROLE_PROP, "") or "")
                linked = str(layer.customProperty(ENVELOPE_SOURCE_LAYER_PROP, "") or "")
            except Exception:  # nosec B112
                continue
            if role == ENVELOPE_ROLE and linked == source_id:
                return layer
        return None


    @staticmethod
    def _register_below_source(layer: QgsVectorLayer, turbine_layer: QgsVectorLayer) -> None:
        """Registra la capa y la coloca bajo sus puntos en el árbol de capas.

        QGIS dibuja las capas superiores por encima de las inferiores. Insertar
        la envolvente justo después de la capa de turbinas mantiene visibles los
        puntos y conserva cada pareja dentro del mismo grupo del proyecto.
        """
        project = QgsProject.instance()
        project.addMapLayer(layer, False)
        root = project.layerTreeRoot()
        inserted = False
        try:
            source_node = root.findLayer(turbine_layer.id())
            parent = source_node.parent() if source_node is not None else None
            if parent is not None:
                children = list(parent.children())
                index = children.index(source_node)
                parent.insertLayer(index + 1, layer)
                inserted = True
        except Exception:
            inserted = False
        if not inserted:
            try:
                root.addLayer(layer)
            except Exception:  # nosec B110
                pass

    def _ensure_fields(self, layer: QgsVectorLayer) -> None:
        try:
            existing = {str(f.name()) for f in layer.fields()}
            missing = [QgsField(name, typ) for name, typ in _REQUIRED_FIELDS if name not in existing]
            if missing:
                layer.dataProvider().addAttributes(missing)
                layer.updateFields()
        except Exception:  # nosec B110
            pass

    def _bind_layer(self, envelope_layer: QgsVectorLayer, turbine_layer: QgsVectorLayer) -> None:
        source_id = turbine_layer.id()
        model_name = layer_model_name(turbine_layer)
        model_index = layer_model_index(turbine_layer)
        try:
            envelope_layer.setName(f"{tr_text(LAYER_PREFIX)} · {model_name}")
        except Exception:  # nosec B110
            pass
        try:
            envelope_layer.setCustomProperty(ENVELOPE_ROLE_PROP, ENVELOPE_ROLE)
            envelope_layer.setCustomProperty(ENVELOPE_SOURCE_LAYER_PROP, source_id)
            envelope_layer.setCustomProperty(ENVELOPE_MODEL_NAME_PROP, model_name)
            envelope_layer.setCustomProperty(ENVELOPE_MODEL_INDEX_PROP, int(model_index))
            envelope_layer.setCustomProperty(DIAMETER_PROP, layer_diameter_m(turbine_layer, 120.0))
            envelope_layer.setCustomProperty(
                MODEL_LONG_D_PROP,
                turbine_layer.customProperty(MODEL_LONG_D_PROP, 7.0),
            )
            envelope_layer.setCustomProperty(
                MODEL_TRANS_D_PROP,
                turbine_layer.customProperty(MODEL_TRANS_D_PROP, 4.0),
            )
            envelope_layer.setCustomProperty(
                MODEL_MODE_PROP,
                turbine_layer.customProperty(MODEL_MODE_PROP, MODE_AUTO),
            )
            envelope_layer.setCustomProperty(
                MODEL_ANGLE_PROP,
                turbine_layer.customProperty(MODEL_ANGLE_PROP, 0.0),
            )
            turbine_layer.setCustomProperty(TURBINE_ENVELOPE_LAYER_PROP, envelope_layer.id())
        except Exception:  # nosec B110
            pass
        self._layers[source_id] = envelope_layer
        self._sources[source_id] = turbine_layer
        self._last_source_id = source_id

    # ------------------------------------------------------------ capa
    def _ensure_layer(self, turbine_layer: QgsVectorLayer) -> Optional[QgsVectorLayer]:
        source_id = turbine_layer.id()
        # El sistema completo de la capa, también si no tiene identificador de autoridad.
        crs = turbine_layer.crs()

        layer = self._layers.get(source_id)
        if not self._layer_alive(layer):
            layer = self._find_existing_layer(turbine_layer)

        if layer is not None and not self._is_regenerable(layer):
            # Keep the saved snapshot intact, including fields and symbology.
            # Hide it, so that its old ellipses are not drawn over the update.
            try:
                node = QgsProject.instance().layerTreeRoot().findLayer(layer.id())
                if node is not None:
                    node.setItemVisibilityChecked(False)
            except Exception:  # nosec B110
                pass
            try:
                from qgis.utils import iface
                if iface is not None:
                    iface.messageBar().pushWarning("VelantisWind", tr_text(
                        "La envolvente guardada se conserva sin cambios; la actualización se genera en una capa temporal."
                    ))
            except Exception:  # nosec B110
                pass
            layer = None

        # Si el CRS ha cambiado, la capa antigua no es reutilizable.
        try:
            crs_matches = layer is not None and layer.crs() == crs
        except Exception:
            crs_matches = False
        if layer is not None and not crs_matches:
            try:
                _remove_from_project(layer)
            except Exception:  # nosec B110
                pass
            layer = None

        if layer is None:
            try:
                layer = QgsVectorLayer(
                    "Polygon",
                    f"{tr_text(LAYER_PREFIX)} · {layer_model_name(turbine_layer)}",
                    "memory",
                )
                layer.setCrs(crs)
                provider = layer.dataProvider()
                provider.addAttributes([QgsField(name, typ) for name, typ in _REQUIRED_FIELDS])
                layer.updateFields()
                self._apply_symbology(layer)
                self._register_below_source(layer, turbine_layer)
            except Exception:
                return None
        else:
            self._ensure_fields(layer)
            self._apply_symbology(layer)

        self._bind_layer(layer, turbine_layer)
        return layer

    def _apply_symbology(self, layer: QgsVectorLayer) -> None:
        try:
            categories = []
            for status, style in _STYLE.items():
                fill = QColor(style["fill"])
                fill.setAlpha(int(style["fill_alpha"]))
                symbol = QgsFillSymbol.createSimple({
                    "outline_color": style["line"],
                    "outline_width": style["width"],
                    "style": "solid",
                })
                try:
                    symbol.setColor(fill)
                except Exception:  # nosec B110
                    pass
                categories.append(
                    QgsRendererCategory(status, symbol, tr_text(_STATUS_LABELS.get(status, status)))
                )
            layer.setRenderer(QgsCategorizedSymbolRenderer("spacing_status", categories))
            try:
                layer.setFlags(layer.flags() & ~QgsVectorLayer.Identifiable)
            except Exception:  # nosec B110
                pass
        except Exception:  # nosec B110
            pass

    # ------------------------------------------------------------ rebuild
    @staticmethod
    def _resolve_spec(
        turbine_layer: QgsVectorLayer,
        fid: int,
        defaults: SpacingSpec,
        overrides: Dict[int, SpacingSpec],
        spec_resolver: Optional[Callable],
    ) -> SpacingSpec:
        spec = None
        if spec_resolver is not None:
            try:
                spec = spec_resolver(turbine_layer, fid)
            except TypeError:
                try:
                    spec = spec_resolver(fid)
                except Exception:
                    spec = None
            except Exception:
                spec = None
        if spec is None:
            spec = overrides.get(fid)
        if spec is None:
            spec = SpacingSpec(
                long_d=defaults.long_d,
                trans_d=defaults.trans_d,
                angle_deg=defaults.angle_deg,
                mode=defaults.mode,
                shape="elliptical",
            )
        # Migra también overrides antiguos que todavía guarden ``circular``.
        # Se crea una copia para no mutar el objeto persistido durante el cálculo.
        return SpacingSpec(
            long_d=spec.long_d,
            trans_d=spec.trans_d,
            angle_deg=spec.angle_deg,
            mode=spec.mode,
            shape="elliptical",
        )

    def rebuild_many(
        self,
        turbine_layers: Iterable[QgsVectorLayer],
        defaults: SpacingSpec,
        auto_angle_deg: Optional[float],
        fallback_diameter_m: float = 120.0,
        spec_resolver: Optional[Callable] = None,
        create_missing: bool = True,
    ) -> Dict[str, Dict[int, str]]:
        """Reconstruye las capas de todos los modelos y valida el conjunto.

        Los conflictos se evalúan entre modelos siempre que sus capas fuente
        compartan CRS. Con ``create_missing`` falso, una fuente sin envolvente
        cuenta en los conflictos de las demás, pero no se le crea (#96).
        Devuelve ``{source_layer_id: {fid: estado}}``.
        """
        valid_sources: List[QgsVectorLayer] = []
        seen = set()
        for source in turbine_layers or []:
            try:
                if not isinstance(source, QgsVectorLayer) or not source.isValid():
                    continue
                # Los semiejes están en metros y la elipse se construye en el sistema de la capa.
                if not is_projected_in_metres(source.crs()):
                    self._drop_envelope(source)
                    continue
                source_id = source.id()
            except Exception:  # nosec B112
                continue
            if source_id in seen:
                continue
            seen.add(source_id)
            valid_sources.append(source)

        if not valid_sources:
            self.clear()
            self.last_status = {}
            return {}

        self.remove_missing_sources(seen)

        # Geometrías agrupadas por CRS para no comparar coordenadas incompatibles.
        grouped_geometries: Dict[str, Dict[int, QgsGeometry]] = {}
        records: Dict[int, Tuple[str, int, QgsGeometry, SpacingSpec, str, int]] = {}
        next_key = 1

        for source in valid_sources:
            if create_missing or self._layer_alive(self._layers.get(source.id())) or self._find_existing_layer(source):
                if self._ensure_layer(source) is None:
                    continue
            source_id = source.id()
            try:
                crs_key = portable_crs_definition(source.crs())
            except Exception:
                crs_key = source_id
            diameter = layer_diameter_m(source, fallback_diameter_m)
            model_defaults = layer_spacing_spec(source, defaults)
            overrides = read_overrides(source)
            model_name = layer_model_name(source)
            model_index = layer_model_index(source)

            for feature in source.getFeatures():
                try:
                    point = feature.geometry().asPoint()
                    fid = int(feature.id())
                except Exception:  # nosec B112
                    continue
                spec = self._resolve_spec(source, fid, model_defaults, overrides, spec_resolver)
                angle = spec.angle_deg
                if spec.mode == MODE_AUTO:
                    angle = (
                        normalize_azimuth(auto_angle_deg)
                        if auto_angle_deg is not None
                        else normalize_azimuth(spec.angle_deg)
                    )
                a_m, b_m = spec.semi_axes_m(diameter)
                geometry = ellipse_polygon(point.x(), point.y(), a_m, b_m, angle)
                effective = SpacingSpec(
                    spec.long_d,
                    spec.trans_d,
                    angle,
                    spec.mode,
                    spec.shape,
                )
                key = next_key
                next_key += 1
                grouped_geometries.setdefault(crs_key, {})[key] = geometry
                records[key] = (
                    source_id,
                    fid,
                    geometry,
                    effective,
                    model_name,
                    model_index,
                )

        # Estado conjunto, incluyendo pares de modelos diferentes.
        global_status: Dict[int, str] = {}
        for geometries in grouped_geometries.values():
            global_status.update(evaluate_conflicts(geometries))

        nested_status: Dict[str, Dict[int, str]] = {source.id(): {} for source in valid_sources}
        features_by_source: Dict[str, List[QgsFeature]] = {source.id(): [] for source in valid_sources}

        for key, record in records.items():
            source_id, fid, geometry, spec, model_name, model_index = record
            layer = self._layers.get(source_id)
            if layer is None:
                continue
            status = str(global_status.get(key, STATUS_OK))
            nested_status.setdefault(source_id, {})[fid] = status
            try:
                feature = QgsFeature(layer.fields())
                feature.setGeometry(geometry)
                feature.setAttribute("turbine_fid", fid)
                feature.setAttribute("turbine_layer_id", source_id)
                feature.setAttribute("model_index", int(model_index))
                feature.setAttribute("model_name", model_name)
                feature.setAttribute("spacing_long_d", float(spec.long_d))
                feature.setAttribute("spacing_trans_d", float(spec.trans_d))
                feature.setAttribute("spacing_angle_deg", float(spec.angle_deg))
                feature.setAttribute("spacing_mode", str(spec.mode))
                feature.setAttribute("spacing_status", status)
                features_by_source.setdefault(source_id, []).append(feature)
            except Exception:  # nosec B112
                continue

        # Volcado independiente: una capa por modelo/capa fuente.
        for source in valid_sources:
            source_id = source.id()
            layer = self._layers.get(source_id)
            if layer is None:
                continue
            try:
                if not self._is_regenerable(layer):
                    continue
                provider = layer.dataProvider()
                provider.truncate()
                features = features_by_source.get(source_id, [])
                if features:
                    provider.addFeatures(features)
                layer.updateExtents()
                layer.triggerRepaint()
            except Exception:  # nosec B110
                pass

        self.last_status = nested_status
        return nested_status

    def rebuild(
        self,
        turbine_layer: Optional[QgsVectorLayer],
        defaults: SpacingSpec,
        auto_angle_deg: Optional[float],
        fallback_diameter_m: float = 120.0,
        spec_resolver: Optional[Callable[[int], Optional[SpacingSpec]]] = None,
    ) -> Dict[int, str]:
        """Compatibilidad: reconstruye un único modelo."""
        if turbine_layer is None:
            self.clear()
            return {}
        result = self.rebuild_many(
            [turbine_layer],
            defaults,
            auto_angle_deg,
            fallback_diameter_m=fallback_diameter_m,
            spec_resolver=spec_resolver,
        )
        return result.get(turbine_layer.id(), {})

    # ------------------------------------------------------------ acceso
    def envelope_layer(
        self, turbine_layer: Optional[QgsVectorLayer] = None
    ) -> Optional[QgsVectorLayer]:
        """Capa asociada a ``turbine_layer``; sin argumento, la última usada."""
        source_id = None
        try:
            source_id = turbine_layer.id() if turbine_layer is not None else self._last_source_id
        except Exception:
            source_id = self._last_source_id
        layer = self._layers.get(source_id or "")
        return layer if self._layer_alive(layer) else None

    def envelope_layers(self) -> List[QgsVectorLayer]:
        """Todas las capas de envolventes vivas, una por modelo/capa fuente."""
        out = []
        for source_id, layer in list(self._layers.items()):
            if self._layer_alive(layer):
                out.append(layer)
            else:
                self._layers.pop(source_id, None)
                self._sources.pop(source_id, None)
        return out

    def source_layer_for_envelope(self, envelope_layer: QgsVectorLayer) -> Optional[QgsVectorLayer]:
        try:
            source_id = str(envelope_layer.customProperty(ENVELOPE_SOURCE_LAYER_PROP, "") or "")
        except Exception:
            source_id = ""
        source = self._sources.get(source_id)
        if source is not None:
            return source
        try:
            source = QgsProject.instance().mapLayer(source_id)
        except Exception:
            source = None
        return source if isinstance(source, QgsVectorLayer) else None

    # ------------------------------------------------------------ export
    @staticmethod
    def _safe_table_name(layer: QgsVectorLayer, used: set) -> str:
        try:
            model = str(layer.customProperty(ENVELOPE_MODEL_NAME_PROP, "") or "")
            idx = int(layer.customProperty(ENVELOPE_MODEL_INDEX_PROP, -1))
        except Exception:
            model, idx = "modelo", -1
        slug = re.sub(r"[^0-9A-Za-z_]+", "_", model.strip()).strip("_") or "modelo"
        prefix = f"model_{idx + 1}_" if idx >= 0 else ""
        base = f"spacing_{prefix}{slug}"[:60]
        name = base
        n = 2
        while name in used:
            suffix = f"_{n}"
            name = f"{base[:60-len(suffix)]}{suffix}"
            n += 1
        used.add(name)
        return name

    @staticmethod
    def _write_layer_to_gpkg(layer: QgsVectorLayer, path: str, table_name: str, overwrite_file: bool):
        opts = QgsVectorFileWriter.SaveVectorOptions()
        opts.driverName = "GPKG"
        opts.layerName = table_name
        try:
            opts.actionOnExistingFile = (
                QgsVectorFileWriter.CreateOrOverwriteFile
                if overwrite_file
                else QgsVectorFileWriter.CreateOrOverwriteLayer
            )
        except Exception:  # nosec B110
            pass
        try:
            context = QgsProject.instance().transformContext()
        except Exception:
            context = QgsCoordinateTransformContext()
        try:
            result = QgsVectorFileWriter.writeAsVectorFormatV3(layer, path, context, opts)
        except Exception:
            result = QgsVectorFileWriter.writeAsVectorFormatV2(layer, path, context, opts)
        code = result[0] if isinstance(result, (tuple, list)) else result
        if int(code) == int(QgsVectorFileWriter.NoError):
            return True, ""
        message = result[1] if isinstance(result, (tuple, list)) and len(result) > 1 else str(code)
        return False, str(message)

    def export_to_gpkg(self, path: str, turbine_layer: Optional[QgsVectorLayer] = None):
        """Exporta una capa concreta (compatibilidad con la API anterior)."""
        layer = self.envelope_layer(turbine_layer)
        if layer is None:
            return False, "sin capa"
        return self._write_layer_to_gpkg(layer, path, "spacing_envelopes", True)

    def export_all_to_gpkg(self, path: str):
        """Exporta todas las capas, una tabla GeoPackage por modelo."""
        layers = [layer for layer in self.envelope_layers() if layer.featureCount() > 0]
        if not layers:
            return False, "sin capas", 0
        used = set()
        for i, layer in enumerate(layers):
            table_name = self._safe_table_name(layer, used)
            ok, error = self._write_layer_to_gpkg(layer, path, table_name, i == 0)
            if not ok:
                return False, error, i
        return True, "", len(layers)

    # ------------------------------------------------------------ limpieza
    def clear(self) -> None:
        for layer in self.envelope_layers():
            try:
                if not self._is_regenerable(layer):
                    continue
                layer.dataProvider().truncate()
                layer.triggerRepaint()
            except Exception:  # nosec B110
                pass
        self.last_status = {}

    def detach(self) -> None:
        """Libera referencias sin borrar ni vaciar las capas del proyecto."""
        self._layers = {}
        self._sources = {}
        self._last_source_id = None
        self.last_status = {}

    def remove_for_source(self, source_id: str) -> None:
        layer = self._layers.pop(source_id, None)
        source = self._sources.pop(source_id, None)
        try:
            if self._is_regenerable(layer):
                _remove_from_project(layer)
        except Exception:  # nosec B110
            pass
        try:
            if source is not None:
                source.removeCustomProperty(TURBINE_ENVELOPE_LAYER_PROP)
        except Exception:  # nosec B110
            pass
        self.last_status.pop(source_id, None)
        if self._last_source_id == source_id:
            self._last_source_id = next(iter(self._layers), None)

    def _drop_envelope(self, turbine_layer: QgsVectorLayer) -> None:
        """Quita la envolvente de una capa que no lleva elipses, también si la creó otra sesión."""
        source_id = turbine_layer.id()
        layer = self._layers.get(source_id) if self._layer_alive(self._layers.get(source_id)) else None
        layer = layer or self._find_existing_layer(turbine_layer)
        if layer is None:
            return
        self._layers[source_id] = layer
        self._sources[source_id] = turbine_layer
        self.remove_for_source(source_id)

    def remove_missing_sources(self, source_ids: Iterable[str]) -> None:
        keep = set(source_ids or [])
        for source_id in list(self._layers):
            if source_id not in keep:
                self.remove_for_source(source_id)

    def remove(self) -> None:
        """Quita del proyecto todas las capas de envolventes gestionadas."""
        for source_id in list(self._layers):
            self.remove_for_source(source_id)
        self._layers = {}
        self._sources = {}
        self._last_source_id = None
        self.last_status = {}


# -*- coding: utf-8 -*-
"""QGIS layer writers for AEP per-turbine results.

Keeping this code outside the solver makes the AEP computation easier to test
and keeps all QGIS-specific attribute/map-tip logic in one place.
"""
from __future__ import annotations

import math
from typing import Any, Callable, Dict, List, Optional, Tuple

from qgis.PyQt.QtCore import QVariant
from qgis.core import (
    Qgis,
    QgsCoordinateTransform,
    QgsProject,
    QgsRectangle,
    QgsVectorDataProvider,
    QgsVectorLayer,
    QgsFeatureRequest,
    QgsField,
    QgsFields,
    QgsWkbTypes,
    QgsPointXY,
    QgsSpatialIndex,
    QgsGraduatedSymbolRenderer,
    QgsRendererRange,
    QgsMarkerSymbol,
    QgsSingleSymbolRenderer,
    QgsStyle,
)

from ..log_text import LogText, log_text
from ..results.breakdown_translations import register_breakdown_translations

# The map tips and the warnings of the breakdown are translated even when the results window was never opened.
register_breakdown_translations()

_GROUP_NAME = "AEP · Coordenadas por modelo"

_RESULT_FIELDS = [
    ("model", QVariant.String),
    ("aep_mwh", QVariant.Double),
    ("aep_free_mwh", QVariant.Double),
    ("loss_wake_mwh", QVariant.Double),
    ("loss_wake_pct", QVariant.Double),
    ("loss_ti_mwh", QVariant.Double),
    ("loss_ti_pct", QVariant.Double),
    ("ti_impact_mwh", QVariant.Double),
    ("ti_impact_pct", QVariant.Double),
    ("loss_blk_mwh", QVariant.Double),
    ("loss_blk_pct", QVariant.Double),
    ("aep_wake_only_mwh", QVariant.Double),
    ("aep_wake_ti_mwh", QVariant.Double),
    ("aep_wake_blk_mwh", QVariant.Double),
    ("aep_wake_ti_blk_mwh", QVariant.Double),
    ("ti_eff", QVariant.Double),
    ("model_perf_pct", QVariant.Double),
    ("model_rank", QVariant.Int),
]
# The fields of schema 2 (P0 of the wake-model plan, section 8): the signed breakdown, the two TI and the state of
# each term. The schema-1 fields that changed meaning are not written into any more; a layer that has them keeps
# them untouched and is told so.
_RESULT_FIELDS_V2 = [
    ("model", QVariant.String),
    ("aep_mwh", QVariant.Double),
    ("aep_free_mwh", QVariant.Double),
    ("aep_w_mwh", QVariant.Double),
    ("aep_wt_mwh", QVariant.Double),
    ("aep_wb_mwh", QVariant.Double),
    ("l_wake_mwh", QVariant.Double),
    ("l_wake_pct", QVariant.Double),
    ("d_turb_mwh", QVariant.Double),
    ("d_turb_pct", QVariant.Double),
    ("d_blk_mwh", QVariant.Double),
    ("d_blk_pct", QVariant.Double),
    ("l_total_mwh", QVariant.Double),
    ("l_total_pct", QVariant.Double),
    ("ti_ambient", QVariant.Double),
    ("ti_effective", QVariant.Double),
    ("wake_states", QVariant.String),
    ("res_schema", QVariant.Int),
    ("model_perf_pct", QVariant.Double),
    ("model_rank", QVariant.Int),
    # The identification of the wake configuration and its warnings (``export.wake_texts``).
    ("wake_id", QVariant.String),
    ("wake_warn", QVariant.String),
]
# The formats that keep at most 254 bytes of a text (dBASE and MapInfo): a longer one would be cut.
_SHORT_TEXT_FORMATS = ("ESRI Shapefile", "MapInfo File")
_SHORT_TEXT_BYTES = 254
OLD_SCHEMA_FIELDS = [n for n, _t in _RESULT_FIELDS if n not in dict(_RESULT_FIELDS_V2)]


def result_fields(rows: List[Dict[str, Any]]) -> List[Tuple[str, Any]]:
    """The fields of the schema the rows belong to: 2 when they say so (``res_schema``), the previous one otherwise."""
    return _RESULT_FIELDS_V2 if any(r.get("res_schema") == 2 for r in rows) else _RESULT_FIELDS


# Field types that keep each result type's values unchanged.
_LOSSLESS_TYPES = {
    QVariant.String: {QVariant.String},
    QVariant.Double: {QVariant.Double},
    QVariant.Int: {QVariant.Int, QVariant.LongLong, QVariant.Double},
}


def _keeps_value(field: QgsField, value: Any) -> bool:
    """True if ``field``, of a type that suits ``value``, stores it unchanged: not rounded to fewer decimals, nor cut."""
    # Some formats limit a text field in bytes (MapInfo): a name with accents could be cut although its characters fit.
    if isinstance(value, str) and field.length() > 0 and len(value.encode("utf-8")) > field.length():
        return False
    try:
        stored = field.convertCompatible(value)
    except Exception:
        return False
    if isinstance(value, float) and math.isnan(value):
        return isinstance(stored, float) and math.isnan(stored)
    # A fixed decimal without decimals (Decimal(10,0)) keeps whole numbers only, although QGIS does not round to it.
    if isinstance(stored, float) and field.length() > 0 and field.precision() == 0 and math.isfinite(stored) and stored != int(stored):
        return False
    return stored == value


def _text_keeps_number(field: QgsField, value: Any) -> bool:
    """True if a text field stores the number ``value`` as a text that reads back as the same number."""
    try:
        text = field.convertCompatible(value)
        # Whole numbers exactly: a float would round a large integer.
        stored = int(text) if isinstance(value, int) else float(text)
    except Exception:
        return False
    return stored == value or (isinstance(stored, float) and math.isnan(stored) and isinstance(value, float) and math.isnan(value))


def _provider_values(layer: QgsVectorLayer, fids: List[int], names: List[str]) -> Dict[int, Dict[str, Any]]:
    """The values the provider holds in the fields ``names`` of the features ``fids``, past any edit buffer."""
    provider = layer.dataProvider()
    indexes = {n: provider.fields().indexFromName(n) for n in names}
    request = QgsFeatureRequest().setFilterFids(fids)
    return {f.id(): {n: f.attribute(i) for n, i in indexes.items()} for f in provider.getFeatures(request)}


def _same_values(a: Dict[str, Any], b: Dict[str, Any]) -> bool:
    """The same values field by field; two NaN count as the same."""
    def same(x: Any, y: Any) -> bool:
        return x == y or (isinstance(x, float) and isinstance(y, float) and math.isnan(x) and math.isnan(y))
    return a.keys() == b.keys() and all(same(a[k], b[k]) for k in a)


def _emit(log: Optional[Callable[..., None]], msg: str, level: Any = None) -> None:
    if log is not None:
        try:
            log(msg, level)
        except TypeError:
            log(msg)
        except Exception:  # nosec B110
            pass


def layer_points_in_project_crs(layer: QgsVectorLayer) -> Tuple[Dict[int, QgsPointXY], int]:
    """Readable points of a point layer by feature id, in the project CRS, and how many features have none.

    A feature without geometry or a multipoint of several parts has no readable point; a multipoint of one part reads
    as that point. Without a valid project CRS the points stay in the layer CRS. Raises ``ValueError`` if the layer
    has no valid CRS and ``QgsCsException`` if a point cannot be transformed.
    """
    if not layer.crs().isValid():
        raise ValueError(layer.name())
    project = QgsProject.instance()
    transform = None
    if project.crs().isValid():
        transform = QgsCoordinateTransform(layer.crs(), project.crs(), project.transformContext())
    points: Dict[int, QgsPointXY] = {}
    unreadable = 0
    for feat in layer.getFeatures():
        geom = feat.geometry()
        parts = [] if geom.isEmpty() else (geom.asMultiPoint() if geom.isMultipart() else [geom.asPoint()])
        if len(parts) != 1:
            unreadable += 1
            continue
        points[feat.id()] = transform.transform(parts[0]) if transform is not None else QgsPointXY(parts[0])
    return points, unreadable


def _commit(layer: QgsVectorLayer, apply: Callable[[], bool], failure: LogText) -> None:
    """Run ``apply`` in an edit session of its own and commit it, or raise ``RuntimeError`` with the session closed.

    The changes go through the layer's edit buffer and a failed commit is rolled back: a provider with transactions
    keeps nothing of it, one without them (MapInfo) may keep what it wrote before failing.
    """
    if not layer.startEditing():
        raise RuntimeError(log_text("[Layer] No se pudo editar la capa '{layer}': no se han escrito los resultados.", layer=layer.name()))
    try:
        if not apply():
            raise RuntimeError(failure)
        if not layer.commitChanges():
            raise RuntimeError(log_text(
                # Without saying that nothing was written: a provider without transactions may have kept part of it.
                "[Layer] No se pudieron guardar los cambios en la capa '{layer}' ({errors}).",
                layer=layer.name(), errors="; ".join(layer.commitErrors()),
            ))
    except Exception:
        if layer.isEditable():
            layer.rollBack()
        raise


def ensure_result_fields(layer: QgsVectorLayer, fields: Optional[List[Tuple[str, Any]]] = None) -> None:
    """Ensure that the target point layer has all AEP result attributes (of ``fields``, by default those of the
    previous schema), or raise ``RuntimeError``."""
    _RESULT_FIELDS = fields or globals()["_RESULT_FIELDS"]
    existing = {f.name() for f in layer.fields()}
    to_add = [QgsField(n, t) for (n, t) in _RESULT_FIELDS if n not in existing]
    if to_add:
        _commit(
            layer,
            lambda: all(layer.addAttribute(field) for field in to_add),
            log_text("[Layer] No se pudieron crear los campos de resultados en la capa '{layer}': no se han escrito los resultados.", layer=layer.name()),
        )
    # Some formats shorten the names (a shapefile keeps 10 characters): the results would not find their field.
    missing = [n for (n, _t) in _RESULT_FIELDS if layer.fields().indexFromName(n) < 0]
    if missing:
        raise RuntimeError(log_text(
            "[Layer] La capa '{layer}' no admite los campos de resultados con su nombre completo ({fields}): no se han escrito los resultados.",
            layer=layer.name(), fields=", ".join(missing),
        ))


def push_results_to_point_layer(
    layer: QgsVectorLayer, per_turbine_table: List[Dict[str, Any]], tol_m: float = 30.0,
    points: Optional[Dict[int, QgsPointXY]] = None,
) -> int:
    """
    Match each result row (x, y), in the project CRS, with the nearest point of the layer and write AEP fields.

    ``points`` are the layer's points read before any result was written (by default, read now). A row farther than
    ``tol_m`` metres from every point is not written. Returns how many points were written. Raises
    ``RuntimeError`` without writing when the layer cannot take the results: in edit mode, in a project that edits its
    layers in groups, without the capabilities to add the fields or change their values, or with result fields that
    are not its own or that would not keep the values (another type, fewer decimals, a shorter text).
    """
    if layer is None or QgsWkbTypes.geometryType(layer.wkbType()) != QgsWkbTypes.PointGeometry:
        raise RuntimeError(log_text("Proporciona una capa de puntos válida."))
    _RESULT_FIELDS = result_fields(per_turbine_table)
    # Never write into an edit session the user has open.
    if layer.isEditable():
        raise RuntimeError(log_text("[Layer] La capa '{layer}' está en modo edición: no se han escrito los resultados.", layer=layer.name()))
    # When the project edits its layers in groups, this session would also commit or discard other layers' edits.
    if QgsProject.instance().transactionMode() != Qgis.TransactionMode.Disabled:
        raise RuntimeError(log_text(
            "[Layer] El proyecto edita sus capas en grupo (modo de transacción): no se han escrito los resultados en la capa '{layer}' para no guardar ni descartar cambios de otras capas.",
            layer=layer.name(),
        ))
    caps = layer.dataProvider().capabilities()
    # The layer's fields as its provider has them now: a schema the layer has not reloaded yet would hide fields.
    layer.updateFields()
    existing = {f.name() for f in layer.fields()}
    provider_before = {f.name() for f in layer.dataProvider().fields()}
    adds_fields = any(n not in existing for (n, _t) in _RESULT_FIELDS)
    if (adds_fields and not caps & QgsVectorDataProvider.AddAttributes) or not caps & QgsVectorDataProvider.ChangeAttributeValues:
        raise RuntimeError(log_text("[Layer] La capa '{layer}' no admite añadir o cambiar sus campos: no se han escrito los resultados.", layer=layer.name()))
    # A shapefile keeps 10 characters of a field name: the results would land in other fields.
    if layer.dataProvider().storageType() == "ESRI Shapefile":
        too_long = [n for (n, _t) in _RESULT_FIELDS if n not in existing and len(n) > 10]
        if too_long:
            raise RuntimeError(log_text(
                "[Layer] La capa '{layer}' no admite los campos de resultados con su nombre completo ({fields}): no se han escrito los resultados.",
                layer=layer.name(), fields=", ".join(too_long),
            ))
    # A text the format cannot keep whole (the warnings, the identification) is refused, never cut.
    short_text = layer.dataProvider().storageType() in _SHORT_TEXT_FORMATS
    if short_text:
        too_long = sorted({n for row in per_turbine_table for (n, t) in _RESULT_FIELDS if t == QVariant.String
                           and isinstance(row.get(n), str) and len(row[n].encode("utf-8")) > _SHORT_TEXT_BYTES})
        if too_long:
            raise RuntimeError(log_text(
                "[Layer] La capa '{layer}' no guarda textos de más de {limit} bytes, y los campos {fields} los necesitan: no se han escrito los resultados.",
                layer=layer.name(), limit=_SHORT_TEXT_BYTES, fields=", ".join(too_long),
            ))
    # A result field from a join or an expression is not stored in the layer: writing it would change another layer.
    fields = layer.fields()
    foreign = [n for n in existing if n in dict(_RESULT_FIELDS) and fields.fieldOrigin(fields.indexFromName(n)) != QgsFields.OriginProvider]
    if foreign:
        raise RuntimeError(log_text(
            "[Layer] Los campos de resultados {fields} de la capa '{layer}' no son de la propia capa (uniones o expresiones): no se han escrito los resultados.",
            fields=", ".join(sorted(foreign)), layer=layer.name(),
        ))

    # Match first: a layer gets no new field when no result is written into it.
    if points is None:
        points, _unreadable = layer_points_in_project_crs(layer)
    sidx = QgsSpatialIndex()
    for fid, point in points.items():
        sidx.addFeature(fid, QgsRectangle(point, point))
    updates: Dict[int, Dict[str, Any]] = {}

    field_names = [name for name, _typ in _RESULT_FIELDS]
    # Several results may fall next to one point (another point no longer visible, for example through a filter on a
    # result field): the point takes the nearest one, never the last one.
    distances: Dict[int, float] = {}
    for row in per_turbine_table:
        pt = QgsPointXY(row["x"], row["y"])
        near_ids = sidx.nearestNeighbor(pt, 1)
        if not near_ids:
            continue
        fid = near_ids[0]
        near = points[fid]
        distance = math.hypot(near.x() - pt.x(), near.y() - pt.y())
        if distance > tol_m or distance >= distances.get(fid, math.inf):
            continue
        distances[fid] = distance
        updates[fid] = {key: row.get(key, None) for key in field_names}

    # An existing result field would store the values as its type, decimals and length allow: another type is refused
    # (an integer AEP, a numeric model name), and so are fewer decimals or a shorter text when a value would change (a
    # turbulence of 0.073 kept as 0.1). A NULL is never checked: a format may read an always empty field back as text
    # (GeoJSON).
    # A CSV keeps no field types: the result fields written into it come back as text, and the next results are
    # written as text too, as before, when the text reads back as the same number.
    csv_text = layer.dataProvider().storageType() == "CSV"

    def keeps(name: str, kind: Any, value: Any) -> bool:
        field = fields.field(name)
        if csv_text and int(field.type()) == QVariant.String and isinstance(value, (int, float)) and not isinstance(value, bool):
            return _text_keeps_number(field, value)
        return int(field.type()) in _LOSSLESS_TYPES[kind] and _keeps_value(field, value)

    changed = [
        n for n, t in _RESULT_FIELDS
        if n in existing and any(values[n] is not None and not keeps(n, t, values[n]) for values in updates.values())
    ]
    if changed:
        raise RuntimeError(log_text(
            "[Layer] Los campos de resultados {fields} de la capa '{layer}' no guardarían los valores tal cual (otro tipo, menos decimales o un texto más corto): no se han escrito los resultados.",
            fields=", ".join(changed), layer=layer.name(),
        ))

    if updates:
        to_add = [QgsField(n, t) for (n, t) in _RESULT_FIELDS if n not in existing]
        # What the existing result fields hold, to tell whether a provider without transactions (MapInfo) kept part of
        # a write that then fails.
        kept = [n for n in field_names if n in existing]
        before = _provider_values(layer, list(updates), kept) if kept else {}

        def apply() -> bool:
            # The fields and the values in one session: a failure is rolled back (see _commit for what may be left).
            if not all(layer.addAttribute(field) for field in to_add):
                return False
            fields = layer.fields()
            # skipDefaultValues: the layer's default values applied on update must not rewrite the results or other fields.
            return all(
                layer.changeAttributeValues(fid, {fields.indexFromName(k): v for k, v in values.items()}, {}, True)
                for fid, values in updates.items()
            )

        try:
            _commit(layer, apply, log_text("[Layer] No se pudieron escribir los resultados en la capa '{layer}'.", layer=layer.name()))
            # Some formats shorten the names (a shapefile keeps 10 characters): the results would be in other fields.
            missing = [n for n in field_names if layer.fields().indexFromName(n) < 0]
            if missing:
                raise RuntimeError(log_text(
                    "[Layer] La capa '{layer}' no admite los campos de resultados con su nombre completo ({fields}): no se han escrito los resultados.",
                    layer=layer.name(), fields=", ".join(missing),
                ))
        except Exception as exc:
            # Rolling back the edit does not undo what a provider without transactions already did. Nothing is removed
            # or written back: what was read before cannot tell this call's changes from those another layer on the
            # same table made since, which may be the user's. What may be left is reported instead.
            provider = layer.dataProvider()
            error = exc.args[0] if exc.args and isinstance(exc.args[0], LogText) else str(exc)
            failed = False
            layer.updateFields()
            left = [f.name() for f in provider.fields() if f.name() not in provider_before and f.name() in field_names]
            if left:
                failed = True
                error = log_text(
                    "{error} Además, la capa '{layer}' tiene ahora los campos de resultados {fields}, que pueden tener valores a medias.",
                    error=error, layer=layer.name(), fields=", ".join(left),
                )
            changed = [
                fid for fid, vals in _provider_values(layer, list(before), kept).items() if not _same_values(vals, before[fid])
            ] if before else []
            if changed:
                failed = True
                error = log_text(
                    "{error} Además, {count} punto(s) de la capa '{layer}' pueden tener resultados escritos a medias: revísalos.",
                    error=error, count=len(changed), layer=layer.name(),
                )
            if failed:
                raise RuntimeError(error) from exc
            raise
        layer.triggerRepaint()

    layer.setMapTipTemplate(_map_tip_v2(layer) if _RESULT_FIELDS is _RESULT_FIELDS_V2 else """
    <style>body{font-family:sans-serif}.k{color:#555}</style>
    <b>Aerogenerador</b><br/>
    <span class='k'>Modelo</span>: [% "model" %]<br/>
    <span class='k'>AEP</span>: [% round("aep_mwh",0) %] MWh/año<br/>
    <span class='k'>Rendimiento dentro del modelo</span>: [% round("model_perf_pct",1) %]%<br/>
    <span class='k'>Posición dentro del modelo</span>: [% "model_rank" %]<br/>
    <span class='k'>Pérdida por estelas</span>: [% round("loss_wake_mwh",0) %] MWh
    ([% round("loss_wake_pct",1) %]%)<br/>
    <span class='k'>Impacto TI/turbulencia</span>: [% coalesce(round("ti_impact_mwh",0), 'n/d') %] MWh
    ([% coalesce(round("ti_impact_pct",1), 'n/d') %]%)<br/>
    <span class='k'>Pérdida por bloqueo</span>: [% coalesce(round("loss_blk_mwh",0), 'n/d') %] MWh
    ([% coalesce(round("loss_blk_pct",1), 'n/d') %]%)<br/>
    <span class='k'>AEP (sólo estela)</span>: [% coalesce(round("aep_wake_only_mwh",0), 'n/d') %] MWh<br/>
    <span class='k'>AEP (estela+TI)</span>: [% coalesce(round("aep_wake_ti_mwh",0), 'n/d') %] MWh<br/>
    <span class='k'>AEP (estela+bloqueo)</span>: [% coalesce(round("aep_wake_blk_mwh",0), 'n/d') %] MWh<br/>
    <span class='k'>AEP (estela+TI+bloqueo)</span>: [% coalesce(round("aep_wake_ti_blk_mwh",0), 'n/d') %] MWh<br/>
    <span class='k'>TI efectiva</span>: [% coalesce(round("ti_eff",3), 'n/d') %]
    """)
    return len(updates)



# The map tip of schema 2: each entity is read with the fields of its own schema. One with results of schema 2
# (``res_schema`` = 2) shows the signed breakdown and its states; one without them in a partially recalculated layer
# (outside the resource, #43) shows the fields of the previous schema it kept, labelled as such, never mixed.
# (label, field, decimals, unit, field of its percentage)
_TIP_V2_LINES = (
    ("AEP neto", "aep_mwh", 0, " MWh/año", None), ("AEP bruto (A_0)", "aep_free_mwh", 0, " MWh/año", None),
    ("Rendimiento dentro del modelo", "model_perf_pct", 1, "%", None), ("Posición dentro del modelo", "model_rank", 0, "", None),
    ("Pérdida por estelas (L_W)", "l_wake_mwh", 0, " MWh", "l_wake_pct"),
    ("Impacto de la turbulencia (Δ_T)", "d_turb_mwh", 0, " MWh", "d_turb_pct"),
    ("Impacto del bloqueo (Δ_B)", "d_blk_mwh", 0, " MWh", "d_blk_pct"),
    ("Pérdida total", "l_total_mwh", 0, " MWh", "l_total_pct"),
    ("TI ambiente", "ti_ambient", 3, "", None), ("TI efectiva", "ti_effective", 3, "", None),
)
# Every field of the previous map tip (schema 1), for an entity that kept them.
_TIP_V1_LINES = (
    ("AEP", "aep_mwh", 0, " MWh/año", None),
    ("Rendimiento dentro del modelo", "model_perf_pct", 1, "%", None), ("Posición dentro del modelo", "model_rank", 0, "", None),
    ("Pérdida por estelas", "loss_wake_mwh", 0, " MWh", "loss_wake_pct"),
    ("Impacto TI/turbulencia", "ti_impact_mwh", 0, " MWh", "ti_impact_pct"),
    ("Pérdida por bloqueo", "loss_blk_mwh", 0, " MWh", "loss_blk_pct"),
    ("AEP (sólo estela)", "aep_wake_only_mwh", 0, " MWh", None), ("AEP (estela+TI)", "aep_wake_ti_mwh", 0, " MWh", None),
    ("AEP (estela+bloqueo)", "aep_wake_blk_mwh", 0, " MWh", None),
    ("AEP (estela+TI+bloqueo)", "aep_wake_ti_blk_mwh", 0, " MWh", None), ("TI efectiva", "ti_eff", 3, "", None),
)


def _map_tip_v2(layer: QgsVectorLayer) -> str:
    try:
        from ...i18n import tr_text as tr
    except Exception:  # without the plugin's language layer, the source texts
        def tr(text):
            return text

    # The value not available and the units, translated as the labels (the template is not translated again).
    missing = tr("n/d").replace("'", "''")

    def lines(spec, condition):
        out = []
        for label, field, decimals, unit, pct in spec:
            if layer.fields().indexFromName(field) < 0:
                continue
            text = tr(label).replace("'", "''")
            unit = (" " + tr(unit.strip()) if unit.startswith(" ") else unit).replace("'", "''")
            pct_text = ""
            if pct and layer.fields().indexFromName(pct) >= 0:
                pct_text = f" || ' (' || coalesce(to_string(round(\"{pct}\", 1)), '{missing}') || '%)'"
            out.append(f"[% CASE WHEN {condition} THEN '<span class=''k''>{text}</span>: ' || "
                       f"coalesce(to_string(round(\"{field}\", {decimals})), '{missing}') || '{unit}'{pct_text} || "
                       f"'<br/>' ELSE '' END %]")
        return "\n    ".join(out)

    old = lines(_TIP_V1_LINES, '"res_schema" IS NULL') if any(
        layer.fields().indexFromName(n) >= 0 for n in OLD_SCHEMA_FIELDS) else ""
    old_title = tr("Resultados del esquema anterior (sus pérdidas siguen la definición antigua):").replace("'", "''")
    old_header = ("[% CASE WHEN \"res_schema\" IS NULL THEN '<i>" + old_title + "</i><br/>' ELSE '' END %]"
                  if old else "")
    states = tr("Estados").replace("'", "''")
    return f"""
    <style>body{{font-family:sans-serif}}.k{{color:#555}}</style>
    <b>{tr("Aerogenerador")}</b><br/>
    <span class='k'>{tr("Modelo")}</span>: [% "model" %]<br/>
    {lines(_TIP_V2_LINES, '"res_schema" = 2')}
    [% CASE WHEN "res_schema" = 2 THEN '<span class=''k''>{states}</span>: ' || coalesce("wake_states", '{missing}') ELSE '' END %]
    {old_header}
    {old}
    """


def _decorate_model_rows(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Add relative performance and rank within one turbine model."""
    valid = []
    for row in rows:
        try:
            value = float(row.get("aep_mwh"))
        except (TypeError, ValueError):
            continue
        if math.isfinite(value):  # #63: a non-finite value keeps its value, outside the ranking
            valid.append((value, row))

    if not valid:
        return rows

    best = max(value for value, _row in valid)
    ordered = sorted(valid, key=lambda item: item[0], reverse=True)
    rank_by_id = {id(row): rank for rank, (_value, row) in enumerate(ordered, start=1)}

    for value, row in valid:
        row["model_perf_pct"] = (100.0 * value / best) if best > 0.0 else 100.0
        row["model_rank"] = rank_by_id[id(row)]
    return rows


def apply_energy_renderer(layer: QgsVectorLayer, field_name: str = "aep_mwh") -> bool:
    """Style a turbine point layer by individual AEP, independently per model layer."""
    if layer is None or layer.fields().indexFromName(field_name) < 0:
        return False

    values = []
    has_non_finite = False
    for feat in layer.getFeatures():
        try:
            value = float(feat[field_name])
        except (TypeError, ValueError, KeyError):
            continue
        if math.isfinite(value):  # #63: a non-finite value is kept, outside the classes of the renderer
            values.append(value)
        else:
            has_non_finite = True
    if not values:
        return False

    vmin, vmax = min(values), max(values)
    base = QgsMarkerSymbol.createSimple({
        "name": "circle",
        "size": "4.2",
        "outline_width": "0.35",
        "outline_color": "45,45,45,220",
    })

    if abs(vmax - vmin) < 1e-9:
        layer.setRenderer(QgsSingleSymbolRenderer(base))
        layer.setCustomProperty("velantis/energy_renderer", "per_model_aep_single_value")
        layer.setCustomProperty("velantis/energy_renderer_field", field_name)
        layer.triggerRepaint()
        return True

    # A field kept as text (a CSV) would be classified in text order, leaving turbines without a symbol.
    attribute = field_name if layer.fields().field(field_name).isNumeric() else f'to_real("{field_name}")'
    renderer = QgsGraduatedSymbolRenderer(attribute, [])
    renderer.setSourceSymbol(base)
    try:
        ramp = QgsStyle.defaultStyle().colorRamp("RdYlGn")
        if ramp is not None:
            renderer.setSourceColorRamp(ramp)
    except Exception:  # nosec B110
        pass

    # Five equal-interval classes are stable and easy to interpret for screening. With a non-finite value (#63), the
    # classes come from the finite ones: QGIS would classify the layer with it.
    try:
        if has_non_finite:
            raise ValueError("non-finite values")
        renderer.updateClasses(layer, QgsGraduatedSymbolRenderer.EqualInterval, 5)
    except Exception:
        step = (vmax - vmin) / 5.0
        ranges = []
        for i in range(5):
            lower = vmin + i * step
            upper = vmax if i == 4 else vmin + (i + 1) * step
            symbol = base.clone()
            ranges.append(QgsRendererRange(lower, upper, symbol, f"{lower:,.0f}–{upper:,.0f} MWh/año"))
        source_ramp = renderer.sourceColorRamp()
        source_ramp = None if source_ramp is None else source_ramp.clone()  # before the renderer that owns it goes
        renderer = QgsGraduatedSymbolRenderer(field_name, ranges)
        if source_ramp is not None:  # the same colours as the classes of QGIS (with #63 this path is ordinary)
            renderer.setSourceColorRamp(source_ramp)

    try:
        renderer.updateColorRamp(renderer.sourceColorRamp())
    except Exception:  # nosec B110
        pass
    layer.setRenderer(renderer)
    layer.setCustomProperty("velantis/energy_renderer", "per_model_aep")
    layer.setCustomProperty("velantis/energy_renderer_field", field_name)
    layer.triggerRepaint()
    return True

def find_layer_by_name(name: str) -> Optional[QgsVectorLayer]:
    for lyr in QgsProject.instance().mapLayers().values():
        if isinstance(lyr, QgsVectorLayer) and lyr.name() == name:
            return lyr
    return None


def update_layers_from_results(
    per_turbine_table: List[Dict[str, Any]],
    models: List[Dict[str, Any]],
    tol_m: float = 30.0,
    log: Optional[Callable[..., None]] = None,
    warning_level: Any = None,
) -> List[str]:
    """
    Push per-turbine AEP results into the layer each model was computed with (``source_layer_id``).

    A layer that is missing or cannot take the results is skipped with a warning, and so is one where no result
    matches a point: a failure here never stops the calculation. Returns the names of the updated layers.
    """
    warning = warning_level or Qgis.Warning
    by_model: Dict[str, List[Dict[str, Any]]] = {}
    for row in per_turbine_table:
        by_model.setdefault(row["model"], []).append(row)

    updated: List[str] = []
    # A layer computed in several rows keeps the turbine data of the first one, which the spacing ellipses read,
    # whatever happens to its results; the results are the last row's.
    first_model = {}
    for i, m in enumerate(models):
        first_model.setdefault(str(m.get("source_layer_id") or ""), i)
    # Every layer's points, read before any result is written: a write may change what a layer shows (a filter on a
    # result field, also through another layer on the same table), and each result must find the point it was
    # computed on, not a neighbour that is still visible. A point deleted while the results are being written (by
    # code reacting to a commit) is still counted as written: telling it from a point hidden by the filter would mean
    # reading the layer without the user's filter.
    snapshots: Dict[str, Any] = {}
    for m in models:
        layer = QgsProject.instance().mapLayer(str(m.get("source_layer_id") or ""))
        if isinstance(layer, QgsVectorLayer) and layer.id() not in snapshots:
            try:
                snapshots[layer.id()] = layer_points_in_project_crs(layer)[0]
            except Exception as exc:
                snapshots[layer.id()] = exc
    for i, m in enumerate(models):
        name = m.get("name") or "Custom WT"
        layer_id = str(m.get("source_layer_id") or "")
        layer = QgsProject.instance().mapLayer(layer_id) if layer_id else None
        if not isinstance(layer, QgsVectorLayer):
            _emit(log, log_text("[Layer] No se encontró la capa '{layer}'. ¿Está cargada?", layer=m.get("source_layer_name") or name), warning)
            continue

        model_rows = _decorate_model_rows(by_model.get(name, []))
        try:
            points = snapshots.get(layer.id())
            if isinstance(points, Exception):
                raise points
            written = push_results_to_point_layer(layer, model_rows, tol_m=tol_m, points=points)
        except Exception as exc:  # a layer that cannot take the results never stops the others or the AEP
            reason = exc.args[0] if exc.args and isinstance(exc.args[0], LogText) else log_text(
                "[Layer] No se pudieron escribir los resultados en la capa '{layer}': {error}", layer=layer.name(), error=str(exc) or type(exc).__name__,
            )
            _emit(log, reason, warning)
            continue
        if not written:
            _emit(log, log_text(
                "[Layer] Ningún resultado de '{model}' está a {tol} m o menos de un punto de la capa '{layer}': no se ha escrito nada.",
                model=name, tol=f"{tol_m:g}", layer=layer.name(),
            ), warning)
            continue
        if written < len(model_rows):
            _emit(log, log_text(
                "[Layer] Solo se han escrito {written} de {total} resultados en la capa '{layer}'; sus otros puntos conservan los valores anteriores.",
                written=written, total=len(model_rows), layer=layer.name(),
            ), warning)
        old = [n for n in OLD_SCHEMA_FIELDS if layer.fields().indexFromName(n) >= 0]
        if old and result_fields(model_rows) is _RESULT_FIELDS_V2:
            _emit(log, log_text(
                "[Layer] La capa '{layer}' conserva campos de resultados del esquema anterior ({fields}), que ya no se actualizan: los resultados nuevos están en sus propios campos.",
                layer=layer.name(), fields=", ".join(old),
            ), warning)

        try:
            apply_energy_renderer(layer, field_name="aep_mwh")
        except Exception:  # nosec B110
            pass
        if first_model.get(layer.id()) == i:
            try:
                meta = m.get("meta") if isinstance(m, dict) else None
                layer.setCustomProperty("velantis/model_name", str(name))
                if isinstance(meta, dict):
                    if meta.get("hh") is not None:
                        layer.setCustomProperty("velantis/hub_height_m", float(meta.get("hh")))
                    if meta.get("diam") is not None:
                        layer.setCustomProperty("velantis/diameter_m", float(meta.get("diam")))
                    if meta.get("spacing_long_d") is not None:
                        layer.setCustomProperty("velantis/spacing_long_d", float(meta.get("spacing_long_d")))
                    if meta.get("spacing_trans_d") is not None:
                        layer.setCustomProperty("velantis/spacing_trans_d", float(meta.get("spacing_trans_d")))
                    if meta.get("curve_quality"):
                        layer.setCustomProperty("velantis/curve_quality", str(meta.get("curve_quality")))
                    if meta.get("curve_source"):
                        layer.setCustomProperty("velantis/curve_source", str(meta.get("curve_source")))
                    if meta.get("curve_source_url"):
                        layer.setCustomProperty("velantis/curve_source_url", str(meta.get("curve_source_url")))
                csv_path = (m.get("coords_csv") or "").strip() if isinstance(m, dict) else ""
                if csv_path:
                    layer.setCustomProperty("velantis/coords_csv", str(csv_path))
            except Exception:  # nosec B110
                pass
        updated.append(layer.name())

    if updated:
        _emit(log, f"Capas actualizadas: {', '.join(updated)}")
    return updated


__all__ = [
    "ensure_result_fields",
    "push_results_to_point_layer",
    "find_layer_by_name",
    "apply_energy_renderer",
    "update_layers_from_results",
]

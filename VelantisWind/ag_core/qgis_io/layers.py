# -*- coding: utf-8 -*-
"""QGIS layer writers for AEP per-turbine results.

Keeping this code outside the solver makes the AEP computation easier to test
and keeps all QGIS-specific attribute/map-tip logic in one place.
"""
from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional

from qgis.PyQt.QtCore import QVariant
from qgis.core import (
    Qgis,
    QgsProject,
    QgsVectorLayer,
    QgsField,
    QgsGeometry,
    QgsWkbTypes,
    QgsPointXY,
    QgsSpatialIndex,
    QgsFeatureRequest,
    QgsGraduatedSymbolRenderer,
    QgsRendererRange,
    QgsMarkerSymbol,
    QgsSingleSymbolRenderer,
    QgsStyle,
    edit,
)

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


def _emit(log: Optional[Callable[..., None]], msg: str, level: Any = None) -> None:
    if log is not None:
        try:
            log(msg, level)
        except TypeError:
            log(msg)
        except Exception:
            pass


def ensure_result_fields(layer: QgsVectorLayer) -> None:
    """Ensure that the target point layer has all AEP result attributes."""
    prov = layer.dataProvider()
    existing = {f.name(): i for i, f in enumerate(layer.fields())}
    with edit(layer):
        to_add = [QgsField(n, t) for (n, t) in _RESULT_FIELDS if n not in existing]
        if to_add:
            prov.addAttributes(to_add)
            layer.updateFields()


def push_results_to_point_layer(layer: QgsVectorLayer, per_turbine_table: List[Dict[str, Any]], tol_m: float = 30.0) -> None:
    """
    Match each result row (x, y) with the nearest point feature and write AEP fields.
    """
    if layer is None or QgsWkbTypes.geometryType(layer.wkbType()) != QgsWkbTypes.PointGeometry:
        raise RuntimeError("Proporciona una capa de puntos válida.")

    ensure_result_fields(layer)
    sidx = QgsSpatialIndex(layer.getFeatures())
    updates: Dict[int, Dict[int, Any]] = {}

    field_names = [name for name, _typ in _RESULT_FIELDS]
    for row in per_turbine_table:
        pt = QgsPointXY(row["x"], row["y"])
        near_ids = sidx.nearestNeighbor(pt, 1)
        if not near_ids:
            continue
        fid = near_ids[0]
        feat = next(layer.getFeatures(QgsFeatureRequest(fid)))
        dist = feat.geometry().distance(QgsGeometry.fromPointXY(pt))
        if dist > tol_m:
            continue

        attrs = {}
        for key in field_names:
            idx_field = layer.fields().indexFromName(key)
            if idx_field >= 0:
                attrs[idx_field] = row.get(key, None)
        if attrs:
            updates[fid] = attrs

    if updates:
        with edit(layer):
            layer.dataProvider().changeAttributeValues(updates)
        layer.triggerRepaint()

    layer.setMapTipTemplate("""
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



def _decorate_model_rows(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Add relative performance and rank within one turbine model."""
    valid = []
    for row in rows:
        try:
            value = float(row.get("aep_mwh"))
        except (TypeError, ValueError):
            continue
        if value == value:  # not NaN
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
    for feat in layer.getFeatures():
        try:
            value = float(feat[field_name])
        except (TypeError, ValueError, KeyError):
            continue
        if value == value:
            values.append(value)
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

    renderer = QgsGraduatedSymbolRenderer(field_name, [])
    renderer.setSourceSymbol(base)
    try:
        ramp = QgsStyle.defaultStyle().colorRamp("RdYlGn")
        if ramp is not None:
            renderer.setSourceColorRamp(ramp)
    except Exception:
        pass

    # Five equal-interval classes are stable and easy to interpret for screening.
    try:
        renderer.updateClasses(layer, QgsGraduatedSymbolRenderer.EqualInterval, 5)
    except Exception:
        step = (vmax - vmin) / 5.0
        ranges = []
        for i in range(5):
            lower = vmin + i * step
            upper = vmax if i == 4 else vmin + (i + 1) * step
            symbol = base.clone()
            ranges.append(QgsRendererRange(lower, upper, symbol, f"{lower:,.0f}–{upper:,.0f} MWh/año"))
        renderer = QgsGraduatedSymbolRenderer(field_name, ranges)

    try:
        renderer.updateColorRamp(renderer.sourceColorRamp())
    except Exception:
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
    Find '<Modelo> (CSV)' layers and push per-turbine AEP results into them.
    Missing layers are skipped rather than treated as fatal.
    """
    by_model: Dict[str, List[Dict[str, Any]]] = {}
    for row in per_turbine_table:
        by_model.setdefault(row["model"], []).append(row)

    updated: List[str] = []
    for m in models:
        name = m.get("name") or "Custom WT"
        layer_name = f"{name} (CSV)"
        layer = find_layer_by_name(layer_name)
        if layer is None:
            _emit(log, f"[Layer] No se encontró la capa '{layer_name}'. ¿Está cargada?", warning_level or Qgis.Warning)
            continue

        model_rows = _decorate_model_rows(by_model.get(name, []))
        push_results_to_point_layer(layer, model_rows, tol_m=tol_m)
        apply_energy_renderer(layer, field_name="aep_mwh")
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
        except Exception:
            pass
        updated.append(layer_name)

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

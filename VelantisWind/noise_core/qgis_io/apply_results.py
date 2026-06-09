# -*- coding: utf-8 -*-
"""Apply background noise-task results to QGIS layers on the main thread."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from qgis.PyQt.QtCore import QVariant
from qgis.core import QgsFeature, QgsField, QgsFields, QgsGeometry, QgsProject, QgsRasterLayer, QgsVectorLayer

from ..noise_common import NoiseSource, NoiseReceiver
from ..results.evaluator import build_receiver_output_fields
from ..results.summary import extract_result_layer_statistics
from ..results.payload import build_noise_result_payload
from .common import _remove_existing_layers_by_name, _set_field_aliases
from .layers import (
    _build_source_layer,
    _build_dominant_links_layer,
    _build_uncovered_receivers_layer,
    _apply_raster_heatmap_style,
    _build_isophones_layer_from_raster,
)


def _input_fields_from_specs(field_specs: List[Dict[str, Any]]) -> QgsFields:
    fields = QgsFields()
    for spec in field_specs or []:
        try:
            fields.append(QgsField(
                str(spec.get("name") or "field"),
                int(spec.get("type", QVariant.String)),
                str(spec.get("type_name") or ""),
                int(spec.get("length", 0)),
                int(spec.get("precision", 0)),
            ))
        except Exception:
            fields.append(QgsField(str(spec.get("name") or "field"), QVariant.String))
    return fields


def _source_objects(snapshot: Dict[str, Any]) -> List[NoiseSource]:
    out: List[NoiseSource] = []
    for src in snapshot.get("sources") or []:
        try:
            out.append(NoiseSource(
                model_name=str(src.get("model_name") or ""),
                source_group=str(src.get("source_group") or ""),
                park_name=str(src.get("park_name") or ""),
                x=float(src.get("x") or 0.0),
                y=float(src.get("y") or 0.0),
                hub_height=float(src.get("hub_height") or 0.0),
                diameter=None if src.get("diameter") is None else float(src.get("diameter")),
                lwa=float(src.get("lwa") or 0.0),
                feature_id=int(src.get("feature_id") or -1),
                layer_name=str(src.get("layer_name") or ""),
                z_ground=None if src.get("z_ground") is None else float(src.get("z_ground")),
                lw_octave={int(k): float(v) for k, v in ((src.get("lw_octave") or {}).items())},
                spectrum_source=str(src.get("spectrum_source") or ""),
            ))
        except Exception:
            continue
    return out


def _receiver_objects(snapshot: Dict[str, Any]) -> List[NoiseReceiver]:
    out: List[NoiseReceiver] = []
    for rec in snapshot.get("receivers") or []:
        try:
            geom = QgsGeometry.fromWkt(str(rec.get("geometry_wkt") or ""))
            if geom is None or geom.isEmpty():
                geom = QgsGeometry()
            out.append(NoiseReceiver(
                feature_id=int(rec.get("feature_id") or -1),
                x=float(rec.get("x") or 0.0),
                y=float(rec.get("y") or 0.0),
                z_ground=None if rec.get("z_ground") is None else float(rec.get("z_ground")),
                receiver_height=float(rec.get("receiver_height") or 0.0),
                eval_mode=str(rec.get("eval_mode") or "point"),
                geometry=geom,
                attrs=list(rec.get("attrs") or []),
                meta=dict(rec.get("meta") or {}),
            ))
        except Exception:
            continue
    return out


def _add_grid_layer_from_diag(prj: QgsProject, diag: Dict[str, Any], layer_name: str, iso_layer_name: str, create_iso: bool, iso_levels: List[float]):
    grid_layer = None
    iso_layer = None
    raster_path = str((diag or {}).get("grid_path") or "")
    if not raster_path:
        return None, None
    _remove_existing_layers_by_name(prj, [layer_name] + ([iso_layer_name] if create_iso else []))
    lyr = QgsRasterLayer(raster_path, layer_name)
    if lyr.isValid():
        try:
            lyr.setCustomProperty("velantis/noise_output", True)
        except Exception:
            pass
        try:
            min_val = float(diag.get("grid_min_noise", 0.0))
            max_val = float(diag.get("grid_max_noise", 0.0))
            if max_val > min_val:
                _apply_raster_heatmap_style(lyr, min_val, max_val)
        except Exception:
            pass
        prj.addMapLayer(lyr)
        grid_layer = lyr
        try:
            from qgis.utils import iface
            if iface is not None:
                try:
                    iface.layerTreeView().refreshLayerSymbology(lyr.id())
                except Exception:
                    pass
                try:
                    iface.mapCanvas().refreshAllLayers()
                except Exception:
                    iface.mapCanvas().refresh()
        except Exception:
            pass
        if create_iso:
            iso_layer = _build_isophones_layer_from_raster(prj, raster_path, iso_levels or [35.0, 40.0, 45.0, 50.0], iso_layer_name)
    return grid_layer, iso_layer



def _rows_as_dicts(out_fields: QgsFields, rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Convert primitive task rows to field-name dictionaries for UI fallbacks."""
    names: List[str] = []
    try:
        for i in range(out_fields.count()):
            names.append(out_fields.at(i).name())
    except Exception:
        names = []
    out: List[Dict[str, Any]] = []
    for row in rows or []:
        # Newer background tasks provide a named summary for the UI/report.
        # Prefer it over rebuilding dictionaries from the raw attrs vector; that
        # vector is only for the QGIS memory layer and is vulnerable to field
        # order/schema changes.
        summary = row.get("summary") if isinstance(row, dict) else None
        if isinstance(summary, dict) and summary:
            d = dict(summary)
        else:
            attrs = list(row.get("attrs") or [])
            d: Dict[str, Any] = {}
            for i, name in enumerate(names):
                if i < len(attrs):
                    d[name] = attrs[i]
        try:
            fid = int(row.get("feature_id", -1))
        except Exception:
            fid = -1
        d.setdefault("fid", fid)
        d.setdefault("rec_id", fid)
        d.setdefault("geometry_wkt", str(row.get("geometry_wkt") or ""))
        out.append(d)
    def _noise(d: Dict[str, Any]) -> float:
        try:
            return float(d.get("noise_dba") or 0.0)
        except Exception:
            return -1.0e99
    out.sort(key=_noise, reverse=True)
    return out


def _stats_from_row_dicts(rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    def _f(d: Dict[str, Any], key: str, default=None):
        try:
            v = d.get(key, default)
            return default if v is None else float(v)
        except Exception:
            return default
    adiv_vals: List[float] = []
    aatm_vals: List[float] = []
    aground_vals: List[float] = []
    abar_vals: List[float] = []
    for d in rows or []:
        try:
            covered = int(d.get("covered", 0) or 0) == 1
        except Exception:
            covered = (_f(d, "noise_dba", 0.0) or 0.0) > 0.0
        if not covered:
            continue
        for key, target in (("adiv_db", adiv_vals), ("aatm_db", aatm_vals), ("aground_db", aground_vals)):
            v = _f(d, key, None)
            if v is not None and v == v:
                target.append(float(v))
        vabar = _f(d, "abar_max_db", _f(d, "abar_db", None))
        if vabar is not None and vabar == vabar:
            abar_vals.append(float(vabar))
    return {
        "adiv_vals": adiv_vals,
        "aatm_vals": aatm_vals,
        "aground_vals": aground_vals,
        "abar_vals": abar_vals,
        "critical_receiver": dict(rows[0]) if rows else None,
    }

def apply_noise_task_result(snapshot: Dict[str, Any], task_result: Dict[str, Any]) -> Dict[str, Any]:
    """Create QGIS output layers and payload from a completed background task."""
    prj = QgsProject.instance()
    params = dict(snapshot.get("params") or {})
    eval_res = dict(task_result.get("evaluation") or {})
    grid_diag = dict(task_result.get("grid_diag") or {})

    result_layer_name = str(params.get("result_layer_name") or "Noise · Receivers")
    sources_layer_name = str(params.get("sources_layer_name") or "Noise · Sources")
    links_layer_name = str(params.get("links_layer_name") or "Noise · Dominant links")
    uncovered_layer_name = str(params.get("uncovered_layer_name") or "Noise · Receivers outside radius")
    grid_layer_name = str(params.get("grid_layer_name") or "Noise · Map")
    iso_layer_name = str(params.get("iso_layer_name") or "Noise · Isophones")

    names_to_remove = [result_layer_name, uncovered_layer_name]
    if bool(params.get("create_sources_layer", True)):
        names_to_remove.append(sources_layer_name)
    if bool(params.get("create_links_layer", True)):
        names_to_remove.append(links_layer_name)
    if bool(params.get("create_grid_layer", False)):
        names_to_remove.append(grid_layer_name)
    if bool(params.get("create_iso_layer", False)):
        names_to_remove.append(iso_layer_name)
    _remove_existing_layers_by_name(prj, names_to_remove)

    input_fields = _input_fields_from_specs(snapshot.get("field_specs") or [])
    out_fields = build_receiver_output_fields(input_fields)
    geom_type = str(snapshot.get("geometry_type") or "Point")
    crs_authid = str(snapshot.get("crs_authid") or prj.crs().authid() or "EPSG:25830")
    result = QgsVectorLayer(f"{geom_type}?crs={crs_authid}", result_layer_name, "memory")
    pr = result.dataProvider()
    pr.addAttributes(out_fields)
    result.updateFields()

    out_feats: List[QgsFeature] = []
    for row in eval_res.get("rows") or []:
        try:
            feat = QgsFeature(out_fields)
            geom = QgsGeometry.fromWkt(str(row.get("geometry_wkt") or ""))
            if geom is not None and not geom.isEmpty():
                feat.setGeometry(geom)
            attrs = list(row.get("attrs") or [])
            try:
                n_fields = int(out_fields.count())
            except Exception:
                try:
                    n_fields = len(out_fields)
                except Exception:
                    n_fields = len(attrs)
            if len(attrs) < n_fields:
                attrs.extend([None] * (n_fields - len(attrs)))
            elif len(attrs) > n_fields:
                attrs = attrs[:n_fields]
            feat.setAttributes(attrs)
            out_feats.append(feat)
        except Exception:
            continue
    pr.addFeatures(out_feats)
    try:
        result.setCustomProperty("velantis/noise_output", True)
    except Exception:
        pass
    prj.addMapLayer(result)
    _set_field_aliases(result, {
        'noise_dba':'total_level_dba','n_src':'turbines_in_radius','near_m':'nearest_turbine_m',
        'max_src_dba':'dominant_contribution_dba','dom_model':'modelo_dominante','dom_group':'grupo_fuente_dominante','dom_park':'parque_dominante','src_lwa':'lwa_fuente_dom_dba',
        'dist3d_m':'dist_fuente_dom_3d_m','adiv_db':'divergence_loss_db','aatm_db':'atmospheric_loss_db',
        'aground_db':'ground_loss_db','abar_db':'barrier_loss_dominant_path_db','abar_max_db':'barrier_loss_max_contributors_db','abar_mean_db':'barrier_loss_mean_contributors_db','abar_ew_db':'barrier_loss_energy_weighted_db','abar_screen_n':'screened_contributing_turbines','abar_state':'mdt_screening_state','obs_h_m':'mdt_obstacle_height_m','obs_d1_m':'source_obstacle_distance_m','obs_d2_m':'obstacle_receiver_distance_m','obs_thr_m':'mdt_activation_threshold_m','src_z_m':'dominant_source_ground_z_m','hub_h_m':'dominant_source_hub_height_m','src_ac_z_m':'dominant_source_acoustic_z_m','rec_z_m':'receiver_ground_z_m','rec_h_m':'receiver_height_agl_m','rec_ac_z_m':'receiver_acoustic_z_m','maxab_src':'max_abar_source_index','maxab_state':'max_abar_mdt_state','maxab_obs_h':'max_abar_obstacle_height_m','maxab_thr':'max_abar_threshold_m','maxab_d1':'max_abar_source_obstacle_m','maxab_d2':'max_abar_obstacle_receiver_m','maxab_src_z':'max_abar_source_ground_z_m','maxab_hub_h':'max_abar_source_hub_height_m','maxab_src_ac_z':'max_abar_source_acoustic_z_m','maxobs_src':'max_obstacle_source_index','maxobs_state':'max_obstacle_mdt_state','maxobs_h':'max_obstacle_height_m','maxobs_thr':'max_obstacle_threshold_m','maxobs_d1':'max_obstacle_source_obstacle_m','maxobs_d2':'max_obstacle_obstacle_receiver_m','maxobs_src_z':'max_obstacle_source_ground_z_m','maxobs_hub_h':'max_obstacle_source_hub_height_m','maxobs_src_ac_z':'max_obstacle_source_acoustic_z_m','ground_g':'ground_factor_g','dom_freq':'dominant_band_hz','spec_src':'spectrum_source','limit_dba':'receiver_limit_dba','margin_db':'limit_margin_db','exceeds':'exceeds_limit','limit_src':'limit_source','limit_scn':'limit_scenario','limit_fld':'limit_field','rec_type':'receiver_type','src_layer':'receiver_source_layer','dom_src_lyr':'dominant_source_layer','state':'compliance_state','ground_md':'ground_mode'})

    sources = _source_objects(snapshot)
    receivers = _receiver_objects(snapshot)
    src_stats = {int(k): v for k, v in (eval_res.get("src_stats") or {}).items()}
    src_layer = _build_source_layer(prj, sources, src_stats, sources_layer_name) if bool(params.get("create_sources_layer", True)) else None
    link_layer = _build_dominant_links_layer(prj, list(eval_res.get("dom_links") or []), links_layer_name) if bool(params.get("create_links_layer", True)) else None
    uncovered_layer = _build_uncovered_receivers_layer(prj, receivers, list(eval_res.get("uncovered_ids") or []), uncovered_layer_name)

    grid_layer = None
    iso_layer = None
    if bool(params.get("create_grid_layer", False)) and grid_diag.get("grid_path"):
        grid_layer, iso_layer = _add_grid_layer_from_diag(
            prj,
            grid_diag,
            grid_layer_name,
            iso_layer_name,
            bool(params.get("create_iso_layer", False)),
            list(params.get("iso_levels") or [35.0, 40.0, 45.0, 50.0]),
        )

    layer_stats = extract_result_layer_statistics(result, eval_res.get("max_noise_fid"))
    task_row_dicts = _rows_as_dicts(out_fields, list(eval_res.get("rows") or []))
    task_row_stats = _stats_from_row_dicts(task_row_dicts)
    if not layer_stats.adiv_vals:
        layer_stats.adiv_vals = list(task_row_stats.get("adiv_vals") or [])
    if not layer_stats.aatm_vals:
        layer_stats.aatm_vals = list(task_row_stats.get("aatm_vals") or [])
    if not layer_stats.aground_vals:
        layer_stats.aground_vals = list(task_row_stats.get("aground_vals") or [])
    if not layer_stats.abar_vals:
        layer_stats.abar_vals = list(task_row_stats.get("abar_vals") or [])
    if layer_stats.critical_receiver is None:
        layer_stats.critical_receiver = task_row_stats.get("critical_receiver")

    payload = build_noise_result_payload(
        result=result,
        src_layer=src_layer,
        link_layer=link_layer,
        grid_layer=grid_layer,
        iso_layer=iso_layer,
        uncovered_layer=uncovered_layer,
        sources=sources,
        receivers=receivers,
        src_diag=dict(snapshot.get("src_diag") or {}),
        out_feats=out_feats,
        dom_links=list(eval_res.get("dom_links") or []),
        uncovered_ids=list(eval_res.get("uncovered_ids") or []),
        zero_receivers=int(eval_res.get("zero_receivers", 0)),
        n_exceed=int(eval_res.get("n_exceed", 0)),
        max_noise=float(eval_res.get("max_noise", -1.0)),
        max_noise_fid=eval_res.get("max_noise_fid"),
        grid_diag=grid_diag or {'grid_cells': 0, 'grid_width': 0, 'grid_height': 0, 'requested_resolution_m': float(params.get("grid_resolution_m", 100.0)), 'effective_resolution_m': float(params.get("grid_resolution_m", 100.0)), 'auto_adjusted': False},
        alpha_db_per_m=float(params.get("alpha_db_per_m", 0.005)),
        ground_factor_g=float(params.get("ground_factor_g", 0.5)),
        ground_mode=str(params.get("ground_mode") or "global"),
        active_landuse_layer=None,
        receiver_height_m=float(params.get("receiver_height_m", 4.0)),
        max_radius_m=float(params.get("max_radius_m", 5000.0)),
        dem_layer=_PseudoLayer(str(params.get("dem_name") or "")) if bool(params.get("dem_used")) else None,
        adiv_vals=layer_stats.adiv_vals,
        aatm_vals=layer_stats.aatm_vals,
        aground_vals=layer_stats.aground_vals,
        abar_vals=layer_stats.abar_vals,
        ground_g_values=list(eval_res.get("ground_g_values") or []),
        critical_receiver=layer_stats.critical_receiver,
        ground_from_landuse_count=int(eval_res.get("ground_from_landuse_count", 0)),
        ground_fallback_count=int(eval_res.get("ground_fallback_count", 0)),
        applied_limits=list(eval_res.get("applied_limits") or []),
        receiver_type_counts=dict(eval_res.get("receiver_type_counts") or {}),
        receiver_type_compliance=dict(eval_res.get("receiver_type_compliance") or {}),
        receiver_limit_dba=float(params.get("receiver_limit_dba", 45.0)),
        receiver_limit_mode=str(params.get("receiver_limit_mode") or "global"),
        receiver_limit_scenario=str(params.get("receiver_limit_scenario") or "custom"),
        calculation_engine=str(params.get("calculation_engine") or "fast"),
        temperature_c=float(params.get("temperature_c", 15.0)),
        humidity_percent=float(params.get("humidity_percent", 70.0)),
        pressure_kpa=float(params.get("pressure_kpa", 101.325)),
        model_cfg=dict(params.get("model_cfg") or {}),
        path_diagnostics=list(eval_res.get("path_diagnostics") or []),
    )
    # Keep the complete named receiver payload available for exports.
    # This avoids depending on the QGIS memory-layer provider when extra
    # MDT diagnostic fields are added or when the provider silently creates
    # the schema but no feature rows.
    payload["receiver_rows"] = list(task_row_dicts or [])
    payload["top_receivers"] = list(task_row_dicts[:15])
    payload["path_diagnostics"] = list(eval_res.get("path_diagnostics") or payload.get("path_diagnostics") or [])
    if not payload.get("critical_receiver") and task_row_dicts:
        payload["critical_receiver"] = dict(task_row_dicts[0])
    return payload


class _PseudoLayer:
    """Tiny name() compatible object for report metadata when the original layer is not retained."""
    def __init__(self, name: str):
        self._name = str(name or "")
    def name(self) -> str:
        return self._name

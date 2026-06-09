# -*- coding: utf-8 -*-
"""
Noise calculation façade for the plugin.

This module keeps the stable public noise-calculation entry point and coordinates
source collection, receiver evaluation, raster generation and QGIS outputs through
the refactored ``noise_core`` subpackages.
"""
from __future__ import annotations

import math
from typing import Dict, List, Optional, Tuple
import os
import tempfile

import numpy as np
from osgeo import gdal, osr, ogr
from qgis.PyQt.QtCore import QVariant
from qgis.PyQt import QtGui
from qgis.core import (
    QgsCoordinateReferenceSystem,
    QgsFeature,
    QgsFeatureRequest,
    QgsField,
    QgsFields,
    QgsGeometry,
    QgsPointXY,
    QgsProject,
    QgsRasterLayer,
    QgsRectangle,
    QgsSpatialIndex,
    QgsVectorLayer,
    QgsWkbTypes,
    QgsRasterShader,
    QgsColorRampShader,
    QgsSingleBandPseudoColorRenderer,
)

# Acoustic engine imports
from .noise_common import (
    NoiseSource,
    NoiseReceiver,
    OCTAVE_BANDS,
    A_WEIGHTING,
    global_lwa_to_octave_spectrum,
    log as _noise_log,
)
from .noise_spectrum import SpectrumLibrary, get_template_for_model
from .noise_engine_fast import propagate_fast
from .noise_engine_iso import (
    propagate_iso,
    calculate_alpha_atm_iso,
    calculate_agr_iso_regions,
    calculate_abar_iso_simple,
    _prepare_mdt_context,
)
# End spectrum library setup
from .acoustics.curves import load_acoustic_curve_csv, evaluate_acoustic_curve
from .qgis_io.common import (
    _unique_temp_output,
    _sample_dem,
    _layer_crs_matches,
    _remove_existing_layers_by_name,
    _set_field_aliases,
)
from .sources.collector import _collect_sources, _is_model_layer, _iter_model_layers
from .receivers.collector import _build_receiver_feature_list
from .propagation.ground import (
    _bbox_from_point,
    _ground_g_from_attributes,
    _effective_ground_g,
    _lp_from_source,
)
from .qgis_io.layers import (
    _build_source_layer,
    _build_dominant_links_layer,
    _apply_raster_heatmap_style,
    _apply_line_style,
    _build_isophones_layer_from_raster,
    _build_uncovered_receivers_layer,
)
from .raster.grid import _build_noise_grid_layer
from .validation import is_finite_positive as _is_finite_positive, validate_model_config as _validate_model_cfg
from .results.evaluator import evaluate_receivers_for_noise
from .results.summary import extract_result_layer_statistics
from .results.payload import build_noise_result_payload


def _log(msg: str) -> None:
    _noise_log(msg)


# NoiseSource importado de noise_common


# NoiseReceiver se importa desde noise_common.


def compute_noise(
    receiver_layer: QgsVectorLayer,
    model_cfg: Dict[str, Dict[str, float]],
    source_layer_ids: Optional[List[str]] = None,
    receiver_height_m: float = 4.0,
    max_radius_m: float = 5000.0,
    dem_layer: Optional[QgsRasterLayer] = None,
    alpha_db_per_m: float = 0.005,
    ground_factor_g: float = 0.5,
    ground_mode: str = 'global',
    landuse_layer: Optional[QgsVectorLayer] = None,
    receiver_limit_dba: float = 45.0,
    receiver_limit_mode: str = "global",
    receiver_limit_scenario: str = "custom",
    receiver_limit_field_day: Optional[str] = None,
    receiver_limit_field_night: Optional[str] = None,
    receiver_limit_field_custom: Optional[str] = None,
    receiver_type_field: Optional[str] = None,
    receiver_height_field: Optional[str] = None,
    receiver_source_field: Optional[str] = None,
    min_distance_m: float = 25.0,
    result_layer_name: str = "Noise · Receivers",
    sources_layer_name: str = "Noise · Sources",
    links_layer_name: str = "Noise · Dominant links",
    grid_layer_name: str = "Noise · Mapa",
    iso_layer_name: str = "Noise · Isophones",
    uncovered_layer_name: str = "Noise · Receivers outside radius",
    create_sources_layer: bool = True,
    create_links_layer: bool = True,
    create_grid_layer: bool = False,
    create_iso_layer: bool = False,
    iso_levels: Optional[List[float]] = None,
    grid_resolution_m: float = 100.0,
    # Acoustic engine parameters
    calculation_engine: str = "fast",
    temperature_c: float = 15.0,
    humidity_percent: float = 70.0,
    pressure_kpa: float = 101.325,
    # End spectrum library setup
) -> Dict[str, object]:
    prj = QgsProject.instance()
    if receiver_layer is None or not isinstance(receiver_layer, QgsVectorLayer):
        raise ValueError("No valid receiver layer was provided.")
    if not _layer_crs_matches(receiver_layer, prj.crs()):
        raise ValueError("The receiver layer is not in the same CRS as the project. Reproject it before calculating.")
    if dem_layer is not None and not _layer_crs_matches(dem_layer, prj.crs()):
        raise ValueError("El MDT/DSM no está en el mismo CRS que el proyecto. Reproyéctalo antes de calcular.")
    if landuse_layer is not None:
        if not isinstance(landuse_layer, QgsVectorLayer) or QgsWkbTypes.geometryType(landuse_layer.wkbType()) != QgsWkbTypes.PolygonGeometry:
            raise ValueError("La capa de uso del suelo debe ser vectorial poligonal.")
        if not _layer_crs_matches(landuse_layer, prj.crs()):
            raise ValueError("La capa de uso del suelo no está en el mismo CRS que el proyecto. Reproyéctala antes de calcular.")
    if not _is_finite_positive(max_radius_m):
        raise ValueError("El radio máximo debe ser mayor que 0.")
    if not _is_finite_positive(grid_resolution_m):
        raise ValueError("La resolución del raster debe ser mayor que 0.")
    if not _is_finite_positive(min_distance_m):
        raise ValueError("La distancia mínima debe ser mayor que 0.")
    if not _is_finite_positive(receiver_height_m, allow_zero=True):
        raise ValueError("The receiver height is not valid.")
    if not _is_finite_positive(receiver_limit_dba, allow_zero=True):
        raise ValueError("El límite acústico no es válido.")
    if not _is_finite_positive(alpha_db_per_m, allow_zero=True):
        raise ValueError("El coeficiente α no es válido.")
    cfg_errors = _validate_model_cfg(model_cfg)
    if cfg_errors:
        raise ValueError("Configuración acústica inválida:\n- " + "\n- ".join(cfg_errors[:8]))

    # Spectrum library setup
    spectrum_library = None
    if calculation_engine == "iso":
        try:
            import os
            spectrum_library_dir = os.path.join(
                os.path.dirname(__file__),
                'spectrum_library'
            )
            spectrum_library = SpectrumLibrary(library_dir=spectrum_library_dir)
            _log(f"[ISO] Biblioteca inicializada: {spectrum_library_dir}")
        except Exception as e:
            _log(f"[ISO][WARN] Error biblioteca espectros: {e}")
            spectrum_library = None
    # End spectrum library setup

    sources, src_diag = _collect_sources(prj, model_cfg, dem_layer, spectrum_library=spectrum_library, source_layer_ids=source_layer_ids)
    if not sources:
        raise ValueError("No se han detectado turbinas/layout válidos para el cálculo acústico.")
    receivers = _build_receiver_feature_list(receiver_layer, receiver_height_m, dem_layer, receiver_height_field=receiver_height_field, receiver_type_field=receiver_type_field, receiver_limit_day_field=receiver_limit_field_day, receiver_limit_night_field=receiver_limit_field_night, receiver_limit_custom_field=receiver_limit_field_custom, receiver_source_field=receiver_source_field)
    if not receivers:
        raise ValueError("The receiver layer contains no valid features for calculation.")

    _log(f"[Noise] Método acústico: consultoría eólica fuente-receptor (Adiv + Aatm + Aground) | alpha={alpha_db_per_m:.4f} dB/m | G={ground_factor_g:.2f} | modo_suelo={ground_mode} | radio={max_radius_m:.0f} m")
    _log(f"[NOISE] Proyecto: {prj.baseName() or 'Proyecto sin nombre'} | CRS={prj.crs().authid()}")
    _log(f"[NOISE] Detected sources: {len(sources)} turbine(s) in {len(src_diag)} acoustic source group(s).")
    for name, d in src_diag.items():
        hh_txt = f"{d['hub_height']:.1f}" if math.isfinite(d['hub_height']) else "-"
        dia = d.get("diameter")
        d_txt = f"{dia:.1f}" if isinstance(dia, float) and math.isfinite(dia) else "-"
        mode = str(d.get('acoustic_mode') or 'fixed').lower()
        if mode == 'curve' and str(d.get('curve_path') or '').strip():
            if bool(d.get('use_curve_worst_case', False)):
                acoustic_txt = f"Curva peor caso → LwA={d['lwa']:.1f} dB(A)"
            else:
                ws_eval = d.get('eval_ws_m_s')
                ws_txt = f"{float(ws_eval):.1f}" if isinstance(ws_eval, float) and math.isfinite(ws_eval) else '-'
                acoustic_txt = f"Curva @ {ws_txt} m/s → LwA={d['lwa']:.1f} dB(A)"
        else:
            acoustic_txt = f"LwA fijo={d['lwa']:.1f} dB(A)"
        _log(f"[Noise]   - grupo={d.get('name', name)} | parque={d.get('park_name','') or '-'} | modelo={d.get('model_name','-')} | n={int(d['count'])} | {acoustic_txt} | HH={hh_txt} m | D={d_txt} m")
    _log(f"[Noise] Receptores: {len(receivers)} elemento(s) de '{receiver_layer.name()}' | altura base receptor={receiver_height_m:.1f} m | modo_limite={receiver_limit_mode}/{receiver_limit_scenario}")
    if dem_layer is not None:
        _log(f"[Noise] MDT/DSM activo: {dem_layer.name()}")
    active_landuse_layer = landuse_layer if str(ground_mode).lower() == 'landuse' else None
    if active_landuse_layer is not None:
        _log(f"[Noise] Capa de uso del suelo activa: {active_landuse_layer.name()}")

    # Reemplazar capas previas con los mismos nombres para no acumular resultados de ruido.
    _remove_existing_layers_by_name(
        prj,
        [result_layer_name]
        + ([sources_layer_name] if create_sources_layer else [])
        + ([links_layer_name] if create_links_layer else [])
        + ([grid_layer_name] if create_grid_layer else [])
        + ([iso_layer_name] if create_iso_layer else [])
        + ([uncovered_layer_name] if True else []),
    )

    evaluation = evaluate_receivers_for_noise(
        sources=sources,
        receivers=receivers,
        input_fields=receiver_layer.fields(),
        crs_authid=prj.crs().authid() or 'EPSG:25830',
        max_radius_m=float(max_radius_m),
        alpha_db_per_m=float(alpha_db_per_m),
        ground_factor_g=float(ground_factor_g),
        ground_mode=str(ground_mode or 'global'),
        active_landuse_layer=active_landuse_layer,
        receiver_limit_dba=float(receiver_limit_dba),
        receiver_limit_mode=str(receiver_limit_mode or 'global'),
        receiver_limit_scenario=str(receiver_limit_scenario or 'custom'),
        receiver_limit_field_day=receiver_limit_field_day,
        receiver_limit_field_night=receiver_limit_field_night,
        receiver_limit_field_custom=receiver_limit_field_custom,
        min_distance_m=float(min_distance_m),
        calculation_engine=str(calculation_engine or 'fast'),
        temperature_c=float(temperature_c),
        humidity_percent=float(humidity_percent),
        pressure_kpa=float(pressure_kpa),
        dem_layer=dem_layer,
    )

    source_mem = evaluation.source_mem
    sidx = evaluation.sidx
    out_fields = evaluation.out_fields
    out_feats = evaluation.out_feats
    max_noise = evaluation.max_noise
    max_noise_fid = evaluation.max_noise_fid
    total_sources_used = evaluation.total_sources_used
    zero_receivers = evaluation.zero_receivers
    n_exceed = evaluation.n_exceed
    src_stats = evaluation.src_stats
    dom_links = evaluation.dom_links
    uncovered_ids = evaluation.uncovered_ids
    receiver_type_counts = evaluation.receiver_type_counts
    ground_g_values = evaluation.ground_g_values
    ground_fallback_count = evaluation.ground_fallback_count
    ground_from_landuse_count = evaluation.ground_from_landuse_count
    applied_limits = evaluation.applied_limits
    receiver_type_compliance = evaluation.receiver_type_compliance
    path_diagnostics = evaluation.path_diagnostics

    geom_type = QgsWkbTypes.displayString(receiver_layer.wkbType())
    result = QgsVectorLayer(f"{geom_type}?crs={prj.crs().authid() or 'EPSG:25830'}", result_layer_name, "memory")
    pr = result.dataProvider()
    pr.addAttributes(out_fields)
    result.updateFields()

    pr.addFeatures(out_feats)
    try:
        result.setCustomProperty("velantis/noise_output", True)
    except Exception:
        pass
    QgsProject.instance().addMapLayer(result)
    _set_field_aliases(result, {
        'noise_dba':'total_level_dba','n_src':'turbines_in_radius','near_m':'nearest_turbine_m',
        'max_src_dba':'dominant_contribution_dba','dom_model':'modelo_dominante','dom_group':'grupo_fuente_dominante','dom_park':'parque_dominante','src_lwa':'lwa_fuente_dom_dba',
        'dist3d_m':'dist_fuente_dom_3d_m','adiv_db':'divergence_loss_db','aatm_db':'atmospheric_loss_db',
        'aground_db':'ground_loss_db','abar_db':'barrier_loss_dominant_path_db','abar_max_db':'barrier_loss_max_contributors_db','abar_mean_db':'barrier_loss_mean_contributors_db','abar_ew_db':'barrier_loss_energy_weighted_db','abar_screen_n':'screened_contributing_turbines','abar_state':'mdt_screening_state','obs_h_m':'mdt_obstacle_height_m','obs_d1_m':'source_obstacle_distance_m','obs_d2_m':'obstacle_receiver_distance_m','obs_thr_m':'mdt_activation_threshold_m','src_z_m':'dominant_source_ground_z_m','hub_h_m':'dominant_source_hub_height_m','src_ac_z_m':'dominant_source_acoustic_z_m','rec_z_m':'receiver_ground_z_m','rec_h_m':'receiver_height_agl_m','rec_ac_z_m':'receiver_acoustic_z_m','maxab_src':'max_abar_source_index','maxab_state':'max_abar_mdt_state','maxab_obs_h':'max_abar_obstacle_height_m','maxab_thr':'max_abar_threshold_m','maxab_d1':'max_abar_source_obstacle_m','maxab_d2':'max_abar_obstacle_receiver_m','maxab_src_z':'max_abar_source_ground_z_m','maxab_hub_h':'max_abar_source_hub_height_m','maxab_src_ac_z':'max_abar_source_acoustic_z_m','maxobs_src':'max_obstacle_source_index','maxobs_state':'max_obstacle_mdt_state','maxobs_h':'max_obstacle_height_m','maxobs_thr':'max_obstacle_threshold_m','maxobs_d1':'max_obstacle_source_obstacle_m','maxobs_d2':'max_obstacle_obstacle_receiver_m','maxobs_src_z':'max_obstacle_source_ground_z_m','maxobs_hub_h':'max_obstacle_source_hub_height_m','maxobs_src_ac_z':'max_obstacle_source_acoustic_z_m','ground_g':'ground_factor_g','dom_freq':'dominant_band_hz','spec_src':'spectrum_source','limit_dba':'receiver_limit_dba','margin_db':'limit_margin_db','exceeds':'exceeds_limit','limit_src':'limit_source','limit_scn':'limit_scenario','limit_fld':'limit_field','rec_type':'receiver_type','src_layer':'receiver_source_layer','dom_src_lyr':'dominant_source_layer','state':'compliance_state','ground_md':'ground_mode'})

    src_layer = _build_source_layer(prj, sources, src_stats, sources_layer_name) if create_sources_layer else None
    link_layer = _build_dominant_links_layer(prj, dom_links, links_layer_name) if create_links_layer else None
    uncovered_layer = _build_uncovered_receivers_layer(prj, receivers, uncovered_ids, uncovered_layer_name)

    grid_layer = None
    iso_layer = None
    grid_diag = {'grid_cells': 0, 'grid_width': 0, 'grid_height': 0, 'requested_resolution_m': float(grid_resolution_m), 'effective_resolution_m': float(grid_resolution_m), 'auto_adjusted': False}
    if create_grid_layer:
        ext = QgsRectangle(sources[0].x, sources[0].y, sources[0].x, sources[0].y)
        for src in sources[1:]:
            ext.combineExtentWith(QgsRectangle(src.x, src.y, src.x, src.y))
        pad = max(float(max_radius_m), float(grid_resolution_m) * 2.0, 100.0)
        ext = QgsRectangle(ext.xMinimum() - pad, ext.yMinimum() - pad, ext.xMaximum() + pad, ext.yMaximum() + pad)
        grid_layer, grid_diag = _build_noise_grid_layer(
            prj=prj, source_mem=source_mem, sidx=sidx, sources=sources, extent=ext,
            grid_resolution_m=float(grid_resolution_m), max_radius_m=float(max_radius_m),
            alpha_db_per_m=float(alpha_db_per_m), ground_factor_g=float(ground_factor_g), landuse_layer=landuse_layer if str(ground_mode).lower() == 'landuse' else None, min_distance_m=float(min_distance_m),
            receiver_height_m=float(receiver_height_m), dem_layer=dem_layer, layer_name=grid_layer_name,
            # Pass acoustic engine parameters
            calculation_engine=calculation_engine,
            temperature_c=temperature_c,
            humidity_percent=humidity_percent,
            pressure_kpa=pressure_kpa
        )
        if create_iso_layer and grid_layer is not None:
            levels = iso_levels or [35.0, 40.0, 45.0, 50.0]
            iso_layer = _build_isophones_layer_from_raster(prj, str(grid_diag.get('grid_path') or ''), levels, iso_layer_name)

    _log(f"[Noise] Resultado: {len(out_feats)} receptor(es) calculado(s).")
    _log(f"[Noise] Cobertura acústica: {len(out_feats) - zero_receivers}/{len(out_feats)} receptor(es) con al menos una turbina dentro del radio máximo.")
    _log(f"[Noise] Máximo receptor: {max_noise:.2f} dB(A) | feature_id={max_noise_fid if max_noise_fid is not None else '-'}")
    if src_layer is not None:
        _log(f"[Noise] Capa de fuentes creada: {sources_layer_name} | {len(sources)} turbina(s).")
    if link_layer is not None:
        _log(f"[Noise] Capa de enlaces dominantes creada: {links_layer_name} | {len(dom_links)} enlace(s).")
    if uncovered_layer is not None:
        _log(f"[Noise] Capa de receptores sin cobertura creada: {uncovered_layer_name} | {len(uncovered_ids)} receptor(es).")
    if iso_layer is not None:
        try:
            n_iso = int(iso_layer.featureCount())
        except Exception:
            n_iso = 0
        _log(f"[Noise] Capa de isófonas creada: {iso_layer_name} | {n_iso} entidades.")
    _log(f"[Noise] Cumplimiento rápido: {n_exceed}/{len(out_feats)} receptor(es) superan el límite de referencia aplicado.")

    layer_stats = extract_result_layer_statistics(result, max_noise_fid)
    adiv_vals = layer_stats.adiv_vals
    aatm_vals = layer_stats.aatm_vals
    aground_vals = layer_stats.aground_vals
    abar_vals = layer_stats.abar_vals
    critical_receiver = layer_stats.critical_receiver

    return build_noise_result_payload(
        result=result,
        src_layer=src_layer,
        link_layer=link_layer,
        grid_layer=grid_layer,
        iso_layer=iso_layer,
        uncovered_layer=uncovered_layer,
        sources=sources,
        receivers=receivers,
        src_diag=src_diag,
        out_feats=out_feats,
        dom_links=dom_links,
        uncovered_ids=uncovered_ids,
        zero_receivers=zero_receivers,
        n_exceed=n_exceed,
        max_noise=max_noise,
        max_noise_fid=max_noise_fid,
        grid_diag=grid_diag,
        alpha_db_per_m=float(alpha_db_per_m),
        ground_factor_g=float(ground_factor_g),
        ground_mode=str(ground_mode or 'global'),
        active_landuse_layer=active_landuse_layer,
        receiver_height_m=float(receiver_height_m),
        max_radius_m=float(max_radius_m),
        dem_layer=dem_layer,
        adiv_vals=adiv_vals,
        aatm_vals=aatm_vals,
        aground_vals=aground_vals,
        abar_vals=abar_vals,
        ground_g_values=ground_g_values,
        critical_receiver=critical_receiver,
        ground_from_landuse_count=ground_from_landuse_count,
        ground_fallback_count=ground_fallback_count,
        applied_limits=applied_limits,
        receiver_type_counts=receiver_type_counts,
        receiver_type_compliance=receiver_type_compliance,
        receiver_limit_dba=float(receiver_limit_dba),
        receiver_limit_mode=str(receiver_limit_mode or 'global'),
        receiver_limit_scenario=str(receiver_limit_scenario or 'custom'),
        calculation_engine=str(calculation_engine or 'fast'),
        temperature_c=float(temperature_c),
        humidity_percent=float(humidity_percent),
        pressure_kpa=float(pressure_kpa),
        model_cfg=model_cfg,
        path_diagnostics=path_diagnostics,
    )


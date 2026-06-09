# -*- coding: utf-8 -*-
"""Receiver-level noise evaluation helpers.

This module contains the per-receptor loop that used to live inside
``noise_compute.py``. It intentionally still works with QGIS objects because the
existing engine writes memory layers, but the computation is now isolated from the
main orchestration function.
"""
from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Dict, List, Optional, Any

from qgis.PyQt.QtCore import QVariant
from qgis.core import (
    QgsFeature,
    QgsField,
    QgsFields,
    QgsGeometry,
    QgsPointXY,
    QgsSpatialIndex,
    QgsVectorLayer,
)

from ..noise_common import NoiseSource, NoiseReceiver
from ..noise_engine_fast import propagate_fast
from ..noise_engine_iso import propagate_iso
from ..propagation.ground import _bbox_from_point


@dataclass
class ReceiverEvaluation:
    """Output of the receiver evaluation stage."""

    source_mem: QgsVectorLayer
    sidx: QgsSpatialIndex
    out_fields: QgsFields
    out_feats: List[QgsFeature]
    max_noise: float
    max_noise_fid: Optional[int]
    total_sources_used: int
    zero_receivers: int
    n_exceed: int
    src_stats: Dict[int, Dict[str, object]]
    dom_links: List[Dict[str, object]]
    uncovered_ids: List[int]
    receiver_type_counts: Dict[str, int]
    ground_g_values: List[float]
    ground_fallback_count: int
    ground_from_landuse_count: int
    applied_limits: List[float]
    receiver_type_compliance: Dict[str, Dict[str, int]]
    path_diagnostics: List[Dict[str, object]]


def build_receiver_output_fields(input_fields: QgsFields) -> QgsFields:
    """Build the memory-layer schema for the receiver result layer."""
    out_fields = QgsFields()
    for fld in input_fields:
        out_fields.append(fld)
    for name, qvariant_type in [
        ("noise_dba", QVariant.Double),
        ("n_src", QVariant.Int),
        ("near_m", QVariant.Double),
        ("max_src_dba", QVariant.Double),
        ("dom_model", QVariant.String),
        ("dom_group", QVariant.String),
        ("dom_park", QVariant.String),
        ("src_lwa", QVariant.Double),
        ("dist3d_m", QVariant.Double),
        ("adiv_db", QVariant.Double),
        ("aatm_db", QVariant.Double),
        ("aground_db", QVariant.Double),
        ("abar_db", QVariant.Double),
        # Receiver-level MDT screening diagnostics.  ``abar_db`` above is the
        # value for the dominant source path only; the fields below summarize
        # all source paths that contribute to this receiver.
        ("abar_max_db", QVariant.Double),
        ("abar_mean_db", QVariant.Double),
        ("abar_ew_db", QVariant.Double),
        ("abar_screen_n", QVariant.Int),
        ("abar_state", QVariant.String),
        ("obs_h_m", QVariant.Double),
        ("obs_d1_m", QVariant.Double),
        ("obs_d2_m", QVariant.Double),
        ("obs_thr_m", QVariant.Double),
        # Height diagnostics for the dominant source path. ``*_z_m`` are
        # ground elevations from the DEM/DTM when available; ``*_ac_z_m`` are
        # absolute acoustic heights used for the line-of-sight test.
        ("src_z_m", QVariant.Double),
        ("hub_h_m", QVariant.Double),
        ("src_ac_z_m", QVariant.Double),
        ("rec_z_m", QVariant.Double),
        ("rec_h_m", QVariant.Double),
        ("rec_ac_z_m", QVariant.Double),
        # Diagnostics for the contributing source path with the largest Abar.
        # This is often more useful for MDT debugging than the dominant-energy
        # source path, because a strongly screened turbine can contribute little
        # to the final level.
        ("maxab_src", QVariant.Int),
        ("maxab_state", QVariant.String),
        ("maxab_obs_h", QVariant.Double),
        ("maxab_thr", QVariant.Double),
        ("maxab_d1", QVariant.Double),
        ("maxab_d2", QVariant.Double),
        ("maxab_src_z", QVariant.Double),
        ("maxab_hub_h", QVariant.Double),
        ("maxab_src_ac_z", QVariant.Double),
        # Largest terrain-obstacle candidate among contributing paths, even if
        # it remains below the activation threshold and therefore Abar = 0.
        ("maxobs_src", QVariant.Int),
        ("maxobs_state", QVariant.String),
        ("maxobs_h", QVariant.Double),
        ("maxobs_thr", QVariant.Double),
        ("maxobs_d1", QVariant.Double),
        ("maxobs_d2", QVariant.Double),
        ("maxobs_src_z", QVariant.Double),
        ("maxobs_hub_h", QVariant.Double),
        ("maxobs_src_ac_z", QVariant.Double),
        ("ground_g", QVariant.Double),
        ("dom_freq", QVariant.Int),
        ("spec_src", QVariant.String),
        ("eval_mode", QVariant.String),
        ("calc_meth", QVariant.String),
        ("covered", QVariant.Int),
        ("limit_dba", QVariant.Double),
        ("margin_db", QVariant.Double),
        ("exceeds", QVariant.Int),
        ("limit_src", QVariant.String),
        ("limit_scn", QVariant.String),
        ("limit_fld", QVariant.String),
        ("rec_type", QVariant.String),
        ("src_layer", QVariant.String),
        ("dom_src_lyr", QVariant.String),
        ("state", QVariant.String),
        ("ground_md", QVariant.String),
    ]:
        out_fields.append(QgsField(name, qvariant_type))
    return out_fields


def build_source_spatial_index(sources: List[NoiseSource], crs_authid: str) -> tuple[QgsVectorLayer, QgsSpatialIndex]:
    """Create an in-memory source layer and spatial index used for radius queries."""
    source_fields = QgsFields()
    source_fields.append(QgsField("src_idx", QVariant.Int))
    source_mem = QgsVectorLayer(f"Point?crs={crs_authid or 'EPSG:25830'}", "_noise_sources_idx", "memory")
    spr = source_mem.dataProvider()
    spr.addAttributes(source_fields)
    source_mem.updateFields()

    src_feats = []
    for i, src in enumerate(sources):
        f = QgsFeature(source_fields)
        f.setGeometry(QgsGeometry.fromPointXY(QgsPointXY(src.x, src.y)))
        f["src_idx"] = int(i)
        src_feats.append(f)
    spr.addFeatures(src_feats)
    return source_mem, QgsSpatialIndex(source_mem.getFeatures())




def _ground_z_or_none(obj) -> Optional[float]:
    """Return ground elevation when it is known, otherwise None."""
    try:
        z = getattr(obj, 'z_ground', None)
        return None if z is None else float(z)
    except Exception:
        return None


def _source_acoustic_z_or_none(src: NoiseSource) -> Optional[float]:
    z = _ground_z_or_none(src)
    if z is None:
        return None
    try:
        return float(z) + float(src.hub_height)
    except Exception:
        return None


def _receiver_acoustic_z_or_none(rec: NoiseReceiver) -> Optional[float]:
    z = _ground_z_or_none(rec)
    if z is None:
        return None
    try:
        return float(z) + float(rec.receiver_height)
    except Exception:
        return None


def _active_path_value(value, state: str):
    """Avoid showing fake d1/d2 values for clear-line paths."""
    return value if str(state or '').lower() == 'active' else None


def _candidate_path_value(value, obstacle_height_m):
    """Return obstacle geometry when a real obstacle candidate exists.

    This is intentionally less strict than _active_path_value: below-threshold
    terrain bumps are useful for debugging why Abar stayed zero.
    """
    try:
        return value if float(obstacle_height_m or 0.0) > 0.0 else None
    except Exception:
        return None


def evaluate_receivers_for_noise(
    *,
    sources: List[NoiseSource],
    receivers: List[NoiseReceiver],
    input_fields: QgsFields,
    crs_authid: str,
    max_radius_m: float,
    alpha_db_per_m: float,
    ground_factor_g: float,
    ground_mode: str,
    active_landuse_layer: Any,
    receiver_limit_dba: float,
    receiver_limit_mode: str,
    receiver_limit_scenario: str,
    receiver_limit_field_day: Optional[str],
    receiver_limit_field_night: Optional[str],
    receiver_limit_field_custom: Optional[str],
    min_distance_m: float,
    calculation_engine: str,
    temperature_c: float,
    humidity_percent: float,
    pressure_kpa: float,
    dem_layer: Any,
) -> ReceiverEvaluation:
    """Evaluate all receivers and build output features/statistics."""
    source_mem, sidx = build_source_spatial_index(sources, crs_authid)
    out_fields = build_receiver_output_fields(input_fields)
    try:
        input_field_count = int(input_fields.count())
    except Exception:
        input_field_count = 0

    out_feats: List[QgsFeature] = []
    max_noise = -1.0
    max_noise_fid = None
    total_sources_used = 0
    zero_receivers = 0
    n_exceed = 0
    src_stats: Dict[int, Dict[str, object]] = {
        i: {"n_recv": 0, "max_lp_db": None, "near_rec_m": None, "dom_rec_id": None}
        for i in range(len(sources))
    }
    dom_links: List[Dict[str, object]] = []
    uncovered_ids: List[int] = []
    receiver_type_counts: Dict[str, int] = {}
    ground_g_values: List[float] = []
    ground_fallback_count = 0
    ground_from_landuse_count = 0
    applied_limits: List[float] = []
    receiver_type_compliance: Dict[str, Dict[str, int]] = {}
    path_diagnostics: List[Dict[str, object]] = []

    for rec in receivers:
        rec_limit = float(receiver_limit_dba)
        limit_src = "global"
        limit_fld = ""
        rec_type = str((rec.meta or {}).get("receiver_type") or "")
        src_layer_name = str((rec.meta or {}).get("source_layer_name") or "")
        if str(receiver_limit_mode).lower() == "by_field":
            scenario = str(receiver_limit_scenario or "custom").lower()
            if scenario == "day":
                v = (rec.meta or {}).get("limit_day_dba")
                if v is not None:
                    rec_limit = float(v); limit_src = "capa"; limit_fld = str(receiver_limit_field_day or "")
            elif scenario == "night":
                v = (rec.meta or {}).get("limit_night_dba")
                if v is not None:
                    rec_limit = float(v); limit_src = "capa"; limit_fld = str(receiver_limit_field_night or "")
            else:
                v = (rec.meta or {}).get("limit_custom_dba")
                if v is not None:
                    rec_limit = float(v); limit_src = "capa"; limit_fld = str(receiver_limit_field_custom or "")

        bbox = _bbox_from_point(rec.x, rec.y, float(max_radius_m))
        cand_ids = sidx.intersects(bbox)
        e_sum = 0.0
        n_src = 0
        near_m = None
        max_src_lp = None
        dom_model = ""
        dom_group = ""
        dom_park = ""
        dom_src_idx = None
        dom_src = None
        dom_dist3d = None
        dom_adiv = None
        dom_aatm = None
        dom_aground = None
        dom_abar = None
        dom_abar_state = ''
        dom_obs_h_m = None
        dom_obs_d1_m = None
        dom_obs_d2_m = None
        dom_obs_thr_m = None
        dom_src_z_m = None
        dom_hub_h_m = None
        dom_src_ac_z_m = None
        dom_rec_z_m = _ground_z_or_none(rec)
        dom_rec_h_m = float(rec.receiver_height)
        dom_rec_ac_z_m = _receiver_acoustic_z_or_none(rec)
        maxab_src_idx = None
        maxab_state = ''
        maxab_obs_h_m = None
        maxab_obs_thr_m = None
        maxab_obs_d1_m = None
        maxab_obs_d2_m = None
        maxab_src_z_m = None
        maxab_hub_h_m = None
        maxab_src_ac_z_m = None
        maxobs_src_idx = None
        maxobs_state = ''
        maxobs_h_m = None
        maxobs_thr_m = None
        maxobs_d1_m = None
        maxobs_d2_m = None
        maxobs_src_z_m = None
        maxobs_hub_h_m = None
        maxobs_src_ac_z_m = None
        dom_ground_g = None
        dom_dom_freq = None
        dom_spectrum_source = ''
        dom_src_layer_name = ''
        # Aggregated Abar diagnostics for every turbine contributing to this
        # receiver. The report can then avoid implying that ``abar_db`` is the
        # receiver total; it is only the dominant source / dominant band path.
        rec_abar_sum = 0.0
        rec_abar_max = 0.0
        rec_abar_energy_weighted_sum = 0.0
        rec_abar_energy_sum = 0.0
        rec_abar_screened_count = 0

        for sid in cand_ids:
            f = source_mem.getFeature(int(sid))
            try:
                src_idx = int(f["src_idx"])
                src = sources[src_idx]
            except Exception:
                continue

            path_src_z_m = _ground_z_or_none(src)
            path_src_ac_z_m = _source_acoustic_z_or_none(src)
            path_rec_z_m = dom_rec_z_m
            path_rec_ac_z_m = dom_rec_ac_z_m
            path_mdt_sample_step_m = None
            path_mdt_num_points = None
            path_mdt_valid_points = None
            path_mdt_invalid_points = None

            if calculation_engine == "iso":
                lpa_result, desglose_iso, _ = propagate_iso(
                    src=src, rec=rec,
                    temperature_c=temperature_c,
                    humidity_percent=humidity_percent,
                    pressure_kpa=pressure_kpa,
                    ground_g=float(ground_factor_g),
                    min_distance_m=float(min_distance_m),
                    dem_layer=dem_layer,
                    landuse_layer=active_landuse_layer,
                )
                def _maybe_float(v, fallback=None):
                    try:
                        return float(v) if v is not None else fallback
                    except Exception:
                        return fallback

                path_src_z_m = _maybe_float(desglose_iso.get('mdt_source_ground_z_m'), path_src_z_m)
                path_rec_z_m = _maybe_float(desglose_iso.get('mdt_receiver_ground_z_m'), path_rec_z_m)
                path_src_ac_z_m = _maybe_float(desglose_iso.get('mdt_source_acoustic_z_m'), path_src_ac_z_m)
                path_rec_ac_z_m = _maybe_float(desglose_iso.get('mdt_receiver_acoustic_z_m'), path_rec_ac_z_m)
                path_mdt_sample_step_m = _maybe_float(desglose_iso.get('mdt_sample_step_m'), None)
                try:
                    path_mdt_num_points = int(desglose_iso.get('mdt_num_points')) if desglose_iso.get('mdt_num_points') is not None else None
                except Exception:
                    path_mdt_num_points = None
                try:
                    path_mdt_valid_points = int(desglose_iso.get('mdt_valid_points')) if desglose_iso.get('mdt_valid_points') is not None else None
                except Exception:
                    path_mdt_valid_points = None
                try:
                    path_mdt_invalid_points = int(desglose_iso.get('mdt_invalid_points')) if desglose_iso.get('mdt_invalid_points') is not None else None
                except Exception:
                    path_mdt_invalid_points = None

                calc = (
                    lpa_result,
                    float(desglose_iso.get('dist_xy', 0.0)),
                    float(desglose_iso.get('dist_3d', 0.0)),
                    float(desglose_iso.get('Adiv', 0.0)),
                    float(desglose_iso.get('Aatm', 0.0)),
                    float(desglose_iso.get('Agr', 0.0)),
                    float(desglose_iso.get('Abar', 0.0)),
                    str(desglose_iso.get('mdt_abar_state') or ('no_dem' if dem_layer is None else 'unknown')),
                    float(desglose_iso.get('mdt_obstacle_height_m', 0.0)),
                    float(desglose_iso.get('mdt_d1_m', 0.0)),
                    float(desglose_iso.get('mdt_d2_m', 0.0)),
                    float(desglose_iso.get('mdt_obstacle_threshold_m', 0.0)),
                    float(desglose_iso.get('ground_g', ground_factor_g)),
                    int(desglose_iso.get('dominant_freq')) if desglose_iso.get('dominant_freq') is not None else None,
                )
            else:
                calc_fast = propagate_fast(
                    src=src, rec=rec,
                    alpha_db_per_m=float(alpha_db_per_m),
                    ground_factor_g=float(ground_factor_g),
                    min_distance_m=float(min_distance_m),
                    landuse_layer=active_landuse_layer,
                )
                calc = None if calc_fast is None else (
                    calc_fast[0], calc_fast[1], calc_fast[2], calc_fast[3], calc_fast[4], calc_fast[5],
                    0.0, 'no_dem', 0.0, 0.0, 0.0, 0.0, calc_fast[6], None,
                )
            if calc is None:
                continue

            lp, dist_xy, _dist3d, _adiv, _aatm, _aground, _abar, _abar_state, _obs_h_m, _obs_d1_m, _obs_d2_m, _obs_thr_m, _g_eff, _dom_freq = calc
            if dist_xy > float(max_radius_m):
                continue
            source_energy = 10.0 ** (lp / 10.0)
            e_sum += source_energy
            n_src += 1
            total_sources_used += 1
            try:
                abar_val = max(0.0, float(_abar))
            except Exception:
                abar_val = 0.0
            rec_abar_sum += abar_val
            if abar_val > rec_abar_max:
                rec_abar_max = abar_val
                maxab_src_idx = src_idx
                maxab_state = str(_abar_state or '')
                maxab_obs_h_m = _obs_h_m
                maxab_obs_thr_m = _obs_thr_m
                maxab_obs_d1_m = _active_path_value(_obs_d1_m, _abar_state)
                maxab_obs_d2_m = _active_path_value(_obs_d2_m, _abar_state)
                maxab_src_z_m = _ground_z_or_none(src)
                maxab_hub_h_m = float(src.hub_height)
                maxab_src_ac_z_m = _source_acoustic_z_or_none(src)
            rec_abar_energy_weighted_sum += abar_val * source_energy
            rec_abar_energy_sum += source_energy
            if abar_val > 0.005 or str(_abar_state or '').lower() == 'active':
                rec_abar_screened_count += 1

            # Keep the largest obstacle candidate even when below threshold.
            # This lets the report/CSV explain why many paths have Abar = 0.
            try:
                obs_candidate = max(0.0, float(_obs_h_m or 0.0))
            except Exception:
                obs_candidate = 0.0
            if maxobs_h_m is None or obs_candidate > float(maxobs_h_m or 0.0):
                maxobs_src_idx = src_idx
                maxobs_state = str(_abar_state or '')
                maxobs_h_m = obs_candidate
                maxobs_thr_m = _obs_thr_m
                maxobs_d1_m = _candidate_path_value(_obs_d1_m, obs_candidate)
                maxobs_d2_m = _candidate_path_value(_obs_d2_m, obs_candidate)
                maxobs_src_z_m = _ground_z_or_none(src)
                maxobs_hub_h_m = float(src.hub_height)
                maxobs_src_ac_z_m = _source_acoustic_z_or_none(src)

            path_diagnostics.append({
                'receiver_id': int(rec.feature_id),
                'source_id': int(src_idx),
                'source_feature_id': int(getattr(src, 'feature_id', -1) or -1),
                'source_group': str(getattr(src, 'source_group', '') or ''),
                'model': str(getattr(src, 'model_name', '') or ''),
                'lp_dba': float(lp),
                'distance_xy_m': float(dist_xy),
                'distance_3d_m': float(_dist3d),
                'adiv_db': float(_adiv),
                'aatm_db': float(_aatm),
                'aground_db': float(_aground),
                'abar_db': float(abar_val),
                'mdt_state': str(_abar_state or ''),
                'obstacle_height_m': None if _obs_h_m is None else float(_obs_h_m),
                'threshold_m': None if _obs_thr_m is None else float(_obs_thr_m),
                'd1_m': None if _candidate_path_value(_obs_d1_m, _obs_h_m) is None else float(_obs_d1_m),
                'd2_m': None if _candidate_path_value(_obs_d2_m, _obs_h_m) is None else float(_obs_d2_m),
                'source_ground_z_m': path_src_z_m,
                'source_hub_height_m': float(src.hub_height),
                'source_acoustic_z_m': path_src_ac_z_m,
                'receiver_ground_z_m': path_rec_z_m,
                'receiver_height_m': dom_rec_h_m,
                'receiver_acoustic_z_m': path_rec_ac_z_m,
                'dominant_band_hz': None if _dom_freq is None else int(_dom_freq),
                'mdt_sample_step_m': path_mdt_sample_step_m,
                'mdt_num_points': path_mdt_num_points,
                'mdt_valid_points': path_mdt_valid_points,
                'mdt_invalid_points': path_mdt_invalid_points,
            })

            st = src_stats.setdefault(src_idx, {"n_recv": 0, "max_lp_db": None, "near_rec_m": None, "dom_rec_id": None})
            st["n_recv"] = int(st.get("n_recv", 0)) + 1
            if st.get("near_rec_m") is None or dist_xy < float(st.get("near_rec_m")):
                st["near_rec_m"] = float(dist_xy)
            if st.get("max_lp_db") is None or lp > float(st.get("max_lp_db")):
                st["max_lp_db"] = float(lp)
                st["dom_rec_id"] = int(rec.feature_id)
            if near_m is None or dist_xy < near_m:
                near_m = dist_xy
            if max_src_lp is None or lp > max_src_lp:
                max_src_lp = lp
                dom_model = src.model_name
                dom_group = src.source_group
                dom_park = src.park_name
                dom_src_idx = src_idx
                dom_src = src
                dom_dist3d = _dist3d
                dom_adiv = _adiv
                dom_aatm = _aatm
                dom_aground = _aground
                dom_abar = _abar
                dom_abar_state = _abar_state
                dom_obs_h_m = _obs_h_m
                dom_obs_d1_m = _active_path_value(_obs_d1_m, _abar_state)
                dom_obs_d2_m = _active_path_value(_obs_d2_m, _abar_state)
                dom_obs_thr_m = _obs_thr_m
                dom_src_z_m = _ground_z_or_none(src)
                dom_hub_h_m = float(src.hub_height)
                dom_src_ac_z_m = _source_acoustic_z_or_none(src)
                dom_ground_g = _g_eff
                dom_dom_freq = _dom_freq
                dom_spectrum_source = str(getattr(src, 'spectrum_source', '') or ('Fallback: generado desde LwA' if getattr(src, 'lw_octave', None) is None else ''))
                dom_src_layer_name = str(getattr(src, 'layer_name', '') or '')

        # If no source path has active Abar (>0), still populate the
        # "max Abar" diagnostic source with a meaningful fallback.
        # Otherwise the UI shows many N/A values and looks as if the DEM
        # or the other turbines were not evaluated. In that case the
        # physically correct interpretation is "no active screening":
        # Abar_max remains 0 dB, d1/d2 stay N/A because there is no
        # blocking obstacle, but source heights and state remain auditable.
        if n_src > 0 and maxab_src_idx is None:
            maxab_src_idx = maxobs_src_idx if maxobs_src_idx is not None else dom_src_idx
            maxab_state = 'no_screening'
            maxab_obs_h_m = 0.0
            maxab_obs_thr_m = maxobs_thr_m if maxobs_thr_m is not None else dom_obs_thr_m
            maxab_obs_d1_m = None
            maxab_obs_d2_m = None
            maxab_src_z_m = maxobs_src_z_m if maxobs_src_z_m is not None else dom_src_z_m
            maxab_hub_h_m = maxobs_hub_h_m if maxobs_hub_h_m is not None else dom_hub_h_m
            maxab_src_ac_z_m = maxobs_src_ac_z_m if maxobs_src_ac_z_m is not None else dom_src_ac_z_m

        if n_src > 0 and e_sum > 0.0:
            noise_dba = 10.0 * math.log10(e_sum)
            covered_flag = 1
            rec_abar_mean = rec_abar_sum / float(n_src)
            rec_abar_energy_weighted = rec_abar_energy_weighted_sum / rec_abar_energy_sum if rec_abar_energy_sum > 0.0 else 0.0
        else:
            noise_dba = 0.0
            covered_flag = 0
            rec_abar_mean = 0.0
            rec_abar_energy_weighted = 0.0
            zero_receivers += 1
            uncovered_ids.append(int(rec.feature_id))

        margin_db = float(noise_dba) - float(rec_limit)
        exceeds_flag = 1 if noise_dba > float(rec_limit) else 0
        if margin_db > 0.0:
            state_txt = 'supera'
        elif margin_db > -3.0:
            state_txt = 'near_limit'
        else:
            state_txt = 'cumple'

        applied_limits.append(float(rec_limit))
        _rtype_key = str(rec_type or 'no_type')
        receiver_type_counts[_rtype_key] = int(receiver_type_counts.get(_rtype_key, 0)) + 1
        _rtc = receiver_type_compliance.setdefault(_rtype_key, {'total': 0, 'covered': 0, 'exceed': 0})
        _rtc['total'] = int(_rtc.get('total', 0)) + 1
        if covered_flag == 1:
            _rtc['covered'] = int(_rtc.get('covered', 0)) + 1
        if exceeds_flag == 1:
            _rtc['exceed'] = int(_rtc.get('exceed', 0)) + 1
        if dom_ground_g is not None:
            ground_g_values.append(float(dom_ground_g))
            if str(ground_mode).lower() == 'landuse' and abs(float(dom_ground_g) - float(ground_factor_g)) > 1e-6:
                ground_from_landuse_count += 1
            else:
                ground_fallback_count += 1
        if exceeds_flag:
            n_exceed += 1

        if dom_src is not None and max_src_lp is not None:
            dom_links.append({
                'rec_id': int(rec.feature_id), 'src_id': int(dom_src_idx), 'model': dom_src.model_name,
                'source_group': dom_group, 'park_name': dom_park,
                'lp_dom_db': float(max_src_lp), 'dist_m': 0.0 if near_m is None else float(near_m),
                'dist3d_m': None if dom_dist3d is None else float(dom_dist3d),
                'adiv_db': None if dom_adiv is None else float(dom_adiv),
                'aatm_db': None if dom_aatm is None else float(dom_aatm),
                'aground_db': None if dom_aground is None else float(dom_aground),
                'abar_db': None if dom_abar is None else float(dom_abar),
                'abar_state': str(dom_abar_state or ''),
                'obs_h_m': None if dom_obs_h_m is None else float(dom_obs_h_m),
                'obs_d1_m': None if dom_obs_d1_m is None else float(dom_obs_d1_m),
                'obs_d2_m': None if dom_obs_d2_m is None else float(dom_obs_d2_m),
                'obs_thr_m': None if dom_obs_thr_m is None else float(dom_obs_thr_m),
                'src_z_m': None if dom_src_z_m is None else float(dom_src_z_m),
                'hub_h_m': None if dom_hub_h_m is None else float(dom_hub_h_m),
                'src_ac_z_m': None if dom_src_ac_z_m is None else float(dom_src_ac_z_m),
                'rec_z_m': None if dom_rec_z_m is None else float(dom_rec_z_m),
                'rec_h_m': None if dom_rec_h_m is None else float(dom_rec_h_m),
                'rec_ac_z_m': None if dom_rec_ac_z_m is None else float(dom_rec_ac_z_m),
                'maxab_src': None if maxab_src_idx is None else int(maxab_src_idx),
                'maxab_state': str(maxab_state or ''),
                'maxab_obs_h': None if maxab_obs_h_m is None else float(maxab_obs_h_m),
                'maxab_thr': None if maxab_obs_thr_m is None else float(maxab_obs_thr_m),
                'maxab_d1': None if maxab_obs_d1_m is None else float(maxab_obs_d1_m),
                'maxab_d2': None if maxab_obs_d2_m is None else float(maxab_obs_d2_m),
                'maxab_src_z': None if maxab_src_z_m is None else float(maxab_src_z_m),
                'maxab_hub_h': None if maxab_hub_h_m is None else float(maxab_hub_h_m),
                'maxab_src_ac_z': None if maxab_src_ac_z_m is None else float(maxab_src_ac_z_m),
                'maxobs_src': None if maxobs_src_idx is None else int(maxobs_src_idx),
                'maxobs_state': str(maxobs_state or ''),
                'maxobs_h': None if maxobs_h_m is None else float(maxobs_h_m),
                'maxobs_thr': None if maxobs_thr_m is None else float(maxobs_thr_m),
                'maxobs_d1': None if maxobs_d1_m is None else float(maxobs_d1_m),
                'maxobs_d2': None if maxobs_d2_m is None else float(maxobs_d2_m),
                'maxobs_src_z': None if maxobs_src_z_m is None else float(maxobs_src_z_m),
                'maxobs_hub_h': None if maxobs_hub_h_m is None else float(maxobs_hub_h_m),
                'maxobs_src_ac_z': None if maxobs_src_ac_z_m is None else float(maxobs_src_ac_z_m),
                'ground_g': None if dom_ground_g is None else float(dom_ground_g),
                'dom_freq': None if dom_dom_freq is None else int(dom_dom_freq),
                'spec_src': dom_spectrum_source,
                'src_lwa': float(dom_src.lwa),
                'src_x': float(dom_src.x), 'src_y': float(dom_src.y), 'rec_x': float(rec.x), 'rec_y': float(rec.y),
            })

        feat = QgsFeature(out_fields)
        feat.setGeometry(QgsGeometry(rec.geometry))
        orig_attrs = list(rec.attrs or [])
        if len(orig_attrs) < input_field_count:
            orig_attrs.extend([None] * (input_field_count - len(orig_attrs)))
        elif len(orig_attrs) > input_field_count:
            orig_attrs = orig_attrs[:input_field_count]
        feat.setAttributes(orig_attrs + [
            float(noise_dba),
            int(n_src),
            None if near_m is None else float(near_m),
            None if max_src_lp is None else float(max_src_lp),
            dom_model,
            dom_group,
            dom_park,
            None if dom_src is None else float(dom_src.lwa),
            None if dom_dist3d is None else float(dom_dist3d),
            None if dom_adiv is None else float(dom_adiv),
            None if dom_aatm is None else float(dom_aatm),
            None if dom_aground is None else float(dom_aground),
            None if dom_abar is None else float(dom_abar),
            float(rec_abar_max),
            float(rec_abar_mean),
            float(rec_abar_energy_weighted),
            int(rec_abar_screened_count),
            str(dom_abar_state or ''),
            None if dom_obs_h_m is None else float(dom_obs_h_m),
            None if dom_obs_d1_m is None else float(dom_obs_d1_m),
            None if dom_obs_d2_m is None else float(dom_obs_d2_m),
            None if dom_obs_thr_m is None else float(dom_obs_thr_m),
            None if dom_src_z_m is None else float(dom_src_z_m),
            None if dom_hub_h_m is None else float(dom_hub_h_m),
            None if dom_src_ac_z_m is None else float(dom_src_ac_z_m),
            None if dom_rec_z_m is None else float(dom_rec_z_m),
            None if dom_rec_h_m is None else float(dom_rec_h_m),
            None if dom_rec_ac_z_m is None else float(dom_rec_ac_z_m),
            None if maxab_src_idx is None else int(maxab_src_idx),
            str(maxab_state or ''),
            None if maxab_obs_h_m is None else float(maxab_obs_h_m),
            None if maxab_obs_thr_m is None else float(maxab_obs_thr_m),
            None if maxab_obs_d1_m is None else float(maxab_obs_d1_m),
            None if maxab_obs_d2_m is None else float(maxab_obs_d2_m),
            None if maxab_src_z_m is None else float(maxab_src_z_m),
            None if maxab_hub_h_m is None else float(maxab_hub_h_m),
            None if maxab_src_ac_z_m is None else float(maxab_src_ac_z_m),
            None if maxobs_src_idx is None else int(maxobs_src_idx),
            str(maxobs_state or ''),
            None if maxobs_h_m is None else float(maxobs_h_m),
            None if maxobs_thr_m is None else float(maxobs_thr_m),
            None if maxobs_d1_m is None else float(maxobs_d1_m),
            None if maxobs_d2_m is None else float(maxobs_d2_m),
            None if maxobs_src_z_m is None else float(maxobs_src_z_m),
            None if maxobs_hub_h_m is None else float(maxobs_hub_h_m),
            None if maxobs_src_ac_z_m is None else float(maxobs_src_ac_z_m),
            None if dom_ground_g is None else float(dom_ground_g),
            None if dom_dom_freq is None else int(dom_dom_freq),
            str(dom_spectrum_source),
            rec.eval_mode,
            "iso_aligned" if calculation_engine == "iso" else "consultoria_v2_3_2",
            int(covered_flag),
            float(rec_limit),
            float(margin_db),
            int(exceeds_flag),
            str(limit_src),
            str(receiver_limit_scenario or "custom"),
            str(limit_fld),
            str(rec_type),
            str(src_layer_name),
            str(dom_src_layer_name),
            str(state_txt),
            str(ground_mode or 'global'),
        ])
        out_feats.append(feat)
        if noise_dba > max_noise:
            max_noise = noise_dba
            max_noise_fid = rec.feature_id

    return ReceiverEvaluation(
        source_mem=source_mem,
        sidx=sidx,
        out_fields=out_fields,
        out_feats=out_feats,
        max_noise=float(max_noise),
        max_noise_fid=max_noise_fid,
        total_sources_used=int(total_sources_used),
        zero_receivers=int(zero_receivers),
        n_exceed=int(n_exceed),
        src_stats=src_stats,
        dom_links=dom_links,
        uncovered_ids=uncovered_ids,
        receiver_type_counts=receiver_type_counts,
        ground_g_values=ground_g_values,
        ground_fallback_count=int(ground_fallback_count),
        ground_from_landuse_count=int(ground_from_landuse_count),
        applied_limits=applied_limits,
        receiver_type_compliance=receiver_type_compliance,
        path_diagnostics=path_diagnostics,
    )

# -*- coding: utf-8 -*-
"""Pure Python noise calculation engine for QgsTask workers.

No QGIS layers, QgsProject or widgets are used here.  Inputs and outputs are
plain dictionaries/lists so the code can safely run inside a worker thread.
"""
from __future__ import annotations

import math
from typing import Any, Callable, Dict, List, Optional, Tuple

from ..noise_common import OCTAVE_BANDS, A_WEIGHTING, global_lwa_to_octave_spectrum
from ..noise_engine_iso import calculate_alpha_atm_iso, calculate_agr_iso_regions

ProgressCallback = Optional[Callable[[float], None]]
CancelCallback = Optional[Callable[[], bool]]


def _as_float(value: Any, default: float = 0.0) -> float:
    try:
        v = float(value)
        return v if math.isfinite(v) else float(default)
    except Exception:
        return float(default)


def _ground_z_from_dict(obj: Dict[str, Any]) -> Optional[float]:
    z = obj.get("z_ground")
    if z is None:
        return None
    try:
        return float(z)
    except Exception:
        return None


def _source_acoustic_z_from_dict(src: Dict[str, Any]) -> Optional[float]:
    z = _ground_z_from_dict(src)
    if z is None:
        return None
    return z + _as_float(src.get("hub_height"), 0.0)


def _receiver_acoustic_z_from_dict(rec: Dict[str, Any]) -> Optional[float]:
    z = _ground_z_from_dict(rec)
    if z is None:
        return None
    return z + _as_float(rec.get("receiver_height"), 0.0)


def _active_path_value(value: Any, state: str):
    return value if str(state or '').lower() == 'active' else None


def _candidate_path_value(value: Any, obstacle_height_m: Any):
    try:
        return value if float(obstacle_height_m or 0.0) > 0.0 else None
    except Exception:
        return None


class _GdalDemSampler:
    """Small GDAL-only DEM sampler safe for QgsTask worker threads."""

    def __init__(self, dem_path: str):
        self.dem_path = str(dem_path or "")
        self.ds = None
        self.band = None
        self.inv_gt = None
        self.pixel_size_m = None
        self.nodata = None
        if not self.dem_path:
            return
        try:
            from osgeo import gdal  # imported lazily so this module remains lightweight
            ds = gdal.Open(self.dem_path)
            if ds is None:
                return
            gt = ds.GetGeoTransform()
            inv = gdal.InvGeoTransform(gt)
            # GDAL bindings differ slightly across versions.  Recent versions
            # return the inverse transform directly; some older bindings may
            # wrap it in a (success, transform) tuple.
            if isinstance(inv, tuple) and len(inv) == 2 and isinstance(inv[0], (bool, int)) and isinstance(inv[1], tuple):
                inv = inv[1] if inv[0] else None
            if inv is None:
                return
            band = ds.GetRasterBand(1)
            if band is None:
                return
            self.ds = ds
            self.band = band
            self.inv_gt = inv
            self.nodata = band.GetNoDataValue()
            try:
                self.pixel_size_m = max(abs(float(gt[1])), abs(float(gt[5])))
            except Exception:
                self.pixel_size_m = None
        except Exception:
            self.ds = None
            self.band = None
            self.inv_gt = None

    @property
    def valid(self) -> bool:
        return self.ds is not None and self.band is not None and self.inv_gt is not None

    def sample(self, x: float, y: float) -> Optional[float]:
        if not self.valid:
            return None
        try:
            from osgeo import gdal
            px_f, py_f = gdal.ApplyGeoTransform(self.inv_gt, float(x), float(y))
            px = int(math.floor(px_f + 0.5))
            py = int(math.floor(py_f + 0.5))
            if px < 0 or py < 0 or px >= int(self.ds.RasterXSize) or py >= int(self.ds.RasterYSize):
                return None
            arr = self.band.ReadAsArray(px, py, 1, 1)
            if arr is None:
                return None
            val = float(arr[0][0])
            if self.nodata is not None and abs(val - float(self.nodata)) < 1e-9:
                return None
            if not math.isfinite(val):
                return None
            return val
        except Exception:
            return None

    def profile(self, x1: float, y1: float, x2: float, y2: float, num_points: Optional[int] = None) -> Optional[Dict[str, Any]]:
        """Extract a terrain profile for MDT screening.

        Invalid/no-data samples are not converted to 0.0.  If either endpoint is
        outside the DEM, the profile is rejected so Abar is reported as
        ``no_profile`` instead of creating artificial terrain barriers.
        """
        if not self.valid:
            return None
        dx = float(x2) - float(x1)
        dy = float(y2) - float(y1)
        d_total = math.hypot(dx, dy)
        if d_total <= 0.0:
            return None
        if num_points is None:
            # Point receivers should benefit from high-resolution DEM/DTM data.
            # A 5 m MDT is now sampled at ~5 m instead of being coarsened to
            # 10 m.  Keep an upper cap to avoid excessive cost on long paths.
            if self.pixel_size_m is not None and float(self.pixel_size_m) > 0.0:
                sample_step = max(float(self.pixel_size_m), 5.0)
            else:
                sample_step = 10.0
            num_points = int(math.ceil(d_total / sample_step)) + 1
            num_points = max(50, min(1200, num_points))
        num_points = max(2, int(num_points))
        elevations: List[float] = []
        distances_m: List[float] = []
        source_ground_z = None
        receiver_ground_z = None
        invalid_samples = 0
        for i in range(num_points):
            t = i / float(max(1, num_points - 1))
            x = float(x1) + t * dx
            y = float(y1) + t * dy
            z = self.sample(x, y)
            if i == 0:
                source_ground_z = z
            elif i == num_points - 1:
                receiver_ground_z = z
            if z is None:
                invalid_samples += 1
                continue
            elevations.append(float(z))
            distances_m.append(t * d_total)
        if source_ground_z is None or receiver_ground_z is None:
            return None
        if len(elevations) < 2:
            return None
        return {
            "elevations": elevations,
            "distances_m": distances_m,
            "total_distance_m": float(d_total),
            "sample_step_m": float(d_total / float(max(1, num_points - 1))),
            "pixel_size_m": self.pixel_size_m,
            "num_points": int(num_points),
            "valid_points": int(len(elevations)),
            "invalid_points": int(invalid_samples),
            "source_ground_z_m": float(source_ground_z),
            "receiver_ground_z_m": float(receiver_ground_z),
        }


def _detect_obstacle_state(profile_data: Dict[str, Any], z_source: float, z_receiver: float, activation_threshold_m: float = 1.0) -> Dict[str, Any]:
    elevations = list((profile_data or {}).get("elevations") or [])
    distances_m = list((profile_data or {}).get("distances_m") or [])
    d_total = _as_float((profile_data or {}).get("total_distance_m"), 0.0)
    n = len(elevations)
    if n < 2 or len(distances_m) != n or d_total <= 0.0:
        return {"obstacle_height_m": 0.0, "obstacle_distance_m": 0.0, "obstacle_index": None, "los_clear": True, "threshold_m": activation_threshold_m}
    max_diff = 0.0
    max_idx = None
    for i in range(1, n - 1):
        dist_i = _as_float(distances_m[i], 0.0)
        t = dist_i / d_total if d_total > 0.0 else 0.0
        z_line = float(z_source) + t * (float(z_receiver) - float(z_source))
        diff = _as_float(elevations[i], 0.0) - z_line
        if diff > max_diff:
            max_diff = diff
            max_idx = i
    if max_idx is None or max_diff <= float(activation_threshold_m):
        # Keep the raw maximum excess for diagnostics, but mark the path as
        # line-of-sight clear so Abar remains exactly zero. This does not change
        # the physics; it only helps explain why a DEM was active but no
        # topographic screening was applied.
        return {
            "obstacle_height_m": float(max_diff),
            "obstacle_distance_m": 0.0 if max_idx is None else float(distances_m[max_idx]),
            "obstacle_index": None if max_idx is None else int(max_idx),
            "los_clear": True,
            "threshold_m": activation_threshold_m,
        }
    return {"obstacle_height_m": float(max_diff), "obstacle_distance_m": float(distances_m[max_idx]), "obstacle_index": int(max_idx), "los_clear": False, "threshold_m": activation_threshold_m}


def _prepare_mdt_context(src: Dict[str, Any], rec: Dict[str, Any], dem_sampler: Optional[_GdalDemSampler]) -> Optional[Dict[str, Any]]:
    if dem_sampler is None or not dem_sampler.valid:
        return None
    profile_data = dem_sampler.profile(_as_float(src.get("x")), _as_float(src.get("y")), _as_float(rec.get("x")), _as_float(rec.get("y")))
    if profile_data is None:
        return None
    src_ground = src.get("z_ground") if src.get("z_ground") is not None else profile_data.get("source_ground_z_m")
    rec_ground = rec.get("z_ground") if rec.get("z_ground") is not None else profile_data.get("receiver_ground_z_m")
    if src_ground is None or rec_ground is None:
        return None
    z_source_total = _as_float(src_ground, 0.0) + _as_float(src.get("hub_height"), 0.0)
    z_receiver_total = _as_float(rec_ground, 0.0) + _as_float(rec.get("receiver_height"), 0.0)
    pixel_size = profile_data.get("pixel_size_m") or profile_data.get("sample_step_m") or 0.0
    activation_threshold_m = max(1.0, min(3.0, 0.2 * float(pixel_size or 0.0)))
    obstacle = _detect_obstacle_state(profile_data, z_source_total, z_receiver_total, activation_threshold_m=activation_threshold_m)
    d_total = _as_float(profile_data.get("total_distance_m"), 0.0)
    d1 = max(_as_float(obstacle.get("obstacle_distance_m"), 0.0), 1.0)
    d2 = max(d_total - d1, 1.0)
    return {
        "profile_data": profile_data,
        "obstacle": obstacle,
        "pixel_size_m": pixel_size,
        "activation_threshold_m": activation_threshold_m,
        "d_total_m": d_total,
        "d1_m": d1,
        "d2_m": d2,
        "source_ground_z_m": float(src_ground),
        "receiver_ground_z_m": float(rec_ground),
        "source_acoustic_z_m": float(z_source_total),
        "receiver_acoustic_z_m": float(z_receiver_total),
    }


def _fresnel_diffraction(freq_hz: int, obstacle_height_m: float, distance_source_obstacle_m: float, distance_obstacle_receiver_m: float) -> float:
    if obstacle_height_m <= 0.0:
        return 0.0
    c_sound = 343.0
    freq_hz = max(1, int(freq_hz))
    wavelength = c_sound / float(freq_hz)
    d1 = max(float(distance_source_obstacle_m), 1.0)
    d2 = max(float(distance_obstacle_receiver_m), 1.0)
    delta = 0.5 * (float(obstacle_height_m) ** 2) * ((1.0 / d1) + (1.0 / d2))
    C = (2.0 * delta) / max(wavelength, 1.0e-9)
    if C <= -2.0:
        abar = 0.0
    elif C <= 0.0:
        abar = 10.0 * math.log10(max(1.0e-9, 3.0 + 20.0 * C))
    elif C <= 3.5:
        abar = 10.0 * math.log10(3.0 + 80.0 * C)
    else:
        abar = 10.0 * math.log10(3.0 + 280.0 * C)
    return max(0.0, min(20.0, float(abar)))


def _calculate_abar_mdt(freq_hz: int, mdt_context: Optional[Dict[str, Any]]) -> float:
    if not mdt_context:
        return 0.0
    obstacle = mdt_context.get("obstacle") or {}
    if obstacle.get("los_clear", True):
        return 0.0
    return _fresnel_diffraction(
        int(freq_hz),
        _as_float(obstacle.get("obstacle_height_m"), 0.0),
        _as_float(mdt_context.get("d1_m"), 1.0),
        _as_float(mdt_context.get("d2_m"), 1.0),
    )


def _limit_for_receiver(rec: Dict[str, Any], params: Dict[str, Any]) -> Tuple[float, str, str]:
    rec_limit = _as_float(params.get("receiver_limit_dba"), 45.0)
    limit_src = "global"
    limit_fld = ""
    meta = rec.get("meta") or {}
    if str(params.get("receiver_limit_mode") or "global").lower() == "by_field":
        scenario = str(params.get("receiver_limit_scenario") or "custom").lower()
        if scenario == "day":
            v = meta.get("limit_day_dba")
            if v is not None:
                rec_limit = _as_float(v, rec_limit); limit_src = "capa"; limit_fld = str(params.get("receiver_limit_field_day") or "")
        elif scenario == "night":
            v = meta.get("limit_night_dba")
            if v is not None:
                rec_limit = _as_float(v, rec_limit); limit_src = "capa"; limit_fld = str(params.get("receiver_limit_field_night") or "")
        else:
            v = meta.get("limit_custom_dba")
            if v is not None:
                rec_limit = _as_float(v, rec_limit); limit_src = "capa"; limit_fld = str(params.get("receiver_limit_field_custom") or "")
    return float(rec_limit), limit_src, limit_fld


def _calc_fast(src: Dict[str, Any], rec: Dict[str, Any], params: Dict[str, Any]) -> Optional[Tuple[float, float, float, float, float, float, float, float, Optional[int]]]:
    min_distance_m = _as_float(params.get("min_distance_m"), 25.0)
    dx = _as_float(src.get("x")) - _as_float(rec.get("x"))
    dy = _as_float(src.get("y")) - _as_float(rec.get("y"))
    dist_xy = math.hypot(dx, dy)
    if dist_xy <= 0.0:
        dist_xy = min_distance_m
    z_src = (_as_float(src.get("z_ground"), 0.0) if src.get("z_ground") is not None else 0.0) + _as_float(src.get("hub_height"), 0.0)
    z_rec = (_as_float(rec.get("z_ground"), 0.0) if rec.get("z_ground") is not None else 0.0) + _as_float(rec.get("receiver_height"), 0.0)
    dist_3d = math.sqrt(max(min_distance_m * min_distance_m, dist_xy * dist_xy + (z_src - z_rec) ** 2))
    adiv = 20.0 * math.log10(max(dist_3d, 1.0)) + 11.0
    aatm = _as_float(params.get("alpha_db_per_m"), 0.005) * dist_3d
    g_eff = max(0.0, min(1.0, _as_float(params.get("ground_factor_g"), 0.5)))
    base = 3.0 * math.log10(1.0 + max(dist_xy, 1.0) / 100.0)
    height_factor = 1.0 / (1.0 + ((_as_float(src.get("hub_height"), 0.0) + _as_float(rec.get("receiver_height"), 0.0)) / 80.0))
    aground = max(0.0, min(6.0, g_eff * base * height_factor))
    lp = _as_float(src.get("lwa"), 0.0) - adiv - aatm - aground
    return float(lp), float(dist_xy), float(dist_3d), float(adiv), float(aatm), float(aground), 0.0, 'no_dem', 0.0, 0.0, 0.0, 0.0, float(g_eff), None


def _calc_iso(src: Dict[str, Any], rec: Dict[str, Any], params: Dict[str, Any], dem_sampler: Optional[_GdalDemSampler] = None) -> Optional[Tuple[float, float, float, float, float, float, float, float, Optional[int]]]:
    min_distance_m = _as_float(params.get("min_distance_m"), 25.0)
    dx = _as_float(src.get("x")) - _as_float(rec.get("x"))
    dy = _as_float(src.get("y")) - _as_float(rec.get("y"))
    dist_xy = math.hypot(dx, dy)
    if dist_xy <= 0.0:
        dist_xy = min_distance_m
    z_src = (_as_float(src.get("z_ground"), 0.0) if src.get("z_ground") is not None else 0.0) + _as_float(src.get("hub_height"), 0.0)
    z_rec = (_as_float(rec.get("z_ground"), 0.0) if rec.get("z_ground") is not None else 0.0) + _as_float(rec.get("receiver_height"), 0.0)
    dist_3d = math.sqrt(max(min_distance_m * min_distance_m, dist_xy * dist_xy + (z_src - z_rec) ** 2))
    adiv = 20.0 * math.log10(max(dist_3d, 1.0)) + 11.0
    ground_g = max(0.0, min(1.0, _as_float(params.get("ground_factor_g"), 0.5)))
    lw_octave_raw = src.get("lw_octave") or {}
    lw_octave = {int(k): _as_float(v, 0.0) for k, v in lw_octave_raw.items()} if lw_octave_raw else global_lwa_to_octave_spectrum(_as_float(src.get("lwa"), 0.0))
    mdt_context = _prepare_mdt_context(src, rec, dem_sampler) if dem_sampler is not None else None
    if mdt_context is None:
        mdt_abar_state = 'no_dem' if dem_sampler is None else 'no_profile'
        mdt_obs_h_m = 0.0
        mdt_d1_m = 0.0
        mdt_d2_m = 0.0
        mdt_thr_m = 0.0
    else:
        _obs = mdt_context.get('obstacle') or {}
        mdt_obs_h_m = _as_float(_obs.get('obstacle_height_m'), 0.0)
        mdt_d1_m = _as_float(mdt_context.get('d1_m'), 0.0)
        mdt_d2_m = _as_float(mdt_context.get('d2_m'), 0.0)
        mdt_thr_m = _as_float(mdt_context.get('activation_threshold_m'), 0.0)
        if bool(_obs.get('los_clear', True)):
            mdt_abar_state = 'los_clear' if mdt_obs_h_m <= 0.0 else 'below_threshold'
        else:
            mdt_abar_state = 'active'
    energy = 0.0
    aatm_vals: List[float] = []
    agr_vals: List[float] = []
    abar_vals: List[float] = []
    dom_freq = None
    dom_lpa = -1.0e99
    dom_aatm = 0.0
    dom_agr = 0.0
    dom_abar = 0.0
    for freq in OCTAVE_BANDS:
        f = int(freq)
        alpha = calculate_alpha_atm_iso(f, _as_float(params.get("temperature_c"), 15.0), _as_float(params.get("humidity_percent"), 70.0), _as_float(params.get("pressure_kpa"), 101.325))
        aatm = float(alpha) * dist_3d
        agr = float(calculate_agr_iso_regions(
            freq_hz=f,
            distance_xy_m=float(dist_xy),
            hub_height_m=_as_float(src.get("hub_height"), 0.0),
            receiver_height_m=_as_float(rec.get("receiver_height"), 0.0),
            ground_g=ground_g,
        ))
        abar = _calculate_abar_mdt(f, mdt_context)
        lpa = _as_float(lw_octave.get(f), 0.0) - adiv - aatm - agr - abar + float(A_WEIGHTING.get(f, 0.0))
        energy += 10.0 ** (lpa / 10.0)
        aatm_vals.append(aatm)
        agr_vals.append(agr)
        abar_vals.append(abar)
        if lpa > dom_lpa:
            dom_lpa = lpa
            dom_freq = f
            dom_aatm = float(aatm)
            dom_agr = float(agr)
            dom_abar = float(abar)
    lp_total = 10.0 * math.log10(energy) if energy > 0.0 else 0.0
    # Match the existing QGIS path: the breakdown fields shown in the receiver
    # layer/report correspond to the dominant A-weighted octave band for the
    # dominant source, not to the maximum attenuation over all bands.  The
    # maximum-across-bands values made reports look physically inconsistent
    # (e.g. an 8 kHz Aatm displayed together with a 1 kHz dominant band) even
    # though the energetic total was calculated correctly.
    return (
        float(lp_total), float(dist_xy), float(dist_3d), float(adiv),
        float(dom_aatm if dom_freq is not None else (max(aatm_vals) if aatm_vals else 0.0)),
        float(dom_agr if dom_freq is not None else (max(agr_vals) if agr_vals else 0.0)),
        float(dom_abar if dom_freq is not None else (max(abar_vals) if abar_vals else 0.0)),
        str(mdt_abar_state), float(mdt_obs_h_m), float(mdt_d1_m), float(mdt_d2_m), float(mdt_thr_m),
        float(ground_g), dom_freq,
    )


def evaluate_noise_snapshot(
    snapshot: Dict[str, Any],
    *,
    progress_callback: ProgressCallback = None,
    cancel_callback: CancelCallback = None,
    progress_start: float = 0.0,
    progress_end: float = 60.0,
) -> Dict[str, Any]:
    """Evaluate all receivers from a primitive snapshot."""
    sources = list(snapshot.get("sources") or [])
    receivers = list(snapshot.get("receivers") or [])
    params = dict(snapshot.get("params") or {})
    # Number of attributes originally present in the receiver input layer.
    # The background worker stores rows as a flat attribute list; if this
    # prefix is not normalized, all calculated diagnostics can shift one or
    # more columns in the reconstructed QGIS result layer and in the report.
    input_field_count = len(snapshot.get("field_specs") or [])
    radius = _as_float(params.get("max_radius_m"), 5000.0)
    radius_sq = radius * radius
    engine_key = str(params.get("calculation_engine") or "fast").strip().lower()
    dem_sampler = None
    if engine_key == "iso" and str(params.get("dem_path") or ""):
        try:
            dem_sampler = _GdalDemSampler(str(params.get("dem_path") or ""))
            if dem_sampler is not None and not dem_sampler.valid:
                dem_sampler = None
        except Exception:
            dem_sampler = None

    def _progress(i: int, total: int) -> None:
        if progress_callback is None:
            return
        try:
            value = progress_start + (progress_end - progress_start) * float(i) / float(max(1, total))
            progress_callback(max(0.0, min(100.0, value)))
        except Exception:
            pass

    def _canceled() -> bool:
        if cancel_callback is None:
            return False
        try:
            return bool(cancel_callback())
        except Exception:
            return False

    rows: List[Dict[str, Any]] = []
    max_noise = -1.0
    max_noise_fid = None
    total_sources_used = 0
    zero_receivers = 0
    n_exceed = 0
    src_stats: Dict[int, Dict[str, Any]] = {i: {"n_recv": 0, "max_lp_db": None, "near_rec_m": None, "dom_rec_id": None} for i in range(len(sources))}
    dom_links: List[Dict[str, Any]] = []
    uncovered_ids: List[int] = []
    receiver_type_counts: Dict[str, int] = {}
    receiver_type_compliance: Dict[str, Dict[str, int]] = {}
    path_diagnostics: List[Dict[str, Any]] = []
    ground_g_values: List[float] = []
    ground_fallback_count = 0
    ground_from_landuse_count = 0
    applied_limits: List[float] = []

    n_total = len(receivers)
    for ridx, rec in enumerate(receivers):
        if _canceled():
            raise RuntimeError("Tarea de ruido cancelada.")
        rec_limit, limit_src, limit_fld = _limit_for_receiver(rec, params)
        meta = rec.get("meta") or {}
        rec_type = str(meta.get("receiver_type") or "")
        src_layer_name = str(meta.get("source_layer_name") or "")
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
        dom_abar = 0.0
        dom_abar_state = ''
        dom_obs_h_m = None
        dom_obs_d1_m = None
        dom_obs_d2_m = None
        dom_obs_thr_m = None
        dom_src_z_m = None
        dom_hub_h_m = None
        dom_src_ac_z_m = None
        dom_rec_z_m = _ground_z_from_dict(rec)
        dom_rec_h_m = _as_float(rec.get("receiver_height"), 0.0)
        dom_rec_ac_z_m = _receiver_acoustic_z_from_dict(rec)
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
        dom_spectrum_source = ""
        dom_src_layer_name = ""
        # Receiver-level Abar diagnostics for all contributing source paths.
        # Keep this schema aligned with results.evaluator.build_receiver_output_fields().
        rec_abar_sum = 0.0
        rec_abar_max = 0.0
        rec_abar_energy_weighted_sum = 0.0
        rec_abar_energy_sum = 0.0
        rec_abar_screened_count = 0

        rx = _as_float(rec.get("x"))
        ry = _as_float(rec.get("y"))
        for src_idx, src in enumerate(sources):
            dx = _as_float(src.get("x")) - rx
            dy = _as_float(src.get("y")) - ry
            if dx * dx + dy * dy > radius_sq:
                continue
            calc = _calc_iso(src, rec, params, dem_sampler=dem_sampler) if engine_key == "iso" else _calc_fast(src, rec, params)
            if calc is None:
                continue
            lp, dist_xy, dist3d, adiv, aatm, aground, abar, abar_state, obs_h_m, obs_d1_m, obs_d2_m, obs_thr_m, g_eff, dom_freq = calc
            if dist_xy > radius:
                continue
            source_energy = 10.0 ** (lp / 10.0)
            e_sum += source_energy
            n_src += 1
            total_sources_used += 1
            abar_val = max(0.0, _as_float(abar, 0.0))
            rec_abar_sum += abar_val
            if abar_val > rec_abar_max:
                rec_abar_max = abar_val
                maxab_src_idx = src_idx
                maxab_state = str(abar_state or '')
                maxab_obs_h_m = obs_h_m
                maxab_obs_thr_m = obs_thr_m
                maxab_obs_d1_m = _active_path_value(obs_d1_m, abar_state)
                maxab_obs_d2_m = _active_path_value(obs_d2_m, abar_state)
                maxab_src_z_m = _ground_z_from_dict(src)
                maxab_hub_h_m = _as_float(src.get("hub_height"), 0.0)
                maxab_src_ac_z_m = _source_acoustic_z_from_dict(src)
            rec_abar_energy_weighted_sum += abar_val * source_energy
            rec_abar_energy_sum += source_energy
            if abar_val > 0.005 or str(abar_state or '').lower() == 'active':
                rec_abar_screened_count += 1
            try:
                obs_candidate = max(0.0, float(obs_h_m or 0.0))
            except Exception:
                obs_candidate = 0.0
            if maxobs_h_m is None or obs_candidate > float(maxobs_h_m or 0.0):
                maxobs_src_idx = src_idx
                maxobs_state = str(abar_state or '')
                maxobs_h_m = obs_candidate
                maxobs_thr_m = obs_thr_m
                maxobs_d1_m = _candidate_path_value(obs_d1_m, obs_candidate)
                maxobs_d2_m = _candidate_path_value(obs_d2_m, obs_candidate)
                maxobs_src_z_m = _ground_z_from_dict(src)
                maxobs_hub_h_m = _as_float(src.get("hub_height"), 0.0)
                maxobs_src_ac_z_m = _source_acoustic_z_from_dict(src)

            path_diagnostics.append({
                "receiver_id": int(rec.get("feature_id", -1)),
                "source_id": int(src_idx),
                "source_feature_id": int(src.get("feature_id", -1) or -1),
                "source_group": str(src.get("source_group") or ""),
                "model": str(src.get("model_name") or ""),
                "lp_dba": float(lp),
                "distance_xy_m": float(dist_xy),
                "distance_3d_m": float(dist3d),
                "adiv_db": float(adiv),
                "aatm_db": float(aatm),
                "aground_db": float(aground),
                "abar_db": float(abar_val),
                "mdt_state": str(abar_state or ""),
                "obstacle_height_m": None if obs_h_m is None else float(obs_h_m),
                "threshold_m": None if obs_thr_m is None else float(obs_thr_m),
                "d1_m": None if _candidate_path_value(obs_d1_m, obs_h_m) is None else float(obs_d1_m),
                "d2_m": None if _candidate_path_value(obs_d2_m, obs_h_m) is None else float(obs_d2_m),
                "source_ground_z_m": _ground_z_from_dict(src),
                "source_hub_height_m": _as_float(src.get("hub_height"), 0.0),
                "source_acoustic_z_m": _source_acoustic_z_from_dict(src),
                "receiver_ground_z_m": dom_rec_z_m,
                "receiver_height_m": dom_rec_h_m,
                "receiver_acoustic_z_m": dom_rec_ac_z_m,
                "dominant_band_hz": None if dom_freq is None else int(dom_freq),
            })
            st = src_stats.setdefault(src_idx, {"n_recv": 0, "max_lp_db": None, "near_rec_m": None, "dom_rec_id": None})
            st["n_recv"] = int(st.get("n_recv", 0)) + 1
            if st.get("near_rec_m") is None or dist_xy < _as_float(st.get("near_rec_m"), 1.0e99):
                st["near_rec_m"] = float(dist_xy)
            if st.get("max_lp_db") is None or lp > _as_float(st.get("max_lp_db"), -1.0e99):
                st["max_lp_db"] = float(lp)
                st["dom_rec_id"] = int(rec.get("feature_id", -1))
            if near_m is None or dist_xy < near_m:
                near_m = dist_xy
            if max_src_lp is None or lp > max_src_lp:
                max_src_lp = lp
                dom_src_idx = src_idx
                dom_src = src
                dom_model = str(src.get("model_name") or "")
                dom_group = str(src.get("source_group") or "")
                dom_park = str(src.get("park_name") or "")
                dom_dist3d = dist3d
                dom_adiv = adiv
                dom_aatm = aatm
                dom_aground = aground
                dom_abar = abar
                dom_abar_state = abar_state
                dom_obs_h_m = obs_h_m
                dom_obs_d1_m = _active_path_value(obs_d1_m, abar_state)
                dom_obs_d2_m = _active_path_value(obs_d2_m, abar_state)
                dom_obs_thr_m = obs_thr_m
                dom_src_z_m = _ground_z_from_dict(src)
                dom_hub_h_m = _as_float(src.get("hub_height"), 0.0)
                dom_src_ac_z_m = _source_acoustic_z_from_dict(src)
                dom_ground_g = g_eff
                dom_dom_freq = dom_freq
                dom_spectrum_source = str(src.get("spectrum_source") or ("Fallback: generado desde LwA" if not src.get("lw_octave") else ""))
                dom_src_layer_name = str(src.get("layer_name") or "")

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
            uncovered_ids.append(int(rec.get("feature_id", -1)))

        margin_db = float(noise_dba) - float(rec_limit)
        exceeds_flag = 1 if noise_dba > rec_limit else 0
        state_txt = "supera" if margin_db > 0.0 else ("near_limit" if margin_db > -3.0 else "cumple")
        applied_limits.append(float(rec_limit))
        rtype_key = str(rec_type or "no_type")
        receiver_type_counts[rtype_key] = int(receiver_type_counts.get(rtype_key, 0)) + 1
        rtc = receiver_type_compliance.setdefault(rtype_key, {"total": 0, "covered": 0, "exceed": 0})
        rtc["total"] = int(rtc.get("total", 0)) + 1
        if covered_flag:
            rtc["covered"] = int(rtc.get("covered", 0)) + 1
        if exceeds_flag:
            rtc["exceed"] = int(rtc.get("exceed", 0)) + 1
        if dom_ground_g is not None:
            ground_g_values.append(float(dom_ground_g))
            ground_fallback_count += 1
        if exceeds_flag:
            n_exceed += 1
        if dom_src is not None and max_src_lp is not None:
            dom_links.append({
                "rec_id": int(rec.get("feature_id", -1)), "src_id": int(dom_src_idx), "model": dom_model,
                "source_group": dom_group, "park_name": dom_park, "lp_dom_db": float(max_src_lp),
                "dist_m": 0.0 if near_m is None else float(near_m),
                "dist3d_m": None if dom_dist3d is None else float(dom_dist3d),
                "adiv_db": None if dom_adiv is None else float(dom_adiv),
                "aatm_db": None if dom_aatm is None else float(dom_aatm),
                "aground_db": None if dom_aground is None else float(dom_aground),
                "abar_db": None if dom_abar is None else float(dom_abar),
                "abar_state": str(dom_abar_state or ''),
                "obs_h_m": None if dom_obs_h_m is None else float(dom_obs_h_m),
                "obs_d1_m": None if dom_obs_d1_m is None else float(dom_obs_d1_m),
                "obs_d2_m": None if dom_obs_d2_m is None else float(dom_obs_d2_m),
                "obs_thr_m": None if dom_obs_thr_m is None else float(dom_obs_thr_m),
                "src_z_m": None if dom_src_z_m is None else float(dom_src_z_m),
                "hub_h_m": None if dom_hub_h_m is None else float(dom_hub_h_m),
                "src_ac_z_m": None if dom_src_ac_z_m is None else float(dom_src_ac_z_m),
                "rec_z_m": None if dom_rec_z_m is None else float(dom_rec_z_m),
                "rec_h_m": None if dom_rec_h_m is None else float(dom_rec_h_m),
                "rec_ac_z_m": None if dom_rec_ac_z_m is None else float(dom_rec_ac_z_m),
                "maxab_src": None if maxab_src_idx is None else int(maxab_src_idx),
                "maxab_state": str(maxab_state or ''),
                "maxab_obs_h": None if maxab_obs_h_m is None else float(maxab_obs_h_m),
                "maxab_thr": None if maxab_obs_thr_m is None else float(maxab_obs_thr_m),
                "maxab_d1": None if maxab_obs_d1_m is None else float(maxab_obs_d1_m),
                "maxab_d2": None if maxab_obs_d2_m is None else float(maxab_obs_d2_m),
                "maxab_src_z": None if maxab_src_z_m is None else float(maxab_src_z_m),
                "maxab_hub_h": None if maxab_hub_h_m is None else float(maxab_hub_h_m),
                "maxab_src_ac_z": None if maxab_src_ac_z_m is None else float(maxab_src_ac_z_m),
                "ground_g": None if dom_ground_g is None else float(dom_ground_g),
                "dom_freq": None if dom_dom_freq is None else int(dom_dom_freq),
                "spec_src": dom_spectrum_source,
                "src_lwa": float(_as_float(dom_src.get("lwa"), 0.0)),
                "src_x": float(_as_float(dom_src.get("x"))), "src_y": float(_as_float(dom_src.get("y"))),
                "rec_x": float(rx), "rec_y": float(ry),
            })
        orig_attrs = list(rec.get("attrs") or [])
        if input_field_count >= 0:
            if len(orig_attrs) < input_field_count:
                orig_attrs.extend([None] * (input_field_count - len(orig_attrs)))
            elif len(orig_attrs) > input_field_count:
                orig_attrs = orig_attrs[:input_field_count]
        attrs = orig_attrs + [
            float(noise_dba), int(n_src), None if near_m is None else float(near_m),
            None if max_src_lp is None else float(max_src_lp), dom_model, dom_group, dom_park,
            None if dom_src is None else float(_as_float(dom_src.get("lwa"), 0.0)),
            None if dom_dist3d is None else float(dom_dist3d), None if dom_adiv is None else float(dom_adiv),
            None if dom_aatm is None else float(dom_aatm), None if dom_aground is None else float(dom_aground),
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
            None if dom_dom_freq is None else int(dom_dom_freq), str(dom_spectrum_source),
            str(rec.get("eval_mode") or "point"), "iso_aligned" if engine_key == "iso" else "consultoria_v2_3_2",
            int(covered_flag), float(rec_limit), float(margin_db), int(exceeds_flag),
            str(limit_src), str(params.get("receiver_limit_scenario") or "custom"), str(limit_fld), str(rec_type),
            str(src_layer_name), str(dom_src_layer_name), str(state_txt), str(params.get("ground_mode") or "global"),
        ]
        # Named Top receivers/UI summary.  Keep this independent from the
        # raw QgsFeature attribute vector so the dialog/CSV cannot be broken by
        # field-order changes, duplicate input field names, or schema evolution.
        summary = {
            "fid": int(rec.get("feature_id", -1)),
            "rec_id": int(rec.get("feature_id", -1)),
            "rec_type": str(rec_type),
            "noise_dba": float(noise_dba),
            "limit_dba": float(rec_limit),
            "margin_db": float(margin_db),
            "state": str(state_txt),
            "exceeds": int(exceeds_flag),
            "n_src": int(n_src),
            "near_m": None if near_m is None else float(near_m),
            "dom_model": str(dom_model),
            "dom_group": str(dom_group),
            "dom_park": str(dom_park),
            "dom_src_lyr": str(dom_src_layer_name),
            "src_lwa": None if dom_src is None else float(_as_float(dom_src.get("lwa"), 0.0)),
            "adiv_db": None if dom_adiv is None else float(dom_adiv),
            "aatm_db": None if dom_aatm is None else float(dom_aatm),
            "aground_db": None if dom_aground is None else float(dom_aground),
            "abar_db": None if dom_abar is None else float(dom_abar),
            "abar_max_db": float(rec_abar_max),
            "abar_mean_db": float(rec_abar_mean),
            "abar_ew_db": float(rec_abar_energy_weighted),
            "abar_screen_n": int(rec_abar_screened_count),
            "dom_freq": None if dom_dom_freq is None else int(dom_dom_freq),
            "abar_state": str(dom_abar_state or ''),
            "obs_h_m": None if dom_obs_h_m is None else float(dom_obs_h_m),
            "obs_thr_m": None if dom_obs_thr_m is None else float(dom_obs_thr_m),
            "obs_d1_m": None if dom_obs_d1_m is None else float(dom_obs_d1_m),
            "obs_d2_m": None if dom_obs_d2_m is None else float(dom_obs_d2_m),
            "src_z_m": None if dom_src_z_m is None else float(dom_src_z_m),
            "hub_h_m": None if dom_hub_h_m is None else float(dom_hub_h_m),
            "src_ac_z_m": None if dom_src_ac_z_m is None else float(dom_src_ac_z_m),
            "rec_z_m": None if dom_rec_z_m is None else float(dom_rec_z_m),
            "rec_h_m": None if dom_rec_h_m is None else float(dom_rec_h_m),
            "rec_ac_z_m": None if dom_rec_ac_z_m is None else float(dom_rec_ac_z_m),
            "maxab_src": None if maxab_src_idx is None else int(maxab_src_idx),
            "maxab_state": str(maxab_state or ''),
            "maxab_obs_h": None if maxab_obs_h_m is None else float(maxab_obs_h_m),
            "maxab_thr": None if maxab_obs_thr_m is None else float(maxab_obs_thr_m),
            "maxab_d1": None if maxab_obs_d1_m is None else float(maxab_obs_d1_m),
            "maxab_d2": None if maxab_obs_d2_m is None else float(maxab_obs_d2_m),
            "maxab_src_z": None if maxab_src_z_m is None else float(maxab_src_z_m),
            "maxab_hub_h": None if maxab_hub_h_m is None else float(maxab_hub_h_m),
            "maxab_src_ac_z": None if maxab_src_ac_z_m is None else float(maxab_src_ac_z_m),
            "maxobs_src": None if maxobs_src_idx is None else int(maxobs_src_idx),
            "maxobs_state": str(maxobs_state or ''),
            "maxobs_h": None if maxobs_h_m is None else float(maxobs_h_m),
            "maxobs_thr": None if maxobs_thr_m is None else float(maxobs_thr_m),
            "maxobs_d1": None if maxobs_d1_m is None else float(maxobs_d1_m),
            "maxobs_d2": None if maxobs_d2_m is None else float(maxobs_d2_m),
            "maxobs_src_z": None if maxobs_src_z_m is None else float(maxobs_src_z_m),
            "maxobs_hub_h": None if maxobs_hub_h_m is None else float(maxobs_hub_h_m),
            "maxobs_src_ac_z": None if maxobs_src_ac_z_m is None else float(maxobs_src_ac_z_m),
        }
        rows.append({
            "feature_id": int(rec.get("feature_id", -1)),
            "geometry_wkt": str(rec.get("geometry_wkt") or ""),
            "attrs": attrs,
            "summary": summary,
        })
        if noise_dba > max_noise:
            max_noise = noise_dba
            max_noise_fid = int(rec.get("feature_id", -1))
        if ridx % 10 == 0 or ridx + 1 == n_total:
            _progress(ridx + 1, n_total)

    return {
        "rows": rows,
        "max_noise": float(max_noise),
        "max_noise_fid": max_noise_fid,
        "total_sources_used": int(total_sources_used),
        "zero_receivers": int(zero_receivers),
        "n_exceed": int(n_exceed),
        "src_stats": src_stats,
        "dom_links": dom_links,
        "uncovered_ids": uncovered_ids,
        "receiver_type_counts": receiver_type_counts,
        "ground_g_values": ground_g_values,
        "ground_fallback_count": int(ground_fallback_count),
        "ground_from_landuse_count": int(ground_from_landuse_count),
        "applied_limits": applied_limits,
        "receiver_type_compliance": receiver_type_compliance,
        "path_diagnostics": path_diagnostics,
    }

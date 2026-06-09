# -*- coding: utf-8 -*-
"""Background generation of noise raster maps.

The worker part of this module intentionally works only with primitive Python
snapshots and GDAL. QGIS layers, QgsProject and Qt widgets are touched only in
``finished()``, which QGIS calls back on the main thread.
"""
from __future__ import annotations

import math
import os
import tempfile
from typing import Any, Callable, Dict, List, Optional, Tuple

import numpy as np
from osgeo import gdal, osr

from qgis.core import QgsApplication, QgsProject, QgsRasterLayer, QgsTask

from ..noise_common import OCTAVE_BANDS, A_WEIGHTING, global_lwa_to_octave_spectrum, log as _log
from ..noise_engine_iso import calculate_alpha_atm_iso, calculate_agr_iso_regions
from ..tasks.pure_engine import _GdalDemSampler, _prepare_mdt_context, _calculate_abar_mdt
from ..qgis_io.common import _remove_existing_layers_by_name, _unique_temp_output
from ..qgis_io.layers import _apply_raster_heatmap_style, _build_isophones_layer_from_raster


GridFinishedCallback = Callable[[bool, Dict[str, Any], Optional[Any], Optional[Any], Optional[str]], None]


def _snapshot_sources(raw_sources: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Return a defensive primitive-only copy of source snapshots."""
    out: List[Dict[str, Any]] = []
    for src in raw_sources or []:
        try:
            lw_octave_raw = src.get("lw_octave") or {}
            lw_octave = {int(k): float(v) for k, v in lw_octave_raw.items()}
            out.append({
                "model_name": str(src.get("model_name") or ""),
                "source_group": str(src.get("source_group") or ""),
                "park_name": str(src.get("park_name") or ""),
                "layer_name": str(src.get("layer_name") or ""),
                "x": float(src.get("x")),
                "y": float(src.get("y")),
                "hub_height": float(src.get("hub_height") or 0.0),
                "diameter": None if src.get("diameter") is None else float(src.get("diameter")),
                "lwa": float(src.get("lwa") or 0.0),
                "feature_id": int(src.get("feature_id") or -1),
                "z_ground": None if src.get("z_ground") is None else float(src.get("z_ground")),
                "lw_octave": lw_octave,
                "spectrum_source": str(src.get("spectrum_source") or ""),
            })
        except Exception:
            continue
    return out


def _extent_from_sources(sources: List[Dict[str, Any]], max_radius_m: float, grid_resolution_m: float) -> Tuple[float, float, float, float]:
    xs = [float(s["x"]) for s in sources]
    ys = [float(s["y"]) for s in sources]
    pad = max(float(max_radius_m), float(grid_resolution_m) * 2.0, 100.0)
    return (min(xs) - pad, min(ys) - pad, max(xs) + pad, max(ys) + pad)


def _sample_gdal_raster_nearest(ds: Any, inv_gt: Tuple[float, ...], x: float, y: float, band_index: int = 1) -> Tuple[float, bool]:
    """Sample a GDAL raster at map coordinates without using QGIS objects."""
    try:
        px_f, py_f = gdal.ApplyGeoTransform(inv_gt, float(x), float(y))
        px = int(math.floor(px_f + 0.5))
        py = int(math.floor(py_f + 0.5))
        if px < 0 or py < 0 or px >= int(ds.RasterXSize) or py >= int(ds.RasterYSize):
            return 0.0, False
        band = ds.GetRasterBand(int(band_index))
        arr = band.ReadAsArray(px, py, 1, 1)
        if arr is None:
            return 0.0, False
        val = float(arr[0][0])
        nodata = band.GetNoDataValue()
        if nodata is not None and abs(val - float(nodata)) < 1e-9:
            return 0.0, False
        if not math.isfinite(val):
            return 0.0, False
        return val, True
    except Exception:
        return 0.0, False


class _GdalArraySampler:
    """Vectorized GDAL sampler used by the background raster task.

    It reads band 1 into a NumPy array once and then samples arrays of map
    coordinates without using live QGIS raster objects.  If the DEM is too large
    to cache safely, ``valid`` becomes False and the caller can fall back to the
    cheaper distance/elevation-only path.
    """

    def __init__(self, dem_path: str, *, max_cached_cells: int = 25000000):
        self.dem_path = str(dem_path or "")
        self.valid = False
        self.array = None
        self.inv_gt = None
        self.nodata = None
        self.width = 0
        self.height = 0
        self.pixel_size_m = None
        self.error = ""
        if not self.dem_path:
            self.error = "No DEM path provided."
            return
        try:
            ds = gdal.Open(self.dem_path)
            if ds is None:
                self.error = f"Could not open DEM: {self.dem_path}"
                return
            self.width = int(ds.RasterXSize)
            self.height = int(ds.RasterYSize)
            n_cells = self.width * self.height
            if n_cells <= 0:
                self.error = "DEM has no cells."
                return
            if n_cells > int(max_cached_cells):
                self.error = f"DEM too large for cached screening ({n_cells} cells)."
                return
            gt = ds.GetGeoTransform()
            inv = gdal.InvGeoTransform(gt)
            if isinstance(inv, tuple) and len(inv) == 2 and isinstance(inv[0], (bool, int)) and isinstance(inv[1], tuple):
                inv = inv[1] if inv[0] else None
            if inv is None:
                self.error = "Could not invert DEM geotransform."
                return
            band = ds.GetRasterBand(1)
            if band is None:
                self.error = "DEM has no band 1."
                return
            arr = band.ReadAsArray()
            if arr is None:
                self.error = "Could not read DEM band 1."
                return
            self.array = np.asarray(arr, dtype=np.float64)
            self.inv_gt = tuple(float(v) for v in inv)
            self.nodata = band.GetNoDataValue()
            try:
                self.pixel_size_m = max(abs(float(gt[1])), abs(float(gt[5])))
            except Exception:
                self.pixel_size_m = None
            self.valid = True
        except Exception as exc:
            self.error = str(exc)
            self.valid = False

    def sample_array(self, x: np.ndarray, y: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
        """Nearest-neighbour sample for arrays of map coordinates.

        Returns ``(values, valid_mask)`` with the same broadcasted shape as the
        input arrays.
        """
        x_arr, y_arr = np.broadcast_arrays(np.asarray(x, dtype=np.float64), np.asarray(y, dtype=np.float64))
        values = np.zeros(x_arr.shape, dtype=np.float64)
        valid = np.zeros(x_arr.shape, dtype=bool)
        if not self.valid or self.array is None or self.inv_gt is None:
            return values, valid
        inv = self.inv_gt
        px_f = inv[0] + inv[1] * x_arr + inv[2] * y_arr
        py_f = inv[3] + inv[4] * x_arr + inv[5] * y_arr
        px = np.rint(px_f).astype(np.int64)
        py = np.rint(py_f).astype(np.int64)
        inside = (px >= 0) & (py >= 0) & (px < self.width) & (py < self.height)
        if not np.any(inside):
            return values, valid
        sampled = self.array[py[inside], px[inside]]
        sampled_valid = np.isfinite(sampled)
        if self.nodata is not None:
            sampled_valid &= np.abs(sampled - float(self.nodata)) > 1e-9
        values_inside = np.zeros(sampled.shape, dtype=np.float64)
        values_inside[sampled_valid] = sampled[sampled_valid]
        values[inside] = values_inside
        tmp_valid = np.zeros(sampled.shape, dtype=bool)
        tmp_valid[sampled_valid] = True
        valid[inside] = tmp_valid
        return values, valid

    def sample_scalar(self, x: float, y: float) -> Optional[float]:
        vals, valid = self.sample_array(np.asarray([[float(x)]], dtype=np.float64), np.asarray([[float(y)]], dtype=np.float64))
        if bool(valid[0, 0]):
            return float(vals[0, 0])
        return None


def _fresnel_diffraction_array(freq_hz: int, obstacle_height_m: np.ndarray, d1_m: np.ndarray, d2_m: np.ndarray) -> np.ndarray:
    """Vectorized version of the ISO-aligned Fresnel diffraction approximation."""
    h = np.maximum(np.asarray(obstacle_height_m, dtype=np.float64), 0.0)
    d1 = np.maximum(np.asarray(d1_m, dtype=np.float64), 1.0)
    d2 = np.maximum(np.asarray(d2_m, dtype=np.float64), 1.0)
    freq = max(1, int(freq_hz))
    wavelength = 343.0 / float(freq)
    delta = 0.5 * h * h * ((1.0 / d1) + (1.0 / d2))
    C = (2.0 * delta) / max(wavelength, 1.0e-9)
    abar = np.zeros_like(C, dtype=np.float64)
    m = (C > -2.0) & (C <= 0.0)
    if np.any(m):
        abar[m] = 10.0 * np.log10(np.maximum(1.0e-9, 3.0 + 20.0 * C[m]))
    m = (C > 0.0) & (C <= 3.5)
    if np.any(m):
        abar[m] = 10.0 * np.log10(3.0 + 80.0 * C[m])
    m = C > 3.5
    if np.any(m):
        abar[m] = 10.0 * np.log10(3.0 + 280.0 * C[m])
    return np.clip(abar, 0.0, 20.0)


def _detect_mdt_obstacle_grid(
    *,
    src: Dict[str, Any],
    xs: np.ndarray,
    ys: np.ndarray,
    z_rec_total: np.ndarray,
    dist_xy: np.ndarray,
    mask: np.ndarray,
    dem_sampler: Optional[_GdalArraySampler],
    effective_resolution: float,
) -> Tuple[np.ndarray, np.ndarray, np.ndarray, Dict[str, Any]]:
    """Approximate terrain screening for a source-to-raster-cell block.

    The task samples a few intermediate points along every source-cell line,
    detects the dominant terrain point above the line of sight, and later turns
    that obstacle into a frequency-dependent Abar.  This is intentionally an
    efficient raster approximation of the receptor profile method used by the
    detailed ISO point calculation.
    """
    shape = np.broadcast_shapes(np.shape(xs), np.shape(ys), np.shape(z_rec_total))
    h_obs = np.zeros(shape, dtype=np.float64)
    d1 = np.ones(shape, dtype=np.float64)
    d2 = np.maximum(np.broadcast_to(dist_xy, shape).astype(np.float64), 1.0)
    diag = {"screening_available": False, "screened_cells": 0, "max_obstacle_m": 0.0, "max_abar_1000_db": 0.0}
    if dem_sampler is None or not dem_sampler.valid:
        if dem_sampler is not None and getattr(dem_sampler, "error", ""):
            diag["screening_error"] = dem_sampler.error
        return h_obs, d1, d2, diag

    sx = float(src["x"])
    sy = float(src["y"])
    src_ground = src.get("z_ground")
    if src_ground is None:
        src_ground = dem_sampler.sample_scalar(sx, sy)
    z_src_total = (float(src_ground) if src_ground is not None else 0.0) + float(src.get("hub_height") or 0.0)
    z_rec_total = np.asarray(z_rec_total, dtype=np.float64)
    xs_full, ys_full = np.broadcast_arrays(np.asarray(xs, dtype=np.float64), np.asarray(ys, dtype=np.float64))
    max_diff = np.full(shape, -np.inf, dtype=np.float64)
    best_t = np.zeros(shape, dtype=np.float64)

    # Fixed fractions keep the raster responsive and make the DEM visible in
    # the map.  Receptor-specific detailed reports still use the denser profile.
    for t in (0.15, 0.30, 0.45, 0.60, 0.75, 0.90):
        x_t = sx + float(t) * (xs_full - sx)
        y_t = sy + float(t) * (ys_full - sy)
        z_dem, valid = dem_sampler.sample_array(x_t, y_t)
        z_line = z_src_total + float(t) * (z_rec_total - z_src_total)
        diff = z_dem - z_line
        use = mask & valid & np.isfinite(diff) & (diff > max_diff)
        if np.any(use):
            max_diff[use] = diff[use]
            best_t[use] = float(t)

    threshold = max(1.0, min(3.0, 0.2 * float(dem_sampler.pixel_size_m or effective_resolution or 0.0)))
    screened = mask & np.isfinite(max_diff) & (max_diff > threshold)
    if np.any(screened):
        h_obs[screened] = max_diff[screened]
        d_total = np.maximum(np.asarray(dist_xy, dtype=np.float64), 1.0)
        d1[screened] = np.maximum(d_total[screened] * best_t[screened], 1.0)
        d2[screened] = np.maximum(d_total[screened] * (1.0 - best_t[screened]), 1.0)
        abar_1000 = _fresnel_diffraction_array(1000, h_obs, d1, d2)
        diag.update({
            "screening_available": True,
            "screened_cells": int(np.count_nonzero(screened)),
            "max_obstacle_m": float(np.max(h_obs[screened])),
            "max_abar_1000_db": float(np.max(abar_1000[screened])),
            "screening_threshold_m": float(threshold),
        })
    else:
        diag.update({"screening_available": True, "screened_cells": 0, "screening_threshold_m": float(threshold)})
    return h_obs, d1, d2, diag


def _ground_term_iso_scalar(freq_hz: int, height_m: float) -> float:
    """Same base term used by noise_engine_iso._calculate_a_ground_term."""
    h_eff = max(float(height_m), 1.0)
    freq = int(freq_hz)
    if freq <= 500:
        a_ground = 1.5
    elif freq == 1000:
        a_ground = 1.5 * (1.0 - math.exp(-h_eff / 10.0))
    elif freq == 2000:
        a_ground = 3.0 * (1.0 - math.exp(-h_eff / 10.0))
    elif freq == 4000:
        a_ground = 6.0 * (1.0 - math.exp(-h_eff / 10.0))
    else:
        a_ground = 12.0 * (1.0 - math.exp(-h_eff / 10.0))
    return max(0.0, float(a_ground))


def _calculate_agr_iso_regions_array(
    *,
    freq_hz: int,
    distance_xy_m: np.ndarray,
    hub_height_m: float,
    receiver_height_m: float,
    ground_g: float,
) -> np.ndarray:
    """Vectorized equivalent of calculate_agr_iso_regions().

    This keeps the same simplified ISO-aligned ground physics but avoids a
    Python call for every corrected raster cell.
    """
    d = np.maximum(np.asarray(distance_xy_m, dtype=np.float64), 1.0)
    hs = max(float(hub_height_m), 1.0)
    hr = max(float(receiver_height_m), 1.0)
    d_source = np.minimum(30.0 * hs, d / 3.0)
    d_receiver = np.minimum(30.0 * hr, d / 3.0)
    d_middle = np.maximum(d - d_source - d_receiver, 0.0)
    g = max(0.0, min(1.0, float(ground_g)))

    a_s = _ground_term_iso_scalar(freq_hz, hs)
    a_m = _ground_term_iso_scalar(freq_hz, (hs + hr) / 2.0)
    a_r = _ground_term_iso_scalar(freq_hz, hr)
    agr = (g * a_s) + np.where(d_middle > 0.0, g * a_m, 0.0) + (g * a_r)
    return np.clip(agr, 0.0, 10.0)


def _detect_mdt_obstacles_compat_vectorized(
    *,
    src: Dict[str, Any],
    cell_x: np.ndarray,
    cell_y: np.ndarray,
    z_rec_total: np.ndarray,
    dem_sampler: Optional[_GdalArraySampler],
    effective_resolution: float,
    cancel_callback: Optional[Callable[[], bool]] = None,
    chunk_target_samples: Optional[int] = None,
) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, Dict[str, Any]]:
    """Vectorized compatibility MDT obstacle detection for raster cells.

    The old synchronous raster path extracted a full source-cell terrain
    profile and then applied the dominant-obstacle/Fresnel logic.  This helper
    keeps that logic but batches cells with the same adaptive number of profile
    points, sampling the DEM array with NumPy instead of calling GDAL once per
    point/cell.

    Returns ``(screened_mask, h_obs, d1, d2, diag)`` for the flattened cells.
    """
    x = np.asarray(cell_x, dtype=np.float64).ravel()
    y = np.asarray(cell_y, dtype=np.float64).ravel()
    z_rec = np.asarray(z_rec_total, dtype=np.float64).ravel()
    n_cells = int(x.size)
    screened = np.zeros(n_cells, dtype=bool)
    h_obs = np.zeros(n_cells, dtype=np.float64)
    d1 = np.ones(n_cells, dtype=np.float64)
    d2 = np.ones(n_cells, dtype=np.float64)
    diag: Dict[str, Any] = {
        "screening_available": False,
        "screened_cells": 0,
        "max_obstacle_m": 0.0,
        "max_abar_1000_db": 0.0,
        "compat_profile_vectorized": False,
        "compat_profile_cells": n_cells,
        "compat_profile_target_samples": 0,
    }
    if n_cells <= 0:
        return screened, h_obs, d1, d2, diag
    if chunk_target_samples is None:
        try:
            chunk_target_samples = int(os.environ.get("VELANTIS_NOISE_MDT_CHUNK_SAMPLES", "2200000"))
        except Exception:
            chunk_target_samples = 2200000
        chunk_target_samples = max(350000, min(int(chunk_target_samples), 5000000))
    diag["compat_profile_target_samples"] = int(chunk_target_samples)

    if dem_sampler is None or not getattr(dem_sampler, "valid", False):
        if dem_sampler is not None and getattr(dem_sampler, "error", ""):
            diag["screening_error"] = dem_sampler.error
        return screened, h_obs, d1, d2, diag

    sx = float(src["x"])
    sy = float(src["y"])
    src_ground = src.get("z_ground")
    if src_ground is None:
        src_ground = dem_sampler.sample_scalar(sx, sy)
    z_src_total = (float(src_ground) if src_ground is not None else 0.0) + float(src.get("hub_height") or 0.0)

    dx = x - sx
    dy = y - sy
    d_total = np.hypot(dx, dy)
    valid_dist = d_total > 0.0
    d1[:] = np.maximum(d_total, 1.0)
    d2[:] = np.maximum(d_total, 1.0)
    if not np.any(valid_dist):
        diag.update({"screening_available": True, "compat_profile_vectorized": True})
        return screened, h_obs, d1, d2, diag

    pixel_size = float(dem_sampler.pixel_size_m or effective_resolution or 0.0)
    sample_step = max(pixel_size, 10.0)
    threshold = max(1.0, min(3.0, 0.2 * pixel_size))
    num_points = np.ceil(d_total / sample_step).astype(np.int32) + 1
    num_points = np.clip(num_points, 50, 250)

    n_groups = 0
    n_chunks = 0
    for n in np.unique(num_points[valid_dist]):
        if cancel_callback is not None and cancel_callback():
            raise RuntimeError("Tarea de raster cancelada.")
        group_idx = np.flatnonzero(valid_dist & (num_points == int(n)))
        if group_idx.size == 0:
            continue
        n_groups += 1
        t_all = np.linspace(0.0, 1.0, int(n), dtype=np.float64)
        # The compatibility obstacle detector ignores endpoints.
        t_inner = t_all[1:-1]
        if t_inner.size == 0:
            continue
        chunk_size = max(128, int(chunk_target_samples // max(1, int(t_inner.size))))
        for start in range(0, int(group_idx.size), chunk_size):
            if cancel_callback is not None and cancel_callback():
                raise RuntimeError("Tarea de raster cancelada.")
            idx = group_idx[start:start + chunk_size]
            n_chunks += 1
            xe = x[idx]
            ye = y[idx]
            zre = z_rec[idx]

            # Shape: (n_profile_points, n_cells_in_chunk).  Keep the compatibility
            # profile physics, but avoid allocating both z_line and diff as
            # separate large arrays.  z_dem is converted in-place into
            # (terrain - line_of_sight), which reduces memory traffic and is
            # noticeably faster on large 81-turbine rasters.
            t_col = t_inner[:, None]
            xt = sx + t_col * (xe[None, :] - sx)
            yt = sy + t_col * (ye[None, :] - sy)
            z_dem, _valid = dem_sampler.sample_array(xt, yt)
            # Compatibility behavior: invalid DEM samples are treated as 0.0.  The
            # vectorized sampler already returns 0.0 for invalid values, so the
            # validity mask is intentionally not applied here.
            z_dem -= (z_src_total + t_col * (zre[None, :] - z_src_total))
            best_pos = np.argmax(z_dem, axis=0)
            best_diff = z_dem[best_pos, np.arange(idx.size)]
            obs = np.isfinite(best_diff) & (best_diff > threshold)
            if not np.any(obs):
                continue
            idx_obs = idx[obs]
            t_best = t_inner[best_pos[obs]]
            d_tot_obs = d_total[idx_obs]
            screened[idx_obs] = True
            h_obs[idx_obs] = best_diff[obs]
            d1[idx_obs] = np.maximum(d_tot_obs * t_best, 1.0)
            d2[idx_obs] = np.maximum(d_tot_obs - d1[idx_obs], 1.0)

    if np.any(screened):
        abar_1000 = _fresnel_diffraction_array(1000, h_obs[screened], d1[screened], d2[screened])
        diag.update({
            "screening_available": True,
            "compat_profile_vectorized": True,
            "screened_cells": int(np.count_nonzero(screened)),
            "max_obstacle_m": float(np.max(h_obs[screened])),
            "max_abar_1000_db": float(np.max(abar_1000)) if abar_1000.size else 0.0,
            "screening_threshold_m": float(threshold),
            "compat_profile_groups": int(n_groups),
            "compat_profile_chunks": int(n_chunks),
        })
    else:
        diag.update({
            "screening_available": True,
            "compat_profile_vectorized": True,
            "screened_cells": 0,
            "screening_threshold_m": float(threshold),
            "compat_profile_groups": int(n_groups),
            "compat_profile_chunks": int(n_chunks),
        })
    return screened, h_obs, d1, d2, diag


def _presample_dem_grid(
    *,
    dem_path: str,
    sources: List[Dict[str, Any]],
    x_coords: np.ndarray,
    y_coords: np.ndarray,
    x0: float,
    y_top: float,
    width: int,
    height: int,
    effective_resolution: float,
    radius: float,
    progress_callback: Optional[Callable[[float], None]] = None,
    cancel_callback: Optional[Callable[[], bool]] = None,
) -> Tuple[np.ndarray, Dict[str, Any]]:
    """Build receptor ground elevations for a raster grid using GDAL only."""
    z_ground_grid = np.zeros((height, width), dtype=np.float32)
    diag: Dict[str, Any] = {"grid_dem_used": False, "grid_dem_samples_ok": 0, "grid_dem_samples_fail": 0}
    if not dem_path:
        return z_ground_grid, diag

    ds = gdal.Open(str(dem_path))
    if ds is None:
        diag["grid_dem_error"] = f"No se pudo abrir el MDT/DSM: {dem_path}"
        return z_ground_grid, diag
    gt = ds.GetGeoTransform()
    inv_gt = gdal.InvGeoTransform(gt)
    if inv_gt is None:
        diag["grid_dem_error"] = "No se pudo invertir la geotransformación del MDT/DSM."
        return z_ground_grid, diag

    valid_any = np.zeros((height, width), dtype=bool)
    radius_sq = float(radius) * float(radius)
    for src in sources:
        sx = float(src["x"])
        sy = float(src["y"])
        ix0 = max(0, int(math.floor((sx - radius - x0) / effective_resolution)))
        ix1 = min(width, int(math.ceil((sx + radius - x0) / effective_resolution)) + 1)
        iy0 = max(0, int(math.floor((y_top - (sy + radius)) / effective_resolution)))
        iy1 = min(height, int(math.ceil((y_top - (sy - radius)) / effective_resolution)) + 1)
        if ix0 >= ix1 or iy0 >= iy1:
            continue
        xs = x_coords[ix0:ix1][np.newaxis, :]
        ys = y_coords[iy0:iy1][:, np.newaxis]
        valid_any[iy0:iy1, ix0:ix1] |= ((xs - sx) ** 2 + (ys - sy) ** 2) <= radius_sq

    valid_idx = np.argwhere(valid_any)
    n_total = max(1, int(len(valid_idx)))
    n_ok = 0
    n_fail = 0

    # Vectorized DEM presampling.  This keeps the same nearest-neighbour / 0.0
    # fallback semantics as the old scalar loop, but avoids one GDAL call per
    # raster cell.
    sampler = _GdalArraySampler(str(dem_path or ""))
    if sampler.valid and len(valid_idx):
        chunk_size = 200000
        for start in range(0, len(valid_idx), chunk_size):
            if cancel_callback is not None and cancel_callback():
                raise RuntimeError("Tarea de raster cancelada.")
            chunk = valid_idx[start:start + chunk_size]
            iy = chunk[:, 0]
            ix = chunk[:, 1]
            vals, ok_mask = sampler.sample_array(x_coords[ix], y_coords[iy])
            if np.any(ok_mask):
                z_ground_grid[iy[ok_mask], ix[ok_mask]] = vals[ok_mask].astype(np.float32)
            n_ok += int(np.count_nonzero(ok_mask))
            n_fail += int(ok_mask.size - np.count_nonzero(ok_mask))
            if progress_callback is not None:
                try:
                    progress_callback(2.0 + 13.0 * float(min(start + chunk_size, len(valid_idx))) / float(n_total))
                except Exception:
                    pass
        diag["grid_dem_presample_vectorized"] = True
    else:
        if not sampler.valid and getattr(sampler, "error", ""):
            diag["grid_dem_presample_vectorized_error"] = sampler.error
        for k, (iy, ix) in enumerate(valid_idx):
            if cancel_callback is not None and cancel_callback():
                raise RuntimeError("Tarea de raster cancelada.")
            val, ok = _sample_gdal_raster_nearest(ds, inv_gt, float(x_coords[ix]), float(y_coords[iy]), 1)
            if ok:
                z_ground_grid[iy, ix] = float(val)
                n_ok += 1
            else:
                n_fail += 1
            if progress_callback is not None and (k % 750 == 0 or k + 1 == n_total):
                try:
                    progress_callback(2.0 + 13.0 * float(k + 1) / float(n_total))
                except Exception:
                    pass
        diag["grid_dem_presample_vectorized"] = False

    diag.update({
        "grid_dem_used": True,
        "grid_dem_path": str(dem_path),
        "grid_dem_samples_ok": int(n_ok),
        "grid_dem_samples_fail": int(n_fail),
    })
    return z_ground_grid, diag


def compute_noise_grid_file_from_snapshot(
    *,
    sources_snapshot: List[Dict[str, Any]],
    crs_wkt: str,
    layer_name: str,
    grid_resolution_m: float,
    max_radius_m: float,
    alpha_db_per_m: float,
    ground_factor_g: float,
    min_distance_m: float,
    receiver_height_m: float,
    calculation_engine: str = "fast",
    temperature_c: float = 15.0,
    humidity_percent: float = 70.0,
    pressure_kpa: float = 101.325,
    dem_path: str = "",
    max_cells: int = 150000,
    progress_callback: Optional[Callable[[float], None]] = None,
    cancel_callback: Optional[Callable[[], bool]] = None,
) -> Dict[str, Any]:
    """Compute a noise raster as GeoTIFF using only primitive inputs.

    This is the safe worker function for QgsTask. It supports vectorized
    fast/ISO paths without land-use. ISO + DEM/MDT uses the same compatibility
    source-cell terrain profile and Fresnel Abar logic as the old synchronous
    raster, but batches the DEM sampling with NumPy/GDAL so QGIS remains
    responsive.
    """
    sources = _snapshot_sources(sources_snapshot)
    if not sources:
        raise ValueError("No hay fuentes acústicas válidas para crear el raster.")

    def _progress(value: float) -> None:
        if progress_callback is not None:
            try:
                progress_callback(float(max(0.0, min(100.0, value))))
            except Exception:
                pass

    def _canceled() -> bool:
        if cancel_callback is None:
            return False
        try:
            return bool(cancel_callback())
        except Exception:
            return False

    requested_resolution = float(grid_resolution_m)
    effective_resolution = max(1.0, float(grid_resolution_m))
    xmin, ymin, xmax, ymax = _extent_from_sources(sources, max_radius_m, effective_resolution)
    width = max(1, int(math.ceil((xmax - xmin) / effective_resolution)))
    height = max(1, int(math.ceil((ymax - ymin) / effective_resolution)))
    n_cells = int(width * height)
    auto_adjusted = False
    if n_cells > int(max_cells):
        cell_area = max((xmax - xmin) * (ymax - ymin), 1.0)
        effective_resolution = max(effective_resolution, math.sqrt(cell_area / float(max_cells)))
        width = max(1, int(math.ceil((xmax - xmin) / effective_resolution)))
        height = max(1, int(math.ceil((ymax - ymin) / effective_resolution)))
        n_cells = int(width * height)
        auto_adjusted = True

    diag: Dict[str, Any] = {
        "grid_cells": n_cells,
        "grid_width": width,
        "grid_height": height,
        "requested_resolution_m": requested_resolution,
        "effective_resolution_m": effective_resolution,
        "auto_adjusted": bool(auto_adjusted),
        "async_task": True,
        "grid_engine": "async_iso_compat_mdt" if str(calculation_engine).lower() == "iso" else "async_fast_vectorized",
    }

    _progress(2.0)
    nodata_value = -9999.0
    arr = np.full((height, width), nodata_value, dtype=np.float32)
    x0 = xmin + 0.5 * effective_resolution
    y_top = ymax - 0.5 * effective_resolution
    x_coords = x0 + np.arange(width, dtype=np.float64) * effective_resolution
    y_coords = y_top - np.arange(height, dtype=np.float64) * effective_resolution

    radius = float(max_radius_m)
    radius_sq = radius * radius
    min_dist = float(min_distance_m)
    min_dist_sq = min_dist * min_dist
    g = max(0.0, min(1.0, float(ground_factor_g)))
    rec_h = float(receiver_height_m)
    engine_key = str(calculation_engine or "fast").strip().lower()
    e_sum_grid = np.zeros((height, width), dtype=np.float64)

    dem_array_sampler = _GdalArraySampler(str(dem_path or "")) if str(dem_path or "") else None
    # Exact compatibility Abar path for ISO+MDT.  This sampler extracts the same
    # source-cell terrain profile used by the old synchronous QGIS raster path,
    # but via GDAL so it is safe inside QgsTask.
    dem_profile_sampler = None
    if str(dem_path or ""):
        try:
            dem_profile_sampler = _GdalDemSampler(str(dem_path or ""))
            if dem_profile_sampler is not None and not dem_profile_sampler.valid:
                dem_profile_sampler = None
        except Exception:
            dem_profile_sampler = None

    z_ground_grid, dem_diag = _presample_dem_grid(
        dem_path=str(dem_path or ""),
        sources=sources,
        x_coords=x_coords,
        y_coords=y_coords,
        x0=x0,
        y_top=y_top,
        width=width,
        height=height,
        effective_resolution=effective_resolution,
        radius=radius,
        progress_callback=_progress,
        cancel_callback=_canceled,
    )
    diag.update(dem_diag)
    if dem_array_sampler is not None:
        diag["grid_dem_screening_cache_valid"] = bool(dem_array_sampler.valid)
        if not dem_array_sampler.valid and getattr(dem_array_sampler, "error", ""):
            diag["grid_dem_screening_error"] = dem_array_sampler.error
    diag["grid_dem_profile_sampler_valid"] = bool(dem_profile_sampler is not None and getattr(dem_profile_sampler, "valid", False))

    grid_screened_cells_total = 0
    grid_screening_sources = 0
    grid_max_obstacle_m = 0.0
    grid_max_abar_1000_db = 0.0

    alpha_by_freq: Dict[int, float] = {}
    if engine_key == "iso":
        alpha_by_freq = {
            int(freq): float(calculate_alpha_atm_iso(
                int(freq), float(temperature_c), float(humidity_percent), float(pressure_kpa)
            ))
            for freq in OCTAVE_BANDS
        }

    n_sources = max(1, len(sources))
    for i, src in enumerate(sources):
        if _canceled():
            raise RuntimeError("Tarea de raster cancelada.")

        sx = float(src["x"])
        sy = float(src["y"])
        ix0 = max(0, int(math.floor((sx - radius - x0) / effective_resolution)))
        ix1 = min(width, int(math.ceil((sx + radius - x0) / effective_resolution)) + 1)
        iy0 = max(0, int(math.floor((y_top - (sy + radius)) / effective_resolution)))
        iy1 = min(height, int(math.ceil((y_top - (sy - radius)) / effective_resolution)) + 1)
        if ix0 >= ix1 or iy0 >= iy1:
            _progress(5.0 + 90.0 * float(i + 1) / float(n_sources))
            continue

        xs = x_coords[ix0:ix1][np.newaxis, :]
        ys = y_coords[iy0:iy1][:, np.newaxis]
        dx = sx - xs
        dy = sy - ys
        dist_xy_sq = dx * dx + dy * dy
        mask = dist_xy_sq <= radius_sq
        if not np.any(mask):
            _progress(5.0 + 90.0 * float(i + 1) / float(n_sources))
            continue

        dist_xy_raw = np.sqrt(dist_xy_sq)
        dist_xy = np.maximum(dist_xy_raw, min_dist)
        z_src = (float(src.get("z_ground")) if src.get("z_ground") is not None else 0.0) + float(src.get("hub_height") or 0.0)
        z_rec = z_ground_grid[iy0:iy1, ix0:ix1].astype(np.float64) + rec_h
        dz = z_src - z_rec
        dist_3d_sq = np.maximum(min_dist_sq, dist_xy * dist_xy + dz * dz)
        dist_3d = np.sqrt(dist_3d_sq)

        if engine_key == "iso":
            adiv = 20.0 * np.log10(np.maximum(dist_3d, 1.0)) + 11.0
            lw_octave = src.get("lw_octave") or global_lwa_to_octave_spectrum(float(src.get("lwa") or 0.0))
            source_energy = np.zeros_like(dist_3d, dtype=np.float64)

            # Compatibility base path from the older implementation: vectorized ISO without Abar
            # first, with the same Agr call used there.  MDT is then applied as
            # a per-cell correction only where the compatibility profile detects a real
            # obstacle above the line of sight.
            for freq in OCTAVE_BANDS:
                freq = int(freq)
                lw = float(lw_octave.get(freq, 0.0))
                aatm = alpha_by_freq[freq] * dist_3d
                agr = _calculate_agr_iso_regions_array(
                    freq_hz=freq,
                    distance_xy_m=dist_xy,
                    hub_height_m=float(src.get("hub_height") or 0.0),
                    receiver_height_m=rec_h,
                    ground_g=g,
                )
                lp_a = lw - adiv - aatm - agr + float(A_WEIGHTING.get(freq, 0.0))
                source_energy += np.where(mask, np.power(10.0, lp_a / 10.0), 0.0)

            if dem_array_sampler is not None and getattr(dem_array_sampler, "valid", False):
                # Accelerated compatibility MDT correction.  This preserves the old
                # source-cell profile logic (adaptive number of samples,
                # dominant obstacle, same Fresnel Abar formula) but evaluates
                # profiles in NumPy batches instead of looping one cell at a
                # time with GDAL/QGIS calls.
                flat_valid = np.flatnonzero(mask.ravel())
                grid_screened_cells_total += 0  # keep key initialized even when no obstacles
                if flat_valid.size:
                    ly_all, lx_all = np.unravel_index(flat_valid, mask.shape)
                    cell_x = x_coords[ix0 + lx_all]
                    cell_y = y_coords[iy0 + ly_all]
                    z_rec_total_flat = z_rec[ly_all, lx_all]
                    screened_flat, h_obs_flat, d1_flat, d2_flat, obs_diag = _detect_mdt_obstacles_compat_vectorized(
                        src=src,
                        cell_x=cell_x,
                        cell_y=cell_y,
                        z_rec_total=z_rec_total_flat,
                        dem_sampler=dem_array_sampler,
                        effective_resolution=effective_resolution,
                        cancel_callback=_canceled,
                    )
                    if obs_diag.get("compat_profile_vectorized"):
                        diag["grid_mdt_compat_profile_vectorized"] = True
                        diag["grid_mdt_compat_profile_groups"] = int(obs_diag.get("compat_profile_groups", 0) or 0)
                        diag["grid_mdt_compat_profile_chunks"] = int(obs_diag.get("compat_profile_chunks", 0) or 0)
                    if np.any(screened_flat):
                        obs_pos = np.flatnonzero(screened_flat)
                        ly = ly_all[obs_pos]
                        lx = lx_all[obs_pos]
                        h_obs = h_obs_flat[obs_pos]
                        d1_obs = d1_flat[obs_pos]
                        d2_obs = d2_flat[obs_pos]

                        grid_screened_cells_total += int(obs_pos.size)
                        grid_screening_sources += int(obs_pos.size)
                        grid_max_obstacle_m = max(grid_max_obstacle_m, float(np.max(h_obs)) if h_obs.size else 0.0)

                        corrected_energy = np.zeros(obs_pos.size, dtype=np.float64)
                        adiv_cell = adiv[ly, lx].astype(np.float64)
                        d3d_cell = dist_3d[ly, lx].astype(np.float64)
                        dist_xy_cell = dist_xy[ly, lx].astype(np.float64)
                        for freq in OCTAVE_BANDS:
                            freq = int(freq)
                            lw = float(lw_octave.get(freq, 0.0))
                            aatm = alpha_by_freq[freq] * d3d_cell
                            agr = _calculate_agr_iso_regions_array(
                                freq_hz=freq,
                                distance_xy_m=dist_xy_cell,
                                hub_height_m=float(src.get("hub_height") or 0.0),
                                receiver_height_m=rec_h,
                                ground_g=g,
                            )
                            abar = _fresnel_diffraction_array(freq, h_obs, d1_obs, d2_obs)
                            if freq == 1000 and abar.size:
                                grid_max_abar_1000_db = max(grid_max_abar_1000_db, float(np.max(abar)))
                            lp_a = lw - adiv_cell - aatm - agr - abar + float(A_WEIGHTING.get(freq, 0.0))
                            corrected_energy += np.power(10.0, lp_a / 10.0)
                        source_energy[ly, lx] = corrected_energy
            elif dem_profile_sampler is not None and getattr(dem_profile_sampler, "valid", False):
                # Conservative fallback for very large DEMs that were not cached
                # in memory.  It keeps the exact old scalar path, slower but safe.
                local_valid = np.argwhere(mask)
                grid_screened_cells_total += 0  # keep key initialized even when no obstacles
                for ly, lx in local_valid:
                    if _canceled():
                        raise RuntimeError("Tarea de raster cancelada.")
                    try:
                        gx = float(x_coords[ix0 + lx])
                        gy = float(y_coords[iy0 + ly])
                        rec = {
                            "feature_id": -(int(iy0 + ly) * width + int(ix0 + lx) + 1),
                            "x": gx,
                            "y": gy,
                            "z_ground": float(z_ground_grid[iy0 + ly, ix0 + lx]),
                            "receiver_height": rec_h,
                            "eval_mode": "grid",
                        }
                        mdt_context = _prepare_mdt_context(src, rec, dem_profile_sampler)
                        if not mdt_context:
                            continue
                        obstacle = mdt_context.get("obstacle") or {}
                        if obstacle.get("los_clear", True):
                            continue

                        grid_screened_cells_total += 1
                        grid_screening_sources += 1
                        grid_max_obstacle_m = max(grid_max_obstacle_m, float(obstacle.get("obstacle_height_m") or 0.0))
                        corrected_energy = 0.0
                        adiv_cell = float(adiv[ly, lx])
                        d3d_cell = float(dist_3d[ly, lx])
                        max_abar_cell_1000 = 0.0
                        for freq in OCTAVE_BANDS:
                            freq = int(freq)
                            lw = float(lw_octave.get(freq, 0.0))
                            aatm = alpha_by_freq[freq] * d3d_cell
                            agr = float(calculate_agr_iso_regions(
                                freq_hz=freq,
                                distance_xy_m=float(dist_xy[ly, lx]),
                                hub_height_m=float(src.get("hub_height") or 0.0),
                                receiver_height_m=rec_h,
                                ground_g=g,
                            ))
                            abar = float(_calculate_abar_mdt(freq, mdt_context))
                            if freq == 1000:
                                max_abar_cell_1000 = max(max_abar_cell_1000, abar)
                            lp_a = lw - adiv_cell - aatm - agr - abar + float(A_WEIGHTING.get(freq, 0.0))
                            corrected_energy += 10.0 ** (lp_a / 10.0)
                        source_energy[ly, lx] = corrected_energy
                        grid_max_abar_1000_db = max(grid_max_abar_1000_db, float(max_abar_cell_1000))
                    except Exception:
                        # Compatibility fallback: keep the vectorized base
                        # value if the MDT profile/correction cannot be applied.
                        continue
            e_sum_grid[iy0:iy1, ix0:ix1] += source_energy
        else:
            adiv = 20.0 * np.log10(np.maximum(dist_3d, 1.0)) + 11.0
            aatm = float(alpha_db_per_m) * dist_3d
            base = 3.0 * np.log10(1.0 + np.maximum(dist_xy, 1.0) / 100.0)
            height_factor = 1.0 / (1.0 + ((float(src.get("hub_height") or 0.0) + rec_h) / 80.0))
            aground = np.clip(g * base * height_factor, 0.0, 6.0)
            lp = float(src.get("lwa") or 0.0) - adiv - aatm - aground
            e_sum_grid[iy0:iy1, ix0:ix1] += np.where(mask, np.power(10.0, lp / 10.0), 0.0)

        _progress(5.0 + 90.0 * float(i + 1) / float(n_sources))

    covered_mask = e_sum_grid > 0.0
    covered = int(np.count_nonzero(covered_mask))
    min_noise = float("inf")
    max_noise = float("-inf")
    if covered > 0:
        arr[covered_mask] = (10.0 * np.log10(e_sum_grid[covered_mask])).astype(np.float32)
        min_noise = float(np.min(arr[covered_mask]))
        max_noise = float(np.max(arr[covered_mask]))

    tmpdir = os.path.join(tempfile.gettempdir(), "velantis_noise")
    os.makedirs(tmpdir, exist_ok=True)
    out_path = _unique_temp_output(tmpdir, layer_name.replace(" · ", "_").replace(" ", "_"), ".tif")
    driver = gdal.GetDriverByName("GTiff")
    ds = driver.Create(out_path, width, height, 1, gdal.GDT_Float32, options=["COMPRESS=LZW"])
    if ds is None:
        raise RuntimeError("GDAL no pudo crear el GeoTIFF del raster de ruido.")
    gt = (xmin, effective_resolution, 0.0, ymax, 0.0, -effective_resolution)
    ds.SetGeoTransform(gt)
    try:
        srs = osr.SpatialReference()
        if crs_wkt:
            srs.ImportFromWkt(str(crs_wkt))
            ds.SetProjection(srs.ExportToWkt())
    except Exception:
        pass
    band = ds.GetRasterBand(1)
    band.WriteArray(arr)
    band.SetNoDataValue(float(nodata_value))
    band.FlushCache()
    ds.FlushCache()
    ds = None

    diag.update({
        "grid_covered_cells": int(covered),
        "grid_min_noise": float(min_noise if math.isfinite(min_noise) else 0.0),
        "grid_max_noise": float(max_noise if math.isfinite(max_noise) else 0.0),
        "grid_mdt_screening_used": bool(engine_key == "iso" and dem_profile_sampler is not None and getattr(dem_profile_sampler, "valid", False)),
        "grid_mdt_screening_sources": int(grid_screening_sources),
        "grid_mdt_screened_cell_hits": int(grid_screened_cells_total),
        "grid_mdt_max_obstacle_m": float(grid_max_obstacle_m),
        "grid_mdt_max_abar_1000_db": float(grid_max_abar_1000_db),
        "grid_path": out_path,
    })
    _progress(100.0)
    return diag


class NoiseGridTask(QgsTask):
    """QgsTask that computes the noise raster in the background."""

    def __init__(self, *, params: Dict[str, Any], on_finished: Optional[GridFinishedCallback] = None):
        super().__init__("Velantis Wind · Noise raster", QgsTask.CanCancel)
        self.params = dict(params)
        self.on_finished_callback = on_finished
        self.diag: Dict[str, Any] = {}
        self.error: Optional[str] = None
        self.grid_layer = None
        self.iso_layer = None

    def run(self) -> bool:  # QGIS worker thread
        try:
            self.diag = compute_noise_grid_file_from_snapshot(
                **self.params,
                progress_callback=self.setProgress,
                cancel_callback=self.isCanceled,
            )
            return True
        except Exception as exc:
            self.error = str(exc)
            return False

    def finished(self, success: bool) -> None:  # QGIS main thread
        ok = bool(success and not self.error and self.diag.get("grid_path"))
        if ok:
            try:
                prj = QgsProject.instance()
                layer_name = str(self.params.get("layer_name") or "Noise · Map")
                iso_layer_name = str(self.params.get("iso_layer_name") or "Noise · Isophones")
                _remove_existing_layers_by_name(prj, [layer_name] + ([iso_layer_name] if self.params.get("create_iso_layer") else []))
                raster_path = str(self.diag.get("grid_path") or "")
                lyr = QgsRasterLayer(raster_path, layer_name)
                if not lyr.isValid():
                    raise RuntimeError(f"No se pudo cargar el raster generado: {raster_path}")
                try:
                    lyr.setCustomProperty("velantis/noise_output", True)
                except Exception:
                    pass
                min_val = float(self.diag.get("grid_min_noise", 0.0))
                max_val = float(self.diag.get("grid_max_noise", 0.0))
                if math.isfinite(min_val) and math.isfinite(max_val) and max_val > min_val:
                    _apply_raster_heatmap_style(lyr, min_val, max_val)
                prj.addMapLayer(lyr)
                self.grid_layer = lyr
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

                if bool(self.params.get("create_iso_layer", False)):
                    levels = self.params.get("iso_levels") or [35.0, 40.0, 45.0, 50.0]
                    self.iso_layer = _build_isophones_layer_from_raster(prj, raster_path, levels, iso_layer_name)
            except Exception as exc:
                ok = False
                self.error = str(exc)

        if self.on_finished_callback is not None:
            try:
                self.on_finished_callback(ok, self.diag or {}, self.grid_layer, self.iso_layer, self.error)
            except Exception:
                pass


def start_noise_grid_task(
    params: Dict[str, Any],
    on_finished: Optional[GridFinishedCallback] = None,
    on_progress: Optional[GridProgressCallback] = None,
) -> NoiseGridTask:
    """Create, connect and register a noise-grid task in QGIS task manager."""
    task = NoiseGridTask(params=params, on_finished=on_finished)
    if on_progress is not None:
        try:
            task.progressChanged.connect(on_progress)
        except Exception:
            pass
    QgsApplication.taskManager().addTask(task)
    return task

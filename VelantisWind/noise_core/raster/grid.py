# -*- coding: utf-8 -*-
"""Raster/grid noise-map generation."""
from __future__ import annotations

import math
import os
import tempfile
from typing import Dict, List, Optional, Tuple

import numpy as np
from osgeo import gdal, osr
from qgis.core import (
    QgsGeometry,
    QgsPointXY,
    QgsProject,
    QgsRasterLayer,
    QgsRectangle,
    QgsSpatialIndex,
    QgsVectorLayer,
)

from ..noise_common import (
    NoiseSource,
    NoiseReceiver,
    OCTAVE_BANDS,
    A_WEIGHTING,
    global_lwa_to_octave_spectrum,
    log as _log,
)
from ..noise_engine_iso import (
    propagate_iso,
    calculate_alpha_atm_iso,
    calculate_agr_iso_regions,
    calculate_abar_iso_simple,
    _prepare_mdt_context,
)
from ..propagation.ground import _bbox_from_point, _lp_from_source
from ..qgis_io.common import _is_valid_dem_value, _remove_existing_layers_by_name, _sample_dem, _unique_temp_output
from ..qgis_io.layers import _apply_raster_heatmap_style


def _ground_term_iso_scalar(freq_hz: int, height_m: float) -> float:
    """Same simplified ground term used by noise_engine_iso._calculate_a_ground_term."""
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
    """Vectorized equivalent of calculate_agr_iso_regions() for raster cells."""
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

def _build_noise_grid_layer(
    prj: QgsProject,
    source_mem: QgsVectorLayer,
    sidx: QgsSpatialIndex,
    sources: List[NoiseSource],
    extent: QgsRectangle,
    grid_resolution_m: float,
    max_radius_m: float,
    alpha_db_per_m: float,
    ground_factor_g: float,
    landuse_layer: Optional[QgsVectorLayer],
    min_distance_m: float,
    receiver_height_m: float,
    dem_layer: Optional[QgsRasterLayer],
    layer_name: str,
    max_cells: int = 150000,
    # Acoustic engine selection
    calculation_engine: str = "fast",
    temperature_c: float = 15.0,
    humidity_percent: float = 70.0,
    pressure_kpa: float = 101.325
) -> Tuple[Optional[QgsRasterLayer], Dict[str, object]]:
    requested_resolution = float(grid_resolution_m)
    effective_resolution = max(1.0, float(grid_resolution_m))
    width = max(1, int(math.ceil(extent.width() / effective_resolution)))
    height = max(1, int(math.ceil(extent.height() / effective_resolution)))
    n_cells = int(width * height)
    auto_adjusted = False
    if n_cells > max_cells:
        cell_area = max(extent.width() * extent.height(), 1.0)
        effective_resolution = max(effective_resolution, math.sqrt(cell_area / float(max_cells)))
        width = max(1, int(math.ceil(extent.width() / effective_resolution)))
        height = max(1, int(math.ceil(extent.height() / effective_resolution)))
        n_cells = int(width * height)
        auto_adjusted = True
        _log(f"[Noise][GRID] Malla solicitada demasiado grande. Resolución pedida={requested_resolution:.1f} m -> resolución efectiva={effective_resolution:.1f} m | celdas={n_cells}/{max_cells}")
    else:
        _log(f"[Noise][GRID] Preparando raster: resolución={effective_resolution:.1f} m | celdas={n_cells}")
    diag = {
        'grid_cells': n_cells, 'grid_width': width, 'grid_height': height,
        'requested_resolution_m': requested_resolution, 'effective_resolution_m': effective_resolution,
        'auto_adjusted': bool(auto_adjusted),
    }

    _remove_existing_layers_by_name(prj, [layer_name])
    nodata_value = -9999.0
    arr = np.full((height, width), nodata_value, dtype=np.float32)
    x0 = extent.xMinimum() + 0.5 * effective_resolution
    y_top = extent.yMaximum() - 0.5 * effective_resolution
    min_noise = float('inf')
    max_noise = float('-inf')
    covered = 0

    # Fast raster path:
    # - Same acoustic formula as the previous grid path (_lp_from_source fast branch)
    # - Avoids creating a NoiseReceiver/QgsGeometry for every pixel
    # - Avoids QgsSpatialIndex + source_mem.getFeature() inside the pixel loop
    # - Uses NumPy over source bounding boxes. This is analogous to the shadow
    #   raster acceleration: precomputed axes + vectorized masks + one final write.
    engine_key = str(calculation_engine or "fast").strip().lower()

    use_vectorized_fast_grid = (
        engine_key != "iso"
        and landuse_layer is None
        and bool(sources)
    )

    # ISO raster acceleration:
    # - Fully vectorized when there is no land-use layer.
    # - With DEM/MDT active, the expensive topographic barrier (Abar) is still
    #   evaluated per source-cell pair to preserve the existing result, but only
    #   as a correction over the vectorized base Adiv/Aatm/Agr/octave sum.
    # - If landuse is active we keep the conservative route because G-effective
    #   currently depends on line/polygon intersections for every trajectory.
    use_vectorized_iso_grid = (
        engine_key == "iso"
        and landuse_layer is None
        and bool(sources)
    )

    if use_vectorized_fast_grid:
        import time
        t_grid = time.time()
        _log(
            f"[V2.4][GRID-FAST] Usando raster vectorizado "
            f"(motor rápido, sin landuse): {width}x{height}={n_cells} celdas, "
            f"{len(sources)} fuente(s)"
        )

        x_coords = (x0 + np.arange(width, dtype=np.float64) * effective_resolution)
        y_coords = (y_top - np.arange(height, dtype=np.float64) * effective_resolution)

        # Build a global coverage mask first. This lets us sample DEM only where
        # at least one turbine can contribute and keeps no-coverage cells at 0 dB,
        # exactly as in the previous implementation.
        valid_any = np.zeros((height, width), dtype=bool)
        radius = float(max_radius_m)
        radius_sq = radius * radius

        for src in sources:
            sx = float(src.x)
            sy = float(src.y)

            ix0 = max(0, int(math.floor((sx - radius - x0) / effective_resolution)))
            ix1 = min(width, int(math.ceil((sx + radius - x0) / effective_resolution)) + 1)

            iy0 = max(0, int(math.floor((y_top - (sy + radius)) / effective_resolution)))
            iy1 = min(height, int(math.ceil((y_top - (sy - radius)) / effective_resolution)) + 1)

            if ix0 >= ix1 or iy0 >= iy1:
                continue

            xs = x_coords[ix0:ix1][np.newaxis, :]
            ys = y_coords[iy0:iy1][:, np.newaxis]
            mask = ((xs - sx) ** 2 + (ys - sy) ** 2) <= radius_sq
            valid_any[iy0:iy1, ix0:ix1] |= mask

        # DEM pre-sampling. QGIS raster sampling is still necessarily point-wise,
        # but doing it once upfront is cheaper than embedding it in source loops.
        z_ground_grid = np.zeros((height, width), dtype=np.float32)
        if dem_layer is not None:
            t_dem = time.time()
            valid_idx = np.argwhere(valid_any)
            dem_provider = dem_layer.dataProvider()
            n_dem_ok = 0
            n_dem_fail = 0
            for iy, ix in valid_idx:
                try:
                    val, ok = dem_provider.sample(
                        QgsPointXY(float(x_coords[ix]), float(y_coords[iy])),
                        1
                    )
                    if ok and _is_valid_dem_value(val, dem_provider, 1):
                        fval = float(val)
                        z_ground_grid[iy, ix] = fval
                        n_dem_ok += 1
                    else:
                        n_dem_fail += 1
                except Exception:
                    n_dem_fail += 1
            _log(
                f"[V2.4][GRID-FAST] DEM presample: {n_dem_ok}/{len(valid_idx)} ok "
                f"({n_dem_fail} fallback a z=0) en {time.time() - t_dem:.2f}s"
            )

        e_sum_grid = np.zeros((height, width), dtype=np.float64)
        min_dist_sq = float(min_distance_m) ** 2
        g = max(0.0, min(1.0, float(ground_factor_g)))

        for src in sources:
            sx = float(src.x)
            sy = float(src.y)

            ix0 = max(0, int(math.floor((sx - radius - x0) / effective_resolution)))
            ix1 = min(width, int(math.ceil((sx + radius - x0) / effective_resolution)) + 1)

            iy0 = max(0, int(math.floor((y_top - (sy + radius)) / effective_resolution)))
            iy1 = min(height, int(math.ceil((y_top - (sy - radius)) / effective_resolution)) + 1)

            if ix0 >= ix1 or iy0 >= iy1:
                continue

            xs = x_coords[ix0:ix1][np.newaxis, :]
            ys = y_coords[iy0:iy1][:, np.newaxis]
            dx = sx - xs
            dy = sy - ys
            dist_xy_sq = dx * dx + dy * dy
            mask = dist_xy_sq <= radius_sq
            if not np.any(mask):
                continue

            dist_xy = np.sqrt(dist_xy_sq)
            dist_xy = np.where(dist_xy <= 0.0, float(min_distance_m), dist_xy)

            z_src = (float(src.z_ground) if src.z_ground is not None else 0.0) + float(src.hub_height)
            z_rec = z_ground_grid[iy0:iy1, ix0:ix1].astype(np.float64) + float(receiver_height_m)
            dz = z_src - z_rec

            dist_3d_sq = np.maximum(min_dist_sq, dist_xy * dist_xy + dz * dz)
            dist_3d = np.sqrt(dist_3d_sq)

            # Adiv ISO 9613-2: divergencia geométrica esférica (4π).
            # Coincide con la fórmula de noise_engine_fast.calculate_adiv usada
            # en receptores y con propagation/ground._lp_from_source corregido.
            # Antes (v0.1.0): 10*log10(2*pi*d^2), hemisferio 2π,
            # sobreestimaba ~3 dB e introducía inconsistencia raster/receptor.
            adiv = 10.0 * np.log10(np.maximum(dist_3d_sq, 1.0)) + 11.0
            aatm = float(alpha_db_per_m) * dist_3d

            base = 3.0 * np.log10(1.0 + np.maximum(dist_xy, 1.0) / 100.0)
            height_factor = 1.0 / (1.0 + ((float(src.hub_height) + float(receiver_height_m)) / 80.0))
            aground = np.clip(g * base * height_factor, 0.0, 6.0)

            lp = float(src.lwa) - adiv - aatm - aground
            contrib = np.zeros_like(lp, dtype=np.float64)
            contrib[mask] = np.power(10.0, lp[mask] / 10.0)
            e_sum_grid[iy0:iy1, ix0:ix1] += contrib

        covered_mask = e_sum_grid > 0.0
        covered = int(np.count_nonzero(covered_mask))
        if covered > 0:
            arr[covered_mask] = (10.0 * np.log10(e_sum_grid[covered_mask])).astype(np.float32)
            min_noise = float(np.min(arr[covered_mask]))
            max_noise = float(np.max(arr[covered_mask]))

        _log(
            f"[V2.4][GRID-FAST] Raster vectorizado calculado en "
            f"{time.time() - t_grid:.2f}s | cobertura={covered}/{n_cells}"
        )

    elif use_vectorized_iso_grid:
        import time
        t_grid = time.time()
        _log(
            f"[V2.5][GRID-ISO-FAST] Usando raster ISO vectorizado "
            f"(sin landuse): {width}x{height}={n_cells} celdas, "
            f"{len(sources)} fuente(s), DEM={'sí' if dem_layer is not None else 'no'}"
        )

        x_coords = (x0 + np.arange(width, dtype=np.float64) * effective_resolution)
        y_coords = (y_top - np.arange(height, dtype=np.float64) * effective_resolution)

        valid_any = np.zeros((height, width), dtype=bool)
        radius = float(max_radius_m)
        radius_sq = radius * radius

        for src in sources:
            sx = float(src.x)
            sy = float(src.y)

            ix0 = max(0, int(math.floor((sx - radius - x0) / effective_resolution)))
            ix1 = min(width, int(math.ceil((sx + radius - x0) / effective_resolution)) + 1)

            iy0 = max(0, int(math.floor((y_top - (sy + radius)) / effective_resolution)))
            iy1 = min(height, int(math.ceil((y_top - (sy - radius)) / effective_resolution)) + 1)

            if ix0 >= ix1 or iy0 >= iy1:
                continue

            xs = x_coords[ix0:ix1][np.newaxis, :]
            ys = y_coords[iy0:iy1][:, np.newaxis]
            mask = ((xs - sx) ** 2 + (ys - sy) ** 2) <= radius_sq
            valid_any[iy0:iy1, ix0:ix1] |= mask

        # Igual que en el raster rápido: samplear el DEM del receptor una sola vez.
        # Si falla el sampleo se mantiene z_ground=0, que coincide con el fallback
        # anterior de propagate_iso: (rec.z_ground or 0.0) + receiver_height.
        z_ground_grid = np.zeros((height, width), dtype=np.float32)
        if dem_layer is not None:
            t_dem = time.time()
            valid_idx = np.argwhere(valid_any)
            dem_provider = dem_layer.dataProvider()
            n_dem_ok = 0
            n_dem_fail = 0
            for iy, ix in valid_idx:
                try:
                    val, ok = dem_provider.sample(
                        QgsPointXY(float(x_coords[ix]), float(y_coords[iy])),
                        1
                    )
                    if ok and _is_valid_dem_value(val, dem_provider, 1):
                        fval = float(val)
                        z_ground_grid[iy, ix] = fval
                        n_dem_ok += 1
                    else:
                        n_dem_fail += 1
                except Exception:
                    n_dem_fail += 1
            _log(
                f"[V2.5][GRID-ISO-FAST] DEM receptor presample: "
                f"{n_dem_ok}/{len(valid_idx)} ok ({n_dem_fail} fallback a z=0) "
                f"en {time.time() - t_dem:.2f}s"
            )

        # Coeficientes atmosféricos por banda: constantes para todo el raster.
        alpha_by_freq = {
            int(freq): float(calculate_alpha_atm_iso(
                int(freq),
                float(temperature_c),
                float(humidity_percent),
                float(pressure_kpa),
            ))
            for freq in OCTAVE_BANDS
        }

        e_sum_grid = np.zeros((height, width), dtype=np.float64)
        min_dist = float(min_distance_m)
        min_dist_sq = min_dist * min_dist
        g = max(0.0, min(1.0, float(ground_factor_g)))
        rec_h = float(receiver_height_m)
        n_pairs = 0
        n_mdt_pairs = 0
        n_mdt_obstructed = 0

        for src in sources:
            sx = float(src.x)
            sy = float(src.y)

            ix0 = max(0, int(math.floor((sx - radius - x0) / effective_resolution)))
            ix1 = min(width, int(math.ceil((sx + radius - x0) / effective_resolution)) + 1)

            iy0 = max(0, int(math.floor((y_top - (sy + radius)) / effective_resolution)))
            iy1 = min(height, int(math.ceil((y_top - (sy - radius)) / effective_resolution)) + 1)

            if ix0 >= ix1 or iy0 >= iy1:
                continue

            xs = x_coords[ix0:ix1][np.newaxis, :]
            ys = y_coords[iy0:iy1][:, np.newaxis]
            dx = sx - xs
            dy = sy - ys
            dist_xy_raw_sq = dx * dx + dy * dy
            dist_xy_raw = np.sqrt(dist_xy_raw_sq)
            dist_xy = np.maximum(dist_xy_raw, min_dist)
            mask = (dist_xy_raw_sq <= radius_sq) & (dist_xy <= radius)
            if not np.any(mask):
                continue

            z_src = (float(src.z_ground) if src.z_ground is not None else 0.0) + float(src.hub_height)
            z_rec = z_ground_grid[iy0:iy1, ix0:ix1].astype(np.float64) + rec_h
            dz = z_src - z_rec
            dist_3d_sq = np.maximum(min_dist_sq, dist_xy * dist_xy + dz * dz)
            dist_3d = np.sqrt(dist_3d_sq)

            adiv = 20.0 * np.log10(np.maximum(dist_3d, 1.0)) + 11.0
            lw_octave = src.lw_octave if src.lw_octave is not None else global_lwa_to_octave_spectrum(float(src.lwa))

            source_energy = np.zeros_like(dist_3d, dtype=np.float64)
            for freq in OCTAVE_BANDS:
                freq = int(freq)
                lw = float(lw_octave.get(freq, 0.0))
                aatm = alpha_by_freq[freq] * dist_3d
                agr = _calculate_agr_iso_regions_array(
                    freq_hz=freq,
                    distance_xy_m=dist_xy,
                    hub_height_m=float(src.hub_height),
                    receiver_height_m=rec_h,
                    ground_g=g,
                )
                lp_a = lw - adiv - aatm - agr + float(A_WEIGHTING.get(freq, 0.0))
                source_energy += np.where(mask, np.power(10.0, lp_a / 10.0), 0.0)

            # Corrección topográfica ISO por MDT. Se mantiene la lógica existente
            # de obstáculo dominante, pero se aplica solo como corrección donde
            # realmente hay obstáculo; si la línea de visión queda libre, el
            # resultado vectorizado sin Abar ya es idéntico al anterior.
            if dem_layer is not None:
                local_valid = np.argwhere(mask)
                n_pairs += int(len(local_valid))
                for ly, lx in local_valid:
                    try:
                        gx = float(x_coords[ix0 + lx])
                        gy = float(y_coords[iy0 + ly])
                        rec = NoiseReceiver(
                            feature_id=-(int(iy0 + ly) * width + int(ix0 + lx) + 1),
                            x=gx,
                            y=gy,
                            z_ground=float(z_ground_grid[iy0 + ly, ix0 + lx]),
                            receiver_height=rec_h,
                            eval_mode='grid',
                            geometry=None,
                            attrs=[],
                        )
                        mdt_context = _prepare_mdt_context(src, rec, dem_layer)
                        n_mdt_pairs += 1
                        if not mdt_context:
                            continue
                        obstacle = mdt_context.get('obstacle') or {}
                        if obstacle.get('los_clear', True):
                            continue

                        n_mdt_obstructed += 1
                        corrected_energy = 0.0
                        adiv_cell = float(adiv[ly, lx])
                        d3d_cell = float(dist_3d[ly, lx])
                        for freq in OCTAVE_BANDS:
                            freq = int(freq)
                            lw = float(lw_octave.get(freq, 0.0))
                            aatm = alpha_by_freq[freq] * d3d_cell
                            agr = float(calculate_agr_iso_regions(
                                freq_hz=freq,
                                distance_xy_m=float(dist_xy[ly, lx]),
                                hub_height_m=float(src.hub_height),
                                receiver_height_m=rec_h,
                                ground_g=g,
                            ))
                            abar = float(calculate_abar_iso_simple(
                                freq,
                                src,
                                rec,
                                dem_layer,
                                mdt_context=mdt_context,
                            ))
                            lp_a = lw - adiv_cell - aatm - agr - abar + float(A_WEIGHTING.get(freq, 0.0))
                            corrected_energy += 10.0 ** (lp_a / 10.0)
                        source_energy[ly, lx] = corrected_energy
                    except Exception:
                        # Fallback seguro: conservar valor vectorizado sin Abar.
                        continue
            else:
                n_pairs += int(np.count_nonzero(mask))

            e_sum_grid[iy0:iy1, ix0:ix1] += source_energy

        covered_mask = e_sum_grid > 0.0
        covered = int(np.count_nonzero(covered_mask))
        if covered > 0:
            arr[covered_mask] = (10.0 * np.log10(e_sum_grid[covered_mask])).astype(np.float32)
            min_noise = float(np.min(arr[covered_mask]))
            max_noise = float(np.max(arr[covered_mask]))

        diag.update({
            'grid_engine': 'iso_vectorized_v2_5',
            'grid_iso_pairs': int(n_pairs),
            'grid_iso_mdt_pairs': int(n_mdt_pairs),
            'grid_iso_mdt_obstructed_pairs': int(n_mdt_obstructed),
        })
        _log(
            f"[V2.5][GRID-ISO-FAST] Raster ISO calculado en "
            f"{time.time() - t_grid:.2f}s | cobertura={covered}/{n_cells} | "
            f"pares={n_pairs} | MDT obst={n_mdt_obstructed}/{n_mdt_pairs}"
        )

    else:
        if str(calculation_engine or "fast").lower() == "iso":
            _log("[V2.5][GRID] Motor ISO con landuse: ruta conservadora píxel-fuente para preservar G por trayectoria.")
        elif landuse_layer is not None:
            _log("[V2.4][GRID] Landuse activo: usando ruta conservadora para preservar G por trayectoria.")

        for iy in range(height):
            y = y_top - iy * effective_resolution
            for ix in range(width):
                x = x0 + ix * effective_resolution
                rec = NoiseReceiver(feature_id=-(iy * width + ix + 1), x=x, y=y, z_ground=_sample_dem(dem_layer, x, y), receiver_height=float(receiver_height_m), eval_mode='grid', geometry=QgsGeometry.fromPointXY(QgsPointXY(x, y)), attrs=[])
                bbox = _bbox_from_point(x, y, float(max_radius_m))
                cand_ids = sidx.intersects(bbox)
                e_sum = 0.0
                n_src = 0
                for sid in cand_ids:
                    f = source_mem.getFeature(int(sid))
                    try:
                        src_idx = int(f['src_idx'])
                        src = sources[src_idx]
                    except Exception:
                        continue

                    # Branch according to the selected acoustic engine
                    if calculation_engine == "iso":
                        # Usar motor ISO
                        lpa_result, desglose_iso, _ = propagate_iso(
                            src=src, rec=rec,
                            temperature_c=temperature_c,
                            humidity_percent=humidity_percent,
                            pressure_kpa=pressure_kpa,
                            ground_g=float(ground_factor_g),
                            min_distance_m=float(min_distance_m),
                            dem_layer=dem_layer,
                            landuse_layer=landuse_layer
                        )
                        lp = lpa_result
                        dist_xy = desglose_iso['dist_xy']
                    else:
                        # Usar motor rápido
                        calc = _lp_from_source(
                            src, rec,
                            alpha_db_per_m=float(alpha_db_per_m),
                            ground_factor_g=float(ground_factor_g),
                            min_distance_m=float(min_distance_m),
                            landuse_layer=landuse_layer
                        )
                        if calc is None:
                            continue
                        lp, dist_xy, _, _, _, _, _ = calc

                    if dist_xy > float(max_radius_m):
                        continue
                    e_sum += 10.0 ** (lp / 10.0)
                    n_src += 1
                noise_dba = 10.0 * math.log10(e_sum) if n_src > 0 and e_sum > 0.0 else 0.0
                if n_src > 0:
                    arr[iy, ix] = float(noise_dba)
                    covered += 1
                    if noise_dba < min_noise:
                        min_noise = float(noise_dba)
                    if noise_dba > max_noise:
                        max_noise = float(noise_dba)

    _remove_existing_layers_by_name(prj, [layer_name])
    tmpdir = os.path.join(tempfile.gettempdir(), 'velantis_noise')
    os.makedirs(tmpdir, exist_ok=True)
    out_path = _unique_temp_output(tmpdir, layer_name.replace(' · ', '_').replace(' ', '_'), '.tif')
    driver = gdal.GetDriverByName('GTiff')
    ds = driver.Create(out_path, width, height, 1, gdal.GDT_Float32, options=['COMPRESS=LZW'])
    gt = (extent.xMinimum(), effective_resolution, 0.0, extent.yMaximum(), 0.0, -effective_resolution)
    ds.SetGeoTransform(gt)
    srs = osr.SpatialReference()
    try:
        srs.ImportFromWkt(prj.crs().toWkt())
        ds.SetProjection(srs.ExportToWkt())
    except Exception:
        pass
    band = ds.GetRasterBand(1)
    band.WriteArray(arr)
    band.SetNoDataValue(float(nodata_value))
    band.FlushCache()
    ds.FlushCache()
    ds = None

    lyr = QgsRasterLayer(out_path, layer_name)
    if not lyr.isValid():
        _log(f"[Noise][GRID][WARN] No se pudo crear el raster de mapa acústico: {out_path}")
        return None, diag
    try:
        lyr.setCustomProperty('velantis/noise_output', True)
    except Exception:
        pass
    if covered > 0 and math.isfinite(min_noise) and math.isfinite(max_noise):
        _apply_raster_heatmap_style(lyr, float(min_noise), float(max_noise))
    prj.addMapLayer(lyr)
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
    diag.update({'grid_covered_cells': int(covered), 'grid_min_noise': float(min_noise if math.isfinite(min_noise) else 0.0), 'grid_max_noise': float(max_noise if math.isfinite(max_noise) else 0.0), 'grid_path': out_path})
    _log(f"[Noise][GRID] Raster de mapa creado: {layer_name} | celdas={n_cells} | resolución efectiva={effective_resolution:.1f} m | cobertura={covered}/{n_cells}")
    return lyr, diag


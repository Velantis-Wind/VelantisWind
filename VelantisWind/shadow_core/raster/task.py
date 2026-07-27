# -*- coding: utf-8 -*-
"""Background QgsTask for shadow flicker raster generation.

This module keeps the heavy raster task outside shadow_page.py.
"""
from __future__ import annotations

from types import SimpleNamespace

from ..debug import debug_print
from ..i18n_local import tr4 as _ml

from qgis.core import QgsTask

from ...raster_io import read_float64_pixel, write_float32_band


class ShadowRasterTask(QgsTask):
    """Task to calculate the shadow flicker raster in the background with threading."""

    def __init__(self, description, turbines, calculator_snapshot, turbine_crs_wkt, resolution,
                 raster_timestep=5, dem_path=""):
        super().__init__(description, QgsTask.CanCancel)
        self.turbines = [dict(turbine) for turbine in (turbines or [])]
        self.calculator = SimpleNamespace(**dict(calculator_snapshot or {}))
        self.turbine_crs_wkt = str(turbine_crs_wkt or "")
        self.resolution = resolution
        self.raster_timestep = raster_timestep  # min/timestep para raster
        self.dem_path = str(dem_path or "")
        self.raster_path = None
        self.npz_path = None  # Path del archivo NPZ with matriz 12x24
        self.points_calculated = 0
        self.elapsed_time = 0
        self.exception = None

    def run(self):
        """Run the calculation in the background."""
        import time
        import numpy as np
        from datetime import datetime, timedelta
        from threading import Thread, Lock
        import math
        import os

        start_time = time.time()

        try:
            debug_print("[Shadow Raster Task] Starting calculation...")

            # 1. Setup
            max_distance = float(getattr(self.calculator, "max_shadow_distance_m", 2000.0))
            x_coords = [t['x'] for t in self.turbines]
            y_coords = [t['y'] for t in self.turbines]

            xmin = min(x_coords) - max_distance
            xmax = max(x_coords) + max_distance
            ymin = min(y_coords) - max_distance
            ymax = max(y_coords) + max_distance

            debug_print(f"[Shadow Raster Task] Area: ({xmin:.0f}, {ymin:.0f}) - ({xmax:.0f}, {ymax:.0f})")

            # 2. Grilla
            x_range = np.arange(xmin, xmax, self.resolution)
            y_range = np.arange(ymin, ymax, self.resolution)

            debug_print(f"[Shadow Raster Task] Grilla: {len(x_range)}x{len(y_range)} = {len(x_range)*len(y_range)} points")

            # 3. Máscara de distancia (vectorizado)
            XX, YY = np.meshgrid(x_range, y_range)
            mask = np.zeros_like(XX, dtype=bool)
            for turb in self.turbines:
                dist_sq = (XX - turb['x'])**2 + (YY - turb['y'])**2
                mask |= (dist_sq <= max_distance**2)

            valid_indices = np.argwhere(mask)
            self.points_calculated = len(valid_indices)

            debug_print(f"[Shadow Raster Task] Valid points: {len(valid_indices)}")

            if len(valid_indices) == 0:
                self.exception = "No valid points to calculate"
                debug_print("[Shadow Raster Task] ERROR: no valid points")
                return False

            # 3b. DEM pre-sampling for the whole grid (terrain-aware mode).
            # QgsRasterLayer/QgsRasterDataProvider objects belong to QGIS' main
            # thread, so the task receives only a GDAL-readable path and CRS WKT.
            # ReadRaster is used instead of ReadAsArray to avoid the optional
            # gdal_array NumPy bridge on installations with a NumPy/GDAL ABI
            # mismatch.
            pixel_ground_elevs = np.zeros((len(y_range), len(x_range)), dtype=np.float32)
            if self.dem_path:
                debug_print(f"[Shadow Raster Task] Pre-sampling DEM with GDAL: {self.dem_path}")
                t_dem = time.time()
                n_off = 0
                dem_ds = None
                try:
                    from osgeo import gdal, osr

                    dem_ds = gdal.Open(self.dem_path, gdal.GA_ReadOnly)
                    if dem_ds is None:
                        raise RuntimeError(f"GDAL could not open DEM: {self.dem_path}")
                    dem_band = dem_ds.GetRasterBand(1)
                    if dem_band is None:
                        raise RuntimeError("The selected DEM has no band 1.")

                    geotransform = dem_ds.GetGeoTransform()
                    inv_gt = gdal.InvGeoTransform(geotransform)
                    if (
                        isinstance(inv_gt, tuple)
                        and len(inv_gt) == 2
                        and isinstance(inv_gt[0], (bool, int))
                        and isinstance(inv_gt[1], tuple)
                    ):
                        inv_gt = inv_gt[1] if inv_gt[0] else None
                    if inv_gt is None:
                        raise RuntimeError("Could not invert the DEM geotransform.")

                    coord_transform = None
                    dem_wkt = str(dem_ds.GetProjection() or "")
                    if self.turbine_crs_wkt and dem_wkt:
                        source_srs = osr.SpatialReference()
                        target_srs = osr.SpatialReference()
                        source_srs.ImportFromWkt(self.turbine_crs_wkt)
                        target_srs.ImportFromWkt(dem_wkt)
                        if hasattr(source_srs, "SetAxisMappingStrategy"):
                            source_srs.SetAxisMappingStrategy(osr.OAMS_TRADITIONAL_GIS_ORDER)
                            target_srs.SetAxisMappingStrategy(osr.OAMS_TRADITIONAL_GIS_ORDER)
                        if not source_srs.IsSame(target_srs):
                            coord_transform = osr.CoordinateTransformation(source_srs, target_srs)

                    nodata = dem_band.GetNoDataValue()
                    dem_width = int(dem_ds.RasterXSize)
                    dem_height = int(dem_ds.RasterYSize)

                    for j, i in valid_indices:
                        sample_x = float(x_range[i])
                        sample_y = float(y_range[j])
                        try:
                            if coord_transform is not None:
                                sample_x, sample_y, _ = coord_transform.TransformPoint(sample_x, sample_y)
                            px_f, py_f = gdal.ApplyGeoTransform(inv_gt, sample_x, sample_y)
                            px = int(math.floor(px_f))
                            py = int(math.floor(py_f))
                            if px < 0 or py < 0 or px >= dem_width or py >= dem_height:
                                n_off += 1
                                continue
                            fval = read_float64_pixel(
                                dem_band,
                                px,
                                py,
                                gdal_module=gdal,
                            )
                            if not math.isfinite(fval):
                                n_off += 1
                                continue
                            if nodata is not None and math.isclose(
                                fval,
                                float(nodata),
                                rel_tol=0.0,
                                abs_tol=max(1e-9, abs(float(nodata)) * 1e-12),
                            ):
                                n_off += 1
                                continue
                            pixel_ground_elevs[j, i] = fval
                        except Exception:
                            n_off += 1

                    elapsed_dem = time.time() - t_dem
                    masked = pixel_ground_elevs[mask]
                    if masked.size > 0:
                        debug_print(
                            f"[Shadow Raster Task] DEM pre-sampling done in {elapsed_dem:.2f}s "
                            f"({len(valid_indices):,} pixels, min={masked.min():.1f}m "
                            f"max={masked.max():.1f}m, no-data={n_off})"
                        )
                except Exception as exc:
                    pixel_ground_elevs.fill(0.0)
                    debug_print(f"[Shadow Raster Task] WARN DEM unavailable in worker; flat fallback: {exc}")
                finally:
                    dem_ds = None
            else:
                debug_print("[Shadow Raster Task] No DEM - flat terrain assumed for grid (z=0)")

            # ----- Raster geometry verification: first valid pixel × first turbine -----
            try:
                jv, iv = valid_indices[0]
                px_x = float(x_range[iv])
                px_y = float(y_range[jv])
                px_z = float(pixel_ground_elevs[jv, iv]) + 2.0
                t_first = self.turbines[0]
                t_ground = float(t_first.get('ground_elev', 0.0))
                t_abs = float(t_first['hub_height']) + t_ground
                horiz = ((t_first['x'] - px_x) ** 2 + (t_first['y'] - px_y) ** 2) ** 0.5
                dz_flat = float(t_first['hub_height']) - 2.0
                dz_dem = t_abs - px_z
                debug_print(f"[Shadow Raster Task] Geometry check: first valid pixel "
                      f"({px_x:.0f}, {px_y:.0f})  vs  first turbine '{t_first.get('name','T0')}'")
                debug_print(f"  pixel:    abs_z={px_z:.1f}m   "
                      f"(ground={pixel_ground_elevs[jv, iv]:.1f}m + observer=2.0m)")
                debug_print(f"  turbine:  abs_hub_z={t_abs:.1f}m   "
                      f"(hub={t_first['hub_height']:.1f}m + ground={t_ground:+.1f}m)")
                debug_print(f"  Δz: flat={dz_flat:+.1f}m   DEM={dz_dem:+.1f}m   "
                      f"shift={dz_dem-dz_flat:+.1f}m   horiz_dist={horiz:.1f}m")
            except Exception as _e:
                debug_print(f"[Shadow Raster Task] (geometry check skipped: {_e})")

            # 4. Pre-calcular posiciones solares (VECTORIZADO - 50x más rápido)
            debug_print("[Shadow Raster Task] Precomputing solar positions (vectorized)...")

            try:
                from ..solar_geometry import get_sun_positions_vectorized
                debug_print("[Shadow Raster Task] ✅ Import get_sun_positions_vectorized OK")
            except ImportError as e:
                self.exception = _ml(
                    f"Error al importar las funciones vectorizadas: {e}",
                    f"Error importing vectorized functions: {e}",
                    f"Erreur lors de l’import des fonctions vectorisées : {e}",
                    f"Fehler beim Import der vektorisierten Funktionen: {e}",
                )
                debug_print(f"[Shadow Raster Task] ❌ ImportError: {e}")
                return False

            t0 = time.time()
            timestamps_all, azimuths_all, altitudes_all, is_up_all, months_all, hours_all = get_sun_positions_vectorized(
                self.calculator.year,
                self.calculator.latitude,
                self.calculator.longitude,
                self.calculator.timezone_offset,
                self.raster_timestep,  # timestep específico del raster
                timezone_mode=self.calculator.timezone_mode,
                timezone_name=self.calculator.timezone_name,
            )

            # Filtrar solo timesteps válidos (sol up + en rango de elevación)
            valid_mask = (is_up_all & 
                         (altitudes_all >= self.calculator.min_sun_elevation) & 
                         (altitudes_all <= self.calculator.max_sun_elevation))

            sun_az_array = azimuths_all[valid_mask]
            sun_alt_array = altitudes_all[valid_mask]

            # Month and hour for each valid timestep (vectorized, no iteration)
            sun_month_array = (months_all[valid_mask] - 1).astype(np.int8)  # 0-11
            sun_hour_array = hours_all[valid_mask].astype(np.int8)  # 0-23

            elapsed_solar = time.time() - t0
            debug_print(f"[Shadow Raster Task] ✅ Solar positions: {len(sun_az_array):,} valid timesteps in {elapsed_solar:.2f}s (timestep={self.raster_timestep}min)")

            if len(sun_az_array) == 0:
                self.exception = "No valid solar positions were found"
                debug_print("[Shadow Raster Task] ❌ ERROR: No valid timesteps")
                return False

            # 5. Calculate shadow with THREADING (more stable than multiprocessing)
            raster_array = np.zeros((len(y_range), len(x_range)), dtype=np.float32)
            raster_array[:] = -9999

            # Matriz 12x24 por píxel para filtrado posterior por mes/hora
            # Shape: (height, width, 12, 24) - stores shadow minutes by month-hour
            # Only guardamos para píxeles válidos (resto = 0)
            raster_12x24 = np.zeros((len(y_range), len(x_range), 12, 24), dtype=np.int32)

            # Dividir trabajo en chunks - usar más threads (NumPy libera GIL)
            n_threads = min(8, os.cpu_count() or 1)  # Hasta 8 threads
            chunk_size = max(1, len(valid_indices) // n_threads)

            lock = Lock()
            progress_counter = [0]  # mutable para compartir entre threads

            def process_chunk(chunk_indices, thread_id):
                """Procesa un chunk de points VECTORIZADO (angular method)."""
                # Importar funciones necesarias UNA VEZ al inicio del thread
                try:
                    from ..solar_geometry import calculate_flicker_angles
                    if thread_id == 0:
                        debug_print("[Shadow Raster Task] ✅ Thread 0: Imports OK")
                except ImportError as e:
                    debug_print(f"[Shadow Raster Task] ❌ Thread {thread_id}: ImportError: {e}")
                    return

                # Pre-extraer arrays de turbines para vectorización
                turb_xs = np.array([t['x'] for t in self.turbines])
                turb_ys = np.array([t['y'] for t in self.turbines])
                turb_hubs = np.array([t['hub_height'] for t in self.turbines])
                turb_rotors = np.array([t['rotor_diameter'] for t in self.turbines])
                # Cota absoluta del hub = hub_height + ground_elev (terrain-aware).
                # Si no se proporcionó DEM, ground_elev=0 → comportamiento previo.
                turb_ground = np.array([float(t.get('ground_elev', 0.0)) for t in self.turbines])
                turb_hub_abs = turb_hubs + turb_ground

                step_min = self.raster_timestep  # Timestep específico del raster
                resolution = self.resolution

                # Pre-shape de arrays solares para broadcasting eficiente
                sun_az_2d = sun_az_array[:, np.newaxis]
                sun_alt_2d = sun_alt_array[:, np.newaxis]

                debug_count = 0

                for idx in chunk_indices:
                    if self.isCanceled():
                        return

                    j, i = idx
                    x = x_range[i]
                    y = y_range[j]
                    pixel_z = float(pixel_ground_elevs[j, i]) + 2.0  # ground + 2m observer

                    # ========== ÁNGULOS PRE-CALCULADOS (vectorizado por turbines) ==========
                    x_dist = turb_xs - x
                    y_dist = turb_ys - y
                    # elev_diff = (hub_top_abs) - (pixel_top_abs)
                    # terrain-aware equivalent: hubHeight + thisTurb.elev - zoneElev (- observer)
                    elev_diff = turb_hub_abs - pixel_z

                    distance_to_base = np.sqrt(x_dist**2 + y_dist**2)
                    distance_to_hub = np.sqrt(distance_to_base**2 + elev_diff**2)

                    target_azs = 90 - np.arctan2(y_dist, x_dist) * 180 / np.pi
                    target_azs = np.where(target_azs > 180, target_azs - 360, target_azs)
                    target_alts = np.arctan2(elev_diff, distance_to_base) * 180 / np.pi
                    # Cada píxel representa un PUNTO específico (no una zona promedio)
                    # Por eso usamos receptor_size pequeño (2m = ventana típica)
                    # Si usáramos receptor_size = resolution, la variance se infla y los valores
                    # se vuelven irrealistas (1000+ h/year en píxeles cercanos a turbines)
                    angle_vars = np.arctan2(turb_rotors / 2 + 1.0, distance_to_hub) * 180 / np.pi + 0.2725

                    # ========== COMPARACIÓN VECTORIZADA (timesteps × turbines) ==========
                    # Usar variables pre-shapeadas
                    azi_diff = ((sun_az_2d - target_azs[np.newaxis, :] + 180.0) % 360.0) - 180.0
                    alt_diff = sun_alt_2d - target_alts[np.newaxis, :]
                    has_shadow = (azi_diff**2 + alt_diff**2) <= angle_vars[np.newaxis, :]**2

                    # Sombra de cualquier turbina
                    has_shadow_any = np.any(has_shadow, axis=1)

                    # Count timesteps with shadow
                    shadow_timesteps = int(has_shadow_any.sum())
                    hours = (shadow_timesteps * step_min) / 60.0

                    # ========== ACUMULAR MATRIZ 12x24 PARA ESTE PÍXEL ==========
                    # For timesteps with shadow, count by month-hour
                    pixel_matrix = np.zeros((12, 24), dtype=np.int32)
                    if shadow_timesteps > 0:
                        shadow_indices = np.where(has_shadow_any)[0]
                        months_shadow = sun_month_array[shadow_indices]
                        hours_shadow = sun_hour_array[shadow_indices]
                        # Acumular: cada timestep aporta `step_min` minutos
                        np.add.at(pixel_matrix, (months_shadow, hours_shadow), step_min)

                    # DEBUG
                    if thread_id == 0 and debug_count < 5:
                        closest_turb = min(self.turbines, key=lambda t: np.sqrt((x-t['x'])**2 + (y-t['y'])**2))
                        dx = x - closest_turb['x']
                        dy = y - closest_turb['y']
                        direction = "NORTE" if dy > 0 else "SUR" if dy < 0 else "ESTE" if dx > 0 else "OESTE"
                        debug_print(f"\n[DEBUG Raster] Punto {debug_count}: ({x:.1f}, {y:.1f}) - {direction}")
                        debug_print(f"  Timesteps with shadow: {shadow_timesteps}/{len(sun_az_array)}")
                        debug_print(f"  Total hours: {hours:.2f} h/year")
                        debug_count += 1

                    with lock:
                        raster_array[j, i] = hours
                        raster_12x24[j, i] = pixel_matrix
                        progress_counter[0] += 1

                        # Update progress cada 50 points
                        if progress_counter[0] % 50 == 0:
                            progress_pct = int(100 * progress_counter[0] / len(valid_indices))
                            self.setProgress(progress_pct)

            # Lanzar threads
            debug_print(f"[Shadow Raster Task] Lanzando {n_threads} threads...")
            threads = []
            for t_id in range(n_threads):
                start_idx = t_id * chunk_size
                end_idx = (t_id + 1) * chunk_size if t_id < n_threads - 1 else len(valid_indices)
                chunk = valid_indices[start_idx:end_idx]

                thread = Thread(target=process_chunk, args=(chunk, t_id))
                thread.start()
                threads.append(thread)
                debug_print(f"[Shadow Raster Task] Thread {t_id} iniciado ({len(chunk)} points)")

            # Esperar a que terminen
            debug_print("[Shadow Raster Task] Esperando a que terminen los threads...")
            for thread in threads:
                thread.join()

            debug_print("[Shadow Raster Task] All los threads terminados")

            if self.isCanceled():
                debug_print("[Shadow Raster Task] Cancelled after threads")
                return False

            # 6. Guardar raster
            debug_print("[Shadow Raster Task] Saving raster...")
            from osgeo import gdal, osr

            output_dir = os.path.join(os.path.expanduser("~"), "shadow_raster")
            os.makedirs(output_dir, exist_ok=True)

            self.raster_path = os.path.join(
                output_dir, 
                f"shadow_flicker_{datetime.now().strftime('%Y%m%d_%H%M%S')}.tif"
            )

            debug_print(f"[Shadow Raster Task] Ruta: {self.raster_path}")

            driver = gdal.GetDriverByName('GTiff')
            dataset = driver.Create(
                self.raster_path,
                len(x_range),
                len(y_range),
                1,
                gdal.GDT_Float32
            )

            dataset.SetGeoTransform([xmin, self.resolution, 0, ymax, 0, -self.resolution])

            srs = osr.SpatialReference()
            if self.turbine_crs_wkt:
                srs.ImportFromWkt(self.turbine_crs_wkt)
                dataset.SetProjection(srs.ExportToWkt())

            band = dataset.GetRasterBand(1)

            # CRITICAL: Voltear array verticalmente antes de escribir
            # raster_array[0] corresponde a y_range[0] = ymin (SUR)
            # GDAL espera raster_array[0] = ymax (NORTE) cuando GeoTransform tiene origen TOP-LEFT
            # Por eso hacemos flipud para que coincidan
            write_float32_band(
                band,
                raster_array,
                gdal_module=gdal,
                flip_vertical=True,
                nodata=-9999,
            )
            band.FlushCache()
            dataset.FlushCache()
            dataset = None

            debug_print(f"[Shadow Raster Task] Raster saved successfully")

            # Guardar archivo NPZ with datos completos para filtrado posterior
            npz_path = self.raster_path.replace('.tif', '_data.npz')
            self.npz_path = npz_path

            debug_print(f"[Shadow Raster Task] Saving data for filtering: {npz_path}")
            np.savez_compressed(
                npz_path,
                raster_12x24=raster_12x24,        # (height, width, 12, 24) minutos por mes-hora
                valid_mask_grid=mask,             # valid calculation pixels, including 0-hour pixels
                xmin=xmin,
                ymax=ymax,
                resolution=self.resolution,
                width=len(x_range),
                height=len(y_range),
                crs_wkt=self.turbine_crs_wkt,
                year=self.calculator.year,
                latitude=self.calculator.latitude,
                longitude=self.calculator.longitude,
            )
            debug_print(f"[Shadow Raster Task] ✅ NPZ saved: {os.path.getsize(npz_path)/1024:.0f} KB")

            self.elapsed_time = time.time() - start_time
            debug_print(f"[Shadow Raster Task] ✅ Completed in {self.elapsed_time:.1f}s")
            return True

        except Exception as e:
            import traceback
            error_msg = f"{str(e)}\n{traceback.format_exc()}"
            self.exception = error_msg
            debug_print(f"[Shadow Raster Task] ❌ EXCEPCIÓN:")
            debug_print(error_msg)
            return False

    def finished(self, result):
        """Llamado cuando termina el task."""
        if result:
            debug_print(f"[Shadow Raster Task] ✅ Completed successfully in {self.elapsed_time:.1f}s")
        elif self.exception:
            debug_print(f"[Shadow Raster Task] ❌ Error: {self.exception}")
        else:
            debug_print(f"[Shadow Raster Task] ⚠️ Cancelled (no specific error)")

    def cancel(self):
        """Cancelar el task."""
        debug_print("[Shadow Raster Task] Cancelando...")
        super().cancel()

# -*- coding: utf-8 -*-
"""Raster creation, filtering and styling for shadow flicker outputs."""
from __future__ import annotations

from ..debug import debug_print

from datetime import datetime
import os

import numpy as np
from qgis.PyQt import QtWidgets, QtGui
from qgis.core import QgsRasterLayer, QgsProject

from .task import ShadowRasterTask
from ..i18n_local import tr4 as _ml, lang_code, hours_per_year_unit
from ...raster_io import write_float32_band


def _raster_prefix() -> str:
    return {
        "es": "Sombras",
        "en": "Shadow",
        "fr": "Ombres",
        "de": "Schattenwurf",
    }.get(lang_code(), "Sombras")


def create_shadow_raster_for_page(self, turbines, calculator, turbine_layer, dem_layer=None):
    """Create shadow flicker raster map using a background QgsTask."""
    debug_print("[Shadow Raster] Starting background raster generation...")

    resolution = self.sp_raster_resolution.value()
    raster_timestep = self.sp_raster_timestep.value()
    max_distance = getattr(calculator, "max_shadow_distance_m", 2000.0)

    # Snapshot every worker input on the main thread. QgsMapLayer,
    # QgsRasterDataProvider and QgsProject objects must not be accessed from a
    # QgsTask worker thread.
    turbine_snapshot = []
    for turbine in turbines or []:
        turbine_snapshot.append({
            "name": str(turbine.get("name") or "WT"),
            "x": float(turbine.get("x") or 0.0),
            "y": float(turbine.get("y") or 0.0),
            "hub_height": float(turbine.get("hub_height") or 0.0),
            "rotor_diameter": float(turbine.get("rotor_diameter") or 0.0),
            "ground_elev": float(turbine.get("ground_elev") or 0.0),
        })

    calculator_snapshot = {
        "year": int(calculator.year),
        "latitude": float(calculator.latitude),
        "longitude": float(calculator.longitude),
        "timezone_offset": float(calculator.timezone_offset),
        "timezone_mode": str(calculator.timezone_mode or "fixed"),
        "timezone_name": str(calculator.timezone_name or "UTC"),
        "min_sun_elevation": float(calculator.min_sun_elevation),
        "max_sun_elevation": float(calculator.max_sun_elevation),
        "max_shadow_distance_m": float(max_distance),
    }
    turbine_crs_wkt = str(turbine_layer.crs().toWkt() or "")

    dem_path = ""
    if dem_layer is not None:
        try:
            # Reuse the main-thread materialisation helper already used by the
            # noise task. It returns a real path that GDAL can open safely in a
            # worker, including for provider-backed temporary rasters.
            from ...noise_core.snapshot.builder import _export_dem_layer_for_task
            dem_path = str(_export_dem_layer_for_task(dem_layer) or "")
        except Exception as exc:
            debug_print(f"[Shadow Raster] WARN could not prepare DEM for worker: {exc}")

    task = ShadowRasterTask(
        _ml(
            "Generando mapa ráster de sombras y parpadeo",
            "Generating shadow-flicker raster map",
            "Génération de la carte raster d’ombres et scintillement",
            "Schattenwurf-Rasterkarte wird erzeugt",
        ),
        turbine_snapshot,
        calculator_snapshot,
        turbine_crs_wkt,
        resolution,
        raster_timestep,
        dem_path,
    )

    task.taskCompleted.connect(lambda: self._on_raster_completed(task))
    task.taskTerminated.connect(lambda: self._on_raster_terminated(task))

    from qgis.core import QgsApplication
    QgsApplication.taskManager().addTask(task)

    QtWidgets.QMessageBox.information(
        self,
        _ml("Ráster en curso", "Raster running", "Raster en cours", "Raster wird erzeugt"),
        _ml(
            f"El mapa ráster se está generando en segundo plano.\n\n"
            f"Resolución: {resolution} m\n"
            f"Paso temporal: {raster_timestep} min\n"
            f"Distancia máxima de sombra: {max_distance:.0f} m\n\n"
            f"Puedes seguir trabajando en QGIS.\n\nSe avisará al finalizar.",
            f"The raster map is being generated in the background.\n\n"
            f"Resolution: {resolution} m\n"
            f"Time step: {raster_timestep} min\n"
            f"Maximum shadow distance: {max_distance:.0f} m\n\n"
            f"You can continue working in QGIS.\n\nYou will be notified when it finishes.",
            f"La carte raster est générée en arrière-plan.\n\n"
            f"Résolution : {resolution} m\n"
            f"Pas temporel : {raster_timestep} min\n"
            f"Distance maximale d’ombre : {max_distance:.0f} m\n\n"
            f"Vous pouvez continuer à travailler dans QGIS.\n\nVous serez averti à la fin.",
            f"Die Rasterkarte wird im Hintergrund erzeugt.\n\n"
            f"Auflösung: {resolution} m\n"
            f"Zeitschritt: {raster_timestep} min\n"
            f"Maximale Schattenentfernung: {max_distance:.0f} m\n\n"
            f"Sie können in QGIS weiterarbeiten.\n\nNach Abschluss erhalten Sie eine Meldung.",
        ),
    )


def on_raster_completed_for_page(self, task):
    """Callback when raster generation completes successfully."""
    if task.raster_path and os.path.exists(task.raster_path):
        raster_layer = QgsRasterLayer(
            task.raster_path,
            f"{_raster_prefix()}_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
        )

        if raster_layer.isValid():
            QgsProject.instance().addMapLayer(raster_layer)
            self._apply_raster_symbology(raster_layer)

            try:
                from qgis.utils import iface
                if iface:
                    iface.mapCanvas().setExtent(raster_layer.extent())
                    iface.mapCanvas().refresh()
            except Exception:
                pass

            if hasattr(task, "npz_path") and task.npz_path and os.path.exists(task.npz_path):
                self._last_npz_path = task.npz_path
                self.btn_regenerate.setEnabled(True)
                debug_print(f"[Shadow] NPZ available for filtering: {task.npz_path}")

            QtWidgets.QMessageBox.information(
                self,
                _ml("Ráster terminado", "Raster finished", "Raster terminé", "Raster abgeschlossen"),
                _ml(
                    f"Mapa ráster creado correctamente.\n\n"
                    f"Puntos calculados: {task.points_calculated}\n"
                    f"Tiempo transcurrido: {task.elapsed_time:.1f} segundos\n"
                    f"Archivo: {task.raster_path}\n\n"
                    f"💡 Ahora puedes regenerar TIF filtrados por mes/hora sin recalcular.",
                    f"Raster map created successfully.\n\n"
                    f"Calculated points: {task.points_calculated}\n"
                    f"Elapsed time: {task.elapsed_time:.1f} seconds\n"
                    f"File: {task.raster_path}\n\n"
                    f"💡 You can now regenerate month/hour filtered TIF files without recalculating.",
                    f"Carte raster créée avec succès.\n\n"
                    f"Points calculés : {task.points_calculated}\n"
                    f"Temps écoulé : {task.elapsed_time:.1f} secondes\n"
                    f"Fichier : {task.raster_path}\n\n"
                    f"💡 Vous pouvez maintenant régénérer des TIF filtrés par mois/heure sans recalculer.",
                    f"Rasterkarte erfolgreich erstellt.\n\n"
                    f"Berechnete Punkte: {task.points_calculated}\n"
                    f"Verstrichene Zeit: {task.elapsed_time:.1f} Sekunden\n"
                    f"Datei: {task.raster_path}\n\n"
                    f"💡 Sie können jetzt nach Monat/Stunde gefilterte TIF-Dateien ohne Neuberechnung erzeugen.",
                ),
            )
        else:
            QtWidgets.QMessageBox.critical(
                self,
                _ml("Error", "Error", "Erreur", "Fehler"),
                _ml(
                    "El ráster se ha creado, pero no se pudo cargar en QGIS.",
                    "The raster was created, but it could not be loaded in QGIS.",
                    "Le raster a été créé mais n’a pas pu être chargé dans QGIS.",
                    "Das Raster wurde erstellt, konnte aber nicht in QGIS geladen werden.",
                ),
            )
    else:
        QtWidgets.QMessageBox.critical(
            self,
            _ml("Error", "Error", "Erreur", "Fehler"),
            _ml(
                "No se pudo crear el archivo ráster.",
                "Could not create the raster file.",
                "Impossible de créer le fichier raster.",
                "Die Rasterdatei konnte nicht erstellt werden.",
            ),
        )


def regenerate_filtered_raster_for_page(self):
    """Regenerate a filtered TIF from the saved NPZ by month/hour."""
    if not self._last_npz_path or not os.path.exists(self._last_npz_path):
        QtWidgets.QMessageBox.warning(
            self,
            _ml("Sin datos", "No data", "Aucune donnée", "Keine Daten"),
            _ml(
                "No hay datos ráster disponibles. Genera primero un ráster.",
                "No raster data is available. Generate a raster first.",
                "Aucune donnée raster n’est disponible. Générez d’abord un raster.",
                "Es sind keine Rasterdaten verfügbar. Erzeugen Sie zuerst ein Raster.",
            ),
        )
        return

    month_idx = self.cb_filter_month.currentData()
    hour_idx = self.cb_filter_hour.currentData()

    try:
        debug_print("\n[Shadow Filter] Regenerating filtered raster...")
        debug_print(f"  Month: {self.cb_filter_month.currentText()}")
        debug_print(f"  Hour: {self.cb_filter_hour.currentText()}")

        data = np.load(self._last_npz_path)
        raster_12x24 = data["raster_12x24"]
        valid_mask_grid = data["valid_mask_grid"].astype(bool) if "valid_mask_grid" in data.files else None
        xmin = float(data["xmin"])
        ymax = float(data["ymax"])
        resolution = float(data["resolution"])
        width = int(data["width"])
        height = int(data["height"])
        crs_wkt = str(data["crs_wkt"])

        if month_idx == -1 and hour_idx == -1:
            filtered = raster_12x24.sum(axis=(2, 3))
            filter_name = "all"
            filter_label = _ml("Todos los meses, todas las horas", "All months, all hours", "Tous les mois, toutes les heures", "Alle Monate, alle Stunden")
        elif month_idx != -1 and hour_idx == -1:
            filtered = raster_12x24[:, :, month_idx, :].sum(axis=2)
            filter_name = f"month{month_idx + 1:02d}"
            filter_label = _ml(f"Solo {self.cb_filter_month.currentText()}", f"Only {self.cb_filter_month.currentText()}", f"Seulement {self.cb_filter_month.currentText()}", f"Nur {self.cb_filter_month.currentText()}")
        elif month_idx == -1 and hour_idx != -1:
            filtered = raster_12x24[:, :, :, hour_idx].sum(axis=2)
            filter_name = f"hour{hour_idx:02d}"
            filter_label = _ml(f"Solo a las {hour_idx:02d}:00", f"Only at {hour_idx:02d}:00", f"Seulement à {hour_idx:02d}:00", f"Nur um {hour_idx:02d}:00")
        else:
            filtered = raster_12x24[:, :, month_idx, hour_idx]
            filter_name = f"month{month_idx + 1:02d}_hour{hour_idx:02d}"
            filter_label = _ml(f"{self.cb_filter_month.currentText()} a las {hour_idx:02d}:00", f"{self.cb_filter_month.currentText()} at {hour_idx:02d}:00", f"{self.cb_filter_month.currentText()} à {hour_idx:02d}:00", f"{self.cb_filter_month.currentText()} um {hour_idx:02d}:00")

        filtered_hours = filtered.astype(np.float32) / 60.0
        total_per_pixel = raster_12x24.sum(axis=(2, 3))
        if valid_mask_grid is not None:
            filtered_hours[~valid_mask_grid] = -9999
        else:
            filtered_hours[total_per_pixel == 0] = -9999

        output_dir = os.path.dirname(self._last_npz_path)
        base_name = os.path.basename(self._last_npz_path).replace("_data.npz", "")
        filtered_path = os.path.join(output_dir, f"{base_name}_{filter_name}.tif")

        from osgeo import gdal, osr
        driver = gdal.GetDriverByName("GTiff")
        ds = driver.Create(filtered_path, width, height, 1, gdal.GDT_Float32)
        ds.SetGeoTransform([xmin, resolution, 0, ymax, 0, -resolution])

        srs = osr.SpatialReference()
        srs.ImportFromWkt(crs_wkt)
        ds.SetProjection(srs.ExportToWkt())

        band = ds.GetRasterBand(1)
        write_float32_band(
            band,
            filtered_hours,
            gdal_module=gdal,
            flip_vertical=True,
            nodata=-9999,
        )
        band.FlushCache()
        ds = None

        debug_print(f"[Shadow Filter] ✅ Filtered TIF saved: {filtered_path}")

        raster_layer = QgsRasterLayer(filtered_path, f"{_raster_prefix()}_{filter_name}_{datetime.now().strftime('%H%M%S')}")

        if raster_layer.isValid():
            QgsProject.instance().addMapLayer(raster_layer)
            self._apply_raster_symbology(raster_layer)

            valid_data = filtered_hours[filtered_hours > -100]
            max_val = float(valid_data.max()) if len(valid_data) > 0 else 0.0
            mean_val = float(valid_data.mean()) if len(valid_data) > 0 else 0.0

            QtWidgets.QMessageBox.information(
                self,
                _ml("Ráster filtrado generado", "Filtered raster generated", "Raster filtré généré", "Gefiltertes Raster erzeugt"),
                _ml(
                    f"Filtro aplicado: {filter_label}\n\nMáximo: {max_val:.2f} h\nMedia: {mean_val:.2f} h\n\nArchivo: {filtered_path}",
                    f"Applied filter: {filter_label}\n\nMaximum: {max_val:.2f} h\nMean: {mean_val:.2f} h\n\nFile: {filtered_path}",
                    f"Filtre appliqué : {filter_label}\n\nMaximum : {max_val:.2f} h\nMoyenne : {mean_val:.2f} h\n\nFichier : {filtered_path}",
                    f"Angewandter Filter: {filter_label}\n\nMaximum: {max_val:.2f} h\nMittelwert: {mean_val:.2f} h\n\nDatei: {filtered_path}",
                ),
            )
        else:
            QtWidgets.QMessageBox.warning(
                self,
                _ml("Error", "Error", "Erreur", "Fehler"),
                _ml("No se pudo cargar el TIF filtrado.", "Could not load the filtered TIF.", "Impossible de charger le TIF filtré.", "Das gefilterte TIF konnte nicht geladen werden."),
            )

    except Exception as e:
        import traceback
        debug_print(f"[Shadow Filter] ❌ Error: {e}")
        traceback.print_exc()
        QtWidgets.QMessageBox.critical(
            self,
            _ml("Error", "Error", "Erreur", "Fehler"),
            _ml(
                f"Error al regenerar el ráster:\n\n{e}",
                f"Error while regenerating the raster:\n\n{e}",
                f"Erreur lors de la régénération du raster :\n\n{e}",
                f"Fehler beim erneuten Erzeugen des Rasters:\n\n{e}",
            ),
        )


def on_raster_terminated_for_page(self, task=None):
    """Report a real task error separately from an explicit cancellation."""
    raw_error = str(getattr(task, "exception", "") or "").strip()
    if raw_error:
        detail = raw_error.splitlines()[0].strip() or raw_error
        QtWidgets.QMessageBox.critical(
            self,
            _ml("Error de ráster", "Raster error", "Erreur raster", "Rasterfehler"),
            _ml(
                f"No se pudo generar el ráster de sombras:\n\n{detail}\n\nLos resultados por receptor siguen disponibles.",
                f"The shadow-flicker raster could not be generated:\n\n{detail}\n\nThe receiver results remain available.",
                f"Le raster d’ombres et scintillement n’a pas pu être généré :\n\n{detail}\n\nLes résultats par récepteur restent disponibles.",
                f"Das Schattenwurf-Raster konnte nicht erzeugt werden:\n\n{detail}\n\nDie Ergebnisse je Rezeptor bleiben verfügbar.",
            ),
        )
        return

    QtWidgets.QMessageBox.warning(
        self,
        _ml("Cancelado", "Cancelled", "Annulé", "Abgebrochen"),
        _ml("La generación del ráster se canceló.", "Raster generation was cancelled.", "La génération du raster a été annulée.", "Die Rastererzeugung wurde abgebrochen."),
    )


def apply_raster_symbology_for_page(self, layer):
    """Apply heatmap-style symbology to the shadow flicker raster."""
    from qgis.core import (
        QgsColorRampShader, QgsRasterShader, QgsSingleBandPseudoColorRenderer,
    )

    stats = layer.dataProvider().bandStatistics(1)
    max_val = min(60, stats.maximumValue)
    unit = hours_per_year_unit()

    shader = QgsColorRampShader()
    shader.setColorRampType(QgsColorRampShader.Interpolated)

    color_ramp_items = [
        QgsColorRampShader.ColorRampItem(0, QtGui.QColor(0, 0, 255), f"0 {unit}"),
        QgsColorRampShader.ColorRampItem(5, QtGui.QColor(0, 255, 255), f"5 {unit}"),
        QgsColorRampShader.ColorRampItem(10, QtGui.QColor(0, 255, 0), f"10 {unit}"),
        QgsColorRampShader.ColorRampItem(20, QtGui.QColor(255, 255, 0), f"20 {unit}"),
        QgsColorRampShader.ColorRampItem(30, QtGui.QColor(255, 165, 0), f"30 {unit}"),
        QgsColorRampShader.ColorRampItem(max_val, QtGui.QColor(255, 0, 0), f"{max_val:.0f} {unit}"),
    ]
    shader.setColorRampItemList(color_ramp_items)

    raster_shader = QgsRasterShader()
    raster_shader.setRasterShaderFunction(shader)

    renderer = QgsSingleBandPseudoColorRenderer(layer.dataProvider(), 1, raster_shader)
    layer.setRenderer(renderer)
    layer.triggerRepaint()

# ========== MODEL DETECTION ==========

# -*- coding: utf-8 -*-
"""Raster creation, filtering and styling for shadow flicker outputs."""
from __future__ import annotations

from ..debug import debug_print

from datetime import datetime
import os

import numpy as np
from qgis.PyQt import QtWidgets, QtGui
from qgis.core import QgsApplication, QgsRasterLayer, QgsProject

from .task import ShadowRasterTask


def _is_de() -> bool:
    try:
        from ...i18n import current_language  # type: ignore
    except Exception:
        try:
            from ..i18n import current_language  # type: ignore
        except Exception:
            try:
                from i18n import current_language  # type: ignore
            except Exception:
                return False
    try:
        return str(current_language()).lower().startswith("de")
    except Exception:
        return False


def create_shadow_raster_for_page(self, turbines, calculator, turbine_layer, dem_layer=None):
    """Create shadow flicker raster map using a background QgsTask.

    If ``dem_layer`` is provided, ground elevations are sampled from it for
    every grid pixel and used in the shadow geometry (terrain-aware equivalent).
    If None, the raster falls back to the flat-terrain assumption.
    """
    debug_print("[Shadow Raster] Starting background raster generation...")

    resolution = self.sp_raster_resolution.value()
    raster_timestep = self.sp_raster_timestep.value()
    max_distance = getattr(calculator, "max_shadow_distance_m", 2000.0)

    # Crear task
    task = ShadowRasterTask(
        ("Schattenwurf-Rasterkarte wird erzeugt" if _is_de() else "Génération de la carte raster d’ombres et scintillement"),
        turbines,
        calculator,
        turbine_layer,
        resolution,
        raster_timestep,  # Timestep específico del raster
        dem_layer,        # Optional DEM for terrain-aware grid
    )

    # Conectar señales
    task.taskCompleted.connect(lambda: self._on_raster_completed(task))
    task.taskTerminated.connect(lambda: self._on_raster_terminated())

    # Añadir a task manager de QGIS
    from qgis.core import QgsApplication
    QgsApplication.taskManager().addTask(task)

    QtWidgets.QMessageBox.information(
        self,
        "Raster en cours",
        f"La carte raster est générée en arrière-plan.\n\n"
        f"Résolution : {resolution} m\n"
        f"Pas temporel : {raster_timestep} min\n"
        f"Distance maximale d’ombre : {max_distance:.0f} m\n"
        f"Vous pouvez continuer à travailler dans QGIS.\n\n"
        f"Vous serez averti à la fin."
    )

def on_raster_completed_for_page(self, task):
    """Callback when raster generation completes successfully."""
    import os

    if task.raster_path and os.path.exists(task.raster_path):
        # Cargar raster en QGIS
        from qgis.core import QgsRasterLayer, QgsProject
        raster_layer = QgsRasterLayer(
            task.raster_path, 
            f"Carte_ombres_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        )

        if raster_layer.isValid():
            QgsProject.instance().addMapLayer(raster_layer)
            self._apply_raster_symbology(raster_layer)

            # Zoom
            from qgis.utils import iface
            if iface:
                iface.mapCanvas().setExtent(raster_layer.extent())
                iface.mapCanvas().refresh()

            # ============ GUARDAR NPZ PARA FILTRADO POSTERIOR ============
            if hasattr(task, 'npz_path') and task.npz_path and os.path.exists(task.npz_path):
                self._last_npz_path = task.npz_path
                self.btn_regenerate.setEnabled(True)
                debug_print(f"[Shadow] NPZ disponible para filtrado: {task.npz_path}")

            QtWidgets.QMessageBox.information(
                self,
                "Raster terminé",
                f"Carte raster créée avec succès.\n\n"
                f"Points calculés : {task.points_calculated}\n"
                f"Temps écoulé : {task.elapsed_time:.1f} secondes\n"
                f"Fichier : {task.raster_path}\n\n"
                f"💡 Vous pouvez maintenant régénérer des TIF filtrés par mois/heure\n"
                f"   sans recalculer (avec les listes de filtre)."
            )
        else:
            QtWidgets.QMessageBox.critical(
                self,
                "Erreur",
                ("Das Raster wurde erstellt, konnte aber nicht in QGIS geladen werden." if _is_de() else "Le raster a été créé mais n’a pas pu être chargé dans QGIS.")
            )
    else:
        QtWidgets.QMessageBox.critical(
            self,
            "Erreur",
            "Impossible de créer le fichier raster."
        )

def regenerate_filtered_raster_for_page(self):
    """Regenerate a filtered TIF from the saved NPZ by month/hour."""
    import os

    if not self._last_npz_path or not os.path.exists(self._last_npz_path):
        QtWidgets.QMessageBox.warning(
            self,
            "Aucune donnée",
            "Aucune donnée raster n’est disponible. Générez d’abord un raster."
        )
        return

    # Get selection
    month_idx = self.cb_filter_month.currentData()  # -1 = todos, 0-11 = mes específico
    hour_idx = self.cb_filter_hour.currentData()    # -1 = todas, 0-23 = hora específica

    try:
        debug_print(f"\n[Shadow Filter] Regenerating filtered raster...")
        debug_print(f"  Month: {self.cb_filter_month.currentText()}")
        debug_print(f"  Hour: {self.cb_filter_hour.currentText()}")

        # Cargar NPZ
        data = np.load(self._last_npz_path)
        raster_12x24 = data['raster_12x24']  # (height, width, 12, 24) en minutos
        valid_mask_grid = data['valid_mask_grid'].astype(bool) if 'valid_mask_grid' in data.files else None
        xmin = float(data['xmin'])
        ymax = float(data['ymax'])
        resolution = float(data['resolution'])
        width = int(data['width'])
        height = int(data['height'])
        crs_wkt = str(data['crs_wkt'])
        year = int(data['year'])

        # Apply filtro
        if month_idx == -1 and hour_idx == -1:
            # Todo (suma completa) - igual que el raster original
            filtered = raster_12x24.sum(axis=(2, 3))  # (height, width)
            filter_name = "all"
            filter_label = "Tous les mois, toutes les heures"
        elif month_idx != -1 and hour_idx == -1:
            # Only un mes
            filtered = raster_12x24[:, :, month_idx, :].sum(axis=2)
            filter_name = f"month{month_idx+1:02d}"
            filter_label = f"Seulement {self.cb_filter_month.currentText()}"
        elif month_idx == -1 and hour_idx != -1:
            # Only una hora
            filtered = raster_12x24[:, :, :, hour_idx].sum(axis=2)
            filter_name = f"hour{hour_idx:02d}"
            filter_label = f"Seulement à {hour_idx:02d}:00"
        else:
            # Specific month + hour
            filtered = raster_12x24[:, :, month_idx, hour_idx]
            filter_name = f"month{month_idx+1:02d}_hour{hour_idx:02d}"
            filter_label = f"{self.cb_filter_month.currentText()} à {hour_idx:02d}:00"

        # Convert minutes to hours
        filtered_hours = filtered.astype(np.float32) / 60.0

        # Marcar píxeles fuera del área (los que tenían 0 en TODOS los slots = inválidos)
        # En el original eran -9999. Detectamos píxeles válidos como aquellos donde la suma total > 0
        # o cualquier píxel calculado (mejor: usar la suma original)
        total_per_pixel = raster_12x24.sum(axis=(2, 3))
        # Píxeles fuera del área de cálculo se marcan como NoData.
        # En versiones anteriores se usaba total_per_pixel == 0, lo que convertía
        # píxeles válidos de 0 h/año en NoData. El NPZ nuevo guarda la máscara
        # real de píxeles calculados; para NPZ antiguos se mantiene el fallback.
        if valid_mask_grid is not None:
            filtered_hours[~valid_mask_grid] = -9999
        else:
            filtered_hours[total_per_pixel == 0] = -9999

        # Generar nombre del TIF filtrado
        output_dir = os.path.dirname(self._last_npz_path)
        base_name = os.path.basename(self._last_npz_path).replace('_data.npz', '')
        filtered_path = os.path.join(output_dir, f"{base_name}_{filter_name}.tif")

        # Guardar TIF filtrado
        from osgeo import gdal, osr
        driver = gdal.GetDriverByName('GTiff')
        ds = driver.Create(filtered_path, width, height, 1, gdal.GDT_Float32)
        ds.SetGeoTransform([xmin, resolution, 0, ymax, 0, -resolution])

        srs = osr.SpatialReference()
        srs.ImportFromWkt(crs_wkt)
        ds.SetProjection(srs.ExportToWkt())

        band = ds.GetRasterBand(1)
        # Mismo flip que el raster original
        band.WriteArray(np.flipud(filtered_hours))
        band.SetNoDataValue(-9999)
        band.FlushCache()
        ds = None

        debug_print(f"[Shadow Filter] ✅ Filtered TIF saved: {filtered_path}")

        # Cargar en QGIS
        from qgis.core import QgsRasterLayer, QgsProject
        layer_name = f"Schattenwurf_{filter_name}_{datetime.now().strftime('%H%M%S')}" if _is_de() else f"Ombres_{filter_name}_{datetime.now().strftime('%H%M%S')}"
        raster_layer = QgsRasterLayer(filtered_path, layer_name)

        if raster_layer.isValid():
            QgsProject.instance().addMapLayer(raster_layer)
            self._apply_raster_symbology(raster_layer)

            # Stats
            valid_data = filtered_hours[filtered_hours > -100]
            if len(valid_data) > 0:
                max_val = valid_data.max()
                mean_val = valid_data.mean()
            else:
                max_val = 0
                mean_val = 0

            QtWidgets.QMessageBox.information(
                self,
                "Raster filtré généré",
                f"Filtre appliqué : {filter_label}\n\n"
                f"Maximum : {max_val:.2f} h\n"
                f"Moyenne : {mean_val:.2f} h\n\n"
                f"Fichier : {filtered_path}"
            )
        else:
            QtWidgets.QMessageBox.warning(self, "Erreur", "Impossible de charger le TIF filtré")

    except Exception as e:
        import traceback
        debug_print(f"[Shadow Filter] ❌ Error: {e}")
        traceback.print_exc()
        QtWidgets.QMessageBox.critical(self, "Erreur", f"Erreur lors de la régénération du raster :\n\n{e}")

def on_raster_terminated_for_page(self):
    """Callback when raster generation is cancelled."""
    QtWidgets.QMessageBox.warning(
        self,
        "Annulé",
        "La génération du raster a été annulée."
    )

def apply_raster_symbology_for_page(self, layer):
    """Apply heatmap-style symbology to the shadow flicker raster."""
    from qgis.core import (
        QgsColorRampShader, QgsRasterShader, QgsSingleBandPseudoColorRenderer,
        QgsGradientColorRamp
    )

    # Get statistics
    stats = layer.dataProvider().bandStatistics(1)
    min_val = max(0, stats.minimumValue)
    max_val = min(60, stats.maximumValue)  # Cap a 60h para escala

    # Create color ramp: blue → green → yellow → orange → red
    shader = QgsColorRampShader()
    shader.setColorRampType(QgsColorRampShader.Interpolated)

    color_ramp_items = [
        QgsColorRampShader.ColorRampItem(0, QtGui.QColor(0, 0, 255), "0 h/an"),           # Azul
        QgsColorRampShader.ColorRampItem(5, QtGui.QColor(0, 255, 255), "5 h/an"),        # Cyan
        QgsColorRampShader.ColorRampItem(10, QtGui.QColor(0, 255, 0), "10 h/an"),        # Verde
        QgsColorRampShader.ColorRampItem(20, QtGui.QColor(255, 255, 0), "20 h/an"),      # Yellow
        QgsColorRampShader.ColorRampItem(30, QtGui.QColor(255, 165, 0), "30 h/an"),      # Orange
        QgsColorRampShader.ColorRampItem(max_val, QtGui.QColor(255, 0, 0), f"{max_val:.0f} h/an"),  # Red
    ]
    shader.setColorRampItemList(color_ramp_items)

    raster_shader = QgsRasterShader()
    raster_shader.setRasterShaderFunction(shader)

    renderer = QgsSingleBandPseudoColorRenderer(layer.dataProvider(), 1, raster_shader)
    layer.setRenderer(renderer)
    layer.triggerRepaint()

# ========== MODEL DETECTION ==========


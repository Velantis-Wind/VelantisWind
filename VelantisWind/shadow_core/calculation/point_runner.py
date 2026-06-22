# -*- coding: utf-8 -*-
"""Point-receptor runner for the shadow-flicker module.

The physics code is intentionally kept equivalent to the ShadowPage
implementation.  This module only moves the long calculation workflow out of
the UI class so the page remains a UI/controller surface.
"""

from __future__ import annotations

from ..debug import debug_print

from qgis.PyQt import QtCore, QtWidgets
from qgis.core import (
    QgsProject, QgsRasterLayer, QgsCoordinateTransform, QgsPointXY, QgsWkbTypes,
)

from .. import ShadowFlickerCalculator
from ..timezone_utils import timezone_label
from ..terrain.dem import make_dem_sampler, resolve_dem_layer
from ..turbines.collector import collect_shadow_turbines, log_turbine_dem_summary
from ..receptors.collector import collect_shadow_receptors, log_receptor_dem_summary
from .executor import execute_shadow_receptor_calculations
try:
    from ...i18n import current_language
except Exception:
    def current_language(): return "fr"

def _is_de():
    return str(current_language()).lower().startswith("de")


def run_shadow_point_calculation_for_page(self):
        """Shadow-flicker point-receptor calculation implementation.

        The public UI enters through shadow_core.dialog_controller, which validates
        the configuration and delegates the point-receptor workflow here.
        """
        try:
            # Validate configuration
            prj = QgsProject.instance()

            # Get turbine layer
            turbine_layer_id = self.cb_turbines.currentData(QtCore.Qt.UserRole)
            if not turbine_layer_id:
                QtWidgets.QMessageBox.warning(self, "Keine Windturbine" if _is_de() else "Aucune éolienne", "Wählen Sie einen Windturbinen-Layer aus." if _is_de() else "Sélectionnez une couche d’éoliennes.")
                return

            turbine_layer = prj.mapLayer(turbine_layer_id)
            if not turbine_layer:
                QtWidgets.QMessageBox.critical(self, "Fehler" if _is_de() else "Erreur", "Windturbinen-Layer nicht gefunden." if _is_de() else "Couche d’éoliennes introuvable.")
                return

            # Detailed diagnostics
            debug_print("\n" + "="*70)
            debug_print("[Shadow] TURBINE LAYER CHECK")
            debug_print("="*70)
            debug_print(f"  Selected layer: '{turbine_layer.name()}'")
            debug_print(f"  Layer ID: {turbine_layer_id}")
            debug_print(f"  CRS: {turbine_layer.crs().authid()} ({turbine_layer.crs().description()})")
            debug_print(f"  Total features: {turbine_layer.featureCount()}")
            debug_print(f"  Geometry type: {QgsWkbTypes.displayString(turbine_layer.wkbType())}")

            # Mostrar las primeras 5 coordenadas
            debug_print(f"\n  First coordinates:")
            for i, feat in enumerate(turbine_layer.getFeatures()):
                if i >= 5:
                    break
                geom = feat.geometry()
                if geom and not geom.isNull():
                    pt = geom.asPoint()
                    debug_print(f"    Turbine {i+1}: ({pt.x():.1f}, {pt.y():.1f})")

            # Calculate bounding box
            extent = turbine_layer.extent()
            debug_print(f"\n  Bounding box:")
            debug_print(f"    X: {extent.xMinimum():.0f} - {extent.xMaximum():.0f}  (span: {extent.width():.0f}m)")
            debug_print(f"    Y: {extent.yMinimum():.0f} - {extent.yMaximum():.0f}  (span: {extent.height():.0f}m)")
            debug_print("="*70 + "\n")
            # End diagnostics

            # Get receivers
            receiver_id = self.cb_receivers.currentData(QtCore.Qt.UserRole)
            if not receiver_id:
                QtWidgets.QMessageBox.warning(self, "Kein Rezeptor" if _is_de() else "Aucun récepteur", "Wählen Sie einen Rezeptor-Layer aus." if _is_de() else "Sélectionnez une couche de récepteurs.")
                return

            receiver_layer = prj.mapLayer(receiver_id)
            if not receiver_layer:
                QtWidgets.QMessageBox.critical(self, "Fehler" if _is_de() else "Erreur", "Rezeptor-Layer nicht gefunden." if _is_de() else "Couche de récepteurs introuvable.")
                return

            # Obtener configuración del modelo desde la tabla
            if self.tbl_models.rowCount() == 0:
                QtWidgets.QMessageBox.warning(
                    self,
                    ("Fehlende Konfiguration" if _is_de() else "Configuration manquante"),
                    ("Es ist keine Modellkonfiguration verfügbar.\n\n"
                     "Bitte tragen Sie Nabenhöhe und Rotordurchmesser in der Tabelle ein." if _is_de() else
                     "Aucune configuration de modèle n’est disponible.\n\n"
                     "Veuillez renseigner la hauteur de moyeu et le diamètre du rotor dans le tableau.")
                )
                return

            try:
                hub_height = float(self.tbl_models.item(0, 2).text())
                rotor_diameter = float(self.tbl_models.item(0, 3).text())
            except (ValueError, AttributeError):
                QtWidgets.QMessageBox.warning(
                    self,
                    ("Ungültige Konfiguration" if _is_de() else "Configuration non valide"),
                    ("Nabenhöhe und Rotordurchmesser müssen gültige Zahlen sein." if _is_de() else "La hauteur de moyeu et le diamètre du rotor doivent être des nombres valides.")
                )
                return

            # ===================================================================
            # DEM/DSM terrain sampling.  Moved to shadow_core.terrain.dem while
            # preserving current behavior: missing/invalid samples fall back to 0 m.
            # ===================================================================
            dem_layer_id = self.cb_dem.currentData(QtCore.Qt.UserRole)
            dem_layer, dem_provider = resolve_dem_layer(prj, dem_layer_id)
            sample_turb_elev = make_dem_sampler(turbine_layer.crs(), dem_layer, dem_provider)
            sample_recv_elev = make_dem_sampler(receiver_layer.crs(), dem_layer, dem_provider)

            # Collect turbines from the selected layer
            turbines, n_turb_offdem = collect_shadow_turbines(
                turbine_layer=turbine_layer,
                hub_height=hub_height,
                rotor_diameter=rotor_diameter,
                sample_ground_elev=sample_turb_elev,
                dem_enabled=dem_provider is not None,
            )

            if not turbines:
                QtWidgets.QMessageBox.warning(
                    self,
                    "Keine Windturbine" if _is_de() else "Aucune éolienne",
                    ("Mit der Modellkonfiguration wurde keine gültige Windturbine gefunden.\n\n"
                     "Prüfen Sie, dass:\n"
                     "1. Windturbinen-Layer ausgewählt sind\n"
                     "2. die Modelltabelle Nabenhöhe und Rotordurchmesser enthält\n"
                     "3. die Modellnamen zu den Layern passen" if _is_de() else
                     "Aucune éolienne valide n’a été trouvée avec la configuration du modèle.\n\n"
                     "Vérifiez que :\n"
                     "1. les couches d’éoliennes sont sélectionnées\n"
                     "2. le tableau des modèles contient la hauteur de moyeu et le diamètre du rotor\n"
                     "3. les noms de modèle correspondent aux couches")
                )
                return

            if dem_provider is not None:
                log_turbine_dem_summary(turbines, n_turb_offdem)

            # Site configuration
            latitude = self.sp_latitude.value()
            longitude = self.sp_longitude.value()
            year = self.sp_year.value()
            timezone_mode, timezone_name, timezone_offset = self._get_timezone_settings()
            min_sun_elevation = self.sp_min_elevation.value()
            max_sun_elevation = self.sp_max_elevation.value()
            time_step_minutes = self.sp_time_step.value()
            turbine_availability = self.sp_availability.value()
            observer_height = self.sp_observer_height.value()
            max_shadow_distance_m = float(self.sp_max_shadow_distance.value())

            # Site diagnostics
            debug_print("[Shadow] SITE CONFIGURATION")
            debug_print(f"  Latitude:       {latitude}°")
            debug_print(f"  Longitude:      {longitude}°")
            debug_print(f"  Year:           {year}")
            debug_print(f"  Timezone:      {timezone_label(timezone_mode, timezone_name, timezone_offset)}")
            debug_print(f"  Hub height:    {hub_height}m")
            debug_print(f"  Rotor diam:    {rotor_diameter}m")
            debug_print(f"  Min elev sol:  {min_sun_elevation}°")
            debug_print(f"  Max elev sol:  {max_sun_elevation}°")
            debug_print(f"  Time step:     {time_step_minutes} min")
            debug_print(f"  Max shadow distance: {max_shadow_distance_m:.0f} m")

            # Calculate centroid for validation
            avg_x = sum(t['x'] for t in turbines) / len(turbines)
            avg_y = sum(t['y'] for t in turbines) / len(turbines)
            debug_print(f"\n  Turbine centroid: ({avg_x:.0f}, {avg_y:.0f})")
            debug_print(f"  → Check that it matches the expected location")
            debug_print()
            # End diagnostics

            # Crear calculador
            calculator = ShadowFlickerCalculator(
                latitude=latitude,
                longitude=longitude,
                year=year,
                timezone_offset=timezone_offset,
                timezone_mode=timezone_mode,
                timezone_name=timezone_name,
                min_sun_elevation=min_sun_elevation,
                max_sun_elevation=max_sun_elevation,
                time_step_minutes=time_step_minutes,
                turbine_availability=turbine_availability,
                max_shadow_distance_m=max_shadow_distance_m,
            )

            # Crear diálogo de progreso
            progress_dialog = QtWidgets.QProgressDialog(
                ("Schattenwurfberechnung…" if _is_de() else "Calcul des ombres et du scintillement…"),
                ("Abbrechen" if _is_de() else "Annuler"),
                0,
                100,
                self
            )
            progress_dialog.setWindowTitle("Berechnung läuft" if _is_de() else "Calcul en cours")
            progress_dialog.setWindowModality(QtCore.Qt.WindowModal)
            progress_dialog.setMinimumDuration(0)
            progress_dialog.setValue(0)

            # Receiver-layer diagnostics
            debug_print("[Shadow] RECEIVER LAYER CHECK")
            debug_print(f"  Selected layer: '{receiver_layer.name()}'")
            debug_print(f"  CRS: {receiver_layer.crs().authid()}")
            debug_print(f"  Total features: {receiver_layer.featureCount()}")

            # Verificar que el CRS coincide with turbines
            if receiver_layer.crs().authid() != turbine_layer.crs().authid():
                debug_print(f"  ⚠️ WARNING: receiver CRS ({receiver_layer.crs().authid()}) != CRS de turbines ({turbine_layer.crs().authid()})")
                debug_print(f"  ⚠️ This may cause coordinate errors")
            else:
                debug_print(f"  ✅ CRS matches the turbine layer")
            debug_print()
            # End diagnostics

            # Collect receivers
            receptors, n_recv_offdem = collect_shadow_receptors(
                receiver_layer=receiver_layer,
                observer_height=observer_height,
                sample_ground_elev=sample_recv_elev,
                dem_enabled=dem_provider is not None,
            )

            if not receptors:
                QtWidgets.QMessageBox.warning(self, "Kein Rezeptor" if _is_de() else "Aucun récepteur", "Der Rezeptor-Layer ist leer." if _is_de() else "La couche de récepteurs est vide.")
                return

            if dem_provider is not None:
                log_receptor_dem_summary(receptors, n_recv_offdem)

            # ============ MOSTRAR PRIMEROS RECEPTORES ============
            debug_print("[Shadow] FIRST RECEIVERS READ:")
            for i, r in enumerate(receptors[:5]):
                # Compute distance to nearest turbine
                min_dist = min(((r['x']-t['x'])**2 + (r['y']-t['y'])**2)**0.5 for t in turbines)
                debug_print(f"  {i+1}. {r['name']:30s} ({r['x']:.1f}, {r['y']:.1f})  → nearest turbine: {min_dist:.0f}m")
            debug_print()
            # ============ FIN ============

            # ===================================================================
            # GEOMETRY VERIFICATION DUMP (one-shot)
            # Compares flat vs DEM-aware geometry for the first turbine -> first
            # receptor pair so the user can confirm numerically how the DEM is
            # affecting the calculation BEFORE running the year-long simulation.
            # ===================================================================
            try:
                from ..solar_geometry import calculate_flicker_angles
                t0 = turbines[0]
                r0 = receptors[0]

                t0_ground = float(t0.get('ground_elev', 0.0))
                r0_ground = float(r0.get('ground_elev', 0.0))

                # Flat-terrain reference: hub above z=0, observer above z=0
                az_flat, alt_flat, var_flat = calculate_flicker_angles(
                    t0['x'], t0['y'], t0['hub_height'],
                    r0['x'], r0['y'], r0['z'],
                    t0['rotor_diameter'], receptor_size=2.0,
                )
                # Terrain-aware (what calc will actually use)
                az_dem, alt_dem, var_dem = calculate_flicker_angles(
                    t0['x'], t0['y'], t0['hub_height'] + t0_ground,
                    r0['x'], r0['y'], r0['z'] + r0_ground,
                    t0['rotor_diameter'], receptor_size=2.0,
                )

                horiz_dist = ((t0['x']-r0['x'])**2 + (t0['y']-r0['y'])**2)**0.5
                effective_dz_flat = t0['hub_height'] - r0['z']
                effective_dz_dem = (t0['hub_height'] + t0_ground) - (r0['z'] + r0_ground)

                debug_print("="*70)
                debug_print("[Shadow] GEOMETRY VERIFICATION (flat vs DEM-aware)")
                debug_print("="*70)
                debug_print(f"  Pair: turbine '{t0.get('name','T0')}'  →  receptor '{r0.get('name','R0')}'")
                debug_print(f"  Horizontal distance: {horiz_dist:.1f} m")
                debug_print(f"  Turbine:   hub_height={t0['hub_height']:>6.1f} m   "
                      f"ground_elev={t0_ground:+8.1f} m   "
                      f"abs_hub_z={t0['hub_height']+t0_ground:>7.1f} m")
                debug_print(f"  Receptor:  observer_z={r0['z']:>6.1f} m   "
                      f"ground_elev={r0_ground:+8.1f} m   "
                      f"abs_recv_z={r0['z']+r0_ground:>7.1f} m")
                debug_print(f"  Effective Δz (turb − recv):  flat={effective_dz_flat:+.1f} m   "
                      f"DEM={effective_dz_dem:+.1f} m   "
                      f"shift={effective_dz_dem-effective_dz_flat:+.1f} m")
                debug_print()
                debug_print(f"  {'':22}{'flat terrain':>14}{'with DEM':>14}{'Δ':>10}")
                debug_print(f"  {'target_azimuth':22}{az_flat:>13.3f}°{az_dem:>13.3f}°{az_dem-az_flat:>+9.3f}°")
                debug_print(f"  {'target_altitude':22}{alt_flat:>13.3f}°{alt_dem:>13.3f}°{alt_dem-alt_flat:>+9.3f}°")
                debug_print(f"  {'angle_variance':22}{var_flat:>13.3f}°{var_dem:>13.3f}°{var_dem-var_flat:>+9.3f}°")
                debug_print()
                if dem_provider is None:
                    debug_print("  → No DEM selected: 'with DEM' column equals 'flat terrain' (Δ=0).")
                else:
                    if abs(alt_dem - alt_flat) < 0.01:
                        debug_print("  → DEM active but terrain is essentially flat at this pair.")
                    else:
                        debug_print(f"  → DEM is shifting the target altitude by {alt_dem-alt_flat:+.3f}° "
                              f"({(alt_dem-alt_flat)*60:+.1f}'). Shadow window will be displaced "
                              f"in time accordingly.")
                debug_print("="*70)
                debug_print()
            except Exception as _ver_e:
                debug_print(f"[Shadow] (verification dump skipped: {_ver_e})")
                debug_print()
            # ============ FIN VERIFICATION DUMP ============

            # Verificar si usar paralelización
            use_parallel = False  # parallel calculation removed: always sequential
            num_workers = 1

            # Calculate each receiver.  The execution strategy now lives in
            # shadow_core.calculation.executor, preserving the previous
            # sequential/parallel physics and fallback behavior.
            results = execute_shadow_receptor_calculations(
                calculator=calculator,
                receptors=receptors,
                turbines=turbines,
                latitude=latitude,
                longitude=longitude,
                year=year,
                timezone_offset=timezone_offset,
                min_sun_elevation=min_sun_elevation,
                max_sun_elevation=max_sun_elevation,
                time_step_minutes=time_step_minutes,
                turbine_availability=turbine_availability,
                max_shadow_distance_m=max_shadow_distance_m,
                timezone_mode=timezone_mode,
                timezone_name=timezone_name,
                use_parallel=use_parallel,
                num_workers=num_workers,
                progress_dialog=progress_dialog,
            )

            if results is None:
                return

            progress_dialog.setValue(100)

            # Create layer de resultados
            self._create_results_layer(results, receiver_layer, turbines, calculator)

            # Crear mapa raster si está habilitado
            if self.chk_create_raster.isChecked():
                debug_print("[Shadow] Creating raster map...")
                try:
                    self._create_shadow_raster(turbines, calculator, turbine_layer, dem_layer)
                except Exception as e:
                    debug_print(f"[Shadow] ERROR creating raster: {e}")
                    import traceback
                    traceback.print_exc()
                    QtWidgets.QMessageBox.warning(
                        self, 
                        "Erreur raster", 
                        (f"Rasterkarte konnte nicht erstellt werden:\n\n{e}\n\nDer Punkt-Layer wurde erfolgreich erstellt." if _is_de() else f"Impossible de créer la carte raster :\n\n{e}\n\nLa couche de points a été créée avec succès.")
                    )

            # Mostrar resumen completo (formato resumen)
            self._show_summary_dialog(results, turbines, calculator)

        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "Erreur", f"Erreur pendant le calcul :\n\n{e}")

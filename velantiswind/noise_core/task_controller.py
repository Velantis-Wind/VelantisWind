# -*- coding: utf-8 -*-
"""QgsTask orchestration and raster fallback helpers for Noise calculations."""
from __future__ import annotations

from typing import List

from qgis.PyQt import QtWidgets
from qgis.core import QgsProject

from .domain import NoiseRunConfig
from .result_status import append_result_status as _append_result_status
from .ui_feedback import (
    _append_status_line,
    _close_task_progress_dialog,
    _finish_dialog_progress,
    _hide_dialog_progress,
    _notify_qgis,
    _set_calculate_enabled,
    _set_dialog_busy,
    _set_dialog_progress,
    _show_task_progress_dialog,
    _update_task_progress_dialog,
)
from ..noise_results_dialog import NoiseResultsDialog


def _can_run_grid_as_task(config: NoiseRunConfig) -> bool:
    """Return True when the raster can be safely computed from primitive data.

    Land-use remains synchronous because it still needs vector intersections
    from QGIS layers. DEM/MDT is now safe for both fast and ISO engines because
    the task receives only the raster file path and samples it with GDAL.
    """
    if not bool(config.create_grid_layer):
        return False
    if config.landuse_layer is not None:
        return False
    return True


def _full_noise_task_block_reason(config: NoiseRunConfig) -> str:
    """Explain why the full background task is disabled for this run."""
    if str(config.ground_mode or "global").strip().lower() == "landuse" or config.landuse_layer is not None:
        return "uso del suelo / G efectivo por polígonos todavía usa intersecciones de capas QGIS"
    return "ruta no compatible con tarea en segundo plano"


def _can_run_full_noise_as_task(config: NoiseRunConfig) -> bool:
    """Return whether the full receiver/raster workflow can run safely in QgsTask.

    The worker uses primitive snapshots only. Land-use remains synchronous for
    now because it requires vector intersection logic that is still QGIS-layer
    based. MDT/DSM is supported in the task for both fast and ISO engines: the
    main thread only passes the raster path/elevations, and the worker samples
    terrain profiles with GDAL.
    """
    if str(config.ground_mode or "global").strip().lower() == "landuse" or config.landuse_layer is not None:
        return False
    return True

def _run_full_noise_task_from_dialog(dialog, config: NoiseRunConfig, warnings: List[str]) -> bool:
    """Launch the full noise calculation as a background QgsTask."""
    prep_progress = None
    try:
        from .snapshot.builder import build_noise_calculation_snapshot
        _set_dialog_busy(dialog, "Preparando datos para cálculo en segundo plano…")
        prep_progress = _show_task_progress_dialog(
            dialog,
            "Velantis Wind · preparando ruido",
            "Preparando fuentes, receptores y MDT para el cálculo en segundo plano…",
        )
        _update_task_progress_dialog(prep_progress, "Preparando fuentes, receptores y MDT…", 5.0)
        snapshot = build_noise_calculation_snapshot(config)
        _update_task_progress_dialog(prep_progress, "Datos preparados. Lanzando QgsTask…", 100.0)
        _close_task_progress_dialog(prep_progress, 100)
    except Exception as exc:
        _close_task_progress_dialog(prep_progress, 100)
        QtWidgets.QMessageBox.critical(dialog, "Noise", f"No se pudo preparar el cálculo en segundo plano:\n{exc}")
        _set_calculate_enabled(dialog, True)
        _hide_dialog_progress(dialog)
        return False

    def _finished(ok, task_result, error):
        try:
            if not ok:
                raise RuntimeError(str(error or "error desconocido"))
            from .qgis_io.apply_results import apply_noise_task_result
            _set_dialog_busy(dialog, "Añadiendo capas de resultados a QGIS…")
            res = apply_noise_task_result(snapshot, task_result or {})
            _append_result_status(dialog, res, warnings, grid_async_pending=False)
            _finish_dialog_progress(dialog, "Cálculo de ruido completado.", hide_after_ms=5000)
            _notify_qgis("Noise · Calculation", "Cálculo de ruido completado en segundo plano.", "Success")
            try:
                dlg = NoiseResultsDialog(dialog, res)
                dlg.exec_()
            except Exception as exc:
                QtWidgets.QMessageBox.warning(dialog, "Noise", f"No se pudo mostrar el resumen visual de ruido:\n{exc}")
            QtWidgets.QMessageBox.information(
                dialog,
                "Noise",
                "Cálculo acústico completado en segundo plano.\n\n"
                "Las capas de receptores/fuentes y el raster, si estaba activado, ya se han añadido al proyecto.",
            )
        except Exception as exc:
            _hide_dialog_progress(dialog)
            _notify_qgis("Noise · Calculation", f"No se pudo completar el cálculo: {exc}", "Critical")
            QtWidgets.QMessageBox.critical(dialog, "Noise", f"No se pudo calcular el ruido en segundo plano:\n{exc}")
        finally:
            _set_calculate_enabled(dialog, True)
            try:
                dialog._noise_calc_task = None
            except Exception:
                pass

    try:
        from .tasks.noise_task import start_noise_calculation_task
        create_grid = bool((snapshot.get("params") or {}).get("create_grid_layer", False))
        progress_box = _show_task_progress_dialog(
            dialog,
            "Velantis Wind · Noise calculation",
            "Calculando ruido en segundo plano… 0%",
        )
        try:
            dialog._noise_task_progress_dialog = progress_box
        except Exception:
            pass

        task_holder = {"task": None}

        def _cancel_task():
            try:
                t = task_holder.get("task")
                if t is not None:
                    t.cancel()
            except Exception:
                pass

        try:
            if progress_box is not None:
                progress_box.canceled.connect(_cancel_task)
        except Exception:
            pass

        def _on_progress(value):
            try:
                v = float(value)
                if create_grid and v >= 62.0:
                    label = f"Generando raster de ruido… {v:.0f}%"
                else:
                    label = f"Calculando ruido en segundo plano… {v:.0f}%"
                _set_dialog_progress(dialog, label, v)
                _update_task_progress_dialog(progress_box, label, v)
            except Exception:
                pass

        def _finished_with_progress(ok, task_result, error):
            try:
                if ok:
                    _update_task_progress_dialog(progress_box, "Añadiendo capas de resultados a QGIS…", 100.0)
                else:
                    _update_task_progress_dialog(progress_box, "Cálculo de ruido cancelado o fallido.", 100.0)
                _finished(ok, task_result, error)
            finally:
                _close_task_progress_dialog(progress_box, 100)
                try:
                    dialog._noise_task_progress_dialog = None
                except Exception:
                    pass

        task = start_noise_calculation_task(snapshot, on_finished=_finished_with_progress, on_progress=_on_progress)
        task_holder["task"] = task
        try:
            dialog._noise_calc_task = task
        except Exception:
            pass
        _set_dialog_progress(dialog, "Calculando ruido en segundo plano… 0%", 0.0)
        _notify_qgis("Noise · Calculation", "Cálculo de ruido lanzado en segundo plano. Puedes verlo en el administrador de tareas de QGIS.", "Info")
        _append_status_line(dialog, "• Cálculo pesado lanzado como QgsTask. Puedes seguir usando QGIS mientras avanza.")
        return True
    except Exception as exc:
        _set_calculate_enabled(dialog, True)
        _hide_dialog_progress(dialog)
        QtWidgets.QMessageBox.critical(dialog, "Noise", f"No se pudo lanzar el cálculo en segundo plano:\n{exc}")
        return False

def _task_dem_path(dem_layer) -> str:
    """Return a GDAL-readable DEM path for background tasks."""
    try:
        if dem_layer is None:
            return ""
        from .snapshot.builder import _export_dem_layer_for_task
        return str(_export_dem_layer_for_task(dem_layer) or "")
    except Exception:
        try:
            return str(dem_layer.source() or "")
        except Exception:
            return ""


def _refresh_raster_layer_on_canvas(layer) -> None:
    """Force a QGIS repaint after adding a raster from the noise module."""
    if layer is None:
        return
    try:
        from qgis.utils import iface
        if iface is None:
            return
        try:
            iface.layerTreeView().refreshLayerSymbology(layer.id())
        except Exception:
            pass
        try:
            iface.mapCanvas().refreshAllLayers()
        except Exception:
            try:
                iface.mapCanvas().refresh()
            except Exception:
                pass
    except Exception:
        pass


def _fallback_grid_from_runtime_snapshot(dialog, config: NoiseRunConfig, res: dict) -> bool:
    """Last-resort raster creation when the exact synchronous grid did not add a layer.

    The exact main-thread grid should normally create the raster, including when
    land-use/effective-G is active.  Some experimental release QGIS setups return receiver
    results but fail to materialise the raster layer.  In that case, create a
    task-safe GeoTIFF from the primitive source snapshot and add it on the main
    thread so the user still gets a visible noise map.  If land-use was selected,
    this fallback uses the global G value and records that in the status/report.
    """
    try:
        if not bool(config.create_grid_layer):
            return False
        if res.get("grid_layer") is not None:
            _refresh_raster_layer_on_canvas(res.get("grid_layer"))
            return True
        sources_snapshot = list(res.get("_runtime_sources_snapshot") or [])
        if not sources_snapshot:
            return False
        try:
            crs_wkt = QgsProject.instance().crs().toWkt()
        except Exception:
            crs_wkt = ""
        from .raster.task import compute_noise_grid_file_from_snapshot
        from .qgis_io.apply_results import _add_grid_layer_from_diag
        _append_status_line(dialog, "• AVISO: el raster exacto no se añadió al proyecto; intentando crear un GeoTIFF de respaldo.")
        _set_dialog_progress(dialog, "Creando raster de ruido de respaldo…", 0.0)
        diag = compute_noise_grid_file_from_snapshot(
            sources_snapshot=sources_snapshot,
            crs_wkt=crs_wkt,
            layer_name=config.grid_layer_name,
            grid_resolution_m=float(config.grid_resolution_m),
            max_radius_m=float(config.max_radius_m),
            alpha_db_per_m=float(config.alpha_db_per_m),
            ground_factor_g=float(config.ground_factor_g),
            min_distance_m=float(config.min_distance_m),
            receiver_height_m=float(config.receiver_height_m),
            calculation_engine=str(config.calculation_engine or "fast"),
            temperature_c=float(config.temperature_c),
            humidity_percent=float(config.humidity_percent),
            pressure_kpa=float(config.pressure_kpa),
            dem_path=_task_dem_path(config.dem_layer),
        )
        grid_layer, iso_layer = _add_grid_layer_from_diag(
            QgsProject.instance(),
            diag or {},
            config.grid_layer_name,
            config.iso_layer_name,
            bool(config.create_iso_layer),
            list(config.iso_levels or [35.0, 40.0, 45.0, 50.0]),
        )
        if grid_layer is None:
            return False
        res["grid_layer"] = grid_layer
        res["iso_layer"] = iso_layer
        res["grid_diag"] = diag or {}
        res["grid_cells"] = int((diag or {}).get("grid_cells", 0))
        res["n_iso_features"] = int(iso_layer.featureCount()) if iso_layer is not None else 0
        report_meta = res.get("report_meta") or {}
        report_meta["grid_created"] = True
        report_meta["iso_created"] = bool(iso_layer is not None)
        if str(config.ground_mode or "global").strip().lower() == "landuse" or config.landuse_layer is not None:
            report_meta["grid_note"] = "Fallback raster created with global G because the exact land-use raster layer could not be materialised."
            res.setdefault("grid_warnings", []).append("Raster de respaldo creado con G global porque el raster exacto con land-use no se pudo materializar.")
        res["report_meta"] = report_meta
        _refresh_raster_layer_on_canvas(grid_layer)
        return True
    except Exception as exc:
        try:
            _append_status_line(dialog, f"• AVISO: tampoco se pudo crear el raster de respaldo: {exc}")
        except Exception:
            pass
        return False

def _schedule_grid_task_from_dialog(dialog, config: NoiseRunConfig, res: dict) -> bool:
    """Schedule asynchronous raster generation after receiver results exist."""
    sources_snapshot = list(res.get("_runtime_sources_snapshot") or [])
    if not sources_snapshot:
        return False
    try:
        prj = QgsProject.instance()
        crs_wkt = prj.crs().toWkt()
    except Exception:
        crs_wkt = ""

    params = {
        "sources_snapshot": sources_snapshot,
        "crs_wkt": crs_wkt,
        "layer_name": config.grid_layer_name,
        "iso_layer_name": config.iso_layer_name,
        "create_iso_layer": bool(config.create_iso_layer),
        "iso_levels": list(config.iso_levels or [35.0, 40.0, 45.0, 50.0]),
        "grid_resolution_m": float(config.grid_resolution_m),
        "max_radius_m": float(config.max_radius_m),
        "alpha_db_per_m": float(config.alpha_db_per_m),
        "ground_factor_g": float(config.ground_factor_g),
        "min_distance_m": float(config.min_distance_m),
        "receiver_height_m": float(config.receiver_height_m),
        "calculation_engine": str(config.calculation_engine or "fast"),
        "temperature_c": float(config.temperature_c),
        "humidity_percent": float(config.humidity_percent),
        "pressure_kpa": float(config.pressure_kpa),
        "dem_path": _task_dem_path(config.dem_layer),
    }

    def _finished(ok, diag, grid_layer, iso_layer, error):
        if ok:
            try:
                res["grid_layer"] = grid_layer
                res["iso_layer"] = iso_layer
                res["grid_diag"] = diag or {}
                res["grid_cells"] = int((diag or {}).get("grid_cells", 0))
                _refresh_raster_layer_on_canvas(grid_layer)
                res["n_iso_features"] = int(iso_layer.featureCount()) if iso_layer is not None else 0
                report_meta = res.get("report_meta") or {}
                report_meta["grid_created"] = True
                report_meta["iso_created"] = bool(iso_layer is not None)
                res["report_meta"] = report_meta
            except Exception:
                pass
            cells = int((diag or {}).get("grid_cells", 0))
            eff_res = float((diag or {}).get("effective_resolution_m", config.grid_resolution_m))
            _append_status_line(dialog, f"• Raster de ruido terminado en segundo plano: Noise · Map ({cells} celdas, resolución efectiva {eff_res:.1f} m).")
            if iso_layer is not None:
                _append_status_line(dialog, f"• Isófonas terminadas en segundo plano: {int(iso_layer.featureCount())} entidades.")
            _finish_dialog_progress(dialog, "Raster de ruido completado.", hide_after_ms=5000)
            _notify_qgis("Noise · Raster", "Raster de ruido generado y añadido al proyecto.", "Success")
        else:
            msg = str(error or "error desconocido")
            _append_status_line(dialog, f"• AVISO: el raster en segundo plano no se pudo generar: {msg}")
            _finish_dialog_progress(dialog, "Raster de ruido finalizado con aviso.", hide_after_ms=6500)
            _notify_qgis("Noise · Raster", f"No se pudo generar el raster: {msg}", "Warning")
        _set_calculate_enabled(dialog, True)
        try:
            dialog._noise_grid_task = None
        except Exception:
            pass

    try:
        from .raster.task import start_noise_grid_task
        progress_box = _show_task_progress_dialog(
            dialog,
            "Velantis Wind · Noise raster",
            "Generando raster de ruido… 0%",
        )
        task_holder = {"task": None}

        def _cancel_task():
            try:
                t = task_holder.get("task")
                if t is not None:
                    t.cancel()
            except Exception:
                pass

        try:
            if progress_box is not None:
                progress_box.canceled.connect(_cancel_task)
        except Exception:
            pass

        def _on_grid_progress(value):
            try:
                label = f"Generando raster de ruido… {float(value):.0f}%"
                _set_dialog_progress(dialog, label, float(value))
                _update_task_progress_dialog(progress_box, label, float(value))
            except Exception:
                pass

        def _finished_with_progress(ok, diag, grid_layer, iso_layer, error):
            try:
                _finished(ok, diag, grid_layer, iso_layer, error)
            finally:
                _close_task_progress_dialog(progress_box, 100)

        task = start_noise_grid_task(params, on_finished=_finished_with_progress, on_progress=_on_grid_progress)
        task_holder["task"] = task
        try:
            dialog._noise_grid_task = task
        except Exception:
            pass
        _set_dialog_progress(dialog, "Generando raster de ruido… 0%", 0.0)
        _notify_qgis("Noise · Raster", "Raster de ruido lanzado en segundo plano. Puedes verlo en el administrador de tareas de QGIS.", "Info")
        return True
    except Exception as exc:
        _append_status_line(dialog, f"• AVISO: no se pudo lanzar el raster en segundo plano: {exc}")
        return False

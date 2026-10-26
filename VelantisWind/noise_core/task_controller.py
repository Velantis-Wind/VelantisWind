# -*- coding: utf-8 -*-
"""QgsTask orchestration and raster fallback helpers for Noise calculations."""
from __future__ import annotations

import os
from typing import List

from qgis.PyQt import QtWidgets
try:
    from ..i18n import current_language
except Exception:
    def current_language():
        return "es"
from ..i18n import tr_text
from qgis.core import QgsProject

from ..crs_utils import preferred_wkt
from .domain import NoiseRunConfig
from .project_watch import PROJECT_CHANGED, PROJECT_CHANGED_NO_FILES, ProjectWatch
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
        return tr_text("uso del suelo / G efectivo por polígonos todavía usa intersecciones de capas QGIS")
    return tr_text("ruta no compatible con tarea en segundo plano")


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
        _set_dialog_busy(dialog, tr_text("Preparando datos para cálculo en segundo plano…"))
        prep_progress = _show_task_progress_dialog(
            dialog,
            tr_text("Velantis Wind · preparando ruido"),
            tr_text("Preparando fuentes, receptores y MDT para el cálculo en segundo plano…"),
        )
        _update_task_progress_dialog(prep_progress, tr_text("Preparando fuentes, receptores y MDT…"), 5.0)
        snapshot = build_noise_calculation_snapshot(config)
        _update_task_progress_dialog(prep_progress, tr_text("Datos preparados. Lanzando QgsTask…"), 100.0)
        _close_task_progress_dialog(prep_progress, 100)
    except Exception as exc:
        _close_task_progress_dialog(prep_progress, 100)
        QtWidgets.QMessageBox.critical(dialog, tr_text("Ruido"), tr_text("No se pudo preparar el cálculo en segundo plano:") + f"\n{exc}")
        _set_calculate_enabled(dialog, True)
        _hide_dialog_progress(dialog)
        return False

    watch = ProjectWatch()

    def _finished(ok, task_result, error):
        project_changed = watch.changed()
        try:
            if not ok:
                raise RuntimeError(str(error or tr_text("error desconocido")))
            if project_changed:
                # A result of another project is never added to this one; the raster file, if any, is kept.
                grid_path = str(((task_result or {}).get("grid_diag") or {}).get("grid_path") or "")
                msg = (tr_text(PROJECT_CHANGED).format(path=os.path.dirname(grid_path)) if grid_path
                       else tr_text(PROJECT_CHANGED_NO_FILES))
                _hide_dialog_progress(dialog)
                _notify_qgis(tr_text("Ruido · Cálculo"), msg, "Warning")
                QtWidgets.QMessageBox.warning(dialog, tr_text("Ruido"), msg)
                return
            from .qgis_io.apply_results import apply_noise_task_result
            _set_dialog_busy(dialog, tr_text("Añadiendo capas de resultados a QGIS…"))
            res = apply_noise_task_result(snapshot, task_result or {})
            _append_result_status(dialog, res, warnings, grid_async_pending=False)
            _finish_dialog_progress(dialog, tr_text("Cálculo de ruido completado."), hide_after_ms=5000)
            _notify_qgis(tr_text("Ruido · Cálculo"), tr_text("Cálculo de ruido completado en segundo plano."), "Success")
            try:
                dlg = NoiseResultsDialog(dialog, res)
                dlg.exec_()
            except Exception as exc:
                _lang = str(current_language()).lower()
                if _lang.startswith("de"):
                    QtWidgets.QMessageBox.warning(dialog, "Schall", f"Die visuelle Schallübersicht konnte nicht angezeigt werden:\n{exc}")
                elif _lang.startswith("fr"):
                    QtWidgets.QMessageBox.warning(dialog, "Bruit", f"Impossible d’afficher le résumé visuel du bruit :\n{exc}")
                elif _lang.startswith("en"):
                    QtWidgets.QMessageBox.warning(dialog, "Noise", f"Could not display the visual noise summary:\n{exc}")
                else:
                    QtWidgets.QMessageBox.warning(dialog, "Ruido", f"No se pudo mostrar el resumen visual de ruido:\n{exc}")
            QtWidgets.QMessageBox.information(
                dialog,
                tr_text("Ruido"),
                tr_text("Cálculo acústico completado en segundo plano.\n\n"
                        "Las capas de receptores/fuentes y el ráster, si estaba activado, ya se han añadido al proyecto."),
            )
        except Exception as exc:
            _hide_dialog_progress(dialog)
            _notify_qgis(tr_text("Ruido · Cálculo"), tr_text("No se pudo completar el cálculo: {error}").format(error=exc), "Critical")
            QtWidgets.QMessageBox.critical(dialog, tr_text("Ruido"), tr_text("No se pudo calcular el ruido en segundo plano:") + f"\n{exc}")
        finally:
            _set_calculate_enabled(dialog, True)
            try:
                dialog._noise_calc_task = None
            except Exception:  # nosec B110
                pass

    try:
        from .tasks.noise_task import start_noise_calculation_task
        create_grid = bool((snapshot.get("params") or {}).get("create_grid_layer", False))
        progress_box = _show_task_progress_dialog(
            dialog,
            tr_text("Velantis Wind · cálculo de ruido"),
            tr_text("Calculando ruido en segundo plano… {pct}%").format(pct=0),
        )
        try:
            dialog._noise_task_progress_dialog = progress_box
        except Exception:  # nosec B110
            pass

        task_holder = {"task": None}

        def _cancel_task():
            try:
                t = task_holder.get("task")
                if t is not None:
                    t.cancel()
            except Exception:  # nosec B110
                pass

        try:
            if progress_box is not None:
                progress_box.canceled.connect(_cancel_task)
        except Exception:  # nosec B110
            pass

        def _on_progress(value):
            try:
                v = float(value)
                if create_grid and v >= 62.0:
                    label = tr_text("Generando ráster de ruido… {pct}%").format(pct=f"{v:.0f}")
                else:
                    label = tr_text("Calculando ruido en segundo plano… {pct}%").format(pct=f"{v:.0f}")
                _set_dialog_progress(dialog, label, v)
                _update_task_progress_dialog(progress_box, label, v)
            except Exception:  # nosec B110
                pass

        def _finished_with_progress(ok, task_result, error):
            try:
                if ok:
                    _update_task_progress_dialog(progress_box, tr_text("Añadiendo capas de resultados a QGIS…"), 100.0)
                else:
                    _update_task_progress_dialog(progress_box, tr_text("Cálculo de ruido cancelado o fallido."), 100.0)
                _finished(ok, task_result, error)
            finally:
                _close_task_progress_dialog(progress_box, 100)
                try:
                    dialog._noise_task_progress_dialog = None
                except Exception:  # nosec B110
                    pass

        task = start_noise_calculation_task(snapshot, on_finished=_finished_with_progress, on_progress=_on_progress)
        task_holder["task"] = task
        try:
            dialog._noise_calc_task = task
        except Exception:  # nosec B110
            pass
        _set_dialog_progress(dialog, tr_text("Calculando ruido en segundo plano… {pct}%").format(pct=0), 0.0)
        _notify_qgis(tr_text("Ruido · Cálculo"), tr_text("Cálculo de ruido lanzado en segundo plano. Puedes verlo en el administrador de tareas de QGIS."), "Info")
        _append_status_line(dialog, tr_text("• Cálculo pesado lanzado como QgsTask. Puedes seguir usando QGIS mientras avanza."))
        return True
    except Exception as exc:
        watch.release()
        _set_calculate_enabled(dialog, True)
        _hide_dialog_progress(dialog)
        QtWidgets.QMessageBox.critical(dialog, tr_text("Ruido"), tr_text("No se pudo lanzar el cálculo en segundo plano:") + f"\n{exc}")
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
        except Exception:  # nosec B110
            pass
        try:
            iface.mapCanvas().refreshAllLayers()
        except Exception:
            try:
                iface.mapCanvas().refresh()
            except Exception:  # nosec B110
                pass
    except Exception:  # nosec B110
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
            crs_wkt = preferred_wkt(QgsProject.instance().crs())
        except Exception:
            crs_wkt = ""
        from .raster.task import compute_noise_grid_file_from_snapshot
        from .qgis_io.apply_results import _add_grid_layer_from_diag
        _append_status_line(dialog, tr_text("• AVISO: el ráster exacto no se añadió al proyecto; intentando crear un GeoTIFF de respaldo."))
        _set_dialog_progress(dialog, tr_text("Creando ráster de ruido de respaldo…"), 0.0)
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
            res.setdefault("grid_warnings", []).append("Ráster de respaldo creado con G global porque el ráster exacto con uso del suelo no se pudo materializar.")
        res["report_meta"] = report_meta
        _refresh_raster_layer_on_canvas(grid_layer)
        return True
    except Exception as exc:
        try:
            _append_status_line(dialog, tr_text("• AVISO: tampoco se pudo crear el ráster de respaldo: {error}").format(error=exc))
        except Exception:  # nosec B110
            pass
        return False

def _schedule_grid_task_from_dialog(dialog, config: NoiseRunConfig, res: dict) -> bool:
    """Schedule asynchronous raster generation after receiver results exist."""
    sources_snapshot = list(res.get("_runtime_sources_snapshot") or [])
    if not sources_snapshot:
        return False
    try:
        prj = QgsProject.instance()
        crs_wkt = preferred_wkt(prj.crs())
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
            except Exception:  # nosec B110
                pass
            cells = int((diag or {}).get("grid_cells", 0))
            eff_res = float((diag or {}).get("effective_resolution_m", config.grid_resolution_m))
            layer_name = grid_layer.name() if grid_layer is not None else config.grid_layer_name
            _append_status_line(dialog, tr_text("• Ráster de ruido terminado en segundo plano: {layer} ({cells} celdas, resolución efectiva {resolution} m).").format(
                layer=layer_name, cells=cells, resolution=f"{eff_res:.1f}"))
            if iso_layer is not None:
                _append_status_line(dialog, tr_text("• Isófonas terminadas en segundo plano: {n} entidades.").format(n=int(iso_layer.featureCount())))
            _finish_dialog_progress(dialog, tr_text("Ráster de ruido completado."), hide_after_ms=5000)
            _notify_qgis(tr_text("Ruido · Ráster"), tr_text("Ráster de ruido generado y añadido al proyecto."), "Success")
        elif getattr(task_holder.get("task"), "project_changed", False):
            # The raster was generated for a project that is no longer open: not added, its file kept.
            msg = str(error or "")
            _append_status_line(dialog, tr_text("• AVISO: {message}").format(message=msg))
            _finish_dialog_progress(dialog, tr_text("Ráster de ruido finalizado con aviso."), hide_after_ms=6500)
            _notify_qgis(tr_text("Ruido · Ráster"), msg, "Warning")
        else:
            msg = str(error or tr_text("error desconocido"))
            _append_status_line(dialog, tr_text("• AVISO: el ráster en segundo plano no se pudo generar: {error}").format(error=msg))
            _finish_dialog_progress(dialog, tr_text("Ráster de ruido finalizado con aviso."), hide_after_ms=6500)
            _notify_qgis(tr_text("Ruido · Ráster"), tr_text("No se pudo generar el ráster: {error}").format(error=msg), "Warning")
        _set_calculate_enabled(dialog, True)
        try:
            dialog._noise_grid_task = None
        except Exception:  # nosec B110
            pass

    try:
        from .raster.task import start_noise_grid_task
        progress_box = _show_task_progress_dialog(
            dialog,
            tr_text("Velantis Wind · ráster de ruido"),
            tr_text("Generando ráster de ruido… {pct}%").format(pct=0),
        )
        task_holder = {"task": None}

        def _cancel_task():
            try:
                t = task_holder.get("task")
                if t is not None:
                    t.cancel()
            except Exception:  # nosec B110
                pass

        try:
            if progress_box is not None:
                progress_box.canceled.connect(_cancel_task)
        except Exception:  # nosec B110
            pass

        def _on_grid_progress(value):
            try:
                label = tr_text("Generando ráster de ruido… {pct}%").format(pct=f"{float(value):.0f}")
                _set_dialog_progress(dialog, label, float(value))
                _update_task_progress_dialog(progress_box, label, float(value))
            except Exception:  # nosec B110
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
        except Exception:  # nosec B110
            pass
        _set_dialog_progress(dialog, tr_text("Generando ráster de ruido… {pct}%").format(pct=0), 0.0)
        _notify_qgis(tr_text("Ruido · Ráster"), tr_text("Ráster de ruido lanzado en segundo plano. Puedes verlo en el administrador de tareas de QGIS."), "Info")
        return True
    except Exception as exc:
        _append_status_line(dialog, tr_text("• AVISO: no se pudo lanzar el ráster en segundo plano: {error}").format(error=exc))
        return False

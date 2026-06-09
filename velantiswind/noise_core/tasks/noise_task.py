# -*- coding: utf-8 -*-
"""Full background task for the noise module.

The worker stage uses only primitive snapshots plus GDAL/NumPy helpers. QGIS
layers are created later on the main thread by ``qgis_io.apply_results``.
"""
from __future__ import annotations

from typing import Any, Callable, Dict, Optional

from qgis.core import QgsApplication, QgsTask

from .pure_engine import evaluate_noise_snapshot
from ..raster.task import compute_noise_grid_file_from_snapshot

NoiseFinishedCallback = Callable[[bool, Dict[str, Any], Optional[str]], None]
NoiseProgressCallback = Callable[[float], None]


class NoiseCalculationTask(QgsTask):
    """QgsTask that evaluates receivers and optional raster in the background."""

    def __init__(self, *, snapshot: Dict[str, Any], on_finished: Optional[NoiseFinishedCallback] = None):
        super().__init__("Velantis Wind · Noise calculation", QgsTask.CanCancel)
        self.snapshot = dict(snapshot)
        self.on_finished_callback = on_finished
        self.result: Dict[str, Any] = {}
        self.error: Optional[str] = None

    def run(self) -> bool:  # worker thread
        try:
            params = dict(self.snapshot.get("params") or {})
            create_grid = bool(params.get("create_grid_layer", False))
            receiver_end = 62.0 if create_grid else 96.0
            self.setProgress(1.0)
            evaluation = evaluate_noise_snapshot(
                self.snapshot,
                progress_callback=self.setProgress,
                cancel_callback=self.isCanceled,
                progress_start=2.0,
                progress_end=receiver_end,
            )
            self.result = {"evaluation": evaluation, "grid_diag": {}}
            if self.isCanceled():
                self.error = "Tarea de ruido cancelada."
                return False
            if create_grid:
                sources_snapshot = list(self.snapshot.get("sources") or [])
                grid_params = {
                    "sources_snapshot": sources_snapshot,
                    "crs_wkt": str(self.snapshot.get("crs_wkt") or ""),
                    "layer_name": str(params.get("grid_layer_name") or "Noise · Map"),
                    "grid_resolution_m": float(params.get("grid_resolution_m", 100.0)),
                    "max_radius_m": float(params.get("max_radius_m", 5000.0)),
                    "alpha_db_per_m": float(params.get("alpha_db_per_m", 0.005)),
                    "ground_factor_g": float(params.get("ground_factor_g", 0.5)),
                    "min_distance_m": float(params.get("min_distance_m", 25.0)),
                    "receiver_height_m": float(params.get("receiver_height_m", 4.0)),
                    "calculation_engine": str(params.get("calculation_engine") or "fast"),
                    "temperature_c": float(params.get("temperature_c", 15.0)),
                    "humidity_percent": float(params.get("humidity_percent", 70.0)),
                    "pressure_kpa": float(params.get("pressure_kpa", 101.325)),
                    "dem_path": str(params.get("dem_path") or ""),
                }

                def _grid_progress(value: float) -> None:
                    try:
                        self.setProgress(receiver_end + (98.0 - receiver_end) * max(0.0, min(100.0, float(value))) / 100.0)
                    except Exception:
                        pass

                grid_diag = compute_noise_grid_file_from_snapshot(
                    **grid_params,
                    progress_callback=_grid_progress,
                    cancel_callback=self.isCanceled,
                )
                self.result["grid_diag"] = grid_diag
            self.setProgress(100.0)
            return True
        except Exception as exc:
            self.error = str(exc)
            return False

    def finished(self, success: bool) -> None:  # main thread
        ok = bool(success and not self.error)
        if self.on_finished_callback is not None:
            try:
                self.on_finished_callback(ok, self.result or {}, self.error)
            except Exception:
                pass


def start_noise_calculation_task(
    snapshot: Dict[str, Any],
    on_finished: Optional[NoiseFinishedCallback] = None,
    on_progress: Optional[NoiseProgressCallback] = None,
) -> NoiseCalculationTask:
    """Create, connect and register the full noise task in QGIS task manager.

    Signals are connected before ``addTask`` because QGIS may start the task
    immediately. This makes the progress bar visible from the first emitted
    values and matches the behaviour of the shadow/flicker module.
    """
    task = NoiseCalculationTask(snapshot=snapshot, on_finished=on_finished)
    if on_progress is not None:
        try:
            task.progressChanged.connect(on_progress)
        except Exception:
            pass
    QgsApplication.taskManager().addTask(task)
    return task

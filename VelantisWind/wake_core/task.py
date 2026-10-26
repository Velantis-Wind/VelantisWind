# -*- coding: utf-8 -*-
"""Cancelable background QgsTask for PyWake flow-map raster generation."""
from __future__ import annotations

from typing import Any, Callable, Dict, Optional
import traceback

from qgis.core import Qgis, QgsApplication, QgsMessageLog, QgsTask

from .domain import WakeRasterTaskConfig

WakeFinishedCallback = Callable[[bool, Dict[str, Any], Optional[str]], None]
WakeProgressCallback = Callable[[float], None]


class WakeRasterTask(QgsTask):
    """Run PyWake and GDAL work away from QGIS' GUI thread."""

    def __init__(
        self,
        *,
        config: WakeRasterTaskConfig,
        description: str = "Velantis Wind · Wake raster",
        on_finished: Optional[WakeFinishedCallback] = None,
    ):
        super().__init__(description, QgsTask.CanCancel)
        self.config = config
        self.on_finished_callback = on_finished
        self.result: Dict[str, Any] = {}
        self.error: Optional[str] = None
        self.traceback_text: Optional[str] = None

    def run(self) -> bool:  # worker thread
        try:
            from .raster import compute_wake_raster_config

            kwargs = self.config.to_engine_kwargs()
            kwargs["progress_callback"] = self.setProgress
            kwargs["cancel_callback"] = self.isCanceled
            self.result = compute_wake_raster_config(**kwargs)
            if self.isCanceled():
                self.error = "Tarea de ráster de estelas cancelada."
                return False
            if not self.result.get("path"):
                self.error = "El cálculo terminó sin generar un GeoTIFF de estelas."
                self.result = {"error_item": (self.error, {})}
                return False
            return True
        except Exception as exc:
            self.error = str(exc)
            # Si el motor adjunta plantilla y datos (en la excepción o en su mensaje), el controlador traduce el error
            # al mostrarlo.
            item = getattr(exc, "template_item", None) or getattr(exc.args[0] if exc.args else None,
                                                                 "template_item", None)
            if item:
                self.result = {"error_item": item}
            self.traceback_text = traceback.format_exc()
            try:
                QgsMessageLog.logMessage(
                    self.traceback_text,
                    "VelantisWind · Wake raster",
                    level=Qgis.Critical,
                )
            except Exception:  # nosec B110
                pass
            return False

    def finished(self, success: bool) -> None:  # main thread
        if self.isCanceled() and not self.error:
            self.error = "Tarea de ráster de estelas cancelada."
        ok = bool(success and not self.error and self.result.get("path"))
        if self.on_finished_callback is not None:
            try:
                self.on_finished_callback(ok, self.result or {}, self.error)
            except Exception:  # nosec B110
                pass


def start_wake_raster_task(
    config: WakeRasterTaskConfig,
    *,
    description: str = "Velantis Wind · Wake raster",
    on_finished: Optional[WakeFinishedCallback] = None,
    on_progress: Optional[WakeProgressCallback] = None,
) -> WakeRasterTask:
    """Register the task after all signals have been connected."""
    task = WakeRasterTask(config=config, description=description, on_finished=on_finished)
    if on_progress is not None:
        try:
            task.progressChanged.connect(on_progress)
        except Exception:  # nosec B110
            pass
    QgsApplication.taskManager().addTask(task)
    return task

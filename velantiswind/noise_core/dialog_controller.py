# -*- coding: utf-8 -*-
"""Workflow controller for the Noise page.

The heavy acoustic engine remains in ``noise_compute`` and subpackages.  This
controller now coordinates a small number of focused modules:

- ``dialog_state`` reads widgets/layers and creates ``NoiseRunConfig``.
- ``validation`` checks the run before launching.
- ``task_controller`` handles QgsTask execution and raster fallback.
- ``ui_feedback`` centralises progress and message-bar updates.
"""
from __future__ import annotations

from dataclasses import replace

from qgis.PyQt import QtWidgets

from .dialog_state import build_config_from_dialog
from .result_status import append_result_status as _append_result_status
from .runner import NoiseRunner
from .task_controller import (
    _can_run_full_noise_as_task,
    _can_run_grid_as_task,
    _fallback_grid_from_runtime_snapshot,
    _full_noise_task_block_reason,
    _run_full_noise_task_from_dialog,
    _schedule_grid_task_from_dialog,
)
from .ui_feedback import (
    _append_status_line,
    _finish_dialog_progress,
    _hide_dialog_progress,
    _notify_qgis,
    _set_calculate_enabled,
    _set_dialog_busy,
    _set_dialog_progress,
)
from .validation import validate_run_config
from ..noise_results_dialog import NoiseResultsDialog


def run_noise_from_dialog(dialog) -> None:
    """Run the noise calculation from a ``NoisePage`` instance."""
    try:
        config = build_config_from_dialog(dialog)
    except Exception as exc:
        QtWidgets.QMessageBox.warning(dialog, "Noise", str(exc))
        return

    ui_errors, ui_warnings = dialog._validate_inputs_for_run()
    core_errors, core_warnings = validate_run_config(config)
    errors = list(dict.fromkeys(ui_errors + core_errors))
    warnings = list(dict.fromkeys(ui_warnings + core_warnings))
    if errors:
        QtWidgets.QMessageBox.warning(dialog, "Noise", "No se puede lanzar el cálculo:\n- " + "\n- ".join(errors[:12]))
        return

    _set_calculate_enabled(dialog, False)

    if _can_run_full_noise_as_task(config):
        # Preferred public-plugin path: the heavy receiver loop and optional raster
        # run in a QgsTask. The main thread only prepares primitive snapshots and
        # later creates QGIS layers from the finished result.
        _run_full_noise_task_from_dialog(dialog, config, warnings)
        return

    reason = _full_noise_task_block_reason(config)
    _append_status_line(dialog, f"• AVISO: esta configuración usa ruta síncrona porque {reason}.")
    _notify_qgis("Noise · Calculation", f"Ruta síncrona: {reason}.", "Warning")

    grid_async_pending = _can_run_grid_as_task(config)
    run_config = replace(config, create_grid_layer=False, create_iso_layer=False) if grid_async_pending else config

    if grid_async_pending:
        _set_dialog_busy(dialog, "Calculando receptores y resumen…")
    elif bool(config.create_grid_layer):
        _set_dialog_busy(dialog, "Calculando ruido y raster…")
    else:
        _set_dialog_busy(dialog, "Calculando receptores y resumen…")

    try:
        wrapped = NoiseRunner().run(run_config)
        res = wrapped.raw
    except Exception as exc:
        _set_calculate_enabled(dialog, True)
        _hide_dialog_progress(dialog)
        QtWidgets.QMessageBox.critical(dialog, "Noise", f"No se pudo calcular el ruido:\n{exc}")
        return

    if bool(config.create_grid_layer) and not grid_async_pending:
        _fallback_grid_from_runtime_snapshot(dialog, config, res)

    _set_dialog_progress(dialog, "Resultados por receptor calculados.", 100.0)

    if grid_async_pending:
        if not _schedule_grid_task_from_dialog(dialog, config, res):
            grid_async_pending = False
            _set_calculate_enabled(dialog, True)
            _finish_dialog_progress(dialog, "Cálculo de ruido completado.", hide_after_ms=3500)
    else:
        _set_calculate_enabled(dialog, True)
        _finish_dialog_progress(dialog, "Cálculo de ruido completado.", hide_after_ms=3500)

    _append_result_status(dialog, res, warnings, grid_async_pending=grid_async_pending)

    try:
        dlg = NoiseResultsDialog(dialog, res)
        dlg.exec_()
    except Exception as exc:
        QtWidgets.QMessageBox.warning(dialog, "Noise", f"No se pudo mostrar el resumen visual de ruido:\n{exc}")

    QtWidgets.QMessageBox.information(
        dialog,
        "Noise",
        "Cálculo acústico completado.\n\n"
        "Las capas de receptores/fuentes ya se han añadido al proyecto. "
        "Si el raster estaba activado y no usa uso del suelo, se está generando en segundo plano cuando es seguro hacerlo.",
    )


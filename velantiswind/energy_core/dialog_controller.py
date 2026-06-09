# -*- coding: utf-8 -*-
"""Controlador de la pantalla de energía/AEP.

La ventana ``aep_setup_dialog.py`` conserva la creación de widgets y acciones.
Este controlador se ocupa del flujo de ejecución: leer estado de UI, validar,
mostrar progreso, llamar al runner, registrar resultados y exportar salidas.
"""

from __future__ import annotations

from typing import Any, Dict
import os
import traceback

from qgis.PyQt import QtWidgets
from qgis.core import Qgis, QgsProject
from qgis.utils import iface

from . import EnergyRunner, format_validation_issues, validate_energy_config
from .dialog_state import DialogStateError, build_energy_dialog_state


def _is_debug_enabled() -> bool:
    """Return True when optional developer diagnostics are enabled."""
    try:
        return str(os.environ.get("VELANTISWIND_DEBUG", "")).strip().lower() in {"1", "true", "yes", "on", "debug"}
    except Exception:
        return False
from .ui_feedback import (
    close_progress_dialog,
    create_progress_dialog,
    make_progress_callback,
    qgis_level_from_severity,
    show_message_bar,
    show_user_critical,
    show_user_warning,
)

try:
    from ..ag_core import export_results
except Exception:  # pragma: no cover - standalone fallback
    from ag_core import export_results  # type: ignore

try:
    from ..results_dialog import AEPResultsDialog
except Exception:  # pragma: no cover - standalone fallback
    from results_dialog import AEPResultsDialog  # type: ignore


def _project_crs_authid() -> str:
    try:
        return QgsProject.instance().crs().authid() or "EPSG:25830"
    except Exception:
        return "EPSG:25830"


def _show_state_messages(state: Any) -> None:
    for message in getattr(state, "messages", []) or []:
        show_message_bar(
            getattr(message, "title", "AEP"),
            getattr(message, "message", ""),
            level=qgis_level_from_severity(getattr(message, "severity", "info")),
            duration=getattr(message, "duration", 8),
        )


def _validate_before_run(dialog: Any, config: Any) -> bool:
    """Valida antes de abrir el diálogo de progreso y muestra mensajes claros."""
    issues = validate_energy_config(config)
    errors = [issue for issue in issues if getattr(issue, "is_error", False)]
    if errors:
        show_user_warning(dialog, "Validación AEP", format_validation_issues(errors))
        return False

    warnings = [issue for issue in issues if not getattr(issue, "is_error", False)]
    if warnings:
        show_message_bar("AEP", format_validation_issues(warnings), level=Qgis.Warning, duration=10)
    return True


def _run_energy_calculation(dialog: Any, config: Any) -> Dict[str, Any]:
    """Ejecuta EnergyRunner con diálogo de progreso."""
    progress_dlg = None
    try:
        progress_dlg = create_progress_dialog(dialog)
        progress_callback = make_progress_callback(progress_dlg)
        result = EnergyRunner().run(config, progress_callback=progress_callback)
        close_progress_dialog(progress_dlg, value=100)
        return result
    except Exception:
        close_progress_dialog(progress_dlg)
        raise


def _show_result_summary(result: Dict[str, Any]) -> None:
    try:
        msg = (
            f"AEP con estelas: {result['aep_wake_MWh']:,.0f} MWh | "
            f"Free-stream: {result['aep_free_MWh']:,.0f} MWh | "
            f"Pérdidas: {result['wake_loss_MWh']:,.0f} MWh ({result['wake_loss_pct']:.1f}%)"
        )
        show_message_bar("AEP", msg, level=Qgis.Success, duration=10)
    except Exception:
        pass

    try:
        if result.get("simulation_degraded"):
            show_message_bar(
                "AEP",
                f"La simulación requirió degradación automática: {result.get('simulation_degradation_label')}",
                level=Qgis.Warning,
                duration=12,
            )
    except Exception:
        pass


def _show_results_dialog(parent: Any, result: Dict[str, Any]) -> None:
    try:
        dlg = AEPResultsDialog(parent, result)
        dlg.exec_()
    except Exception as exc:
        show_message_bar(
            "AEP",
            f"No se pudo mostrar el resumen visual de resultados: {exc}",
            level=Qgis.Warning,
            duration=10,
        )


def run_compute_and_update_from_dialog(dialog: Any) -> None:
    """Ejecuta el cálculo AEP desde el diálogo sin alojar lógica en la UI."""
    try:
        state = build_energy_dialog_state(dialog, project_crs_authid=_project_crs_authid())
    except DialogStateError as exc:
        show_user_warning(dialog, exc.title, exc.message)
        return
    except Exception as exc:
        tb = traceback.format_exc()
        if _is_debug_enabled():
            try:
                print(tb)
            except Exception:
                pass
        show_user_critical(dialog, "Cálculo AEP", f"No se pudo leer la configuración de energía:\n{repr(exc)}\n\nDetalles:\n{tb}")
        return

    _show_state_messages(state)
    config = state.to_energy_config()
    if not _validate_before_run(dialog, config):
        return

    try:
        result = _run_energy_calculation(dialog, config)
    except Exception as exc:
        tb = traceback.format_exc()
        if _is_debug_enabled():
            try:
                print(tb)
            except Exception:
                pass
        show_user_critical(dialog, "Cálculo AEP", f"Ocurrió un error:\n{repr(exc)}\n\nDetalles:\n{tb}")
        return

    try:
        dialog._register_last_aep_result(result, "Cálculo AEP")
    except Exception:
        pass

    try:
        export_results_from_dialog(dialog, result, state.base_export_dir)
    except Exception:
        pass

    _show_result_summary(result)
    _show_results_dialog(dialog, result)


def export_results_from_dialog(dialog: Any, res: Dict[str, Any], wasp_dir: str) -> None:
    """Crea capa resumen y exporta CSV por turbina desde el flujo AEP."""
    if not res:
        return

    try:
        export_results.create_summary_layer(res, layer_name="AEP resumen por modelo")
    except Exception as exc:
        show_message_bar(
            "AEP",
            f"No se pudo crear la capa resumen: {exc}",
            level=Qgis.Warning,
            duration=10,
        )

    per_turb = res.get("per_turbine_table")
    if not per_turb:
        return

    base_dir = wasp_dir if wasp_dir and os.path.isdir(wasp_dir) else ""
    suggested = os.path.join(base_dir, "aep_por_turbina.csv") if base_dir else "aep_por_turbina.csv"

    csv_path, _ = QtWidgets.QFileDialog.getSaveFileName(
        dialog,
        "Guardar resultados por turbina",
        suggested,
        "CSV (*.csv)",
    )
    if not csv_path:
        return

    try:
        export_results.export_per_turbine_to_csv(per_turb, csv_path)
    except Exception as exc:
        show_message_bar(
            "AEP",
            f"No se pudo exportar el CSV: {exc}",
            level=Qgis.Warning,
            duration=10,
        )

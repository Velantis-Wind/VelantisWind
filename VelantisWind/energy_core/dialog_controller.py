# -*- coding: utf-8 -*-
"""Controlador de la pantalla de energía/AEP.

La ventana ``aep_setup_dialog.py`` conserva la creación de widgets y acciones.
Este controlador se ocupa del flujo de ejecución: leer estado de UI, validar,
mostrar progreso, llamar al runner, registrar resultados y exportar salidas.
"""

from __future__ import annotations

from typing import Any, Dict, Optional
import html
import os
import traceback

from qgis.PyQt import QtWidgets
from qgis.core import Qgis, QgsCoordinateReferenceSystem, QgsProject
from qgis.utils import iface

from . import EnergyRunner, format_validation_issues, validate_energy_config
from .dialog_state import DialogStateCancelled, DialogStateError, build_energy_dialog_state, layers_used_message
from .translation import tr
from . import aep_inputs
from ..ag_core.log_text import shown
from ..ag_core.results.coverage import partial_aep_warning
from ..wake_core.controller import _uses_metre_units, is_projected_in_metres


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


def _error_text(exc: Exception) -> str:
    """Error para mostrarlo: traducido desde su plantilla si la trae, en la excepción (p. ej. la densidad del aire) o
    en su mensaje (los de la física: la fábrica, la comprobación de clases, los lectores, la API); si no, su mensaje tal
    cual (su ``repr`` solo si no tiene)."""
    if getattr(exc, "template_item", None):
        return shown(exc, tr)
    message = exc.args[0] if exc.args else None
    return shown(message, tr) if getattr(message, "template_item", None) else (str(exc) or repr(exc))


def _resolve_layers_in_edit_mode(dialog: Any, models: Any) -> Optional[bool]:
    """Pregunta qué hacer con las capas elegidas que están en modo edición; None si no se calcula.

    «Guardar cambios y calcular» confirma sus ediciones (si alguna falla, no se calcula) y devuelve True;
    «Calcular sin escribir en la capa» calcula, el volcado de resultados las salta y devuelve False.
    """
    layers = []
    for model in models or []:
        layer = QgsProject.instance().mapLayer(str(model.get("source_layer_id") or ""))
        if layer is not None and layer.isEditable() and all(layer.id() != other.id() for other in layers):
            layers.append(layer)
    if not layers:
        return False
    box = QtWidgets.QMessageBox(dialog)
    box.setIcon(QtWidgets.QMessageBox.Warning)
    box.setWindowTitle(tr("Capas en modo edición"))
    box.setText(
        tr(
            "Estas capas de turbinas están en modo edición:\n{layers}\n\n"
            "Los resultados no se escriben en una capa con la edición abierta."
        ).format(layers="\n".join(f"• {layer.name()}" for layer in layers))
    )
    save = box.addButton(tr("Guardar cambios y calcular"), QtWidgets.QMessageBox.AcceptRole)
    skip = box.addButton(tr("Calcular sin escribir en la capa"), QtWidgets.QMessageBox.ActionRole)
    cancel = box.addButton(tr("Cancelar"), QtWidgets.QMessageBox.RejectRole)
    box.setDefaultButton(cancel)
    box.exec_()
    clicked = box.clickedButton()
    if clicked is skip:
        return False
    if clicked is not save:
        return None
    # Editando en grupo, confirmar una capa confirmaría también las ediciones de otras que no están en la lista.
    if QgsProject.instance().transactionMode() != Qgis.TransactionMode.Disabled:
        show_user_warning(
            dialog,
            tr("Capas en modo edición"),
            tr(
                "El proyecto edita sus capas en grupo (modo de transacción): guardar estas capas guardaría también "
                "los cambios de otras. Guárdalas desde QGIS o calcula sin escribir en la capa. No se ha calculado el AEP."
            ),
        )
        return None
    for layer in layers:
        if not layer.commitChanges():
            show_user_warning(
                dialog,
                tr("Capas en modo edición"),
                tr("No se pudieron guardar los cambios de la capa «{layer}»:\n{errors}\n\nNo se ha calculado el AEP.").format(
                    layer=layer.name(), errors="\n".join(layer.commitErrors())
                ),
            )
            return None
    return True


def _remember_aep_inputs(dialog: Any, config: Any) -> None:
    """What this AEP calculated with, summarised: the wake raster says which of its inputs differ from it (#36)."""
    dialog._last_aep_inputs = aep_inputs.from_run_config(config)


def _project_crs_authid() -> str:
    """El sistema del proyecto para el núcleo: su identificador o, si no lo tiene, su WKT completo.

    WKT2: algunos sistemas válidos (un proyectado derivado, por ejemplo) no tienen WKT1, y llegarían vacíos.
    """
    crs = QgsProject.instance().crs()
    authid = crs.authid()
    # USER: identifiers only exist in QGIS' local CRS database: GDAL cannot interpret them.
    return authid if authid and not authid.upper().startswith("USER:") else crs.toWkt(
        QgsCoordinateReferenceSystem.WKT_PREFERRED
    )


def _project_crs_problem(crs: Any):
    """(título, mensaje) si el sistema del proyecto no es válido, proyectado y en metros; si lo es, None."""
    if is_projected_in_metres(crs):
        return None
    if not crs.isValid():
        return tr("CRS del proyecto"), tr(
            "Define en el proyecto un sistema de coordenadas proyectado y en metros antes de calcular el AEP."
        )
    # Geográfico, o en metros pero geocéntrico: no proyectado.
    if crs.isGeographic() or _uses_metre_units(crs):
        return tr("CRS no proyectado"), tr(
            "El proyecto usa un sistema de coordenadas no proyectado. El AEP necesita un sistema proyectado "
            "y en metros: cambia el del proyecto."
        )
    return tr("Unidades del CRS"), tr(
        "El sistema de coordenadas del proyecto no está en metros. El AEP necesita un sistema proyectado "
        "y en metros: cambia el del proyecto."
    )


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
        show_user_warning(dialog, tr("Validación AEP"), format_validation_issues(errors))
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


def _number(value: Any, spec: str) -> str:
    """A number of the summary in ``spec``; a non-finite one, with its label (#63, decision 10)."""
    from ..ag_core.edge_cases import non_finite_label
    from ..number_format import format_number
    return non_finite_label(value) or format_number(value, spec)


def _summary_message(result: Dict[str, Any]) -> str:
    """The message-bar summary. With a result of schema 2, the total loss (gross minus net: wakes, turbulence and
    blockage, #75 row 4.9), or «no disponible» when the gross AEP could not be calculated."""
    if int(result.get("result_schema_version") or 1) != 2:
        return tr("AEP con estelas: {wake} MWh | AEP bruto: {free} MWh | Pérdidas: {loss} MWh ({pct} %)").format(
            wake=_number(result['aep_wake_MWh'], ",.0f"),
            free=_number(result['aep_free_MWh'], ",.0f"),
            loss=_number(result['wake_loss_MWh'], ",.0f"),
            pct=_number(result['wake_loss_pct'], ".1f"),
        )
    total = result["breakdown"]["L_total"]
    if total["mwh"] is None:
        return tr("AEP neto: {net} MWh | AEP bruto: no disponible | Pérdida total: no disponible").format(
            net=_number(result['aep_wake_MWh'], ",.0f"))
    return tr("AEP neto: {net} MWh | AEP bruto: {free} MWh | Pérdida total: {loss} MWh ({pct} %)").format(
        net=_number(result['aep_wake_MWh'], ",.0f"), free=_number(result['aep_free_MWh'], ",.0f"),
        loss=_number(total['mwh'], ",.0f"), pct=_number(total['pct'], ".1f") if total["pct"] is not None else tr("n/d"))


def _show_result_summary(result: Dict[str, Any], *, layer_message: Optional[str] = None) -> None:
    try:
        show_message_bar("AEP", _summary_message(result), level=Qgis.Success, duration=10)
    except Exception:  # nosec B110
        pass

    # The persistent warnings (decision 19) and the loops that did not converge (decision 9), each saying whether it is
    # of the main calculation or of the variants, as in the results window: visible, never a barrier.
    from ..ag_core.wake_setup.notices import result_warnings
    for warning in result_warnings(result):
        show_message_bar("AEP", shown(warning, tr), level=Qgis.Warning, duration=12)

    if layer_message:
        show_message_bar("AEP", layer_message, level=Qgis.Info, duration=10)

    # Post the coverage warning after success AND the layer-information message,
    # on QGIS's UI thread so it cannot be hidden behind routine notifications.
    # The bar renders HTML, so model names are escaped to be shown literally.
    coverage = partial_aep_warning(result, tr)
    if coverage:
        show_message_bar("AEP", html.escape(coverage), level=Qgis.Warning, duration=16)


def _show_results_dialog(parent: Any, result: Dict[str, Any]) -> None:
    try:
        dlg = AEPResultsDialog(parent, result)
        dlg.exec_()
    except Exception as exc:
        show_message_bar(
            "AEP",
            tr("No se pudo mostrar el resumen visual de resultados: {error}").format(error=exc),
            level=Qgis.Warning,
            duration=10,
        )


def _read_dialog_state(dialog: Any, warn: bool = True) -> Any:
    """El estado del diálogo con las capas de las filas leídas, o None tras avisar de por qué no se puede leer."""
    try:
        return build_energy_dialog_state(dialog, project_crs_authid=_project_crs_authid(), warn=warn)
    except DialogStateCancelled:
        pass  # the dialog has said why (a conflict of the physics) or the user cancelled
    except DialogStateError as exc:
        show_user_warning(dialog, exc.title, exc.message)
    except Exception as exc:
        tb = traceback.format_exc()
        if _is_debug_enabled():
            try:
                print(tb)
            except Exception:  # nosec B110
                pass
        show_user_critical(
            dialog,
            tr("Cálculo AEP"),
            tr("No se pudo leer la configuración de energía:\n{error}\n\nDetalles:\n{details}").format(error=repr(exc), details=tb),
        )
    return None


def run_compute_and_update_from_dialog(dialog: Any) -> None:
    """Ejecuta el cálculo AEP desde el diálogo sin alojar lógica en la UI."""
    # Antes de leer las capas: sus puntos se pasan al sistema del proyecto, y el cálculo mide en metros.
    problem = _project_crs_problem(QgsProject.instance().crs())
    if problem:
        show_user_warning(dialog, *problem)
        return
    state = _read_dialog_state(dialog)
    if state is None:
        return

    _show_state_messages(state)
    config = state.to_energy_config()
    if not _validate_before_run(dialog, config):
        return

    # El caso único escribe resultados en las capas: nunca con una edición abierta.
    saved = _resolve_layers_in_edit_mode(dialog, state.models)
    if saved is None:
        return
    if saved:
        # Lo guardado puede no ser lo que la capa mostraba en edición (un filtro sobre un campo editado): se calcula
        # con lo que queda en la capa, leído de nuevo (sin repetir los avisos de la primera lectura).
        state = _read_dialog_state(dialog, warn=False)
        if state is None:
            return
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
            except Exception:  # nosec B110
                pass
        show_user_critical(
            dialog, tr("Cálculo AEP"), tr("Ocurrió un error:\n{error}\n\nDetalles:\n{details}").format(error=_error_text(exc), details=tb)
        )
        return

    _remember_aep_inputs(dialog, config)
    try:
        dialog._register_last_aep_result(result, tr("Cálculo AEP"))
    except Exception:  # nosec B110
        pass

    try:
        export_results_from_dialog(dialog, result, state.base_export_dir)
    except Exception:  # nosec B110
        pass

    _show_result_summary(result, layer_message=layers_used_message(state.models))
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
            tr("No se pudo crear la capa resumen: {error}").format(error=exc),
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
        tr("Guardar resultados por turbina"),
        suggested,
        "CSV (*.csv)",
    )
    if not csv_path:
        return

    try:
        export_results.export_per_turbine_to_csv(per_turb, csv_path, res)
    except Exception as exc:
        show_message_bar(
            "AEP",
            tr("No se pudo exportar el CSV: {error}").format(error=exc),
            level=Qgis.Warning,
            duration=10,
        )

# -*- coding: utf-8 -*-
"""Main-thread orchestration for the asynchronous wake-raster workflow."""
from __future__ import annotations

import os
import re
from typing import Any, Dict, List, Optional

from qgis.PyQt import QtWidgets
from qgis.core import Qgis, QgsCoordinateReferenceSystem, QgsProject, QgsUnitTypes

from ..ag_core.log_text import log_text, shown
from ..ag_core.wake_setup.messages_translations import register_messages_translations
from .domain import WakeRasterTaskConfig
from ..crs_utils import preferred_wkt

register_messages_translations()  # the warnings and errors of the raster, translated when shown
from .task import start_wake_raster_task

try:
    from ..i18n import tr_text
except Exception:  # pragma: no cover
    def tr_text(text: str) -> str:
        return text

try:
    from ..ag_core.log_text import shown
except Exception:  # pragma: no cover
    from ag_core.log_text import shown  # type: ignore

try:
    from ..ag_core.qgis_io.wake_raster import (
        add_wake_raster_result_to_qgis,
        output_directory_for_project,
    )
except Exception:  # pragma: no cover
    from ag_core.qgis_io.wake_raster import (  # type: ignore
        add_wake_raster_result_to_qgis,
        output_directory_for_project,
    )


def error_text(result: Optional[Dict[str, Any]], error: Optional[str]) -> Optional[str]:
    """The error of a raster task as shown: its template translated, with the data that are templates (the reasons
    of a refusal) translated too; the text as it came without one."""
    item = (result or {}).get("error_item")
    return str(shown(log_text(item[0], **item[1]), tr_text)) if item else error


def _message_bar(title: str, text: str, level=Qgis.Info, duration: int = 8) -> None:
    try:
        from qgis.utils import iface
        if iface is not None:
            iface.messageBar().pushMessage(title, text, level=level, duration=duration)
            return
    except Exception:  # nosec B110
        pass


def _uses_metre_units(crs: Any) -> bool:
    try:
        unit = crs.mapUnits()
    except Exception:
        return False
    candidates = []
    try:
        candidates.append(Qgis.DistanceUnit.Meters)
    except Exception:  # nosec B110
        pass
    try:
        candidates.append(QgsUnitTypes.DistanceMeters)
    except Exception:  # nosec B110
        pass
    if any(candidate is not None and unit == candidate for candidate in candidates):
        return True
    try:
        label = str(QgsUnitTypes.toString(unit) or "").strip().lower()
    except Exception:
        label = str(unit or "").strip().lower()
    # The whole name: a substring would also take kilometres, centimetres or millimetres for metres.
    return label in {"meter", "meters", "metre", "metres", "metro", "metros", "mètre", "mètres"}


def _horizontal_wkt(wkt: str) -> str:
    """The first CRS of a WKT2, unwrapped from ``BOUNDCRS`` and ``COMPOUNDCRS``, without what follows it and with its
    quoted texts (names, remarks) emptied, since they may hold any word."""
    wkt = re.sub(r'"(?:[^"]|"")*"', '""', wkt)
    previous = None
    while wkt != previous:
        previous, wkt = wkt, wkt.lstrip()
        if wkt.startswith("BOUNDCRS["):
            wkt = wkt.split("SOURCECRS[", 1)[-1]
        elif wkt.startswith("COMPOUNDCRS["):
            wkt = re.sub(r'^COMPOUNDCRS\[\s*""\s*,', "", wkt)
    depth = 0
    for i, char in enumerate(wkt):
        if char == "[":
            depth += 1
        elif char == "]":
            depth -= 1
            if depth == 0:
                return wkt[:i + 1]
    return wkt


def _has_geocentric_axes(wkt: str) -> bool:
    """Whether the CRS's own axes, not those of a base CRS inside it, are geocentric."""
    return any(
        match.group(1) == "GEOCENTRICX" and wkt.count("[", 0, match.start()) - wkt.count("]", 0, match.start()) == 1
        for match in re.finditer(r'\bAXIS\[\s*""\s*,\s*(\w+)', wkt)
    )


def is_projected_in_metres(crs: Any) -> bool:
    """Valid, not geographic, in metres, not geocentric and not vertical-only.

    Recognised without ``type()``, in every QGIS version: a geocentric CRS by ``+proj=geocent`` in its PROJ string,
    also when wrapped with datum parameters (``Bound``), or by the geocentric axes of its WKT2 (a derived geocentric
    CRS has no PROJ string; a topocentric one, east/north/up in metres, is accepted); a vertical-only one (heights, no
    horizontal plane) by its WKT2, since its PROJ string is only ``+vunits``, some valid projected systems have no
    PROJ string at all, and a derived vertical CRS has no WKT1. Both are looked for in the horizontal component: the
    source of a ``BOUNDCRS`` and the first component of a ``COMPOUNDCRS``. A projected CRS with datum parameters is
    accepted: its type is ``Bound`` too.
    """
    try:
        wkt = _horizontal_wkt(str(crs.toWkt(QgsCoordinateReferenceSystem.WKT_PREFERRED) or "").upper())
        return bool(
            crs.isValid()
            and not crs.isGeographic()
            and _uses_metre_units(crs)
            and "+proj=geocent" not in str(crs.toProj() or "")
            and not _has_geocentric_axes(wkt)
            and not wkt.startswith(("VERTCRS[", "VERTICALCRS[", "VERT_CS["))
        )
    except Exception:
        return False


def _capture_project_context() -> tuple[str, str, str, bool, bool, bool, Any]:
    project = QgsProject.instance()
    home = str(project.homePath() or "")
    crs_wkt = ""
    crs_authid = ""
    crs_valid = False
    crs_geographic = False
    crs_metric = False
    crs = None
    try:
        crs = project.crs()
        crs_valid = bool(crs is not None and crs.isValid())
        if crs_valid:
            crs_wkt = preferred_wkt(crs)
            # QGIS-local USER: IDs are not portable: persist the WKT separately.
            candidate_authid = str(crs.authid() or "")
            crs_authid = "" if candidate_authid.upper().startswith("USER:") else candidate_authid
            crs_geographic = bool(crs.isGeographic())
            crs_metric = _uses_metre_units(crs)
    except Exception:  # nosec B110
        pass
    return (
        output_directory_for_project(home),
        crs_wkt,
        crs_authid,
        crs_valid,
        crs_geographic,
        crs_metric,
        crs,
    )


def _dialog_is_alive(dialog: Any) -> bool:
    """Return False when the Qt wrapper was deleted while the task was running."""
    if dialog is None:
        return False
    try:
        from qgis.PyQt import sip
        if sip.isdeleted(dialog):
            return False
    except Exception:  # pragma: no cover - depends on PyQt packaging
        pass
    try:
        dialog.thread()
    except RuntimeError:
        return False
    except Exception:
        pass
    return True


def _set_button_running(dialog: Any, running: bool, progress: Optional[float] = None) -> None:
    try:
        button = getattr(dialog, "btn_plot_wakes", None)
    except Exception:
        return
    if button is None:
        return
    try:
        button.setEnabled(not running)
        if running:
            pct = int(round(float(progress or 0.0)))
            button.setText(tr_text("Ráster de estelas en curso… {pct}%").format(pct=pct))
        else:
            button.setText(tr_text("Crear ráster de estelas"))
    except Exception:  # nosec B110
        pass


def _refresh_canvas(layer: Any) -> None:
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
            iface.mapCanvas().refresh()
    except Exception:  # nosec B110
        pass


def start_wake_raster_from_dialog(
    dialog: Any,
    *,
    models: List[Dict[str, Any]],
    wasp_dir: str,
    resolution_m: float,
    wrg_paths: Optional[List[str]],
    wake_config: Any,
    wd_target: Optional[float],
    wake_provenance: Optional[Dict[str, Any]] = None,
    ws_plot: float = 10.0,
    air_density: Optional[Dict[str, Any]] = None,
    changed_aep_inputs: Optional[List[str]] = None,
    last_aep_available: bool = False,
    wd_interp: str = "nearest",
    wrg_direction_count: Optional[int] = None,
    wrg_ti_paths: Optional[List[str]] = None,
    wrg_ti_heights_m: Optional[List[Optional[float]]] = None,
    fixed_ti: Optional[float] = None,
    without_blockage: bool = False,
):
    """Capture state, start the QgsTask and apply its result on completion.

    ``wake_config`` is the validated configuration of the AEP (the dialog's), with the resource inputs of the AEP,
    and ``wake_provenance`` the provenance of its predefined model, if it is one;
    ``without_blockage`` asks for the explicit scenario without blockage.

    Every input is the dialog's when the raster is created (#36): ``changed_aep_inputs`` are the labels of the
    categories that differ from the last AEP of the project (``energy_core.aep_inputs``), which the final window warns
    about, and ``last_aep_available`` says whether there was one.
    """
    existing = getattr(dialog, "_wake_raster_task", None)
    if existing is not None and not bool(getattr(dialog, "_wake_raster_task_finished", True)):
        _message_bar(
            tr_text("Estelas"),
            tr_text("Ya hay un ráster de estelas calculándose. Puedes cancelarlo desde el gestor de tareas de QGIS."),
            Qgis.Warning,
            8,
        )
        return existing

    (
        output_dir,
        crs_wkt,
        crs_authid,
        crs_valid,
        crs_geographic,
        crs_metric,
        project_crs,
    ) = _capture_project_context()
    if not crs_valid:
        QtWidgets.QMessageBox.warning(
            dialog,
            tr_text("CRS del proyecto"),
            tr_text("Define un CRS proyectado válido en el proyecto antes de crear el ráster. Sin CRS no se puede garantizar la georreferenciación del resultado."),
        )
        return None
    if crs_geographic:
        QtWidgets.QMessageBox.warning(
            dialog,
            tr_text("CRS no proyectado"),
            tr_text("El proyecto usa un CRS geográfico. La resolución y las distancias del cálculo están expresadas en metros; reproyecta el proyecto y las capas a un CRS métrico adecuado."),
        )
        return None
    if not crs_metric:
        QtWidgets.QMessageBox.warning(
            dialog,
            tr_text("Unidades del CRS"),
            tr_text("El CRS proyectado no utiliza metros. Selecciona un CRS métrico antes de crear el ráster para que la resolución y las distancias sean correctas."),
        )
        return None
    # What is left: a geocentric or vertical-only CRS, not geographic and in metres, without a horizontal plane. The
    # AEP refuses it too.
    if not is_projected_in_metres(project_crs):
        QtWidgets.QMessageBox.warning(
            dialog,
            tr_text("CRS no proyectado"),
            tr_text("El proyecto usa un CRS geocéntrico o solo vertical. El ráster necesita un sistema proyectado y en metros: cambia el del proyecto."),
        )
        return None

    config = WakeRasterTaskConfig(
        models=models,
        wasp_dir=wasp_dir,
        resolution_m=resolution_m,
        wrg_paths=list(wrg_paths or []),
        ws_plot=ws_plot,
        wake_config=wake_config,
        wake_provenance=wake_provenance,
        wd_target=wd_target,
        output_dir=output_dir,
        crs_wkt=crs_wkt,
        crs_authid=crs_authid,
        air_density=dict(air_density or {"mode": "off"}),
        wd_interp=wd_interp,
        wrg_direction_count=wrg_direction_count,
        wrg_ti_paths=wrg_ti_paths,
        wrg_ti_heights_m=wrg_ti_heights_m,
        fixed_ti=fixed_ti,
        # The CRS of the TI raster's target, as the AEP passes it: the identifier or, without one, the WKT2 captured
        # here, never the project the worker would read later (it may have changed).
        project_crs_authid=crs_authid or crs_wkt or None,
        without_blockage=bool(without_blockage),
        aep_comparison={"last_aep_available": bool(last_aep_available),
                        "same_inputs_as_last_aep": (not changed_aep_inputs) if last_aep_available else None,
                        "changed_inputs": list(changed_aep_inputs or [])},
    )

    # QgsProject is a singleton; comparing instance() before and after a task cannot
    # detect that QGIS has opened/cleared a different project in the meantime.
    # Capture an invalidation signal instead. Never use the completed raster in a
    # project that has been cleared or replaced while the task was running.
    source_project = QgsProject.instance()
    source_project_changed = False

    def _invalidate_project(*_args: Any) -> None:
        nonlocal source_project_changed
        source_project_changed = True

    connected_signals = []
    for signal_name in ("cleared", "readProject"):
        signal = getattr(source_project, signal_name, None)
        if signal is not None:
            signal.connect(_invalidate_project)
            connected_signals.append(signal)

    def _disconnect_project_signals() -> None:
        for signal in connected_signals:
            try:
                signal.disconnect(_invalidate_project)
            except (RuntimeError, TypeError):
                pass

    dialog._wake_raster_task_finished = False
    _set_button_running(dialog, True, 0.0)

    def _on_progress(value: float) -> None:
        if _dialog_is_alive(dialog):
            _set_button_running(dialog, True, value)

    def _on_finished(ok: bool, result: Dict[str, Any], error: Optional[str]) -> None:
        _disconnect_project_signals()
        dialog_alive = _dialog_is_alive(dialog)
        parent = dialog if dialog_alive else None
        if dialog_alive:
            dialog._wake_raster_task_finished = True
            dialog._wake_raster_task = None
            _set_button_running(dialog, False)

        if not ok:
            if error and "cancel" in error.lower():
                _message_bar(
                    tr_text("Estelas"),
                    tr_text("Se canceló la creación del ráster de estelas."),
                    Qgis.Info,
                    6,
                )
            else:
                error = error_text(result, error)
                QtWidgets.QMessageBox.critical(
                    parent,
                    tr_text("Error de ráster de estelas"),
                    tr_text("No se pudo crear el ráster de estelas:\n{error}").format(
                        error=error or tr_text("Error desconocido.")
                    ),
                )
            return

        if source_project_changed or QgsProject.instance() is not source_project:
            # Keep the GeoTIFF(s) and metadata: a project switch must not destroy
            # a successful computation, nor import it into the newly opened project.
            path = str((result or {}).get("path") or "")
            saved_at = os.path.dirname(path) if path else output_dir
            QtWidgets.QMessageBox.warning(
                parent,
                tr_text("Ráster de estelas no cargado"),
                tr_text(
                    "El proyecto cambió durante el cálculo del ráster de estelas. "
                    "No se han añadido capas al proyecto actual. "
                    "Los archivos generados se conservan en:\n{path}"
                ).format(path=saved_at),
            )
            return

        try:
            layers = add_wake_raster_result_to_qgis(result)
            for layer in (layers if isinstance(layers, (list, tuple)) else [layers]):
                if layer is not None:
                    _refresh_canvas(layer)
        except Exception as exc:
            QtWidgets.QMessageBox.critical(
                parent,
                tr_text("Carga del ráster"),
                tr_text("El GeoTIFF se creó, pero QGIS no pudo cargarlo:\n{error}\n\nArchivo: {path}").format(
                    error=exc, path=result.get("path", "")
                ),
            )
            return

        # El motor guarda cada aviso como plantilla y datos: se traduce la plantilla, no los datos.
        warnings = [
            tr_text(template).format(**{key: shown(value, tr_text) for key, value in data.items()})
            for template, data in (result.get("warning_items") or [])
        ]
        density_summary = (result.get("air_density") or {}).get("summary")
        density_text = (
            tr_text("Densidad del aire:") + f" {shown(density_summary, tr_text)}\n" if density_summary else ""
        )
        if changed_aep_inputs:
            warnings.insert(0, tr_text(
                "El ráster se ha calculado con las entradas actuales del diálogo, que difieren del último AEP en: "
                "{categories}. Vuelve a calcular el AEP para que el informe corresponda al mapa."
            ).format(categories=", ".join(tr_text(label) for label in changed_aep_inputs)))
        warning_text = ""
        if warnings:
            warning_text = "\n\n" + tr_text("Avisos:") + "\n• " + "\n• ".join(warnings)

        metadata_path = str(result.get("metadata_path") or "")
        # Without the free flow of PyWake there is no range to show (#75, row 5.7): «n/d», never the reference speed.
        if result.get("free_flow_min_ws") is None or result.get("free_flow_max_ws") is None:
            free_range = " " + tr_text("n/d") + "\n"
        else:
            free_range = f" {float(result['free_flow_min_ws']):.2f}–{float(result['free_flow_max_ws']):.2f} m/s\n"
        # A layer of effective speed without finite cells has no statistics (#63, decision 7): «n/d», never 0.
        if result.get("min_ws") is None or result.get("max_ws") is None:
            effective_range = effective_mean = " " + tr_text("n/d") + "\n"
        else:
            effective_range = f" {float(result['min_ws']):.2f}–{float(result['max_ws']):.2f} m/s\n"
            effective_mean = f" {float(result.get('mean_ws', 0.0)):.2f} / {float(result.get('p50_ws', 0.0)):.2f} m/s\n"
        product = (tr_text(str(result.get("product"))) + "\n") if result.get("without_blockage") else ""
        QtWidgets.QMessageBox.information(
            parent,
            tr_text("Ráster de estelas creado"),
            tr_text("Las capas de flujo libre, velocidad efectiva y déficit, junto con el terreno cuando está disponible, se han añadido al grupo ‘{group}’.").format(group="VelantisWind · Estelas")
            + "\n\n"
            + product
            + tr_text("Dirección usada:")
            + f" {float(result.get('wd', 0.0)):.1f}°\n"
            + tr_text("Velocidad de referencia:")
            + f" {float(result.get('ws', 0.0)):.1f} m/s\n"
            + tr_text("Rango WS libre:")
            + free_range
            + tr_text("Rango WS efectiva:")
            + effective_range
            + tr_text("Media / P50:")
            + effective_mean
            + tr_text("Turbinas usadas:")
            + f" {int(result.get('turbines_used', 0))}/{int(result.get('turbines_total', 0))}\n"
            + density_text
            + tr_text("Metadatos de trazabilidad:")
            + f" {metadata_path or os.path.splitext(str(result.get('path') or ''))[0] + '.json'}"
            + warning_text,
        )

    try:
        task = start_wake_raster_task(
            config,
            description=tr_text("Velantis Wind · Ráster de estelas"),
            on_finished=_on_finished,
            on_progress=_on_progress,
        )
    except Exception:
        _disconnect_project_signals()
        dialog._wake_raster_task_finished = True
        _set_button_running(dialog, False)
        raise
    dialog._wake_raster_task = task
    _message_bar(
        tr_text("Estelas"),
        tr_text("El ráster se está calculando en segundo plano. Puedes seguir trabajando en QGIS y cancelarlo desde el gestor de tareas."),
        Qgis.Info,
        8,
    )
    return task

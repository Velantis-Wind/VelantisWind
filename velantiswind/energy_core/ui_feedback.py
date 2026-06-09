# -*- coding: utf-8 -*-
"""Utilidades de feedback visual para el módulo Energy/AEP."""

from __future__ import annotations

from typing import Any, Callable, Optional

from qgis.PyQt import QtWidgets, QtCore
from qgis.core import Qgis
from qgis.utils import iface


def qgis_level_from_severity(severity: str) -> Any:
    severity_norm = str(severity or "info").lower()
    if severity_norm in ("warning", "warn", "aviso"):
        return Qgis.Warning
    if severity_norm in ("success", "ok"):
        return Qgis.Success
    if severity_norm in ("critical", "error"):
        return Qgis.Critical
    return Qgis.Info


def show_message_bar(title: str, message: str, level: Any = None, duration: int = 8) -> None:
    """Muestra un mensaje en la barra de QGIS, ignorando fallos de entorno."""
    try:
        iface.messageBar().pushMessage(
            str(title or "AEP"),
            str(message),
            level=level if level is not None else Qgis.Info,
            duration=int(duration),
        )
    except Exception:
        pass


def show_user_warning(parent: Any, title: str, message: str) -> None:
    QtWidgets.QMessageBox.warning(parent, str(title or "AEP"), str(message))


def show_user_critical(parent: Any, title: str, message: str) -> None:
    QtWidgets.QMessageBox.critical(parent, str(title or "AEP"), str(message))


def create_progress_dialog(parent: Any, title: str = "Calculando AEP", label: str = "Inicializando cálculo…") -> Any:
    progress_dlg = QtWidgets.QProgressDialog(str(label), "Cancelar", 0, 100, parent)
    progress_dlg.setWindowTitle(str(title))
    progress_dlg.setWindowModality(QtCore.Qt.WindowModal)
    progress_dlg.setMinimumDuration(0)
    progress_dlg.setAutoClose(True)
    progress_dlg.setAutoReset(False)
    try:
        # Cancel real requeriría ejecución en thread/task. Se oculta para no dar
        # una falsa sensación de cancelación mientras PyWake corre en primer plano.
        progress_dlg.setCancelButton(None)
    except Exception:
        pass
    progress_dlg.setValue(0)
    progress_dlg.show()
    QtWidgets.QApplication.processEvents()
    return progress_dlg


def make_progress_callback(progress_dlg: Any) -> Callable[[int, str], None]:
    def _on_progress(value: int, message: str) -> None:
        try:
            progress_dlg.setValue(int(value))
            progress_dlg.setLabelText(str(message))
            QtWidgets.QApplication.processEvents()
        except Exception:
            pass

    return _on_progress


def close_progress_dialog(progress_dlg: Optional[Any], value: Optional[int] = None) -> None:
    try:
        if progress_dlg is None:
            return
        if value is not None:
            progress_dlg.setValue(int(value))
        progress_dlg.close()
    except Exception:
        pass

# -*- coding: utf-8 -*-
"""Small UI feedback helpers for the Noise module.

This module centralises progress bars, message-bar notifications and status-box
updates so the main controller can focus on workflow decisions.
"""
from __future__ import annotations

import time

from qgis.PyQt import QtCore, QtWidgets


_QT_PROCESS_EVENTS_ACTIVE = False
_LAST_QT_PROCESS_EVENTS_MS = 0.0


def _safe_qt_process_events(min_interval_ms: int = 150) -> None:
    """Process Qt events without allowing recursive progress-slot re-entry.

    Some QGIS/Qt builds can re-enter the progressChanged slot while
    QApplication.processEvents() is already running. In the noise workflow this
    may recurse through _set_dialog_progress() until Windows raises a stack
    overflow and QGIS closes. The guard keeps the UI responsive but prevents
    nested event-loop calls.
    """
    global _QT_PROCESS_EVENTS_ACTIVE, _LAST_QT_PROCESS_EVENTS_MS
    if _QT_PROCESS_EVENTS_ACTIVE:
        return
    try:
        now_ms = time.monotonic() * 1000.0
        if min_interval_ms > 0 and (now_ms - _LAST_QT_PROCESS_EVENTS_MS) < float(min_interval_ms):
            return
        _QT_PROCESS_EVENTS_ACTIVE = True
        _LAST_QT_PROCESS_EVENTS_MS = now_ms
        try:
            QtWidgets.QApplication.processEvents(QtCore.QEventLoop.ExcludeUserInputEvents)
        except TypeError:
            QtWidgets.QApplication.processEvents()
    except Exception:
        pass
    finally:
        _QT_PROCESS_EVENTS_ACTIVE = False

def _show_task_progress_dialog(dialog, title: str, label: str, cancel_callback=None):
    """Show a small floating progress dialog tied to a QgsTask.

    The inline progress bar can be hidden by scroll/layout constraints on small
    screens. This floating dialog makes the heavy background calculation visible
    in the same spirit as the shadow/flicker raster task.
    """
    try:
        dlg = QtWidgets.QProgressDialog(str(label), "Cancelar", 0, 100, dialog)
        dlg.setWindowTitle(str(title))
        dlg.setWindowModality(QtCore.Qt.NonModal)
        dlg.setAutoClose(False)
        dlg.setAutoReset(False)
        dlg.setMinimumDuration(0)
        dlg.setValue(0)
        if cancel_callback is not None:
            try:
                dlg.canceled.connect(cancel_callback)
            except Exception:
                pass
        dlg.show()
        _safe_qt_process_events()
        return dlg
    except Exception:
        return None


def _update_task_progress_dialog(progress_dlg, label: str, value: float) -> None:
    try:
        if progress_dlg is None:
            return
        v = max(0, min(100, int(round(float(value)))))
        progress_dlg.setLabelText(str(label))
        progress_dlg.setValue(v)
        _safe_qt_process_events()
    except Exception:
        pass


def _close_task_progress_dialog(progress_dlg, value: int = 100) -> None:
    try:
        if progress_dlg is None:
            return
        progress_dlg.setValue(int(value))
        progress_dlg.close()
        progress_dlg.deleteLater()
    except Exception:
        pass

def _append_status_line(dialog, text: str) -> None:
    try:
        current = dialog.txt_status.toPlainText().rstrip()
        dialog.txt_status.setPlainText((current + "\n" + text).strip())
    except Exception:
        pass


def _notify_qgis(title: str, message: str, level_name: str = "Info") -> None:
    try:
        from qgis.utils import iface
        from qgis.core import Qgis
        if iface is None:
            return
        level = getattr(Qgis, level_name, Qgis.Info)
        iface.messageBar().pushMessage(title, message, level, duration=6)
    except Exception:
        pass


def _set_dialog_busy(dialog, text: str) -> None:
    """Show an indeterminate progress bar in the Noise page."""
    try:
        lbl = getattr(dialog, "lbl_noise_progress", None)
        pb = getattr(dialog, "pb_noise_progress", None)
        if lbl is not None:
            lbl.setText(str(text))
            lbl.setVisible(True)
        if pb is not None:
            pb.setVisible(True)
            pb.setRange(0, 0)
            pb.setFormat("")
        _safe_qt_process_events()
    except Exception:
        pass


def _set_dialog_progress(dialog, text: str, value: float) -> None:
    """Show a determinate progress bar in the Noise page."""
    try:
        value = max(0.0, min(100.0, float(value)))
        lbl = getattr(dialog, "lbl_noise_progress", None)
        pb = getattr(dialog, "pb_noise_progress", None)
        if lbl is not None:
            lbl.setText(str(text))
            lbl.setVisible(True)
        if pb is not None:
            pb.setVisible(True)
            pb.setRange(0, 100)
            pb.setFormat("%p%")
            pb.setValue(int(round(value)))
        _safe_qt_process_events()
    except Exception:
        pass


def _hide_dialog_progress(dialog) -> None:
    try:
        pb = getattr(dialog, "pb_noise_progress", None)
        lbl = getattr(dialog, "lbl_noise_progress", None)
        if pb is not None:
            pb.setRange(0, 100)
            pb.setValue(0)
            pb.setVisible(False)
        if lbl is not None:
            lbl.setVisible(False)
    except Exception:
        pass


def _finish_dialog_progress(dialog, text: str, *, hide_after_ms: int = 3500) -> None:
    try:
        _set_dialog_progress(dialog, text, 100.0)
        QtCore.QTimer.singleShot(int(hide_after_ms), lambda: _hide_dialog_progress(dialog))
    except Exception:
        pass


def _set_calculate_enabled(dialog, enabled: bool) -> None:
    try:
        btn = getattr(dialog, "btn_calc", None)
        if btn is not None:
            btn.setEnabled(bool(enabled))
    except Exception:
        pass

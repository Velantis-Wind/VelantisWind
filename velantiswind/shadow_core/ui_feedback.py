# -*- coding: utf-8 -*-
"""Small UI feedback helpers for the shadow-flicker controller."""

from __future__ import annotations

from qgis.PyQt import QtWidgets


def inform_calculation_already_running(dialog) -> None:
    QtWidgets.QMessageBox.information(
        dialog,
        "Shadow calculation running",
        "A shadow-flicker calculation is already running.",
    )


def show_validation_errors(dialog, errors) -> None:
    message = "Cannot start the shadow-flicker calculation:\n\n" + "\n".join(f"• {e}" for e in errors)
    if hasattr(dialog, "txt_status"):
        dialog.txt_status.setText(message)
    QtWidgets.QMessageBox.warning(dialog, "Invalid shadow configuration", message)


def set_shadow_calculation_running(dialog, running: bool, *, old_enabled=None) -> None:
    if hasattr(dialog, "btn_calc"):
        if running:
            dialog.btn_calc.setEnabled(False)
        else:
            dialog.btn_calc.setEnabled(bool(old_enabled) if old_enabled is not None else True)
    dialog._shadow_calculation_running = bool(running)


def show_shadow_starting_status(dialog) -> None:
    if hasattr(dialog, "txt_status"):
        dialog.txt_status.setText("Starting shadow-flicker calculation...")

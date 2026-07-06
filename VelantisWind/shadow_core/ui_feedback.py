# -*- coding: utf-8 -*-
"""Small UI feedback helpers for the shadow-flicker controller."""

from __future__ import annotations

from qgis.PyQt import QtWidgets

from .i18n_local import tr4 as _ml


def inform_calculation_already_running(dialog) -> None:
    QtWidgets.QMessageBox.information(
        dialog,
        _ml("Cálculo de sombras en curso", "Shadow calculation running", "Calcul d’ombres en cours", "Schattenwurfberechnung läuft"),
        _ml(
            "Ya hay un cálculo de sombras y parpadeo en curso.",
            "A shadow flicker calculation is already running.",
            "Un calcul d’ombres et scintillement est déjà en cours.",
            "Eine Schattenwurfberechnung läuft bereits.",
        ),
    )


def show_validation_errors(dialog, errors) -> None:
    message = _ml(
        "No se puede iniciar el cálculo de sombras y parpadeo:\n\n",
        "The shadow flicker calculation cannot be started:\n\n",
        "Impossible de démarrer le calcul d’ombres et scintillement :\n\n",
        "Die Schattenwurfberechnung kann nicht gestartet werden:\n\n",
    ) + "\n".join(f"• {e}" for e in errors)
    title = _ml(
        "Configuración de sombras no válida",
        "Invalid shadow configuration",
        "Configuration d’ombres non valide",
        "Ungültige Schattenwurfkonfiguration",
    )
    if hasattr(dialog, "txt_status"):
        dialog.txt_status.setText(message)
    QtWidgets.QMessageBox.warning(dialog, title, message)


def set_shadow_calculation_running(dialog, running: bool, *, old_enabled=None) -> None:
    if hasattr(dialog, "btn_calc"):
        if running:
            dialog.btn_calc.setEnabled(False)
        else:
            dialog.btn_calc.setEnabled(bool(old_enabled) if old_enabled is not None else True)
    dialog._shadow_calculation_running = bool(running)


def show_shadow_starting_status(dialog) -> None:
    if hasattr(dialog, "txt_status"):
        dialog.txt_status.setText(
            _ml(
                "Iniciando cálculo de sombras y parpadeo…",
                "Starting shadow flicker calculation…",
                "Démarrage du calcul d’ombres et scintillement…",
                "Schattenwurfberechnung wird gestartet…",
            )
        )

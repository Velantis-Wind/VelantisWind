# -*- coding: utf-8 -*-
"""Small UI feedback helpers for the shadow-flicker controller."""

from __future__ import annotations

from qgis.PyQt import QtWidgets
try:
    from ..i18n import current_language
except Exception:
    try:
        from VelantisWind.i18n import current_language
    except Exception:
        def current_language(): return "fr"

def _is_de():
    return str(current_language()).lower().startswith("de")


def inform_calculation_already_running(dialog) -> None:
    QtWidgets.QMessageBox.information(
        dialog,
        "Schattenwurfberechnung läuft" if _is_de() else "Calcul d’ombres en cours",
        "Eine Schattenwurfberechnung läuft bereits." if _is_de() else "Un calcul d’ombres et scintillement est déjà en cours.",
    )


def show_validation_errors(dialog, errors) -> None:
    if _is_de():
        message = "Die Schattenwurfberechnung kann nicht gestartet werden:\n\n" + "\n".join(f"• {e}" for e in errors)
        title = "Ungültige Schattenwurfkonfiguration"
    else:
        message = ("Schattenwurfberechnung konnte nicht gestartet werden:\n\n" if _is_de() else "Impossible de démarrer le calcul d’ombres et scintillement :\n\n") + "\n".join(f"• {e}" for e in errors)
        title = "Configuration d’ombres non valide"
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
        dialog.txt_status.setText("Schattenwurfberechnung wird gestartet…" if _is_de() else "Démarrage du calcul d’ombres et scintillement…")

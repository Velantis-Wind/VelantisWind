# -*- coding: utf-8 -*-
"""Controller layer for the shadow-flicker dialog/page."""

from __future__ import annotations

from .dialog_state import read_shadow_run_config_from_dialog
from .runner import ShadowRunner
from .ui_feedback import (
    inform_calculation_already_running,
    set_shadow_calculation_running,
    show_shadow_starting_status,
    show_validation_errors,
)
from .validation import validate_shadow_run_config


def run_shadow_calculation_from_dialog(dialog):
    """Validate and execute the shadow-flicker calculation requested by the UI."""

    if bool(getattr(dialog, "_shadow_calculation_running", False)):
        inform_calculation_already_running(dialog)
        return None

    config = read_shadow_run_config_from_dialog(dialog)
    errors = validate_shadow_run_config(config)
    if errors:
        show_validation_errors(dialog, errors)
        return None

    old_enabled = None
    if hasattr(dialog, "btn_calc"):
        old_enabled = dialog.btn_calc.isEnabled()

    set_shadow_calculation_running(dialog, True)
    show_shadow_starting_status(dialog)

    try:
        return ShadowRunner().run_from_dialog(dialog, config)
    finally:
        set_shadow_calculation_running(dialog, False, old_enabled=old_enabled)

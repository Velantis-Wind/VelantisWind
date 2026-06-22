# -*- coding: utf-8 -*-
"""Receiver calculation executor for the shadow-flicker module.

This module contains the execution strategy that used to live inside
``shadow_page.py`` / ``point_runner.py``: sequential calculation with
progress-dialog updates. The former multiprocessing parallel mode was removed.

The numerical physics is intentionally unchanged.  The executor only calls the
existing ``ShadowFlickerCalculator.calculate_for_receptor`` method.
"""

from __future__ import annotations

from ..debug import debug_print

import traceback
from typing import Any, Dict, Iterable, List, Optional

from qgis.PyQt import QtWidgets


def _is_de() -> bool:
    try:
        from ...i18n import current_language  # type: ignore
    except Exception:
        try:
            from ..i18n import current_language  # type: ignore
        except Exception:
            try:
                from i18n import current_language  # type: ignore
            except Exception:
                return False
    try:
        return str(current_language()).lower().startswith("de")
    except Exception:
        return False



def _process_events() -> None:
    """Keep the UI responsive while preserving the current synchronous flow."""
    try:
        QtWidgets.QApplication.processEvents()
    except Exception:
        pass


def _was_cancelled(progress_dialog: Any) -> bool:
    try:
        return bool(progress_dialog is not None and progress_dialog.wasCanceled())
    except Exception:
        return False


def _set_progress(progress_dialog: Any, value: int, label: Optional[str] = None) -> None:
    if progress_dialog is None:
        return
    try:
        if label is not None:
            progress_dialog.setLabelText(label)
        progress_dialog.setValue(max(0, min(100, int(value))))
    except Exception:
        pass
    _process_events()


def _calculate_sequential(
    *,
    calculator: Any,
    receptors: List[Dict[str, Any]],
    turbines: List[Dict[str, Any]],
    progress_dialog: Any,
    label_suffix: str = "",
    use_fine_progress: bool = True,
) -> Optional[List[Any]]:
    """Run the sequential receptor calculation."""
    total_receptors = len(receptors)
    results: List[Any] = []

    if total_receptors <= 0:
        return results

    debug_print(f"[Shadow] Starting calculation SEQUENTIAL for {total_receptors} receivers with {len(turbines)} turbines")

    for i, receptor in enumerate(receptors):
        if _was_cancelled(progress_dialog):
            return None

        progress_pct = int(100 * i / total_receptors)
        suffix = f"\n{label_suffix}" if label_suffix else (f"\n{len(turbines)} Windturbine(n) · 365 Tage" if _is_de() else f"\n{len(turbines)} éolienne(s) · 365 jours")
        _set_progress(
            progress_dialog,
            progress_pct,
            (f"Berechnung Rezeptor {i+1}/{total_receptors}: {receptor['name']}{suffix}" if _is_de() else f"Calcul du récepteur {i+1}/{total_receptors} : {receptor['name']}{suffix}"),
        )

        debug_print(f"[Shadow] Receptor {i+1}/{total_receptors}: {receptor['name']} - Starting calculation...")

        def callback(prog, msg):
            if _was_cancelled(progress_dialog):
                raise InterruptedError("Berechnung durch den Benutzer abgebrochen" if _is_de() else "Calcul annulé par l’utilisateur")
            if use_fine_progress:
                receptor_progress = progress_pct + int((100 / total_receptors) * float(prog))
                _set_progress(progress_dialog, min(99, receptor_progress))

        try:
            result = calculator.calculate_for_receptor(
                receptor_x=receptor['x'],
                receptor_y=receptor['y'],
                receptor_z=receptor['z'],
                receptor_name=receptor['name'],
                turbines=turbines,
                callback=callback if use_fine_progress else None,
                receptor_ground_elev=float(receptor.get('ground_elev', 0.0)),
            )
            result.feat_id = receptor['feat_id']
            results.append(result)
            debug_print(
                f"[Shadow] Receptor {i+1}/{total_receptors}: {receptor['name']} - "
                f"Completed ({result.hours_per_year_astronomical:.1f}h/year)"
            )
        except Exception as e:
            debug_print(f"[Shadow] ERROR in receiver {receptor['name']}: {e}")
            traceback.print_exc()
            raise

    return results


def execute_shadow_receptor_calculations(
    *,
    calculator: Any,
    receptors: List[Dict[str, Any]],
    turbines: List[Dict[str, Any]],
    latitude: float,
    longitude: float,
    year: int,
    timezone_offset: float,
    min_sun_elevation: float,
    max_sun_elevation: float,
    time_step_minutes: int,
    turbine_availability: float,
    max_shadow_distance_m: float,
    timezone_mode: str,
    timezone_name: Optional[str],
    use_parallel: bool,
    num_workers: int,
    progress_dialog: Any,
) -> Optional[List[Any]]:
    """Execute the point-receptor shadow calculation.

    Returns:
        list of ``ShadowFlickerResult`` objects, or ``None`` if the user cancels.

    The calculation always runs sequentially. The former multiprocessing
    parallel mode has been removed.
    """
    total_receptors = len(receptors)
    if total_receptors <= 0:
        return []

    return _calculate_sequential(
        calculator=calculator,
        receptors=receptors,
        turbines=turbines,
        progress_dialog=progress_dialog,
        use_fine_progress=True,
    )

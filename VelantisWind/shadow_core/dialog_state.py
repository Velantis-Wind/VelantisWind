# -*- coding: utf-8 -*-
"""Read shadow-flicker dialog state into domain objects.

This module is the only place where the controller reads Qt widgets to build
a :class:`ShadowRunConfig`. Keeping this separate makes ``domain.py`` a pure
dataclass module and mirrors the Energy/Noise architecture.
"""

from __future__ import annotations

from .domain import ShadowRunConfig


def _combo_data(combo):
    try:
        return combo.currentData()
    except Exception:
        return None


def read_shadow_run_config_from_dialog(dialog) -> ShadowRunConfig:
    """Build a shadow-flicker run configuration from the current UI state."""

    return ShadowRunConfig(
        turbine_layer_id=str(_combo_data(dialog.cb_turbines) or ""),
        receiver_layer_id=str(_combo_data(dialog.cb_receivers) or ""),
        dem_layer_id=str(_combo_data(dialog.cb_dem) or "") or None,
        latitude=float(dialog.sp_latitude.value()),
        longitude=float(dialog.sp_longitude.value()),
        year=int(dialog.sp_year.value()),
        timezone_mode=str(dialog.cb_timezone_mode.currentData() or "fixed"),
        timezone_name=str(dialog.cb_timezone_name.currentText()).strip() or "UTC",
        timezone_offset=float(dialog.sp_timezone.value()),
        observer_height_m=float(dialog.sp_observer_height.value()),
        max_shadow_distance_m=float(dialog.sp_max_shadow_distance.value()),
        time_step_minutes=int(dialog.sp_time_step.value()),
        min_sun_elevation_deg=float(dialog.sp_min_elevation.value()),
        max_sun_elevation_deg=float(dialog.sp_max_elevation.value()),
        turbine_availability=float(dialog.sp_availability.value()),
        use_parallel=False,  # receiver calculation is intentionally sequential for stability
        num_workers=1,
        create_raster=bool(dialog.chk_create_raster.isChecked()),
        raster_resolution_m=int(dialog.sp_raster_resolution.value()),
        raster_timestep_minutes=int(dialog.sp_raster_timestep.value()),
    )

# -*- coding: utf-8 -*-
"""Domain objects for the shadow-flicker module.

These dataclasses keep the calculation configuration independent from the
Qt widgets.  The domain layer gives the UI/controller a stable, typed object to pass
into the shadow/flicker runner.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class ShadowRunConfig:
    """Configuration for one shadow-flicker calculation run."""

    turbine_layer_id: str
    receiver_layer_id: str
    dem_layer_id: Optional[str]
    latitude: float
    longitude: float
    year: int
    timezone_mode: str
    timezone_name: str
    timezone_offset: float
    observer_height_m: float
    max_shadow_distance_m: float
    time_step_minutes: int
    min_sun_elevation_deg: float
    max_sun_elevation_deg: float
    turbine_availability: float
    use_parallel: bool
    num_workers: int
    create_raster: bool
    raster_resolution_m: int
    raster_timestep_minutes: int

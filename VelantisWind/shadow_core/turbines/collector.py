# -*- coding: utf-8 -*-
"""Collect turbine inputs for shadow-flicker calculations."""

from __future__ import annotations

from ..debug import debug_print

from typing import Callable, Dict, List, Tuple


def collect_shadow_turbines(
    turbine_layer,
    hub_height: float,
    rotor_diameter: float,
    sample_ground_elev: Callable[[float, float], float],
    dem_enabled: bool = False,
) -> Tuple[List[Dict[str, object]], int]:
    """Read turbine point features into pure dictionaries.

    Returns ``(turbines, n_offdem)``.  The dictionaries keep the field names used
    by the point-receptor engine to preserve behavior.
    """
    turbines: List[Dict[str, object]] = []
    model_name = turbine_layer.name()
    n_offdem = 0

    for feat in turbine_layer.getFeatures():
        geom = feat.geometry()
        if not geom or geom.isNull():
            continue
        pt = geom.asPoint()
        ground_elev = float(sample_ground_elev(pt.x(), pt.y()))
        if dem_enabled and ground_elev == 0.0:
            n_offdem += 1
        turbines.append(
            {
                "x": pt.x(),
                "y": pt.y(),
                "hub_height": float(hub_height),
                "ground_elev": ground_elev,
                "rotor_diameter": float(rotor_diameter),
                "name": f"{model_name}_{feat.id()}",
            }
        )

    return turbines, n_offdem


def log_turbine_dem_summary(turbines: List[Dict[str, object]], n_offdem: int) -> None:
    """Print the same DEM-sampling summary used by the Shadow UI code."""
    if not turbines:
        return
    elevs = [float(t.get("ground_elev", 0.0)) for t in turbines]
    debug_print(
        f"[Shadow] DEM-sampled turbine ground elevations: "
        f"min={min(elevs):.1f}m, max={max(elevs):.1f}m, "
        f"span={max(elevs)-min(elevs):.1f}m"
    )
    if n_offdem > 0:
        debug_print(
            f"[Shadow] WARNING: {n_offdem}/{len(turbines)} turbines returned 0 m "
            f"from DEM (possible no-data / outside coverage)"
        )

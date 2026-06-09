# -*- coding: utf-8 -*-
"""Collect receptor inputs for shadow-flicker calculations."""

from __future__ import annotations

from ..debug import debug_print

from typing import Callable, Dict, List, Tuple


def _safe_name(feat) -> str:
    try:
        name = feat.attribute("name")
    except Exception:
        name = None
    return str(name) if name else f"R{feat.id()}"


def collect_shadow_receptors(
    receiver_layer,
    observer_height: float,
    sample_ground_elev: Callable[[float, float], float],
    dem_enabled: bool = False,
) -> Tuple[List[Dict[str, object]], int]:
    """Read point receptors into pure dictionaries.

    Returns ``(receptors, n_offdem)``.  Field names are kept compatible with the
    existing shadow calculator.
    """
    receptors: List[Dict[str, object]] = []
    n_offdem = 0

    for feat in receiver_layer.getFeatures():
        geom = feat.geometry()
        if not geom or geom.isNull():
            continue
        pt = geom.asPoint()
        ground_elev = float(sample_ground_elev(pt.x(), pt.y()))
        if dem_enabled and ground_elev == 0.0:
            n_offdem += 1
        receptors.append(
            {
                "x": pt.x(),
                "y": pt.y(),
                "z": float(observer_height),
                "ground_elev": ground_elev,
                "name": _safe_name(feat),
                "feat_id": feat.id(),
            }
        )

    return receptors, n_offdem


def log_receptor_dem_summary(receptors: List[Dict[str, object]], n_offdem: int) -> None:
    """Print the same receptor DEM summary used by the Shadow UI code."""
    if not receptors:
        return
    elevs = [float(r.get("ground_elev", 0.0)) for r in receptors]
    debug_print(
        f"[Shadow] DEM-sampled receptor ground elevations: "
        f"min={min(elevs):.1f}m, max={max(elevs):.1f}m, "
        f"span={max(elevs)-min(elevs):.1f}m"
    )
    if n_offdem > 0:
        debug_print(
            f"[Shadow] WARNING: {n_offdem}/{len(receptors)} receptors returned 0 m "
            f"from DEM (possible no-data / outside coverage)"
        )

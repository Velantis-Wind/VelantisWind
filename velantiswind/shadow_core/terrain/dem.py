# -*- coding: utf-8 -*-
"""DEM/DSM helpers for shadow-flicker calculations.

These helpers keep terrain sampling out of the UI/runner workflow while
preserving the previous calculation semantics: missing DEM, no-data, CRS
errors or provider errors fall back to flat terrain (0.0 m).
"""

from __future__ import annotations

from ..debug import debug_print

from typing import Callable, Optional, Tuple

from qgis.core import (
    QgsCoordinateTransform,
    QgsPointXY,
    QgsProject,
    QgsRasterLayer,
    QgsCoordinateReferenceSystem,
)


def resolve_dem_layer(project: QgsProject, dem_layer_id: Optional[str]) -> Tuple[Optional[QgsRasterLayer], object]:
    """Return ``(dem_layer, provider)`` for a configured DEM/DSM layer.

    If the layer is absent or invalid, returns ``(None, None)`` and leaves the
    calculation in flat-terrain mode.
    """
    if not dem_layer_id:
        debug_print("[Shadow] No DEM selected - flat terrain assumed (z=0)")
        return None, None

    dem_layer = project.mapLayer(dem_layer_id)
    if dem_layer is not None and isinstance(dem_layer, QgsRasterLayer):
        try:
            provider = dem_layer.dataProvider()
        except Exception:
            provider = None
        if provider is not None:
            debug_print(
                f"[Shadow] DEM enabled: '{dem_layer.name()}' "
                f"(CRS {dem_layer.crs().authid()}, band 1)"
            )
            return dem_layer, provider

    debug_print("[Shadow] WARNING: DEM layer id set but layer not found - falling back to flat terrain")
    return None, None


def make_dem_sampler(
    source_crs: QgsCoordinateReferenceSystem,
    dem_layer: Optional[QgsRasterLayer],
    dem_provider,
) -> Callable[[float, float], float]:
    """Build a DEM sampler closure for points in ``source_crs``.

    The returned callable matches the current behavior: any failed transform,
    provider sample, no-data or NaN returns 0.0 m.
    """
    if dem_provider is None or dem_layer is None:
        return lambda x, y: 0.0

    xform = None
    if source_crs != dem_layer.crs():
        try:
            xform = QgsCoordinateTransform(source_crs, dem_layer.crs(), QgsProject.instance())
        except Exception as e:
            debug_print(
                f"[Shadow] WARNING: failed to build CRS transform "
                f"({source_crs.authid()} → {dem_layer.crs().authid()}): {e}"
            )
            xform = None

    def _sampler(x, y):
        pt = QgsPointXY(float(x), float(y))
        if xform is not None:
            try:
                pt = xform.transform(pt)
            except Exception:
                return 0.0
        try:
            val, ok = dem_provider.sample(pt, 1)
        except Exception:
            return 0.0
        if not ok:
            return 0.0
        try:
            fval = float(val)
        except (TypeError, ValueError):
            return 0.0
        if fval != fval:  # NaN guard
            return 0.0
        return fval

    return _sampler

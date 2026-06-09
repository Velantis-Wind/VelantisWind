# -*- coding: utf-8 -*-
"""Common QGIS helpers for the noise module."""
from __future__ import annotations

import os
import tempfile
import math
from typing import List, Dict, Optional
from qgis.core import QgsCoordinateReferenceSystem, QgsPointXY, QgsRasterLayer, QgsProject

def _unique_temp_output(tmpdir: str, layer_name: str, suffix: str) -> str:
    os.makedirs(tmpdir, exist_ok=True)
    safe = ''.join(c if c.isalnum() or c in ('_', '-') else '_' for c in (layer_name or 'output'))
    # Use a unique filename on every run to avoid Windows file locks when QGIS still has
    # previous outputs loaded in the project.
    fd, path = tempfile.mkstemp(prefix=f"{safe}_", suffix=suffix, dir=tmpdir)
    os.close(fd)
    try:
        os.remove(path)
    except Exception:
        pass
    return path
def _iter_provider_nodata_values(provider, band: int = 1):
    """Yield declared no-data values/ranges from a QGIS raster provider.

    QGIS providers are not perfectly consistent across GDAL formats and QGIS
    versions: some expose a single sourceNoDataValue(), others expose user
    no-data ranges, and some return sentinel values through sample(...).  This
    helper keeps DEM sampling conservative for acoustic terrain diagnostics.
    """
    try:
        nodata = provider.sourceNoDataValue(int(band))
        if nodata is not None:
            yield (float(nodata), float(nodata))
    except Exception:
        pass

    try:
        ranges = provider.userNoDataValues(int(band)) or []
    except Exception:
        ranges = []

    for rng in ranges:
        try:
            lo = float(rng.min())
            hi = float(rng.max())
            yield (lo, hi)
            continue
        except Exception:
            pass
        try:
            lo = float(rng.minValue())
            hi = float(rng.maxValue())
            yield (lo, hi)
        except Exception:
            pass


def _is_valid_dem_value(value, provider=None, band: int = 1) -> bool:
    """Return True only for physically plausible, non-NoData DEM samples."""
    if value is None:
        return False
    try:
        z = float(value)
    except Exception:
        return False
    if not math.isfinite(z):
        return False

    # Catch common DEM NoData sentinels even when the provider does not expose
    # them correctly.  Real terrain elevations should never be anywhere close
    # to these magnitudes.
    if abs(z) > 100000.0:
        return False
    for sentinel in (-9999.0, -32768.0, 32767.0, 32768.0, 99999.0):
        if abs(z - sentinel) <= 1e-6:
            return False

    if provider is not None:
        for lo, hi in _iter_provider_nodata_values(provider, band):
            try:
                if not (math.isfinite(lo) and math.isfinite(hi)):
                    continue
                eps = max(1e-6, 1e-9 * max(abs(lo), abs(hi), 1.0))
                if (lo - eps) <= z <= (hi + eps):
                    return False
            except Exception:
                continue
    return True


def _sample_dem(dem_layer: Optional[QgsRasterLayer], x: float, y: float) -> Optional[float]:
    """Sample DEM elevation and return None for NoData/NaN/sentinel values."""
    if dem_layer is None:
        return None
    try:
        provider = dem_layer.dataProvider()
        val, ok = provider.sample(QgsPointXY(float(x), float(y)), 1)
        if ok and _is_valid_dem_value(val, provider, 1):
            return float(val)
    except Exception:
        return None
    return None


def _layer_crs_matches(layer, project_crs: QgsCoordinateReferenceSystem) -> bool:
    try:
        return bool(layer.crs().isValid()) and layer.crs() == project_crs
    except Exception:
        return False


def _set_field_aliases(layer, aliases: Dict[str, str]) -> None:
    try:
        for name, alias in aliases.items():
            idx = layer.fields().indexOf(name)
            if idx >= 0:
                layer.setFieldAlias(idx, alias)
    except Exception:
        pass

def _remove_existing_layers_by_name(prj: QgsProject, names: List[str]) -> None:
    wanted = set(names)
    for lyr in list(prj.mapLayers().values()):
        try:
            if lyr.name() in wanted:
                prj.removeMapLayer(lyr.id())
        except Exception:
            continue

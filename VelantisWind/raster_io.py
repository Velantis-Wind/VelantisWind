# -*- coding: utf-8 -*-
"""Small GDAL raster I/O helpers that avoid the optional ``gdal_array`` bridge.

Some QGIS/OSGeo4W installations can load NumPy and GDAL successfully but still
fail inside ``Band.WriteArray`` with ``TypeError: not a numpy array``.  That
method goes through GDAL's NumPy C extension and is sensitive to binary/API
mismatches between the NumPy runtime and the GDAL bindings.

The helpers below use GDAL's byte-buffer ``WriteRaster`` API instead.  Arrays
are normalised to contiguous Float32 storage first, so the resulting GeoTIFF is
identical without depending on ``gdal_array``.
"""
from __future__ import annotations

from typing import Any, Optional

import numpy as np

try:
    from .ag_core.log_text import log_error
except ImportError:  # imported on its own, outside the plugin package
    from ag_core.log_text import log_error  # type: ignore


def read_float64_pixel(
    band: Any,
    xoff: int,
    yoff: int,
    *,
    gdal_module: Any,
) -> float:
    """Read one GDAL cell without importing or invoking ``gdal_array``."""
    raw = band.ReadRaster(
        int(xoff),
        int(yoff),
        1,
        1,
        buf_xsize=1,
        buf_ysize=1,
        buf_type=gdal_module.GDT_Float64,
    )
    if raw is None:
        raise log_error(RuntimeError, "GDAL no devolvió datos al leer una celda del ráster.")
    values = np.frombuffer(raw, dtype=np.float64, count=1)
    if values.size != 1:
        raise log_error(RuntimeError, "GDAL devolvió un búfer incompleto al leer una celda del ráster.")
    return float(values[0])


def read_float64_band(
    band: Any,
    width: int,
    height: int,
    *,
    gdal_module: Any,
) -> np.ndarray:
    """Read a complete GDAL band through its byte-buffer API."""
    width = int(width)
    height = int(height)
    if width <= 0 or height <= 0:
        raise log_error(ValueError, "La banda del ráster debe tener al menos una celda.")
    raw = band.ReadRaster(
        0,
        0,
        width,
        height,
        buf_xsize=width,
        buf_ysize=height,
        buf_type=gdal_module.GDT_Float64,
    )
    if raw is None:
        raise log_error(RuntimeError, "GDAL no devolvió datos al leer la banda del ráster.")
    values = np.frombuffer(raw, dtype=np.float64, count=width * height)
    if values.size != width * height:
        raise log_error(RuntimeError, "GDAL devolvió un búfer incompleto al leer la banda del ráster.")
    return values.reshape((height, width))


def write_float32_band(
    band: Any,
    array: Any,
    *,
    gdal_module: Any,
    flip_vertical: bool = False,
    nodata: Optional[float] = None,
) -> int:
    """Write a two-dimensional array through GDAL's raw-buffer API.

    Parameters are deliberately explicit so this module does not import GDAL
    itself.  QGIS keeps ownership of the GDAL module used by each caller.
    """
    data = np.asarray(array, dtype=np.float32)
    if data.ndim != 2:
        raise log_error(ValueError, "Se necesita una matriz ráster 2-D; se ha recibido la forma {shape}.",
                        shape=repr(data.shape))
    if flip_vertical:
        data = np.flipud(data)
    data = np.ascontiguousarray(data, dtype=np.float32)

    height, width = (int(data.shape[0]), int(data.shape[1]))
    if width <= 0 or height <= 0:
        raise log_error(ValueError, "La matriz ráster debe tener al menos una celda.")

    result = band.WriteRaster(
        0,
        0,
        width,
        height,
        data.tobytes(order="C"),
        buf_xsize=width,
        buf_ysize=height,
        buf_type=gdal_module.GDT_Float32,
    )
    if result not in (None, 0):
        raise log_error(RuntimeError, "GDAL WriteRaster falló con el código de error {code}.", code=result)
    if nodata is not None:
        band.SetNoDataValue(float(nodata))
    return 0 if result is None else int(result)

# -*- coding: utf-8 -*-
"""Air density at each turbine hub, from a site calibration and the hub altitude.

Turbine power and thrust depend on air density, and each turbine of a wind farm
sits at a different hub altitude, so a single park-wide density biases energy:
it overestimates the turbines above the reference altitude and underestimates
those below it.

The reference is a project input, "density X kg/m³ at altitude Y m above sea
level", never a constant of the code. The vertical profile is the ISA
troposphere law, rescaled so that it reproduces exactly the supplied reference:

    rho(z) = rho_ref * rho_ISA(z) / rho_ISA(z_ref)

This keeps the calibration exact at its own altitude and applies the standard
lapse elsewhere, with no site data beyond the terrain elevation of the resource.

Altitudes here are always *hub* altitudes: terrain elevation at the turbine
position plus its own hub height.

Depends only on numpy: no QGIS, no PyWake (the site object is duck-typed).
"""
from __future__ import annotations

from typing import Any, Optional, Sequence, Tuple

import numpy as np

from ..log_text import log_text
from ..turbine import _error

__all__ = [
    "AirDensityError",
    "SiteAirDensityError",
    "isa_density",
    "calibrated_air_density",
    "air_density_per_turbine",
    "terrain_elevation_from_site",
    "site_has_elevation",
    "site_defines_air_density",
]

# International Standard Atmosphere, troposphere.
ISA_SEA_LEVEL_DENSITY_KG_M3 = 1.225
_ISA_LAPSE_FACTOR = 2.25577e-5   # 1/m
_ISA_EXPONENT = 4.2559

# Plausibility window for a wind-turbine hub altitude. Anything outside points at
# a unit or datum problem (feet read as metres, missing elevation surface, ...)
# rather than at a real site, so it is rejected instead of silently computed.
_MIN_PLAUSIBLE_ALTITUDE_M = -500.0
_MAX_PLAUSIBLE_ALTITUDE_M = 9000.0


class AirDensityError(ValueError):
    """Raised when the air density of each turbine cannot be established reliably."""


class SiteAirDensityError(AirDensityError):
    """The resource defines its own ``Air_density``, which PyWake puts before any other."""


def isa_density(altitude_m: Any) -> Any:
    """ISA troposphere air density [kg/m³] at a geometric altitude [m]."""
    z = np.asarray(altitude_m, dtype=float)
    return ISA_SEA_LEVEL_DENSITY_KG_M3 * np.power(1.0 - _ISA_LAPSE_FACTOR * z, _ISA_EXPONENT)


def _check_altitude_range(altitudes: np.ndarray, label: str) -> None:
    finite = np.isfinite(altitudes)
    if not np.all(finite):
        raise _error(
            AirDensityError, "{label} contiene {n} valor(es) no numérico(s).",
            label=label, n=int(np.sum(~finite)),
        )
    bad = altitudes[(altitudes < _MIN_PLAUSIBLE_ALTITUDE_M) | (altitudes > _MAX_PLAUSIBLE_ALTITUDE_M)]
    if bad.size:
        raise _error(
            AirDensityError,
            "{label} queda fuera del rango plausible ({low:g} a {high:g} m s.n.m.): p. ej. {value:g} m. "
            "Revisa las unidades de la elevación (¿pies en vez de metros?) o el origen de cotas.",
            label=label, low=_MIN_PLAUSIBLE_ALTITUDE_M, high=_MAX_PLAUSIBLE_ALTITUDE_M, value=float(bad.ravel()[0]),
        )


def _as_float(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError, OverflowError):
        return float("nan")


def calibrated_air_density(altitude_m: Any, *, reference_density: float, reference_altitude_m: float) -> Any:
    """ISA profile rescaled to match ``reference_density`` at ``reference_altitude_m``."""
    rho_ref, z_ref = _as_float(reference_density), _as_float(reference_altitude_m)
    if not np.isfinite(rho_ref) or rho_ref <= 0.0:
        raise _error(
            AirDensityError, "La densidad de referencia debe ser un número positivo; se recibió {value!r}.",
            value=reference_density,
        )
    if not np.isfinite(z_ref):
        raise _error(
            AirDensityError, "La altitud de referencia debe ser un número finito; se recibió {value!r}.",
            value=reference_altitude_m,
        )
    _check_altitude_range(np.asarray([z_ref], dtype=float), log_text("La altitud de referencia"))
    return rho_ref * isa_density(altitude_m) / isa_density(z_ref)


def air_density_per_turbine(
    terrain_elevation_m: Sequence[float],
    hub_height_m: Sequence[float],
    *,
    reference_density: float,
    reference_altitude_m: float,
) -> Tuple[np.ndarray, np.ndarray]:
    """``(density, hub_altitude)`` of each turbine, from terrain elevation and hub height."""
    terrain = np.asarray(terrain_elevation_m, dtype=float).ravel()
    hubs = np.asarray(hub_height_m, dtype=float).ravel()
    if terrain.size == 0:
        raise _error(AirDensityError, "No hay posiciones de turbina para calcular la densidad de aire.")
    if hubs.size != terrain.size:
        raise _error(
            AirDensityError,
            "Se recibieron {n_terrain} cotas de terreno y {n_hubs} alturas de buje; deben coincidir (una por turbina).",
            n_terrain=terrain.size, n_hubs=hubs.size,
        )
    if not np.all(np.isfinite(terrain)):
        raise _error(
            AirDensityError,
            "{n} turbina(s) sin cota de terreno válida. Comprueba que el recurso cubre todas las posiciones del layout.",
            n=int(np.sum(~np.isfinite(terrain))),
        )
    if not np.all(np.isfinite(hubs)) or np.any(hubs <= 0.0):
        raise _error(AirDensityError, "Todas las alturas de buje deben ser números positivos.")

    hub_altitude = terrain + hubs
    _check_altitude_range(hub_altitude, log_text("La cota de buje"))
    density = np.asarray(
        calibrated_air_density(hub_altitude, reference_density=reference_density, reference_altitude_m=reference_altitude_m),
        dtype=float,
    )
    return density, hub_altitude


# ---------------------------------------------------------------------
# Terrain elevation from a PyWake Site (duck-typed, no PyWake import)
# ---------------------------------------------------------------------
def site_has_elevation(site: Any) -> bool:
    """True when the site carries a real terrain-elevation surface.

    PyWake's ``XRSite.elevation`` silently returns zeros when the resource has no
    elevation variable, which would quietly turn every hub into a sea-level hub,
    so callers must check this first instead of trusting the returned values.
    """
    if site is None:
        return False
    if getattr(site, "elevation_interpolator", None) is not None:
        return True
    ds = getattr(site, "ds", None)
    try:
        return ds is not None and "Elevation" in ds
    except Exception:
        return False


def site_defines_air_density(site: Any) -> bool:
    """True when the resource dataset carries its own ``Air_density``.

    PyWake resolves turbine inputs from the site dataset *before* the keyword
    arguments of the simulation call, so a site that defines ``Air_density``
    overrides any per-turbine array without a single error.
    """
    ds = getattr(site, "ds", None)
    if ds is None:
        return False
    try:
        return "Air_density" in ds
    except Exception:
        return False


def _site_grid_bounds(site: Any) -> Optional[Tuple[float, float, float, float]]:
    """Extent of the resource grid as ``(xmin, xmax, ymin, ymax)``, when it has one."""
    ds = getattr(site, "ds", None)
    if ds is None:
        return None
    try:
        x = np.asarray(ds["x"].values, dtype=float).ravel()
        y = np.asarray(ds["y"].values, dtype=float).ravel()
    except Exception:
        return None
    x = x[np.isfinite(x)]
    y = y[np.isfinite(y)]
    if x.size == 0 or y.size == 0:
        return None
    return float(np.min(x)), float(np.max(x)), float(np.min(y)), float(np.max(y))


def terrain_elevation_from_site(site: Any, xs: Sequence[float], ys: Sequence[float]) -> np.ndarray:
    """Terrain elevation [m] at each turbine position, from the resource grid."""
    if not site_has_elevation(site):
        raise _error(
            AirDensityError,
            "El recurso cargado no incluye una superficie de elevación, así que no se puede deducir la cota de "
            "cada buje. Usa un WRG con elevación o fija una densidad de aire uniforme.",
        )
    x = np.asarray(xs, dtype=float).ravel()
    y = np.asarray(ys, dtype=float).ravel()
    if x.size != y.size:
        raise _error(AirDensityError, "Se recibieron {nx} coordenadas X y {ny} coordenadas Y.", nx=x.size, ny=y.size)
    # A position outside the grid does not reliably come back as NaN. PyWake's
    # regular-grid interpolator keeps any index whose fractional part is >= 0, and
    # ``-0.0`` passes that test, so a coordinate sitting exactly on the grid step
    # but outside the domain wraps around to the opposite edge and returns a
    # perfectly finite elevation from the wrong side of the park. The extent is
    # therefore checked explicitly instead of trusting the returned values.
    bounds = _site_grid_bounds(site)
    if bounds is not None:
        gx0, gx1, gy0, gy1 = bounds
        outside = (x < gx0) | (x > gx1) | (y < gy0) | (y > gy1)
        if np.any(outside):
            first = int(np.argmax(outside))
            raise _error(
                AirDensityError,
                "{n_out} de {n} turbina(s) caen fuera de la malla de elevación del recurso (X[{x0:.1f}, {x1:.1f}], "
                "Y[{y0:.1f}, {y1:.1f}]); por ejemplo la turbina {index} en ({x:.1f}, {y:.1f}). Amplía el WRG o "
                "corrige el layout.",
                n_out=int(np.sum(outside)), n=x.size, x0=gx0, x1=gx1, y0=gy0, y1=gy1,
                index=first, x=float(x[first]), y=float(y[first]),
            )
    try:
        elevation = np.asarray(site.elevation(x, y), dtype=float).ravel()
    except Exception as exc:
        raise _error(
            AirDensityError,
            "No se pudo consultar la elevación del recurso en las posiciones del layout: {error}",
            error=exc,
        ) from exc
    if elevation.size != x.size or not np.all(np.isfinite(elevation)):
        raise _error(
            AirDensityError,
            "El recurso no devolvió una cota válida para cada una de las {n} turbina(s). Amplía el WRG o corrige el layout.",
            n=x.size,
        )
    return elevation

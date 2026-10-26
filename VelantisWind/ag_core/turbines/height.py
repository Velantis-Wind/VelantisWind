# -*- coding: utf-8 -*-
"""Helpers de alturas de buje para WindTurbines/PyWake."""
from __future__ import annotations

from typing import Any, Callable, Optional
import numpy as np

from ..physics.common.compat import emit
from ..log_text import log_text
from ..turbine import _error

F32 = np.float32

class _QgisLevels:
    Info: Any = None
    Warning: Any = None

Qgis = _QgisLevels()
_LOG: Optional[Callable[..., None]] = None


def configure_logging(log: Optional[Callable[..., None]] = None, *, warning_level: Any = None, info_level: Any = None) -> None:
    global _LOG
    _LOG = log
    Qgis.Warning = warning_level
    Qgis.Info = info_level


def _log(msg: str, level: Any = None) -> None:
    emit(_LOG, msg, level)

def _type_hub_heights(wt_all: Any) -> np.ndarray:
    """Hub height of each turbine *type*, however the PyWake version exposes it.

    PyWake 2.6.x stores them in ``_hub_heights`` and exposes the accessor
    ``hub_height(type)``; there is no public plural attribute. Reading only
    ``hub_heights`` therefore yields nothing at all, and every consumer silently
    falls back to a default height instead of the real one.
    """
    for attr in ("hub_heights", "_hub_heights"):
        try:
            values = np.asarray(getattr(wt_all, attr), dtype=float).ravel()
        except Exception:
            continue
        values = values[np.isfinite(values)]
        if values.size:
            return values

    accessor = getattr(wt_all, "hub_height", None)
    if callable(accessor):
        try:
            value = float(np.asarray(accessor(0), dtype=float).ravel()[0])
            if np.isfinite(value) and value > 0.0:
                return np.array([value], dtype=float)
        except Exception:  # nosec B110 - introspección defensiva de PyWake
            pass
    return np.array([], dtype=float)


def _clip_hub_heights_to_site(wt_all: Any, site) -> None:
    """Validate hub heights against WRG climate heights without mutating turbines.

    Historical versions silently clipped ``WindTurbines.hub_heights`` to the
    resource range. That changes the physical turbine geometry and can alter
    wake calculations. The new policy is:

    * one WRG climate height: use it as a height-independent reference climate
      (the WRG loader removes ``h`` from climate variables) and warn when the
      turbine HH differs;
    * multiple WRG climate heights: PyWake may interpolate inside the available
      range, but values outside the range are rejected explicitly;
    * no WRG height metadata: leave the site untouched.
    """
    ds = getattr(site, "ds", None) or getattr(site, "dataset", None)
    if ds is None:
        return

    hh = _type_hub_heights(wt_all)
    if hh.size == 0:
        return

    heights = []
    try:
        heights = [float(v) for v in ds.attrs.get("wrg_heights_m", []) if np.isfinite(float(v))]
    except Exception:
        heights = []
    if not heights:
        try:
            if "h" in ds.coords or "h" in ds:
                vals = np.asarray(ds["h"].values, dtype=float).reshape(-1)
                heights = [float(v) for v in vals[np.isfinite(vals)].tolist()]
        except Exception:
            heights = []

    hvals = np.unique(np.asarray(heights, dtype=float)) if heights else np.array([], dtype=float)
    if hvals.size == 0:
        return

    if hvals.size == 1:
        href = float(hvals[0])
        if np.any(np.abs(hh - href) > 1e-6):
            _log(
                log_text(
                    "[WT][WRG] WRG disponible solo a {height} m; HH turbina={hub_heights}. "
                    "Se conserva la HH física y se usa el clima WRG de esa altura como referencia vertical "
                    "(sin inferir shear).",
                    height=f"{href:.1f}", hub_heights=hh.tolist(),
                ),
                Qgis.Warning,
            )
        return

    hmin = float(np.nanmin(hvals)); hmax = float(np.nanmax(hvals))
    outside = hh[(hh < hmin - 1e-6) | (hh > hmax + 1e-6)]
    if outside.size:
        raise _error(
            ValueError,
            "La altura de buje queda fuera del rango vertical cubierto por el WRG. "
            "WRG=[{hmin:.1f}, {hmax:.1f}] m; HH fuera de rango={outside}. "
            "No se modifica la turbina ni se extrapola el recurso automáticamente. "
            "Añade WRG que cubran la HH o define explícitamente un modelo de shear/extrapolación.",
            hmin=hmin, hmax=hmax, outside=outside.tolist(),
        )

    if np.any(~np.isclose(hh[:, None], hvals[None, :], atol=1e-6).any(axis=1)):
        _log(
            f"[WT][WRG] HH={hh.tolist()} dentro del rango WRG [{hmin:.1f},{hmax:.1f}] m; "
            "PyWake interpolará linealmente el clima entre alturas disponibles.",
            Qgis.Info,
        )

def _hub_heights_per_turbine(wt_all: Any, type_i, n: int, *, strict: bool = False) -> np.ndarray:
    if n <= 0:
        return np.array([], dtype=F32)
    hh = _type_hub_heights(wt_all).astype(F32)
    if hh.size == 0:
        if strict:
            raise _error(ValueError, "No se conoce la altura de buje real; cálculo energético detenido.")
        return np.full(int(n), F32(100.0), dtype=F32)
    if type_i is None or hh.size == 1:
        return np.full(int(n), F32(hh[0]), dtype=F32)
    idx = np.asarray(type_i, dtype=int).ravel()
    idx = np.clip(idx, 0, max(0, hh.size - 1))
    if idx.size != int(n):
        out = np.full(int(n), F32(hh[0]), dtype=F32)
        m = min(int(n), idx.size)
        out[:m] = hh[idx[:m]]
        return out.astype(F32)
    return hh[idx].astype(F32)

clip_hub_heights_to_site = _clip_hub_heights_to_site
hub_heights_per_turbine = _hub_heights_per_turbine

__all__ = ["configure_logging", "clip_hub_heights_to_site", "hub_heights_per_turbine"]

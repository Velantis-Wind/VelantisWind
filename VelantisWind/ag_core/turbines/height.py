# -*- coding: utf-8 -*-
"""Helpers de alturas de buje para WindTurbines/PyWake."""
from __future__ import annotations

from typing import Any, Callable, Optional
import numpy as np

from ..physics.common.compat import emit

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

def _clip_hub_heights_to_site(wt_all: Any, site) -> None:
    try:
        ds = getattr(site, "ds", None) or getattr(site, "dataset", None)
        if ds is None:
            return
        if "h" not in ds.coords and "h" not in ds:
            return
        hcoord = ds["h"]
        hvals = np.asarray(hcoord.values if hasattr(hcoord, "values") else hcoord, dtype=F32)
        if hvals.size == 0:
            return
        hmin = float(np.nanmin(hvals)); hmax = float(np.nanmax(hvals))
        hh = np.array(getattr(wt_all, "hub_heights", []), dtype=F32)
        if hh.size == 0:
            return
        if (hh < hmin).any() or (hh > hmax).any():
            hh2 = np.clip(hh, hmin, hmax).astype(F32)
            _log(f"[WT] Hub heights fuera de [{hmin:.1f},{hmax:.1f}] -> recortados: {hh.tolist()} -> {hh2.tolist()}", Qgis.Warning)

            applied = False
            # Variante 1: atributo re-asignable
            for candidate in (hh2.tolist(), hh2, tuple(float(v) for v in hh2.tolist())):
                try:
                    setattr(wt_all, "hub_heights", candidate)
                    chk = np.asarray(getattr(wt_all, "hub_heights", []), dtype=F32)
                    if chk.size == hh2.size and np.allclose(chk, hh2, equal_nan=True):
                        applied = True
                        break
                except Exception:
                    pass

            # Variante 2: mutación in-place
            if not applied:
                try:
                    target = getattr(wt_all, "hub_heights", None)
                    if target is not None:
                        target[:] = hh2.tolist()
                        chk = np.asarray(getattr(wt_all, "hub_heights", []), dtype=F32)
                        if chk.size == hh2.size and np.allclose(chk, hh2, equal_nan=True):
                            applied = True
                except Exception:
                    pass

            if not applied:
                _log("[WT] No se pudieron aplicar los hub heights recortados al objeto WindTurbines.", Qgis.Warning)
    except Exception as e:
        try:
            _log(f"[WT] Falló el clipping de hub heights contra el site: {repr(e)}", Qgis.Warning)
        except Exception:
            pass

def _hub_heights_per_turbine(wt_all: Any, type_i, n: int) -> np.ndarray:
    if n <= 0:
        return np.array([], dtype=F32)
    try:
        hh = np.asarray(getattr(wt_all, "hub_heights", []), dtype=F32).ravel()
    except Exception:
        hh = np.array([], dtype=F32)
    if hh.size == 0:
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

# -*- coding: utf-8 -*-
"""Array extraction helpers for PyWake simulation results.

The historical AEP engine supports several PyWake versions.  These helpers keep
that compatibility code out of ``aep_compute.py`` and return plain Python/numpy
objects that the UI and reports can consume.
"""
from __future__ import annotations

from typing import Callable, List, Optional, Tuple

import numpy as np


def aep_per_turb(sim) -> np.ndarray:
    """
    Return AEP per turbine as a 1-D numpy array in MWh.

    Preferred path: ``sim.aep_ilk()`` where PyWake returns GWh indexed by
    turbine, wind direction and wind speed.  The helper then sums over wind
    direction/speed and converts to MWh.
    """
    # 1) Preferred route: aep_ilk (i=turbine, l=wd, k=ws)
    try:
        if hasattr(sim, "aep_ilk"):
            aep_ilk = sim.aep_ilk()  # xarray DataArray or numpy, in GWh
            try:
                vals = aep_ilk.values
            except Exception:
                vals = np.asarray(aep_ilk)

            if vals.ndim == 3 and vals.shape[0] >= 1:
                aep_i_gwh = np.nansum(vals, axis=(1, 2))
                return aep_i_gwh * 1000.0

            try:
                dims = getattr(aep_ilk, "dims", None)
                if dims and ("wt" in dims or "i" in dims):
                    da = aep_ilk
                    for d in list(dims):
                        if d not in ("wt", "i"):
                            da = da.sum(d)
                    return np.asarray(da.values) * 1000.0
            except Exception:
                pass
    except Exception:
        pass

    # 2) Fallback: sim.aep() may be scalar or per-turbine depending on PyWake/version.
    aep = sim.aep()
    try:
        vals = aep.values
        dims = getattr(aep, "dims", None)
    except Exception:
        vals = np.asarray(aep)
        dims = None

    if np.asarray(vals).ndim == 0 or np.asarray(vals).size == 1:
        n_wt = None
        for attr in ("wt_x", "x", "WT_x"):
            if hasattr(sim, attr):
                try:
                    n_wt = len(getattr(sim, attr))
                    break
                except Exception:
                    pass
        if n_wt is None:
            try:
                n_wt = int(getattr(sim, "n_wt"))
            except Exception:
                n_wt = 1
        total_mwh = float(np.asarray(vals).reshape(-1)[0]) * 1000.0
        return np.full(int(n_wt), total_mwh / max(int(n_wt), 1), dtype=float)

    arr = np.asarray(vals, dtype=float)

    try:
        if dims:
            da = aep
            for d in list(dims):
                if d not in ("wt", "i"):
                    da = da.sum(d)
            arr = np.asarray(da.values, dtype=float)
    except Exception:
        pass

    arr = np.asarray(arr).reshape(-1)
    return arr * 1000.0


def _aep_by_wd(sim) -> Tuple[Optional[List[float]], Optional[List[float]]]:
    """Return (AEP_MWh_per_wd, wind_directions_deg) when ``aep_ilk`` is available."""
    if not hasattr(sim, "aep_ilk"):
        return None, None
    arr = sim.aep_ilk()
    try:
        vals = arr.values
        dims = getattr(arr, "dims", None)
    except Exception:
        vals = np.asarray(arr)
        dims = None
    vals = np.asarray(vals)
    if vals.ndim != 3:
        return None, None

    # PyWake convention: (i=wt, l=wd, k=ws). Sum turbine and ws -> vector per wd.
    gwh_per_wd = np.nansum(vals, axis=(0, 2))
    wd_arr = None
    try:
        if dims and "wd" in dims:
            wd_arr = np.asarray(arr.coords["wd"].values, dtype=float)
    except Exception:
        wd_arr = None
    if wd_arr is None:
        n = len(gwh_per_wd)
        wd_arr = np.linspace(0.0, 360.0, n, endpoint=False)
    return [float(v) * 1000.0 for v in gwh_per_wd], [float(d) for d in wd_arr]


def extract_directional_breakdown(sim_wake, sim_free, log: Optional[Callable[[str], None]] = None) -> Tuple[Optional[List[float]], Optional[List[float]], Optional[List[float]]]:
    """
    Extract directional AEP breakdown for wake and free-stream simulations.

    Returns ``(wake_mwh_per_wd, free_mwh_per_wd, directions_deg)``. If the data is
    unavailable or inconsistent, returns ``(None, None, None)``.
    """
    try:
        wake_per_wd, wd_arr_w = _aep_by_wd(sim_wake)
        free_per_wd, wd_arr_f = _aep_by_wd(sim_free)
        if wake_per_wd and free_per_wd and len(wake_per_wd) == len(free_per_wd):
            return wake_per_wd, free_per_wd, wd_arr_w or wd_arr_f
    except Exception as exc:
        if log is not None:
            try:
                log(f"[AEP] No se pudo extraer desglose por dirección: {exc!r}")
            except Exception:
                pass
    return None, None, None


__all__ = ["aep_per_turb", "extract_directional_breakdown"]

# -*- coding: utf-8 -*-
"""Array extraction helpers for PyWake simulation results.

The AEP is annualised with 8766 h/year (``resource_grid.hours_per_year``)
instead of PyWake's default 8760.  These helpers therefore prefer ``sim.aep`` with an
explicit ``hours_pr_year`` and only fall back to ``aep_ilk`` when necessary.
"""
from __future__ import annotations

import logging

from typing import Callable, List, Optional, Tuple

import numpy as np


def _aep_da(sim, hours_per_year: float = 8760.0):
    """Return a PyWake AEP DataArray in GWh with explicit annualisation."""
    hours = float(hours_per_year or 8760.0)
    try:
        if hasattr(sim, "aep"):
            return sim.aep(hours_pr_year=hours)
    except TypeError:
        # Older PyWake: scale the standard 8760-h result explicitly.
        try:
            da = sim.aep()
            return da * (hours / 8760.0)
        except Exception as _ignored_exc:
            logging.getLogger(__name__).debug("Ignored optional operation at %s:%d: %s", __name__, 26, _ignored_exc)
    except Exception as _ignored_exc:
        logging.getLogger(__name__).debug("Ignored optional operation at %s:%d: %s", __name__, 28, _ignored_exc)

    if hasattr(sim, "aep_ilk"):
        da = sim.aep_ilk()
        if abs(hours - 8760.0) > 1e-9:
            da = da * (hours / 8760.0)
        return da
    raise RuntimeError("SimulationResult no expone un método AEP compatible")


def aep_per_turb(sim, hours_per_year: float = 8760.0) -> np.ndarray:
    """Return AEP per turbine as a 1-D numpy array in MWh."""
    try:
        aep = _aep_da(sim, hours_per_year=hours_per_year)
        try:
            vals = aep.values
            dims = getattr(aep, "dims", None)
        except Exception:
            vals = np.asarray(aep)
            dims = None

        arr = np.asarray(vals, dtype=float)
        if arr.ndim == 3 and arr.shape[0] >= 1:
            return np.nansum(arr, axis=(1, 2)) * 1000.0

        try:
            if dims and ("wt" in dims or "i" in dims):
                da = aep
                for d in list(dims):
                    if d not in ("wt", "i"):
                        da = da.sum(d)
                return np.asarray(da.values, dtype=float).reshape(-1) * 1000.0
        except Exception as _ignored_exc:
            logging.getLogger(__name__).debug("Ignored optional operation at %s:%d: %s", __name__, 61, _ignored_exc)

        if arr.ndim == 0 or arr.size == 1:
            n_wt = None
            for attr in ("wt_x", "x", "WT_x"):
                if hasattr(sim, attr):
                    try:
                        n_wt = len(getattr(sim, attr))
                        break
                    except Exception as _ignored_exc:
                        logging.getLogger(__name__).debug("Ignored optional operation at %s:%d: %s", __name__, 71, _ignored_exc)
            if n_wt is None:
                try:
                    n_wt = int(getattr(sim, "n_wt"))
                except Exception:
                    n_wt = 1
            total_mwh = float(arr.reshape(-1)[0]) * 1000.0
            return np.full(int(n_wt), total_mwh / max(int(n_wt), 1), dtype=float)

        return arr.reshape(-1) * 1000.0
    except Exception:
        # Historical last-resort path.
        aep = sim.aep()
        vals = np.asarray(getattr(aep, "values", aep), dtype=float)
        if vals.ndim == 3:
            vals = np.nansum(vals, axis=(1, 2))
        return vals.reshape(-1) * 1000.0 * (float(hours_per_year or 8760.0) / 8760.0)


def _aep_by_wd(sim, hours_per_year: float = 8760.0) -> Tuple[Optional[List[float]], Optional[List[float]]]:
    """Return (AEP_MWh_per_wd, wind_directions_deg)."""
    try:
        arr = _aep_da(sim, hours_per_year=hours_per_year)
    except Exception:
        return None, None
    try:
        vals = arr.values
        dims = getattr(arr, "dims", None)
    except Exception:
        vals = np.asarray(arr)
        dims = None
    vals = np.asarray(vals)
    if vals.ndim != 3:
        return None, None

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


def _aggregate_to_sector_centers(values: List[float], directions: List[float], sector_centers_deg) -> Tuple[List[float], List[float]]:
    """Aggregate fine directional bins back to native sector centres."""
    centers = np.asarray(sector_centers_deg, dtype=float).reshape(-1)
    centers = centers[np.isfinite(centers)]
    dirs = np.asarray(directions, dtype=float).reshape(-1)
    vals = np.asarray(values, dtype=float).reshape(-1)
    if centers.size == 0 or dirs.size != vals.size:
        return list(values), list(directions)
    delta = ((dirs[:, None] - centers[None, :] + 180.0) % 360.0) - 180.0
    idx = np.argmin(np.abs(delta), axis=1)
    out = np.zeros(centers.size, dtype=float)
    for i, value in zip(idx.tolist(), vals.tolist()):
        if np.isfinite(value):
            out[int(i)] += float(value)
    return [float(v) for v in out.tolist()], [float(v) for v in centers.tolist()]


def extract_directional_breakdown(
    sim_wake,
    sim_free,
    log: Optional[Callable[[str], None]] = None,
    sector_centers_deg=None,
    hours_per_year: float = 8760.0,
) -> Tuple[Optional[List[float]], Optional[List[float]], Optional[List[float]]]:
    """Extract directional AEP breakdown for wake and free-stream simulations."""
    try:
        wake_per_wd, wd_arr_w = _aep_by_wd(sim_wake, hours_per_year=hours_per_year)
        free_per_wd, wd_arr_f = _aep_by_wd(sim_free, hours_per_year=hours_per_year)
        if wake_per_wd and free_per_wd and len(wake_per_wd) == len(free_per_wd):
            dirs = wd_arr_w or wd_arr_f
            if sector_centers_deg is not None and dirs is not None:
                wake_per_wd, centers = _aggregate_to_sector_centers(wake_per_wd, dirs, sector_centers_deg)
                free_per_wd, _ = _aggregate_to_sector_centers(free_per_wd, dirs, sector_centers_deg)
                return wake_per_wd, free_per_wd, centers
            return wake_per_wd, free_per_wd, dirs
    except Exception as exc:
        if log is not None:
            try:
                log(f"[AEP] No se pudo extraer desglose por dirección: {exc!r}")
            except Exception as _ignored_exc:
                logging.getLogger(__name__).debug("Ignored optional operation at %s:%d: %s", __name__, 159, _ignored_exc)
    return None, None, None


def edge_case_arrays(sim, hours_per_year: float) -> dict:
    """Copies of the arrays of a simulation the edge cases read (#63): the AEP per (turbine, direction, speed) and,
    aligned with it, ``WS_eff``, ``P``, the power and, with a Weibull resource, the frequency of each sector (``None``
    without it). A simulation without the 0 m/s node gives them with the slice of its small one
    (``zero_node.Joined.diagnosis_source``). Only for the diagnosis, called once the calculation has read everything
    it reads from ``sim``: nothing of the calculation reads them."""
    source = getattr(sim, "diagnosis_source", sim)
    aep = source.aep(hours_pr_year=float(hours_per_year))

    def own(values):
        out = np.array(values, dtype=float)
        out.setflags(write=False)  # read-only copies: the module receives nothing it could write into
        return out

    def aligned(name):
        return own(source[name].broadcast_like(aep).transpose(*aep.dims).values)
    return {"aep": own(aep.values), "ws_eff": aligned("WS_eff"), "p": aligned("P"), "power": aligned("Power"),
            "frequency": aligned("Sector_frequency") if "Sector_frequency" in source else None}


def ti_arrays(sim) -> tuple:
    """Read-only copies of ``TI_eff`` (turbine first) and of ``P`` aligned with it, for the reasons of the effective
    TI (#63, decision 8); ``(None, None)`` when the simulation does not give ``TI_eff``."""
    try:
        ti = sim["TI_eff"]  # also a ``zero_node.Joined``, which has no ``in``
    except KeyError:
        return None, None
    ti = ti.transpose("wt", *[d for d in ti.dims if d != "wt"])

    def own(values):
        out = np.array(values, dtype=float)
        out.setflags(write=False)
        return out
    return own(ti.values), own(sim["P"].broadcast_like(ti).transpose(*ti.dims).values)


__all__ = ["aep_per_turb", "extract_directional_breakdown", "edge_case_arrays", "ti_arrays"]

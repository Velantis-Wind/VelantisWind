# -*- coding: utf-8 -*-
"""One PyWake simulation of a built wind farm model (#46 P5b).

The model is built and its classes checked by ``wake_setup.factory``; here it is only called. With turbines of
several types, the type of each one is passed as ``type`` and checked in the result; with one type, nothing is
passed. The grid of the bin-mean power is checked before simulating. There is no retry and no fallback: an error of
PyWake is the error of the calculation (decision 1).

With ``operator_ws`` (only the exception of WeightedSum with the 0 m/s node passes it, ``zero_node``; #63, decision
4), the bin-mean power is that of ``operator_ws``, the whole grid, and the simulated speeds can only be that grid
without its first node, 0 m/s, or its first two nodes.
"""
from __future__ import annotations

from typing import Any, Dict, Optional

import numpy as np

from ..turbines.bin_power import check_grid

__all__ = ["simulate"]


def _check_operator_ws(ws, operator_ws) -> None:
    grid = np.atleast_1d(np.asarray(operator_ws, dtype=float))
    simulated = None if ws is None else np.atleast_1d(np.asarray(ws, dtype=float))
    if grid.size < 2 or grid[0] != 0.0 or simulated is None or not (
            np.array_equal(simulated, grid[1:]) or np.array_equal(simulated, grid[:2])):
        raise ValueError("La rejilla simulada no es una de las de la excepción del nodo de 0 m/s.")


def simulate(wfm: Any, xs, ys, *, type_i=None, wd=None, ws=None, wt_inputs: Optional[Dict[str, Any]] = None,
             operator_ws=None) -> Any:
    """Simulate ``wfm`` at ``xs``, ``ys`` (see the module docstring); ``wt_inputs`` are the per-turbine inputs of the
    power and Ct functions (e.g. ``{"Air_density": array}``)."""
    wt = getattr(wfm, "windTurbines", None)
    if operator_ws is not None:
        _check_operator_ws(ws, operator_ws)
    if hasattr(wt, "powerCtFunction"):
        check_grid(wt, operator_ws if operator_ws is not None else (ws if ws is not None else wfm.site.default_ws))
    xs, ys = np.asarray(xs), np.asarray(ys)
    kwargs: Dict[str, Any] = {"x": xs, "y": ys}
    if wd is not None:
        kwargs["wd"] = np.asarray(wd, dtype=float)
    if ws is not None:
        kwargs["ws"] = np.asarray(ws, dtype=float)
    kwargs.update({str(k): v for k, v in (wt_inputs or {}).items() if v is not None})
    if type_i is None:
        return wfm(**kwargs)
    types = np.asarray(type_i, dtype=int).ravel()
    if types.size != xs.size:
        raise ValueError(f"El vector de tipos tiene {types.size} elementos para {xs.size} turbinas.")
    sim = wfm(**kwargs, type=types)
    got = np.asarray(sim["type"].values, dtype=int).ravel()
    if got.size != types.size or not np.array_equal(got, types):
        raise RuntimeError("PyWake ejecutó la simulación, pero no con el vector de tipos pedido.")
    return sim

# -*- coding: utf-8 -*-
"""How the iterative loops of a simulation ended, and the effective TI it computed (decisions 9 and 21).

``ConvergenceRecorder`` watches, during one simulation and only in the
thread that runs it, the three iterative loops of PyWake 2.6.18: the weights
of ``WeightedSum`` (``superposition_models.py:143``), the iterations of
``All2AllIterative`` (``engineering_models.py:1020-1152``) and those of
``PropagateUpDownIterative`` (``:559-596``). It reads their local variables
when each loop returns, through a trace function of the interpreter
(``sys.settrace``); it changes no operation and no object, so the result is
the same as without it and the class check does not see it (P0, section 5).
If the variables cannot be read, the convergence is «unavailable», never
«converged».

States: ``WeightedSum``: ``converged`` (also when no deficit needs weighting),
``max_iter`` (it reached ``max_iter`` with the error above ``max_err``) or
``tolerance_not_met`` (it stopped without meeting ``max_err``, e.g. with a
non-finite error). ``All2AllIterative``: ``converged``, ``no_check``
(``convergence_tolerance = None``: one iteration) or ``not_converged``
(PyWake's warning after its last iteration). ``PropagateUpDownIterative``:
``converged``, ``converged_on_mask`` (the tolerance was met only by the flow
cases its ``iconverging`` mask keeps: one it left out has a larger residual),
``max_iter`` or ``loop_exhausted`` (its loop has at most as many iterations as
turbines); and, in every state, how many flow cases the mask left out of the
check, with their largest residual. A loop counts as converged only in the
state ``converged``; ``no_check`` is not a convergence.
"""
from __future__ import annotations

import importlib
import sys
from collections import Counter
from typing import Any, Dict, List, Optional

import numpy as np

__all__ = ["ConvergenceRecorder", "effective_ti_per_turbine", "UNAVAILABLE"]

UNAVAILABLE = "unavailable"


_TARGETS = (("py_wake.superposition_models", "WeightedSum", "__call__"),
            ("py_wake.wind_farm_models.engineering_models", "All2AllIterative", "_calc_wt_interaction"),
            ("py_wake.wind_farm_models.engineering_models", "PropagateUpDownIterative", "_calc_wt_interaction"))


def _targets() -> Dict[Any, str]:
    """The loops to watch, each on its own: a class this PyWake does not have is not watched, so a calculation never
    needs a class it does not use (an installed class is the validation's business, R14). Any other failure (the
    module, or the method of a class that is there) is raised, never taken for an absence."""
    out = {}
    for module, name, method in _TARGETS:
        cls = getattr(importlib.import_module(module), name, None)
        if cls is not None:
            out[getattr(cls, method).__code__] = name
    return out


def _weighted_sum(loc: Dict[str, Any]) -> Dict[str, Any]:
    self, count, il = loc["self"], int(loc["count"]) if "count" in loc else 0, loc["Il"]
    if not np.any(il):
        return {"state": "converged", "iterations": 0, "error": 0.0}
    from py_wake.utils.gradients import cabs
    ilx, uc, uc_star = loc["Ilx"], loc["Uc"], loc["Uc_star"]
    with np.errstate(all="ignore"):
        err = float(np.max(cabs((uc[ilx] - uc_star[ilx]) / uc_star[ilx])))
    if err <= self.max_err:
        state = "converged"
    elif count >= self.max_iter:
        state = "max_iter"
    else:
        state = "tolerance_not_met"
    return {"state": state, "iterations": count, "error": err, "max_err": _as_given(self.max_err),
            "max_iter": _as_given(self.max_iter)}


def _all2all(loc: Dict[str, Any]) -> Dict[str, Any]:
    self, j, max_diff = loc["self"], int(loc["j"]), float(loc["max_diff"])
    tol = self.convergence_tolerance
    if tol is None:
        state = "no_check"
    elif tol and max_diff < tol:
        state = "converged"
    else:
        state = "not_converged"
    return {"state": state, "iterations": j + 1, "max_diff": max_diff, "tolerance": tol}


def _propagate_up_down(loc: Dict[str, Any]) -> Dict[str, Any]:
    self, j, max_diff = loc["self"], int(loc["j"]), float(loc["max_diff"])
    excluded = ~np.asarray(loc["iconverging"], dtype=bool)
    diff = np.asarray(np.abs(loc["diff_ilk"]), dtype=float)
    residual = float(diff[excluded].max()) if excluded.any() else None
    if max_diff < self.convergence_tolerance:
        state = "converged" if residual is None or residual < self.convergence_tolerance else "converged_on_mask"
    elif j + 1 >= self.max_iter:
        state = "max_iter"
    else:
        state = "loop_exhausted"
    return {"state": state, "iterations": j + 1, "max_diff": max_diff, "tolerance": _as_given(self.convergence_tolerance),
            "max_iter": _as_given(self.max_iter), "excluded_cases": int(excluded.sum()),
            "excluded_max_residual": residual}


def _as_given(value: Any) -> Any:
    """An argument as PyWake compares it: ``max_iter`` with its counter (``count < max_iter``: 2.5 makes three passes,
    so it is recorded as 2.5, not truncated; #64 lets it be edited), and a tolerance with its error (an integer too
    large for a float is compared exactly, and recorded as given: decision 6.2 of #64)."""
    return value.item() if hasattr(value, "item") else value


_READERS = {"WeightedSum": _weighted_sum, "All2AllIterative": _all2all, "PropagateUpDownIterative": _propagate_up_down}


class ConvergenceRecorder:
    """Context manager around one simulation (``with ConvergenceRecorder() as rec: wfm(...)``)."""

    def __init__(self) -> None:
        self.records: Dict[str, List[Dict[str, Any]]] = {name: [] for name in _READERS}
        self._previous = None
        self._targets: Dict[Any, str] = {}

    def __enter__(self) -> "ConvergenceRecorder":
        self._targets = _targets()
        self._previous = sys.gettrace()
        sys.settrace(self._global)
        return self

    def __exit__(self, *exc: Any) -> None:
        sys.settrace(self._previous)

    def _global(self, frame, event, arg):
        kind = self._targets.get(frame.f_code) if event == "call" else None
        if kind is None:
            return None

        def local(frame, event, arg):
            if event == "return":
                try:
                    record = _READERS[kind](frame.f_locals) if arg is not None else {"state": UNAVAILABLE,
                                                                                   "reason": "excepción"}
                except Exception as exc:
                    record = {"state": UNAVAILABLE, "reason": f"{type(exc).__name__}: {exc}"}
                self.records[kind].append(record)
            return local
        return local

    def summary(self) -> Dict[str, Any]:
        """Per loop: how many times it ran, how many ended in each state (with the reasons of those whose state could
        not be read), the worst finite residual and how many residuals were not finite (decision 6.5 of #64)."""
        out: Dict[str, Any] = {}
        for kind, recs in self.records.items():
            if not recs:
                continue
            states = Counter(r["state"] for r in recs)
            entry: Dict[str, Any] = {"calls": len(recs), "states": dict(states),
                                     "converged": set(states) == {"converged"},
                                     "unavailable_reasons": sorted({r["reason"] for r in recs
                                                                    if r["state"] == UNAVAILABLE})}
            non_finite = 0
            if kind == "WeightedSum":
                entry["max_error"], non_finite = _worst([r.get("error") for r in recs])
            else:
                entry["max_diff"], non_finite = _worst([r.get("max_diff") for r in recs])
                entry["iterations"] = max((r["iterations"] for r in recs if "iterations" in r), default=None)
            if kind == "PropagateUpDownIterative":
                entry["excluded_cases"] = sum(r.get("excluded_cases", 0) for r in recs)
                entry["excluded_max_residual"], excluded = _worst([r.get("excluded_max_residual") for r in recs])
                non_finite += excluded
            entry["non_finite_residuals"] = non_finite
            out[kind] = entry
        return out


def _worst(values: List[Any]) -> tuple:
    """The largest finite residual (``None`` without one) and how many were not finite: never Python's ``max``, which
    with a NaN depends on the order."""
    arr = np.asarray([v for v in values if v is not None], dtype=float)
    finite = arr[np.isfinite(arr)]
    return (float(finite.max()) if finite.size else None), int(arr.size - finite.size)


def effective_ti_per_turbine(sim: Any) -> Optional[np.ndarray]:
    """The effective TI of each turbine of a simulation (``TI_eff``), as a fraction, weighted by the probability of
    each wind direction and speed (``P``, as the AEP). ``None`` if the simulation does not give it, and ``NaN`` for a
    turbine with a value that is not finite: never a default, never a sum that skips what is missing.
    """
    try:
        ti, p = sim["TI_eff"], sim["P"]
        dims = [d for d in ("wd", "ws", "time") if d in ti.dims]
        w = p.broadcast_like(ti)
        values = ((ti * w).sum(dims, skipna=False) / w.sum(dims, skipna=False)).values
        out = np.asarray(values, dtype=float).reshape(-1)
        out[~np.isfinite(out)] = np.nan  # an infinite value is not a value either
        return out if out.size == ti.sizes["wt"] else None
    except Exception:
        return None

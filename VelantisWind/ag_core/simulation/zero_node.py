# -*- coding: utf-8 -*-
"""The exception of ``WeightedSum`` with the 0 m/s node (#63, decisions 3 and 4, mechanism (a+)).

With 0 m/s in the grid, the residual ``WeightedSum`` checks has a NaN (0/0, ``superposition_models.py:143``) and,
as a rule, it adds the wakes linearly in the whole calculation. The node is put there by the discretisation of the
plugin, so, only when ``WeightedSum`` is the wake superposition, the grid has the 0 m/s node and its arguments do
not discard the weighting (``edge_cases.weighting_discarded``):

- each simulation of the calculation (the main one, the variants and A_0) runs without the 0 m/s node, with the
  bin-mean power of the whole grid (``operator_ws`` of the runner);
- a small simulation with the same model and ``ws = [0, step]`` gives the 0 m/s slice (two nodes: with one, PyWake
  gives P = NaN; its edges of P are those of the whole grid); its convergence is recorded apart, without the
  records of ``WeightedSum``, which belong to the node of support or to a 0 m/s without wakes;
- the slice goes into the AEP per (turbine, direction, speed) before the reductions that exist (``Joined``).

The attempt is atomic (``Attempt``): if a simulation of it fails, the calculation is repeated with the whole grid.
Joining the slice is code of the calculation: a failure there is an error of the calculation. Everything else of
the calculation is as always; nothing here runs without the three conditions.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Callable, Dict, Optional

import numpy as np

from ..edge_cases import weighting_discarded
from ..log_text import log_text
from ..wake_setup.instrumentation import ConvergenceRecorder

__all__ = ["Plan", "ORDINARY", "plan", "Joined", "Attempt", "NOTE", "NOT_APPLIED", "AUXILIARY_LABEL", "zero_node_note"]

NOTE = ("Con WeightedSum, el nodo de 0 m/s se calcula aparte: las simulaciones van sin él, para que WeightedSum pueda "
        "ponderar, y su parte del AEP sale de una simulación pequeña con las velocidades {small} m/s.")
NOT_APPLIED = "Excepción de WeightedSum con el nodo de 0 m/s no aplicada: {reason}"
AUXILIARY_LABEL = "Simulación auxiliar de 0 m/s"


@dataclass(frozen=True)
class Plan:
    """Whether the exception applies, its grids and, if it does not apply when it should, the warning why."""
    applies: bool
    operator_ws: Optional[np.ndarray] = None  # the whole grid: the bin-mean power, always
    ws: Optional[np.ndarray] = None           # the simulations of always, without the 0 m/s node
    small_ws: Optional[np.ndarray] = None     # the small simulation, [0, step]
    warning: Optional[Any] = None


ORDINARY = Plan(False)


def _not_applied(reason: Any) -> Plan:
    return Plan(False, warning=log_text(NOT_APPLIED, reason=reason))


def plan(config: Any, ws_grid: Any) -> Plan:
    """The plan of the exception for ``config`` and the wind speeds of the calculation (``None``: those of the site,
    without the node). A failure preparing it is a warning, and the calculation is the ordinary one."""
    try:
        if config.superposition.name != "WeightedSum" or ws_grid is None:
            return ORDINARY
        grid = np.asarray(ws_grid, dtype=float).reshape(-1)
        if grid.size == 0 or grid[0] != 0.0:
            return ORDINARY
        params = config.superposition.params
        if weighting_discarded(params):
            return ORDINARY
        if params.get("max_iter") == math.inf:
            return _not_applied(log_text("con max_iter = +inf, WeightedSum podría no terminar sin el nodo de 0 m/s."))
        if grid.size < 3:
            return _not_applied(log_text("sin el nodo de 0 m/s, la malla quedaría con un solo nodo."))
        return Plan(True, operator_ws=grid.copy(), ws=grid[1:].copy(), small_ws=grid[:2].copy())
    except Exception as exc:  # noqa: BLE001 - before simulating: the ordinary calculation, said
        return _not_applied(log_text("no se pudo preparar ({error}).", error=f"{type(exc).__name__}: {exc}"))


class Joined:
    """A simulation without the 0 m/s node and the small one: its AEP is the AEP of the small one at 0 m/s followed
    by that of the simulation, along ``ws``, before any reduction. Every other field is the simulation's
    (``sim["TI_eff"]``: the effective TI is weighted without the 0 m/s node, a declared consequence);
    ``diagnosis_source`` gives each field with the 0 m/s slice, for the diagnosis of the edge cases."""

    def __init__(self, rest: Any, small: Any, on_error: Callable[[BaseException], None]):
        self.rest, self.small, self._on_error = rest, small, on_error

    def _join(self, rest: Any, small: Any) -> Any:
        import xarray as xr
        try:
            return xr.concat([small.isel(ws=slice(0, 1)), rest], dim="ws")
        except Exception as exc:
            self._on_error(exc)
            raise

    def aep(self, **kwargs: Any) -> Any:
        try:
            rest, small = self.rest.aep(**kwargs), self.small.aep(**kwargs)
        except Exception as exc:
            self._on_error(exc)
            raise
        return self._join(rest, small)

    def __getitem__(self, key: str) -> Any:
        return self.rest[key]

    @property
    def diagnosis_source(self) -> "_Slices":
        return _Slices(self)


class _Slices:
    """The fields of a ``Joined`` with the 0 m/s slice, for the diagnosis only: its failures are not the
    calculation's (the diagnosis is protected), so they are not reported to the attempt."""

    def __init__(self, joined: Joined):
        self._joined = joined

    @staticmethod
    def _concat(rest: Any, small: Any) -> Any:
        import xarray as xr
        if "ws" not in rest.dims:
            return rest
        return xr.concat([small.isel(ws=slice(0, 1)), rest], dim="ws")

    def aep(self, **kwargs: Any) -> Any:
        return self._concat(self._joined.rest.aep(**kwargs), self._joined.small.aep(**kwargs))

    def __getitem__(self, key: str) -> Any:
        return self._concat(self._joined.rest[key], self._joined.small[key])

    def __contains__(self, key: str) -> bool:
        return key in self._joined.rest


class Attempt:
    """One calculation with the exception: all its simulations count, or none (``error``)."""

    def __init__(self, plan_: Plan):
        self.plan = plan_
        self.error: Optional[BaseException] = None
        self.join_error: Optional[BaseException] = None
        self.auxiliary = ConvergenceRecorder()

    def _join_failed(self, exc: BaseException) -> None:
        if self.join_error is None:
            self.join_error = exc

    def simulate(self, simulate: Callable[..., Any]) -> Joined:
        """The simulation without the 0 m/s node and the small one; ``simulate(ws, operator_ws)`` runs one of the
        model with those wind speeds and the bin-mean power of ``operator_ws``."""
        try:
            rest = simulate(self.plan.ws, self.plan.operator_ws)
            with self.auxiliary:
                small = simulate(self.plan.small_ws, self.plan.operator_ws)
        except Exception as exc:
            if self.error is None:
                self.error = exc
            raise
        return Joined(rest, small, self._join_failed)

    def auxiliary_summary(self) -> Dict[str, Any]:
        """The convergence of the small simulations without that of ``WeightedSum`` (decision 4)."""
        return {k: v for k, v in self.auxiliary.summary().items() if k != "WeightedSum"}

    def retry_warning(self) -> Any:
        return log_text(NOT_APPLIED, reason=log_text("con la malla sin 0 m/s PyWake da un error: {error}",
                                                     error=f"{type(self.error).__name__}: {self.error}"))

    def note(self) -> Any:
        return zero_node_note({"zero_node_m_s": self.plan.small_ws})


def zero_node_note(executed_ws: Any) -> Any:
    """The note of a result calculated with the exception, from its ``executed_ws`` (for its outputs)."""
    return log_text(NOTE, small=", ".join(f"{float(v):g}" for v in executed_ws["zero_node_m_s"]))

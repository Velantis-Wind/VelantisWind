# -*- coding: utf-8 -*-
"""Power of a wind-speed bin: the mean of the power curve over the bin, not its value at the centre.

PyWake weighs each wind-speed bin by the probability of the whole bin, from
``a_k`` to ``b_k``, but evaluates the power at one speed of it. Here the power
assigned to the bin is the mean of the curve over the interval instead:

    P_bin = 1 / (b - a) * integral from a to b of P(v) dv

PyWake hands the power function only the speed ``v`` it evaluates (the free
or effective speed, projected by yaw), not the flow case. The interval is the
bin of the simulated grid that contains ``v``, with the edges PyWake uses for
its probabilities (``set_W``), translated to ``v``:
``[a_k + (v - ws_k), b_k + (v - ws_k)]``. In free stream without speed-up,
``v = ws_k`` and the interval is the bin itself.

The integral is exact for the curves the plugins build: the primitive of the
linear interpolation PyWake evaluates, per density column, and the analytic
one of ``CubePowerSimpleCt``. Outside the operating band a builder declares on
the curve (``operating_band``) the power is zero, with steps at its edges.
Ct is not touched: only the power changes.

``POINT`` keeps PyWake's own evaluation at the speed; nothing in the dialogs
reaches it.
It needs only numpy; PyWake is imported lazily. Its errors are programming
errors, not messages for the interface.
"""
from __future__ import annotations

import copy

import numpy as np

__all__ = ["BIN_MEAN", "POINT", "bin_edges", "bin_mean_power_ct", "simulation_wind_turbines", "check_grid"]

BIN_MEAN = "bin_mean"
POINT = "point"


def bin_edges(ws_grid):
    """Return ``(grid, edges)``: a float copy of the grid, shape ``(n,)``, and its bin edges, shape ``(n + 1,)``.

    The edges are PyWake's (``Site.set_W``): the midpoints between speeds, the
    first edge clipped at 0; with a single speed ``v``, ``[v - 0.5, v + 0.5]``,
    unclipped.
    """
    try:
        grid = np.atleast_1d(np.array(ws_grid, dtype=float))
    except (TypeError, ValueError):
        raise ValueError(f"Rejilla de velocidades no válida: {ws_grid!r}.") from None
    if grid.ndim != 1 or grid.size == 0 or not np.all(np.isfinite(grid)) or np.any(np.diff(grid) <= 0):
        raise ValueError(f"La rejilla de velocidades tiene que ser finita, no vacía y estrictamente creciente: {ws_grid!r}.")
    if grid.size == 1:
        edges = grid + np.array([-0.5, 0.5])
    else:
        d = np.diff(grid) / 2
        edges = np.maximum(np.concatenate([grid[:1] - d[:1], grid[:-1] + d, grid[-1:] + d[-1:]]), 0)
    if np.any(np.diff(edges) <= 0):
        raise ValueError(f"La rejilla de velocidades deja bins sin anchura al recortar en 0: {ws_grid!r}.")
    return grid, edges


def _edge_value(xs, Y, v, from_right):
    """Row of ``Y`` at ``v`` seen from one side: at a repeated speed, the row of that side; between rows, interpolated."""
    same = np.flatnonzero(xs == v)
    if same.size:
        return Y[same[-1] if from_right else same[0]]
    i = np.searchsorted(xs, v, side="right") - 1
    w = (v - xs[i]) / (xs[i + 1] - xs[i])
    return Y[i] + (Y[i + 1] - Y[i]) * w


class _Table:
    """Piecewise-linear table ``Y[:, c]`` over ``xs`` (one column per density) with its exact primitive.

    Outside the table the values are flat, as ``np.interp``. With a band, the
    rows inside it are kept as they are (repeated speeds are jumps) and its
    edges are valued from inside; outside it, the power is zero.
    """

    def __init__(self, xs, Y, band):
        xs, Y = np.asarray(xs, dtype=float), np.asarray(Y, dtype=float)
        low, high = band if band is not None else (None, None)
        low = None if low is None else float(low)
        high = None if high is None else float(high)
        for edge in (low, high):
            if edge is not None and not xs[0] <= edge <= xs[-1]:
                raise ValueError(f"La banda de operación {band!r} no está dentro de la tabla ({xs[0]:g}–{xs[-1]:g} m/s).")
        if low is not None and high is not None and low > high:
            raise ValueError(f"La banda de operación {band!r} tiene el inferior mayor que el superior.")
        inside = np.ones(xs.size, dtype=bool)
        head, tail = [], []
        if low is not None:
            inside &= xs > low
            head = [(low, _edge_value(xs, Y, low, from_right=True))]
        if high is not None:
            inside &= xs < high
            tail = [(high, _edge_value(xs, Y, high, from_right=False))]
        rows = head + list(zip(xs[inside], Y[inside])) + tail
        self.xs = np.array([r[0] for r in rows], dtype=float)
        self.Y = np.array([r[1] for r in rows], dtype=float)
        if self.xs.size == 1:  # one row: flat everywhere
            self.xs, self.Y = np.r_[self.xs, self.xs], np.r_[self.Y, self.Y]
        self.low = -np.inf if low is None else low
        self.high = np.inf if high is None else high
        steps = (self.Y[1:] + self.Y[:-1]) / 2 * np.diff(self.xs)[:, None]
        self.C = np.concatenate([np.zeros((1, self.Y.shape[1])), np.cumsum(steps, axis=0)])

    def primitive(self, x, c):
        """Integral of column ``c`` from ``xs[0]`` to ``x``, zero-valued outside the band."""
        xs, Y = self.xs, self.Y
        x = np.clip(x, self.low, self.high)
        xin = np.clip(x, xs[0], xs[-1])
        i = np.clip(np.searchsorted(xs, xin, side="right") - 1, 0, xs.size - 2)
        h = xs[i + 1] - xs[i]
        dx = xin - xs[i]
        y0, y1 = Y[i, c], Y[i + 1, c]
        slope = np.divide(y1 - y0, h, out=np.zeros_like(dx), where=h > 0)
        return (self.C[i, c] + y0 * dx + 0.5 * slope * dx * dx
                + Y[0, c] * np.minimum(x - xs[0], 0) + Y[-1, c] * np.maximum(x - xs[-1], 0))


class _Cube:
    """Exact primitive of ``CubePowerSimpleCt``'s power."""

    def __init__(self, curve):
        self.ci, self.co = float(curve.ws_cutin), float(curve.ws_cutout)
        self.wr, self.pr = float(curve.ws_rated), float(curve.power_rated)

    def primitive(self, x, c):
        x = np.clip(x, self.ci, self.co)
        xa = np.minimum(x, self.wr)
        return self.pr * (xa - self.ci) ** 4 / (4 * (self.wr - self.ci) ** 3) + self.pr * np.maximum(x - self.wr, 0)


def _integral(curve):
    """The integral of a supported curve, its density axis (or ``None``), and its default density (or ``None``)."""
    from py_wake.wind_turbines.power_ct_functions import CubePowerSimpleCt, PowerCtNDTabular, PowerCtTabular

    band = getattr(curve, "operating_band", None)
    if isinstance(curve, PowerCtTabular) and curve.method == "linear":
        return _Table(curve.ws_tab, np.asarray(curve.power_ct_tab[0])[:, None], band), None, None
    if (isinstance(curve, PowerCtNDTabular) and list(curve.input_keys) == ["ws", "Air_density"]
            and curve.interp[0].method == "linear"):
        grid = curve.interp[0]
        V = np.asarray(grid.V, dtype=float)
        # Without the sentinel GridInterpolator appends to an irregular axis.
        ws, rho = np.asarray(grid.x[0][:V.shape[0]], float), np.asarray(grid.x[1][:V.shape[1]], float)
        return _Table(ws, V, band), rho, curve.default_value_dict.get("Air_density")
    if isinstance(curve, CubePowerSimpleCt):
        return _Cube(curve), None, None
    raise ValueError(f"La potencia media del bin no admite esta curva de potencia: {type(curve).__name__}.")


class _BinMeanPowerCt:
    """``power_ct`` of an adapted curve: the bin mean for the power (``run_only=0``), the original otherwise."""

    def __init__(self, curve, ws_grid):
        self.curve = curve
        self.grid, self.edges = bin_edges(ws_grid)
        self.integral, self.densities, self.default_density = _integral(curve)

    def __call__(self, ws, run_only, **kwargs):
        if run_only != 0:
            return self.curve.power_ct(ws, run_only=run_only, **kwargs)
        from py_wake.utils.model_utils import fix_shape

        if np.iscomplexobj(ws):
            raise TypeError("La potencia media del bin no admite velocidades complejas.")
        v = np.asarray(ws, dtype=float)
        k = np.clip(np.searchsorted(self.edges, v, side="right") - 1, 0, self.grid.size - 1)
        shift = v - self.grid[k]
        lo, hi = self.edges[k] + shift, self.edges[k + 1] + shift
        width = self.edges[k + 1] - self.edges[k]

        def mean(c):
            return (self.integral.primitive(hi, c) - self.integral.primitive(lo, c)) / width

        if self.densities is None:
            return mean(np.zeros(v.shape, dtype=int))
        rho = kwargs.get("Air_density")
        if rho is None:
            rho = self.default_density
        if rho is None:
            raise KeyError("Air_density")
        if np.iscomplexobj(rho):
            raise TypeError("La potencia media del bin no admite densidades complejas.")
        d = self.densities
        rho = np.clip(np.asarray(fix_shape(rho, v), dtype=float), d[0], d[-1])
        if d.size == 1:
            return mean(np.zeros(v.shape, dtype=int))
        j = np.clip(np.searchsorted(d, rho, side="right") - 1, 0, d.size - 2)
        w = (rho - d[j]) / (d[j + 1] - d[j])
        return (1 - w) * mean(j) + w * mean(j + 1)


def _original(pcf):
    """The curve an adapted copy was made from, or the curve itself."""
    power_ct = getattr(pcf, "power_ct", None)
    return power_ct.curve if isinstance(power_ct, _BinMeanPowerCt) else pcf


def bin_mean_power_ct(pcf, ws_grid):
    """Shallow copy of a supported curve whose power is the mean over the translated bin of ``ws_grid``.

    The Ct is the original's. The copy shares the original's tables and
    models, which neither modifies; the original is not changed. Adapting an
    adapted curve is adapting its original with the new grid.
    """
    base = _original(pcf)
    power_ct = _BinMeanPowerCt(base, ws_grid)
    out = copy.copy(base)
    out.power_ct = power_ct
    return out


def _type_list(pcf):
    from py_wake.wind_turbines.power_ct_functions import PowerCtFunctionList

    return isinstance(pcf, PowerCtFunctionList) and pcf.key == "type"


def simulation_wind_turbines(wt, ws_grid, mode=BIN_MEAN):
    """Copy of ``wt`` whose curves give the bin mean over ``ws_grid``; with ``POINT``, ``wt`` itself.

    The mode is checked before anything else, so ``POINT`` needs no grid.
    """
    if mode == POINT:
        return wt
    if mode != BIN_MEAN:
        raise ValueError(f"Modo de potencia del bin desconocido: {mode!r}.")
    if ws_grid is None:
        raise ValueError("La potencia media del bin necesita la rejilla de velocidades de la simulación.")
    pcf = wt.powerCtFunction
    if _type_list(pcf):
        adapted = copy.copy(pcf)
        adapted.windTurbineFunction_lst = [bin_mean_power_ct(f, ws_grid) for f in pcf.windTurbineFunction_lst]
        adapted.power_ct = adapted.__call__
    else:
        adapted = bin_mean_power_ct(pcf, ws_grid)
    out = copy.copy(wt)
    out.powerCtFunction = adapted
    return out


def check_grid(wt, ws_grid):
    """``ValueError`` if ``wt`` carries the bin mean of another grid than ``ws_grid`` (or ``ws_grid`` is ``None``).

    Turbines without the bin mean pass with any grid.
    """
    pcf = wt.powerCtFunction
    curves = pcf.windTurbineFunction_lst if _type_list(pcf) else [pcf]
    grids = [f.power_ct.grid for f in curves if isinstance(getattr(f, "power_ct", None), _BinMeanPowerCt)]
    if not grids:
        return
    if ws_grid is None:
        raise ValueError("Las turbinas tienen la potencia media de una rejilla y la simulación no da la suya.")
    simulated = np.atleast_1d(np.asarray(ws_grid, dtype=float))
    if not all(np.array_equal(g, simulated) for g in grids):
        raise ValueError("Las turbinas tienen la potencia media de otra rejilla que la que se simula.")

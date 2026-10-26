# -*- coding: utf-8 -*-
"""The computation directions and wind speeds of a WRG (options, initial choice, validation, grids) and the AEP hours.

A WRG gives its climate in N sectors. The AEP is computed on M directions, a
multiple of N up to 360 (or N alone when N > 360): every sector is divided into
m = M/N equal parts and computed at the centre of each one, so no direction
falls on a border between sectors and every sector gets the same number of
directions. The wind speeds cover the operating band of the turbines, with a
step chosen among a few options. This module is the only place with those
rules; it has no Qt and no PyWake.
"""

from __future__ import annotations

import math
import numbers

import numpy as np

from .log_text import log_error

WD_INTERP_METHODS = ("nearest", "linear")
MAX_DIRECTIONS = 360
SUBDIVISIONS_PER_SECTOR = 7
# The steps of the wind-speed grid (m/s), coarse to fine.
SPEED_STEPS = (1.0, 0.5, 0.25)
_EDGE_GAP_MS = 0.01  # gaps below this are the nodes a reader adds at the band edges, not the table's step


class WrgContractError(ValueError):
    """A request, a bundle, a Site or a worker payload that does not match the WRG configuration."""


def _is_count(value) -> bool:
    """A positive integer, Python or NumPy, and not a bool."""
    return isinstance(value, numbers.Integral) and not isinstance(value, (bool, np.bool_)) and int(value) > 0


def hours_per_year(resource_kind) -> float:
    """The hours an AEP is annualised with, by the kind of resource (not by the wake model).

    8760 (365·24) for IEA37, as the IEA Task 37 case study 3-4 computes its AEP;
    8766 (a Julian year of 365.25 days) for a WRG, a GRD and anything else. The
    one place in the package where these numbers are written.
    """
    return 8760.0 if str(resource_kind or "").strip().lower() == "iea37" else 8766.0


def direction_options(n_sectors: int) -> list[int]:
    """The multiples of N up to 360; N alone when N > 360."""
    n = int(n_sectors)
    if n > MAX_DIRECTIONS:
        return [n]
    return [n * m for m in range(1, MAX_DIRECTIONS // n + 1)]


def initial_direction_count(n_sectors: int) -> int:
    """7N when 7N <= 360; N otherwise."""
    n = int(n_sectors)
    return SUBDIVISIONS_PER_SECTOR * n if SUBDIVISIONS_PER_SECTOR * n <= MAX_DIRECTIONS else n


def validate_request(n_sectors, direction_count, method, source: str) -> None:
    """Raise ``WrgContractError`` unless M is one of the options of N and the method is nearest or linear.

    Nothing is rounded or replaced: a float, a bool, NaN, an infinity, zero or
    a negative number is refused as it comes. ``source`` names the WRG (and the
    ZIP member) in the message.
    """
    if not _is_count(n_sectors):
        raise log_error(
            WrgContractError, "Número de sectores no válido: {n_sectors} en el WRG «{source}» (direcciones pedidas: "
            "{count}). Debe ser un entero positivo.", n_sectors=repr(n_sectors), source=source, count=repr(direction_count),
        )
    n = int(n_sectors)
    if not _is_count(direction_count) or int(direction_count) not in direction_options(n):
        if n > MAX_DIRECTIONS:
            raise log_error(
                WrgContractError, "Número de direcciones no válido: {count}. El WRG «{source}» contiene {n} sectores; al "
                "superar el límite de {max}, la única opción admitida es conservar sus {n} direcciones.",
                count=repr(direction_count), source=source, n=n, max=MAX_DIRECTIONS,
            )
        raise log_error(
            WrgContractError, "Número de direcciones no válido: {count}. Debe ser un múltiplo entero positivo de {n}, el "
            "número de sectores del WRG «{source}», sin superar {max}.", count=repr(direction_count), n=n, source=source,
            max=MAX_DIRECTIONS,
        )
    if not isinstance(method, str) or method not in WD_INTERP_METHODS:
        raise log_error(
            WrgContractError, "Interpolación direccional no válida: {method} para el WRG «{source}» ({n} sectores, {count} "
            "direcciones). Se admiten {first} y {second}.", method=repr(method), source=source, n=n,
            count=int(direction_count), first=WD_INTERP_METHODS[0], second=WD_INTERP_METHODS[1],
        )


def interp_methods(wd_interp: str) -> dict:
    """The XRSite interpolation: ``wd_interp`` on the direction, linear on x, y and h."""
    return {"wd": wd_interp, "x": "linear", "y": "linear", "h": "linear"}


def direction_grid(n_sectors: int, direction_count: int) -> np.ndarray:
    """The M centres of subdivision, sorted, in [0, 360), float64.

    Sector i spans [c - S/2, c + S/2] with S = 360/N and c = i·S; it is divided
    into m = M/N equal parts and each part gives its centre. With m odd the
    sector centres are among them; it is not ``arange(M)·360/M`` when m is even.
    Each angle is 360·((2j + 1)·N − M) / (2·M·N) with integer numerators, so
    it is rounded once (sector centres come out exact).
    """
    n, m_total = int(n_sectors), int(direction_count)
    if n <= 0 or m_total <= 0 or m_total % n:
        raise log_error(WrgContractError, "Malla de direcciones imposible: {count} direcciones con {n} sectores.",
                        count=m_total, n=n)
    j = np.arange(m_total, dtype=np.int64)
    numerator = 360 * ((2 * j + 1) * n - m_total)
    grid = np.mod(numerator / float(2 * m_total * n), 360.0)
    grid[grid >= 360.0] = 0.0  # a -0.0 or a tiny negative rounds up to 360.0
    return np.sort(grid).astype(np.float64)


def validate_speed_step(step, source: str) -> float:
    """``step`` as a float if it is exactly one of ``SPEED_STEPS``; ``WrgContractError`` otherwise, never rounded."""
    ok = (isinstance(step, numbers.Real) and not isinstance(step, (bool, np.bool_))
          and math.isfinite(float(step)) and float(step) in SPEED_STEPS)
    if not ok:
        raise log_error(
            WrgContractError, "Paso de velocidad no válido: {step} para «{source}». Se admiten {steps} m/s.",
            step=repr(step), source=source, steps=", ".join(f"{s:g}" for s in SPEED_STEPS),
        )
    return float(step)


def curve_band(ws, power, band=None) -> tuple[float, float]:
    """The operating band of a tabulated curve, closed: ``(low, high)``.

    ``band`` is the one the curve declares, ``(low, high)`` with ``None`` at
    an open end, or ``None``; an open end closes at the first or last node.
    The band is used as it is: rows of zero power inside it are kept, since a
    row with zero power and a positive Ct still makes a wake. A curve with zero
    power at every node has no band to cover.
    """
    nodes = np.asarray(ws, dtype=float).reshape(-1)
    if nodes.size == 0 or not np.all(np.isfinite(nodes)):
        raise log_error(WrgContractError, "La curva de la turbina no tiene velocidades tabuladas válidas.")
    if not np.any(np.asarray(power, dtype=float) > 0.0):
        raise log_error(WrgContractError,
                        "La curva de la turbina tiene potencia cero en todos sus nodos: no hay banda que cubrir.")
    low, high = (None, None) if band is None else band
    low = float(nodes.min()) if low is None else float(low)
    high = float(nodes.max()) if high is None else float(high)
    if not (math.isfinite(low) and math.isfinite(high) and 0.0 <= low < high):
        raise log_error(WrgContractError, "Banda de operación no válida: {low}–{high} m/s.", low=f"{low:g}", high=f"{high:g}")
    return low, high


def initial_speed_step(curves) -> float:
    """The initial step: from each curve's ``(nodes, (low, high))``, the finest; 1 if no curve gives one.

    For a curve, the gaps between consecutive nodes inside its band, rounded to
    1e-6 m/s and without those below 0.01 m/s (the nodes a reader adds at the
    band edges); the most frequent one (the smaller on a tie), taken to the
    nearest option (the finer when it is halfway). ``nodes=None`` (an analytic
    curve) or no usable gap gives 1.
    """
    steps = []
    for nodes, (low, high) in curves:
        step = SPEED_STEPS[0]
        if nodes is not None:
            x = np.unique(np.asarray(nodes, dtype=float))
            x = x[(x >= low) & (x <= high)]
            gaps = np.round(np.diff(x), 6)
            gaps = gaps[gaps >= _EDGE_GAP_MS]
            if gaps.size:
                values, counts = np.unique(gaps, return_counts=True)
                gap = float(values[counts == counts.max()].min())
                step = min(SPEED_STEPS, key=lambda s: (abs(s - gap), s))
        steps.append(step)
    return min(steps, default=SPEED_STEPS[0])


def speed_grid(low: float, high: float, step: float) -> np.ndarray:
    """The multiples of ``step`` whose bins cover ``[low, high]``, float64.

    From the bin that holds the cut-in (the one that starts at it, on a border)
    to the one that holds the cut-out (the one that ends at it, on a border);
    1e-9 keeps an exact border from changing bin. At least two values: with
    one, PyWake and ``bin_edges`` give a bin 1 m/s wide whatever the step.
    """
    s = float(step)
    k0 = math.floor(float(low) / s + 0.5 + 1e-9)
    k1 = math.ceil(float(high) / s - 0.5 - 1e-9)
    k1 = max(k1, k0 + 1)
    return np.arange(k0, k1 + 1, dtype=np.int64) * s

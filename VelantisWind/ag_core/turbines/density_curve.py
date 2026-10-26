# -*- coding: utf-8 -*-
"""Format-agnostic power/Ct curve families tabulated by air density.

A turbine's power and thrust curves depend on air density, and manufacturers
publish them as a *family*, one curve per density, rather than as a single
curve. Each turbine of a wind farm sits at a different hub altitude and sees a
different density, so one curve for the whole farm biases its energy.

`TurbineCurveTable` holds such a family, with its validation and interpolation
helpers. Nothing here knows about any file format.

Adapter contract
----------------
Every reader of a density-tabulated format (``wtg.py`` today, others later):

* produces a `TurbineCurveTable`;
* validates strictly: whatever does not match the structure it supports is
  rejected with a message naming the offending element, never guessed;
* does not resample to reconcile incompatible grids: tables that do not share
  their wind-speed grid are rejected, not interpolated onto a common one.

CSV and manual curves do not come through here: they carry one curve and keep
the 1-D path (``build_wt_from_manual``), which applies the same rules (band,
no ``DensityScale``, validated Ct).

Error messages are Spanish templates with their data apart (``template_item``),
so the interface can translate them; notes carry their template the same way.
"""
from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import List, Optional, Sequence, Tuple
import math

from ..log_text import log_text
from ..turbine import CT_MAX_PLAUSIBLE, _error

__all__ = [
    "CurveTableError",
    "TurbineCurveTable",
    "BAND_EDGE_EPS_MS",
]

# Wind-speed nudge used to place an explicit zero immediately outside the declared
# operating band. Physically invisible (0.1 mm/s) but coarse enough to survive a
# float32 grid, unlike the 1e-8 that PyWake uses for its own 1-D curves.
BAND_EDGE_EPS_MS = 1e-4

# A declared cut-in or cut-out beyond the tabulated wind speeds by more than this
# means the table does not cover its own band.
_BAND_TOLERANCE_MS = 1e-6


class CurveTableError(ValueError):
    """Raised when a curve family is missing, malformed or physically implausible."""


def _is_finite(value) -> bool:
    try:
        return math.isfinite(float(value))
    except (TypeError, ValueError, OverflowError):
        return False


def _check_strictly_increasing(values: Sequence[float], label: str) -> None:
    for i in range(1, len(values)):
        if not values[i] > values[i - 1]:
            raise _error(
                CurveTableError,
                "{label} debe ser estrictamente creciente, pero el valor {index} ({value:g}) "
                "no es mayor que el anterior ({previous:g}).",
                label=label, index=i, value=values[i], previous=values[i - 1],
            )


@dataclass(frozen=True)
class TurbineCurveTable:
    """Power and Ct of one turbine model, tabulated over wind speed and air density.

    ``power_kw[i][j]`` and ``ct[i][j]`` hold the value for wind speed
    ``wind_speeds_ms[i]`` and air density ``air_densities[j]``. A family with a
    single density column is valid: it means there is nothing to interpolate,
    not that the curve does not depend on density.

    ``default_air_density`` is the density used when nobody supplies another
    one: a density the file declares, or the one a reader takes by policy.
    ``cut_in_ms``/``cut_out_ms`` are the operating band the file declares; it
    must lie within the tabulated wind speeds.
    """

    name: str
    diameter_m: float
    hub_height_m: float
    wind_speeds_ms: Tuple[float, ...]
    air_densities: Tuple[float, ...]
    power_kw: Tuple[Tuple[float, ...], ...]
    ct: Tuple[Tuple[float, ...], ...]
    default_air_density: Optional[float] = None
    rated_power_kw: Optional[float] = None
    cut_in_ms: Optional[float] = None
    cut_out_ms: Optional[float] = None
    source_format: str = ""
    source_path: str = ""
    notes: Tuple[str, ...] = field(default_factory=tuple)

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------
    def __post_init__(self) -> None:
        if not str(self.name).strip():
            raise _error(CurveTableError, "La turbina necesita un nombre no vacío.")

        for label, value in ((log_text("El diámetro de rotor"), self.diameter_m),
                             (log_text("La altura de buje"), self.hub_height_m)):
            if not _is_finite(value) or float(value) <= 0.0:
                raise _error(
                    CurveTableError,
                    "{label} debe ser un número positivo; se recibió {value!r}.",
                    label=label, value=value,
                )

        n_ws = len(self.wind_speeds_ms)
        n_rho = len(self.air_densities)
        if n_ws < 2:
            raise _error(
                CurveTableError,
                "La curva necesita al menos 2 velocidades de viento; se recibieron {n}.",
                n=n_ws,
            )
        if n_rho < 1:
            raise _error(CurveTableError, "La curva necesita al menos una densidad de aire.")

        for i, ws in enumerate(self.wind_speeds_ms):
            if not _is_finite(ws) or float(ws) < 0.0:
                raise _error(
                    CurveTableError,
                    "Velocidad de viento no válida en la posición {index}: {value!r}.",
                    index=i, value=ws,
                )
        _check_strictly_increasing(self.wind_speeds_ms, log_text("La lista de velocidades de viento"))

        for j, rho in enumerate(self.air_densities):
            if not _is_finite(rho) or float(rho) <= 0.0:
                raise _error(
                    CurveTableError,
                    "Densidad de aire no válida en la posición {index}: {value!r}.",
                    index=j, value=rho,
                )
        _check_strictly_increasing(self.air_densities, log_text("La lista de densidades de aire"))

        self._check_matrix(self.power_kw, log_text("potencia"), maximum=None)
        self._check_matrix(self.ct, log_text("Ct"), maximum=CT_MAX_PLAUSIBLE)

        # A curve whose thrust is zero everywhere is not a turbine: at that density
        # it would run without ever shading anything, so wake losses would silently
        # come out as zero. Each density is a curve of its own, so each is checked.
        for j, rho in enumerate(self.air_densities):
            for label, matrix in ((log_text("Ct"), self.ct), (log_text("potencia"), self.power_kw)):
                if max(float(row[j]) for row in matrix) <= 0.0:
                    raise _error(
                        CurveTableError,
                        "La curva de {label} a {rho:g} kg/m³ es cero en todos los puntos: con ella la turbina no "
                        "produce ni genera estela.",
                        label=label, rho=float(rho),
                    )

        for label, value in ((log_text("La densidad por defecto"), self.default_air_density),
                             (log_text("La potencia nominal"), self.rated_power_kw)):
            if value is not None and (not _is_finite(value) or float(value) <= 0.0):
                raise _error(
                    CurveTableError,
                    "{label} debe ser un número positivo; se recibió {value!r}.",
                    label=label, value=value,
                )

        for label, value in ((log_text("El cut-in"), self.cut_in_ms), (log_text("El cut-out"), self.cut_out_ms)):
            if value is not None and (not _is_finite(value) or float(value) < 0.0):
                raise _error(
                    CurveTableError,
                    "{label} debe ser un número finito no negativo; se recibió {value!r}.",
                    label=label, value=value,
                )
        if self.cut_in_ms is not None and self.cut_out_ms is not None:
            if not float(self.cut_in_ms) < float(self.cut_out_ms):
                raise _error(
                    CurveTableError,
                    "El cut-in ({cut_in:g} m/s) debe ser menor que el cut-out ({cut_out:g} m/s).",
                    cut_in=float(self.cut_in_ms), cut_out=float(self.cut_out_ms),
                )
        # The band decides where the machine produces. A declared edge outside the
        # tabulated speeds leaves part of the band without data (or puts it where
        # there is none), and the band enforcement below only acts on edges inside
        # the table, so it is refused.
        ws_low, ws_high = float(self.wind_speeds_ms[0]), float(self.wind_speeds_ms[-1])
        for label, value in ((log_text("El cut-in"), self.cut_in_ms), (log_text("El cut-out"), self.cut_out_ms)):
            if value is not None and not (ws_low - _BAND_TOLERANCE_MS <= float(value) <= ws_high + _BAND_TOLERANCE_MS):
                raise _error(
                    CurveTableError,
                    "{label} declarado ({value:g} m/s) queda fuera de las velocidades tabuladas ({low:g}–{high:g} m/s): "
                    "la tabla no cubre su propia banda de operación.",
                    label=label, value=float(value), low=ws_low, high=ws_high,
                )

    def _check_matrix(self, matrix: Sequence[Sequence[float]], label: str, *, maximum: Optional[float]) -> None:
        n_ws, n_rho = len(self.wind_speeds_ms), len(self.air_densities)
        if len(matrix) != n_ws:
            raise _error(
                CurveTableError,
                "La tabla de {label} tiene {rows} filas y se esperaban {expected} (una por "
                "velocidad de viento).",
                label=label, rows=len(matrix), expected=n_ws,
            )
        for i, row in enumerate(matrix):
            if len(row) != n_rho:
                raise _error(
                    CurveTableError,
                    "La fila de {ws:g} m/s de la tabla de {label} tiene {columns} columnas y se "
                    "esperaban {expected} (una por densidad de aire).",
                    ws=float(self.wind_speeds_ms[i]), label=label, columns=len(row), expected=n_rho,
                )
            for j, value in enumerate(row):
                point = dict(label=label, ws=float(self.wind_speeds_ms[i]), rho=float(self.air_densities[j]))
                if not _is_finite(value):
                    raise _error(
                        CurveTableError,
                        "Valor de {label} no numérico a {ws:g} m/s y {rho:g} kg/m³: {value!r}.",
                        value=value, **point,
                    )
                v = float(value)
                if v < 0.0:
                    raise _error(
                        CurveTableError,
                        "Valor de {label} negativo a {ws:g} m/s y {rho:g} kg/m³: {value:g}.",
                        value=v, **point,
                    )
                if maximum is not None and v > maximum:
                    raise _error(
                        CurveTableError,
                        "Valor de {label} fuera de rango a {ws:g} m/s y {rho:g} kg/m³: {value:g} > "
                        "{maximum:g}. {maximum:g} no es un techo físico, sino el umbral de admisión "
                        "a partir del cual hay que revisar el dato.",
                        value=v, maximum=maximum, **point,
                    )

    # ------------------------------------------------------------------
    # Introspection
    # ------------------------------------------------------------------
    @property
    def n_wind_speeds(self) -> int:
        return len(self.wind_speeds_ms)

    @property
    def n_densities(self) -> int:
        return len(self.air_densities)

    @property
    def is_density_dependent(self) -> bool:
        """True when the family actually carries more than one density column."""
        return self.n_densities > 1

    @property
    def density_range(self) -> Tuple[float, float]:
        return float(self.air_densities[0]), float(self.air_densities[-1])

    @property
    def wind_speed_range(self) -> Tuple[float, float]:
        return float(self.wind_speeds_ms[0]), float(self.wind_speeds_ms[-1])

    @property
    def max_power_kw(self) -> float:
        return max(max(float(v) for v in row) for row in self.power_kw)

    # ------------------------------------------------------------------
    # Interpolation
    # ------------------------------------------------------------------
    def clamp_density(self, air_density: float) -> Tuple[float, bool]:
        """Clamp ``air_density`` into the tabulated range.

        Returns ``(value, was_clamped)``. Clamping is preferred over
        extrapolation: outside the tabulated range the manufacturer data does
        not say anything, and extrapolating a power curve invents output.
        """
        if not _is_finite(air_density):
            raise _error(CurveTableError, "Densidad de aire no numérica: {value!r}.", value=air_density)
        rho = float(air_density)
        low, high = self.density_range
        if rho < low:
            return low, True
        if rho > high:
            return high, True
        return rho, False

    def curve_at_density(self, air_density: float) -> Tuple[List[float], List[float], List[float]]:
        """Return ``(ws, power_kw, ct)`` linearly interpolated at one density, clamped to the table.

        This is the 1-D slice used for previews and single-density families. The
        simulation itself does not use it: there the whole family is handed to
        PyWake, which interpolates per turbine.
        """
        rho, _ = self.clamp_density(air_density)
        densities = self.air_densities
        if len(densities) == 1:
            j0 = j1 = 0
            weight = 0.0
        else:
            j1 = len(densities) - 1
            for j in range(1, len(densities)):
                if rho <= densities[j]:
                    j1 = j
                    break
            j0 = j1 - 1
            weight = (rho - densities[j0]) / (densities[j1] - densities[j0])

        def _at(row: Sequence[float]) -> float:
            return float(row[j0]) + (float(row[j1]) - float(row[j0])) * weight

        return (
            [float(v) for v in self.wind_speeds_ms],
            [_at(row) for row in self.power_kw],
            [_at(row) for row in self.ct],
        )

    # ------------------------------------------------------------------
    # Operating band
    # ------------------------------------------------------------------
    def _row_at(self, matrix: Sequence[Sequence[float]], target: float) -> List[float]:
        """Linear interpolation of every density column at one wind speed inside the table."""
        ws = self.wind_speeds_ms
        for i in range(1, len(ws)):
            if target <= ws[i]:
                lo, hi = float(ws[i - 1]), float(ws[i])
                weight = (target - lo) / (hi - lo)
                return [
                    float(a) + (float(b) - float(a)) * weight
                    for a, b in zip(matrix[i - 1], matrix[i])
                ]
        return [float(v) for v in matrix[-1]]

    def with_operating_band_enforced(self) -> "TurbineCurveTable":
        """Return a copy that produces nothing outside the declared cut-in/cut-out.

        A table and the band the same file declares can disagree: the table may
        extend past the cut-out, or reach its first non-zero value at the cut-in
        while tabulating a zero just below it. Both make the turbine produce where
        the real machine is stopped, because every consumer interpolates linearly
        between tabulated points:

        * beyond a cut-out inside the table the machine keeps producing at full
          power *and* keeps casting a wake;
        * across the cut-in the curve ramps up from the last tabulated zero
          instead of stepping, which credits energy in the band where the Weibull
          density is highest.

        The declared band wins over the tabulated grid: values outside it are
        forced to zero and an explicit zero node is placed one
        ``BAND_EDGE_EPS_MS`` outside each edge, so the transition is a step and
        not a ramp. An edge that falls between two nodes is interpolated there.
        Returns ``self`` unchanged when the table already agrees with its band.
        Idempotent.
        """
        if self.cut_in_ms is None and self.cut_out_ms is None:
            return self

        ws = [float(v) for v in self.wind_speeds_ms]
        power = [[float(v) for v in row] for row in self.power_kw]
        ct = [[float(v) for v in row] for row in self.ct]
        zeros = [0.0] * len(self.air_densities)

        nodes = {w: (power[i], ct[i]) for i, w in enumerate(ws)}

        def _add_edge(edge: float, outside: float) -> None:
            if edge not in nodes:
                nodes[edge] = (self._row_at(self.power_kw, edge), self._row_at(self.ct, edge))
            nodes[outside] = (list(zeros), list(zeros))

        cut_in = None if self.cut_in_ms is None else float(self.cut_in_ms)
        cut_out = None if self.cut_out_ms is None else float(self.cut_out_ms)

        if cut_in is not None and cut_in > ws[0]:
            _add_edge(cut_in, cut_in - BAND_EDGE_EPS_MS)
        if cut_out is not None and cut_out < ws[-1]:
            _add_edge(cut_out, cut_out + BAND_EDGE_EPS_MS)

        out_ws: List[float] = sorted(nodes)
        out_power: List[List[float]] = []
        out_ct: List[List[float]] = []
        for w in out_ws:
            p_row, c_row = nodes[w]
            idle = (cut_in is not None and w < cut_in) or (cut_out is not None and w > cut_out)
            out_power.append(list(zeros) if idle else list(p_row))
            out_ct.append(list(zeros) if idle else list(c_row))

        if out_ws == ws and out_power == power and out_ct == ct:
            return self

        note = log_text(
            "Curva recortada a la banda declarada por el propio fichero ({cut_in}–{cut_out} m/s): "
            "fuera de ella la potencia y el Ct son cero.",
            cut_in="—" if cut_in is None else format(cut_in, "g"),
            cut_out="—" if cut_out is None else format(cut_out, "g"),
        )
        return replace(
            self,
            wind_speeds_ms=tuple(out_ws),
            power_kw=tuple(tuple(row) for row in out_power),
            ct=tuple(tuple(row) for row in out_ct),
            notes=tuple(self.notes) + (note,),
        )

    def describe(self) -> str:
        """One-line summary, used in logs and labels."""
        low, high = self.density_range
        ws_low, ws_high = self.wind_speed_range
        if self.is_density_dependent:
            return log_text(
                "{name}: D={diameter:g} m, HH={hub:g} m, {n_ws} velocidades {ws_low:g}–{ws_high:g} m/s, "
                "{n_rho} densidades {low:.3f}–{high:.3f} kg/m³",
                name=self.name, diameter=self.diameter_m, hub=self.hub_height_m, n_ws=self.n_wind_speeds,
                ws_low=ws_low, ws_high=ws_high, n_rho=self.n_densities, low=low, high=high,
            )
        return log_text(
            "{name}: D={diameter:g} m, HH={hub:g} m, {n_ws} velocidades {ws_low:g}–{ws_high:g} m/s, "
            "densidad única {low:.3f} kg/m³",
            name=self.name, diameter=self.diameter_m, hub=self.hub_height_m, n_ws=self.n_wind_speeds,
            ws_low=ws_low, ws_high=ws_high, low=low,
        )

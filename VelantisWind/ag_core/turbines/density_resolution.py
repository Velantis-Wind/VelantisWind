# -*- coding: utf-8 -*-
"""Which air density each turbine receives, decided once for every consumer.

Each consumer applies only its own error policy to `AirDensityError`:

* the AEP stops: an AEP at the wrong density is a false number;
* a wake map warns with the real cause and goes on, because a map must not cost
  a whole run.

Modes, with the reference (density and the altitude it is given at) always a
project input:

* ``"off"``: no density is passed; each density table is evaluated at its own
  default density, and the result says which one, per type and position;
* ``"uniform"``: the reference density at every turbine;
* ``"per_turbine"``: the calibrated ISA profile at each hub (terrain elevation
  of the resource plus the real hub height).

Each turbine's density is clamped to the table of its own type, with a warning,
and never extrapolated. Curves without a density table never receive
``Air_density`` and are not corrected for density (deferred on purpose).

Depends only on numpy and on duck-typed PyWake objects.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence, Tuple

import numpy as np

from ..log_text import log_text
from ..physics.air_density import (
    AirDensityError,
    SiteAirDensityError,
    air_density_per_turbine,
    site_defines_air_density,
    terrain_elevation_from_site,
)
from ..turbine import _error

__all__ = [
    "AIR_DENSITY_INPUT",
    "AIR_DENSITY_MODES",
    "AirDensityDecision",
    "consumes_air_density",
    "density_tables_by_type",
    "resolve_air_density",
]

AIR_DENSITY_INPUT = "Air_density"
OFF, UNIFORM, PER_TURBINE = "off", "uniform", "per_turbine"
AIR_DENSITY_MODES = (OFF, UNIFORM, PER_TURBINE)


@dataclass(frozen=True)
class AirDensityDecision:
    """What the simulation receives and what the result reports.

    ``values`` is the ``Air_density`` array to pass to the simulation, one value
    per turbine, or ``None`` to pass nothing. ``info`` describes the treatment
    for the result (``None`` when density plays no role); ``warnings`` must be
    shown as warnings and ``notes`` are informative.
    """

    values: Optional[np.ndarray] = None
    info: Optional[Dict[str, Any]] = None
    warnings: Tuple[str, ...] = field(default_factory=tuple)
    notes: Tuple[str, ...] = field(default_factory=tuple)


def _type_curves(wt: Any) -> List[Any]:
    """The power/Ct function of each turbine type, in type order."""
    pcf = getattr(wt, "powerCtFunction", None)
    items = getattr(pcf, "windTurbineFunction_lst", None)
    if items is not None and getattr(pcf, "key", None) == "type":
        return list(items)
    return [pcf]


def _density_table(curve: Any) -> Optional[Tuple[float, float, Optional[float]]]:
    """``(low, high, default)`` of a curve tabulated by air density, ``None`` otherwise."""
    keys = [str(k) for k in (getattr(curve, "input_keys", None) or [])]
    interp = getattr(curve, "interp", None)
    if AIR_DENSITY_INPUT not in keys or not interp:
        return None
    axis = np.asarray(interp[0].x[keys.index(AIR_DENSITY_INPUT)], dtype=float)
    default = (getattr(curve, "default_value_dict", None) or {}).get(AIR_DENSITY_INPUT)
    return float(np.min(axis)), float(np.max(axis)), (None if default is None else float(default))


def _declares_air_density(curve: Any) -> bool:
    inputs = list(getattr(curve, "required_inputs", None) or []) + list(getattr(curve, "optional_inputs", None) or [])
    return AIR_DENSITY_INPUT in inputs


def density_tables_by_type(wt: Any) -> List[Optional[Tuple[float, float, Optional[float]]]]:
    """``(low, high, default)`` of the density table of each turbine type, ``None`` for curves without one."""
    return [_density_table(curve) for curve in _type_curves(wt)]


def consumes_air_density(wt: Any) -> bool:
    """True when some turbine type of the park is tabulated by air density."""
    return any(table is not None for table in density_tables_by_type(wt))


def _type_names(wt: Any, indices: Sequence[int]) -> str:
    names = []
    for i in indices:
        try:
            names.append(str(wt.name(int(i))))
        except Exception:
            names.append(str(int(i) + 1))
    return ", ".join(names)


def _hub_heights(wt: Any, types: np.ndarray) -> np.ndarray:
    """Real hub height of each turbine; never a default, because it sets the hub altitude."""
    try:
        hubs = np.asarray(wt.hub_height(types), dtype=float).ravel()
    except Exception:
        hubs = np.array([], dtype=float)
    if hubs.size != types.size or not np.all(np.isfinite(hubs)) or np.any(hubs <= 0.0):
        raise _error(
            AirDensityError,
            "No se pudo leer la altura de buje de la turbina, y sin ella la cota de cada buje (y por tanto su "
            "densidad de aire) sería inventada. Define la altura de buje en el modelo de turbina o desactiva el "
            "ajuste por densidad.",
        )
    return hubs


def _range_text(values: Sequence[float]) -> str:
    low, high = min(values), max(values)
    return f"{low:.4f} kg/m³" if abs(high - low) < 5e-5 else f"{low:.4f}–{high:.4f} kg/m³"


def _mode(mode: Any) -> str:
    value = OFF if mode is None else str(mode).strip().lower()
    if value not in AIR_DENSITY_MODES:
        raise _error(AirDensityError, "Modo de densidad de aire no reconocido: {mode!r}.", mode=mode)
    return value


def resolve_air_density(
    *,
    site: Any,
    wt: Any,
    xs: Sequence[float],
    ys: Sequence[float],
    type_i: Optional[Sequence[int]] = None,
    mode: Any = OFF,
    reference_density: Optional[float] = None,
    reference_altitude_m: Optional[float] = None,
) -> AirDensityDecision:
    """Decide the air density of every turbine of a layout.

    Raises `AirDensityError` (`SiteAirDensityError` when the resource defines its
    own ``Air_density``) whenever the density cannot be established reliably;
    each consumer decides whether that stops it.
    """
    mode = _mode(mode)
    tables = density_tables_by_type(wt)
    n = len(np.asarray(xs).ravel())
    types = np.zeros(n, dtype=int) if type_i is None else np.asarray(type_i, dtype=int).ravel()
    if types.size != n:
        raise _error(
            AirDensityError, "El vector de tipos tiene {n_types} elementos para {n} turbinas.", n_types=types.size, n=n,
        )

    if types.size and (types.min() < 0 or types.max() >= len(tables)):
        raise _error(AirDensityError, "El vector de tipos no corresponde a los {n} tipos del parque.", n=len(tables))
    in_use = sorted(set(types.tolist()))
    curves = _type_curves(wt)
    # PyWake resolves the variables of the site before the arguments of the call,
    # so its own Air_density would reach every curve that accepts one, replacing
    # the density decided here without an error: the result would state a density
    # that was not used, or a curve would be rescaled without asking.
    if site_defines_air_density(site) and any(_declares_air_density(curves[t]) for t in in_use):
        raise _error(
            SiteAirDensityError,
            "El recurso define su propia variable 'Air_density', que PyWake antepone a la densidad de cada "
            "turbina: el cálculo no usaría la densidad que dice usar. Elimina esa variable del recurso.",
        )
    if not any(tables[t] is not None for t in in_use):
        if mode == OFF:
            return AirDensityDecision()
        return AirDensityDecision(warnings=(log_text(
            "Se pidió ajustar las curvas a la densidad del aire, pero ninguna curva del parque está tabulada por "
            "densidad: se usan tal cual, sin corregir."
        ),))

    ranges = [None if t is None else [t[0], t[1]] for t in tables]
    if mode == OFF:
        used = [None if tables[t] is None else tables[t][2] for t in types]
        known = [v for v in used if v is not None]
        info = {
            "mode": OFF,
            "reference_density_kg_m3": None,
            "reference_altitude_m": None,
            "values_kg_m3": used,
            "terrain_elevation_m": None,
            "hub_altitude_m": None,
            "clamped": [False] * n,
            "n_clamped": 0,
            "table_range_by_type": ranges,
            "min_kg_m3": min(known) if known else None,
            "max_kg_m3": max(known) if known else None,
            "mean_kg_m3": float(np.mean(known)) if known else None,
            "summary": log_text(
                "ajuste por densidad desactivado: cada turbina usa la densidad por defecto de su curva ({densities})",
                densities=_range_text(known) if known else "n/d",
            ),
        }
        return AirDensityDecision(info=info, warnings=(log_text(
            "Las curvas de potencia están tabuladas por densidad, pero el ajuste está desactivado: cada turbina se "
            "evalúa a la densidad por defecto de su curva ({densities}), sin tener en cuenta la cota de su buje.",
            densities=_range_text(known) if known else "n/d",
        ),))

    rescaled = [t for t in in_use if tables[t] is None and _declares_air_density(curves[t])]
    if rescaled:
        raise _error(
            AirDensityError,
            "La curva de {names} no está tabulada por densidad pero acepta 'Air_density' para reescalar su "
            "potencia y su Ct: recibiría la densidad de cada turbina y se corregiría sin pedirlo.",
            names=_type_names(wt, rescaled),
        )
    if reference_density is None:
        raise _error(AirDensityError, "Falta la densidad de aire de referencia del proyecto.")
    try:
        reference = float(reference_density)
    except (TypeError, ValueError):
        reference = float("nan")
    if not np.isfinite(reference) or reference <= 0.0:
        raise _error(
            AirDensityError, "La densidad de referencia debe ser un número positivo; se recibió {value!r}.",
            value=reference_density,
        )

    terrain = hub_altitude = None
    if mode == UNIFORM:
        density = np.full(n, reference, dtype=float)
    else:
        if reference_altitude_m is None:
            raise _error(
                AirDensityError,
                "Falta la altitud (m s.n.m.) a la que está dada la densidad de referencia; sin ella no se puede "
                "calcular la densidad en la cota de cada buje.",
            )
        terrain = terrain_elevation_from_site(site, xs, ys)
        density, hub_altitude = air_density_per_turbine(
            terrain, _hub_heights(wt, types),
            reference_density=reference, reference_altitude_m=reference_altitude_m,
        )

    values = np.array(density, dtype=float)
    used: List[Optional[float]] = []
    clamped = np.zeros(n, dtype=bool)
    for k, t in enumerate(types):
        table = tables[t]
        if table is None:
            used.append(None)
            continue
        values[k] = min(max(values[k], table[0]), table[1])
        clamped[k] = values[k] != density[k]
        used.append(float(values[k]))

    warnings = []
    notes = []
    known = [v for v in used if v is not None]
    n_clamped = int(np.count_nonzero(clamped))
    if n_clamped:
        warnings.append(log_text(
            "{n} turbina(s) quedan fuera del rango de densidad tabulado por su curva y se acotan a su extremo, "
            "sin extrapolar.",
            n=n_clamped,
        ))
    one_density = sorted({int(t) for t in types if tables[t] is None})
    if one_density:
        notes.append(log_text(
            "Las turbinas de {names} tienen una curva de una sola densidad: no se corrigen con la densidad del aire.",
            names=_type_names(wt, one_density),
        ))

    if mode == UNIFORM:
        summary = log_text("densidad uniforme {reference:.4f} kg/m³", reference=reference)
    else:
        summary = log_text(
            "densidad por turbina (ISA calibrado, referencia {reference:.4f} kg/m³ a {altitude:g} m s.n.m.): "
            "{densities}; cota de buje {low:.0f}–{high:.0f} m s.n.m.",
            reference=reference, altitude=float(reference_altitude_m), densities=_range_text(known),
            low=float(np.min(hub_altitude)), high=float(np.max(hub_altitude)),
        )
    if n_clamped:
        summary = log_text("{summary}; {n} turbina(s) acotada(s) al rango de su curva", summary=summary, n=n_clamped)
    info = {
        "mode": mode,
        "reference_density_kg_m3": reference,
        "reference_altitude_m": None if mode == UNIFORM else float(reference_altitude_m),
        "values_kg_m3": used,
        "terrain_elevation_m": None if terrain is None else [float(v) for v in terrain],
        "hub_altitude_m": None if hub_altitude is None else [float(v) for v in hub_altitude],
        "clamped": [bool(v) for v in clamped],
        "n_clamped": n_clamped,
        "table_range_by_type": ranges,
        "min_kg_m3": min(known),
        "max_kg_m3": max(known),
        "mean_kg_m3": float(np.mean(known)),
        "summary": summary,
    }
    return AirDensityDecision(values=values, info=info, warnings=tuple(warnings), notes=tuple(notes))

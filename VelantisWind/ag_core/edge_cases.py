# -*- coding: utf-8 -*-
"""The edge cases of a calculation (#63): negative effective wind speeds, the 0 m/s node and non-finite values.

What PyWake calculates without an error is kept and said, never refused, corrected nor replaced (principle A). This
module only reads: each function takes numpy arrays, works on read-only views of them (a mutation by mistake
raises) and returns counts, classifications, reasons and texts; it never receives a simulation result nor an object
of the calculation. With every value finite and every speed non-negative it returns nothing (``None``), so the
ordinary calculation gets nothing from here (principle B). Its callers protect each call (``guarded``): a failure of
a diagnosis is the warning «aviso no disponible», never a change of the calculation.

The arrays of a simulation are ``(turbine, direction, speed)``: the AEP of each case, its probability ``P``, the power,
the effective speed ``WS_eff`` and, with a Weibull resource, the frequency of its sector. A non-finite AEP case is
of group 1, without energy, when its ``P`` is 0 or its ``P`` is not finite in a sector whose frequency is 0 (read
from the resource, never deduced from the other cases); of group 2 otherwise. The sums of the plugin keep what they
do (decision 5): ``np.nansum`` per turbine and per direction keeps ±inf and skips NaN, and the aggregation to the
sectors of the resource skips every non-finite value; a total that skips a case of group 2 is partial.
"""
from __future__ import annotations

import logging

import math
from typing import Any, Callable, Dict, List, Optional, Sequence

import numpy as np

from .log_text import log_text

__all__ = ["read_only", "guarded", "speed_diagnosis", "simulation_diagnosis", "diagnosis_warnings", "ti_reasons",
           "TI_REASON_TEXTS", "weighting_discarded", "may_not_terminate", "UNAVAILABLE_TEXT"]

UNAVAILABLE_TEXT = "Aviso no disponible: {error}"

# The arguments of WeightedSum in PyWake 2.6.18 (superposition_models.py:82) for the ones a configuration leaves out.
_WS_DEFAULTS = {"delta": 0.01, "max_err": 1e-3, "max_iter": 5, "weight_limit": 10 ** 10}
# Below it, the residual of WeightedSum stays at the level of the ULP and may never go under it (README, decision 9).
_ULP_MAX_ERR = 1e-12


def read_only(values: Any) -> np.ndarray:
    """A read-only float view of ``values`` (the original stays writable; this view cannot write into it)."""
    view = np.asarray(values, dtype=float).view()
    view.setflags(write=False)
    return view


def guarded(log: Callable[[Any], None], fn: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
    """``fn(*args, **kwargs)``, or ``None`` with «aviso no disponible: <error>» to ``log`` if it fails."""
    try:
        return fn(*args, **kwargs)
    except Exception as exc:  # noqa: BLE001 - a diagnosis never stops nor changes the calculation
        try:
            log(log_text(UNAVAILABLE_TEXT, error=f"{type(exc).__name__}: {exc}"))
        except Exception as _ignored_exc:  # noqa: BLE001
            logging.getLogger(__name__).debug("Ignored optional operation at %s:%d: %s", __name__, 52, _ignored_exc)
        return None


def _counts(a: np.ndarray) -> Dict[str, int]:
    return {"nan": int(np.isnan(a).sum()), "+inf": int(np.isposinf(a).sum()), "-inf": int(np.isneginf(a).sum())}


def _ids(mask: np.ndarray) -> List[int]:
    """The turbines (1-based, as the table of the result) of the cases in ``mask`` (turbine first)."""
    return [int(i) + 1 for i in np.nonzero(mask.reshape(mask.shape[0], -1).any(axis=1))[0]]


def speed_diagnosis(ws_eff: Any, *, turbines: bool = True) -> Optional[Dict[str, Any]]:
    """The negative and non-finite effective speeds (decision 2): how many cases, the smallest finite negative one
    and, with ``turbines`` (the first axis), which turbines have negatives. ``None`` if all are finite and ≥ 0."""
    a = read_only(ws_eff)
    negative = a < 0  # −inf included; NaN is not negative
    finite = np.isfinite(a)
    if finite.all() and not negative.any():
        return None
    out: Dict[str, Any] = {"cells": int(a.size), "negative": int(negative.sum()), **_counts(a)}
    if negative.any():
        values = a[negative & finite]
        out["min_m_s"] = float(values.min()) if values.size else None
        if turbines and a.ndim:
            out["turbines"] = _ids(negative)
    return out


def _aligned(values: Any, shape) -> np.ndarray:
    """``values`` read-only, with the dimensions of ``shape`` (each its size or 1): never numpy's broadcast from the
    last axis, which would put a frequency per direction on the axis of the speeds."""
    a = read_only(values)
    if a.ndim != len(shape) or any(n not in (1, m) for n, m in zip(a.shape, shape)):
        raise ValueError(f"forma {a.shape} no alineada con el AEP {tuple(shape)}")
    return np.broadcast_to(a, shape)


def _zero(values: Optional[np.ndarray], shape) -> np.ndarray:
    return np.zeros(shape, bool) if values is None else _aligned(values, shape) == 0


def _sector_index(directions: Sequence[float], centers: Sequence[float]) -> np.ndarray:
    """The sector of each direction, as the aggregation of the plugin (``aep_arrays._aggregate_to_sector_centers``)."""
    dirs, c = np.asarray(directions, float).reshape(-1), np.asarray(centers, float).reshape(-1)
    c = c[np.isfinite(c)]
    return np.argmin(np.abs(((dirs[:, None] - c[None, :] + 180.0) % 360.0) - 180.0), axis=1), c


def _sectors(directions: Sequence[float], sector_centers: Optional[Sequence[float]], mask: np.ndarray) -> List[float]:
    """The sectors (``sector_centers``, or the directions themselves) of the directions in ``mask``."""
    dirs = np.asarray(directions, float).reshape(-1)
    if sector_centers is not None and np.isfinite(np.asarray(sector_centers, float)).any():
        index, centers = _sector_index(dirs, sector_centers)
        return sorted({float(centers[i]) for i, b in zip(index, mask) if b})
    return [float(d) for d, b in zip(dirs, mask) if b]


def _sector_totals(direction: np.ndarray, directions: Sequence[float], sector_centers: Sequence[float]):
    """The totals of the sectors as ``aep_arrays._aggregate_to_sector_centers`` adds them (its finite directions, in
    order), with their centres; ``None`` if it would not aggregate."""
    dirs = np.asarray(directions, float).reshape(-1)
    if dirs.size != direction.size or not np.isfinite(np.asarray(sector_centers, float)).any():
        return None
    index, centers = _sector_index(dirs, sector_centers)
    totals = np.zeros(centers.size, dtype=float)
    for i, value in zip(index.tolist(), direction.tolist()):
        if np.isfinite(value):
            totals[int(i)] += float(value)
    return totals, centers


def _aep_diagnosis(aep: np.ndarray, p: Optional[np.ndarray], frequency: Optional[np.ndarray],
                   directions: Optional[Sequence[float]],
                   sector_centers: Optional[Sequence[float]]) -> Optional[Dict[str, Any]]:
    """The non-finite AEP cases and what the sums of the plugin do with them, by their real reductions (MWh): per
    turbine and per direction ``np.nansum`` (it skips NaN and keeps ±inf), the farm as the sum of the turbines, and
    the sectors, which skip a direction whose total is not finite (``aep_arrays.py:52``, ``:107``, ``:120-134``).
    ``None`` with every case and every total finite."""
    bad = ~np.isfinite(aep)
    n = aep.shape[0] if aep.ndim else 1
    flat, flat_bad = aep.reshape(n, -1), bad.reshape(n, -1)
    with np.errstate(all="ignore"):
        turbine = np.nansum(flat, axis=1) * 1000.0
        farm = float(np.sum(turbine))
        direction = np.nansum(aep, axis=(0, 2)) * 1000.0 if aep.ndim == 3 else None
        sector = (_sector_totals(direction, directions, sector_centers)
                  if direction is not None and directions is not None and sector_centers is not None else None)
    if not bad.any() and np.isfinite(turbine).all() and math.isfinite(farm) and (
            direction is None or np.isfinite(direction).all()) and (sector is None or np.isfinite(sector[0]).all()):
        return None
    out: Dict[str, Any] = {"cells": int(aep.size), **_counts(aep)}
    try:
        p_ro = None if p is None else _aligned(p, aep.shape)
        empty_sector = (np.zeros(aep.shape, bool) if p_ro is None
                        else ~np.isfinite(p_ro) & _zero(frequency, aep.shape))
        group1 = bad & (_zero(p_ro, aep.shape) | empty_sector)
    except Exception as exc:  # noqa: BLE001 - every non-finite case counts as one with energy
        group1 = np.zeros(aep.shape, bool)
        out["classification"] = f"{type(exc).__name__}: {exc}"
    group2 = bad & ~group1
    out["group1"], out["group2"] = int(group1.sum()), int(group2.sum())
    out["group2_counts"] = _counts(np.where(group2, aep, 0.0))
    skipped = (group2 & np.isnan(aep)).reshape(n, -1).any(axis=1)
    finite_turbine = np.isfinite(turbine)
    # partial: it leaves out a case that may have energy, whatever the state of the total (it may still be infinite)
    out["partial_turbines"] = [int(i) + 1 for i in np.nonzero(skipped)[0]]
    out["non_finite_turbines"] = [int(i) + 1 for i in np.nonzero(~finite_turbine)[0]]
    out["farm_finite"] = math.isfinite(farm)
    # A total that is not finite with no infinite case in it: the sum overflows.
    infinite = np.isinf(flat).any(axis=1)
    out["overflow"] = bool((~finite_turbine & ~infinite).any() or (finite_turbine.all() and not out["farm_finite"]))
    if direction is not None and directions is not None:
        lost = ~np.isfinite(direction)
        partial = (group2 & np.isnan(aep)).any(axis=(0, 2)) & ~lost
        out["overflow"] = out["overflow"] or bool((lost & ~np.isinf(aep).any(axis=(0, 2))).any())
        out["lost_directions_deg"] = [float(d) for d, b in zip(np.asarray(directions, float).reshape(-1), lost) if b]
        out["partial_sectors_deg"] = _sectors(directions, sector_centers, lost | partial)
    if sector is not None and not np.isfinite(sector[0]).all():  # the finite directions of a sector overflow
        out["overflow"] = True
        out["non_finite_sectors_deg"] = [float(c) for c, v in zip(sector[1], sector[0]) if not math.isfinite(v)]
    return out


def simulation_diagnosis(*, ws_eff: Any, aep: Any, p: Any = None, power: Any = None, frequency: Any = None,
                         directions: Optional[Sequence[float]] = None,
                         sector_centers: Optional[Sequence[float]] = None) -> Optional[Dict[str, Any]]:
    """What one simulation has of decisions 2 and 5, ``None`` if nothing: the negative and non-finite effective
    speeds, the non-finite cases of ``P`` and of the power, and the non-finite AEP cases with their group, the
    turbines whose total is partial or not finite and the sectors (``sector_centers``, or the ``directions`` of the
    simulation) whose total is partial. ``p`` and ``frequency`` have the dimensions of the AEP (each of its size or
    1); otherwise the classification is not available and every non-finite case counts as one with energy."""
    out: Dict[str, Any] = {}
    speeds = speed_diagnosis(ws_eff)
    if speeds is not None:
        out["ws_eff"] = speeds
    for key, values in (("p", p), ("power", power)):
        if values is not None:
            a = read_only(values)
            if not np.isfinite(a).all():
                out[key] = {"cells": int(a.size), **_counts(a)}
    aep_part = _aep_diagnosis(read_only(aep), p, frequency, directions, sector_centers)
    if aep_part is not None:
        out["aep"] = aep_part
    return out or None


def non_finite_label(value: Any) -> Optional[str]:
    """The label of a non-finite number in the outputs (decision 10): «NaN», «+inf» or «−inf»; ``None`` for a finite
    number or anything that is not a number, which each output shows as always."""
    try:
        x = float(value)
    except (TypeError, ValueError, OverflowError):
        return None
    if math.isfinite(x):
        return None
    return "NaN" if math.isnan(x) else ("+inf" if x > 0 else "−inf")


def _list(values: Sequence[Any]) -> str:
    return ", ".join(f"{v:g}" if isinstance(v, float) else str(v) for v in values)


def diagnosis_warnings(diagnosis: Optional[Dict[str, Any]], label: Any) -> Dict[str, List[Any]]:
    """The texts of a ``simulation_diagnosis``: ``warnings`` for every output, ``notes`` (the cases without energy,
    decision 5) only for the log. ``label`` says which simulation (e.g. «Cálculo principal»)."""
    out: Dict[str, List[Any]] = {"warnings": [], "notes": []}
    if not diagnosis:
        return out
    w = out["warnings"]
    speeds = diagnosis.get("ws_eff")
    if speeds and speeds["negative"]:
        w.append(log_text(
            "{label}: velocidad efectiva negativa en {count} de {cells} casos (turbina × dirección × velocidad; mínimo "
            "finito {min} m/s; turbinas {turbines}). PyWake la calcula sin error; el resultado se conserva.",
            label=label, count=speeds["negative"], cells=speeds["cells"],
            min="—" if speeds.get("min_m_s") is None else f"{speeds['min_m_s']:.4g}",
            turbines=_list(speeds.get("turbines") or [])))
    if speeds and (speeds["nan"] or speeds["+inf"] or speeds["-inf"]):
        w.append(log_text("{label}: velocidad efectiva no finita en {count} casos (NaN {nan}, +inf {pinf}, −inf {ninf}).",
                          label=label, count=speeds["nan"] + speeds["+inf"] + speeds["-inf"], nan=speeds["nan"],
                          pinf=speeds["+inf"], ninf=speeds["-inf"]))
    for key, name in (("p", "P"), ("power", log_text("potencia"))):
        c = diagnosis.get(key)
        if c:
            w.append(log_text("{label}: {name} no finita en {count} casos (NaN {nan}, +inf {pinf}, −inf {ninf}).",
                              label=label, name=name, count=c["nan"] + c["+inf"] + c["-inf"], nan=c["nan"],
                              pinf=c["+inf"], ninf=c["-inf"]))
    aep = diagnosis.get("aep")
    if not aep:
        return out
    if aep.get("classification"):
        w.append(log_text("{label}: clasificación de los casos no finitos no disponible ({error}): todos cuentan como "
                          "casos con energía.", label=label, error=aep["classification"]))
    if aep["group1"]:
        out["notes"].append(log_text(
            "{label}: {count} casos sin energía (P = 0, o P no finita en un sector de frecuencia nula) con AEP no "
            "finito: no aportan energía y las sumas los omiten.", label=label, count=aep["group1"]))
    if aep["group2"]:
        c = aep["group2_counts"]
        w.append(log_text("{label}: AEP no finito en {count} casos que pueden tener energía (NaN {nan}, +inf {pinf}, −inf {ninf}).",
                          label=label, count=aep["group2"], nan=c["nan"], pinf=c["+inf"], ninf=c["-inf"]))
    if aep.get("partial_turbines"):  # the farm is the sum of the turbines: it leaves out the same cases
        w.append(log_text("{label}: AEP parcial (omite casos no finitos con energía) en las turbinas {turbines}, y "
                          "en el total del parque.", label=label, turbines=_list(aep["partial_turbines"])))
    if aep.get("non_finite_turbines"):
        w.append(log_text("{label}: AEP no finito en las turbinas {turbines}, y en el total del parque.", label=label,
                          turbines=_list(aep["non_finite_turbines"])))
    elif not aep.get("farm_finite", True):
        w.append(log_text("{label}: AEP total del parque no finito.", label=label))
    if aep.get("overflow"):
        w.append(log_text("{label}: una suma del AEP desborda: da un infinito sin ningún caso infinito.",
                          label=label))
    if aep.get("non_finite_sectors_deg"):
        w.append(log_text("{label}: AEP por sector no finito en los sectores {sectors}° (su suma desborda).", label=label,
                          sectors=_list(aep["non_finite_sectors_deg"])))
    if aep.get("lost_directions_deg"):
        w.append(log_text("{label}: AEP por sector parcial en los sectores {sectors}°: omite los casos no finitos con "
                          "energía y toda la energía de las direcciones cuya suma no es finita ({directions}°).",
                          label=label, sectors=_list(aep["partial_sectors_deg"]),
                          directions=_list(aep["lost_directions_deg"])))
    elif aep.get("partial_sectors_deg"):
        w.append(log_text("{label}: AEP por sector parcial (omite casos no finitos con energía) en los sectores {sectors}°.",
                          label=label, sectors=_list(aep["partial_sectors_deg"])))
    return out


# The free speed under which the relative deficit of the raster is not defined (``qgis_io/wake_raster.py``).
DEFICIT_PCT_MIN_WS = 1e-9


def raster_diagnosis(ws_eff: Any, ws_free: Any = None) -> Optional[Dict[str, Any]]:
    """The edge cases of a wake map (decisions 2, 7 and 8): its negative and non-finite speeds and a map without wakes
    (``WS_eff`` equal to ``WS`` in every cell), read from the values of PyWake; and, on the speeds and the deficits as
    the exporter writes them (in float32), the cells where the relative deficit is not defined (``|WS| ≤ 1e-9``) or
    changes sign (``WS < 0``), the layers of the package without any finite cell and, in the others, the cells that
    float32 overflows (non-finite with finite speeds). ``None`` for an ordinary map."""
    def written(values: Any) -> np.ndarray:  # own read-only copies, in float32 as the exporter converts them
        with np.errstate(over="ignore"):
            a = np.array(values, dtype=np.float32)
        a.setflags(write=False)
        return a
    eff, eff32 = read_only(ws_eff), written(ws_eff)
    out: Dict[str, Any] = {}
    speeds = speed_diagnosis(eff, turbines=False)
    if speeds:
        out["ws_eff"] = speeds
    if ws_free is not None:
        free, free32 = read_only(ws_free), written(ws_free)
        if speed_diagnosis(free, turbines=False):
            out["ws"] = speed_diagnosis(free, turbines=False)
        with np.errstate(divide="ignore", invalid="ignore", over="ignore"):  # as the exporter writes them
            deficit = np.asarray(free32 - eff32, dtype=np.float32)
            defined = np.abs(free32) > DEFICIT_PCT_MIN_WS
            pct = np.full_like(deficit, np.nan)
            np.divide(deficit, free32, out=pct, where=defined)
            pct *= np.float32(100.0)
        undefined = int((np.isfinite(free32) & ~defined).sum())
        if undefined:
            out["deficit_pct_undefined"] = undefined
        given = ~np.isfinite(free) | ~np.isfinite(eff)  # cells already said with the speeds
        layers = (("WS", free32, ~np.isfinite(free)), ("WS_eff", eff32, ~np.isfinite(eff)),
                  ("wake_deficit", deficit, given), ("wake_deficit_pct", pct, given | (np.isfinite(free32) & ~defined)))
    else:
        layers = (("WS_eff", eff32, ~np.isfinite(eff)),)
    empty = [name for name, values, _said in layers if not np.isfinite(values).any()]
    if empty:
        out["empty_layers"] = empty
    # the other non-finite cells of a layer that keeps finite ones: an overflow of the float32 the exporter writes
    overflow = {name: int((~np.isfinite(values) & ~said).sum()) for name, values, said in layers if name not in empty}
    overflow = {name: n for name, n in overflow.items() if n}
    if overflow:
        out["overflow_cells"] = overflow
    if ws_free is not None and np.isfinite(eff).all() and np.isfinite(free).all() and np.array_equal(eff, free):
        out["no_wakes"] = True
    if out:
        out["cells"] = int(eff.size)
    return out or None


def raster_warnings(diagnosis: Optional[Dict[str, Any]]) -> List[Any]:
    """The texts of a ``raster_diagnosis``, translated when shown."""
    if not diagnosis:
        return []
    out: List[Any] = []
    for key, name in (("ws_eff", log_text("velocidad efectiva")), ("ws", log_text("velocidad libre"))):
        c = diagnosis.get(key)
        if not c:
            continue
        if c["negative"]:
            out.append(log_text("Ráster: {name} negativa en {count} de {cells} celdas (mínimo finito {min} m/s). "
                                "PyWake la calcula sin error; el mapa se conserva.", name=name, count=c["negative"],
                                cells=c["cells"], min="—" if c.get("min_m_s") is None else f"{c['min_m_s']:.4g}"))
        if c["nan"] or c["+inf"] or c["-inf"]:
            out.append(log_text("Ráster: {name} no finita en {count} celdas (NaN {nan}, +inf {pinf}, −inf {ninf}): son "
                                "NoData, y las estadísticas solo cubren las celdas finitas.", name=name,
                                count=c["nan"] + c["+inf"] + c["-inf"], nan=c["nan"], pinf=c["+inf"], ninf=c["-inf"]))
    if (diagnosis.get("ws") or {}).get("negative"):
        out.append(log_text("Ráster: con velocidad libre negativa, el déficit relativo cambia de signo en {count} celdas.",
                            count=diagnosis["ws"]["negative"]))
    if diagnosis.get("deficit_pct_undefined"):
        out.append(log_text("Ráster: el déficit relativo no está definido con velocidad libre nula: {count} celdas son "
                            "NoData.", count=diagnosis["deficit_pct_undefined"]))
    for layer in diagnosis.get("empty_layers") or []:
        out.append(log_text("Ráster: la capa {layer} no tiene celdas finitas: se escribe entera como NoData y sin estilo.",
                            layer=layer))
    for layer, count in (diagnosis.get("overflow_cells") or {}).items():
        out.append(log_text("Ráster: la capa {layer} tiene {count} celdas no finitas por desbordamiento al escribirla en "
                            "float32: son NoData.", layer=layer, count=count))
    if diagnosis.get("no_wakes"):
        out.append(log_text("Ráster: sin estelas: la velocidad efectiva es igual a la libre en todas las celdas."))
    return out


TI_REASON_TEXTS = {
    "unavailable": "no disponible: la simulación no da la TI efectiva",
    "infinite": "infinita",
    "nan": "NaN",
    "nan_weight": "NaN por ponderación con una P no finita",
    "zero_weight": "indefinida por peso total nulo",
    "reduction": "no finita en la reducción",
}


def ti_reasons(ti_eff: Any, p: Any, values: Any, n_turbines: int) -> Optional[Dict[int, str]]:
    """Why the effective TI of each turbine is not a value (decision 8), by precedence: not available (``ti_eff`` or
    ``values`` ``None``), the TI of a case infinite, NaN, a NaN by weighting with a non-finite ``P``, a total weight
    of 0, and, otherwise, the reduction. ``values`` is the TI of each turbine (``effective_ti_per_turbine``). Keyed
    by turbine (1-based); ``None`` if every one is finite. ``p`` broadcasts to ``ti_eff``."""
    if ti_eff is None or values is None:
        return {i + 1: "unavailable" for i in range(int(n_turbines))}
    v = read_only(values)
    if np.isfinite(v).all():
        return None
    ti = read_only(ti_eff)
    w = np.broadcast_to(read_only(p), ti.shape)
    n = ti.shape[0]
    flat_ti, flat_w = ti.reshape(n, -1), w.reshape(n, -1)
    out: Dict[int, str] = {}
    for i in np.nonzero(~np.isfinite(v))[0]:
        t, q = flat_ti[i], flat_w[i]
        if np.isinf(t).any():
            out[int(i) + 1] = "infinite"
        elif np.isnan(t).any():
            out[int(i) + 1] = "nan"
        elif not np.isfinite(q).all():
            out[int(i) + 1] = "nan_weight"
        elif q.sum() == 0:
            out[int(i) + 1] = "zero_weight"
        else:
            out[int(i) + 1] = "reduction"
    return out


def _number(v: Any) -> bool:
    return isinstance(v, (bool, int, float))


def _nan(v: Any) -> bool:
    return isinstance(v, float) and math.isnan(v)


def _arg(params: Dict[str, Any], name: str) -> Any:
    return params.get(name, _WS_DEFAULTS[name])


def weighted_sum_argument(params: Dict[str, Any], name: str) -> Any:
    """An argument of ``WeightedSum``: its value, or that of its signature."""
    return _arg(params, name)


def weighting_discarded(params: Dict[str, Any]) -> Optional[str]:
    """The argument of ``WeightedSum`` that leaves it as ``LinearSum`` in every case (decision 9), or ``None``:
    ``max_iter`` ≤ 0 or NaN (``count < max_iter`` never holds), ``max_err`` NaN or ≥ 1 (its first residual is
    0.9 plus at most a few ULP), ``delta`` NaN (no deficit reaches the limit) or ``weight_limit`` NaN (the weights
    stay 1). It does not say that it weighs otherwise (decision 9, «lo que el predicado no afirma»)."""
    max_iter, max_err = _arg(params, "max_iter"), _arg(params, "max_err")
    if _number(max_iter) and (_nan(max_iter) or max_iter <= 0):
        return "max_iter"
    if _number(max_err) and (_nan(max_err) or max_err >= 1):
        return "max_err"
    for name in ("delta", "weight_limit"):
        if _nan(_arg(params, name)):
            return name
    return None


def may_not_terminate(params: Dict[str, Any]) -> List[str]:
    """The arguments with which ``WeightedSum`` may iterate up to ``max_iter`` without its residual going under
    ``max_err`` (decision 9): ``max_err`` ≤ 1e-12 or ``max_iter`` = +inf; nothing if the weighting is discarded."""
    if weighting_discarded(params):
        return []
    out = []
    max_err, max_iter = _arg(params, "max_err"), _arg(params, "max_iter")
    if _number(max_err) and max_err <= _ULP_MAX_ERR:
        out.append("max_err")
    if _number(max_iter) and max_iter == math.inf:
        out.append("max_iter")
    return out

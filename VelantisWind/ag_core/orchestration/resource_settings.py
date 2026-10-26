# -*- coding: utf-8 -*-
"""The resource settings of an AEP: directions, interpolation, Speedup, wind speeds and hours.

A WRG computes on the policy of ``ag_core.resource_grid``, shared with the
optimiser: the chosen number of directions at the centres of the subdivisions
of its sectors, the chosen interpolation on the direction, Speedup ``none``
(the local Weibull climate of each position) and the wind speeds that cover the
operating band of the turbines with the chosen step. A GRD (a WAsP grid folder)
keeps the directions and wind speeds of its PyWake ``Site``. Both are
annualised with ``resource_grid.hours_per_year``. QGIS-free.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence, Tuple

import numpy as np

from ..log_text import log_error, log_text
from ..resource_grid import (
    WrgContractError,
    curve_band,
    direction_grid,
    hours_per_year,
    initial_speed_step,
    speed_grid,
    validate_speed_step,
)

# Where the band of a turbine comes from, by how it was defined (the ``mode`` of its metadata).
_BAND_ORIGIN = {"wtg": "declared", "owtg": "declared", "csv": "deduced", "manual": "deduced"}


def check_speedup(method: Any) -> str:
    """``none``, the only Speedup: anything else (``global_weibull`` too) is refused, never ignored."""
    if method != "none":
        raise log_error(
            WrgContractError, "Speedup no válido: {method}. Con un WRG solo se admite none: se conservan en cada punto las "
            "Weibull y frecuencias locales del WRG.", method=repr(method),
        )
    return "none"


def turbine_speed_curves(
    wind_turbines: Sequence[Any], bin_mean: bool = True
) -> List[Tuple[Optional[np.ndarray], Tuple[float, float]]]:
    """The ``(nodes, band)`` of each curve of each turbine in ``wind_turbines``, for the wind-speed policy.

    The curve the simulation integrates (the one the bin mean adapts): a table
    with its ``operating_band`` (the one the plugin's builders declare; without
    it, its tabulated range), a density table likewise, or an analytic curve
    between its cut-in and cut-out (no nodes). A curve the bin mean does not
    take, ``WrgContractError``; without ``bin_mean`` (``POINT``, which keeps the
    curve as it is), only one whose band cannot be read. The rule of the optimiser
    (its ``core/recurso.turbine_speed_curves``), for each turbine of a list.
    """
    from py_wake.wind_turbines.power_ct_functions import CubePowerSimpleCt, PowerCtNDTabular, PowerCtTabular

    from ..turbines.bin_power import _integral, _original, _type_list

    out = []
    for wt in wind_turbines:
        pcf = _original(wt.powerCtFunction)
        curves = [_original(f) for f in pcf.windTurbineFunction_lst] if _type_list(pcf) else [pcf]
        for curve in curves:
            if bin_mean:
                try:
                    _integral(curve)  # the bin mean takes it, as the simulation will need
                except ValueError as exc:
                    raise log_error(
                        WrgContractError, "La curva de la turbina no sirve para las velocidades de cálculo: {error}", error=exc,
                    ) from None
            elif not (isinstance(curve, (PowerCtTabular, CubePowerSimpleCt))
                      or (isinstance(curve, PowerCtNDTabular) and list(curve.input_keys)[:1] == ["ws"])):
                raise log_error(
                    WrgContractError, "La curva de la turbina no da su banda de velocidades de cálculo: {kind}.",
                    kind=type(curve).__name__,
                )
            band = getattr(curve, "operating_band", None)
            if isinstance(curve, PowerCtTabular):
                nodes, power = np.asarray(curve.ws_tab, dtype=float), np.asarray(curve.power_ct_tab[0], dtype=float)
            elif isinstance(curve, PowerCtNDTabular):
                grid = curve.interp[0]
                power = np.asarray(grid.V, dtype=float)
                nodes = np.asarray(grid.x[0][: power.shape[0]], dtype=float)
            else:  # CubePowerSimpleCt, the only other kind taken
                out.append((None, curve_band([curve.ws_cutin, curve.ws_cutout], [1.0, 1.0], None)))
                continue
            if band is None:  # the presets from PyWake: the range of the table they bring
                inside = nodes[(nodes > 0.0) & (nodes < 100.0)]
                band = (float(inside.min()), float(inside.max())) if inside.size else None
            out.append((nodes, curve_band(nodes, power, band)))
    return out


def effective_turbines(models: Sequence[Dict[str, Any]]) -> List[Any]:
    """The turbines the simulation will integrate for ``models``: for the wind-speed policy.

    A model's ``wt`` may be a composite ``WindTurbines`` of which the simulation
    takes one type (``source_type_index``, or the one that matches its geometry);
    ``combine_wt`` makes that choice, so the policy reads the curves of the
    combined set it builds, one per model, and never the unused branches. With no
    models, or a model without a turbine, the original turbines, so that
    ``turbine_speed_grid`` says what is missing.
    """
    if not models or any(m.get("wt") is None for m in models):
        return [m.get("wt") for m in models]
    from ..turbines.factory import combine_wt

    return [combine_wt(list(models))[0]]


def _union(curves) -> Tuple[float, float]:
    return min(b[0] for _, b in curves), max(b[1] for _, b in curves)


def turbine_speed_grid(wind_turbines: Sequence[Any], ws_step: Any = None, source: str = "",
                       bin_mean: bool = True) -> Dict[str, Any]:
    """The wind speeds of a WRG for ``wind_turbines`` (the turbine of each model): grid, step and band.

    The band is the union of the bands of their curves; the step, ``ws_step``
    (one of ``resource_grid.SPEED_STEPS``, never rounded) or, without it, the
    initial one of the curves (the finest). Without turbines (or with a model
    without one), ``WrgContractError``.
    The calculation and the dialog use it alike.
    """
    if not wind_turbines or any(wt is None for wt in wind_turbines):
        raise log_error(
            WrgContractError,
            "El WRG «{source}» necesita la turbina de cada modelo para sus velocidades de cálculo: define los modelos.",
            source=source,
        )
    curves = turbine_speed_curves(wind_turbines, bin_mean)
    band = _union(curves)
    step = initial_speed_step(curves) if ws_step is None else validate_speed_step(ws_step, source)
    return {"ws": speed_grid(band[0], band[1], step), "ws_step": step, "band": band}


def native_wd(ds: Any) -> Optional[np.ndarray]:
    """The sector centres of a resource, without the 360° closure, for the breakdown by sector."""
    try:
        if ds is None or "wd" not in ds.coords:
            return None
        wd = np.asarray(ds["wd"].values, dtype=float).reshape(-1)
        wd = wd[np.isfinite(wd)]
        if wd.size == 0:
            return None
        if wd.size > 1 and abs(float(wd[-1]) - 360.0) < 1e-6 and np.any(np.isclose(wd[:-1], 0.0, atol=1e-6)):
            wd = wd[:-1]
        return wd.astype(float)
    except Exception:
        return None


def resolve_resource_settings(
    site: Any,
    ds: Any,
    *,
    use_wrg: bool,
    source: str,
    speeds: Optional[Dict[str, Any]] = None,
    models: Sequence[Dict[str, Any]] = (),
    bin_mean: bool = True,
) -> Dict[str, Any]:
    """What the simulations receive and the result records, read from the effective ``site``.

    ``wd`` and ``ws`` go to the simulations: with a WRG, the grid of its
    ``wrg_direction_count`` subdivision centres and the wind speeds of
    ``speeds`` (``turbine_speed_grid``); with a GRD, ``None`` (the defaults of
    its ``Site``). ``native_wd`` are the sector centres for the breakdown.
    """
    method = getattr(site, "interp_method", None)
    record: Dict[str, Any] = {
        "kind": "WRG" if use_wrg else "GRD",
        "source": str(source),
        "wd_interp": str(method.get("wd", "linear") if isinstance(method, dict) else (method or "linear")),
        "speedup": "Speedup" if "Speedup" in ds else "none",
        "hours_per_year": hours_per_year("wrg" if use_wrg else "grd"),
    }
    native = native_wd(ds)
    if use_wrg:
        n_sectors = int(ds.attrs["n_sectors"])
        wd = direction_grid(n_sectors, int(ds.attrs["wrg_direction_count"]))
        ws = np.asarray(speeds["ws"], dtype=np.float64)
        bands = []
        from ..turbines.factory import canonicalize_models

        canonical = canonicalize_models(list(models))
        curves = turbine_speed_curves(effective_turbines(canonical), bin_mean) if canonical else []
        for m, (_nodes, band) in zip(canonical, curves):
            meta = m.get("meta") if isinstance(m.get("meta"), dict) else {}
            bands.append({
                "model": str(m.get("name") or meta.get("name") or "Custom WT"),
                "band_m_s": [float(v) for v in band],
                "origin": _BAND_ORIGIN.get(str(meta.get("mode") or "").lower(), "preset"),
            })
        record.update(
            n_sectors=n_sectors,
            direction_count=int(wd.size),
            subdivisions=int(wd.size) // n_sectors,
            direction_points="subdivision_centres",
            wd_eval_deg=wd.tolist(),
            ws_m_s=ws.tolist(),
            ws_step_m_s=float(speeds["ws_step"]),
            turbine_band_m_s=[float(v) for v in speeds["band"]],
            turbine_bands=bands,
        )
        sim_wd, sim_ws = wd, ws
    else:
        wd = np.asarray(site.default_wd, dtype=float).reshape(-1)
        ws = np.asarray(site.default_ws, dtype=float).reshape(-1)
        record.update(
            n_sectors=int(native.size) if native is not None else None,
            direction_count=int(wd.size),
            wd_eval_deg=wd.tolist(),
            ws_m_s=ws.tolist(),
        )
        sim_wd = sim_ws = None
    return {"record": record, "wd": sim_wd, "ws": sim_ws, "native_wd": native,
            "hours_per_year": float(record["hours_per_year"])}


def resource_log_line(record: Dict[str, Any]) -> str:
    """The ``[RECURSO]`` line: what the simulations compute with (the format of the optimiser's line for a WRG)."""
    ws = record["ws_m_s"]
    if record["kind"] == "WRG":
        return (
            f"[RECURSO] WRG | sectores={record['n_sectors']} | direcciones={record['direction_count']} | "
            f"subdivisiones={record['subdivisions']} | wd={record['wd_interp']} | centros de subdivisión | "
            f"speedup={record['speedup']} | ws={ws[0]:g}–{ws[-1]:g}/{record['ws_step_m_s']:g} m/s | "
            f"horas={record['hours_per_year']:g}"
        )
    wd = record["wd_eval_deg"]
    return (
        f"[RECURSO] GRD | sectores={record['n_sectors']} | direcciones={record['direction_count']} "
        f"({wd[0]:g}–{wd[-1]:g}°, las del Site) | wd={record['wd_interp']} | speedup={record['speedup']} | "
        f"ws={ws[0]:g}–{ws[-1]:g} m/s (las del Site) | horas={record['hours_per_year']:g}"
    )


def resource_note(record: Dict[str, Any]):
    """The note of the result: the same settings, for the user."""
    ws = record["ws_m_s"]
    if record["kind"] == "WRG":
        return log_text(
            "Parámetros del recurso (WRG): {count} direcciones ({sectors} sectores × {sub}), interpolación {interp}, "
            "Speedup {speedup}, velocidades {low}–{high} m/s cada {step} m/s (banda de las turbinas {band_low}–{band_high} "
            "m/s); {hours} h/año.",
            count=record["direction_count"], sectors=record["n_sectors"], sub=record["subdivisions"],
            interp=record["wd_interp"], speedup=record["speedup"], low=f"{ws[0]:g}", high=f"{ws[-1]:g}",
            step=f"{record['ws_step_m_s']:g}", band_low=f"{record['turbine_band_m_s'][0]:g}",
            band_high=f"{record['turbine_band_m_s'][1]:g}", hours=f"{record['hours_per_year']:g}",
        )
    wd = record["wd_eval_deg"]
    return log_text(
        "Recurso GRD, direcciones y velocidades del Site de PyWake: {count} direcciones ({wd_low}–{wd_high}°), "
        "{low}–{high} m/s, interpolación {interp}; {hours} h/año.",
        count=record["direction_count"], wd_low=f"{wd[0]:g}", wd_high=f"{wd[-1]:g}", low=f"{ws[0]:g}",
        high=f"{ws[-1]:g}", interp=record["wd_interp"], hours=f"{record['hours_per_year']:g}",
    )


__all__ = [
    "check_speedup",
    "turbine_speed_curves",
    "turbine_speed_grid",
    "native_wd",
    "resolve_resource_settings",
    "resource_log_line",
    "resource_note",
]

# -*- coding: utf-8 -*-
"""The AEP result of schema 2 (P0, section 8): the dictionary the results window, the report, the exports and the
layers read. QGIS-free; it only assembles what the calculation gives.

Kept from schema 1 with their meaning: the net AEP and A_0 of the farm and of each model, the geometry and power of
the models, the directional breakdown, the coverage of the resource, the resource settings and the air density.
New: ``result_schema_version``, ``breakdown`` and ``per_model_breakdown`` (``breakdown.aggregate``), the per-turbine
fields of the breakdown with ``wake_states`` and ``res_schema``, ``ti_ambient`` and ``ti_effective`` with their
declared aggregation, and the wake configuration, convergence and persistent warnings as the calculation gives
them. The schema-1 keys of the loss breakdown are not written (they changed meaning).
"""
from __future__ import annotations

from typing import Any, Callable, Dict, List, Mapping, Optional, Sequence

import numpy as np

from . import breakdown as bd
from . import summary as _summary
from ..log_text import log_text

__all__ = ["RESULT_SCHEMA_VERSION", "TI_AGGREGATION", "result_schema", "build_result", "log_breakdown"]

RESULT_SCHEMA_VERSION = 2
TI_AGGREGATION = {
    "ti_ambient": "media aritmética, sin ponderar, sobre las direcciones y velocidades del recurso, en el buje",
    "ti_effective": "media ponderada por la probabilidad de cada dirección y velocidad (la del AEP)",
}


def result_schema(result: Mapping[str, Any]) -> int:
    """The schema of a result: 2 if it says so, 1 (the previous one) otherwise."""
    try:
        return int(result.get("result_schema_version") or 1)
    except Exception:
        return 1


def _value(arr: Optional[np.ndarray], i: int) -> Optional[float]:
    if arr is None:
        return None
    v = float(np.asarray(arr, float)[i])
    return v if np.isfinite(v) else None


def build_result(*, models: List[Dict[str, Any]], xs, ys, use_types: bool, type_i, skipped: int,
                 skipped_by_model: Optional[Dict[str, int]], aep: Mapping[str, Optional[np.ndarray]],
                 aep_states: Mapping[str, str], term_states: Mapping[str, str], errors: Mapping[str, str],
                 ti_ambient: Optional[np.ndarray], ti_effective: Optional[np.ndarray],
                 aep_per_wd_wake_mwh=None, aep_per_wd_free_mwh=None, sector_directions_deg=None,
                 wake_config: Optional[Dict[str, Any]] = None, convergence: Optional[Dict[str, Any]] = None,
                 persistent_warnings: Sequence[str] = (), notes: Sequence[str] = (),
                 resource_settings: Optional[Dict[str, Any]] = None, air_density: Optional[Dict[str, Any]] = None,
                 log: Optional[Callable[[str], None]] = None) -> Dict[str, Any]:
    """The schema-2 result (see the module docstring). ``aep`` holds the AEP per turbine (MWh) of A_0, A_W, A_WT,
    A_WB and A_WTB, the main one; ``aep_states``/``term_states``/``errors`` come from ``variants.run_breakdown``."""
    principal = np.asarray(aep["A_WTB"], float)
    n = len(principal)
    names_by_type = _summary.build_names_by_type(models)
    types = np.asarray(type_i, dtype=int) if use_types and type_i is not None else np.zeros(n, dtype=int)
    model_of = [names_by_type.get(int(t), f"WT_{int(t)}") for t in types]
    counts: Dict[str, int] = {}
    for m in model_of:
        counts[m] = counts.get(m, 0) + 1
    meta = _summary.build_model_geometry_and_power(models=models, model_counts=counts)

    farm = bd.aggregate(aep, aep_states, term_states)[None]
    per_model = bd.aggregate(aep, aep_states, term_states, groups=model_of)
    # A failed term carries its error; a derived term that failed because of it, the error of its variant.
    # Δ_B is measured from A_WT, or from A_W when there is no added turbulence (breakdown.term_states).
    depends = {"L_W": ("A_0", "A_W"), "D_T": ("A_WT", "A_W"),
               "D_B": ("A_WT",) if term_states.get("D_T") != bd.NOT_MODELLED else ("A_W",), "L_total": ("A_0",),
               "I_TB": ("A_W", "A_WT", "A_WB")}
    for entry in [farm] + list(per_model.values()):
        for term, err in errors.items():
            entry[term]["error"] = err
        for term, deps in depends.items():
            causes = [d for d in deps if d in errors]
            if entry[term]["state"] == bd.FAILED and causes:
                # The errors of the variants stay templates (translated when shown).
                entry[term]["error"] = log_text("; ".join(f"{{t{k}}}: {{e{k}}}" for k in range(len(causes))),
                                                **{f"t{k}": d for k, d in enumerate(causes)},
                                                **{f"e{k}": errors[d] for k, d in enumerate(causes)})
    rows_bd = bd.per_turbine(aep, aep_states, term_states)
    rows: List[Dict[str, Any]] = []
    xs_a, ys_a = np.asarray(xs, float), np.asarray(ys, float)
    densities = (air_density or {}).get("values_kg_m3")
    altitudes = (air_density or {}).get("hub_altitude_m")
    for i in range(n):
        geom = meta["per_model_geom"].get(model_of[i], {})
        row = {
            "id": i + 1, "x": float(xs_a[i]), "y": float(ys_a[i]), "model": model_of[i],
            "diam": geom.get("D"), "hh": geom.get("HH"),
            "p_nom_mw": float(meta["per_model_p_rated_MW"].get(model_of[i], 0.0) or 0.0),
        }
        row.update(rows_bd[i])
        row["ti_ambient"] = _value(ti_ambient, i)
        row["ti_effective"] = _value(ti_effective, i)
        row["res_schema"] = RESULT_SCHEMA_VERSION
        row["air_density_kg_m3"] = densities[i] if densities is not None else None
        row["hub_altitude_m"] = altitudes[i] if altitudes is not None else None
        rows.append(row)

    result: Dict[str, Any] = {
        "result_schema_version": RESULT_SCHEMA_VERSION,
        "aep_wake_MWh": float(principal.sum()),
        "aep_free_MWh": farm["A_0"]["mwh"],
        "breakdown": farm,
        "per_model_breakdown": per_model,
        "per_model_aep_MWh": {m: e["A_WTB"]["mwh"] for m, e in per_model.items()},
        "per_model_aep_free_MWh": {m: e["A_0"]["mwh"] for m, e in per_model.items()},
        "per_model_n_turbines": counts,
        "per_model_geom": meta["per_model_geom"],
        "per_model_p_rated_MW": meta["per_model_p_rated_MW"],
        "per_model_p_inst_MW": meta["per_model_p_inst_MW"],
        "aep_per_wd_wake_MWh": aep_per_wd_wake_mwh,
        "aep_per_wd_free_MWh": aep_per_wd_free_mwh,
        "sector_directions_deg": sector_directions_deg,
        "skipped_outside_grid": int(skipped),
        "skipped_by_model": dict(skipped_by_model or {}),
        "turbines_inside_grid": n,
        "ti_aggregation": dict(TI_AGGREGATION),
        "wake_config": dict(wake_config or {}),
        "convergence": dict(convergence or {}),
        "persistent_warnings": list(persistent_warnings),
        "simulation_notes": list(notes),
        "air_density": dict(air_density) if air_density else None,
        "resource_settings": dict(resource_settings or {}),
        "hours_per_year": float((resource_settings or {}).get("hours_per_year") or 0.0),
        "per_turbine_table": rows,
        "use_types": use_types,
        "types_vector": (np.asarray(type_i).tolist() if use_types and type_i is not None else None),
    }
    if log is not None:
        log_breakdown(result, log)
    return result


_LABELS = {"A_0": "AEP sin estelas ni bloqueo (A_0)", "A_WTB": "AEP neto (configuración principal)",
           "L_W": "Pérdida por estelas (L_W = A_0 − A_W)", "D_T": "Impacto de la turbulencia añadida (Δ_T = A_WT − A_W)",
           "D_B": "Impacto del bloqueo (Δ_B = A_WTB − A_WT)", "L_total": "Pérdida total (L_total = A_0 − A_WTB)",
           "I_TB": "Interacción turbulencia-bloqueo (diagnóstico, fuera del balance)"}
STATE_LABELS = {bd.OK: "calculado", bd.ZERO_BY_CONSTRUCTION: "sin efecto: el déficit no usa la TI efectiva",
                bd.NOT_MODELLED: "no modelado", bd.NOT_REQUESTED: "no solicitado", bd.FAILED: "falló"}


def _line(entry: Mapping[str, Any], term: str):
    e = entry[term]
    label, state = log_text(_LABELS[term]), log_text(STATE_LABELS.get(e["state"], e["state"]))
    if e["mwh"] is None:
        if e.get("error"):
            return log_text("[REPORT]   {label}: no disponible ({state}: {error})", label=label, state=state,
                            error=e["error"])
        return log_text("[REPORT]   {label}: no disponible ({state})", label=label, state=state)
    pct = f" ({e['pct']:+.2f} %)" if e.get("pct") is not None and term not in ("A_0", "A_WTB") else ""
    return log_text("[REPORT]   {label}: {value} MWh{pct} [{state}]", label=label, value=f"{e['mwh']:,.1f}",
                    pct=pct, state=state)


def log_breakdown(result: Mapping[str, Any], log: Callable[[str], None]) -> None:
    """The report of the breakdown in the log: the farm and each model, with the signed values, their state and the
    cause of a failed term."""
    from .breakdown_translations import register_breakdown_translations
    register_breakdown_translations()  # translated even when the results window was never opened
    log(log_text("=== [REPORT] Desglose de pérdidas (con signo: las pérdidas positivas restan, los impactos positivos "
                 "suman) ==="))
    for term in ("A_0", "A_WTB", "L_W", "D_T", "D_B", "L_total", "I_TB"):
        log(_line(result["breakdown"], term))
    for model, entry in result["per_model_breakdown"].items():
        log(log_text("[REPORT]   - Modelo {model}:", model=model))
        for term in ("A_0", "A_WTB", "L_W", "D_T", "D_B", "L_total"):
            log(_line(entry, term))

# -*- coding: utf-8 -*-
"""Summary builders for AEP results.

This module keeps the aggregation/reporting logic QGIS-free and separate from
``aep_compute.py``.  It works with plain arrays/dicts so the same summaries can
be reused by the dialog, report exporters and scenario comparison tools.
"""
from __future__ import annotations

import csv
import os
from typing import Any, Callable, Dict, List, Optional, Tuple

import numpy as np


def _pct(num: Optional[float], den: float) -> float:
    if num is None:
        return 0.0
    den = den if abs(float(den)) > 1e-12 else 1e-12
    return float(num) / float(den) * 100.0


def build_names_by_type(models: List[Dict[str, Any]]) -> Dict[int, str]:
    """Map PyWake ``type_i`` integer ids to user-facing turbine model names."""
    names_by_type: Dict[int, str] = {}
    for i, m in enumerate(models):
        meta = m.get("meta") if isinstance(m.get("meta"), dict) else {}
        nm = m.get("name") or meta.get("name") or f"WT_{i}"
        names_by_type[int(i)] = str(nm)
    return names_by_type


def aggregate_by_model(
    *,
    models: List[Dict[str, Any]],
    nwt: int,
    use_types: bool,
    type_i,
    compute_variants: bool,
    aep_free_wt,
    aep_wake_wt,
    aep_wake_only_wt=None,
    aep_wake_ti_wt=None,
    aep_wake_blk_only_wt=None,
    aep_wake_ti_blk_wt=None,
    ti_breakdown_disabled_for_ti_coupled: bool = False,
    block_model_present: bool = False,
) -> Dict[str, Any]:
    """Aggregate per-turbine AEP arrays into per-model AEP and loss dictionaries."""
    names_by_type = build_names_by_type(models)

    aep_free_wt = np.asarray(aep_free_wt, dtype=float)
    aep_wake_wt = np.asarray(aep_wake_wt, dtype=float)
    type_arr = np.asarray(type_i, dtype=int) if use_types and type_i is not None else None

    per_model_free: Dict[str, float] = {}
    per_model_op: Dict[str, float] = {}
    per_model_wake_only: Dict[str, float] = {}
    per_model_wake_ti: Dict[str, float] = {}
    per_model_wake_blk_only: Dict[str, float] = {}
    per_model_wake_ti_blk: Dict[str, float] = {}
    model_counts: Dict[str, int] = {}

    for i in range(int(nwt)):
        t_id = int(type_arr[i]) if use_types and type_arr is not None else 0
        nm = names_by_type.get(t_id, f"WT_{t_id}")

        free_i = float(aep_free_wt[i])
        wake_i = float(aep_wake_wt[i])

        per_model_free[nm] = per_model_free.get(nm, 0.0) + free_i
        per_model_op[nm] = per_model_op.get(nm, 0.0) + wake_i
        model_counts[nm] = model_counts.get(nm, 0) + 1

        if compute_variants and aep_wake_only_wt is not None:
            per_model_wake_only[nm] = per_model_wake_only.get(nm, 0.0) + float(np.asarray(aep_wake_only_wt)[i])
        if compute_variants and aep_wake_ti_wt is not None:
            per_model_wake_ti[nm] = per_model_wake_ti.get(nm, 0.0) + float(np.asarray(aep_wake_ti_wt)[i])
        if compute_variants and aep_wake_blk_only_wt is not None:
            per_model_wake_blk_only[nm] = per_model_wake_blk_only.get(nm, 0.0) + float(np.asarray(aep_wake_blk_only_wt)[i])
        if compute_variants and aep_wake_ti_blk_wt is not None:
            per_model_wake_ti_blk[nm] = per_model_wake_ti_blk.get(nm, 0.0) + float(np.asarray(aep_wake_ti_blk_wt)[i])

    per_model_loss_wake: Dict[str, float] = {}
    per_model_loss_ti: Dict[str, float] = {}
    per_model_ti_impact: Dict[str, float] = {}
    per_model_loss_blk: Dict[str, float] = {}

    for nm, free_m in per_model_free.items():
        op_m = per_model_op.get(nm, 0.0)
        wakeonly_m = per_model_wake_only.get(nm) if compute_variants else None
        ti_m = per_model_wake_ti.get(nm) if compute_variants else None
        blk_only_m = per_model_wake_blk_only.get(nm) if compute_variants else None
        ti_blk_m = per_model_wake_ti_blk.get(nm) if compute_variants else None

        if compute_variants and wakeonly_m is not None:
            # Pérdida "wake-only": free → wake_only.
            per_model_loss_wake[nm] = max(float(free_m) - float(wakeonly_m), 0.0)

            # Impacto TI/turbulencia: wake_only → wake+TI.
            # Firmado: positivo = recupera AEP; negativo = reduce AEP.
            if ti_m is not None:
                ti_delta_m = float(ti_m) - float(wakeonly_m)
                per_model_ti_impact[nm] = ti_delta_m
                per_model_loss_ti[nm] = max(-ti_delta_m, 0.0)

            # Pérdida por bloqueo:
            #  - preferimos incremental (wake+TI → wake+TI+bloqueo) si hay TI y ti_blk
            #  - si no, usamos (wake_only → wake+bloqueo)
            if (ti_m is not None) and (ti_blk_m is not None):
                per_model_loss_blk[nm] = max(float(ti_m) - float(ti_blk_m), 0.0)
            elif blk_only_m is not None:
                per_model_loss_blk[nm] = max(float(wakeonly_m) - float(blk_only_m), 0.0)
        else:
            # Sin desglose wake/TI: free→op se imputa al wake salvo el bloqueo incremental, si se pudo estimar.
            op_base_m = op_m
            if compute_variants and (ti_breakdown_disabled_for_ti_coupled or wakeonly_m is None):
                if (ti_m is not None) and block_model_present:
                    per_model_loss_blk[nm] = max(float(ti_m) - float(op_m), 0.0)
                elif (blk_only_m is not None) and block_model_present:
                    per_model_loss_blk[nm] = max(float(blk_only_m) - float(op_m), 0.0)
            blk_m = float(per_model_loss_blk.get(nm, 0.0) or 0.0)
            per_model_loss_wake[nm] = max(float(free_m) - float(op_base_m) - blk_m, 0.0)

    return {
        "names_by_type": names_by_type,
        "per_model": per_model_op,
        "per_model_free": per_model_free,
        "per_model_op": per_model_op,
        "per_model_wake_only": per_model_wake_only,
        "per_model_wake_ti": per_model_wake_ti,
        "per_model_wake_blk_only": per_model_wake_blk_only,
        "per_model_wake_ti_blk": per_model_wake_ti_blk,
        "model_counts": model_counts,
        "per_model_loss_wake": per_model_loss_wake,
        "per_model_loss_ti": per_model_loss_ti,
        "per_model_ti_impact": per_model_ti_impact,
        "per_model_loss_blk": per_model_loss_blk,
    }


def _read_curve_from_model_dict(m: Dict[str, Any]) -> Optional[Tuple[np.ndarray, np.ndarray]]:
    """Read the original power curve CSV when metadata points to one."""
    meta = m.get("meta") if isinstance(m.get("meta"), dict) else {}

    path = meta.get("path") or m.get("path") or m.get("curve_csv") or m.get("cp_csv")
    if not path or not os.path.isfile(str(path)):
        return None

    try:
        ws_col = int(meta.get("ws_col", m.get("ws_col", 0)))
        power_col = int(meta.get("power_col", m.get("power_col", 1)))
        delimiter = str(meta.get("delimiter", m.get("delimiter", ",")))
        skip_header = int(meta.get("skip_header", m.get("skip_header", 1)))
    except Exception:
        ws_col, power_col, delimiter, skip_header = 0, 1, ",", 1

    ws, power = [], []
    try:
        with open(str(path), newline="", encoding="utf-8") as f:
            reader = csv.reader(f, delimiter=delimiter)
            for _ in range(max(skip_header, 0)):
                next(reader, None)
            for row in reader:
                if len(row) <= max(ws_col, power_col):
                    continue
                try:
                    ws.append(float(row[ws_col]))
                    power.append(float(row[power_col]))
                except Exception:
                    continue
    except Exception:
        return None

    if len(ws) < 2:
        return None
    return np.asarray(ws, dtype=np.float32), np.asarray(power, dtype=np.float32)


def _estimate_p_rated_mw(model: Dict[str, Any]) -> float:
    """Best-effort rated power estimate from metadata, stored curves or PyWake object."""
    meta = model.get("meta") if isinstance(model.get("meta"), dict) else {}

    for key in ("p_rated_mw", "p_rated_MW", "rated_mw", "rated_MW", "p_nom_MW", "p_nom_mw"):
        if key in meta and meta[key] not in (None, ""):
            try:
                value = float(meta[key])
                if value > 0:
                    return value
            except Exception:
                pass

    for key in ("p_rated_kw", "p_nom_kw", "rated_kw", "p_kw"):
        if key in meta and meta[key] not in (None, ""):
            try:
                value = float(meta[key]) / 1000.0
                if value > 0:
                    return value
            except Exception:
                pass

    try:
        pw_kw_list = meta.get("power_kw") or (model.get("wt_type", {}) or {}).get("power_kw")
        if pw_kw_list and len(pw_kw_list) > 0:
            arr = np.asarray([float(p) for p in pw_kw_list if p is not None], dtype=float)
            if arr.size > 0:
                peak_kw = float(np.nanmax(arr))
                if peak_kw > 0:
                    return peak_kw / 1000.0
    except Exception:
        pass

    try:
        pw_w_list = meta.get("power_w") or meta.get("power")
        if pw_w_list and len(pw_w_list) > 0:
            arr = np.asarray([float(p) for p in pw_w_list if p is not None], dtype=float)
            if arr.size > 0:
                peak = float(np.nanmax(arr))
                if peak > 1000:
                    return peak / 1e6
                if peak > 0:
                    return peak / 1000.0
    except Exception:
        pass

    try:
        curve_source = model.get("wt_type") if isinstance(model.get("wt_type"), dict) else model
        ws_power = _read_curve_from_model_dict(curve_source)
        if ws_power is not None:
            _, power_arr = ws_power
            peak = float(np.nanmax(power_arr))
            if peak > 1000:
                return peak / 1e6
            if peak > 0:
                return peak / 1000.0
    except Exception:
        pass

    try:
        wt_obj = model.get("wt")
        if wt_obj is not None:
            ws_test = np.linspace(4.0, 25.0, 50)
            try:
                power = wt_obj.power(ws_test, type_i=0)
            except TypeError:
                power = wt_obj.power(ws_test)
            arr = np.asarray(power, dtype=float)
            if arr.size > 0:
                return float(np.nanmax(arr)) / 1e6
    except Exception:
        pass

    return 0.0


def build_model_geometry_and_power(
    *,
    models: List[Dict[str, Any]],
    model_counts: Dict[str, int],
) -> Dict[str, Any]:
    """Build model geometry, rated power and installed power dictionaries."""
    per_model_geom: Dict[str, Dict[str, float]] = {}
    per_model_p_rated_MW: Dict[str, float] = {}
    per_model_p_inst_MW: Dict[str, float] = {}

    for m in models:
        meta = m.get("meta") if isinstance(m.get("meta"), dict) else {}
        nm = m.get("name") or meta.get("name") or "Custom WT"

        d_val = meta.get("diam", m.get("diam", m.get("D", None)))
        hh_val = meta.get("hh", m.get("hh", m.get("hub_height", None)))
        try:
            d_float = float(d_val)
        except Exception:
            d_float = float("nan")
        try:
            hh_float = float(hh_val)
        except Exception:
            hh_float = float("nan")

        per_model_geom[nm] = {
            "D": d_float,
            "diameter": d_float,
            "diam": d_float,
            "HH": hh_float,
            "hub_height": hh_float,
            "hh": hh_float,
        }
        per_model_p_rated_MW[nm] = _estimate_p_rated_mw(m)

    for nm, cnt in model_counts.items():
        per_model_p_inst_MW[nm] = float(cnt) * float(per_model_p_rated_MW.get(nm, 0.0))

    return {
        "per_model_geom": per_model_geom,
        "per_model_p_rated_MW": per_model_p_rated_MW,
        "per_model_p_inst_MW": per_model_p_inst_MW,
    }


def compute_global_losses(
    *,
    aep_free: float,
    aep_wake: float,
    compute_variants: bool,
    aep_wake_only: Optional[float] = None,
    aep_wake_ti: Optional[float] = None,
    aep_wake_blk_only: Optional[float] = None,
    block_model_present: bool = False,
    ti_breakdown_disabled_for_ti_coupled: bool = False,
) -> Dict[str, Optional[float]]:
    """Compute global wake/TI/blockage losses with the historical attribution rules."""
    if compute_variants and aep_wake_only is not None:
        wake_loss = max(float(aep_free) - float(aep_wake_only), 0.0)
    else:
        wake_loss = max(float(aep_free) - float(aep_wake), 0.0)
    wake_pct = (wake_loss / float(aep_free) * 100.0) if float(aep_free) > 0 else 0.0

    ti_impact_mwh: Optional[float] = None
    loss_ti_mwh: Optional[float] = None
    if compute_variants and (not ti_breakdown_disabled_for_ti_coupled) and (aep_wake_only is not None) and (aep_wake_ti is not None):
        ti_impact_mwh = float(aep_wake_ti) - float(aep_wake_only)
        loss_ti_mwh = max(-ti_impact_mwh, 0.0)

    loss_blk_mwh: Optional[float] = None
    if compute_variants:
        # Preferimos la pérdida incremental: (wake+TI) → (wake+TI+bloqueo).
        if (aep_wake_ti is not None) and block_model_present:
            loss_blk_mwh = max(float(aep_wake_ti) - float(aep_wake), 0.0)
        # Si no hay TI, usamos (wake_only) → (wake+bloqueo).
        elif (aep_wake_only is not None) and (aep_wake_blk_only is not None):
            loss_blk_mwh = max(float(aep_wake_only) - float(aep_wake_blk_only), 0.0)

    # Bug-fix: en el camino con variantes, wake_loss ya se ha calculado como
    # `aep_free - aep_wake_only` (variante SIN bloqueo y SIN turbulencia
    # añadida), así que ya excluye el bloqueo. Antes restábamos loss_blk_mwh
    # otra vez y el residuo aparecía como "Otras pérdidas" con el mismo valor
    # que el bloqueo (doble conteo). Mantenemos la sustracción solo cuando NO
    # se han ejecutado variantes (compatibility: wake_loss = aep_free - aep_wake con
    # todo incluido, y conviene separar el bloqueo).
    if loss_blk_mwh is not None and not compute_variants:
        wake_loss = max(wake_loss - loss_blk_mwh, 0.0)
        wake_pct = (wake_loss / float(aep_free) * 100.0) if float(aep_free) > 0 else 0.0

    return {
        "wake_loss": wake_loss,
        "wake_pct": wake_pct,
        "ti_impact_MWh": ti_impact_mwh,
        "loss_ti_MWh": loss_ti_mwh,
        "loss_blk_MWh": loss_blk_mwh,
    }


def log_result_summary(
    *,
    log: Callable[[str], None],
    aep_free: float,
    aep_wake: float,
    wake_loss: float,
    wake_pct: float,
    n_inside: int,
    skipped: int,
    per_model: Dict[str, float],
    per_model_free: Dict[str, float],
    per_model_op: Dict[str, float],
    model_counts: Dict[str, int],
    per_model_loss_wake: Dict[str, float],
    per_model_loss_ti: Dict[str, float],
    per_model_ti_impact: Dict[str, float],
    per_model_loss_blk: Dict[str, float],
    compute_variants: bool,
    aep_wake_only_wt=None,
    bg_def_cls: Any = None,
    turb_model: Any = None,
    block_model: Any = None,
    rotor_avg_obj: Any = None,
    superpos: Any = None,
    engine: Any = None,
    aep_wake_only: Optional[float] = None,
    aep_wake_ti: Optional[float] = None,
    aep_wake_blk_only: Optional[float] = None,
) -> None:
    """Emit the historical human-readable report log from summary dictionaries."""
    log("=== [REPORT] Resumen General ===")
    log(f"[REPORT] AEP free-stream: {float(aep_free):,.0f} MWh")
    log(f"[REPORT] AEP con estelas: {float(aep_wake):,.0f} MWh")
    log(f"[REPORT] Pérdidas por estela (total): {float(wake_loss):,.0f} MWh ({float(wake_pct):.1f}%)")
    log(f"[REPORT] Turbinas dentro de grid: {int(n_inside)} | fuera: {int(skipped)}")

    log("=== [REPORT] AEP y pérdidas por modelo ===")
    for nm in per_model.keys():
        free_m = per_model_free.get(nm, 0.0)
        op_m = per_model_op.get(nm, 0.0)
        cnt = model_counts.get(nm, 0)
        loss_wake_tot_m = max(float(free_m) - float(op_m), 0.0)

        loss_wake_puro = per_model_loss_wake.get(nm)
        loss_ti_m = per_model_loss_ti.get(nm)
        ti_impact_m = per_model_ti_impact.get(nm)
        loss_blk_m = per_model_loss_blk.get(nm)

        log(f"[REPORT]   - {nm:>20s} | n={cnt:>3d}")
        log(f"[REPORT]       AEP_free = {free_m:,.0f} MWh")
        log(f"[REPORT]       AEP_op   = {op_m:,.0f} MWh")
        log(
            f"[REPORT]       Pérdida total (free→op) = "
            f"{loss_wake_tot_m:,.0f} MWh ({_pct(loss_wake_tot_m, free_m):.1f}%)"
        )

        if compute_variants and aep_wake_only_wt is not None:
            if loss_wake_puro is not None:
                log(
                    f"[REPORT]       · Pérdida por wake puro     = "
                    f"{loss_wake_puro:,.0f} MWh ({_pct(loss_wake_puro, free_m):.1f}%)"
                )
            if ti_impact_m is not None:
                ti_tag_m = "ganancia" if ti_impact_m >= 0 else "pérdida"
                log(
                    f"[REPORT]       · Impacto TI/turbulencia    = "
                    f"{ti_impact_m:,.0f} MWh ({_pct(ti_impact_m, free_m):.1f}%) [{ti_tag_m}]"
                )
            elif loss_ti_m is not None:
                log(
                    f"[REPORT]       · Impacto TI/turbulencia    = "
                    f"{-loss_ti_m:,.0f} MWh ({_pct(-loss_ti_m, free_m):.1f}%) [pérdida]"
                )
            if loss_blk_m is not None:
                log(
                    f"[REPORT]       · Pérdida por bloqueo       = "
                    f"{loss_blk_m:,.0f} MWh ({_pct(loss_blk_m, free_m):.1f}%)"
                )
        else:
            log(
                "[REPORT]       · Desglose wake/TI/bloqueo no "
                "disponible para esta configuración (compute_variants desactivado o wake acoplado a TI)."
            )

    log("[REPORT] Modelos utilizados:")
    log(f"[REPORT]   Wake deficit: {getattr(bg_def_cls, '__name__', str(bg_def_cls))}")
    log(f"[REPORT]   Turbulence:   {turb_model.__class__.__name__ if turb_model is not None else 'None'}")
    log(f"[REPORT]   Blockage:     {block_model.__class__.__name__ if block_model is not None else 'None'}")
    log(f"[REPORT]   Rotor-avg:    {rotor_avg_obj.__class__.__name__ if rotor_avg_obj is not None else 'None'}")
    log(f"[REPORT]   Superposition:{type(superpos).__name__}")
    log(f"[REPORT]   WFM engine:   {engine}")

    log("=== [REPORT] Desglose global de pérdidas por efecto ===")
    if compute_variants and aep_wake_only is not None:
        loss_wake_only = max(float(aep_free) - float(aep_wake_only), 0.0)
        log(
            f"[REPORT]   Pérdidas por efecto estela (solo wake): "
            f"{loss_wake_only:,.0f} MWh ({_pct(loss_wake_only, aep_free):.1f}%)"
        )
        if aep_wake_ti is not None:
            ti_delta_g = float(aep_wake_ti) - float(aep_wake_only)
            sign_txt = "ganancia" if ti_delta_g >= 0 else "pérdida"
            log(
                f"[REPORT]   Impacto TI/turbulencia (wake+TI vs solo wake): "
                f"{ti_delta_g:,.0f} MWh ({_pct(ti_delta_g, aep_free):.1f}%) [{sign_txt}]"
            )
        if aep_wake_blk_only is not None:
            loss_blk_g = float(aep_wake_only) - float(aep_wake_blk_only)
            log(
                f"[REPORT]   Pérdidas por bloqueo (wake+bloqueo vs solo wake): "
                f"{loss_blk_g:,.0f} MWh ({_pct(loss_blk_g, aep_free):.1f}%)"
            )
    else:
        log(
            "[REPORT]   No se ha activado compute_variants=True -> "
            "no se puede separar pérdidas de wake/TI/bloqueo."
        )


__all__ = [
    "aggregate_by_model",
    "build_model_geometry_and_power",
    "build_names_by_type",
    "compute_global_losses",
    "log_result_summary",
]

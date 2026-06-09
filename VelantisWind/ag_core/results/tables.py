# -*- coding: utf-8 -*-
"""Builders for tabular AEP results.

These functions are intentionally QGIS-free. They only assemble dictionaries
used by the results dialog, CSV export and QGIS layer writers.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

import numpy as np


def _safe_float(value: Any) -> Optional[float]:
    try:
        if value is None:
            return None
        v = float(value)
        return v if np.isfinite(v) else None
    except Exception:
        return None


def _pct(value: Optional[float], base: float) -> Optional[float]:
    if value is None or base <= 0:
        return None
    return float(value) / float(base) * 100.0


def build_per_turbine_table(
    *,
    xs,
    ys,
    nwt: int,
    use_types: bool,
    type_i,
    names_by_type: Dict[int, str],
    per_model_geom: Dict[str, Dict[str, float]],
    per_model_p_rated_MW: Dict[str, float],
    aep_wake_wt,
    aep_free_wt,
    compute_variants: bool,
    aep_wake_only_wt=None,
    aep_wake_ti_wt=None,
    aep_wake_blk_only_wt=None,
    aep_wake_ti_blk_wt=None,
    ti_per_turb=None,
) -> List[Dict[str, Any]]:
    """Build the per-turbine table consumed by the UI, reports and layer writer."""
    rows: List[Dict[str, Any]] = []
    xs_arr = np.asarray(xs)
    ys_arr = np.asarray(ys)
    aep_wake_wt = np.asarray(aep_wake_wt, dtype=float)
    aep_free_wt = np.asarray(aep_free_wt, dtype=float)

    for i in range(int(nwt)):
        t_id = int(type_i[i]) if use_types else 0
        model_name = names_by_type.get(t_id, f"WT_{t_id}")
        geom = per_model_geom.get(model_name, {})
        d_val = _safe_float(geom.get("D") or geom.get("diameter") or geom.get("diam"))
        hh_val = _safe_float(geom.get("HH") or geom.get("hub_height") or geom.get("hh"))
        p_nom_mw = _safe_float(per_model_p_rated_MW.get(model_name, 0.0)) or 0.0

        if compute_variants and aep_wake_only_wt is not None:
            wake_loss_i = float(np.asarray(aep_free_wt)[i]) - float(np.asarray(aep_wake_only_wt)[i])
        else:
            wake_loss_i = float(np.asarray(aep_free_wt)[i]) - float(np.asarray(aep_wake_wt)[i])

        free_i = float(aep_free_wt[i])

        ti_impact_i = None
        loss_ti_i = None
        if compute_variants and (aep_wake_only_wt is not None) and (aep_wake_ti_wt is not None):
            ti_impact_i = float(np.asarray(aep_wake_ti_wt)[i]) - float(np.asarray(aep_wake_only_wt)[i])
            loss_ti_i = max(-ti_impact_i, 0.0)

        loss_blk_i = None
        if compute_variants:
            if (aep_wake_ti_wt is not None) and (aep_wake_ti_blk_wt is not None):
                loss_blk_i = max(float(np.asarray(aep_wake_ti_wt)[i]) - float(np.asarray(aep_wake_ti_blk_wt)[i]), 0.0)
            elif (aep_wake_only_wt is not None) and (aep_wake_blk_only_wt is not None):
                loss_blk_i = max(float(np.asarray(aep_wake_only_wt)[i]) - float(np.asarray(aep_wake_blk_only_wt)[i]), 0.0)

        def arr_val(arr):
            if arr is None:
                return None
            return float(np.asarray(arr)[i])

        rows.append(
            {
                "id": int(i + 1),
                "x": float(xs_arr[i]),
                "y": float(ys_arr[i]),
                "model": model_name,
                "diam": d_val,
                "hh": hh_val,
                "p_nom_mw": float(p_nom_mw),
                "aep_mwh": float(aep_wake_wt[i]),
                "aep_free_mwh": free_i,
                "loss_wake_mwh": float(wake_loss_i),
                "loss_wake_pct": float(wake_loss_i / free_i * 100.0) if free_i > 0 else 0.0,
                "loss_ti_mwh": float(loss_ti_i) if loss_ti_i is not None else None,
                "loss_ti_pct": _pct(loss_ti_i, free_i),
                "ti_impact_mwh": float(ti_impact_i) if ti_impact_i is not None else None,
                "ti_impact_pct": _pct(ti_impact_i, free_i),
                "loss_blk_mwh": float(loss_blk_i) if loss_blk_i is not None else None,
                "loss_blk_pct": _pct(loss_blk_i, free_i),
                "aep_wake_only_mwh": arr_val(aep_wake_only_wt) if compute_variants else None,
                "aep_wake_ti_mwh": arr_val(aep_wake_ti_wt) if compute_variants else None,
                "aep_wake_blk_mwh": arr_val(aep_wake_blk_only_wt) if compute_variants else None,
                "aep_wake_blk_only_mwh": arr_val(aep_wake_blk_only_wt) if compute_variants else None,
                "aep_wake_ti_blk_mwh": arr_val(aep_wake_ti_blk_wt) if compute_variants else None,
                "ti_eff": float(np.asarray(ti_per_turb)[i]) if (ti_per_turb is not None and len(ti_per_turb) > i) else None,
            }
        )
    return rows


__all__ = ["build_per_turbine_table"]

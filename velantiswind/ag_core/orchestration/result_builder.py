# -*- coding: utf-8 -*-
"""Final result assembly for the Energy/AEP calculation.

This module keeps ``ag_core.aep_compute`` focused on orchestration and PyWake
execution.  The functions here are QGIS-free and only assemble dictionaries,
loss summaries, logs and per-turbine rows consumed by the Energy results UI.

The public payload keys intentionally preserve the historical contract of
``compute_aep_from_ui`` so existing dialogs/exporters keep working.
"""
from __future__ import annotations

from typing import Any, Dict, List

import numpy as np

try:
    from ..results import summary as _result_summary
    from ..results import tables as _result_tables
except Exception:  # pragma: no cover - standalone fallback
    from ag_core.results import summary as _result_summary  # type: ignore
    from ag_core.results import tables as _result_tables  # type: ignore


def _class_name(obj: Any) -> Any:
    """Return the instance class name, preserving ``None`` for empty models."""
    return obj.__class__.__name__ if obj is not None else None


def build_energy_result_payload(
    *,
    models: List[Dict[str, Any]],
    xs,
    ys,
    skipped: int,
    use_types: bool,
    type_i,
    compute_variants: bool,
    aep_free: float,
    aep_wake: float,
    aep_free_wt,
    aep_wake_wt,
    aep_wake_only,
    aep_wake_ti,
    aep_wake_blk_only,
    aep_wake_ti_blk,
    aep_wake_only_wt,
    aep_wake_ti_wt,
    aep_wake_blk_only_wt,
    aep_wake_ti_blk_wt,
    ti_breakdown_disabled_for_ti_coupled: bool,
    ti_per_turb,
    block_model,
    turb_model,
    rotor_avg_obj,
    superpos,
    bg_def_cls,
    engine: str,
    aep_per_wd_wake_mwh,
    aep_per_wd_free_mwh,
    sector_directions_deg,
    user_selected_config: Dict[str, str],
    requested_config: Dict[str, str],
    executed_config: Dict[str, str],
    simulation_degraded: bool,
    used_attempt_label: str,
    config_notes: List[str],
    ti_fallback_10pct: bool,
    log,
) -> Dict[str, Any]:
    """Build the final ``compute_aep_from_ui`` result dictionary.

    Parameters mirror the already-computed simulation arrays and model objects.
    The function performs only aggregation, tabular formatting and reporting;
    it does not run PyWake or modify any physical configuration.
    """
    nwt = len(aep_wake_wt)

    model_summary = _result_summary.aggregate_by_model(
        models=models,
        nwt=nwt,
        use_types=use_types,
        type_i=type_i,
        compute_variants=compute_variants,
        aep_free_wt=aep_free_wt,
        aep_wake_wt=aep_wake_wt,
        aep_wake_only_wt=aep_wake_only_wt,
        aep_wake_ti_wt=aep_wake_ti_wt,
        aep_wake_blk_only_wt=aep_wake_blk_only_wt,
        aep_wake_ti_blk_wt=aep_wake_ti_blk_wt,
        ti_breakdown_disabled_for_ti_coupled=ti_breakdown_disabled_for_ti_coupled,
        block_model_present=(block_model is not None),
    )

    names_by_type = model_summary["names_by_type"]
    per_model = model_summary["per_model"]
    per_model_free = model_summary["per_model_free"]
    per_model_op = model_summary["per_model_op"]
    per_model_loss_wake = model_summary["per_model_loss_wake"]
    per_model_loss_ti = model_summary["per_model_loss_ti"]
    per_model_ti_impact = model_summary["per_model_ti_impact"]
    per_model_loss_blk = model_summary["per_model_loss_blk"]
    model_counts = model_summary["model_counts"]

    model_meta = _result_summary.build_model_geometry_and_power(
        models=models,
        model_counts=model_counts,
    )
    per_model_geom = model_meta["per_model_geom"]
    per_model_p_rated_MW = model_meta["per_model_p_rated_MW"]
    per_model_p_inst_MW = model_meta["per_model_p_inst_MW"]

    global_losses = _result_summary.compute_global_losses(
        aep_free=aep_free,
        aep_wake=aep_wake,
        compute_variants=compute_variants,
        aep_wake_only=aep_wake_only,
        aep_wake_ti=aep_wake_ti,
        aep_wake_blk_only=aep_wake_blk_only,
        block_model_present=(block_model is not None),
        ti_breakdown_disabled_for_ti_coupled=ti_breakdown_disabled_for_ti_coupled,
    )
    wake_loss = float(global_losses["wake_loss"] or 0.0)
    wake_pct = float(global_losses["wake_pct"] or 0.0)
    loss_ti_MWh = global_losses["loss_ti_MWh"]
    ti_impact_MWh = global_losses["ti_impact_MWh"]
    loss_blk_MWh = global_losses["loss_blk_MWh"]

    per_turbine_table = _result_tables.build_per_turbine_table(
        xs=xs,
        ys=ys,
        nwt=nwt,
        use_types=use_types,
        type_i=type_i,
        names_by_type=names_by_type,
        per_model_geom=per_model_geom,
        per_model_p_rated_MW=per_model_p_rated_MW,
        aep_wake_wt=aep_wake_wt,
        aep_free_wt=aep_free_wt,
        compute_variants=compute_variants,
        aep_wake_only_wt=aep_wake_only_wt,
        aep_wake_ti_wt=aep_wake_ti_wt,
        aep_wake_blk_only_wt=aep_wake_blk_only_wt,
        aep_wake_ti_blk_wt=aep_wake_ti_blk_wt,
        ti_per_turb=ti_per_turb,
    )

    _result_summary.log_result_summary(
        log=log,
        aep_free=aep_free,
        aep_wake=aep_wake,
        wake_loss=wake_loss,
        wake_pct=wake_pct,
        n_inside=len(xs),
        skipped=skipped,
        per_model=per_model,
        per_model_free=per_model_free,
        per_model_op=per_model_op,
        model_counts=model_counts,
        per_model_loss_wake=per_model_loss_wake,
        per_model_loss_ti=per_model_loss_ti,
        per_model_ti_impact=per_model_ti_impact,
        per_model_loss_blk=per_model_loss_blk,
        compute_variants=compute_variants,
        aep_wake_only_wt=aep_wake_only_wt,
        bg_def_cls=bg_def_cls,
        turb_model=turb_model,
        block_model=block_model,
        rotor_avg_obj=rotor_avg_obj,
        superpos=superpos,
        engine=engine,
        aep_wake_only=aep_wake_only,
        aep_wake_ti=aep_wake_ti,
        aep_wake_blk_only=aep_wake_blk_only,
    )

    return {
        "aep_wake_MWh": aep_wake,
        "aep_free_MWh": aep_free,
        "wake_loss_MWh": wake_loss,
        "wake_loss_pct": wake_pct,
        "loss_ti_MWh": loss_ti_MWh,
        "ti_impact_MWh": ti_impact_MWh,
        "loss_blk_MWh": loss_blk_MWh,
        "per_model_aep_MWh": per_model,
        "per_model_aep_free_MWh": per_model_free,
        "per_model_loss_wake_MWh": per_model_loss_wake,
        "per_model_loss_ti_MWh": per_model_loss_ti,
        "per_model_ti_impact_MWh": per_model_ti_impact,
        "per_model_loss_blk_MWh": per_model_loss_blk,
        "per_model_n_turbines": model_counts,
        "per_model_geom": per_model_geom,
        "per_model_p_rated_MW": per_model_p_rated_MW,
        "per_model_p_inst_MW": per_model_p_inst_MW,
        "aep_per_wd_wake_MWh": aep_per_wd_wake_mwh,
        "aep_per_wd_free_MWh": aep_per_wd_free_mwh,
        "sector_directions_deg": sector_directions_deg,
        "model_counts_inside": model_counts,  # compat
        "skipped_outside_grid": skipped,
        "turbulence_model": _class_name(turb_model),
        "blockage_model": _class_name(block_model),
        "rotor_avg_model": _class_name(rotor_avg_obj),
        "superposition_model": _class_name(superpos),
        "aep_wake_only_MWh": aep_wake_only,
        "aep_wake_ti_MWh": aep_wake_ti,
        "aep_wake_blk_only_MWh": aep_wake_blk_only,
        "aep_wake_ti_blk_MWh": aep_wake_ti_blk,
        "aep_wake_ti_block_MWh": aep_wake_ti_blk,  # compat
        "aep_best_no_rotor_MWh": None,
        "engine": engine,
        "wake_deficit_class": getattr(bg_def_cls, "__name__", str(bg_def_cls)),
        "selection_user": user_selected_config,
        "selection_requested": requested_config,
        "selection_executed": executed_config,
        "simulation_degraded": simulation_degraded,
        "simulation_degradation_label": (used_attempt_label if simulation_degraded else None),
        "simulation_notes": config_notes,
        "ti_fallback_10pct": ti_fallback_10pct,
        "per_turbine_table": per_turbine_table,
        "use_types": use_types,
        "types_vector": (type_i.tolist() if use_types and type_i is not None else None),
    }


__all__ = ["build_energy_result_payload"]

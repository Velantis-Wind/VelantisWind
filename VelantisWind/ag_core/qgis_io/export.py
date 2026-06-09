# -*- coding: utf-8 -*-
"""Export helpers for AEP results.

This module contains CSV export and QGIS memory summary layer creation. The old
``ag_core.export_results`` module remains as a compatibility façade.
"""
from __future__ import annotations

import csv
from typing import Any, Dict, List

from qgis.PyQt.QtCore import QVariant
from qgis.core import QgsFeature, QgsField, QgsFields, QgsProject, QgsVectorLayer


def export_per_turbine_to_csv(per_turbine_table: List[Dict[str, Any]], csv_path: str) -> None:
    """Export a polished per-turbine CSV summary.

    The file stays GIS/Excel friendly: the first row is still the header, with no
    decorative comment lines. The corporate polish is applied through clear
    English column names, units in headers, a stable order and preservation of
    extra diagnostic fields at the end.
    """
    if not per_turbine_table:
        return

    canonical = [
        ("Turbine ID", ["id", "turbine_id", "wt_id", "WTG", "turbine"]),
        ("Turbine model", ["model", "wt_name", "turbine_type", "name"]),
        ("X [m]", ["x", "X", "easting", "Easting"]),
        ("Y [m]", ["y", "Y", "northing", "Northing"]),
        ("Rated power [MW]", ["p_nom_mw", "p_rated_mw", "rated_power_mw", "rated_mw"]),
        ("Net AEP [MWh/year]", ["aep_mwh", "aep_MWh", "aep_net_mwh", "aep_net_MWh"]),
        ("Free-flow AEP [MWh/year]", ["aep_free_mwh", "aep_free_MWh", "gross_aep_mwh"]),
        ("Wake losses [MWh/year]", ["loss_wake_mwh", "loss_wake_MWh", "wake_loss_mwh"]),
        ("Blockage losses [MWh/year]", ["loss_blk_mwh", "loss_blk_MWh", "blockage_loss_mwh"]),
        ("TI/turbulence impact [MWh/year]", ["loss_ti_mwh", "loss_ti_MWh", "ti_impact_mwh"]),
        ("Net capacity factor [%]", ["cf_net_pct", "capacity_factor_pct", "net_cf_pct"]),
    ]

    all_keys: List[str] = []
    for row in per_turbine_table:
        for key in row.keys():
            if key not in all_keys:
                all_keys.append(key)

    used_keys = set()
    output_columns = []
    for label, candidates in canonical:
        found = next((k for k in candidates if k in all_keys), None)
        if found is not None:
            output_columns.append((label, found))
            used_keys.add(found)

    # Preserve any extra diagnostics after the corporate summary columns.
    # Raw diagnostic names are kept to avoid hiding internal meaning.
    for key in all_keys:
        if key not in used_keys:
            output_columns.append((key, key))

    # utf-8-sig helps Excel detect accents correctly while staying valid CSV.
    with open(csv_path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=[label for label, _ in output_columns])
        writer.writeheader()
        for row in per_turbine_table:
            writer.writerow({label: row.get(src, "") for label, src in output_columns})


def _get_val(container, key, idx):
    if isinstance(container, dict):
        return container.get(key, 0.0)
    if isinstance(container, (list, tuple)) and idx < len(container):
        return container[idx]
    return 0.0


def create_summary_layer(res_dict: Dict[str, Any], layer_name: str = "AEP resumen por modelo") -> QgsVectorLayer:
    """Create a QGIS memory table with model-level AEP summary values."""
    per_model = res_dict.get("per_model_aep_MWh") or {}
    per_model_free = res_dict.get("per_model_aep_free_MWh") or {}
    per_model_loss_wake = res_dict.get("per_model_loss_wake_MWh") or {}
    per_model_loss_ti = res_dict.get("per_model_loss_ti_MWh") or {}
    per_model_loss_blk = res_dict.get("per_model_loss_blk_MWh") or {}

    layer = QgsVectorLayer("None", layer_name, "memory")
    provider = layer.dataProvider()

    fields = QgsFields()
    fields.append(QgsField("model", QVariant.String))
    fields.append(QgsField("aep_op_mwh", QVariant.Double))
    fields.append(QgsField("aep_free_mwh", QVariant.Double))
    fields.append(QgsField("loss_wake_mwh", QVariant.Double))
    fields.append(QgsField("loss_ti_mwh", QVariant.Double))
    fields.append(QgsField("loss_blk_mwh", QVariant.Double))
    provider.addAttributes(fields)
    layer.updateFields()

    if isinstance(per_model, dict):
        model_names = list(per_model.keys())
    else:
        model_names = [str(i) for i in range(len(per_model))]

    features = []
    for idx, name in enumerate(model_names):
        feature = QgsFeature(fields)
        feature["model"] = name
        feature["aep_op_mwh"] = float(_get_val(per_model, name, idx))
        feature["aep_free_mwh"] = float(_get_val(per_model_free, name, idx))
        feature["loss_wake_mwh"] = float(_get_val(per_model_loss_wake, name, idx))
        feature["loss_ti_mwh"] = float(_get_val(per_model_loss_ti, name, idx))
        feature["loss_blk_mwh"] = float(_get_val(per_model_loss_blk, name, idx))
        features.append(feature)

    if features:
        provider.addFeatures(features)
    QgsProject.instance().addMapLayer(layer)
    return layer


__all__ = ["export_per_turbine_to_csv", "create_summary_layer"]

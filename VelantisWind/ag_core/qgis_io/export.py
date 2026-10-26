# -*- coding: utf-8 -*-
"""Export helpers for AEP results.

This module contains CSV export and QGIS memory summary layer creation. The old
``ag_core.export_results`` module remains as a compatibility façade.
"""
from __future__ import annotations

import csv
import json
import os
from typing import Any, Dict, List, Optional

from qgis.PyQt.QtCore import QVariant
from qgis.core import QgsFeature, QgsField, QgsFields, QgsProject, QgsVectorLayer


def wake_texts(result: Dict[str, Any]) -> Dict[str, str]:
    """The identification and the warnings of a result of schema 2, in the language of the interface: what the CSV,
    the summary layer and the point layers carry of the configuration (``wake_id``, ``wake_warn``)."""
    from ..log_text import shown
    from ..wake_setup.notices import result_warnings
    from ...i18n import tr_text
    return {"wake_id": str(shown(result["wake_config"]["identification"], tr_text)),
            "wake_warn": " | ".join(str(shown(w, tr_text)) for w in result_warnings(result))}


def wake_record(result: Dict[str, Any]) -> Dict[str, Any]:
    """The complete configuration of a result of schema 2, for the JSON next to the CSV and the summary layer. The
    edge cases (#63) only when the result has them: the grids executed with the exception of ``WeightedSum``, with
    its note, and the diagnoses and warnings."""
    record = {"result_schema_version": 2, "wake_config": result["wake_config"],
              "convergence": result.get("convergence"),
              "persistent_warnings": [str(w) for w in result.get("persistent_warnings") or []],
              "ti_aggregation": result.get("ti_aggregation")}
    if result.get("executed_ws"):
        from ..simulation.zero_node import zero_node_note
        record["executed_ws"] = dict(result["executed_ws"], note=str(zero_node_note(result["executed_ws"])))
    if result.get("edge_cases"):
        edge = result["edge_cases"]
        record["edge_cases"] = {"diagnoses": edge.get("diagnoses") or {},
                                "warnings": [str(w) for w in edge.get("warnings") or []]}
    return record


def wake_json_path(csv_path: str) -> str:
    """The JSON written next to a CSV: ``<name>.wake_config.json``."""
    return os.path.splitext(csv_path)[0] + ".wake_config.json"


def export_per_turbine_to_csv(per_turbine_table: List[Dict[str, Any]], csv_path: str,
                              result: Optional[Dict[str, Any]] = None) -> None:
    """Export a polished per-turbine CSV summary.

    The file stays GIS/Excel friendly: the first row is still the header, with no
    decorative comment lines. The corporate polish is applied through clear
    English column names, units in headers, a stable order and preservation of
    extra diagnostic fields at the end.

    With a ``result`` of schema 2, every row also carries the identification of the wake configuration and its
    warnings («Wake configuration», «Wake warnings»), and the complete configuration is written next to it
    (``wake_json_path``); the export fails if either file cannot be written.
    """
    if not per_turbine_table:
        return
    texts = wake_texts(result) if result and result.get("wake_config") else {}
    if texts:
        with open(wake_json_path(csv_path), "w", encoding="utf-8") as f:
            json.dump(wake_record(result), f, ensure_ascii=False, indent=2, default=str)
        per_turbine_table = [dict(row, **texts) for row in per_turbine_table]

    canonical = [
        ("Turbine ID", ["id", "turbine_id", "wt_id", "WTG", "turbine"]),
        ("Turbine model", ["model", "wt_name", "turbine_type", "name"]),
        ("X [m]", ["x", "X", "easting", "Easting"]),
        ("Y [m]", ["y", "Y", "northing", "Northing"]),
        ("Rated power [MW]", ["p_nom_mw", "p_rated_mw", "rated_power_mw", "rated_mw"]),
        ("Net AEP [MWh/year]", ["aep_mwh", "aep_MWh", "aep_net_mwh", "aep_net_MWh"]),
        ("Free-flow AEP [MWh/year]", ["aep_free_mwh", "aep_free_MWh", "gross_aep_mwh"]),
        # Schema 2 (signed: a loss L is positive when it takes production away, an impact Δ when it adds it).
        ("Wake loss L_W [MWh/year]", ["l_wake_mwh"]),
        ("Turbulence impact Δ_T [MWh/year]", ["d_turb_mwh"]),
        ("Blockage impact Δ_B [MWh/year]", ["d_blk_mwh"]),
        ("Total loss [MWh/year]", ["l_total_mwh"]),
        ("Ambient TI [-]", ["ti_ambient"]),
        ("Effective TI [-]", ["ti_effective"]),
        # Schema 1, for a result of the previous version.
        ("Wake losses [MWh/year]", ["loss_wake_mwh", "loss_wake_MWh", "wake_loss_mwh"]),
        ("Blockage losses [MWh/year]", ["loss_blk_mwh", "loss_blk_MWh", "blockage_loss_mwh"]),
        # The signed impact, not the clipped loss (#75, row 4.5).
        ("TI/turbulence impact [MWh/year]", ["ti_impact_mwh"]),
        ("Net capacity factor [%]", ["cf_net_pct", "capacity_factor_pct", "net_cf_pct"]),
    ]
    # The configuration and its warnings, the last two columns.
    last = [(label, key) for label, key in (("Wake configuration", "wake_id"), ("Wake warnings", "wake_warn"))
            if texts]

    all_keys: List[str] = []
    for row in per_turbine_table:
        for key in row.keys():
            if key not in all_keys:
                all_keys.append(key)

    used_keys = {key for _label, key in last}
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
    output_columns += last

    # utf-8-sig helps Excel detect accents correctly while staying valid CSV.
    with open(csv_path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=[label for label, _ in output_columns])
        writer.writeheader()
        for row in per_turbine_table:
            writer.writerow({label: _csv_value(row.get(src, "")) for label, src in output_columns})


def _csv_value(value: Any) -> Any:
    """A value of the CSV: a non-finite number with its label (#63, decision 10), anything else as it is."""
    from ..edge_cases import non_finite_label
    if isinstance(value, (bool, str)) or value is None:
        return value
    return non_finite_label(value) or value


def _get_val(container, key, idx):
    if isinstance(container, dict):
        return container.get(key, 0.0)
    if isinstance(container, (list, tuple)) and idx < len(container):
        return container[idx]
    return 0.0


def create_summary_layer(res_dict: Dict[str, Any], layer_name: str = "AEP resumen por modelo") -> QgsVectorLayer:
    """Create a QGIS memory table with model-level AEP summary values.

    With a result of schema 2, the signed breakdown of each model; a term that is not available is NULL, never zero
    (#75, row 4.6).
    """
    if int(res_dict.get("result_schema_version") or 1) == 2:
        return _create_summary_layer_v2(res_dict, layer_name)
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


_SUMMARY_V2 = (("aep_op_mwh", "A_WTB"), ("aep_free_mwh", "A_0"), ("l_wake_mwh", "L_W"), ("d_turb_mwh", "D_T"),
               ("d_blk_mwh", "D_B"), ("l_total_mwh", "L_total"))


def _create_summary_layer_v2(res_dict: Dict[str, Any], layer_name: str) -> QgsVectorLayer:
    per_model = res_dict.get("per_model_breakdown") or {}
    layer = QgsVectorLayer("None", layer_name, "memory")
    provider = layer.dataProvider()
    fields = QgsFields()
    fields.append(QgsField("model", QVariant.String))
    for name, _term in _SUMMARY_V2:
        fields.append(QgsField(name, QVariant.Double))
    fields.append(QgsField("wake_states", QVariant.String))
    for name in ("wake_id", "wake_warn", "wake_cfg"):
        fields.append(QgsField(name, QVariant.String))
    provider.addAttributes(fields)
    layer.updateFields()
    texts = (dict(wake_texts(res_dict), wake_cfg=json.dumps(wake_record(res_dict), ensure_ascii=False, default=str))
             if res_dict.get("wake_config") else {})
    features = []
    for name, entry in per_model.items():
        feature = QgsFeature(fields)
        feature["model"] = name
        for field, text in texts.items():
            feature[field] = text
        for field, term in _SUMMARY_V2:
            value = entry[term]["mwh"]
            feature[field] = float(value) if value is not None else None
        feature["wake_states"] = ";".join(f"{t}={entry[t]['state']}" for t in ("A_0", "L_W", "D_T", "D_B", "L_total"))
        features.append(feature)
    if features:
        provider.addFeatures(features)
    QgsProject.instance().addMapLayer(layer)
    return layer


__all__ = ["export_per_turbine_to_csv", "create_summary_layer"]

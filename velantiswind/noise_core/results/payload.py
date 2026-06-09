# -*- coding: utf-8 -*-
"""Final payload builder for the noise module."""
from __future__ import annotations

from typing import Dict, List, Optional, Any

import numpy as np


def _safe_feature_count(layer: Any) -> int:
    if layer is None:
        return 0
    try:
        return int(layer.featureCount())
    except Exception:
        return 0


def _serialize_source_for_runtime(src: Any) -> Dict[str, Any]:
    """Return a primitive-only source snapshot for optional background tasks."""
    try:
        lw_octave = {int(k): float(v) for k, v in ((getattr(src, "lw_octave", None) or {}).items())}
    except Exception:
        lw_octave = {}
    return {
        "model_name": str(getattr(src, "model_name", "") or ""),
        "source_group": str(getattr(src, "source_group", "") or ""),
        "park_name": str(getattr(src, "park_name", "") or ""),
        "layer_name": str(getattr(src, "layer_name", "") or ""),
        "x": float(getattr(src, "x", 0.0) or 0.0),
        "y": float(getattr(src, "y", 0.0) or 0.0),
        "hub_height": float(getattr(src, "hub_height", 0.0) or 0.0),
        "diameter": None if getattr(src, "diameter", None) is None else float(getattr(src, "diameter")),
        "lwa": float(getattr(src, "lwa", 0.0) or 0.0),
        "feature_id": int(getattr(src, "feature_id", -1) or -1),
        "z_ground": None if getattr(src, "z_ground", None) is None else float(getattr(src, "z_ground")),
        "lw_octave": lw_octave,
        "spectrum_source": str(getattr(src, "spectrum_source", "") or ""),
    }



def _receiver_rows_from_layer(layer: Any) -> List[Dict[str, Any]]:
    """Return all result-layer receiver rows as named dictionaries.

    This is used by CSV/XLSX exports as a stable fallback when the QGIS
    memory layer has display/provider issues.  The function uses positional
    access so duplicate input field names do not hide computed output fields
    appended later; if a name appears twice, the later/computed value wins.
    """
    rows: List[Dict[str, Any]] = []
    if layer is None:
        return rows
    try:
        fields = [fld.name() for fld in layer.fields()]
        for feat in layer.getFeatures():
            d: Dict[str, Any] = {}
            for idx, name in enumerate(fields):
                try:
                    d[name] = feat.attribute(idx)
                except Exception:
                    pass
            try:
                d.setdefault("fid", int(feat.id()))
                d.setdefault("rec_id", int(feat.id()))
            except Exception:
                pass
            rows.append(d)
    except Exception:
        return []
    return rows


def _top_receivers_from_rows(rows: List[Dict[str, Any]], limit: int = 15) -> List[Dict[str, Any]]:
    out = [dict(r) for r in (rows or []) if isinstance(r, dict)]
    def _noise(d: Dict[str, Any]) -> float:
        try:
            return float(d.get("noise_dba") or d.get("total_level_dba") or 0.0)
        except Exception:
            return -1.0e99
    out.sort(key=_noise, reverse=True)
    return out[:max(0, int(limit))]


def _top_receivers_from_layer(layer: Any, limit: int = 15) -> List[Dict[str, Any]]:
    return _top_receivers_from_rows(_receiver_rows_from_layer(layer), limit=limit)



def _as_float(v: Any, default: Optional[float] = None) -> Optional[float]:
    if v is None:
        return default
    try:
        text = str(v).strip()
        if text == '' or text.lower() in ('none', 'nan', 'n/a'):
            return default
        x = float(text.replace(',', '.'))
        return x if x == x else default
    except Exception:
        return default


def _receiver_attenuation_values(rows: List[Dict[str, Any]]) -> Dict[str, List[float]]:
    vals = {'adiv': [], 'aatm': [], 'aground': [], 'abar': []}
    for d in rows or []:
        if not isinstance(d, dict):
            continue
        nsrc = _as_float(d.get('n_src'), None)
        if nsrc is None:
            covered = _as_float(d.get('covered'), None)
            if covered is not None:
                is_covered = covered > 0
            else:
                noise = _as_float(d.get('noise_dba'), 0.0) or 0.0
                is_covered = noise > 0.0
        else:
            is_covered = nsrc > 0
        if not is_covered:
            continue
        for name, key in (('adiv', 'adiv_db'), ('aatm', 'aatm_db'), ('aground', 'aground_db')):
            x = _as_float(d.get(key), None)
            if x is not None:
                vals[name].append(float(x))
        x = _as_float(d.get('abar_max_db'), _as_float(d.get('abar_db'), None))
        if x is not None:
            vals['abar'].append(float(x))
    return vals

def build_noise_result_payload(
    *,
    result: Any,
    src_layer: Any,
    link_layer: Any,
    grid_layer: Any,
    iso_layer: Any,
    uncovered_layer: Any,
    sources: List[Any],
    receivers: List[Any],
    src_diag: Dict[str, Dict[str, Any]],
    out_feats: List[Any],
    dom_links: List[Dict[str, Any]],
    uncovered_ids: List[int],
    zero_receivers: int,
    n_exceed: int,
    max_noise: float,
    max_noise_fid: Optional[int],
    grid_diag: Dict[str, Any],
    alpha_db_per_m: float,
    ground_factor_g: float,
    ground_mode: str,
    active_landuse_layer: Any,
    receiver_height_m: float,
    max_radius_m: float,
    dem_layer: Any,
    adiv_vals: List[float],
    aatm_vals: List[float],
    aground_vals: List[float],
    abar_vals: List[float],
    ground_g_values: List[float],
    critical_receiver: Optional[Dict[str, Any]],
    ground_from_landuse_count: int,
    ground_fallback_count: int,
    applied_limits: List[float],
    receiver_type_counts: Dict[str, int],
    receiver_type_compliance: Dict[str, Dict[str, int]],
    receiver_limit_dba: float,
    receiver_limit_mode: str,
    receiver_limit_scenario: str,
    calculation_engine: str,
    temperature_c: float,
    humidity_percent: float,
    pressure_kpa: float,
    model_cfg: Dict[str, Dict[str, Any]],
    path_diagnostics: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, object]:
    """Build the rich dictionary consumed by the existing results dialog."""
    engine_name = "iso_aligned" if calculation_engine == "iso" else "fast"
    equation_summary = {
        "fast": "Lp = LwA - Adiv - Aatm - Aground",
        "iso_aligned": "Lp,b = Lw,b - Adiv - Aatm,b - Agr,b - Abar,b ; LpA,total = 10·log10(Σ 10^((Lp,b + A_weight)/10))",
    }
    receiver_rows = _receiver_rows_from_layer(result)
    fallback_att = _receiver_attenuation_values(receiver_rows)
    if not adiv_vals:
        adiv_vals = fallback_att.get('adiv', [])
    if not aatm_vals:
        aatm_vals = fallback_att.get('aatm', [])
    if not aground_vals:
        aground_vals = fallback_att.get('aground', [])
    if not abar_vals:
        abar_vals = fallback_att.get('abar', [])
    return {
        "method": "consultoria_v2_3_2" if engine_name == "fast" else "iso_aligned_v3_1_1",
        "result_layer": result,
        "result_layer_id": result.id(),
        "sources_layer": src_layer,
        "links_layer": link_layer,
        "grid_layer": grid_layer,
        "iso_layer": iso_layer,
        "uncovered_layer": uncovered_layer,
        "n_sources": len(sources),
        "n_receivers": len(receivers),
        "n_receivers_with_sources": len(receivers) - zero_receivers,
        "max_noise_dba": float(max_noise) if max_noise >= 0 else 0.0,
        "max_noise_receiver_fid": max_noise_fid,
        "n_dom_links": len(dom_links),
        "n_uncovered_receivers": len(uncovered_ids),
        "n_receivers_exceeding_limit": int(n_exceed),
        "n_iso_features": _safe_feature_count(iso_layer),
        "grid_cells": int(grid_diag.get('grid_cells', 0)),
        "model_diag": src_diag,
        "alpha_db_per_m": float(alpha_db_per_m),
        "ground_factor_g": float(ground_factor_g),
        "ground_mode": str(ground_mode or 'global'),
        "landuse_layer_name": str(active_landuse_layer.name()) if active_landuse_layer is not None else '',
        "receiver_height_m": float(receiver_height_m),
        "max_radius_m": float(max_radius_m),
        "dem_used": bool(dem_layer is not None),
        "dem_layer_name": str(dem_layer.name()) if dem_layer is not None else '',
        "grid_diag": grid_diag,
        # Primitive-only data used by optional QgsTask raster generation.
        # It is kept internal so the visual results dialog can ignore it.
        "_runtime_sources_snapshot": [_serialize_source_for_runtime(src) for src in sources],
        "adiv_stats": {"mean": float(np.mean(adiv_vals)) if adiv_vals else 0.0, "max": float(np.max(adiv_vals)) if adiv_vals else 0.0},
        "aatm_stats": {"mean": float(np.mean(aatm_vals)) if aatm_vals else 0.0, "max": float(np.max(aatm_vals)) if aatm_vals else 0.0},
        "aground_stats": {"mean": float(np.mean(aground_vals)) if aground_vals else 0.0, "max": float(np.max(aground_vals)) if aground_vals else 0.0},
        "abar_stats": {"mean": float(np.mean(abar_vals)) if abar_vals else 0.0, "max": float(np.max(abar_vals)) if abar_vals else 0.0},
        "g_eff_stats": {
            "mean": float(np.mean(ground_g_values)) if (active_landuse_layer is not None and ground_g_values) else float(ground_factor_g),
            "critical": float(critical_receiver.get('ground_factor_g')) if (active_landuse_layer is not None and critical_receiver and critical_receiver.get('ground_factor_g') == critical_receiver.get('ground_factor_g')) else float(ground_factor_g),
        },
        "ground_diag": {
            "from_landuse_count": int(ground_from_landuse_count),
            "fallback_count": int(ground_fallback_count),
            "from_landuse_pct": (100.0 * float(ground_from_landuse_count) / float(len(out_feats))) if (active_landuse_layer is not None and out_feats) else 0.0,
        },
        "limit_stats": {
            "mode": str(receiver_limit_mode or 'global'),
            "scenario": str(receiver_limit_scenario or 'custom'),
            "min": float(np.min(applied_limits)) if applied_limits else float(receiver_limit_dba),
            "max": float(np.max(applied_limits)) if applied_limits else float(receiver_limit_dba),
            "unique_count": int(len(set(round(v, 6) for v in applied_limits))) if applied_limits else 1,
        },
        "receiver_type_counts": receiver_type_counts,
        "receiver_type_compliance": receiver_type_compliance,
        "critical_receiver": critical_receiver,
        "receiver_rows": receiver_rows,
        "top_receivers": _top_receivers_from_layer(result),
        "path_diagnostics": list(path_diagnostics or []),
        "report_meta": {
            "engine": engine_name,
            "engine_label": "ISO-aligned por bandas" if engine_name == "iso_aligned" else "Rápido LwA global",
            "equation": equation_summary[engine_name],
            "temperature_c": float(temperature_c),
            "humidity_percent": float(humidity_percent),
            "pressure_kpa": float(pressure_kpa),
            "alpha_db_per_m": float(alpha_db_per_m),
            "ground_factor_g": float(ground_factor_g),
            "ground_mode": str(ground_mode or 'global'),
            "receiver_height_m": float(receiver_height_m),
            "max_radius_m": float(max_radius_m),
            "dem_used": bool(dem_layer is not None),
            "dem_layer_name": str(dem_layer.name()) if dem_layer is not None else '',
            "landuse_used": bool(active_landuse_layer is not None),
            "landuse_layer_name": str(active_landuse_layer.name()) if active_landuse_layer is not None else '',
            "grid_created": bool(grid_layer is not None),
            "iso_created": bool(iso_layer is not None),
            "active_terms": {
                "Adiv": True,
                "Aatm": True,
                "Agr": True,
                "Abar": bool(engine_name == 'iso_aligned' and dem_layer is not None),
                "landuse_g": bool(active_landuse_layer is not None),
            },
            "spectrum_sources": [
                {
                    "group_name": str((d or {}).get('name') or name),
                    "model_name": str((d or {}).get('model_name') or name),
                    "spectrum_source": str((d or {}).get('spectrum_source') or ''),
                    "lw_octave": {int(k): float(v) for k, v in ((d or {}).get('lw_octave') or {}).items()},
                    "spectrum_template_ref": {int(k): float(v) for k, v in ((d or {}).get('spectrum_template_ref') or {}).items()},
                    "spectrum_delta_db": float((d or {}).get('spectrum_delta_db', float('nan'))),
                }
                for name, d in src_diag.items()
            ],
        },
        "acoustic_scenario": {
            "mode": "curve" if any(str((d or {}).get('acoustic_mode') or '').lower() == 'curve' for d in (model_cfg or {}).values()) else "fixed",
            "eval_ws_m_s": float(next((float((d or {}).get('eval_ws_m_s')) for d in (model_cfg or {}).values() if (d or {}).get('eval_ws_m_s') is not None), float('nan'))),
            "use_curve_worst_case": bool(any(bool((d or {}).get('use_curve_worst_case', False)) for d in (model_cfg or {}).values())),
            "effective_models": [
                {
                    "name": str((d or {}).get('name') or name),
                    "model_name": str((d or {}).get('model_name') or name),
                    "park_name": str((d or {}).get('park_name') or ''),
                    "layer_name": str((d or {}).get('layer_name') or ''),
                    "lwa_effective": float((d or {}).get('lwa', float('nan'))),
                    "lwa_fixed": float((d or {}).get('lwa_fixed', float('nan'))),
                    "curve_note": str((d or {}).get('curve_note') or ''),
                    "acoustic_mode": str((d or {}).get('acoustic_mode') or 'fixed'),
                }
                for name, d in src_diag.items()
            ],
        },
    }

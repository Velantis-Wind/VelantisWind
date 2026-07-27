# -*- coding: utf-8 -*-
"""Built-in turbine candidates with explicit curve provenance.

The catalogue separates public/reference curves, manufacturer-neutral generic
approximations and clearly labelled commercial-model approximations anchored to
public technical specifications. The latter are never presented as OEM curves.
"""
from __future__ import annotations

import csv
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List, Mapping, Tuple


def _catalogue_root() -> Path:
    # .../VelantisWind/ag_core/turbines/library.py -> .../VelantisWind
    plugin_root = Path(__file__).resolve().parents[2]
    return plugin_root / "resources" / "turbines"


def _as_float(row: Mapping[str, str], key: str, default: float) -> float:
    try:
        return float(row.get(key, default))
    except Exception:
        return float(default)


@lru_cache(maxsize=1)
def load_builtin_candidates() -> Tuple[Dict[str, Any], ...]:
    """Return immutable candidate metadata loaded from the packaged CSV."""
    root = _catalogue_root()
    path = root / "builtin_turbine_candidates.csv"
    if not path.is_file():
        return tuple()

    out: List[Dict[str, Any]] = []
    with path.open("r", newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            curve_rel = str(row.get("curve_file") or "").strip()
            curve_path = (root / curve_rel).resolve() if curve_rel else None
            item: Dict[str, Any] = {
                "candidate_id": str(row.get("candidate_id") or "").strip(),
                "manufacturer": str(row.get("manufacturer") or "").strip(),
                "model": str(row.get("model") or "").strip(),
                "name": str(row.get("display_name") or "").strip(),
                "display_name": str(row.get("display_name") or "").strip(),
                "rated_kw": _as_float(row, "rated_kw", 0.0),
                "diam": _as_float(row, "diameter_m", 120.0),
                "hub": _as_float(row, "hub_height_m", 90.0),
                "cut_in": _as_float(row, "cut_in_m_s", 3.0),
                "rated_ws": _as_float(row, "rated_m_s", 12.0),
                "cut_out": _as_float(row, "cut_out_m_s", 25.0),
                "curve_path": str(curve_path) if curve_path is not None else "",
                "curve_kind": str(row.get("curve_kind") or "generic_parametric").strip(),
                "curve_quality": str(row.get("curve_quality") or "approximate").strip(),
                "category": str(row.get("category") or "").strip(),
                "source_name": str(row.get("source_name") or "").strip(),
                "source_url": str(row.get("source_url") or "").strip(),
                "source_note": str(row.get("source_note") or "").strip(),
                "spacing_long_d": _as_float(row, "spacing_long_d", 7.0),
                "spacing_trans_d": _as_float(row, "spacing_trans_d", 4.0),
            }
            if item["name"] and item["rated_kw"] > 0 and item["diam"] > 0:
                out.append(item)
    return tuple(out)


def load_candidate_curve(candidate: Mapping[str, Any]) -> Tuple[List[float], List[float], List[float]]:
    """Read ``ws, power_kW, ct`` for a catalogue candidate."""
    path = Path(str(candidate.get("curve_path") or ""))
    if not path.is_file():
        raise FileNotFoundError(f"Turbine curve not found: {path}")

    ws: List[float] = []
    power_kw: List[float] = []
    ct: List[float] = []
    with path.open("r", newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            try:
                ws.append(float(row["ws_m_s"]))
                power_kw.append(float(row["power_kW"]))
                ct.append(float(row["ct"]))
            except (KeyError, TypeError, ValueError):
                continue

    if len(ws) < 2 or len(ws) != len(power_kw) or len(ws) != len(ct):
        raise ValueError(f"Invalid turbine screening curve: {path.name}")
    if any(b <= a for a, b in zip(ws, ws[1:])):
        raise ValueError(f"Wind-speed values are not strictly increasing: {path.name}")
    return ws, power_kw, ct


def catalogue_summary() -> Dict[str, Any]:
    candidates = load_builtin_candidates()
    return {
        "candidate_count": len(candidates),
        "manufacturers": sorted({str(c.get("manufacturer") or "") for c in candidates if c.get("manufacturer")}),
        "public_reference_count": sum(1 for c in candidates if c.get("curve_quality") == "public_reference"),
        "spec_based_approximation_count": sum(
            1 for c in candidates if c.get("curve_quality") == "spec_based_approximation"
        ),
        "approximate_count": sum(1 for c in candidates if c.get("curve_quality") == "approximate"),
        "catalogue_path": str(_catalogue_root() / "builtin_turbine_candidates.csv"),
    }


__all__ = ["load_builtin_candidates", "load_candidate_curve", "catalogue_summary"]

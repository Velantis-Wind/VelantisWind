# -*- coding: utf-8 -*-
"""What the last AEP calculated with, to say which inputs of a wake raster differ from it (#36).

The wake raster reads all its inputs from the dialog when it is created, as the AEP does. The inputs of the last
correct AEP are kept in the dialog, summarised by ``from_run_config``, and the raster's are summarised the same way
(``summarise``), so that its final window can say which categories differ (``differences``). The summary is a
comparison within the session: a turbine is identified by its object, never written anywhere.

Only what changes the field of the raster is compared: not the speed step of the AEP, nor how an adaptation of the
wake model was accepted («Continuar» or a saved decision), which do not change the calculation.
"""
from __future__ import annotations

import math
from typing import Any, Dict, List, Optional

from ..ag_core.wake_setup.api import NOT_SET

# The categories, in the order they are said, with their Spanish source labels (translated when shown).
CATEGORIES = (
    ("turbines", "turbinas y posiciones"),
    ("resource", "recurso eólico y turbulencia"),
    ("wake", "modelo de estela"),
    ("density", "densidad del aire"),
    ("crs", "sistema de coordenadas del proyecto"),
)


def _freeze(value: Any) -> Any:
    """A comparable, immutable copy: mappings and sequences as tuples, a non-finite float as its text."""
    if isinstance(value, dict):
        return tuple((str(k), _freeze(v)) for k, v in sorted(value.items(), key=lambda kv: str(kv[0])))
    if isinstance(value, (list, tuple)):
        return tuple(_freeze(v) for v in value)
    if isinstance(value, float):
        return value if math.isfinite(value) else repr(value)
    if value is None or isinstance(value, (str, bool, int)):
        return value
    if hasattr(value, "tolist"):  # a NumPy array or scalar
        return _freeze(value.tolist())
    return repr(value)


def _field(model: Any, name: str) -> Any:
    return model.get(name) if isinstance(model, dict) else getattr(model, name, None)


def _wake(wake_physics: Any) -> Any:
    """The wake physics without how its adaptations were accepted; ``None`` when not given."""
    if wake_physics is NOT_SET or not isinstance(wake_physics, dict):
        return None
    physics = dict(wake_physics)
    physics["adaptations"] = [{k: v for k, v in dict(a).items() if k != "acceptance"}
                              for a in physics.get("adaptations") or []]
    return _freeze(physics)


def summarise(*, models: Any, wasp_dir: Any, wrg_paths: Any, wrg_ti_paths: Any, wrg_ti_heights_m: Any,
              fixed_ti: Any, direction_count: Any, wd_interp: Any, wake_physics: Any, density: Any,
              project_crs: Any) -> Dict[str, Any]:
    """The inputs of a calculation by category. ``models`` are the dialog's (dicts) or the run's
    (``TurbineModelInput``); ``density`` is the reading of the density controls (``{"mode": "off"}`` when off)."""
    # Metadata that is not a mapping is none, as the engine reads it.
    turbines = tuple((str(_field(m, "name") or ""), id(_field(m, "wt")),
                      _freeze(_field(m, "meta") if isinstance(_field(m, "meta"), dict) else {}),
                      _freeze(list(_field(m, "coords_xy") or []))) for m in models or [])
    if wrg_paths:
        ti = list(wrg_ti_paths or [])
        resource = ("wrg", _freeze(list(wrg_paths)), _freeze(ti), _freeze(list(wrg_ti_heights_m or []) if ti else []),
                    None if ti else _freeze(fixed_ti), _freeze(direction_count), str(wd_interp or "nearest"))
    else:
        resource = ("wasp", str(wasp_dir or ""))
    density = dict(density or {})
    if str(density.get("mode") or "off") == "off":
        density = {"mode": "off"}
    elif density.get("mode") == "uniform":
        density.pop("reference_altitude_m", None)  # a uniform density does not use it
    return {"turbines": turbines, "resource": resource, "wake": _wake(wake_physics), "density": _freeze(density),
            "crs": str(project_crs or "")}


def from_run_config(config: Any) -> Dict[str, Any]:
    """The summary of an AEP from the configuration it ran with (``energy_core.domain.EnergyRunConfig``)."""
    mode = str(getattr(config, "air_density_mode", "off") or "off")
    density = {"mode": "off"} if mode == "off" else {
        "mode": mode, "reference_density_kg_m3": getattr(config, "air_density_ref_kg_m3", None),
        "reference_altitude_m": getattr(config, "air_density_ref_altitude_m", None)}
    return summarise(
        models=getattr(config, "models", []), wasp_dir=getattr(config, "wasp_dir", ""),
        wrg_paths=getattr(config, "wrg_paths", None), wrg_ti_paths=getattr(config, "wrg_ti_paths", None),
        wrg_ti_heights_m=getattr(config, "wrg_ti_heights_m", None), fixed_ti=getattr(config, "fixed_ti", None),
        direction_count=getattr(config, "wrg_direction_count", None),
        wd_interp=getattr(config, "wrg_wd_interp", "nearest"), wake_physics=getattr(config, "wake_physics", NOT_SET),
        density=density, project_crs=getattr(config, "project_crs_authid", ""))


def differences(previous: Optional[Dict[str, Any]], current: Dict[str, Any]) -> List[str]:
    """The labels of the categories that differ, in order; none without a previous AEP."""
    if previous is None:
        return []
    return [label for key, label in CATEGORIES if previous.get(key) != current.get(key)]

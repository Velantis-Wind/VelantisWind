# -*- coding: utf-8 -*-
"""The reference air density of the Energy dialog, kept in the QGIS project (#36).

It belongs to the site, so it is saved with the project (``.qgs``/``.qgz``) and not in the plugin's settings, which
every project shares: a project without one starts «sin definir» (the calculation then stops if the adjustment is
switched on), and never takes the reference of another project. The values of earlier versions, in those settings,
are not imported, for the same reason.
"""
from __future__ import annotations

from typing import Any, Dict

SCOPE = "VelantisWind"
MODES = ("per_turbine", "uniform")
# «Sin definir»: the adjustment off and both values at the minimum of their controls.
UNDEFINED: Dict[str, Any] = {"enabled": False, "mode": "per_turbine", "reference_density_kg_m3": 0.0,
                             "reference_altitude_m": -1000.0}


def read_project_density(project: Any) -> Dict[str, Any]:
    """The density saved in ``project``, or «sin definir» for what it does not have."""
    enabled, has_enabled = project.readBoolEntry(SCOPE, "/air_density_enabled", UNDEFINED["enabled"])
    mode, _ = project.readEntry(SCOPE, "/air_density_mode", UNDEFINED["mode"])
    density, _ = project.readDoubleEntry(SCOPE, "/air_density_ref_kg_m3", UNDEFINED["reference_density_kg_m3"])
    altitude, _ = project.readDoubleEntry(SCOPE, "/air_density_ref_altitude_m", UNDEFINED["reference_altitude_m"])
    return {"enabled": bool(enabled) if has_enabled else UNDEFINED["enabled"],
            "mode": mode if mode in MODES else UNDEFINED["mode"],
            "reference_density_kg_m3": float(density), "reference_altitude_m": float(altitude)}


def write_project_density(project: Any, values: Dict[str, Any]) -> None:
    """Save ``values`` (the keys of ``UNDEFINED``) in ``project``, which QGIS then marks as modified."""
    project.writeEntryBool(SCOPE, "/air_density_enabled", bool(values["enabled"]))
    project.writeEntry(SCOPE, "/air_density_mode", str(values["mode"]))
    project.writeEntryDouble(SCOPE, "/air_density_ref_kg_m3", float(values["reference_density_kg_m3"]))
    project.writeEntryDouble(SCOPE, "/air_density_ref_altitude_m", float(values["reference_altitude_m"]))

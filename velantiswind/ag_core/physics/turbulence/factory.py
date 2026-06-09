# -*- coding: utf-8 -*-
"""Factoría de modelos de turbulencia PyWake.

Mantiene todos los imports robustos y fallbacks de turbulencia fuera del cálculo
AEP monolítico. No depende de QGIS: recibe un logger opcional desde el motor.
"""
from __future__ import annotations

from typing import Any, Optional
import numpy as np

from ..common.compat import emit, try_import_cls


class ConstantTurbulenceModel:
    """Modelo de turbulencia mínimo: no añade turbulencia; TI_eff ~= TI ambiente."""

    def __init__(self, ti: float = 0.10):
        try:
            self.ti = float(ti)
        except Exception:
            self.ti = 0.10

    def calc_added_turbulence(self, *args, **kwargs):
        for key in ("dw_ijlk", "cw_ijlk", "D_src_il", "D_dst_il", "x_ijlk", "y_ijlk"):
            arr = kwargs.get(key, None)
            if hasattr(arr, "shape"):
                return np.zeros_like(arr, dtype=float)
        for arg in args:
            if hasattr(arg, "shape"):
                return np.zeros_like(arg, dtype=float)
        return 0.0

    def __call__(self, *args, **kwargs):
        return self.calc_added_turbulence(*args, **kwargs)

    def calc_effective_TI(self, *args, **kwargs):
        ti_ilk = kwargs.get("TI_ilk", kwargs.get("TI", None))
        if ti_ilk is None:
            return self.ti
        return ti_ilk


def _discover_default_turbulence_class():
    turb_cls = None
    for mod, cls in [
        ("py_wake.turbulence_models.stf", "STF2017TurbulenceModel"),
        ("py_wake.turbulence_models.stf", "STF2005TurbulenceModel"),
        ("py_wake.turbulence_models", "STF2017TurbulenceModel"),
        ("py_wake.turbulence_models", "STF2005TurbulenceModel"),
        ("py_wake.turbulence_models.crespo", "CrespoHernandez"),
        ("py_wake.turbulence_models.gcl", "GCLTurbulence"),
        ("py_wake.turbulence_models.larsen", "LarsenTurbulence"),
        ("py_wake.turbulence_models", "CrespoHernandez"),
        ("py_wake.turbulence_models", "GCLTurbulence"),
        ("py_wake.turbulence_models", "LarsenTurbulence"),
    ]:
        if turb_cls is None:
            turb_cls = try_import_cls(mod, cls)
    return turb_cls


TURB_MODEL_CLS = _discover_default_turbulence_class()


def make_turbulence_model(key: Optional[str], include_turbulence: bool = True, *, log=None) -> Any:
    """Crea el turbulence model seleccionado.

    key puede ser: 'NONE'|'STF2005'|'STF2017'|'GCL'|'CH'|'AUTO' o nombres de clase.
    Devuelve una instancia o None.
    """
    if not include_turbulence:
        return None

    if key is None:
        raw = "AUTO"
    else:
        raw = str(key).strip()
        if raw == "":
            emit(log, "[AEP] Turbulence model: None (no seleccionado)")
            return None

    normalized = raw.upper().replace(" ", "")
    mapping = {
        "NONE": "NONE",
        "NINGUNO": "NONE",
        "NO": "NONE",
        "OFF": "NONE",
        "AUTO": "AUTO",
        "STF2005": "STF2005",
        "STF2005TURBULENCEMODEL": "STF2005",
        "STF2017": "STF2017",
        "STF2017TURBULENCEMODEL": "STF2017",
        "GCL": "GCL",
        "GCLTURBULENCE": "GCL",
        "GCLTURBULENCEMODEL": "GCL",
        "CRESPOHERNANDEZ": "CH",
        "CH": "CH",
    }
    key_norm = mapping.get(normalized, mapping.get(normalized.replace("_", ""), normalized))
    if key_norm == "NONE":
        emit(log, "[AEP] Turbulence model: None (sin turbulencia)")
        return None

    stf2017 = try_import_cls("py_wake.turbulence_models.stf", "STF2017TurbulenceModel") or try_import_cls("py_wake.turbulence_models", "STF2017TurbulenceModel")
    stf2005 = try_import_cls("py_wake.turbulence_models.stf", "STF2005TurbulenceModel") or try_import_cls("py_wake.turbulence_models", "STF2005TurbulenceModel")
    gcl = try_import_cls("py_wake.turbulence_models.gcl", "GCLTurbulence") or try_import_cls("py_wake.turbulence_models", "GCLTurbulence")
    ch = try_import_cls("py_wake.turbulence_models.crespo", "CrespoHernandez") or try_import_cls("py_wake.turbulence_models", "CrespoHernandez")

    if key_norm == "AUTO":
        cls = TURB_MODEL_CLS or stf2017 or stf2005 or gcl or ch
    else:
        cls = {
            "STF2017": stf2017,
            "STF2005": stf2005,
            "GCL": gcl,
            "CH": ch,
        }.get(key_norm) or TURB_MODEL_CLS

    if cls is None:
        emit(log, "[AEP] Turbulence model seleccionado no disponible en esta instalación de PyWake. Se desactiva turbulencia.")
        return None

    try:
        obj = cls()
        emit(log, f"[AEP] Turbulence model (seleccionado): {obj.__class__.__name__}")
        return obj
    except Exception as exc:
        emit(log, f"[AEP] Error creando turbulence model '{getattr(cls, '__name__', str(cls))}': {exc}. Se desactiva turbulencia.")
        return None


def make_turbulence_fallback(*, log=None) -> Any:
    """Fallback seguro para modelos que requieren TI_eff."""
    return (
        make_turbulence_model("STF2017", include_turbulence=True, log=log)
        or make_turbulence_model("STF2005", include_turbulence=True, log=log)
        or make_turbulence_model("GCL", include_turbulence=True, log=log)
        or ConstantTurbulenceModel(0.10)
    )

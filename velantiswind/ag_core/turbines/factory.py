# -*- coding: utf-8 -*-
"""Construcción robusta de turbinas PyWake.

Extraído desde ``ag_core.aep_compute`` para que el motor principal no mezcle
orquestación AEP con detalles de PowerCtFunction / WindTurbines. Mantiene
compatibilidad con varias versiones de PyWake y con los diccionarios que crea
la UI del plugin.
"""
from __future__ import annotations

import inspect
from inspect import signature
from typing import Any, Callable, Dict, List, Optional, Tuple

import numpy as np

from ..physics.common.compat import emit

try:  # pragma: no cover - depende del entorno QGIS/PyWake del usuario
    from py_wake.wind_turbines._wind_turbines import WindTurbines
except Exception:  # pragma: no cover
    WindTurbines = None  # type: ignore
try:  # pragma: no cover
    from py_wake.wind_turbines.power_ct_functions import PowerCtFunctionList
except Exception:  # pragma: no cover
    PowerCtFunctionList = None  # type: ignore


class _QgisLevels:
    Info: Any = None
    Warning: Any = None


Qgis = _QgisLevels()
_LOG: Optional[Callable[..., None]] = None


def configure_logging(log: Optional[Callable[..., None]] = None, *, warning_level: Any = None, info_level: Any = None) -> None:
    """Inyecta logger/QGIS levels desde ``aep_compute`` sin acoplar este módulo a QGIS."""
    global _LOG
    _LOG = log
    Qgis.Warning = warning_level
    Qgis.Info = info_level


def _log(msg: str, level: Any = None) -> None:
    emit(_LOG, msg, level)


def _dump_obj_signature(tag: str, obj: Any) -> None:
    try:
        mod = getattr(obj, "__module__", "?")
        name = obj.__class__.__name__ if not inspect.isclass(obj) else obj.__name__
        try:
            sig = str(inspect.signature(obj.__init__ if not inspect.isclass(obj) else obj))
        except Exception:
            sig = "n/d"
        _log(f"[{tag}] clase={name} | módulo={mod} | firma={sig}")
        _log(f"[{tag}] repr={repr(obj)}")
    except Exception as e:
        _log(f"[{tag}] No se pudo obtener firma/repr: {e}", Qgis.Warning)


def is_pcf_list(pcf: Any) -> bool:
    try:
        cls = pcf.__class__.__name__.lower()
    except Exception:
        cls = ""
    if "powerctfunctionlist" in cls:
        return True
    return any(
        hasattr(pcf, attr)
        for attr in ("funcs", "functions", "powerCtFunctions", "powerCtFunction", "function_list", "pcfs")
    )


def unwrap_pcf_list(pcf: Any) -> Any:
    for attr in ("funcs", "functions", "powerCtFunctions", "powerCtFunction", "function_list", "pcfs"):
        inner = getattr(pcf, attr, None)
        if inner:
            try:
                return inner[0]
            except Exception:
                pass
    try:
        it = iter(pcf)
        return next(it)
    except Exception:
        return pcf


def extract_flat_pcf(obj: Any) -> Any:
    """Devuelve una PowerCtFunction simple, desenvolviendo listas cuando sea necesario."""
    if isinstance(obj, dict):
        pcf = obj.get("powerCtFunction") or obj.get("pcf")
    else:
        pcf = getattr(obj, "powerCtFunction", None)
        if pcf is None:
            pcfs = getattr(obj, "powerCtFunctions", None)
            if pcfs:
                if len(pcfs) > 1:
                    _log("[WT] Varias powerCtFunctions internas; se usa la primera.", Qgis.Warning)
                pcf = pcfs[0]
    if pcf is None:
        raise RuntimeError("No se encontró una PowerCtFunction válida.")
    if is_pcf_list(pcf):
        _log("[WT] powerCtFunction es PowerCtFunctionList -> se toma la primera.", Qgis.Warning)
        pcf = unwrap_pcf_list(pcf)
    if not hasattr(pcf, "__call__"):
        # algunos PCF ofrecen .power(ws)
        if not hasattr(pcf, "power"):
            raise RuntimeError("La PowerCtFunction no es invocable tras desenvolver.")
    return pcf


def ensure_wt_entry(m: Dict[str, Any]) -> Tuple[str, float, float, Any]:
    """Normaliza una entrada de turbina creada por UI/preset/CSV."""
    meta = m.get("meta") if isinstance(m.get("meta"), dict) else {}
    name = m.get("name") or meta.get("name") or "Custom WT"
    diam = meta.get("diam", m.get("diam", 120.0))
    try:
        diam = float(diam)
    except Exception:
        diam = 120.0
    hh = meta.get("hh", m.get("hh", m.get("hub_height", 100.0)))
    try:
        hh = float(hh)
    except Exception:
        hh = 100.0
    if not np.isfinite(hh) or hh <= 0:
        hh = 100.0
    wt_obj = m.get("wt", m)
    pcf = extract_flat_pcf(wt_obj)
    _log(f"[WT] {name}: D={diam}, Hub={hh} -> PowerCtFunction OK")
    return name, diam, hh, pcf


def combine_wt(models: List[Dict[str, Any]]) -> Tuple[Any, bool]:
    """
    Crea un ``WindTurbines`` combinado.

    Solo usa ``PowerCtFunctionList('type_i', ...)`` cuando hay más de un modelo.
    Con un único modelo se mantiene una PCF simple para que PyWake no exija
    ``type_i`` innecesariamente.
    """
    if WindTurbines is None:
        raise RuntimeError("PyWake WindTurbines no está disponible en este entorno.")

    names, diams, hubs, pcfs = [], [], [], []
    for m in models:
        meta = m.get("meta") if isinstance(m.get("meta"), dict) else {}
        name = m.get("name") or meta.get("name") or "Custom WT"
        D = meta.get("diam", m.get("diam", 120.0))
        HH = meta.get("hh", m.get("hh", m.get("hub_height", 100.0)))
        try:
            D = float(D)
        except Exception:
            D = 120.0
        try:
            HH = float(HH)
        except Exception:
            HH = 100.0

        pcf = m.get("powerCtFunction") or m.get("pcf")
        if pcf is None:
            # En modo CSV la WT normalmente ya viene construida desde turbine.py.
            # No reconstruimos aquí la PowerCtFunction desde CSV para evitar acoplar
            # este módulo a loaders internos de PyWake que cambian entre versiones.
            pcf = extract_flat_pcf(m.get("wt", m))

        if not hasattr(pcf, "__call__") and not hasattr(pcf, "power"):
            raise ValueError(f"No se encontró/creó una PowerCtFunction válida para el modelo '{name}'.")

        names.append(name)
        diams.append(D)
        hubs.append(HH)
        pcfs.append(pcf)

    n_types = len(pcfs)
    use_types = n_types > 1

    params = signature(WindTurbines.__init__).parameters
    if "powerCtFunctions" in params:
        # API moderna con argumento plural
        if use_types:
            wt_all = WindTurbines(names=names, diameters=diams, hub_heights=hubs, powerCtFunctions=pcfs)
            # Para garantizar mapping estable por type_i:
            try:
                if PowerCtFunctionList is not None:
                    wt_all.powerCtFunction = PowerCtFunctionList("type_i", pcfs)
                wt_all.powerCtFunctions = pcfs
            except Exception:
                pass
        else:
            # Un solo tipo -> PCF simple (no usar lista como función principal)
            wt_all = WindTurbines(names=names, diameters=diams, hub_heights=hubs, powerCtFunctions=[pcfs[0]])
            try:
                wt_all.powerCtFunction = pcfs[0]
            except Exception:
                pass
    else:
        # API más vieja con 'powerCtFunction' singular
        if use_types:
            if PowerCtFunctionList is None:
                raise RuntimeError("PowerCtFunctionList no está disponible para combinar varios modelos.")
            pcf_multi = PowerCtFunctionList("type_i", pcfs)
            wt_all = WindTurbines(names=names, diameters=diams, hub_heights=hubs, powerCtFunction=pcf_multi)
        else:
            wt_all = WindTurbines(names=names, diameters=diams, hub_heights=hubs, powerCtFunction=pcfs[0])

    try:
        _log(f"[WT] n_tipos={n_types} | nombres={names}")
        _log(f"[WT] diametros={diams} | hub_heights={hubs}")
        _dump_obj_signature("WT.PowerCtFunction", wt_all.powerCtFunction)
        _log(f"WT combinado: {type(wt_all).__name__} | use_types={use_types}")
    except Exception:
        pass

    return wt_all, use_types


# Aliases compatibles con el código histórico
_is_pcf_list = is_pcf_list
_unwrap_pcf_list = unwrap_pcf_list
_extract_flat_pcf = extract_flat_pcf
_ensure_wt_entry = ensure_wt_entry
_combine_wt = combine_wt

__all__ = [
    "configure_logging",
    "is_pcf_list",
    "unwrap_pcf_list",
    "extract_flat_pcf",
    "ensure_wt_entry",
    "combine_wt",
    "_is_pcf_list",
    "_unwrap_pcf_list",
    "_extract_flat_pcf",
    "_ensure_wt_entry",
    "_combine_wt",
]

# -*- coding: utf-8 -*-
"""Carga robusta de recursos WAsP/py_wake para el módulo AEP.

Este módulo concentra el saneo de carpetas WAsP y la carga de ``WaspGridSite``
para que ``ag_core.aep_compute`` no mezcle IO de recurso con el cálculo.
No depende de QGIS directamente: recibe un logger opcional desde el motor.
"""
from __future__ import annotations

import os
import re
from typing import Any, Callable, List, Optional, Tuple

from ..physics.common.compat import emit

try:
    from py_wake.site.wasp_grid_site import WaspGridSite
except Exception:  # pragma: no cover - py_wake puede no estar instalado al importar docs/tests
    WaspGridSite = None  # type: ignore

try:
    from ...union_recurso import load_waspgridsite as _robust_loader
except Exception:
    try:
        from union_recurso import load_waspgridsite as _robust_loader  # type: ignore
    except Exception:
        _robust_loader = None

class _QgisLevels:
    Info: Any = None
    Warning: Any = None

Qgis = _QgisLevels()
_LOG: Optional[Callable[..., None]] = None


def configure_logging(log: Optional[Callable[..., None]] = None, *, warning_level: Any = None, info_level: Any = None) -> None:
    global _LOG
    _LOG = log
    Qgis.Warning = warning_level
    Qgis.Info = info_level


def _log(msg: str, level: Any = None) -> None:
    emit(_LOG, msg, level)

# Patrón real que usa py_wake en wasp_grid_site.py:
_PYW_NAME_RE = re.compile(r"Sector (\w+|\d+)\s+ Height (\d+\.?\d*)m\s+ ([a-zA-Z0-9\- ]+)")

def _resolve_wasp_dir_for_pywake(wasp_dir: str) -> str:
    """Si existe 'pywake_compat' dentro de wasp_dir, úsala. Si no, usa wasp_dir."""
    cand = os.path.join(wasp_dir, "pywake_compat")
    if os.path.isdir(cand) and any(fn.lower().endswith(".grd") for fn in os.listdir(cand)):
        return cand
    return wasp_dir

def _sanitize_dir_for_pywake(dirpath: str, move_bad: bool = True) -> Tuple[int, int, List[str]]:
    """
    Valida los .grd con el patrón de py_wake. Si move_bad=True, mueve los que no casen a _bad_for_pywake.
    Devuelve: (total, moved, bad_list)
    """
    total = 0; moved = 0; bad = []
    if not os.path.isdir(dirpath):
        return 0, 0, []
    bad_dir = os.path.join(dirpath, "_bad_for_pywake")
    if move_bad:
        try:
            os.makedirs(bad_dir, exist_ok=True)
        except Exception:
            move_bad = False

    for f in os.listdir(dirpath):
        if not f.lower().endswith(".grd"):
            continue
        total += 1
        full = os.path.join(dirpath, f)
        if not _PYW_NAME_RE.search(f):
            bad.append(f)
            if move_bad:
                try:
                    os.replace(full, os.path.join(bad_dir, f))
                    moved += 1
                except Exception:
                    pass
    return total, moved, bad

def _load_site_with_filter(wasp_dir: str,
                           prefer_pywake_compat: bool = True,
                           sanitize: bool = True):
    """
    Carga el WaspGridSite con tolerancia:
      - Busca pywake_compat (si existe, la prioriza).
      - Valida nombres; si hay mismatches y sanitize=True, los mueve a _bad_for_pywake.
      - Usa loader robusto (union_recurso) si está disponible; si no, WaspGridSite.from_wasp_grd.
    Devuelve (site, dataset, used_dir)
    """
    load_dir = _resolve_wasp_dir_for_pywake(wasp_dir) if prefer_pywake_compat else wasp_dir
    if os.path.normpath(load_dir) != os.path.normpath(wasp_dir):
        _log(f"[WAsP] Usando subcarpeta prioritaria: {load_dir}")

    # Validar y sanear si hace falta
    tot, moved, bad = _sanitize_dir_for_pywake(load_dir, move_bad=sanitize)
    if bad:
        _log(f"[WAsP] Archivos que NO casaban con el patrón py_wake: {len(bad)}", Qgis.Warning)
        if sanitize:
            _log(f"[WAsP] Movidos a '_bad_for_pywake': {moved} (evita crash).", Qgis.Warning)
        else:
            raise RuntimeError(f"Hay {len(bad)} nombres que no casan con py_wake en: {load_dir}")

    # Loader robusto si está disponible
    site = None; ds = None
    if callable(_robust_loader):
        try:
            site, ds = _robust_loader(load_dir, verbose=False)  # type: ignore
            _log("[WAsP] Cargado con loader robusto (union_recurso.load_waspgridsite)")
            return site, ds, load_dir
        except Exception as e:
            _log(f"[WAsP] Loader robusto falló: {e}. Probando loader estándar…", Qgis.Warning)

    # Fallback estándar
    site = WaspGridSite.from_wasp_grd(load_dir)
    ds = getattr(site, "ds", None)
    _log("[WAsP] Cargado con loader estándar de py_wake")
    return site, ds, load_dir

resolve_wasp_dir_for_pywake = _resolve_wasp_dir_for_pywake
sanitize_dir_for_pywake = _sanitize_dir_for_pywake
load_site_with_filter = _load_site_with_filter

__all__ = [
    "configure_logging",
    "resolve_wasp_dir_for_pywake",
    "sanitize_dir_for_pywake",
    "load_site_with_filter",
]

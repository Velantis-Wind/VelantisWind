# -*- coding: utf-8 -*-
"""Lectura, evaluación y diagnóstico de curvas de potencia/CT.

Este módulo concentra los helpers usados para imprimir y verificar curvas de
potencia sin ensuciar el orquestador AEP. No depende directamente de QGIS.
"""
from __future__ import annotations

import csv
import os
from typing import Any, Callable, Dict, List, Optional, Tuple

import numpy as np

from ..physics.common.compat import emit
from .factory import ensure_wt_entry

F32 = np.float32


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


def auto_unit(P_arr: np.ndarray) -> Tuple[float, str]:
    try:
        pmax = float(np.nanmax(P_arr))
    except Exception:
        return 1.0, "W"
    if pmax >= 1e6:
        return 1e6, "MW"
    if pmax >= 1e3:
        return 1e3, "kW"
    return 1.0, "W"


def tabular_from_pcf(pcf: Any) -> Optional[Tuple[np.ndarray, np.ndarray]]:
    # Intenta extraer tablas internas habituales.
    ws_keys = ("ws", "u", "U", "wind_speeds", "u_ms")
    p_keys = ("power", "P", "Pow", "pow")
    ws = None
    P = None
    for k in ws_keys:
        v = getattr(pcf, k, None)
        if v is not None:
            try:
                ws = np.asarray(v, dtype=F32).ravel()
                break
            except Exception:
                pass
    for k in p_keys:
        v = getattr(pcf, k, None)
        if v is not None:
            try:
                P = np.asarray(v, dtype=F32).ravel()
                break
            except Exception:
                pass
    if ws is not None and P is not None and len(ws) == len(P) and len(ws) > 1:
        return ws, P
    return None


def eval_power(pcf: Any, ws: np.ndarray) -> Optional[np.ndarray]:
    try:
        out = pcf(ws, run_only=False)
        if isinstance(out, tuple):
            return np.asarray(out[0], dtype=F32)
        return np.asarray(out, dtype=F32)
    except Exception:
        try:
            return np.asarray(pcf.power(ws), dtype=F32)
        except Exception:
            return None


def read_curve_from_model_dict(m: Dict[str, Any]) -> Optional[Tuple[np.ndarray, np.ndarray]]:
    """
    Lee la curva de potencia directamente del CSV original definido en la UI.

    Devuelve ``(ws, P)`` como arrays numpy o ``None`` si no puede.
    """
    meta = m.get("meta") if isinstance(m.get("meta"), dict) else {}

    path = meta.get("path") or m.get("path") or m.get("curve_csv") or m.get("cp_csv")
    if not path or not os.path.isfile(path):
        return None

    ws_col = int(meta.get("ws_col", m.get("ws_col", 0)))
    power_col = int(meta.get("power_col", m.get("power_col", 1)))
    delimiter = str(meta.get("delimiter", m.get("delimiter", ",")))
    skip_header = int(meta.get("skip_header", m.get("skip_header", 1)))

    ws, P = [], []
    try:
        with open(path, newline="", encoding="utf-8") as f:
            r = csv.reader(f, delimiter=delimiter)
            for _ in range(max(skip_header, 0)):
                next(r, None)
            for row in r:
                if len(row) <= max(ws_col, power_col):
                    continue
                try:
                    ws.append(float(row[ws_col]))
                    P.append(float(row[power_col]))
                except Exception:
                    continue
    except Exception as e:
        _log(f"[WT] Error leyendo CSV de curva '{path}': {e}", Qgis.Warning)
        return None

    if len(ws) < 2:
        return None

    return np.array(ws, dtype=F32), np.array(P, dtype=F32)


def print_power_curve_info(models: List[Dict[str, Any]]) -> None:
    _log("=== [WT] Curvas de potencia / geometría ===")
    for m in models:
        name, D, HH, pcf = ensure_wt_entry(m)

        # 1) Intentar leer tabla directamente de la PowerCtFunction.
        wsP = tabular_from_pcf(pcf)

        # 2) Si no hay tabla interna, intentar evaluar la función en una rejilla.
        if wsP is None:
            ws_grid = np.array([0, 3, 5, 7, 9, 11, 13, 15, 17, 19, 21, 23, 25], dtype=F32)
            P = eval_power(pcf, ws_grid)
            if P is not None:
                fac, unit = auto_unit(P)
                idxs = [1, 3, 5, 7, 9, 11]
                idxs = [i for i in idxs if i < len(ws_grid)]
                pairs = ", ".join([f"{ws_grid[i]:.0f}→{P[i] / fac:.1f} {unit}" for i in idxs])
                _log(f"[WT] {name} | Hub={HH} m | D={D} m | Curva (eval): {pairs}")
                continue

        # 3) Si tampoco se puede evaluar, leemos directo del CSV del diálogo.
        if wsP is None:
            wsP = read_curve_from_model_dict(m)

        if wsP is not None:
            ws, P = wsP
            fac, unit = auto_unit(P)
            pairs = ", ".join([f"{w:.2f}→{p / fac:.2f} {unit}" for w, p in zip(ws, P)])
            _log(f"[WT] {name} | Hub={HH} m | D={D} m | Curva (CSV): {pairs}")
        else:
            _log(
                f"[WT] {name} | Hub={HH} m | D={D} m | Curva: no se pudo evaluar ni leer del CSV.",
                Qgis.Warning,
            )


# Aliases compatibles con el código histórico.
_auto_unit = auto_unit
_tabular_from_pcf = tabular_from_pcf
_eval_power = eval_power
_read_curve_from_model_dict = read_curve_from_model_dict
_print_power_curve_info = print_power_curve_info

__all__ = [
    "configure_logging",
    "auto_unit",
    "tabular_from_pcf",
    "eval_power",
    "read_curve_from_model_dict",
    "print_power_curve_info",
    "_auto_unit",
    "_tabular_from_pcf",
    "_eval_power",
    "_read_curve_from_model_dict",
    "_print_power_curve_info",
]

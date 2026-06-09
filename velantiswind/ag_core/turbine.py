# -*- coding: utf-8 -*-
"""
Utilidades para gestionar turbinas en PyWake (v2.6.7 comprobado):

- Presets de PyWake listos para usar (p.ej. V80, IEA37) con carga perezosa.
- Creación de turbinas personalizadas a partir de:
    * Listas manuales de velocidades y potencias (kW).
    * Ficheros TXT/CSV (potencias en kW), con columnas configurables.
- Estimación de curva de CT cuando no se dispone de ella.

Notas:
- Todas las potencias de entrada se esperan en kW y se convierten a W para PyWake.
- Las curvas se ordenan por velocidad y la potencia se fuerza a ser no decreciente.
- Optional console diagnostics are disabled by default and can be enabled with VELANTISWIND_DEBUG=1.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import List, Callable, Dict, Optional, Tuple, TYPE_CHECKING, Any
import csv
import math
import os

# PyWake se importa de forma perezosa dentro de las funciones que lo necesitan.
# Motivo: en algunos entornos Windows/QGIS, cargar PyWake al abrir el diálogo
# puede disparar DLLs compiladas de dependencias externas (p. ej. *_compute.pyd)
# y hacer que el diálogo de turbina no llegue a abrirse.
if TYPE_CHECKING:  # solo para tipado; no se ejecuta en QGIS
    from py_wake.wind_turbines import WindTurbines  # pragma: no cover
else:
    WindTurbines = Any  # type: ignore

__all__ = [
    "TxtSpec",
    "load_curves_from_txt",
    "build_wt_from_manual",
    "build_wt_from_txt",
    "list_pywake_presets",
]

def _debug_print(message: str) -> None:
    """Optional console diagnostics enabled with VELANTISWIND_DEBUG=1."""
    try:
        if os.environ.get("VELANTISWIND_DEBUG", "").strip().lower() in {"1", "true", "yes", "on"}:
            print(message)
    except Exception:
        pass


# ---------------------------------------------------------------------
# Helpers numéricos
# ---------------------------------------------------------------------
def _parse_float(s: str) -> float:
    """Convierte cadenas con coma o punto decimal a float."""
    return float(s.strip().replace(",", "."))


def _ensure_monotone_non_decreasing(values: List[float]) -> List[float]:
    """Fuerza monotonía no decreciente (útil para pequeñas oscilaciones de potencia)."""
    out = list(values)
    for i in range(1, len(out)):
        if out[i] < out[i - 1]:
            out[i] = out[i - 1]
    return out


def _estimate_ct(ws: List[float]) -> List[float]:
    """
    Heurística suave para CT si no se facilita:
    ~0.8 para bajas velocidades, decay lineal hacia ~0.2 a 25 m/s.
    """
    out: List[float] = []
    for w in ws:
        if w <= 8.0:
            c = 0.8
        elif w >= 25.0:
            c = 0.2
        else:
            c = 0.8 - (0.6 * (w - 8.0) / (25.0 - 8.0))
        out.append(max(0.0, min(1.0, c)))
    return out


# ---------------------------------------------------------------------
# Entrada desde fichero TXT/CSV
# ---------------------------------------------------------------------
@dataclass
class TxtSpec:
    """
    Especificación de parsing para TXT/CSV.
    Índices de columna son 0-based.
    """
    ws_col: int
    power_col: int
    delimiter: str = "\t"
    skip_header: int = 1
    ct_col: Optional[int] = None  # si existe columna CT


def load_curves_from_txt(path: str, spec: TxtSpec) -> Tuple[List[float], List[float], List[float]]:
    """
    Carga curvas desde TXT/CSV.
    - Potencia en el fichero: kW -> se convierte a W internamente.
    - Si no hay CT, se estima.

    Returns:
        (ws, power_W, ct) ordenados por velocidad y con potencia no decreciente.
    """
    _debug_print(f"[Energy turbine] Reading curve file: {path}")
    _debug_print(f"[Energy turbine] delimiter='{spec.delimiter}' skip={spec.skip_header} ws_col={spec.ws_col} power_col={spec.power_col} ct_col={spec.ct_col}")

    ws: List[float] = []
    pw_watts: List[float] = []
    ct: List[Optional[float]] = []

    with open(path, "r", encoding="utf-8-sig", newline="") as f:
        reader = csv.reader(f, delimiter=spec.delimiter)
        for _ in range(max(0, spec.skip_header)):
            next(reader, None)
        for row in reader:
            if not row:
                continue
            try:
                w = _parse_float(row[spec.ws_col])
                p_kw = _parse_float(row[spec.power_col])
                if not (math.isfinite(w) and math.isfinite(p_kw)) or w < 0:
                    continue
                ws.append(w)
                pw_watts.append(max(0.0, p_kw) * 1000.0)  # kW -> W
                if spec.ct_col is not None:
                    ct_val = row[spec.ct_col]
                    ct.append(_parse_float(ct_val) if ct_val.strip() != "" else None)
                else:
                    ct.append(None)
            except Exception:
                # línea con ruido -> ignorar
                continue

    if not ws:
        raise ValueError(f"No se han leído datos válidos de {path}")

    merged = sorted(zip(ws, pw_watts, ct), key=lambda t: t[0])
    ws_s, pw_s, ct_s = map(list, zip(*merged))
    pw_s = _ensure_monotone_non_decreasing(pw_s)

    if all(c is None for c in ct_s):
        ct_f = _estimate_ct(ws_s)
    else:
        ct_f = [0.0 if c is None else max(0.0, min(1.0, float(c))) for c in ct_s]

    _debug_print(f"[Energy turbine] points={len(ws_s)} ws[min,max]=({min(ws_s):.3f},{max(ws_s):.3f}) P[max]={max(pw_s):.1f} W")
    return list(ws_s), list(pw_s), list(ct_f)


# ---------------------------------------------------------------------
# Construcción de turbinas personalizadas (PyWake 2.6.7)
# ---------------------------------------------------------------------
def build_wt_from_manual(
    name: str,
    diameter_m: float,
    hub_height_m: float,
    ws: List[float],
    power_kw: List[float],
    ct: Optional[List[float]] = None,
) -> WindTurbines:
    """
    Crea un WindTurbines (plural) desde listas manuales (PyWake 2.6.7).
    - `power_kw` -> se pasa a W para PowerCtTabular.
    """
    # Logs
    _debug_print(f"[Energy turbine] build_wt_from_manual('{name}', D={diameter_m}, HH={hub_height_m})")
    _debug_print(f"[Energy turbine] len(ws)={len(ws)} len(power_kw)={len(power_kw)} len(ct)={(len(ct) if ct else 'None')}")

    if len(ws) != len(power_kw) or len(ws) == 0:
        raise ValueError("Listas `ws` y `power_kw` deben tener la misma longitud y no estar vacías.")

    ws_f = [float(x) for x in ws]
    pw_w = [max(0.0, float(p)) * 1000.0 for p in power_kw]  # kW -> W

    if ct is None:
        ct_f = _estimate_ct(ws_f)
    else:
        if len(ct) != len(ws):
            raise ValueError("Si aportas `ct`, su longitud debe coincidir con `ws`.")
        ct_f = [max(0.0, min(1.0, float(c))) for c in ct]

    z = sorted(zip(ws_f, pw_w, ct_f), key=lambda t: t[0])
    ws_sorted, pw_sorted, ct_sorted = map(list, zip(*z))
    pw_sorted = _ensure_monotone_non_decreasing(pw_sorted)

    # Import perezoso: solo se carga PyWake cuando el usuario pulsa Crear/usar turbina.
    try:
        from py_wake.wind_turbines import WindTurbine, WindTurbines
        from py_wake.wind_turbines.power_ct_functions import PowerCtTabular
    except Exception as e:
        raise RuntimeError(
            "No se pudo cargar PyWake para construir la turbina. "
            "Comprueba que py_wake está instalado en el Python de QGIS y que "
            "Windows no está bloqueando alguna DLL/.pyd de sus dependencias."
        ) from e

    pct = PowerCtTabular(ws_sorted, pw_sorted, 'W', ct_sorted)
    wt = WindTurbine(
        name=str(name),
        diameter=float(diameter_m),
        hub_height=float(hub_height_m),
        powerCtFunction=pct,
    )
    WT = WindTurbines.from_WindTurbine_lst([wt])

    # Logs
    try:
        _debug_print(f"[Energy turbine] WT ready. names={WT.names()} D0={WT.diameter(0)} HH0={WT.hub_height(0)}")
    except Exception as e:
        _debug_print(f"[Energy turbine] WT ready without property preview: {type(WT)} err={e}")

    return WT


def build_wt_from_txt(
    path: str,
    spec: TxtSpec,
    name: str,
    diameter_m: float,
    hub_height_m: float,
) -> WindTurbines:
    """Lee curvas TXT/CSV y construye la turbina."""
    ws, power_W, ct = load_curves_from_txt(path, spec)
    power_kW = [p / 1000.0 for p in power_W]
    return build_wt_from_manual(name, diameter_m, hub_height_m, ws, power_kW, ct)


# ---------------------------------------------------------------------
# Presets de PyWake
# ---------------------------------------------------------------------
def _preset_v80():
    """Horns Rev 1 V80."""
    from py_wake.examples.data.hornsrev1 import V80
    return V80()


def _preset_iea37():
    """Conjunto IEA37 3.4 MW."""
    from py_wake.examples.data.iea37 import IEA37_WindTurbines
    return IEA37_WindTurbines()


def list_pywake_presets() -> Dict[str, Callable[[], WindTurbines]]:
    """Devuelve un diccionario {etiqueta -> factory()} con presets disponibles."""
    presets: Dict[str, Callable[[], WindTurbines]] = {}
    try:
        presets["PyWake: V80 (Horns Rev 1)"] = _preset_v80  # type: ignore[assignment]
    except Exception:
        pass
    try:
        presets["PyWake: IEA37 (3.4MW)"] = _preset_iea37  # type: ignore[assignment]
    except Exception:
        pass
    return presets

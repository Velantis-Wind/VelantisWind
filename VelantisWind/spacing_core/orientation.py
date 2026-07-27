# -*- coding: utf-8 -*-
"""spacing_core/orientation.py — Sector más energético a partir de un WRG.

Calcula, sin dependencias externas (sólo stdlib), la contribución energética
relativa por sector a partir de un WRG (WAsP Resource Grid) o de un ZIP que
contenga uno, y devuelve el azimut del sector más energético.

Modelo
------
Para cada sector s con frecuencia f_s y Weibull (A_s, k_s), la densidad de
energía relativa se aproxima con el tercer momento de la Weibull:

    E_s ∝ f_s · A_s³ · Γ(1 + 3/k_s)

Se promedia sobre todos los nodos del grid (suficiente para orientar una
envolvente de separación; no pretende ser un cálculo de AEP).

El formato de línea WRG y los escalados (f en %·10, A en m/s·10, k en ·100)
siguen los mismos criterios que ag_core/wrg_site.py.

El resultado se cachea por (ruta, mtime) para no re-parsear el WRG en cada
refresco de envolventes.
"""

from __future__ import annotations

import math
import os
import re
import zipfile
from typing import Dict, List, Optional, Tuple

_num_re = re.compile(r"^[-+]?(\d+(\.\d*)?|\.\d+)([eE][-+]?\d+)?$")

# cache: {(abspath, mtime): SectorEnergy}
_CACHE: Dict[Tuple[str, float], "SectorEnergy"] = {}


class SectorEnergy:
    """Resultado del análisis por sectores de un WRG."""

    def __init__(self, n_sectors: int, energy: List[float]):
        self.n_sectors = int(n_sectors)
        total = sum(energy) or 1.0
        self.energy_rel = [e / total for e in energy]
        self.sector_width = 360.0 / float(self.n_sectors)

    @property
    def sector_centers(self) -> List[float]:
        return [i * self.sector_width for i in range(self.n_sectors)]

    @property
    def best_sector(self) -> int:
        return max(range(self.n_sectors), key=lambda i: self.energy_rel[i])

    @property
    def best_angle_deg(self) -> float:
        """Azimut (desde el Norte, horario) del centro del sector más energético."""
        return self.best_sector * self.sector_width


def _read_wrg_lines(path: str) -> List[str]:
    if not os.path.isfile(path):
        raise FileNotFoundError(path)
    if path.lower().endswith(".zip"):
        with zipfile.ZipFile(path, "r") as zf:
            names = [n for n in zf.namelist() if n.lower().endswith(".wrg")]
            if not names:
                raise ValueError(f"El ZIP no contiene ningún .wrg: {path}")
            raw = zf.read(names[0])
    else:
        with open(path, "rb") as fh:
            raw = fh.read()
    text = raw.decode("utf-8", errors="ignore")
    return [ln for ln in text.splitlines() if ln.strip()]


def _strip_optional_id(tokens: List[str]) -> List[str]:
    if tokens and not _num_re.match(tokens[0]):
        return tokens[1:]
    return tokens


def _sector_energy_from_lines(lines: List[str], max_nodes: int = 5000) -> SectorEnergy:
    if len(lines) < 2:
        raise ValueError("WRG vacío o sin puntos")

    header = lines[0].split()
    if len(header) < 5:
        raise ValueError(f"Cabecera WRG inválida: {lines[0]}")
    nx, ny = int(float(header[0])), int(float(header[1]))
    npts = max(1, nx * ny)

    # nsec desde el primer nodo
    toks0 = _strip_optional_id(lines[1].split())
    if len(toks0) < 9:
        raise ValueError("Línea de punto WRG inválida")
    nsec = int(float(toks0[7]))
    if nsec <= 0 or nsec > 72:
        raise ValueError(f"Nº de sectores WRG fuera de rango: {nsec}")

    # Submuestreo simple para WRG muy grandes
    node_lines = lines[1:1 + npts]
    stride = max(1, len(node_lines) // max_nodes)

    energy = [0.0] * nsec
    used = 0
    for ln in node_lines[::stride]:
        toks = _strip_optional_id(ln.split())
        need = 8 + 3 * nsec
        if len(toks) < need:
            continue
        try:
            arr = [float(t) for t in toks[8:need]]
        except Exception:
            continue
        ok = True
        for s in range(nsec):
            f_raw, a_raw, k_raw = arr[3 * s], arr[3 * s + 1], arr[3 * s + 2]
            A = a_raw / 10.0
            k = k_raw / 100.0
            if k <= 0.05:
                ok = False
                break
            try:
                mom3 = (A ** 3) * math.gamma(1.0 + 3.0 / k)
            except Exception:
                mom3 = A ** 3
            energy[s] += max(0.0, f_raw) * mom3
        if ok:
            used += 1
    if used == 0 or sum(energy) <= 0.0:
        raise ValueError("No se pudo calcular energía por sector del WRG")
    return SectorEnergy(nsec, energy)


def sector_energy_from_wrg(path: str) -> SectorEnergy:
    """Analiza un WRG (o ZIP con WRG) y devuelve la energía relativa por sector.

    Cachea por (ruta absoluta, mtime).
    """
    abspath = os.path.abspath(path)
    try:
        mtime = os.path.getmtime(abspath)
    except Exception:
        mtime = 0.0
    key = (abspath, mtime)
    hit = _CACHE.get(key)
    if hit is not None:
        return hit
    result = _sector_energy_from_lines(_read_wrg_lines(abspath))
    # cache pequeño: nos quedamos con las 4 últimas entradas
    if len(_CACHE) > 4:
        _CACHE.clear()
    _CACHE[key] = result
    return result


def most_energetic_angle(path: Optional[str]) -> Optional[float]:
    """Azimut del sector más energético del WRG, o None si no se puede calcular.

    Nunca lanza: el llamador decide el fallback (ángulo manual o 0°).
    """
    if not path:
        return None
    try:
        return sector_energy_from_wrg(path).best_angle_deg
    except Exception:
        return None


def sector_centers(path: Optional[str]) -> Optional[List[float]]:
    """Centros de sector del WRG (para snapping angular), o None."""
    if not path:
        return None
    try:
        return sector_energy_from_wrg(path).sector_centers
    except Exception:
        return None

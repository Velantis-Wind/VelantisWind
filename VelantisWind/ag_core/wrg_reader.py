# -*- coding: utf-8 -*-
"""wrg_reader.py — Utilidades para leer WRG (WAsP Resource Grid)

Este módulo está pensado para usarse desde un plugin QGIS sin dependencias extra.

En esta primera fase (conector UI), sólo necesitamos:
  - validar que el archivo parece un WRG
  - leer metadatos básicos (malla, cellsize, altura, nº sectores)

Más adelante se puede ampliar para construir un XRSite para PyWake.
"""

from __future__ import annotations

import math
import os
import zipfile
from typing import Dict, Any, List, Tuple, Optional, IO

from .log_text import log_error
from .wrg_nodes import node_tokens, wrg_error


def _open_wrg_text(path: str) -> Tuple[IO[bytes], Optional[zipfile.ZipFile]]:
    """Compat: abre el primer .wrg de ``path``."""
    if not os.path.isfile(path):
        raise FileNotFoundError(path)

    if path.lower().endswith(".zip"):
        zf = zipfile.ZipFile(path, "r")
        names = [n for n in zf.namelist() if n.lower().endswith(".wrg")]
        if not names:
            zf.close()
            raise log_error(ValueError, "El ZIP no contiene ningún .wrg: {path}", path=path)
        fh = zf.open(names[0], "r")
        return fh, zf

    # WRG directo
    return open(path, "rb"), None


def _open_all_wrg_texts(path: str) -> List[Tuple[IO[bytes], Optional[zipfile.ZipFile], str]]:
    """
    Abre todos los WRG legibles contenidos en ``path``.

    Devuelve una lista de tuplas ``(file_handle_bytes, zipfile_or_None, label)``.
    El caller debe cerrar ambos (si zipfile no es None) para cada entrada.
    """
    if not os.path.isfile(path):
        raise FileNotFoundError(path)

    if path.lower().endswith(".zip"):
        out: List[Tuple[IO[bytes], Optional[zipfile.ZipFile], str]] = []
        zf = zipfile.ZipFile(path, "r")
        names = [n for n in zf.namelist() if n.lower().endswith(".wrg")]
        if not names:
            zf.close()
            raise log_error(ValueError, "El ZIP no contiene ningún .wrg: {path}", path=path)
        try:
            for name in names:
                out.append((zf.open(name, "r"), zf, f"{os.path.basename(path)}::{name}"))
            return out
        except Exception:
            try:
                zf.close()
            except Exception:  # nosec B110
                pass
            raise

    return [(open(path, "rb"), None, os.path.basename(path))]


def _read_wrg_meta_from_handle(fh: IO[bytes], *, source="WRG") -> Dict[str, Any]:
    line_number = 0
    def read_line():
        nonlocal line_number
        while True:
            raw = fh.readline()
            if not raw:
                return ""
            line_number += 1
            text = raw.decode("utf-8", errors="ignore").strip("\r\n")
            if text.strip():
                return text
    header = read_line()
    if not header:
        raise log_error(ValueError, "WRG vacío")

    parts = header.strip().split()
    if len(parts) < 5:
        raise log_error(ValueError, "Cabecera WRG inválida: {header}", header=header)

    try:
        nx, ny = int(parts[0]), int(parts[1])
        xmin, ymin, cell = float(parts[2]), float(parts[3]), float(parts[4])
    except ValueError as exc:
        raise log_error(ValueError, "Cabecera WRG inválida: {header}", header=header) from exc
    xmax = xmin + (nx - 1) * cell
    ymax = ymin + (ny - 1) * cell

    # segunda línea: primer gridpoint para altura y nsec
    first = read_line()
    if not first:
        raise log_error(ValueError, "WRG sin puntos (sólo cabecera)")
    vals, _ = node_tokens(first.split(), source=source, line_number=line_number)
    try:
        finite_header = all(math.isfinite(float(value)) for value in vals[:8])
    except ValueError:
        finite_header = False
    if not finite_header:
        raise wrg_error("los campos del nodo deben ser números finitos.",
                        source=source, line_number=line_number)
    height = float(vals[3])
    nsec = int(float(vals[7]))

    return {
        "nx": nx,
        "ny": ny,
        "xmin": xmin,
        "ymin": ymin,
        "cellsize": cell,
        "height_m": height,
        "n_sectors": nsec,
        "extent": (xmin, xmax, ymin, ymax),
    }


def read_wrg_meta(path: str) -> Dict[str, Any]:
    """Lee metadatos básicos de un WRG (o ZIP con WRG).

    Retorna un dict con:
      - nx, ny, xmin, ymin, cellsize
      - height_m (altura única si sólo hay una; primera altura si hay varias)
      - height_m_list (todas las alturas detectadas)
      - n_sectors (del primer WRG) y n_sectors_list (de cada WRG, p. ej. de cada miembro de un ZIP)
      - extent (xmin, xmax, ymin, ymax)
    """
    items = _open_all_wrg_texts(path)
    metas: List[Dict[str, Any]] = []
    try:
        for fh, _zf, label in items:
            source = os.path.abspath(path)
            if path.lower().endswith(".zip"):
                source += "::" + label.split("::", 1)[1]
            meta = _read_wrg_meta_from_handle(fh, source=source)
            meta["label"] = label
            metas.append(meta)
    finally:
        seen_zf = set()
        for fh, zf, _label in items:
            try:
                fh.close()
            except Exception:  # nosec B110
                pass
            if zf is not None and id(zf) not in seen_zf:
                seen_zf.add(id(zf))
                try:
                    zf.close()
                except Exception:  # nosec B110
                    pass

    if not metas:
        raise log_error(ValueError, "No se pudo leer ningún WRG desde: {path}", path=path)

    m0 = dict(metas[0])
    heights = [float(m.get("height_m")) for m in metas]
    m0["height_m_list"] = heights
    m0["n_sectors_list"] = [m.get("n_sectors") for m in metas]
    if len(heights) == 1:
        m0["height_m"] = heights[0]
    else:
        m0["height_m"] = heights[0]
    return m0

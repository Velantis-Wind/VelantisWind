# -*- coding: utf-8 -*-
"""
wrg_site.py — Loader de WRG (WAsP/WRG) -> PyWake XRSite

Soporta:
- .wrg directo
- .zip que contiene uno o varios .wrg

Construye un xarray.Dataset con las variables que PyWake espera para clima Weibull direccional:
  - Sector_frequency  (probabilidad por sector)   dims: (x, y, h, wd)
  - Weibull_A         (m/s)                       dims: (x, y, h, wd)
  - Weibull_k         (-)                         dims: (x, y, h, wd)
Opcional:
  - Elevation         (m)                         dims: (x, y)

Notas de formato (WRG “climate grid” de WAsP/WRG):
- Tras el header (nx ny x_min y_min dx), cada línea de nodo contiene:
  x y z h A k Pdens nsec   [freq A k] * nsec
- freq está en [% * 10]  → prob = freq / 1000 (y se renormaliza por redondeo)
- A sector está en [m/s * 10] → A = Araw / 10
- k sector está en [ * 100]   → k = kraw / 100

Recomendación:
- Para estabilidad en 0/360, añadimos wd=360 y duplicamos el primer sector (cierre).

Devuelve:
  site, ds, label
"""
from __future__ import annotations

import os
import re
import zipfile
from typing import List, Tuple, Optional

import numpy as np

try:
    import xarray as xr
except Exception as e:
    raise ImportError("xarray es necesario para usar WRG con PyWake") from e

# PyWake
try:
    from py_wake.site.xrsite import XRSite
except Exception:
    # compatibility path
    from py_wake.site._site import XRSite  # type: ignore

try:
    from py_wake.site.distance import StraightDistance
except Exception:
    StraightDistance = None  # type: ignore

F32 = np.float32

_num_re = re.compile(r"^-?\d+(\.\d+)?$")


def _read_wrg_text(path: str) -> Tuple[str, str]:
    """Compat: devuelve el primer WRG encontrado en ``path``."""
    items = _read_all_wrg_texts(path)
    if not items:
        raise ValueError(f"No se encontró ningún WRG legible en: {path}")
    return items[0]


def _read_all_wrg_texts(path: str) -> List[Tuple[str, str]]:
    """
    Lee uno o varios WRG desde una ruta:
      - .wrg  -> una entrada
      - .zip  -> una entrada por cada .wrg dentro del ZIP
    Devuelve una lista ``[(texto, label), ...]``.
    """
    p = os.path.abspath(path)
    lo = p.lower()
    if lo.endswith(".wrg"):
        with open(p, "r", encoding="utf-8", errors="ignore") as f:
            return [(f.read(), os.path.basename(p))]
    if lo.endswith(".zip"):
        with zipfile.ZipFile(p, "r") as z:
            wrgs = [n for n in z.namelist() if n.lower().endswith(".wrg")]
            if not wrgs:
                raise ValueError(f"ZIP no contiene .wrg: {p}")
            out: List[Tuple[str, str]] = []
            for name in wrgs:
                data = z.read(name).decode("utf-8", errors="ignore")
                out.append((data, f"{os.path.basename(p)}::{name}"))
            return out
    raise ValueError(f"Extensión no soportada: {path} (use .wrg o .zip)")


def _parse_header(first_line: str) -> Tuple[int, int, float, float, float]:
    parts = first_line.split()
    if len(parts) < 5:
        raise ValueError(f"Header WRG inválido: '{first_line}'")
    nx = int(float(parts[0]))
    ny = int(float(parts[1]))
    x0 = float(parts[2])
    y0 = float(parts[3])
    dx = float(parts[4])
    if nx <= 0 or ny <= 0 or dx <= 0:
        raise ValueError(f"Header WRG inválido (nx,ny,dx): nx={nx} ny={ny} dx={dx}")
    return nx, ny, x0, y0, dx


def _strip_optional_id(tokens: List[str]) -> List[str]:
    # Algunos WRG llevan un "site id" textual al inicio (10 chars). Si el primer token no es numérico, lo quitamos.
    if tokens and (not _num_re.match(tokens[0])):
        return tokens[1:]
    return tokens


def _parse_node(tokens: List[str], nsec_expected: Optional[int]) -> Tuple[float, float, float, float, float, float, float, int, np.ndarray, np.ndarray, np.ndarray]:
    tokens = _strip_optional_id(tokens)
    if len(tokens) < 9:
        raise ValueError("Línea WRG demasiado corta")
    x = float(tokens[0]); y = float(tokens[1]); z = float(tokens[2])
    h = float(tokens[3])
    A_tot = float(tokens[4]); k_tot = float(tokens[5])
    pdens = float(tokens[6])
    nsec = int(float(tokens[7]))
    if nsec_expected is not None and nsec != nsec_expected:
        raise ValueError(f"Nº sectores inconsistente: esperado {nsec_expected}, leído {nsec}")
    need = 8 + 3 * nsec
    if len(tokens) < need:
        raise ValueError(f"Línea WRG incompleta: esperados >= {need} tokens, hay {len(tokens)}")
    arr = np.asarray(list(map(float, tokens[8:8 + 3 * nsec])), dtype=F32)
    f_raw = arr[0::3]
    A_raw = arr[1::3]
    k_raw = arr[2::3]
    return x, y, z, h, A_tot, k_tot, pdens, nsec, f_raw, A_raw, k_raw


def _build_ds_from_wrg_text(text: str) -> xr.Dataset:
    # Limpieza de líneas vacías
    lines = [ln for ln in text.splitlines() if ln.strip()]
    if not lines:
        raise ValueError("WRG vacío")

    nx, ny, x0, y0, dx = _parse_header(lines[0])
    npts = nx * ny

    if len(lines) < 1 + npts:
        raise ValueError(f"WRG incompleto: header + {npts} líneas esperadas; hay {len(lines) - 1}")

    # coords
    x = (x0 + dx * np.arange(nx)).astype(F32)
    y = (y0 + dx * np.arange(ny)).astype(F32)

    # parse primer nodo para detectar nsec y h
    first_tokens = lines[1].split()
    _, _, _, h0, _, _, _, nsec, _, _, _ = _parse_node(first_tokens, None)
    sector_width = 360.0 / float(nsec)

    # wd centers + cierre 360
    wd = (np.arange(nsec, dtype=F32) * sector_width).astype(F32)  # 0, 22.5, ...
    wd_closed = np.concatenate([wd, np.array([360.0], dtype=F32)], axis=0)

    # buffers (float32)
    elev = np.zeros((ny, nx), dtype=F32)
    freq = np.zeros((ny, nx, nsec), dtype=F32)
    A = np.zeros((ny, nx, nsec), dtype=F32)
    k = np.zeros((ny, nx, nsec), dtype=F32)

    # recorremos nodos
    for idx in range(npts):
        ln = lines[1 + idx]
        toks = ln.split()
        x_i, y_i, z_i, h_i, A_tot, k_tot, pdens, nsec_i, f_raw, A_raw, k_raw = _parse_node(toks, nsec)

        # posicion en grid (orden WRG típico: x varía rápido, luego y)
        iy = idx // nx
        ix = idx - iy * nx

        elev[iy, ix] = float(z_i)

        # scaling según formato WRG
        # freq: [%*10] -> prob; renormalizamos por redondeos
        f = f_raw.astype(F32)
        s = float(np.sum(f)) if np.sum(f) > 0 else 1.0
        f_prob = (f / s).astype(F32)

        freq[iy, ix, :] = f_prob
        A[iy, ix, :] = (A_raw / 10.0).astype(F32)
        k[iy, ix, :] = (k_raw / 100.0).astype(F32)

    # Cierre 360 duplicando primer sector
    freq_c = np.concatenate([freq, freq[:, :, :1]], axis=2)  # (ny,nx,nsec+1)
    A_c = np.concatenate([A, A[:, :, :1]], axis=2)
    k_c = np.concatenate([k, k[:, :, :1]], axis=2)

    # Pasamos a dims (x,y,wd) → transponemos a (nx,ny,wd)
    freq_c = np.transpose(freq_c, (1, 0, 2))  # (nx,ny,wd)
    A_c = np.transpose(A_c, (1, 0, 2))
    k_c = np.transpose(k_c, (1, 0, 2))
    elev = np.transpose(elev, (1, 0))  # (nx,ny)

    # Añadimos dim h
    h = np.array([h0], dtype=F32)
    freq_c = freq_c[:, :, None, :]  # (nx,ny,h,wd)
    A_c = A_c[:, :, None, :]
    k_c = k_c[:, :, None, :]

    ds = xr.Dataset(
        data_vars=dict(
            Sector_frequency=(("x", "y", "h", "wd"), freq_c),
            Weibull_A=(("x", "y", "h", "wd"), A_c),
            Weibull_k=(("x", "y", "h", "wd"), k_c),
            Elevation=(("x", "y"), elev),
        ),
        coords=dict(
            x=x,
            y=y,
            h=h,
            wd=wd_closed,
        ),
        attrs=dict(
            sector_width=float(sector_width),
            dx=float(dx),
            source="WRG",
        )
    )
    return ds


def load_wrg_site(wrg_paths: List[str]):
    """
    Carga uno o varios WRG (distintas alturas) y devuelve:
      (site, ds, label)
    Si se pasan varias alturas, concatena por dim 'h' (ordenado).

    Importante: si una ruta es un .zip, se expanden todos los .wrg internos
    y se incorporan como alturas independientes.
    """
    if not wrg_paths:
        raise ValueError("Lista WRG vacía")

    ds_items: List[Tuple[xr.Dataset, str]] = []
    labels: List[str] = []

    nx0 = ny0 = None
    x0 = y0 = dx0 = None

    for p in wrg_paths:
        wrg_items = _read_all_wrg_texts(p)
        for text, label in wrg_items:
            ds = _build_ds_from_wrg_text(text)

            # Validar malla consistente si hay varios
            if nx0 is None:
                nx0 = int(ds.sizes["x"]); ny0 = int(ds.sizes["y"])
                x0 = float(ds["x"].values[0]); y0 = float(ds["y"].values[0])
                dx0 = float(ds.attrs.get("dx", 0))
            else:
                if int(ds.sizes["x"]) != nx0 or int(ds.sizes["y"]) != ny0:
                    raise ValueError("WRG con distinta resolución/extent: no se pueden combinar por altura")
                if abs(float(ds["x"].values[0]) - x0) > 1e-6 or abs(float(ds["y"].values[0]) - y0) > 1e-6:
                    raise ValueError("WRG con distinto origen x0/y0: no se pueden combinar por altura")
                if abs(float(ds.attrs.get("dx", 0)) - dx0) > 1e-6:
                    raise ValueError("WRG con distinto dx: no se pueden combinar por altura")

            ds_items.append((ds, label))
            labels.append(label)

    if not ds_items:
        raise ValueError("No se pudo leer ningún WRG válido")

    # Deduplicar alturas repetidas para evitar coords 'h' duplicadas en Xarray/PyWake.
    unique_items: List[Tuple[xr.Dataset, str]] = []
    seen_h = {}
    for ds, label in ds_items:
        try:
            h_val = float(np.asarray(ds["h"].values).ravel()[0])
        except Exception:
            h_val = float("nan")
        key = round(h_val, 6) if np.isfinite(h_val) else label
        if key in seen_h:
            prev_ds, prev_label = seen_h[key]
            same = True
            for var in ("Sector_frequency", "Weibull_A", "Weibull_k", "Elevation"):
                try:
                    if not np.allclose(np.asarray(prev_ds[var].values), np.asarray(ds[var].values), equal_nan=True):
                        same = False
                        break
                except Exception:
                    same = False
                    break
            if same:
                continue
            raise ValueError(
                f"Hay WRG duplicados para la altura {h_val:g} m con contenido distinto: "
                f"'{prev_label}' y '{label}'"
            )
        seen_h[key] = (ds, label)
        unique_items.append((ds, label))

    ds_list = [ds for ds, _ in unique_items]

    # Concat por h si hay varios
    if len(ds_list) == 1:
        ds_all = ds_list[0]
    else:
        ds_all = xr.concat(ds_list, dim="h", data_vars="all", coords="minimal", compat="equals")
        # ordenar por altura
        ds_all = ds_all.sortby("h")

    # Construir XRSite
    if StraightDistance is not None:
        site = XRSite(ds_all, distance=StraightDistance())
    else:
        site = XRSite(ds_all)

    return site, ds_all, " | ".join([label for _, label in unique_items])

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
- El eje wd va en float64 (con 400 sectores, float32 no da anchos iguales); el resto conserva float32.

El Site conserva en cada punto el clima Weibull local del WRG (Speedup ``none``) y
usa la interpolación direccional pedida; la política de direcciones es la de
``resource_grid``.

Devuelve:
  site, ds, label
"""
from __future__ import annotations

import logging

import os
import warnings
import zipfile
from typing import List, Tuple, Optional

import numpy as np

from .log_text import log_error
from .wrg_nodes import node_tokens, wrg_error
from .resource_grid import WrgContractError, initial_direction_count, interp_methods, validate_request

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

try:
    from py_wake.site.distance import TerrainFollowingDistance
except Exception:
    TerrainFollowingDistance = None  # type: ignore

F32 = np.float32

# The propagation distance of a WRG Site, the same for the AEP and the wake raster: straight. The terrain of a
# WRG is its elevation alone, and following it changes the wakes but not the climate.
TERRAIN_FOLLOWING = False


def _read_wrg_text(path: str) -> Tuple[str, str]:
    """Compat: devuelve el primer WRG encontrado en ``path``."""
    items = _read_all_wrg_texts(path)
    if not items:
        raise log_error(ValueError, "No se encontró ningún WRG legible en: {path}", path=path)
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
                raise log_error(ValueError, "ZIP no contiene .wrg: {path}", path=p)
            out: List[Tuple[str, str]] = []
            for name in wrgs:
                data = z.read(name).decode("utf-8", errors="ignore")
                out.append((data, f"{os.path.basename(p)}::{name}"))
            return out
    raise log_error(ValueError, "Extensión no soportada: {path} (use .wrg o .zip)", path=path)


def _parse_header(first_line: str) -> Tuple[int, int, float, float, float]:
    parts = first_line.split()
    if len(parts) < 5:
        raise log_error(ValueError, "Cabecera WRG inválida: '{line}'", line=first_line)
    try:
        nx = int(float(parts[0]))
        ny = int(float(parts[1]))
        x0 = float(parts[2])
        y0 = float(parts[3])
        dx = float(parts[4])
    except (ValueError, OverflowError) as exc:
        raise log_error(ValueError, "Cabecera WRG inválida: '{line}'", line=first_line) from exc
    if nx <= 0 or ny <= 0 or dx <= 0:
        raise log_error(ValueError, "Cabecera WRG inválida (nx,ny,dx): nx={nx} ny={ny} dx={dx}", nx=nx, ny=ny, dx=dx)
    return nx, ny, x0, y0, dx


def _parse_node(
    tokens: List[str], nsec_expected: Optional[int], *, source="WRG", line_number=None,
) -> Tuple[float, float, float, float, float, float, float, int, np.ndarray, np.ndarray, np.ndarray]:
    tokens, _ = node_tokens(tokens, source=source, line_number=line_number,
                            nsec_expected=nsec_expected)
    try:
        values = np.asarray(list(map(float, tokens)), dtype=np.float64)
    except ValueError as exc:
        raise wrg_error("campos WRG no numéricos.", source=source, line_number=line_number) from exc
    if not np.all(np.isfinite(values)):
        raise wrg_error("campos WRG no finitos.", source=source, line_number=line_number)
    x, y, z, h, A_tot, k_tot, pdens = values[:7]
    nsec = int(values[7])
    arr = values[8:].astype(F32)
    return x, y, z, h, A_tot, k_tot, pdens, nsec, arr[0::3], arr[1::3], arr[2::3]


def _build_ds_from_wrg_text(text: str, *, source: str = "WRG") -> xr.Dataset:
    # Limpieza de líneas vacías
    numbered_lines = [(i, ln) for i, ln in enumerate(text.splitlines(), 1) if ln.strip()]
    lines = [ln for _, ln in numbered_lines]
    if not lines:
        raise log_error(ValueError, "WRG vacío")

    nx, ny, x0, y0, dx = _parse_header(lines[0])
    npts = nx * ny

    if len(lines) < 1 + npts:
        raise log_error(ValueError, "WRG incompleto: cabecera + {expected} líneas esperadas; hay {lines}", expected=npts,
                        lines=len(lines) - 1)

    # coords
    x = (x0 + dx * np.arange(nx)).astype(F32)
    y = (y0 + dx * np.arange(ny)).astype(F32)

    # parse primer nodo para detectar nsec y h
    first_tokens = lines[1].split()
    _, _, _, h0, _, _, _, nsec, _, _, _ = _parse_node(first_tokens, None, source=source, line_number=numbered_lines[1][0])
    sector_width = 360.0 / float(nsec)

    # wd centers + cierre 360, en float64
    wd = np.arange(nsec, dtype=np.float64) * sector_width  # 0, 22.5, ...
    wd_closed = np.concatenate([wd, np.array([360.0])], axis=0)

    # Check each row's structure in Python before flattening; NumPy then converts
    # headers and sector values together. Stop this scan at the first ID: the
    # fallback validates and converts every row, including those after that ID.
    expected_cols = 8 + 3 * nsec
    parsed_fast = False
    numeric_rows = len(first_tokens) == expected_cols
    if numeric_rows:
        for line, ln in numbered_lines[2:1 + npts]:
            _, offset = node_tokens(ln.split(), source=source, line_number=line,
                                    nsec_expected=nsec)
            if offset:
                numeric_rows = False
                break
    elev = np.zeros((ny, nx), dtype=F32)
    freq = np.zeros((ny, nx, nsec), dtype=F32)
    A = np.zeros((ny, nx, nsec), dtype=F32)
    k = np.zeros((ny, nx, nsec), dtype=F32)
    try:
        if numeric_rows:
            with warnings.catch_warnings():
                # NumPy 1.x warns on partial conversion; NumPy 2.x raises.
                # Both cases must fall back to strict parsing with a source/line.
                warnings.simplefilter("error", DeprecationWarning)
                raw = np.fromstring("\n".join(lines[1:1 + npts]), sep=" ", dtype=np.float64)
            if raw.size == npts * expected_cols:
                table = raw.reshape(npts, expected_cols)
                if np.all(np.isfinite(table)) and np.all(table[:, 7] == int(nsec)):
                    elev[:, :] = table[:, 2].reshape(ny, nx).astype(F32)
                    sectors = table[:, 8:].reshape(npts, nsec, 3)
                    f = sectors[:, :, 0].astype(F32, copy=False)
                    sums = np.sum(f, axis=1, keepdims=True, dtype=np.float64)
                    sums = np.where(sums > 0.0, sums, 1.0)
                    freq[:, :, :] = (f / sums).reshape(ny, nx, nsec).astype(F32)
                    A[:, :, :] = (sectors[:, :, 1] * 0.1).reshape(ny, nx, nsec).astype(F32)
                    k[:, :, :] = (sectors[:, :, 2] * 0.01).reshape(ny, nx, nsec).astype(F32)
                    h0 = float(table[0, 3])
                    parsed_fast = True
    except Exception:
        parsed_fast = False

    if not parsed_fast:
        for idx in range(npts):
            ln = lines[1 + idx]
            toks = ln.split()
            x_i, y_i, z_i, h_i, A_tot, k_tot, pdens, nsec_i, f_raw, A_raw, k_raw = _parse_node(toks, nsec, source=source, line_number=numbered_lines[1 + idx][0])

            iy = idx // nx
            ix = idx - iy * nx
            elev[iy, ix] = float(z_i)

            f = f_raw.astype(F32)
            total = float(np.sum(f))
            if total <= 0.0:
                total = 1.0
            freq[iy, ix, :] = (f / total).astype(F32)
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
            n_sectors=int(nsec),
            dx=float(dx),
            source="WRG",
            parser="numpy_bulk" if parsed_fast else "python_fallback",
        )
    )
    return ds


def _prepare_vertical_climate(ds: xr.Dataset) -> xr.Dataset:
    """Make WRG height handling explicit without changing turbine geometry.

    - Multi-height WRG: retain ``h`` so PyWake can interpolate vertically.
    - Single-height WRG: climate variables are made height-independent. This
      means the one available WRG climate is used as a vertical reference for
      any turbine hub height, while the physical turbine hub height remains
      untouched. The approximation is recorded in dataset attributes.
    """
    out = ds.copy()
    try:
        hvals = np.asarray(out["h"].values, dtype=float).reshape(-1) if "h" in out.coords else np.array([])
        hvals = np.unique(hvals[np.isfinite(hvals)])
    except Exception:
        hvals = np.array([])

    out.attrs["wrg_heights_m"] = [float(v) for v in hvals.tolist()]
    if hvals.size != 1:
        out.attrs["wrg_vertical_policy"] = "multi_height_interpolation" if hvals.size > 1 else "no_height_axis"
        return out

    # A single WRG height cannot define vertical shear. Remove h only from the
    # wind-climate variables so PyWake does not need to clamp/extrapolate hub
    # height. TI may later be injected with its own height dependence.
    for var_name in ("Sector_frequency", "Weibull_A", "Weibull_k", "Turning"):
        if var_name in out and "h" in out[var_name].dims:
            out[var_name] = out[var_name].isel(h=0, drop=True)

    # Drop the now-unused scalar h coordinate if no remaining variable uses it.
    try:
        if "h" in out.coords and not any("h" in out[name].dims for name in out.data_vars):
            out = out.drop_vars("h")
    except Exception as _ignored_exc:
        logging.getLogger(__name__).debug("Ignored optional operation at %s:%d: %s", __name__, 301, _ignored_exc)

    out.attrs.update({
        "wrg_vertical_policy": "single_height_reference",
        "wrg_reference_height_m": float(hvals[0]),
        "wrg_vertical_note": (
            "Only one WRG climate height is available. The climate is treated as height-independent; "
            "turbine hub heights are not modified. No vertical shear is inferred from the WRG."
        ),
    })
    return out


def load_wrg_site(
    wrg_paths: List[str],
    *,
    direction_count: Optional[int] = None,
    wd_interp: str = "nearest",
    speedup_method: str = "none",
    terrain_following: bool = TERRAIN_FOLLOWING,
):
    """
    Carga uno o varios WRG (distintas alturas) y devuelve ``(site, ds, label)``.

    El Site conserva en cada punto A, k y las frecuencias locales del WRG: el
    único ``speedup_method`` es ``none``; cualquier otro (también
    ``global_weibull``) lanza ``WrgContractError``. La interpolación direccional
    es ``wd_interp`` (``x``, ``y`` y ``h`` lineales). ``direction_count`` son las
    direcciones de cálculo pedidas (sin ellas, la selección inicial): se validan
    contra los sectores del WRG sin redondear, y todos los WRG (ficheros o
    miembros de un ZIP) deben tener los mismos sectores. ``ds.attrs`` guarda
    ``n_sectors``, ``wrg_direction_count``, ``wrg_wd_interp_method`` y
    ``wrg_source``; las direcciones se pasan a la simulación
    (``resource_grid.direction_grid``).

    ``terrain_following=True`` usa la elevación del WRG para las distancias de
    propagación cuando la versión instalada de PyWake lo permite.
    """
    if not wrg_paths:
        raise log_error(ValueError, "Lista WRG vacía")
    if speedup_method != "none":
        raise log_error(
            WrgContractError, "Speedup no válido: {method}. Con un WRG solo se admite none: se conservan en cada punto las "
            "Weibull y frecuencias locales del WRG.", method=repr(speedup_method),
        )

    ds_items: List[Tuple[xr.Dataset, str]] = []
    labels: List[str] = []

    nx0 = ny0 = None
    x0 = y0 = dx0 = None

    sources: List[str] = []
    for p in wrg_paths:
        wrg_items = _read_all_wrg_texts(p)
        for text, label in wrg_items:
            source = os.path.abspath(p)
            if p.lower().endswith(".zip"):
                source += "::" + label.split("::", 1)[1]
            ds = _build_ds_from_wrg_text(text, source=source)

            # Validar malla consistente si hay varios
            if nx0 is None:
                nx0 = int(ds.sizes["x"]); ny0 = int(ds.sizes["y"])
                x0 = float(ds["x"].values[0]); y0 = float(ds["y"].values[0])
                dx0 = float(ds.attrs.get("dx", 0))
            else:
                if int(ds.sizes["x"]) != nx0 or int(ds.sizes["y"]) != ny0:
                    raise log_error(ValueError, "WRG con distinta resolución/extensión: no se pueden combinar por altura")
                if abs(float(ds["x"].values[0]) - x0) > 1e-6 or abs(float(ds["y"].values[0]) - y0) > 1e-6:
                    raise log_error(ValueError, "WRG con distinto origen x0/y0: no se pueden combinar por altura")
                if abs(float(ds.attrs.get("dx", 0)) - dx0) > 1e-6:
                    raise log_error(ValueError, "WRG con distinto dx: no se pueden combinar por altura")
                first = ds_items[0][0]
                if ds.attrs["n_sectors"] != first.attrs["n_sectors"] or not np.array_equal(ds["wd"].values, first["wd"].values):
                    raise log_error(
                        WrgContractError, "Los WRG no tienen los mismos sectores: {n_first} en «{first}» y {n} en «{source}». "
                        "No se pueden combinar por altura.", n_first=first.attrs['n_sectors'], first=sources[0],
                        n=ds.attrs['n_sectors'], source=source,
                    )

            ds_items.append((ds, label))
            labels.append(label)
            sources.append(source)

    if not ds_items:
        raise log_error(ValueError, "No se pudo leer ningún WRG válido")

    # La petición se valida en cuanto se conoce N, antes de combinar alturas.
    n_sectors = int(ds_items[0][0].attrs["n_sectors"])
    count = initial_direction_count(n_sectors) if direction_count is None else direction_count
    source = " | ".join(sources)
    validate_request(n_sectors, count, wd_interp, source)

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
            raise log_error(
                ValueError, "Hay WRG duplicados para la altura {height} m con contenido distinto: '{first}' y '{second}'",
                height=f"{h_val:g}", first=prev_label, second=label,
            )
        seen_h[key] = (ds, label)
        unique_items.append((ds, label))

    ds_list = [ds for ds, _ in unique_items]

    # Concat por h si hay varios.
    #
    # IMPORTANTE: ``Elevation`` no depende de la altura del recurso. Usar
    # ``data_vars="all"`` hace que xarray la expanda a ``Elevation(h,x,y)``.
    # PyWake/TerrainFollowingDistance espera una superficie 2-D ``(x,y)``;
    # con dos WRG de distintas alturas terminaba interpretando un índice
    # espacial (p. ej. 217) sobre el eje h, de tamaño 2.
    if len(ds_list) == 1:
        ds_all = ds_list[0]
    else:
        elevation_ref = ds_list[0]["Elevation"].transpose("x", "y")
        for ds in ds_list[1:]:
            elevation_other = ds["Elevation"].transpose("x", "y")
            if not np.allclose(
                np.asarray(elevation_ref.values),
                np.asarray(elevation_other.values),
                rtol=0.0,
                atol=1e-3,
                equal_nan=True,
            ):
                raise log_error(
                    ValueError, "Los WRG contienen superficies de elevación distintas entre alturas; "
                    "no se puede construir un terreno único y coherente."
                )

        # Se retira Elevation durante la concatenación y se restaura después.
        # De esta forma nunca puede adquirir accidentalmente una dimensión h.
        climate_datasets = [ds.drop_vars("Elevation") for ds in ds_list]
        ds_all = xr.concat(
            climate_datasets,
            dim="h",
            data_vars="minimal",
            coords="minimal",
            compat="equals",
        )
        ds_all = ds_all.sortby("h")
        ds_all["Elevation"] = elevation_ref

    # Defensa adicional para archivos/objetos creados por versiones anteriores:
    # la elevación del terreno debe quedar siempre como Elevation(x,y).
    if "Elevation" in ds_all:
        elevation = ds_all["Elevation"]
        extra_dims = [d for d in elevation.dims if d not in {"x", "y"}]
        for dim in extra_dims:
            if int(elevation.sizes.get(dim, 0)) == 1:
                elevation = elevation.isel({dim: 0}, drop=True)
                continue
            first = elevation.isel({dim: 0}, drop=True)
            same = True
            for idx in range(1, int(elevation.sizes[dim])):
                if not np.allclose(
                    np.asarray(first.values),
                    np.asarray(elevation.isel({dim: idx}, drop=True).values),
                    rtol=0.0,
                    atol=1e-3,
                    equal_nan=True,
                ):
                    same = False
                    break
            if not same:
                raise log_error(
                    ValueError, "Los WRG contienen superficies de elevación distintas entre alturas; "
                    "no se puede construir un terreno único y coherente."
                )
            elevation = first
        if set(elevation.dims) != {"x", "y"}:
            raise log_error(ValueError, "Dimensiones de Elevation no compatibles: {dims}; se esperaba (x, y).",
                            dims=elevation.dims)
        ds_all["Elevation"] = elevation.transpose("x", "y")

    # Normaliza el orden de dimensiones de las variables climáticas. Esto evita
    # que un dataset persistido con otro orden de ejes llegue al interpolador de
    # PyWake aunque los nombres de dimensión sean correctos.
    for var_name in ("Sector_frequency", "Weibull_A", "Weibull_k", "Turning"):
        if var_name not in ds_all:
            continue
        var = ds_all[var_name]
        expected = tuple(d for d in ("x", "y", "h", "wd") if d in var.dims)
        if set(var.dims) == set(expected) and tuple(var.dims) != expected:
            ds_all[var_name] = var.transpose(*expected)

    ds_all.attrs.update({
        "n_sectors": n_sectors,
        "wrg_direction_count": int(count),
        "wrg_source": source,
        "wrg_speedup_method": "none",
    })

    # Height handling is explicit: interpolate only when the WRG actually has
    # multiple climate heights. A single-height WRG is treated as a reference
    # climate and never changes the physical turbine hub height.
    ds_all = _prepare_vertical_climate(ds_all)

    # Construir XRSite, con la distancia pedida (la del AEP y el ráster: ``TERRAIN_FOLLOWING``).
    distance = None
    if bool(terrain_following) and TerrainFollowingDistance is not None:
        distance = TerrainFollowingDistance()
        ds_all.attrs["distance_method"] = "TerrainFollowingDistance"
    elif StraightDistance is not None:
        distance = StraightDistance()
        ds_all.attrs["distance_method"] = "StraightDistance"

    # WRG values are sector climates: the chosen interpolation in wind direction
    # (nearest keeps each sub-direction tied to its WRG sector), while spatial and
    # vertical interpolation remain linear when those axes exist.
    interp_method = interp_methods(wd_interp)
    ds_all.attrs["wrg_wd_interp_method"] = wd_interp
    if distance is not None:
        site = XRSite(ds_all, distance=distance, interp_method=interp_method)
    else:
        site = XRSite(ds_all, interp_method=interp_method)

    return site, ds_all, " | ".join([label for _, label in unique_items])

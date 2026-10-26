# -*- coding: utf-8 -*-
"""
wake_core/engine.py — Worker-safe helpers of the wake raster: the resource of a WAsP grid (.grd) or a WRG
(.wrg/.zip), its bounds and terrain, the domain-anchored grid with its memory budget, the tiled flow map and the
writing of the package. The raster itself, with the configuration of the AEP, is ``wake_core.raster`` (#46).

Requisitos:
- PyWake 2.6.x
- GDAL (normalmente desde el entorno Python de QGIS)
"""

from __future__ import annotations

import csv
import math
import os
from typing import List, Dict, Any, Tuple, Optional



def _is_debug_enabled() -> bool:
    return str(os.environ.get("VELANTISWIND_DEBUG", "")).strip().lower() in {"1", "true", "yes", "on", "debug"}


def _debug_print(message: str) -> None:
    if _is_debug_enabled():
        print(message)


def _error(cls, template: str, **data: Any) -> Exception:
    """Excepción con el texto en español y, aparte, su plantilla y datos para traducirla al mostrarla."""
    exc = cls(template.format(**data))
    exc.template_item = (template, data)
    return exc

import numpy as np




# ---------------- py_wake imports (robustos) ----------------
try:
    from py_wake import HorizontalGrid
except Exception:  # pragma: no cover
    try:
        from py_wake.flow_map import HorizontalGrid  # type: ignore
    except Exception:
        HorizontalGrid = None  # type: ignore

# ---- WT combinado (mismo criterio que el cálculo AEP) ----
_combine_wt = None
_canonicalize_models = None
try:
    from ..ag_core.turbines.factory import (
        combine_wt as _combine_wt,
        canonicalize_models as _canonicalize_models,
    )  # type: ignore
except Exception:
    try:
        from ag_core.turbines.factory import (
            combine_wt as _combine_wt,
            canonicalize_models as _canonicalize_models,
        )  # type: ignore
    except Exception:
        _combine_wt = None
        _canonicalize_models = None

# ---- Densidad del aire: la misma decisión que el cálculo AEP ----
# Las excepciones se enlazan al importar, no se resuelven como atributo de otro
# módulo dentro de un ``except``, donde un fallo de búsqueda taparía el error real.
try:
    from ..ag_core.physics.air_density import AirDensityError, SiteAirDensityError  # type: ignore
    from ..ag_core.turbines.density_resolution import resolve_air_density  # type: ignore
except Exception:
    from ag_core.physics.air_density import AirDensityError, SiteAirDensityError  # type: ignore
    from ag_core.turbines.density_resolution import resolve_air_density  # type: ignore

# ---- Exportación worker-safe de flow maps como GeoTIFF ----
_build_wake_raster_file = None
try:
    from ..ag_core.qgis_io.wake_raster import build_wake_raster_file as _build_wake_raster_file  # type: ignore
except Exception:
    try:
        from ag_core.qgis_io.wake_raster import build_wake_raster_file as _build_wake_raster_file  # type: ignore
    except Exception:
        _build_wake_raster_file = None


# ===================== WAsP helpers =====================
# ===================== Lectura / helpers =====================
def _read_coords_csv(path: str) -> List[Tuple[float, float]]:
    rows: List[Tuple[float, float]] = []
    with open(path, "r", encoding="utf-8-sig") as f:
        sample = f.read(2048); f.seek(0)
        try:
            dialect = csv.Sniffer().sniff(sample, delimiters=",;")
        except Exception:
            dialect = csv.excel
        reader = csv.reader(f, dialect)
        header = next(reader, None)
        if header is None:
            raise _error(ValueError, "CSV vacío.")

        h = [c.strip().lower() for c in header]
        def _find(*keys):
            for k in keys:
                if k in h:
                    return h.index(k)
            return None

        ix = _find("x", "easting", "east")
        iy = _find("y", "northing", "north")
        if ix is None or iy is None:
            raise _error(ValueError, "El CSV debe tener cabeceras 'X' y 'Y' (o easting/northing).")

        for r in reader:
            if not r or all(not (c or "").strip() for c in r):
                continue
            try:
                x = float(str(r[ix]).replace(",", "."))
                y = float(str(r[iy]).replace(",", "."))
                rows.append((x, y))
            except Exception:  # nosec B112
                continue

    if not rows:
        raise _error(ValueError, "No se encontraron coordenadas válidas en el CSV.")
    return rows

def _collect_coordinates_types_and_labels(models: List[Dict[str, Any]]) -> Tuple[np.ndarray, np.ndarray, List[str], List[int]]:
    """Recoge coordenadas, vector ``type_i`` y etiquetas por modelo/capa.

    El orden de ``type_i`` coincide exactamente con el orden de ``models`` que
    se pasa a ``combine_wt(models)``. Así PyWake aplica la curva/diámetro/altura
    correcta a cada coordenada cuando hay varios modelos de aerogenerador.
    """
    coords: List[Tuple[float, float]] = []
    type_i: List[int] = []
    labels: List[str] = []
    counts: List[int] = []

    for i, m in enumerate(models or []):
        local: List[Tuple[float, float]] = []
        # Preferir puntos vivos suministrados por la UI (capa en memoria editada)
        cxy = m.get("coords_xy")
        if cxy:
            try:
                local = [(float(p[0]), float(p[1])) for p in cxy]
            except Exception:
                local = []
        if not local:
            p = (m.get("coords_csv") or "").strip()
            if p and os.path.isfile(p):
                local = _read_coords_csv(p)

        name = str(m.get("name") or (m.get("meta") or {}).get("name") or f"Modelo {i+1}")
        layer_name = str(m.get("source_layer_name") or "").strip()
        if layer_name and layer_name not in name:
            label = f"{name} · {layer_name}"
        else:
            label = name
        labels.append(label)
        counts.append(len(local))

        if local:
            coords.extend(local)
            type_i.extend([int(i)] * len(local))

    if not coords:
        raise _error(ValueError, "No hay coordenadas válidas en las capas/CSV proporcionados.")
    return np.asarray(coords, dtype=float), np.asarray(type_i, dtype=int), labels, counts


def _pad_to_step(vmin: float, vmax: float, step: float) -> Tuple[float, float]:
    lo = math.floor(vmin / step) * step
    hi = math.ceil(vmax / step) * step
    if hi <= lo:
        hi = lo + step
    return lo, hi

def _to_1d_float(arr, name: str) -> np.ndarray:
    """
    Convierte arr a 1D float de forma robusta.
    """
    if arr is None:
        raise _error(RuntimeError, "No se pudo leer '{name}' del dataset.", name=name)

    try:
        if hasattr(arr, "values"):
            arr = arr.values
    except Exception:  # nosec B110
        pass

    if isinstance(arr, (bytes, bytearray)):
        raise _error(RuntimeError, "'{name}' es bytes (lectura errónea).", name=name)
    if isinstance(arr, str):
        raise _error(RuntimeError, "'{name}' es str (lectura errónea).", name=name)

    a = np.asarray(arr)

    if a.dtype == object:
        try:
            cleaned = []
            for v in a.ravel():
                if isinstance(v, (bytes, bytearray)):
                    vv = v.decode("utf-8", errors="ignore").strip()
                    cleaned.append(float(vv))
                else:
                    cleaned.append(float(v))
            a = np.asarray(cleaned, dtype=float)
        except Exception as e:
            raise _error(RuntimeError, "No se pudo convertir '{name}' a float: {error}", name=name, error=e)

    a = np.asarray(a, dtype=float).ravel()
    if a.size < 2:
        raise _error(RuntimeError, "'{name}' no tiene suficientes valores para definir bounds.", name=name)
    a = a[np.isfinite(a)]
    if a.size < 2:
        raise _error(RuntimeError, "'{name}' contiene NaNs/no finitos.", name=name)
    return a

def _get_site_bounds(site) -> Tuple[float, float, float, float]:
    """
    Lee bounds desde coords x/y del Dataset (xarray).
    Funciona tanto para WAsPGridSite como para XRSite (WRG).
    """
    ds = getattr(site, "ds", None)
    if ds is None:
        ds = getattr(site, "dataset", None)
    if ds is None:
        raise _error(RuntimeError, "El site no expone 'ds'/'dataset'.")

    x_src = None
    y_src = None

    try:
        if hasattr(ds, "coords"):
            if "x" in ds.coords:
                x_src = ds.coords["x"]
            if "y" in ds.coords:
                y_src = ds.coords["y"]
    except Exception:  # nosec B110
        pass

    try:
        if x_src is None and "x" in ds:
            x_src = ds["x"]
        if y_src is None and "y" in ds:
            y_src = ds["y"]
    except Exception:  # nosec B110
        pass

    x_vals = _to_1d_float(x_src, "x")
    y_vals = _to_1d_float(y_src, "y")

    return float(np.nanmin(x_vals)), float(np.nanmax(x_vals)), float(np.nanmin(y_vals)), float(np.nanmax(y_vals))


def _ensure_dataset_has_ti(site, ti_value: float = 0.10) -> None:
    """
    Para BastankhahGaussianDeficit en varios flujos, es más seguro que exista ds['TI'].
    Creamos ds['TI'] y además alias ds['ti15ms'], ds['ti'] con dims correctas:
      ('x','y') y si existen también 'h' y 'wd' -> ('x','y','h','wd').

    (Esto vale para WAsP y para WRG/XRSite)
    """
    ti_value = float(ti_value)
    ti_value = min(max(ti_value, 0.0), 0.10)

    ds = getattr(site, "ds", None)
    if ds is None:
        ds = getattr(site, "dataset", None)
    if ds is None:
        return

    # Si ya existe TI o ti/ti15ms, aún así garantizamos 'TI'
    try:
        has_TI = ("TI" in ds)
    except Exception:
        has_TI = False

    if has_TI:
        # asegurar aliases
        try:
            if "ti" not in ds:
                ds["ti"] = ds["TI"]
            if "ti15ms" not in ds:
                ds["ti15ms"] = ds["TI"]
        except Exception:  # nosec B110
            pass
        return

    # dims objetivo
    try:
        sizes = getattr(ds, "sizes", {}) or {}
        dims = []
        for d in ("x", "y", "h", "wd"):
            if d in sizes:
                dims.append(d)
        if "x" not in dims or "y" not in dims:
            # fallback mínimo
            dims = ["x", "y"]
        shape = tuple(int(sizes.get(d, 1)) for d in dims)
        arr = np.full(shape, ti_value, dtype=np.float32)
        ds["TI"] = (tuple(dims), arr)
        ds["ti"] = ds["TI"]
        ds["ti15ms"] = ds["TI"]
        _debug_print(f"[AEP-plot] Inyectado ds['TI']=ds['ti']=ds['ti15ms'] con TI fija={ti_value:.2f} dims={dims}")
    except Exception as e:
        _debug_print(f"[AEP-plot] No se pudo inyectar TI fija en dataset: {e}")


# ============ Construcción de grid (anclado + control memoria) ============
def _build_domain_anchored_grid(
    sx_min: float, sx_max: float, sy_min: float, sy_max: float,
    gx_min_req: float, gx_max_req: float, gy_min_req: float, gy_max_req: float,
    res_x: float, res_y: float,
    max_cells: int = 2_000_000,
    max_span_m: float = 60_000.0
) -> Tuple[np.ndarray, np.ndarray, float, float, float, float, float, float]:

    gx_min = max(gx_min_req, sx_min); gx_max = min(gx_max_req, sx_max)
    gy_min = max(gy_min_req, sy_min); gy_max = min(gy_max_req, sy_max)
    if gx_min >= gx_max: gx_min, gx_max = sx_min, sx_max
    if gy_min >= gy_max: gy_min, gy_max = sy_min, sy_max

    cx = 0.5 * (gx_min + gx_max)
    cy = 0.5 * (gy_min + gy_max)
    half = max_span_m * 0.5
    gx_min = max(sx_min, max(gx_min, cx - half)); gx_max = min(sx_max, min(gx_max, cx + half))
    gy_min = max(sy_min, max(gy_min, cy - half)); gy_max = min(sy_max, min(gy_max, cy + half))

    def _grid_with_res(rx: float, ry: float):
        kx_start = int(math.ceil((gx_min - sx_min) / rx))
        kx_end   = int(math.floor((gx_max - sx_min) / rx))
        ky_start = int(math.ceil((gy_min - sy_min) / ry))
        ky_end   = int(math.floor((gy_max - sy_min) / ry))

        grid_x = sx_min + np.arange(kx_start, kx_end + 1, dtype=float) * rx
        grid_y = sy_min + np.arange(ky_start, ky_end + 1, dtype=float) * ry

        grid_x = grid_x[(grid_x >= sx_min) & (grid_x <= sx_max)]
        grid_y = grid_y[(grid_y >= sy_min) & (grid_y <= sy_max)]

        if grid_x.size == 0:
            grid_x = np.array([sx_min, min(sx_max, sx_min + rx)], float)
        if grid_y.size == 0:
            grid_y = np.array([sy_min, min(sy_max, sy_min + ry)], float)

        return grid_x, grid_y

    grid_x, grid_y = _grid_with_res(res_x, res_y)

    nx, ny = int(grid_x.size), int(grid_y.size)
    cells = nx * ny
    if cells > max_cells:
        ratio = math.sqrt(cells / max_cells) * 1.05
        res_x_eff = res_x * ratio
        res_y_eff = res_y * ratio
        grid_x, grid_y = _grid_with_res(res_x_eff, res_y_eff)
    else:
        res_x_eff, res_y_eff = res_x, res_y

    gx_min_eff = float(grid_x.min()); gx_max_eff = float(grid_x.max())
    gy_min_eff = float(grid_y.min()); gy_max_eff = float(grid_y.max())

    return grid_x, grid_y, gx_min_eff, gx_max_eff, gy_min_eff, gy_max_eff, res_x_eff, res_y_eff


# TerrainFollowingDistance (used by PyWake for WAsP sites) builds a
# 1000-point terrain profile for every cell-turbine pair, which PyWake's
# memory_GB estimate does not count (measured peak: ~125 kB per pair,
# temporaries included). Flow maps are therefore computed in tiles of at most
# this many cell-turbine pairs.
_FLOW_MAP_TILE_PAIRS = 4_000


def _tiled_flow_map(flow_map_func, grid_x, grid_y, n_turbines: int, after_tile=None, **kwargs):
    """Compute a horizontal flow map tile by tile and join WS_eff and WS.

    Every cell is computed independently, so the joined map is identical to a
    single call on the full grid. ``after_tile(done, total)`` is called after
    each tile, e.g. to report progress or raise on cancellation.
    """
    import xarray as xr

    grid_x = np.asarray(grid_x)
    grid_y = np.asarray(grid_y)
    tile_cells = max(1, _FLOW_MAP_TILE_PAIRS // max(int(n_turbines), 1))
    cols = min(grid_x.size, tile_cells)
    rows = max(1, tile_cells // cols)
    n_tiles = len(range(0, grid_x.size, cols)) * len(range(0, grid_y.size, rows))
    done = 0

    def _tile(x, y):
        nonlocal done
        flow_map = flow_map_func(grid=HorizontalGrid(x=x, y=y), **kwargs)
        # WS only if PyWake gave it: the exporter writes the effective speed alone and says why (#75, row 5.7).
        tile = xr.Dataset({v: flow_map[v] for v in ("WS_eff", "WS") if v in flow_map})
        done += 1
        if after_tile is not None:
            after_tile(done, n_tiles)
        return tile

    return xr.concat(
        [
            xr.concat(
                [_tile(grid_x[c:c + cols], grid_y[r:r + rows]) for c in range(0, grid_x.size, cols)],
                dim="x",
            )
            for r in range(0, grid_y.size, rows)
        ],
        dim="y",
    )


def _gamma_one_plus_three_over_k(k_values: np.ndarray) -> np.ndarray:
    k = np.asarray(k_values, dtype=float)
    out = np.full(k.shape, np.nan, dtype=float)
    valid = np.isfinite(k) & (k > 0.0)
    if not np.any(valid):
        return out
    try:
        from scipy.special import gammaln
        out[valid] = np.exp(gammaln(1.0 + 3.0 / k[valid]))
    except Exception:
        out[valid] = np.fromiter(
            (math.gamma(1.0 + 3.0 / float(value)) for value in k[valid]),
            dtype=float,
            count=int(np.sum(valid)),
        )
    return out


def _pick_resource_dominant_wd(site, x_positions=None, y_positions=None) -> Optional[Tuple[float, float]]:
    """Select the dominant sector without running a full wind-farm AEP matrix.

    The score is a vectorised wind-power-density proxy per direction:
    Sector_frequency * (A * Speedup)^3 * Gamma(1 + 3/k).
    It uses the resource itself and is therefore much cheaper than simulating all
    wind directions and wind-speed bins only to choose one map direction.
    """
    ds = getattr(site, "ds", None)
    if ds is None:
        ds = getattr(site, "dataset", None)
    if ds is None:
        return None
    try:
        if not all(name in ds for name in ("Sector_frequency", "Weibull_A", "Weibull_k")):
            return None
        freq_full = ds["Sector_frequency"]
        if "wd" not in getattr(freq_full, "dims", ()):
            return None
        freq = freq_full
        point_ix = point_iy = None
        point_dim = "wake_raster_point"
        # Focus the automatic direction on actual turbine locations instead of
        # averaging the complete resource domain. Paired vectorized indexers
        # avoid a Python turbine loop and avoid creating a Cartesian x/y subset.
        if (
            x_positions is not None
            and y_positions is not None
            and "x" in getattr(freq_full, "dims", ())
            and "y" in getattr(freq_full, "dims", ())
        ):
            try:
                import xarray as xr
                x_coord = np.asarray(freq_full.coords["x"].values, dtype=float).ravel()
                y_coord = np.asarray(freq_full.coords["y"].values, dtype=float).ravel()
                xp = np.asarray(x_positions, dtype=float).ravel()
                yp = np.asarray(y_positions, dtype=float).ravel()
                n_points = min(xp.size, yp.size)
                if n_points and x_coord.size and y_coord.size:
                    xp, yp = xp[:n_points], yp[:n_points]
                    ix_right = np.clip(np.searchsorted(x_coord, xp), 0, x_coord.size - 1)
                    ix_left = np.clip(ix_right - 1, 0, x_coord.size - 1)
                    point_ix = np.where(
                        np.abs(x_coord[ix_right] - xp) < np.abs(x_coord[ix_left] - xp),
                        ix_right,
                        ix_left,
                    ).astype(np.int64)
                    iy_right = np.clip(np.searchsorted(y_coord, yp), 0, y_coord.size - 1)
                    iy_left = np.clip(iy_right - 1, 0, y_coord.size - 1)
                    point_iy = np.where(
                        np.abs(y_coord[iy_right] - yp) < np.abs(y_coord[iy_left] - yp),
                        iy_right,
                        iy_left,
                    ).astype(np.int64)
                    ix_da = xr.DataArray(point_ix, dims=point_dim)
                    iy_da = xr.DataArray(point_iy, dims=point_dim)
                    freq = freq_full.isel(x=ix_da, y=iy_da)
            except Exception as exc:
                point_ix = point_iy = None
                freq = freq_full
                _debug_print(f"[Wake raster] No se pudo muestrear recurso en turbinas: {exc}")

        def _sample_like_frequency(data_array):
            da = data_array.broadcast_like(freq_full)
            if point_ix is not None and point_iy is not None:
                import xarray as xr
                da = da.isel(
                    x=xr.DataArray(point_ix, dims=point_dim),
                    y=xr.DataArray(point_iy, dims=point_dim),
                )
            return da.broadcast_like(freq)

        a_da = _sample_like_frequency(ds["Weibull_A"])
        k_da = _sample_like_frequency(ds["Weibull_k"])
        local_a = np.asarray(a_da.values, dtype=np.float32)
        if "Speedup" in ds:
            local_a = local_a * np.asarray(_sample_like_frequency(ds["Speedup"]).values, dtype=np.float32)
        f = np.asarray(freq.values, dtype=np.float32)
        k = np.asarray(k_da.values, dtype=np.float32)
        gamma3 = _gamma_one_plus_three_over_k(k).astype(np.float32, copy=False)
        score = f * local_a * local_a * local_a * gamma3
        wd_axis = list(freq.dims).index("wd")
        reduce_axes = tuple(axis for axis in range(score.ndim) if axis != wd_axis)
        score_wd = np.nanmean(score, axis=reduce_axes) if reduce_axes else score
        wd = np.asarray(freq.coords["wd"].values, dtype=float).ravel()
        score_wd = np.asarray(score_wd, dtype=float).ravel()
        n = min(wd.size, score_wd.size)
        wd, score_wd = wd[:n], score_wd[:n]
        finite = np.isfinite(wd) & np.isfinite(score_wd)
        wd, score_wd = wd[finite], score_wd[finite]
        if wd.size == 0:
            return None
        # Many WRG/GRD datasets close the circular coordinate by duplicating 0 at 360.
        if wd.size > 1 and abs(((wd[-1] - wd[0]) % 360.0)) < 1e-6 and abs(wd[-1] - wd[0]) > 1.0:
            wd, score_wd = wd[:-1], score_wd[:-1]
        idx = int(np.nanargmax(score_wd))
        return float(wd[idx] % 360.0), float(score_wd[idx])
    except Exception as exc:
        _debug_print(f"[Wake raster] No se pudo seleccionar sector dominante desde el recurso: {exc}")
        return None


def _terrain_on_grid(site, grid_x: np.ndarray, grid_y: np.ndarray):
    """Bilinear terrain interpolation implemented with NumPy only.

    The wake grid is rectilinear, so vectorised index arithmetic is much faster
    than constructing a full xarray interpolation graph for every task.
    """
    ds = getattr(site, "ds", None)
    if ds is None:
        ds = getattr(site, "dataset", None)
    if ds is None:
        return None
    try:
        if "Elevation" not in ds:
            return None
        da = ds["Elevation"]
        for dim in list(getattr(da, "dims", ())):
            if dim not in ("x", "y"):
                da = da.isel({dim: 0}, drop=True)
        if hasattr(da, "transpose"):
            da = da.transpose("y", "x")
        src_x = np.asarray(da.coords["x"].values, dtype=float).ravel()
        src_y = np.asarray(da.coords["y"].values, dtype=float).ravel()
        z = np.asarray(da.values, dtype=np.float32)
        if src_x[0] > src_x[-1]:
            src_x, z = src_x[::-1].copy(), z[:, ::-1]
        if src_y[0] > src_y[-1]:
            src_y, z = src_y[::-1].copy(), z[::-1, :]
        gx = np.asarray(grid_x, dtype=float)
        gy = np.asarray(grid_y, dtype=float)
        if src_x.size < 2 or src_y.size < 2:
            return None
        ix = np.clip(np.searchsorted(src_x, gx, side="right") - 1, 0, src_x.size - 2)
        iy = np.clip(np.searchsorted(src_y, gy, side="right") - 1, 0, src_y.size - 2)
        x0, x1 = src_x[ix], src_x[ix + 1]
        y0, y1 = src_y[iy], src_y[iy + 1]
        tx = np.divide(gx - x0, x1 - x0, out=np.zeros_like(gx), where=(x1 != x0))
        ty = np.divide(gy - y0, y1 - y0, out=np.zeros_like(gy), where=(y1 != y0))
        z00 = z[np.ix_(iy, ix)]
        z10 = z[np.ix_(iy, ix + 1)]
        z01 = z[np.ix_(iy + 1, ix)]
        z11 = z[np.ix_(iy + 1, ix + 1)]
        tx2 = tx[None, :].astype(np.float32, copy=False)
        ty2 = ty[:, None].astype(np.float32, copy=False)
        out = (
            z00 * (1.0 - tx2) * (1.0 - ty2)
            + z10 * tx2 * (1.0 - ty2)
            + z01 * (1.0 - tx2) * ty2
            + z11 * tx2 * ty2
        )
        return np.asarray(out, dtype=np.float32)
    except Exception as exc:
        _debug_print(f"[Wake raster] No se pudo interpolar Elevation: {exc}")
        return None


def _create_single_wake_raster_file(
    flow_map,
    *,
    wd_real: float,
    ws_real: float,
    output_dir: str,
    crs_wkt: str,
    metadata: Dict[str, Any],
    terrain_values=None,
):
    """Write a precomputed PyWake flow map as a worker-safe raster package."""
    if _build_wake_raster_file is None:
        raise _error(RuntimeError, "No se pudo importar ag_core.qgis_io.wake_raster.")
    return _build_wake_raster_file(
        flow_map,
        wd=wd_real,
        ws=ws_real,
        output_dir=output_dir,
        crs_wkt=crs_wkt,
        metadata=metadata,
        terrain_values=terrain_values,
    )

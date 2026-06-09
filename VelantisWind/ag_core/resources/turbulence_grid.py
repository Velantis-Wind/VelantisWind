# -*- coding: utf-8 -*-
"""Utilidades de recurso WRG/TI para el cálculo AEP.

Incluye inyección de TI fija, reproyección/alineado de rasters TI sobre el grid
WRG y lectura de TI por turbina. Mantiene las dependencias QGIS/GDAL aisladas
del motor principal tanto como es posible.
"""
from __future__ import annotations

import os
import re
from typing import Any, Callable, List, Optional, Tuple

import numpy as np

from ..physics.common.compat import emit

F32 = np.float32

try:
    from osgeo import gdal, osr
except Exception:  # pragma: no cover
    gdal = None
    osr = None

try:
    from py_wake.site.xrsite import XRSite
except Exception:  # pragma: no cover
    XRSite = None
try:
    from py_wake.site.distance import StraightDistance
except Exception:  # pragma: no cover
    StraightDistance = None

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


def _project_crs_authid_fallback() -> Optional[str]:
    try:
        from qgis.core import QgsProject  # type: ignore
        return QgsProject.instance().crs().authid()
    except Exception:
        return None

def _xy_dims(ds):
    try:
        cand = ("Elevation", "Weibull_A", "Weibull_k", "orog_spd",
                "Sector_frequency", "Turning", "V", "Z0")
        for name in cand:
            if name in ds:
                v = ds[name]
                dims = tuple(getattr(v, "dims", ()) or ())
                if "x" in dims and "y" in dims:
                    return tuple(d for d in dims if d in ("x", "y"))
    except Exception:
        pass
    try:
        keys = list(getattr(ds, "dims", {}).keys())
        if "x" in keys and "y" in keys:
            return tuple(d for d in keys if d in ("x", "y"))
    except Exception:
        pass
    return ("x", "y")

def _apply_fixed_ti(site, ti: float, prefer_var: str = "TI") -> None:
    ti = float(ti)
    if not (0.0 <= ti < 1.0):
        raise ValueError("'ti' debe ser unitario (0.10 ≡ 10%).")
    ds = getattr(site, "ds", None) or getattr(site, "dataset", None)
    if ds is None:
        if hasattr(site, "default_TI"):
            try:
                site.default_TI = ti
                return
            except Exception:
                pass
        raise RuntimeError("El 'site' no expone 'ds'/'dataset'.")

    # En PyWake, algunos modelos esperan TI en mayúsculas ('TI'), otros usan
    # 'ti' o 'ti15ms'. Además, puede venir con dims (x,y) o (x,y,h,wd).
    # Para evitar errores tipo "'TI' needed ... is missing" generamos TI con
    # las dims más completas disponibles y añadimos alias.

    # Normalizar nombre preferido
    prefer_var = prefer_var if prefer_var in ("TI", "ti", "ti15ms") else "TI"

    dims_xy = _xy_dims(ds)
    nx = int(ds.sizes.get("x", 1)) if "x" in ds.sizes else 1
    ny = int(ds.sizes.get("y", 1)) if "y" in ds.sizes else 1
    nh = int(ds.sizes.get("h", 1)) if "h" in ds.sizes else 1
    nwd = int(ds.sizes.get("wd", 1)) if "wd" in ds.sizes else 1

    # dims finales en orden canónico
    dims: Tuple[str, ...] = tuple(dims_xy)
    shape: Tuple[int, ...]

    # Nota: dims_xy puede ser ('x','y') o ('y','x') dependiendo del ds
    if "h" in getattr(ds, "dims", {}):
        dims = dims + ("h",)
    if "wd" in getattr(ds, "dims", {}):
        dims = dims + ("wd",)

    # shape coherente con dims_xy
    shape_xy = (nx, ny) if dims_xy == ("x", "y") else (ny, nx)
    if dims == dims_xy:
        shape = shape_xy
    elif dims == dims_xy + ("h",):
        shape = shape_xy + (nh,)
    elif dims == dims_xy + ("wd",):
        shape = shape_xy + (nwd,)
    else:
        # dims == dims_xy + ('h','wd')
        shape = shape_xy + (nh, nwd)

    arr = np.full(shape, ti, dtype=F32)

    # Escribir TI principal y alias
    # TI (mayúsculas) es el más seguro para BastankhahGaussianDeficit en varias versiones.
    ds["TI"] = (dims, arr)
    ds["ti"] = ds["TI"]
    ds["ti15ms"] = ds["TI"]

    # Si el usuario pidió otro nombre preferido, lo exponemos también
    if prefer_var not in ("TI", "ti", "ti15ms"):
        ds[prefer_var] = ds["TI"]

    if hasattr(site, "default_TI"):
        try:
            site.default_TI = ti
        except Exception:
            pass

    # Asegurar no-NaN
    try:
        a = np.array(ds["TI"], dtype=F32)
        a[~np.isfinite(a)] = ti
        ds["TI"] = (dims, a.reshape(shape))
        ds["ti"] = ds["TI"]
        ds["ti15ms"] = ds["TI"]
    except Exception:
        pass

def _authid_to_wkt(authid: Optional[str]) -> Optional[str]:
    if not authid or osr is None:
        return None
    txt = str(authid).strip()
    if not txt:
        return None
    srs = osr.SpatialReference()
    try:
        if txt.upper().startswith("EPSG:"):
            if srs.ImportFromEPSG(int(txt.split(":", 1)[1])) == 0:
                return srs.ExportToWkt()
        if srs.SetFromUserInput(txt) == 0:
            return srs.ExportToWkt()
    except Exception:
        return None
    return None

def _coord_step(vals: np.ndarray) -> float:
    arr = np.asarray(vals, dtype=float).ravel()
    if arr.size < 2:
        return 1.0
    diffs = np.diff(arr)
    diffs = diffs[np.isfinite(diffs)]
    diffs = np.abs(diffs[diffs != 0])
    if diffs.size == 0:
        return 1.0
    return float(np.median(diffs))

def _to_unit_ti(arr: np.ndarray) -> np.ndarray:
    out = np.asarray(arr, dtype=F32).copy()
    finite = out[np.isfinite(out)]
    if finite.size and float(np.nanmean(finite)) > 1.0:
        out *= F32(0.01)
    out = np.clip(out, 0.0, 1.0)
    return out

def _extract_height_from_ti_path(path: str) -> Optional[float]:
    name = os.path.basename(str(path or ""))
    patterns = (
        r'(?i)(?:ti(?:mean)?|turb(?:ulence)?)[^\d]{0,5}(\d+(?:[\.,]\d+)?)',
        r'(?i)(\d+(?:[\.,]\d+)?)\s*m(?:[^a-zA-Z]|$)',
        r'(?i)h(?:ub)?[_-]?(\d+(?:[\.,]\d+)?)',
    )
    for pat in patterns:
        m = re.search(pat, name)
        if m:
            try:
                return float(m.group(1).replace(',', '.'))
            except Exception:
                pass
    return None

def _looks_like_lonlat_geotransform(src) -> bool:
    """Heurística para ASCII grid sin CRS: detectar si sus coordenadas parecen geográficas."""
    try:
        gt = src.GetGeoTransform(can_return_null=True) or src.GetGeoTransform()
        nx = int(src.RasterXSize)
        ny = int(src.RasterYSize)
        if gt is None:
            return False
        xmin = float(gt[0])
        dx = float(gt[1])
        rot1 = float(gt[2])
        ymax = float(gt[3])
        rot2 = float(gt[4])
        dy = float(gt[5])
        xmax = xmin + dx * nx
        ymin = ymax + dy * ny
        if abs(rot1) > 1e-9 or abs(rot2) > 1e-9:
            return False
        if not (-180.5 <= xmin <= 180.5 and -180.5 <= xmax <= 180.5):
            return False
        if not (-90.5 <= ymin <= 90.5 and -90.5 <= ymax <= 90.5):
            return False
        # Para grids geográficos típicos de TI esperamos pasos pequeños en grados.
        if abs(dx) > 1.0 or abs(dy) > 1.0:
            return False
        return True
    except Exception:
        return False

def _sample_ti_raster_on_wrg_grid(ds, ti_raster_path: str, target_wkt: str, default_ti: float = 0.10) -> np.ndarray:
    """Lee, reproyecta y alinea un raster TI a la malla (x,y) del WRG.

    La alineación se hace explícitamente contra el grid del WRG mediante ``gdal.Warp``
    (mismo CRS, extensión, resolución y tamaño de celda), evitando depender de la
    reproyección "on-the-fly" o de grids intermedios ambiguos.
    """
    if gdal is None or osr is None:
        raise RuntimeError("GDAL/OSR no disponible para leer el raster de turbulencia")
    if ds is None:
        raise RuntimeError("Dataset WRG no disponible para inyectar TI")
    if not ti_raster_path or not os.path.isfile(ti_raster_path):
        raise RuntimeError(f"Raster TI no válido: {ti_raster_path}")

    x = np.asarray(ds["x"].values, dtype=float)
    y = np.asarray(ds["y"].values, dtype=float)
    if x.size < 1 or y.size < 1:
        raise RuntimeError("El dataset WRG no contiene coordenadas x/y válidas")

    src = gdal.Open(ti_raster_path, gdal.GA_ReadOnly)
    if src is None:
        raise RuntimeError(f"No se pudo abrir el raster TI: {ti_raster_path}")

    src_wkt = src.GetProjection() or ""
    src_label = "definido"
    if not src_wkt:
        if _looks_like_lonlat_geotransform(src):
            srs = osr.SpatialReference()
            srs.ImportFromEPSG(4326)
            src_wkt = srs.ExportToWkt()
            src_label = "EPSG:4326 (inferido)"
            _log("[WRG][TI] Raster sin CRS explícito; por su cabecera parece lon/lat y se asume EPSG:4326.", Qgis.Warning)
        else:
            src_wkt = target_wkt
            src_label = "CRS del WRG/proyecto (inferido)"
            _log("[WRG][TI] Raster sin CRS explícito; se asume el CRS del WRG/proyecto.", Qgis.Warning)

    nx = int(x.size)
    ny = int(y.size)
    dx = _coord_step(x)
    dy = _coord_step(y)
    xmin = float(np.min(x))
    xmax = float(np.max(x))
    ymin = float(np.min(y))
    ymax = float(np.max(y))
    bounds = (xmin - dx / 2.0, ymin - dy / 2.0, xmax + dx / 2.0, ymax + dy / 2.0)
    nodata = -9999.0

    _log(
        f"[WRG][TI] Reproyectando y alineando '{os.path.basename(ti_raster_path)}' al grid del WRG "
        f"(size={nx}x{ny}, dx={dx:.3f}, dy={dy:.3f})."
    )

    warp_opts = gdal.WarpOptions(
        format="MEM",
        srcSRS=src_wkt,
        dstSRS=target_wkt,
        resampleAlg=gdal.GRA_Bilinear,
        outputBounds=bounds,
        width=nx,
        height=ny,
        dstNodata=nodata,
        multithread=True,
        errorThreshold=0.0,
    )
    mem = gdal.Warp("", src, options=warp_opts)
    if mem is None:
        raise RuntimeError("GDAL.Warp devolvió None al alinear el raster TI al grid WRG")

    arr = mem.GetRasterBand(1).ReadAsArray().astype(F32)
    arr[arr == nodata] = np.nan
    # GDAL entrega (row=y_desc, col=x_asc); la malla WRG interna usa (x, y)
    arr = np.flipud(arr).T
    arr = _to_unit_ti(arr)

    n_nan = int(np.count_nonzero(~np.isfinite(arr)))
    if n_nan:
        if n_nan == int(arr.size):
            _log(
                f"[WRG][TI] El raster TI ha quedado completamente fuera de cobertura tras reproyección/alineado; "
                f"se usará TI uniforme={default_ti:.3f} en toda la malla.",
                Qgis.Warning,
            )
        else:
            _log(
                f"[WRG][TI] Raster TI con {n_nan} celdas fuera de cobertura tras reproyección/alineado; "
                f"se rellenan con {default_ti:.3f}.",
                Qgis.Warning,
            )
        arr[~np.isfinite(arr)] = F32(default_ti)

    try:
        finite = arr[np.isfinite(arr)]
        if finite.size:
            _log(
                f"[WRG][TI] Alineado OK | src_crs={src_label} | rango_reproy=[{float(np.nanmin(finite)):.3f}, {float(np.nanmax(finite)):.3f}]"
            )
    except Exception:
        pass
    return arr

def _build_ti_cube_for_site(ds, ti_raster_paths: List[str], default_ti: float, target_wkt: str,
                            ti_heights_m: Optional[List[Optional[float]]] = None):
    try:
        import xarray as xr
    except Exception as e:
        raise RuntimeError(f"xarray no disponible para construir TI por altura: {e}")

    h_site = None
    try:
        if "h" in ds.coords or "h" in ds:
            h_site = np.asarray(ds["h"].values, dtype=float).ravel()
    except Exception:
        h_site = None

    items = []
    ti_heights_m = list(ti_heights_m or [])
    for i, path in enumerate(ti_raster_paths):
        arr = _sample_ti_raster_on_wrg_grid(ds, path, target_wkt=target_wkt, default_ti=default_ti)
        h = None
        if i < len(ti_heights_m) and ti_heights_m[i] is not None:
            try:
                h = float(ti_heights_m[i])
                _log(f"[WRG][TI] Altura override para '{os.path.basename(path)}': {h:g} m")
            except Exception:
                h = None
        if h is None:
            h = _extract_height_from_ti_path(path)
        items.append((path, h, arr))

    if not items:
        raise RuntimeError("No se han podido leer raster(s) TI")

    valid_h = [h for _, h, _ in items if h is not None]
    if len(items) == 1 or len(set(round(h, 6) for h in valid_h)) < 2:
        path, h0, arr = items[0]
        if h_site is not None and h_site.size > 1:
            if h0 is not None:
                _log(f"[WRG][TI] Solo hay un raster TI ({os.path.basename(path)}) a {h0:g} m; se aplicará a todas las alturas del WRG como aproximación.", Qgis.Warning)
            else:
                _log(f"[WRG][TI] Solo hay un raster TI ({os.path.basename(path)}) sin altura identificable; se aplicará a todas las alturas del WRG como aproximación.", Qgis.Warning)
            cube = np.repeat(arr[:, :, None], int(h_site.size), axis=2).astype(F32)
            da = xr.DataArray(cube, dims=("x", "y", "h"), coords={"x": ds["x"].values, "y": ds["y"].values, "h": h_site})
            return da, {"mode": "single_replicated", "paths": [path], "heights": [h0] if h0 is not None else []}
        da = xr.DataArray(arr, dims=("x", "y"), coords={"x": ds["x"].values, "y": ds["y"].values})
        return da, {"mode": "single_xy", "paths": [path], "heights": [h0] if h0 is not None else []}

    seen = {}
    for path, h, arr in items:
        if h is None:
            _log(f"[WRG][TI] No se pudo inferir la altura de '{os.path.basename(path)}'; se ignora para construir TI(x,y,h).", Qgis.Warning)
            continue
        key = round(float(h), 6)
        if key in seen:
            _log(f"[WRG][TI] Altura TI duplicada {h:g} m en '{os.path.basename(path)}'; se conserva el primer raster para esa altura.", Qgis.Warning)
            continue
        seen[key] = (float(h), path, arr)

    if len(seen) < 2:
        path, h0, arr = items[0]
        _log("[WRG][TI] No se han identificado al menos dos alturas TI distintas; se usará el primer raster para todas las alturas.", Qgis.Warning)
        if h_site is not None and h_site.size > 1:
            cube = np.repeat(arr[:, :, None], int(h_site.size), axis=2).astype(F32)
            da = xr.DataArray(cube, dims=("x", "y", "h"), coords={"x": ds["x"].values, "y": ds["y"].values, "h": h_site})
            return da, {"mode": "single_replicated", "paths": [path], "heights": [h0] if h0 is not None else []}
        da = xr.DataArray(arr, dims=("x", "y"), coords={"x": ds["x"].values, "y": ds["y"].values})
        return da, {"mode": "single_xy", "paths": [path], "heights": [h0] if h0 is not None else []}

    h_in = np.array(sorted(seen.keys()), dtype=float)
    stack = np.stack([seen[key][2] for key in sorted(seen.keys())], axis=2).astype(F32)

    if h_site is None or h_site.size == 0:
        da = xr.DataArray(stack, dims=("x", "y", "h"), coords={"x": ds["x"].values, "y": ds["y"].values, "h": h_in})
        return da, {"mode": "multi_native", "paths": [seen[key][1] for key in sorted(seen.keys())], "heights": h_in.tolist()}

    cube = np.empty((stack.shape[0], stack.shape[1], int(h_site.size)), dtype=F32)
    for ix in range(stack.shape[0]):
        for iy in range(stack.shape[1]):
            cube[ix, iy, :] = np.interp(h_site, h_in, stack[ix, iy, :], left=stack[ix, iy, 0], right=stack[ix, iy, -1]).astype(F32)

    if float(np.min(h_site)) < float(np.min(h_in)) or float(np.max(h_site)) > float(np.max(h_in)):
        _log(f"[WRG][TI] Las alturas del WRG {h_site.tolist()} exceden el rango TI disponible {h_in.tolist()}; se usan valores de borde fuera del rango.", Qgis.Warning)

    da = xr.DataArray(cube, dims=("x", "y", "h"), coords={"x": ds["x"].values, "y": ds["y"].values, "h": h_site})
    return da, {"mode": "multi_interp_h", "paths": [seen[key][1] for key in sorted(seen.keys())], "heights": h_in.tolist()}

def _apply_ti_raster_to_site(site, ds, ti_raster_path: Any, project_crs_authid: Optional[str] = None,
                             default_ti: float = 0.10,
                             ti_heights_m: Optional[List[Optional[float]]] = None):
    """Muestrea/reproyecta uno o varios raster(s) de TI sobre la malla (x,y[,h]) del WRG.

    - Acepta una ruta o una lista de rutas.
    - Si hay varias alturas TI identificables por override manual o por nombre de archivo, construye TI(x,y,h).
    - Si solo hay una capa, la replica en altura cuando el WRG tiene varias h.
    - Si el raster no trae CRS, se asume el CRS del proyecto/target.
    - Si hay huecos, se rellenan con ``default_ti``.
    """
    if ds is None:
        raise RuntimeError("Dataset WRG no disponible para inyectar TI")

    if isinstance(ti_raster_path, (list, tuple)):
        ti_paths = [str(p).strip() for p in ti_raster_path if str(p).strip()]
    else:
        ti_paths = [str(ti_raster_path).strip()] if str(ti_raster_path).strip() else []
    if not ti_paths:
        raise RuntimeError("No se han indicado raster(s) TI válidos")

    target_wkt = _authid_to_wkt(project_crs_authid)
    target_label = project_crs_authid
    if not target_wkt:
        ds_auth = None
        try:
            ds_auth = ds.attrs.get('crs_authid') or ds.attrs.get('crs')
        except Exception:
            ds_auth = None
        if ds_auth:
            target_wkt = _authid_to_wkt(ds_auth)
            target_label = ds_auth if target_wkt else target_label
    if not target_wkt:
        try:
            auth = _project_crs_authid_fallback()
        except Exception:
            auth = None
        target_wkt = _authid_to_wkt(auth)
        if target_wkt:
            target_label = auth
    if not target_wkt:
        raise RuntimeError("No se pudo resolver el CRS destino del WRG/proyecto para el raster TI")
    _log(f"[WRG][TI] CRS destino del grid WRG: {target_label or '?'}")

    ti_da, meta = _build_ti_cube_for_site(
        ds, ti_paths, default_ti=float(default_ti), target_wkt=target_wkt,
        ti_heights_m=ti_heights_m,
    )

    ds["TI"] = ti_da
    ds["ti"] = ds["TI"]
    ds["ti15ms"] = ds["TI"]
    try:
        ds["TI"].attrs["source"] = ";".join(os.path.basename(p) for p in meta.get("paths", ti_paths))
        ds["TI"].attrs["units"] = "fraction"
        if meta.get("heights"):
            ds["TI"].attrs["input_heights_m"] = list(meta.get("heights", []))
    except Exception:
        pass

    site = _rebuild_xrsite_if_needed(site, ds)
    try:
        arr = np.asarray(ds["TI"].values, dtype=float)
        vmin = float(np.nanmin(arr))
        vmax = float(np.nanmax(arr))
        _log(
            f"[WRG][TI] Raster(s) TI aplicados: {', '.join(os.path.basename(p) for p in meta.get('paths', ti_paths))} "
            f"| modo={meta.get('mode','?')} | rango=[{vmin:.3f}, {vmax:.3f}] | target_crs={target_label or '?'}"
        )
    except Exception:
        _log(f"[WRG][TI] Raster(s) TI aplicados: {', '.join(os.path.basename(p) for p in ti_paths)}")
    return site, ds

def _ensure_wd_dim(ds):
    """
    Asegura que el Dataset tenga dimensión/coord 'wd' (wind direction) con tamaño > 1.

    Este ajuste es crítico para WRG: si el dataset acaba con 'wd' de tamaño 1 (o con un
    dim alternativo tipo 'sector'), PyWake puede intentar evaluar direcciones (p.ej. 128°)
    e indexar fuera de rango → "index 128 is out of bounds for axis 0 with size 1".

    Estrategia:
    - Si 'wd' existe y tiene >1 → OK.
    - Si no, intentamos encontrar una dimensión candidata (sector/dir/...) con tamaño >1
      en Sector_frequency / Weibull_A / Weibull_k.
    - Si ya existe 'wd' pero tamaño 1 y hay un dim candidato >1, eliminamos/squeezeamos
      el 'wd' antiguo y usamos el candidato como 'wd'.
    """
    try:
        import numpy as _np
        import xarray as _xr  # noqa: F401
    except Exception:
        return ds

    if ds is None:
        return ds

    if "wd" in ds.dims and int(ds.sizes.get("wd", 0)) > 1:
        return ds

    cand_vars = [v for v in ("Sector_frequency", "Weibull_A", "Weibull_k") if v in ds]
    if not cand_vars:
        return ds

    # Buscar dim candidato con size>1 (preferimos nombres tipo sector)
    best_dim = None
    best_size = 0
    best_name_score = -1
    name_scores = {
        "sector": 3, "sectors": 3,
        "dir": 2, "dirs": 2,
        "direction": 2, "directions": 2,
        "wd": 1,
    }

    for v in cand_vars:
        da = ds[v]
        for d in da.dims:
            sz = int(da.sizes.get(d, 0))
            if sz <= 1:
                continue
            score = name_scores.get(d.lower(), 0)
            # Elegimos el de mayor score y mayor tamaño
            if (score > best_name_score) or (score == best_name_score and sz > best_size):
                best_dim = d
                best_size = sz
                best_name_score = score

    if not best_dim or best_size <= 1:
        return ds

    out = ds

    # Si hay un wd antiguo de tamaño 1, lo eliminamos (squeeze) para evitar conflicto
    if "wd" in out.dims and int(out.sizes.get("wd", 0)) == 1 and best_dim != "wd":
        try:
            out = out.squeeze("wd", drop=True)
        except Exception:
            pass

    nsec = int(best_size)
    sector_width = float(out.attrs.get("sector_width", 360.0 / float(nsec)))
    wd = (_np.arange(nsec, dtype=float) * sector_width).astype(float)

    # Renombrar mejor dim a wd si hace falta
    if best_dim != "wd":
        try:
            out = out.rename({best_dim: "wd"})
        except Exception:
            # Si falla por conflicto residual, intentamos con un nombre temporal
            tmp = "wd_tmp"
            out = out.rename({best_dim: tmp})
            out = out.rename({tmp: "wd"})

    # Asignar coordenadas wd
    try:
        out = out.assign_coords(wd=wd)
    except Exception:
        pass

    out.attrs["sector_width"] = float(sector_width)
    return out

def _rebuild_xrsite_if_needed(site, ds):
    """
    Si tenemos XRSite disponible y el ds ha cambiado (por ejemplo al renombrar dims),
    recrea el site para asegurar coherencia.
    """
    if XRSite is None or ds is None:
        return site
    try:
        if StraightDistance is not None:
            return XRSite(ds, distance=StraightDistance())
        return XRSite(ds)
    except Exception:
        return site

def _compute_ti_per_turbine(*args,
                           ti_cap: float = 1.00,
                           default_ti: float = 0.10,
                           hh_per_turb: Optional[np.ndarray] = None) -> np.ndarray:
    """Compatibilidad:
    - _compute_ti_per_turbine(sim) -> TI por turbina desde el resultado de PyWake.
    - _compute_ti_per_turbine(site, xs, ys) -> TI por turbina desde el dataset del site.

    En caso de fallo: devuelve TI=default_ti (por defecto 0.10) y limita a <= ti_cap.
    """
    # ---- Caso 1: llamado con sim ----
    if len(args) == 1:
        sim = args[0]
        try:
            ti = getattr(sim, "TI", None)
            if ti is None:
                ti = getattr(sim, "ti", None)
            if ti is None:
                return np.array([], dtype=F32)
            for d in [d for d in getattr(ti, "dims", ()) if d not in ("wt",)]:
                try:
                    ti = ti.mean(d)
                except Exception:
                    pass
            out = np.asarray(getattr(ti, "values", ti), dtype=F32).ravel()
            return np.clip(out, 0.0, float(ti_cap)).astype(F32)
        except Exception:
            return np.array([], dtype=F32)

    # ---- Caso 2: llamado con site, xs, ys ----
    if len(args) < 3:
        return np.array([], dtype=F32)

    site, xs, ys = args[0], args[1], args[2]
    n = int(len(xs)) if xs is not None else 0
    if n == 0:
        return np.array([], dtype=F32)

    xs = np.asarray(xs, dtype=F32).ravel()
    ys = np.asarray(ys, dtype=F32).ravel()

    def _fallback():
        return np.full(n, float(default_ti), dtype=F32)

    try:
        ds = getattr(site, "ds", None) or getattr(site, "dataset", None)
        if ds is None:
            return np.clip(_fallback(), 0.0, float(ti_cap)).astype(F32)

        ti_da = None
        for key in ("TI", "ti", "ti15ms", "turbulence_intensity", "turbulenceIntensity"):
            if key in ds:
                ti_da = ds[key]
                break
        if ti_da is None:
            return np.clip(_fallback(), 0.0, float(ti_cap)).astype(F32)

        dims = set(getattr(ti_da, "dims", ()))
        coords = getattr(ti_da, "coords", {})
        has_x = ("x" in dims) or ("x" in coords)
        has_y = ("y" in dims) or ("y" in coords)

        if has_x and has_y:
            try:
                ti_i = ti_da.interp(x=("wt", xs), y=("wt", ys))
            except Exception:
                return np.clip(_fallback(), 0.0, float(ti_cap)).astype(F32)

            if hh_per_turb is not None:
                try:
                    hhv = np.asarray(hh_per_turb, dtype=F32).ravel()
                    has_h = ("h" in getattr(ti_i, "dims", ())) or ("h" in getattr(ti_i, "coords", {}))
                    if has_h and hhv.size == n:
                        try:
                            ti_i = ti_i.interp(h=("wt", hhv))
                        except Exception:
                            pass
                except Exception:
                    pass

            for d in [d for d in getattr(ti_i, "dims", ()) if d != "wt"]:
                try:
                    ti_i = ti_i.mean(d)
                except Exception:
                    pass

            vals = np.asarray(getattr(ti_i, "values", ti_i), dtype=F32).ravel()
            ti = vals if vals.size == n else _fallback()
        else:
            try:
                tmp = ti_da
                for d in [d for d in getattr(tmp, "dims", ())]:
                    try:
                        tmp = tmp.mean(d)
                    except Exception:
                        pass
                scalar = float(np.asarray(getattr(tmp, "values", tmp)).reshape(-1)[0])
                ti = np.full(n, scalar, dtype=F32)
            except Exception:
                ti = _fallback()

        return np.clip(ti, 0.0, float(ti_cap)).astype(F32)

    except Exception:
        return np.clip(_fallback(), 0.0, float(ti_cap)).astype(F32)

xy_dims = _xy_dims
apply_fixed_ti = _apply_fixed_ti
authid_to_wkt = _authid_to_wkt
coord_step = _coord_step
to_unit_ti = _to_unit_ti
extract_height_from_ti_path = _extract_height_from_ti_path
looks_like_lonlat_geotransform = _looks_like_lonlat_geotransform
sample_ti_raster_on_wrg_grid = _sample_ti_raster_on_wrg_grid
build_ti_cube_for_site = _build_ti_cube_for_site
apply_ti_raster_to_site = _apply_ti_raster_to_site
ensure_wd_dim = _ensure_wd_dim
rebuild_xrsite_if_needed = _rebuild_xrsite_if_needed
compute_ti_per_turbine = _compute_ti_per_turbine

__all__ = [
    "configure_logging",
    "xy_dims",
    "apply_fixed_ti",
    "authid_to_wkt",
    "coord_step",
    "to_unit_ti",
    "extract_height_from_ti_path",
    "looks_like_lonlat_geotransform",
    "sample_ti_raster_on_wrg_grid",
    "build_ti_cube_for_site",
    "apply_ti_raster_to_site",
    "ensure_wd_dim",
    "rebuild_xrsite_if_needed",
    "compute_ti_per_turbine",
]

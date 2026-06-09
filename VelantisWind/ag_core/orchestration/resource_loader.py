# -*- coding: utf-8 -*-
"""Resource-loading helpers for the Energy/AEP module.

The functions here deliberately avoid importing QGIS.  The caller passes the
logger and the existing compatibility callbacks from ``aep_compute`` so this
module can be unit-tested outside QGIS and without changing the calculation
semantics.
"""

from __future__ import annotations

import os
from typing import Any, Callable, Dict, List, Optional, Tuple

import numpy as np

LogFn = Callable[..., None]


def normalize_resource_inputs(
    *,
    wasp_dir: str,
    models: List[Dict[str, Any]],
    wrg_paths: Optional[List[str]],
    wrg_ti_paths: Optional[List[str]],
    wrg_ti_path: Optional[str],
) -> Tuple[bool, List[str], Optional[List[str]]]:
    """Validate and normalize resource inputs coming from the UI.

    Returns ``(use_wrg, normalized_wrg_paths, normalized_wrg_ti_paths)``.
    It intentionally preserves the old validation messages to avoid surprising
    testers and downstream UI code.
    """
    use_wrg = bool(wrg_paths)
    if (not wrg_ti_paths) and wrg_ti_path:
        wrg_ti_paths = [str(wrg_ti_path)]

    if use_wrg:
        clean_wrg_paths = [str(p) for p in (wrg_paths or []) if str(p).strip()]
        if not clean_wrg_paths:
            raise ValueError("No se proporcionaron rutas WRG")
        for path in clean_wrg_paths:
            if not os.path.isfile(path):
                raise ValueError(f"WRG/ZIP no existe: {path}")
            if not path.lower().endswith((".wrg", ".zip")):
                raise ValueError(f"Extensión WRG no soportada (use .wrg o .zip): {path}")
        wrg_paths = clean_wrg_paths
    else:
        if not wasp_dir or not os.path.isdir(wasp_dir):
            raise ValueError("Directorio WAsP inválido o no existente")
        wrg_paths = []

    if not models:
        raise ValueError("No se han definido modelos de aerogeneradores")

    return use_wrg, list(wrg_paths or []), wrg_ti_paths


def load_energy_site(
    *,
    use_wrg: bool,
    wasp_dir: str,
    wrg_paths: List[str],
    wrg_ti_paths: Optional[List[str]],
    wrg_ti_heights_m: Optional[List[Optional[float]]],
    project_crs_authid: Optional[str],
    fixed_ti: Optional[float],
    log: LogFn,
    warning_level: Any,
    info_level: Any,
    resolve_wasp_dir_for_pywake: Callable[[str], Optional[str]],
    sanitize_dir_for_pywake: Callable[..., Any],
    load_site_with_filter: Callable[[str], Tuple[Any, Any, str]],
    ensure_wd_dim: Callable[[Any], Any],
    rebuild_xrsite_if_needed: Callable[[Any, Any], Any],
    apply_ti_raster_to_site: Callable[..., Tuple[Any, Any]],
) -> Tuple[Any, Any, str, Optional[float], str]:
    """Load a WAsP or WRG resource and apply WRG TI rasters when present.

    Returns ``(site, ds, used_dir, fixed_ti, wasp_dir)``. ``fixed_ti`` and
    ``wasp_dir`` may be normalized for the caller.
    """
    if use_wrg:
        from ..wrg_site import load_wrg_site

        site, ds, used_dir = load_wrg_site(wrg_paths or [])
        log(f"[WRG] Site cargado desde: {used_dir}", info_level)
        ds = ensure_wd_dim(ds)
        site = rebuild_xrsite_if_needed(site, ds)

        if wrg_ti_paths:
            try:
                site, ds = apply_ti_raster_to_site(
                    site,
                    ds,
                    wrg_ti_paths,
                    project_crs_authid=project_crs_authid,
                    default_ti=float(fixed_ti) if fixed_ti is not None else 0.10,
                    ti_heights_m=wrg_ti_heights_m,
                )
            except Exception as exc:
                log(
                    f"[WRG][TI] No se pudieron aplicar los raster(s) TI '{wrg_ti_paths}': {exc}. Se usará fallback fijo.",
                    warning_level,
                )
                if fixed_ti is None:
                    fixed_ti = 0.10
        else:
            if fixed_ti is None:
                fixed_ti = 0.10
            log(
                f"[WRG][TI] No se ha seleccionado raster de turbulencia. Se usará TI fija={float(fixed_ti):.3f}.",
                warning_level,
            )

        try:
            log(f"[WRG] dims={dict(ds.sizes)} | wd[n]={int(ds.sizes.get('wd', 0))}", info_level)
        except Exception:
            pass
        return site, ds, used_dir, fixed_ti, wasp_dir

    wasp_dir = os.path.abspath(wasp_dir)
    compat_dir = resolve_wasp_dir_for_pywake(wasp_dir)
    if compat_dir is None:
        raise RuntimeError(
            "No se ha podido encontrar una subcarpeta válida para PyWake "
            f"en '{wasp_dir}'. Revisa la estructura exportada de WAsP."
        )

    sanitize_dir_for_pywake(compat_dir, move_bad=True)
    site, ds, used_dir = load_site_with_filter(compat_dir)
    return site, ds, used_dir, fixed_ti, wasp_dir


def ensure_ti_available(
    *,
    site: Any,
    ds: Any,
    fixed_ti: Optional[float],
    log: LogFn,
    warning_level: Any,
    apply_fixed_ti: Callable[..., None],
) -> Any:
    """Ensure the PyWake site exposes a TI-like variable.

    Some PyWake combinations access ``TI``/``ti``/``ti15ms`` even when no added
    turbulence model is selected. This mirrors the previous in-line safeguard.
    """
    ds = ds or getattr(site, "ds", None) or getattr(site, "dataset", None)
    if ds is None:
        raise RuntimeError("El 'site' cargado no expone 'ds'/'dataset'.")

    try:
        ds_check = getattr(site, "ds", None) or getattr(site, "dataset", None)
        if ds_check is not None and ("TI" not in ds_check) and ("ti15ms" not in ds_check) and ("ti" not in ds_check):
            ti_val = float(fixed_ti) if fixed_ti is not None else 0.10
            if (not np.isfinite(ti_val)) or ti_val <= 0 or ti_val >= 1:
                ti_val = 0.10
            log(f"[TI] Dataset sin 'TI/ti15ms/ti' -> inyecto TI fija={ti_val:.3f}.", warning_level)
            apply_fixed_ti(site, ti_val, prefer_var="TI")
    except Exception as exc:
        log(f"[TI] No se pudo inyectar TI fija en dataset: {exc}", warning_level)
    return ds

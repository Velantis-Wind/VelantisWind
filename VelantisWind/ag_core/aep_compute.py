# -*- coding: utf-8 -*-
"""
aep_compute.py  — Cálculo AEP con carga robusta de WAsP grids (py_wake-safe) + escritura a capas QGIS

- Detecta automáticamente y prioriza la subcarpeta 'pywake_compat' si existe.
- Valida nombres con el patrón real de py_wake para evitar IndexError al cargar .grd.
- Opción de saneo: mueve a _bad_for_pywake los .grd que no casen (por defecto activado).
- La física de estelas es la configuración validada (``wake_setup``), construida exactamente por la fábrica, con la
  comprobación de clases antes de simular y sin sustituciones ni reintentos; lo ejecutado se lee de los objetos.
- Calcula el AEP por turbina de la configuración principal, A_0 y las variantes del desglose firmado de pérdidas.
- Imprime por modelo: curva de potencia (muestra), altura de buje y diámetro.
- Actualiza las capas de puntos por modelo (las creadas en aep_setup_dialog) y configura Map Tips.

Uso desde el diálogo:
    from .ag_core.aep_compute import compute_and_update
    res = compute_and_update(wasp_dir, models, compute_variants=True)
"""

from __future__ import annotations
import copy
import os
import re
from typing import Dict, List, Tuple, Any, Optional, Callable

import numpy as np

try:
    from osgeo import gdal, osr
except Exception:
    gdal = None
    osr = None


# ========= QGIS =========
from qgis.utils import iface
from qgis.core import (
    Qgis, QgsMessageLog,
    QgsProject, QgsVectorLayer, QgsField, QgsFeature, QgsGeometry,
    QgsWkbTypes, QgsPointXY, QgsSpatialIndex, QgsFeatureRequest, edit
)
from qgis.PyQt.QtCore import QCoreApplication, QThread, QVariant

# --- WAsP grids / py_wake
from py_wake.site.wasp_grid_site import WaspGridSite
# --- XRSite (para WRG)
try:
    from py_wake.site.xrsite import XRSite
except Exception:
    XRSite = None
try:
    from py_wake.site.distance import StraightDistance
except Exception:
    StraightDistance = None


# --- Loader robusto (si está disponible en tu proyecto)
# (Este import funciona cuando aep_compute.py está en ag/ag_core/)
try:
    from ..union_recurso import load_waspgridsite as _robust_loader
except Exception:
    try:
        # fallback si se ejecuta fuera del paquete
        from union_recurso import load_waspgridsite as _robust_loader  # type: ignore
    except Exception:
        _robust_loader = None  # fallback a WaspGridSite.from_wasp_grd

from py_wake.wind_turbines._wind_turbines import WindTurbines
from py_wake.wind_turbines.power_ct_functions import PowerCtFunctionList

try:
    from .resources import wasp as _resource_wasp
    from .resources import turbulence_grid as _resource_ti
    from .layout import io as _layout_io
    from .turbines import height as _turbine_height
    from .turbines import factory as _turbine_factory
    from .turbines import curves as _turbine_curves
    from .turbines import density_resolution as _density_resolution
    from .turbines.bin_power import BIN_MEAN, POINT
    from .results import aep_arrays as _result_arrays
    from .results import tables as _result_tables
    from .results import summary as _result_summary
    from .qgis_io import export as _qgis_export
    from .qgis_io import layers as _qgis_layers
    from .simulation import runner as _simulation_runner
    from .simulation import zero_node as _zero_node
    from .simulation.pywake_lock import PYWAKE_LOCK
    from .wake_setup import api as _wake_api
    from .wake_setup import config as _wake_config
    from .wake_setup import factory as _wake_factory
    from .wake_setup import notices as _wake_notices
    from .wake_setup import presets as _wake_presets
    from .wake_setup import readers as _wake_readers
    from .wake_setup.api import NOT_SET
    from .wake_setup.instrumentation import ConvergenceRecorder, effective_ti_per_turbine
    from .results import result_v2 as _result_v2
    from .results import variants as _variants
    from . import orchestration as _orchestration
    from . import edge_cases as _edge_cases
    from .log_text import log_text, shown
    from .turbine import CT_ESTIMATED_WARNING
except Exception:  # pragma: no cover - fallback standalone
    from ag_core.log_text import log_text, shown  # type: ignore
    from ag_core.resources import wasp as _resource_wasp  # type: ignore
    from ag_core.resources import turbulence_grid as _resource_ti  # type: ignore
    from ag_core.layout import io as _layout_io  # type: ignore
    from ag_core.turbines import height as _turbine_height  # type: ignore
    from ag_core.turbines import factory as _turbine_factory  # type: ignore
    from ag_core.turbines import curves as _turbine_curves  # type: ignore
    from ag_core.turbines import density_resolution as _density_resolution  # type: ignore
    from ag_core.turbines.bin_power import BIN_MEAN, POINT  # type: ignore
    from ag_core.results import aep_arrays as _result_arrays  # type: ignore
    from ag_core.results import tables as _result_tables  # type: ignore
    from ag_core.results import summary as _result_summary  # type: ignore
    from ag_core.qgis_io import export as _qgis_export  # type: ignore
    from ag_core.qgis_io import layers as _qgis_layers  # type: ignore
    from ag_core.simulation import runner as _simulation_runner  # type: ignore
    from ag_core.simulation import zero_node as _zero_node  # type: ignore
    from ag_core.simulation.pywake_lock import PYWAKE_LOCK  # type: ignore
    from ag_core.wake_setup import api as _wake_api  # type: ignore
    from ag_core.wake_setup import config as _wake_config  # type: ignore
    from ag_core.wake_setup import factory as _wake_factory  # type: ignore
    from ag_core.wake_setup import notices as _wake_notices  # type: ignore
    from ag_core.wake_setup import presets as _wake_presets  # type: ignore
    from ag_core.wake_setup import readers as _wake_readers  # type: ignore
    from ag_core.wake_setup.api import NOT_SET  # type: ignore
    from ag_core.wake_setup.instrumentation import ConvergenceRecorder, effective_ti_per_turbine  # type: ignore
    from ag_core.results import result_v2 as _result_v2  # type: ignore
    from ag_core.results import variants as _variants  # type: ignore
    from ag_core import orchestration as _orchestration  # type: ignore
    from ag_core import edge_cases as _edge_cases  # type: ignore
    from ag_core.turbine import CT_ESTIMATED_WARNING  # type: ignore



def _resource_ti_notes(*, use_wrg: bool, wrg_ti_paths: Optional[List[str]] = None,
                       unique_hubs: Optional[List[float]] = None) -> List[Any]:
    """The notes of the ambient TI of a WRG (what was given, not a judgement of the physics)."""
    notes: List[Any] = []
    hubs = [float(h) for h in (unique_hubs or [])]
    ti_paths = [p for p in (wrg_ti_paths or []) if p]
    if use_wrg:
        if ti_paths:
            if len(ti_paths) == 1:
                notes.append(log_text("WRG: se ha usado un único ráster de TI ambiente; si mezclas varias alturas de buje, esa TI "
                                      "se replica/interpola como aproximación vertical."))
            else:
                notes.append(log_text("WRG: se han usado {n} rásteres de TI ambiente para reconstruir TI por altura cuando es "
                                      "posible.", n=len(ti_paths)))
        else:
            notes.append(log_text("WRG: no se ha proporcionado ráster TI, así que la TI ambiente se ha fijado al valor de respaldo "
                                  "definido por el usuario como campo uniforme."))
        if len(hubs) > 1 and len(ti_paths) <= 1:
            notes.append(log_text("Hay varias alturas de buje pero solo una TI ambiente verticalmente uniforme; el cálculo sigue "
                                  "siendo válido, aunque es una aproximación en altura."))
    return notes


# ============================================================
# Utils de logging/diagnóstico
# ============================================================
def _log(msg: str, level=Qgis.Info):
    if str(os.environ.get("VELANTISWIND_DEBUG", "")).strip().lower() in {"1", "true", "yes", "on", "debug"}:
        print("[AEP] " + msg)
    try:
        QgsMessageLog.logMessage(msg, "AEP", level=level)
    except Exception:  # nosec B110
        pass
    try:
        # The message bar is a widget: touching it from a QgsTask worker corrupts Qt state.
        # It shows only the warnings, translated from their template when the message carries one;
        # the message log keeps every message in Spanish.
        if level in (Qgis.Warning, Qgis.Critical) and QThread.currentThread() == QCoreApplication.instance().thread():
            if getattr(msg, "template_item", None):
                try:
                    from ..i18n import tr_text
                    msg = shown(msg, tr_text)
                except Exception:  # nosec B110
                    pass
            iface.messageBar().pushMessage("AEP", msg, level=level, duration=6)
    except Exception:  # nosec B110
        pass


# The messages of the wake physics (the contract of the API, the validation, the notices) are translated wherever the
# AEP shows them, even when no window that registers them was opened.
from .wake_setup.messages_translations import register_messages_translations  # noqa: E402

register_messages_translations()

# Conectar módulos extraídos al logger/QGIS levels del motor principal.
try:
    _turbine_height.configure_logging(_log, warning_level=Qgis.Warning, info_level=Qgis.Info)
    _turbine_factory.configure_logging(_log, warning_level=Qgis.Warning, info_level=Qgis.Info)
    _turbine_curves.configure_logging(_log, warning_level=Qgis.Warning, info_level=Qgis.Info)
except Exception:  # nosec B110
    pass

# ============================================================
# Helpers WAsP / py_wake (filtro nombres + carga)
# ============================================================
# Patrón real que usa py_wake en wasp_grid_site.py:
_PYW_NAME_RE = re.compile(r"Sector (\w+|\d+)\s+ Height (\d+\.?\d*)m\s+ ([a-zA-Z0-9\- ]+)")

def _resolve_wasp_dir_for_pywake(wasp_dir: str) -> str:
    """Compatibilidad: delega en ag_core.resources.wasp."""
    return _resource_wasp.resolve_wasp_dir_for_pywake(wasp_dir)

def _sanitize_dir_for_pywake(dirpath: str, move_bad: bool = True) -> Tuple[int, int, List[str]]:
    """Compatibilidad: delega en ag_core.resources.wasp."""
    return _resource_wasp.sanitize_dir_for_pywake(dirpath, move_bad=move_bad)

def _load_site_with_filter(wasp_dir: str,
                           prefer_pywake_compat: bool = True,
                           sanitize: bool = True):
    """Compatibilidad: delega la carga WAsP en ag_core.resources.wasp."""
    _resource_wasp.configure_logging(_log, warning_level=Qgis.Warning, info_level=Qgis.Info)
    return _resource_wasp.load_site_with_filter(
        wasp_dir,
        prefer_pywake_compat=prefer_pywake_compat,
        sanitize=sanitize,
    )

# ============================================================
# Utilidades coords / CSV
# ============================================================
def _read_xy_csv(path: str) -> Tuple[List[float], List[float]]:
    """Compatibilidad: delega lectura CSV en ag_core.layout.io."""
    return _layout_io.read_xy_csv(path)

def _bbox_from_site(site) -> Tuple[float, float, float, float]:
    """Compatibilidad: delega bbox en ag_core.layout.io."""
    return _layout_io.bbox_from_site(site)


# ============================================================
# TI fija / inyección si falta
# ============================================================
def _xy_dims(ds):
    return _resource_ti.xy_dims(ds)

def _apply_fixed_ti(site, ti: float, prefer_var: str = "TI") -> None:
    _resource_ti.configure_logging(_log, warning_level=Qgis.Warning, info_level=Qgis.Info)
    return _resource_ti.apply_fixed_ti(site, ti, prefer_var=prefer_var)

def _authid_to_wkt(authid: Optional[str]) -> Optional[str]:
    return _resource_ti.authid_to_wkt(authid)


def _coord_step(vals: np.ndarray) -> float:
    return _resource_ti.coord_step(vals)


def _to_unit_ti(arr: np.ndarray) -> np.ndarray:
    return _resource_ti.to_unit_ti(arr)


def _extract_height_from_ti_path(path: str) -> Optional[float]:
    return _resource_ti.extract_height_from_ti_path(path)


def _looks_like_lonlat_geotransform(src) -> bool:
    return _resource_ti.looks_like_lonlat_geotransform(src)



def _sample_ti_raster_on_wrg_grid(ds, ti_raster_path: str, target_wkt: str, default_ti: float = 0.10) -> np.ndarray:
    _resource_ti.configure_logging(_log, warning_level=Qgis.Warning, info_level=Qgis.Info)
    return _resource_ti.sample_ti_raster_on_wrg_grid(ds, ti_raster_path, target_wkt, default_ti=default_ti)


def _build_ti_cube_for_site(ds, ti_raster_paths: List[str], default_ti: float, target_wkt: str,
                            ti_heights_m: Optional[List[Optional[float]]] = None):
    _resource_ti.configure_logging(_log, warning_level=Qgis.Warning, info_level=Qgis.Info)
    return _resource_ti.build_ti_cube_for_site(
        ds, ti_raster_paths, default_ti, target_wkt, ti_heights_m=ti_heights_m
    )


def _apply_ti_raster_to_site(site, ds, ti_raster_path: Any, project_crs_authid: Optional[str] = None,
                             default_ti: float = 0.10,
                             ti_heights_m: Optional[List[Optional[float]]] = None):
    """Compatibilidad: delega TI raster/WRG en ag_core.resources.turbulence_grid."""
    _resource_ti.configure_logging(_log, warning_level=Qgis.Warning, info_level=Qgis.Info)
    return _resource_ti.apply_ti_raster_to_site(
        site, ds, ti_raster_path,
        project_crs_authid=project_crs_authid,
        default_ti=default_ti,
        ti_heights_m=ti_heights_m,
    )


# ============================================================
# WT helpers
# ============================================================



def _ensure_wd_dim(ds):
    return _resource_ti.ensure_wd_dim(ds)



def _rebuild_xrsite_if_needed(site, ds):
    return _resource_ti.rebuild_xrsite_if_needed(site, ds)

# ---- Turbinas / curvas de potencia (extraído a ag_core.turbines) ----
def _is_pcf_list(pcf) -> bool:
    return _turbine_factory.is_pcf_list(pcf)

def _unwrap_pcf_list(pcf):
    return _turbine_factory.unwrap_pcf_list(pcf)

def _extract_flat_pcf(obj) -> Any:
    return _turbine_factory.extract_flat_pcf(obj)

def _ensure_wt_entry(m: Dict[str, Any]) -> Tuple[str, float, float, Any]:
    return _turbine_factory.ensure_wt_entry(m)

def _combine_wt(models: List[Dict[str, Any]]) -> Tuple[WindTurbines, bool]:
    return _turbine_factory.combine_wt(models)

def _auto_unit(P_arr: np.ndarray) -> Tuple[float, str]:
    return _turbine_curves.auto_unit(P_arr)

def _tabular_from_pcf(pcf) -> Optional[Tuple[np.ndarray, np.ndarray]]:
    return _turbine_curves.tabular_from_pcf(pcf)

def _eval_power(pcf, ws: np.ndarray) -> Optional[np.ndarray]:
    return _turbine_curves.eval_power(pcf, ws)

def _read_curve_from_model_dict(m) -> Optional[Tuple[np.ndarray, np.ndarray]]:
    return _turbine_curves.read_curve_from_model_dict(m)

def _print_power_curve_info(models: List[Dict[str, Any]]):
    return _turbine_curves.print_power_curve_info(models)


def _clip_hub_heights_to_site(wt_all: WindTurbines, site) -> None:
    _turbine_height.configure_logging(_log, warning_level=Qgis.Warning, info_level=Qgis.Info)
    return _turbine_height.clip_hub_heights_to_site(wt_all, site)


def _hub_heights_per_turbine(wt_all: WindTurbines, type_i, n: int) -> np.ndarray:
    return _turbine_height.hub_heights_per_turbine(wt_all, type_i, n, strict=True)


def _compute_ti_per_turbine(*args,
                           ti_cap: float = 1.00,
                           hh_per_turb: Optional[np.ndarray] = None) -> np.ndarray:
    return _resource_ti.compute_ti_per_turbine(*args, ti_cap=ti_cap, hh_per_turb=hh_per_turb)


import numpy as np

def _aep_per_turb(sim, hours_per_year: float = 8760.0):
    """Compatibilidad: extrae AEP por turbina con anualización explícita."""
    return _result_arrays.aep_per_turb(sim, hours_per_year=hours_per_year)

def compute_aep_from_ui(wasp_dir: str,
                        models: List[Dict[str, Any]],
                        wake_model: Any = NOT_SET,
                        wake_deficit_model: Any = NOT_SET,
                        wake_deficit_kwargs: Any = NOT_SET,
                        blockage_deficit_model: Any = NOT_SET,
                        turbulence_model: Any = NOT_SET,
                        include_turbulence: Any = NOT_SET,
                        include_blockage: Any = NOT_SET,
                        include_rotor_avg: Any = NOT_SET,
                        rotor_avg_model: Any = NOT_SET,
                        superposition_model: Any = NOT_SET,
                        compute_variants: bool = False,
                        fixed_ti: Optional[float] = None,
                        wfm_engine: Any = NOT_SET,
                        wrg_paths: Optional[List[str]] = None,
                        wrg_speedup_method: str = "none",
                        wrg_direction_count: Optional[int] = None,
                        wrg_wd_interp: str = "nearest",
                        wrg_ti_paths: Optional[List[str]] = None,
                        wrg_ti_path: Optional[str] = None,
                        wrg_ti_heights_m: Optional[List[Optional[float]]] = None,
                        project_crs_authid: Optional[str] = None,
                        energy_ws_step: Optional[float] = None,
                        air_density_mode: str = "off",
                        air_density_ref_kg_m3: Optional[float] = None,
                        air_density_ref_altitude_m: Optional[float] = None,
                        progress_callback: Optional[Callable[[int, str], None]] = None,
                        power_bin_mode: str = BIN_MEAN,
                        wake_physics: Any = NOT_SET,
                        wake_provenance: Optional[Dict[str, Any]] = None,
                        ) -> Dict[str, Any]:
    """AEP of the models on a WRG or a GRD, with the wake physics of the request (result of schema 2).

    The physics is ``wake_physics`` (``ag_core/wake_setup/api.py``) or, translated once, the fields of the previous
    schema (``wfm_engine``, ``wake_deficit_model``, …, each «not indicated» by default); a request that cannot be read
    or a configuration that cannot be calculated raises before loading anything (``api.RequestError``,
    ``api.ConfigRejected``), and nothing is replaced. The wind farm model is built by the factory with the class
    check before simulating, the main calculation and the terms of the signed loss breakdown (A_0 always, the
    variants with ``compute_variants``) are calculated with it, and what was executed is read from the built objects.
    All the PyWake work holds ``PYWAKE_LOCK``, shared with the wake raster.

    With a WRG, the resource settings: ``wrg_direction_count`` directions (``None``, the initial choice of
    ``resource_grid``), the interpolation ``wrg_wd_interp``, Speedup ``none`` (``wrg_speedup_method``; anything else
    is refused) and the wind speeds that cover the band of the turbines with ``energy_ws_step`` (``None``, the
    initial step of their curves). A request outside the options raises ``WrgContractError`` before any simulation,
    never rounded. With a GRD, the directions and wind speeds of its ``Site``; the WRG settings do not apply.

    ``wake_provenance`` is the provenance of a predefined model (``presets.provenance``), given with its configuration
    when the calculation is launched; it is checked against it (``presets.checked_provenance``) and recorded in the
    result.
    """
    config, legacy_request = _wake_api.resolve_request(
        wake_physics, wfm_engine=wfm_engine, wake_deficit_model=wake_deficit_model,
        superposition_model=superposition_model, rotor_avg_model=rotor_avg_model, turbulence_model=turbulence_model,
        blockage_deficit_model=blockage_deficit_model, wake_deficit_kwargs=wake_deficit_kwargs,
        include_turbulence=include_turbulence, include_blockage=include_blockage, include_rotor_avg=include_rotor_avg,
        wake_model=wake_model)
    _wake_api.check_calculable(config)
    provenance = _wake_presets.checked_provenance(config, wake_provenance)
    if legacy_request is not None:
        _log(_wake_api.legacy_note(legacy_request), Qgis.Warning)
    with PYWAKE_LOCK:
        return _compute_aep(
            config=config, provenance=provenance, legacy_request=legacy_request, wasp_dir=wasp_dir, models=models,
            compute_variants=compute_variants, fixed_ti=fixed_ti, wrg_paths=wrg_paths,
            wrg_speedup_method=wrg_speedup_method, wrg_direction_count=wrg_direction_count,
            wrg_wd_interp=wrg_wd_interp, wrg_ti_paths=wrg_ti_paths, wrg_ti_path=wrg_ti_path,
            wrg_ti_heights_m=wrg_ti_heights_m, project_crs_authid=project_crs_authid, energy_ws_step=energy_ws_step,
            air_density_mode=air_density_mode, air_density_ref_kg_m3=air_density_ref_kg_m3,
            air_density_ref_altitude_m=air_density_ref_altitude_m, progress_callback=progress_callback,
            power_bin_mode=power_bin_mode)


class _Discarded(Exception):
    """A simulation of the attempt of the exception of WeightedSum with the 0 m/s node failed (#63, decision 4)."""


def _compute_aep(*, config, provenance, legacy_request, wasp_dir, models, compute_variants, fixed_ti, wrg_paths,
                 wrg_speedup_method, wrg_direction_count, wrg_wd_interp, wrg_ti_paths, wrg_ti_path, wrg_ti_heights_m,
                 project_crs_authid, energy_ws_step, air_density_mode, air_density_ref_kg_m3,
                 air_density_ref_altitude_m, progress_callback, power_bin_mode) -> Dict[str, Any]:
    def _progress(value: int, message: str) -> None:
        """Notifica el progreso al callback (si lo hay) y al log de QGIS."""
        if progress_callback is not None:
            try:
                progress_callback(int(value), str(message))
            except Exception:  # nosec B110
                pass
        try:
            _log(f"[AEP][{value:3d}%] {message}", Qgis.Info)
        except Exception:  # nosec B110
            pass

    _progress(2, "Inicializando cálculo…")

    # Several selected QGIS layers may belong to one physical turbine model.
    # Compact them before both layout indexing and WindTurbines construction so
    # the same dense type vector is used throughout the AEP calculation.
    models = _turbine_factory.canonicalize_models(list(models or []))

    # Ajustes del recurso que no dependen del fichero, antes de cargar nada: el Speedup y,
    # con un WRG, las velocidades de cálculo de las turbinas (también sin modelos: error).
    _orchestration.check_speedup(wrg_speedup_method)
    wrg_speeds = None
    if wrg_paths:
        wrg_speeds = _orchestration.turbine_speed_grid(
            _orchestration.effective_turbines(models), energy_ws_step, " | ".join(str(p) for p in wrg_paths),
            bin_mean=power_bin_mode != POINT,
        )

    # Keep the caller-supplied TI separate from the loader fallback so reports
    # can distinguish a deliberate fixed-TI run from the automatic 10% fallback
    # used when no TI information was provided.
    fixed_ti_requested = fixed_ti

    use_wrg, wrg_paths, wrg_ti_paths = _orchestration.normalize_resource_inputs(
        wasp_dir=wasp_dir,
        models=models,
        wrg_paths=wrg_paths,
        wrg_ti_paths=wrg_ti_paths,
        wrg_ti_path=wrg_ti_path,
    )

    # ===========================
    # 1) Cargar Site (WAsP o WRG)
    # ===========================
    _progress(5, "Cargando recurso eólico (WAsP/WRG)…")
    site, ds, used_dir, fixed_ti, wasp_dir = _orchestration.load_energy_site(
        use_wrg=use_wrg,
        wasp_dir=wasp_dir,
        wrg_paths=wrg_paths,
        wrg_speedup_method=wrg_speedup_method,
        wrg_direction_count=wrg_direction_count,
        wrg_wd_interp=wrg_wd_interp,
        wrg_ti_paths=wrg_ti_paths,
        wrg_ti_heights_m=wrg_ti_heights_m,
        project_crs_authid=project_crs_authid,
        fixed_ti=fixed_ti,
        log=_log,
        warning_level=Qgis.Warning,
        info_level=Qgis.Info,
        resolve_wasp_dir_for_pywake=_resolve_wasp_dir_for_pywake,
        sanitize_dir_for_pywake=_sanitize_dir_for_pywake,
        load_site_with_filter=_load_site_with_filter,
        ensure_wd_dim=_ensure_wd_dim,
        rebuild_xrsite_if_needed=_rebuild_xrsite_if_needed,
        apply_ti_raster_to_site=_apply_ti_raster_to_site,
    )

    ds = _orchestration.ensure_ti_available(
        site=site,
        ds=ds,
        fixed_ti=fixed_ti,
        log=_log,
        warning_level=Qgis.Warning,
        apply_fixed_ti=_apply_fixed_ti,
    )

    # ---------------------------
    # Layout de aerogeneradores
    # ---------------------------
    layout = _orchestration.build_layout_arrays(
        models=models,
        site=site,
        wasp_dir=wasp_dir,
        use_wrg=use_wrg,
        wrg_paths=wrg_paths,
        dtype=np.float64,  # UTM coordinates must not collapse to a float32 grid
        read_xy_csv=_read_xy_csv,
        bbox_from_site=_bbox_from_site,
    )
    xs = layout["xs"]
    ys = layout["ys"]
    type_i = layout["type_i"]
    use_types = bool(layout["use_types"])
    skipped = int(layout["skipped"])
    _wake_api.check_layout(config, len(xs))  # what PyWake refuses only with the layout (R9f), before simulating

    config_notes: List[Any] = [_wake_api.legacy_note(legacy_request)] if legacy_request is not None else []
    use_wrg_resource = bool(wrg_paths)
    ti_paths_used = [p for p in ((wrg_ti_paths or []) if wrg_ti_paths is not None else ([wrg_ti_path] if wrg_ti_path else [])) if p]

    # ==========================================
    # 4) Construir WindTurbines combinado
    # ==========================================
    wt, use_types_wt = _combine_wt(models)
    # Curvas sin Ct: el que se ha estimado no es un dato del fabricante, y el resultado lo dice.
    for m in models:
        meta = m.get("meta") if isinstance(m.get("meta"), dict) else {}
        if meta.get("ct_estimated"):
            note = log_text("Modelo «{name}»: {warning}", name=m.get("name") or meta.get("name") or "Custom WT",
                            warning=log_text(CT_ESTIMATED_WARNING))
            _log(note, Qgis.Info)
            config_notes.append(note)
    # El WT combinado dicta si PyWake necesita type_i.
    use_types = bool(use_types_wt)
    if not use_types:
        type_i = None

    # Validar compatibilidad vertical del WRG sin modificar la geometría de la turbina.
    _clip_hub_heights_to_site(wt, site)
    if use_wrg_resource:
        try:
            _wrg_policy = str(ds.attrs.get("wrg_vertical_policy", "?"))
            _wrg_heights = list(ds.attrs.get("wrg_heights_m", []))
            if _wrg_policy == "single_height_reference":
                config_notes.append(log_text(
                    "WRG: solo hay una altura climática ({heights}); se usa como referencia vertical "
                    "sin modificar la altura de buje ni inferir shear.", heights=_wrg_heights,
                ))
            elif _wrg_policy == "multi_height_interpolation":
                config_notes.append(log_text(
                    "WRG: alturas climáticas disponibles {heights}; PyWake interpola linealmente en altura "
                    "cuando la HH está dentro del rango.", heights=_wrg_heights,
                ))
            config_notes.append(log_text(
                "WRG: se conservan A, k y frecuencia sectorial locales del WRG en cada "
                "posición, sin convertirlos a una Weibull global + Speedup."
            ))
        except Exception:
            pass

    # ===========================
    # 6) Turbulencia inicial (TI)
    # ===========================
    if fixed_ti is not None:
        try:
            _apply_fixed_ti(site, float(fixed_ti), prefer_var="TI")
        except Exception as e:
            _log(log_text("[AEP] No se pudo fijar TI={ti}: {error}", ti=fixed_ti, error=e), Qgis.Warning)
    hh_per_turb = _hub_heights_per_turbine(wt, type_i, len(xs))
    ti_per_turb = _compute_ti_per_turbine(site, xs, ys, hh_per_turb=hh_per_turb)

    unique_hubs = []
    try:
        if hh_per_turb is not None:
            unique_hubs = sorted({round(float(h), 6) for h in np.asarray(hh_per_turb).reshape(-1).tolist() if h is not None})
    except Exception:
        unique_hubs = []

    # ==========================================
    # 6.4) Densidad del aire de cada turbina
    # ==========================================
    # Qué densidad recibe cada turbina se decide en turbines/density_resolution.py.
    # Aquí solo va la política del AEP: si no se puede establecer, AirDensityError
    # detiene el cálculo, porque un AEP con la densidad equivocada es un número falso.
    air_density = _density_resolution.resolve_air_density(
        site=site,
        wt=wt,
        xs=xs,
        ys=ys,
        type_i=type_i if use_types else None,
        mode=air_density_mode,
        reference_density=air_density_ref_kg_m3,
        reference_altitude_m=air_density_ref_altitude_m,
    )
    wt_inputs: Dict[str, Any] = {}
    if air_density.values is not None:
        wt_inputs["Air_density"] = air_density.values
    for message in air_density.warnings:
        _log(message, Qgis.Warning)
        config_notes.append(message)
    for message in air_density.notes:
        _log(message, Qgis.Info)
        config_notes.append(message)
    if air_density.info:
        summary = log_text("Densidad del aire: {summary}.", summary=air_density.info["summary"])
        _log(summary, Qgis.Info)
        config_notes.append(summary)

    # ==========================================
    # 6.5) Parámetros del recurso
    # ==========================================
    resource = _orchestration.resolve_resource_settings(
        site, ds, use_wrg=use_wrg_resource, source=(ds.attrs.get("wrg_source") if use_wrg_resource else used_dir),
        speeds=wrg_speeds, models=models, bin_mean=power_bin_mode != POINT,
    )
    resource_record = resource["record"]
    wd_native = resource["native_wd"]
    wd_eval = resource["wd"]
    ws_eval = resource["ws"]
    aep_hours_per_year = resource["hours_per_year"]
    _log(_orchestration.resource_log_line(resource_record), Qgis.Info)
    config_notes.append(_orchestration.resource_note(resource_record))
    config_notes.extend(_resource_ti_notes(use_wrg=use_wrg_resource, wrg_ti_paths=ti_paths_used,
                                           unique_hubs=unique_hubs))

    # ==========================================
    # 7) El modelo de parque de la configuración, y su simulación
    # ==========================================
    # Each wind farm model is built by the factory from its configuration, with the class check before simulating;
    # nothing is replaced, and an error of PyWake is the error of the calculation (decisions 1 and 15).
    def build(target: Any) -> Any:
        if target is _variants.FREE_STREAM:
            wfm = _wake_factory.build_free_stream_model(config, site, wt, ws_grid=ws_eval, power_bin_mode=power_bin_mode)
            expected = _wake_factory.free_stream_expected_classes(config)
        else:
            expected = _wake_factory.expected_classes(target)
            wfm = _wake_factory.build_wind_farm_model(target, site, wt, ws_grid=ws_eval, power_bin_mode=power_bin_mode)
        _wake_factory.check_classes(expected, wfm)
        if target is not _variants.FREE_STREAM:
            _wake_factory.check_ws_reference(target, wfm)
        return wfm

    # The edge cases (#63): their warnings, said as they come.
    edge_warnings: List[Any] = []

    def edge_warning(text: Any) -> None:
        _log(text, Qgis.Warning)
        edge_warnings.append(text)

    # The warnings of the arguments and the persistent ones, once, before the first simulation (decision 9), each
    # part protected and with its own copies: a failure of a text is «aviso no disponible», never a stop of the
    # calculation, and nothing it does reaches what is calculated.
    persistent = []
    for part in (lambda: _wake_notices.persistent_warnings(copy.deepcopy(config), hub_heights=copy.deepcopy(hh_per_turb)),
                 lambda: _wake_notices.adaptation_notes(copy.deepcopy(config)),
                 lambda: _wake_presets.notes(copy.deepcopy(provenance)) if provenance else []):
        persistent += _edge_cases.guarded(edge_warning, part) or []
    for note in persistent:
        _log(note, Qgis.Warning)

    # The exception of WeightedSum with the 0 m/s node (decision 4): its plan, before simulating, with its own copies
    # (a failure preparing it is the ordinary calculation, with the configuration of always).
    zero_plan = _zero_node.plan(copy.deepcopy(config), copy.deepcopy(ws_eval))
    if zero_plan.warning is not None:
        edge_warning(zero_plan.warning)
    variant_terms = _variants.variant_configs(config)

    def calculate(attempt: Optional[_zero_node.Attempt]) -> Dict[str, Any]:
        """The main simulation, the breakdown and the directional breakdown; with ``attempt``, every simulation runs
        with the exception (``zero_node``). What it gives, with its diagnoses of the edge cases."""
        diagnoses: Dict[str, Any] = {}
        diagnosis_warnings: List[Any] = []

        def simulate(wfm: Any) -> Any:
            def one(ws: Any, operator_ws: Any = None) -> Any:
                return _simulation_runner.simulate(wfm, xs, ys, type_i=type_i if use_types else None, wd=wd_eval,
                                                   ws=ws, wt_inputs=wt_inputs, operator_ws=operator_ws)
            return one(ws_eval) if attempt is None else attempt.simulate(one)

        def diagnose(term: str, sim: Any) -> None:
            """The edge cases of one simulation (decisions 2 and 5), protected, and only once the calculation has
            read everything it reads from it: nothing the diagnosis does can change what was calculated. Its grids
            of directions are read-only copies."""
            def run() -> None:
                found = _edge_cases.simulation_diagnosis(
                    **_result_arrays.edge_case_arrays(sim, aep_hours_per_year),
                    directions=None if wd_eval is None else _edge_cases.read_only(np.array(wd_eval, dtype=float)),
                    sector_centers=None if wd_native is None else _edge_cases.read_only(np.array(wd_native, dtype=float)))
                if found is not None:
                    diagnoses[term] = found
            _edge_cases.guarded(diagnosis_warnings.append, run)

        _progress(35, "Simulación principal con PyWake…")
        wfm_main = build(config)
        executed = _wake_readers.executed_config(wfm_main, config)
        with ConvergenceRecorder() as main_recorder:
            sim_main = simulate(wfm_main)
        principal = _aep_per_turb(sim_main, hours_per_year=aep_hours_per_year)
        ti_effective = effective_ti_per_turbine(sim_main)
        # Why a turbine has no effective TI (decision 8), protected: the value kept stays None.
        ti_reasons = _edge_cases.guarded(
            diagnosis_warnings.append,
            lambda: _edge_cases.ti_reasons(*_result_arrays.ti_arrays(sim_main), None if ti_effective is None
                                           else _edge_cases.read_only(ti_effective), len(xs)))

        # ==========================================
        # 8) El desglose firmado: A_0 siempre; las variantes, si se piden
        # ==========================================
        if compute_variants:
            _progress(55, "Variantes del desglose de pérdidas…")
        sims: Dict[str, Any] = {}
        variant_recorder = ConvergenceRecorder()

        def run(target: Any) -> np.ndarray:
            wfm = build(target)
            if target is _variants.FREE_STREAM:
                sims["free"] = simulate(wfm)
                return _aep_per_turb(sims["free"], hours_per_year=aep_hours_per_year)
            with variant_recorder:
                sim = simulate(wfm)
            per_turbine = _aep_per_turb(sim, hours_per_year=aep_hours_per_year)
            diagnose(next((t for t, c in variant_terms.items() if c == target), "?"), sim)  # its last use
            return per_turbine

        aep, aep_states, term_states, errors = _variants.run_breakdown(
            config, principal, run, compute_variants=compute_variants,
            turbulence_reaches_deficit=_variants.turbulence_changes_deficit(wfm_main.wake_deficitModel))

        # --- Desglose por dirección (rosa de pérdidas por sector) ---
        aep_per_wd_wake_mwh = aep_per_wd_free_mwh = sector_directions_deg = None
        if "free" in sims:
            aep_per_wd_wake_mwh, aep_per_wd_free_mwh, sector_directions_deg = _result_arrays.extract_directional_breakdown(
                sim_main,
                sims["free"],
                log=lambda msg: _log(msg, Qgis.Info),
                sector_centers_deg=wd_native,
                hours_per_year=aep_hours_per_year,
            )
        diagnose("A_WTB", sim_main)  # after the directional breakdown, the last use of these two simulations
        if "free" in sims:
            diagnose("A_0", sims["free"])
        if attempt is not None and attempt.join_error is not None:
            raise attempt.join_error  # joining the 0 m/s slice is code of the calculation: its error, never skipped
        if attempt is not None and attempt.error is not None:
            raise _Discarded()  # a simulation of the attempt failed (also a variant): none of it counts
        return dict(executed=executed, main_recorder=main_recorder, principal=principal, ti_effective=ti_effective,
                    ti_reasons=ti_reasons,
                    aep=aep, aep_states=aep_states, term_states=term_states, errors=errors,
                    variant_recorder=variant_recorder, aep_per_wd_wake_mwh=aep_per_wd_wake_mwh,
                    aep_per_wd_free_mwh=aep_per_wd_free_mwh, sector_directions_deg=sector_directions_deg,
                    diagnoses=diagnoses, diagnosis_warnings=diagnosis_warnings,
                    auxiliary=attempt.auxiliary_summary() if attempt is not None else None)

    attempt = _zero_node.Attempt(zero_plan) if zero_plan.applies else None
    try:
        out = calculate(attempt)
    except Exception:
        if attempt is not None and attempt.join_error is not None:
            raise attempt.join_error  # also with a failed simulation: joining the slice is code of the calculation
        if attempt is None or attempt.error is None:
            raise
        # With the grid without 0 m/s PyWake fails where the whole grid may calculate: the whole calculation again,
        # with the whole grid, and said; nothing of the attempt is kept (decision 4).
        retry = attempt.retry_warning()
        _log(retry, Qgis.Warning)
        edge_warnings.append(retry)
        attempt = None
        out = calculate(None)
    for warning in out["diagnosis_warnings"]:
        _log(warning, Qgis.Warning)
    edge_warnings.extend(out["diagnosis_warnings"])
    # The texts of the diagnoses (decisions 2 and 5), protected: the warnings to every output, the cases without
    # energy only to the log.
    for term, diagnosis in out["diagnoses"].items():
        label = (log_text("Cálculo principal") if term == "A_WTB"
                 else log_text("Variantes del desglose ({term})", term=term))
        texts = _edge_cases.guarded(edge_warning, _edge_cases.diagnosis_warnings, diagnosis, label) or {}
        for warning in texts.get("warnings") or []:
            edge_warning(warning)
        for note in texts.get("notes") or []:
            _log(note, Qgis.Info)
    # Why a turbine has no effective TI (decision 8): a warning for each reason.
    for reason in _edge_cases.TI_REASON_TEXTS:
        turbines = [i for i, r in (out["ti_reasons"] or {}).items() if r == reason]
        if turbines:
            edge_warning(log_text("TI efectiva {reason} en las turbinas {turbines}: no se guarda ningún valor.",
                                  reason=log_text(_edge_cases.TI_REASON_TEXTS[reason]),
                                  turbines=", ".join(str(i) for i in sorted(turbines))))
    if attempt is not None:
        _log(attempt.note(), Qgis.Info)
        config_notes.append(attempt.note())
    executed, main_recorder, variant_recorder = out["executed"], out["main_recorder"], out["variant_recorder"]
    principal, ti_effective, aep, errors = out["principal"], out["ti_effective"], out["aep"], out["errors"]
    aep_states, term_states = out["aep_states"], out["term_states"]
    aep_per_wd_wake_mwh, aep_per_wd_free_mwh = out["aep_per_wd_wake_mwh"], out["aep_per_wd_free_mwh"]
    sector_directions_deg = out["sector_directions_deg"]
    for term, error in errors.items():
        _log(log_text("[AEP] No se pudo calcular {term}: {error}", term=term, error=error), Qgis.Warning)

    # ==========================================
    # 9) Convergencia, avisos persistentes y configuración ejecutada
    # ==========================================
    convergence = {"main": main_recorder.summary(), "variants": variant_recorder.summary()}
    if out["auxiliary"] is not None:
        convergence["auxiliary_zero"] = out["auxiliary"]
    convergence_notes = [log_text("Cálculo principal: {warning}", warning=w)
                         for w in _wake_notices.convergence_warnings(convergence["main"])]
    convergence_notes += [log_text("Variantes del desglose: {warning}", warning=w)
                          for w in _wake_notices.convergence_warnings(convergence["variants"])]
    convergence_notes += [log_text("Simulación auxiliar de 0 m/s: {warning}", warning=w)
                          for w in _wake_notices.convergence_warnings(convergence.get("auxiliary_zero") or {})]
    for note in convergence_notes:
        _log(note, Qgis.Warning)
    selection = _wake_api.user_selection(config)
    wake_config = {
        "selected": selection.to_dict(), "effective": config.to_dict(),
        "identification": _wake_config.identification(config),
        "differences_vs_signature": _wake_config.differences_vs_signature(config),
        "expected_classes": {p: (c.__name__ if c else None)
                             for p, c in _wake_factory.expected_classes(config).items()},
        "executed": executed,
        "differences_vs_selection": _wake_readers.differences_vs_selection(executed, selection),
        "adaptations": config.to_dict()["adaptations"],
        "legacy_request": legacy_request,
    }
    if provenance is not None:
        # A predefined model: its identification (its differences with the signatures are not the user's), adapted when
        # the user accepted CGIRotorAvg(7) (decision 19 of the predefined models), and where it comes from, with the
        # full configuration above.
        wake_config["identification"] = _wake_presets.identification(provenance, config)
        wake_config["provenance"] = provenance
        data = dict(preset=provenance["preset"], revision=provenance["revision"],
                    reference=provenance["reference_class"], reference_version=provenance["reference_version"],
                    executed_version=provenance["executed_version"])
        if config.adaptations:
            _log(log_text("[REPORT] Configuración adaptada a partir del modelo predefinido {preset}, revisión {revision} "
                          "({reference} de PyWake {reference_version}), calculada con PyWake {executed_version}.",
                          **data), Qgis.Info)
        else:
            _log(log_text("[REPORT] Modelo predefinido {preset}, revisión {revision}: {reference} de PyWake "
                          "{reference_version}, calculado con PyWake {executed_version}.", **data), Qgis.Info)
    _log("[REPORT] Configuración ejecutada: " + str(wake_config["identification"]), Qgis.Info)
    for line in _wake_readers.executed_lines(executed):
        _log("[REPORT]   " + line, Qgis.Info)

    # ==========================================
    # 10) Construcción del resultado final para la UI (esquema 2)
    # ==========================================
    _progress(92, "Generando tabla por aerogenerador…")
    result = _result_v2.build_result(
        models=models, xs=xs, ys=ys, use_types=use_types, type_i=type_i, skipped=skipped,
        skipped_by_model=layout["skipped_by_model"], aep=aep, aep_states=aep_states, term_states=term_states,
        errors=errors, ti_ambient=ti_per_turb, ti_effective=ti_effective, aep_per_wd_wake_mwh=aep_per_wd_wake_mwh,
        aep_per_wd_free_mwh=aep_per_wd_free_mwh, sector_directions_deg=sector_directions_deg,
        wake_config=wake_config, convergence=convergence, persistent_warnings=persistent,
        notes=config_notes + convergence_notes + edge_warnings, resource_settings=resource_record, air_density=air_density.info,
        log=lambda msg: _log(msg))
    result["ti_fallback_10pct"] = bool(
        use_wrg_resource and not ti_paths_used and fixed_ti_requested is None and fixed_ti is not None
        and abs(float(fixed_ti) - 0.10) <= 1e-9)
    # The edge cases (#63), only when there are some: an ordinary result has none of these keys.
    if attempt is not None:  # the grids executed with the exception of WeightedSum (decision 4)
        result["executed_ws"] = {"simulations_m_s": attempt.plan.ws.tolist(),
                                 "zero_node_m_s": attempt.plan.small_ws.tolist(),
                                 "bin_mean_m_s": attempt.plan.operator_ws.tolist()}
    if out["ti_reasons"]:  # the reason of each turbine without an effective TI (decision 8); its warnings, above
        result["ti_effective_reasons"] = {str(i): reason for i, reason in out["ti_reasons"].items()}
        for row in result.get("per_turbine_table") or []:
            reason = out["ti_reasons"].get(int(row.get("id", 0) or 0))
            if reason is not None:
                row["ti_effective_reason"] = _edge_cases.TI_REASON_TEXTS[reason]
    if out["diagnoses"] or edge_warnings:
        result["edge_cases"] = {"diagnoses": out["diagnoses"], "warnings": edge_warnings}
    return result


# ============================================================
# ESCRITURA A CAPAS DE PUNTOS (compatibilidad)
# ============================================================
def _ensure_fields(layer):
    """Compatibilidad: delega en ag_core.qgis_io.layers."""
    return _qgis_layers.ensure_result_fields(layer)


def push_results_to_point_layer(layer, per_turbine_table: list, tol_m: float = 30.0):
    """Compatibilidad: delega en ag_core.qgis_io.layers."""
    return _qgis_layers.push_results_to_point_layer(layer, per_turbine_table, tol_m=tol_m)


def _find_layer_by_name(name: str):
    """Compatibilidad: delega en ag_core.qgis_io.layers."""
    return _qgis_layers.find_layer_by_name(name)


def update_layers_from_results(per_turbine_table: list, models: List[Dict[str, Any]], tol_m: float = 30.0):
    """Compatibilidad: delega la escritura de resultados en capas QGIS."""
    return _qgis_layers.update_layers_from_results(
        per_turbine_table,
        models,
        tol_m=tol_m,
        log=_log,
        warning_level=Qgis.Warning,
    )

# ============================================================
# Función “todo en uno” para el botón del diálogo
# ============================================================
def compute_and_update(
    wasp_dir: str,
    models: List[Dict[str, Any]],
    *,
    wrg_paths: Optional[List[str]] = None,
    wrg_speedup_method: str = "none",
    wrg_direction_count: Optional[int] = None,
    wrg_wd_interp: str = "nearest",
    compute_variants: bool = True,
    include_turbulence: Any = NOT_SET,
    include_blockage: Any = NOT_SET,
    include_rotor_avg: Any = NOT_SET,
    fixed_ti: Optional[float] = None,
    wrg_ti_paths: Optional[List[str]] = None,
    wrg_ti_path: Optional[str] = None,
    wrg_ti_heights_m: Optional[List[Optional[float]]] = None,
    project_crs_authid: Optional[str] = None,
    wfm_engine: Any = NOT_SET,
    wake_deficit_model: Any = NOT_SET,
    wake_deficit_kwargs: Any = NOT_SET,
    blockage_deficit_model: Any = NOT_SET,
    turbulence_model: Any = NOT_SET,
    rotor_avg_model: Any = NOT_SET,
    superposition_model: Any = NOT_SET,
    wake_physics: Any = NOT_SET,
    wake_provenance: Optional[Dict[str, Any]] = None,
    wake_model: Any = NOT_SET,
    energy_ws_step: Optional[float] = None,
    air_density_mode: str = "off",
    air_density_ref_kg_m3: Optional[float] = None,
    air_density_ref_altitude_m: Optional[float] = None,
    update_project_layers: bool = True,
    tol_m: float = 30.0,
    progress_callback: Optional[Callable[[int, str], None]] = None,
) -> Dict[str, Any]:
    """
    Calcula y actualiza las capas del proyecto en un paso. La física, como en ``compute_aep_from_ui``: los campos
    que no se indican llegan como «no indicados» (``NOT_SET``), nunca con un valor por defecto propio.
    """
    res = compute_aep_from_ui(
        wake_physics=wake_physics,
        wake_provenance=wake_provenance,
        wake_model=wake_model,
        wasp_dir=wasp_dir,
        models=models,
        wrg_paths=wrg_paths,
        wrg_speedup_method=wrg_speedup_method,
        wrg_direction_count=wrg_direction_count,
        wrg_wd_interp=wrg_wd_interp,
        include_turbulence=include_turbulence,
        include_blockage=include_blockage,
        include_rotor_avg=include_rotor_avg,
        compute_variants=compute_variants,
        fixed_ti=fixed_ti,
        wrg_ti_paths=wrg_ti_paths,
        wrg_ti_path=wrg_ti_path,
        wrg_ti_heights_m=wrg_ti_heights_m,
        project_crs_authid=project_crs_authid,
        wfm_engine=wfm_engine,
        wake_deficit_model=wake_deficit_model,
        wake_deficit_kwargs=wake_deficit_kwargs,
        blockage_deficit_model=blockage_deficit_model,
        turbulence_model=turbulence_model,
        rotor_avg_model=rotor_avg_model,
        superposition_model=superposition_model,
        energy_ws_step=energy_ws_step,
        air_density_mode=air_density_mode,
        air_density_ref_kg_m3=air_density_ref_kg_m3,
        air_density_ref_altitude_m=air_density_ref_altitude_m,
        progress_callback=progress_callback,
    )
    if progress_callback is not None:
        try:
            progress_callback(96, "Volcando resultados a las capas QGIS…" if update_project_layers else "Finalizando caso de sensibilidad…")
        except Exception:  # nosec B110
            pass
    if update_project_layers:
        rows = res["per_turbine_table"]
        if res.get("wake_config"):
            # Each entity that receives the results carries the identification and the warnings of this calculation.
            texts = _qgis_export.wake_texts(res)
            rows = [dict(row, **texts) for row in rows]
        update_layers_from_results(rows, models, tol_m=tol_m)
    if progress_callback is not None:
        try:
            progress_callback(100, "Cálculo completado.")
        except Exception:  # nosec B110
            pass
    return res


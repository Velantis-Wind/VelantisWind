# -*- coding: utf-8 -*-
"""
aep_compute.py  — Cálculo AEP con carga robusta de WAsP grids (py_wake-safe) + escritura a capas QGIS

- Detecta automáticamente y prioriza la subcarpeta 'pywake_compat' si existe.
- Valida nombres con el patrón real de py_wake para evitar IndexError al cargar .grd.
- Opción de saneo: mueve a _bad_for_pywake los .grd que no casen (por defecto activado).
- Fallbacks amplios de PyWake (modelos, compatibility paths) para mayor compatibilidad.
- Calcula AEP por turbina (free/operativa) y deltas por efecto.
- Integra rotor-average Gaussian (CGIRotorAvg) con fallbacks.
- Integra bloqueo (SelfSimilarityDeficit2020) y fuerza A2A si hay bloqueo.
- Superposición compatible: WeightedSum SOLO con rotor-average por nodos; si no, LinearSum.
- Imprime por modelo: curva de potencia (muestra), altura de buje y diámetro.
- Actualiza las capas de puntos por modelo (las creadas en aep_setup_dialog) y configura Map Tips.

Uso desde el diálogo:
    from .ag_core.aep_compute import compute_and_update
    res = compute_and_update(wasp_dir, models, compute_variants=True)
"""

from __future__ import annotations
import os
import re, inspect
from typing import Dict, List, Tuple, Any, Optional, Callable

import numpy as np

try:
    from osgeo import gdal, osr
except Exception:
    gdal = None
    osr = None


# --------- Fallback: turbulencia constante para evitar AssertionError ---------
class ConstantTurbulenceModel:
    """Modelo de turbulencia mínimo: no añade turbulencia; TI_eff ~= TI_ambiente.
    Útil como compatibilidad cuando el turbulenceModel seleccionado no está disponible.
    """
    def __init__(self, ti: float = 0.10):
        try:
            self.ti = float(ti)
        except Exception:
            self.ti = 0.10

    def calc_added_turbulence(self, *args, **kwargs):
        """Devuelve turbulencia añadida cero con forma compatible si es posible."""
        # PyWake suele pasar arrays con sufijos *_ijlk. Buscamos uno para clonar la forma.
        for key in ("dw_ijlk", "cw_ijlk", "D_src_il", "D_dst_il", "x_ijlk", "y_ijlk"):
            arr = kwargs.get(key, None)
            if hasattr(arr, "shape"):
                return np.zeros_like(arr, dtype=float)
        for a in args:
            if hasattr(a, "shape"):
                return np.zeros_like(a, dtype=float)
        return 0.0

    def __call__(self, *args, **kwargs):
        return self.calc_added_turbulence(*args, **kwargs)

    def calc_effective_TI(self, *args, **kwargs):
        """Si alguien pide TI efectiva directamente, devolvemos TI ambiente o constante."""
        TI_ilk = kwargs.get("TI_ilk", kwargs.get("TI", None))
        if TI_ilk is None:
            return self.ti
        return TI_ilk
def _safe_name(obj) -> str:
    if obj is None:
        return "None"
    try:
        return obj.__class__.__name__
    except Exception:
        return str(obj)


def _safe_cls_name(obj) -> str:
    if obj is None:
        return "None"
    try:
        return getattr(obj, "__name__", str(obj))
    except Exception:
        return str(obj)


def _choice_text(value: Any, fallback: str = "None") -> str:
    try:
        txt = str(value).strip()
    except Exception:
        txt = ""
    return txt or fallback


def _build_config_snapshot(*, engine: Any, wake: Any, turbulence: Any, blockage: Any, rotor_avg: Any, superposition: Any = None) -> Dict[str, str]:
    snap = {
        "engine": _choice_text(engine),
        "wake_deficit": _choice_text(wake),
        "turbulence": _choice_text(turbulence),
        "blockage": _choice_text(blockage),
        "rotor_avg": _choice_text(rotor_avg),
    }
    if superposition is not None:
        snap["superposition"] = _choice_text(superposition)
    return snap


def _guidance_notes_for_config(*, wake_cls, turbulence_obj, use_wrg: bool, wrg_ti_paths: Optional[List[str]] = None, unique_hubs: Optional[List[float]] = None) -> List[str]:
    notes: List[str] = []
    wake_name = _safe_cls_name(wake_cls)
    turb_name = _safe_name(turbulence_obj)
    hubs = [float(h) for h in (unique_hubs or [])]
    if wake_cls is BG_DEF:
        notes.append("BastankhahGaussianDeficit usa una k fija: la TI ambiente y el modelo de turbulencia apenas cambian el déficit base del wake.")
    elif wake_cls is NOJ_DEF:
        notes.append("NOJDeficit usa una expansión top-hat constante: el modelo de turbulencia no cambia el AEP en la configuración estándar.")
    elif wake_cls in (NIA_DEF, ZG_DEF, TG_DEF, TNOJ_DEF, GCL_DEF):
        if turbulence_obj is None:
            notes.append(f"{wake_name} puede ser sensible a la TI, pero se ha ejecutado sin modelo de turbulencia añadida; la sensibilidad queda limitada a la TI ambiente disponible.")
        else:
            notes.append(f"{wake_name} puede usar la TI ambiente/efectiva para abrir la estela; el modelo de turbulencia activo ({turb_name}) sí puede influir en el AEP.")

    ti_paths = [p for p in (wrg_ti_paths or []) if p]
    if use_wrg:
        if ti_paths:
            if len(ti_paths) == 1:
                notes.append("WRG: se ha usado un único raster de TI ambiente; si mezclas varios hub heights, esa TI se replica/interpela como aproximación vertical.")
            else:
                notes.append(f"WRG: se han usado {len(ti_paths)} raster(s) de TI ambiente para reconstruir TI por altura cuando es posible.")
        else:
            notes.append("WRG: no se ha proporcionado raster TI, así que la TI ambiente se ha fijado al valor fallback definido por el usuario como campo uniforme.")
        if len(hubs) > 1 and len(ti_paths) <= 1:
            notes.append("Hay varios hub heights pero solo una TI ambiente verticalmente uniforme; el cálculo sigue siendo válido, aunque es una aproximación en altura.")
    return notes


# Tipado NumPy: usar float32 por defecto en arrays
F32 = np.float32

# ========= QGIS =========
from qgis.utils import iface
from qgis.core import (
    Qgis, QgsMessageLog,
    QgsProject, QgsVectorLayer, QgsField, QgsFeature, QgsGeometry,
    QgsWkbTypes, QgsPointXY, QgsSpatialIndex, QgsFeatureRequest, edit
)
from qgis.PyQt.QtCore import QVariant

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

# ============================================================
# Modelos PyWake físicos
# ============================================================
# Los imports/fallbacks de wake, turbulencia, bloqueo y rotor-average viven en
# ag_core.physics.*. Aquí solo se mantiene el import de WindTurbines y se
# reexportan aliases para compatibilidad con el resto del motor histórico.
from py_wake.wind_turbines._wind_turbines import WindTurbines
from py_wake.wind_turbines.power_ct_functions import PowerCtFunctionList


# ============================================================
# Arquitectura física extraída (wake / turbulencia / bloqueo / rotor-average)
# ============================================================
try:
    from .physics import wake as _physics_wake
    from .physics import blockage as _physics_blockage
    from .physics import rotor_average as _physics_rotor
    from .physics import turbulence as _physics_turbulence
except Exception:  # pragma: no cover - fallback standalone
    from ag_core.physics import wake as _physics_wake  # type: ignore
    from ag_core.physics import blockage as _physics_blockage  # type: ignore
    from ag_core.physics import rotor_average as _physics_rotor  # type: ignore
    from ag_core.physics import turbulence as _physics_turbulence  # type: ignore

try:
    from .resources import wasp as _resource_wasp
    from .resources import turbulence_grid as _resource_ti
    from .layout import io as _layout_io
    from .turbines import height as _turbine_height
    from .turbines import factory as _turbine_factory
    from .turbines import curves as _turbine_curves
    from .results import aep_arrays as _result_arrays
    from .results import tables as _result_tables
    from .results import summary as _result_summary
    from .qgis_io import layers as _qgis_layers
    from .simulation import runner as _simulation_runner
    from . import orchestration as _orchestration
except Exception:  # pragma: no cover - fallback standalone
    from ag_core.resources import wasp as _resource_wasp  # type: ignore
    from ag_core.resources import turbulence_grid as _resource_ti  # type: ignore
    from ag_core.layout import io as _layout_io  # type: ignore
    from ag_core.turbines import height as _turbine_height  # type: ignore
    from ag_core.turbines import factory as _turbine_factory  # type: ignore
    from ag_core.turbines import curves as _turbine_curves  # type: ignore
    from ag_core.results import aep_arrays as _result_arrays  # type: ignore
    from ag_core.results import tables as _result_tables  # type: ignore
    from ag_core.results import summary as _result_summary  # type: ignore
    from ag_core.qgis_io import layers as _qgis_layers  # type: ignore
    from ag_core.simulation import runner as _simulation_runner  # type: ignore
    from ag_core import orchestration as _orchestration  # type: ignore

# Usar el registry nuevo como fuente de verdad para los modelos PyWake.
PDW = _physics_wake.PDW
A2A = _physics_wake.A2A
PUD = _physics_wake.PUD
BG_DEF = _physics_wake.BG_DEF
NOJ_DEF = _physics_wake.NOJ_DEF
TNOJ_DEF = _physics_wake.TNOJ_DEF
TG_DEF = _physics_wake.TG_DEF
ZG_DEF = _physics_wake.ZG_DEF
NIA_DEF = _physics_wake.NIA_DEF
GCL_DEF = _physics_wake.GCL_DEF
WeightedSum = _physics_wake.WeightedSum
LinearSum = _physics_wake.LinearSum
SquaredSum = getattr(_physics_wake, "SquaredSum", None)
MaxSum = getattr(_physics_wake, "MaxSum", None)
NoWakeDeficit = _physics_wake.NoWakeDeficit

SS_BLOCK = _physics_blockage.SS_BLOCK
VD_BLOCK = _physics_blockage.VD_BLOCK
HI_BLOCK = _physics_blockage.HI_BLOCK
RATH_BLOCK = _physics_blockage.RATH_BLOCK
BLOCKAGE_MODEL_CLS = _physics_blockage.BLOCKAGE_MODEL_CLS

CGI_AVG = _physics_rotor.CGI_AVG
GO_AVG = _physics_rotor.GO_AVG
EQ_AVG = _physics_rotor.EQ_AVG
RC_AVG = _physics_rotor.RC_AVG
TURB_MODEL_CLS = _physics_turbulence.TURB_MODEL_CLS
ConstantTurbulenceModel = _physics_turbulence.ConstantTurbulenceModel

# ============================================================
# Utils de logging/diagnóstico
# ============================================================
def _log(msg: str, level=Qgis.Info):
    if str(os.environ.get("VELANTISWIND_DEBUG", "")).strip().lower() in {"1", "true", "yes", "on", "debug"}:
        print("[AEP] " + msg)
    try:
        QgsMessageLog.logMessage(msg, "AEP", level=level)
    except Exception:
        pass
    try:
        iface.messageBar().pushMessage("AEP", msg, level=level, duration=6)
    except Exception:
        pass


# Conectar módulos extraídos al logger/QGIS levels del motor principal.
try:
    _turbine_height.configure_logging(_log, warning_level=Qgis.Warning, info_level=Qgis.Info)
    _turbine_factory.configure_logging(_log, warning_level=Qgis.Warning, info_level=Qgis.Info)
    _turbine_curves.configure_logging(_log, warning_level=Qgis.Warning, info_level=Qgis.Info)
except Exception:
    pass

def _dump_obj_signature(tag: str, obj: Any):
    try:
        mod = getattr(obj, "__module__", "?")
        name = obj.__class__.__name__ if not inspect.isclass(obj) else obj.__name__
        try:
            sig = str(inspect.signature(obj.__init__ if not inspect.isclass(obj) else obj))
        except Exception:
            sig = "n/d"
        _log(f"[{tag}] clase={name} | módulo={mod} | firma={sig}")
        _log(f"[{tag}] repr={repr(obj)}")
    except Exception as e:
        _log(f"[{tag}] No se pudo obtener firma/repr: {e}", Qgis.Warning)


# ============================================================
# Compatibilidad: PropagateUpDownIterative requiere WS efectiva
# ============================================================
# En PyWake, PropagateUpDownIterative suele exigir que wake_deficitModel y
# blockage_deficitModel "escalen" con WS_eff. Muchos modelos lo activan con
# use_effective_ws=True. Aquí lo forzamos automáticamente cuando el motor es PUD.
_FORCE_EFFECTIVE_WS = False

def _set_force_effective_ws(enabled: bool) -> None:
    global _FORCE_EFFECTIVE_WS
    _FORCE_EFFECTIVE_WS = bool(enabled)
    try:
        _physics_wake.set_force_effective_ws(enabled)
    except Exception:
        pass

def _kw_supported(cls, kw: str) -> bool:
    """True si la clase expone el kwarg en su firma (__init__)."""
    try:
        if cls is None:
            return False
        if not inspect.isclass(cls):
            cls = cls.__class__
        sig = inspect.signature(cls.__init__)
        return kw in sig.parameters
    except Exception:
        return False

def _instantiate_with_optional_kw(cls, **preferred_kwargs):
    """Instancia cls pasando solo kwargs soportados (o devuelve instancia si ya lo es)."""
    if cls is None:
        return None
    try:
        if not inspect.isclass(cls):
            return cls
    except Exception:
        pass

    try:
        sig = inspect.signature(cls.__init__)
        params = sig.parameters
        kw = {k: v for k, v in preferred_kwargs.items() if k in params}
    except Exception:
        kw = {}

    try:
        return cls(**kw) if kw else cls()
    except Exception:
        # Último intento: sin kwargs
        try:
            return cls()
        except Exception:
            raise


def _force_ws_eff_if_needed(obj, *, context: str = "wake"):
    """Compatibilidad para PropagateUpDownIterative (PUD).

    PyWake hace un assert en PUD exigiendo que el deficit (y el bloqueo) se
    evalúen con la **velocidad efectiva** (WS_eff) y no con la free-stream.
    En muchas clases esto se activa con `use_effective_ws=True`, pero NO en
    todas las versiones/modelos (p.ej. algunas variantes de NOJ).

    Si estamos en modo PUD (_FORCE_EFFECTIVE_WS=True) y el objeto expone
    `WS_key`, lo forzamos a 'WS_eff_ilk' para evitar el assert.
    """
    if not _FORCE_EFFECTIVE_WS or obj is None:
        return obj
    try:
        ws_key = getattr(obj, "WS_key", None)
        if ws_key and ws_key != "WS_eff_ilk":
            try:
                setattr(obj, "WS_key", "WS_eff_ilk")
                _log(f"[AEP] [Compat] {context}: se fuerza WS_key='WS_eff_ilk' (modelo no expone use_effective_ws).", Qgis.Warning)
            except Exception:
                # Si es propiedad read-only o falla, no forzamos
                pass
    except Exception:
        pass
    return obj
def _resolve_engine_choice(wfm_engine: str) -> str:
    """Resuelve el motor WFM final (PDW/A2A/PUD) usando el registry físico extraído."""
    return _physics_wake.resolve_engine_choice(wfm_engine)
def _make_turbulence_model(key: Optional[str], include_turbulence: bool = True) -> Any:
    """Crea el turbulence model seleccionado usando ag_core.physics.turbulence."""
    return _physics_turbulence.make_turbulence_model(
        key,
        include_turbulence=include_turbulence,
        log=_log,
    )
def _make_rotor_avg_model(key: Optional[str]) -> Any:
    """Crea el rotor-average model seleccionado usando ag_core.physics.rotor_average."""
    return _physics_rotor.make_rotor_avg_model(key, log=_log)
def _env_diag():
    try:
        import py_wake as _pyw
        _log(f"[ENV] py_wake version = {getattr(_pyw, '__version__', '?')}")
    except Exception:
        _log("[ENV] No se pudo leer la versión de py_wake", Qgis.Warning)
    try:
        import py_wake.blockage_models as bm
        names = [n for n in dir(bm) if "Deficit" in n or "Block" in n]
        _log(f"[ENV] blockage_models(moderno) = {names if names else '[]'}")
    except Exception:
        _log("[ENV] blockage_models(moderno) no disponible", Qgis.Warning)
    try:
        import py_wake.deficit_models.selfsimilarity as s
        names = [n for n in dir(s) if "Deficit" in n or "Block" in n]
        _log(f"[ENV] selfsimilarity(clásico) = {names if names else '[]'}")
    except Exception:
        _log("[ENV] selfsimilarity(clásico) no disponible", Qgis.Warning)
    try:
        import py_wake.turbulence_models as tm
        names = [n for n in dir(tm) if any(k in n for k in ("Turbulence", "Crespo", "STF", "GCL"))]
        _log(f"[ENV] turbulence_models = {names if names else '[]'}")
    except Exception:
        _log("[ENV] py_wake.turbulence_models no disponible", Qgis.Warning)


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


def _native_wd_for_site(ds) -> Optional[np.ndarray]:
    """Return native wind-direction centres for sector-based resources.

    PyWake defaults to 360 one-degree directions when ``wd`` is omitted. For
    WAsP/WRG sector climates this linearly interpolates Weibull A/k and sector
    probabilities between sector centres, which can bias the free-flow AEP.
    Using the native WRG/WAsP sector centres evaluates the climate exactly as
    exported. A duplicated closure at 360° is removed to avoid double-counting
    the first sector.
    """
    try:
        if ds is None or "wd" not in ds.coords:
            return None
        wd = np.asarray(ds["wd"].values, dtype=float).reshape(-1)
        wd = wd[np.isfinite(wd)]
        if wd.size == 0:
            return None
        # Remove duplicated 360° closure when 0° is already present.
        if wd.size > 1 and abs(float(wd[-1]) - 360.0) < 1e-6 and np.any(np.isclose(wd[:-1], 0.0, atol=1e-6)):
            wd = wd[:-1]
        # Use native sectors only when they are coarser than 1-degree; if a site
        # already provides many directions, passing them is still harmless.
        return wd.astype(float)
    except Exception:
        return None

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


# ============================================================
# Utilidades varias
# ============================================================
def _diag_pdw(pdw_obj):
    _log(f"PropagateDownwind obj: {repr(pdw_obj)}")
    _log(f"  módulo: {getattr(pdw_obj,'__module__','?')}")
    _log(f"  es clase: {inspect.isclass(pdw_obj)} | callable: {callable(pdw_obj)}")
    try:
        _log(f"  firma __init__: {inspect.signature(pdw_obj.__init__)}")
    except Exception:
        pass



def _build_deficit_model(deficit_cls, turb_model=None, rotor_avg_model=None, block_model=None,
                         user_kwargs: Optional[Dict[str, Any]] = None):
    """Instancia el wake deficit model usando ag_core.physics.wake."""
    return _physics_wake.build_deficit_model(
        deficit_cls,
        turb_model=turb_model,
        rotor_avg_model=rotor_avg_model,
        block_model=block_model,
        user_kwargs=user_kwargs,
        force_effective_ws=_FORCE_EFFECTIVE_WS,
        log=_log,
    )
def _build_wfm(engine: str,
               site,
               windTurbines: WindTurbines,
               wake_deficitModel,
               superpositionModel,
               *,
               turbulenceModel=None,
               rotorAvgModel=None,
               blockageModel=None):
    """Crea el WindFarmModel usando ag_core.physics.wake."""
    return _physics_wake.build_wfm(
        engine,
        site,
        windTurbines,
        wake_deficitModel,
        superpositionModel,
        turbulenceModel=turbulenceModel,
        rotorAvgModel=rotorAvgModel,
        blockageModel=blockageModel,
        force_effective_ws=_FORCE_EFFECTIVE_WS,
        log=_log,
    )
def _run_sim_with_type_fallback(*args, **kwargs):
    """Compatibilidad: delega la ejecución con fallback de `type_i` en ag_core.simulation.runner.

    Mantiene las dos firmas históricas:
    - _run_sim_with_type_fallback(wfm, xs, ys, types, need_types=bool) -> (sim, used_key)
    - _run_sim_with_type_fallback(site=..., windTurbines=..., ...) -> sim
    """
    # ---- Firma antigua de compatibilidad interna ----
    if args and callable(args[0]) and len(args) >= 3 and isinstance(args[1], np.ndarray):
        wfm = args[0]
        xs = args[1]
        ys = args[2]
        types = args[3] if len(args) > 3 else None
        need_types = kwargs.get("need_types", False)
        return _simulation_runner.call_wfm_with_type_fallback(
            wfm,
            xs,
            ys,
            type_i=types,
            wd=kwargs.get("wd", None),
            need_types=need_types,
            log=_log,
            warning_level=Qgis.Warning,
        )

    # ---- Firma nueva ----
    site = kwargs["site"]
    wt = kwargs["windTurbines"]
    deficit = kwargs.get("wake_deficitModel") or kwargs.get("bg_deficitModel")
    superpos = kwargs.get("superpositionModel")
    xs = kwargs["xs"]
    ys = kwargs["ys"]
    engine = kwargs.get("engine", "auto")
    type_i = kwargs.get("type_i", None)

    return _simulation_runner.run_simulation(
        site=site,
        windTurbines=wt,
        wake_deficitModel=deficit,
        turbulenceModel=kwargs.get("turbulenceModel", None),
        rotorAvgModel=kwargs.get("rotorAvgModel", None),
        blockageModel=kwargs.get("blockageModel", None),
        superpositionModel=superpos,
        xs=xs,
        ys=ys,
        type_i=type_i,
        wd=kwargs.get("wd", None),
        engine=engine,
        build_wfm=_build_wfm,
        log=_log,
        warning_level=Qgis.Warning,
    )


def _run_sim_robust(*,
                   site,
                   windTurbines: WindTurbines,
                   deficit_cls,
                   turbulenceModel,
                   rotorAvgModel,
                   blockageModel,
                   engine: str,
                   xs: np.ndarray,
                   ys: np.ndarray,
                   type_i=None,
                   wd=None,
                   superpositionModel=None,
                   wake_deficit_kwargs: Optional[Dict[str, Any]] = None,
                   blockage_alternatives: Optional[list] = None):
    """Compatibilidad: delega la simulación robusta en ag_core.simulation.runner."""
    fallback_cls = BG_DEF if (BG_DEF is not None and deficit_cls is not BG_DEF) else None
    return _simulation_runner.run_robust_simulation(
        site=site,
        windTurbines=windTurbines,
        deficit_cls=deficit_cls,
        turbulenceModel=turbulenceModel,
        rotorAvgModel=rotorAvgModel,
        blockageModel=blockageModel,
        engine=engine,
        xs=xs,
        ys=ys,
        type_i=type_i,
        wd=wd,
        superpositionModel=superpositionModel,
        wake_deficit_kwargs=wake_deficit_kwargs,
        fallback_deficit_cls=fallback_cls,
        blockage_alternatives=blockage_alternatives,
        build_deficit_model=_build_deficit_model,
        build_wfm=_build_wfm,
        choose_superposition=_choose_superposition,
        log=_log,
        warning_level=Qgis.Warning,
    )


def _clip_hub_heights_to_site(wt_all: WindTurbines, site) -> None:
    _turbine_height.configure_logging(_log, warning_level=Qgis.Warning, info_level=Qgis.Info)
    return _turbine_height.clip_hub_heights_to_site(wt_all, site)


def _hub_heights_per_turbine(wt_all: WindTurbines, type_i, n: int) -> np.ndarray:
    return _turbine_height.hub_heights_per_turbine(wt_all, type_i, n)


def _compute_ti_per_turbine(*args,
                           ti_cap: float = 1.00,
                           default_ti: float = 0.10,
                           hh_per_turb: Optional[np.ndarray] = None) -> np.ndarray:
    return _resource_ti.compute_ti_per_turbine(
        *args, ti_cap=ti_cap, default_ti=default_ti, hh_per_turb=hh_per_turb
    )


import numpy as np

def _aep_per_turb(sim):
    """Compatibilidad: delega la extracción AEP por turbina en ag_core.results.aep_arrays."""
    return _result_arrays.aep_per_turb(sim)

def _is_node_rotor_avg_instance(rotor_mdl) -> bool:
    """True si el rotor-average es NodeRotorAvgModel (compatible con WeightedSum)."""
    return _physics_rotor.is_node_rotor_avg_instance(rotor_mdl)
def _deficit_cls_name(deficit_cls) -> str:
    """Nombre de clase para logs/heurísticas (acepta clase o instancia)."""
    return _physics_wake.deficit_cls_name(deficit_cls)
def _is_gaussian_deficit(deficit_cls) -> bool:
    """True si el wake deficit es Gaussiano (candidato a WeightedSum)."""
    return _physics_wake.is_gaussian_deficit(deficit_cls)
def _is_weightedsum_incompatible_deficit(deficit_cls) -> bool:
    """True si WeightedSum NO aplica (deficits no-Gaussian: NOJ/TurboNOJ/GCL)."""
    return _physics_wake.is_weightedsum_incompatible_deficit(deficit_cls)
def _choose_superposition(rotor_mdl, deficit_cls=None, engine: Optional[str] = None, selected: Optional[str] = "AUTO", include_blockage: bool = False):
    """Selecciona/crea el superpositionModel evitando combinaciones no soportadas."""
    return _physics_wake.make_superposition_model(selected, rotor_mdl, deficit_cls, engine, include_blockage=include_blockage, log=_log)
def compute_aep_from_ui(wasp_dir: str,
                        models: List[Dict[str, Any]],
                        wake_model: str = 'gauss',
                        wake_deficit_model: Optional[str] = None,
                        wake_deficit_kwargs: Optional[Dict[str, Any]] = None,
                        blockage_deficit_model: Optional[str] = None,
                        turbulence_model: Optional[str] = None,
                        include_turbulence: bool = True,
                        include_blockage: bool = True,
                        include_rotor_avg: bool = True,
                        rotor_avg_model: Optional[str] = None,
                        superposition_model: Optional[str] = "AUTO",
                        compute_variants: bool = False,
                        fixed_ti: Optional[float] = None,
                        wfm_engine: str = "auto",  # 'auto' | 'PDW' | 'A2A' | 'PUD'
                        wrg_paths: Optional[List[str]] = None,
                        wrg_ti_paths: Optional[List[str]] = None,
                        wrg_ti_path: Optional[str] = None,
                        wrg_ti_heights_m: Optional[List[Optional[float]]] = None,
                        project_crs_authid: Optional[str] = None,
                        progress_callback: Optional[Callable[[int, str], None]] = None,
                        ) -> Dict[str, Any]:


    def _progress(value: int, message: str) -> None:
        """Notifica el progreso al callback (si lo hay) y al log de QGIS."""
        if progress_callback is not None:
            try:
                progress_callback(int(value), str(message))
            except Exception:
                pass
        try:
            _log(f"[AEP][{value:3d}%] {message}", Qgis.Info)
        except Exception:
            pass

    _progress(2, "Inicializando cálculo…")

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
        dtype=F32,
        read_xy_csv=_read_xy_csv,
        bbox_from_site=_bbox_from_site,
    )
    xs = layout["xs"]
    ys = layout["ys"]
    type_i = layout["type_i"]
    use_types = bool(layout["use_types"])
    skipped = int(layout["skipped"])

    
    # ===========================
    # 2.4) Trazabilidad de selección del usuario
    # ===========================
    config_notes: List[str] = []
    use_wrg_resource = bool(wrg_paths)
    ti_paths_used = [p for p in ((wrg_ti_paths or []) if wrg_ti_paths is not None else ([wrg_ti_path] if wrg_ti_path else [])) if p]
    user_selected_config = _build_config_snapshot(
        engine=wfm_engine or "AUTO",
        wake=wake_deficit_model or wake_model or "BG",
        turbulence=("NONE" if not include_turbulence else (turbulence_model or "NONE")),
        blockage=("NONE" if not include_blockage else (blockage_deficit_model or "NONE")),
        rotor_avg=("NONE" if not include_rotor_avg else (rotor_avg_model or "NONE")),
        superposition=(superposition_model or "AUTO"),
    )

    # ===========================
    # 2.5 / 3) Configuración física PyWake
    # ===========================
    _progress(20, "Configurando modelos PyWake (wake / TI / bloqueo / rotor-avg)…")
    physical_config = _orchestration.build_physical_model_config(
        wake_model=wake_model,
        wake_deficit_model=wake_deficit_model,
        blockage_deficit_model=blockage_deficit_model,
        turbulence_model=turbulence_model,
        include_turbulence=include_turbulence,
        include_blockage=include_blockage,
        include_rotor_avg=include_rotor_avg,
        rotor_avg_model=rotor_avg_model,
        superposition_model=superposition_model,
        wfm_engine=wfm_engine,
        resolve_engine_choice=_resolve_engine_choice,
        set_force_effective_ws=_set_force_effective_ws,
        make_turbulence_model=_make_turbulence_model,
        make_rotor_avg_model=_make_rotor_avg_model,
        choose_superposition=_choose_superposition,
        log=_log,
        info_level=Qgis.Info,
        warning_level=Qgis.Warning,
    )

    config_notes.extend(physical_config["notes"])
    engine = physical_config["engine"]
    bg_def_cls = physical_config["wake_deficit_cls"]
    key = physical_config["wake_key"]
    wake_key_norm = physical_config["wake_key_norm"]
    turb_model = physical_config["turbulence_model"]
    block_model = physical_config["blockage_model"]
    block_model_alternatives = physical_config["blockage_alternatives"]
    rotor_avg_obj = physical_config["rotor_avg_model"]
    superpos = physical_config["superposition_model"]
    include_turbulence = bool(physical_config["include_turbulence"])
    include_blockage = bool(physical_config["include_blockage"])
    include_rotor_avg = bool(physical_config["include_rotor_avg"])
    turbulence_model = physical_config["turbulence_model_key"]
    blockage_deficit_model = physical_config["blockage_deficit_model_key"]
    rotor_avg_model = physical_config["rotor_avg_model_key"]


    # ==========================================
    # 4) Construir WindTurbines combinado
    # ==========================================
    wt, use_types_wt = _combine_wt(models)
    # El WT combinado dicta si PyWake necesita type_i.
    use_types = bool(use_types_wt)
    if not use_types:
        type_i = None

    # Forzar clipping de hub heights a rango del site (por seguridad)
    _clip_hub_heights_to_site(wt, site)
    # ===========================
    # 5) Engine WFM (ya resuelto)
    # ===========================
    _log(f"[AEP] WFM engine utilizado: {engine}", Qgis.Info)

    # ===========================
    # 6) Turbulencia inicial (TI)
    # ===========================
    if fixed_ti is not None:
        try:
            _apply_fixed_ti(site, float(fixed_ti), prefer_var="TI")
        except Exception as e:
            _log(f"[AEP] No se pudo fijar TI={fixed_ti}: {e}", Qgis.Warning)
        hh_per_turb = _hub_heights_per_turbine(wt, type_i, len(xs))
        ti_per_turb = _compute_ti_per_turbine(site, xs, ys, hh_per_turb=hh_per_turb)
    else:
        hh_per_turb = _hub_heights_per_turbine(wt, type_i, len(xs))
        ti_per_turb = _compute_ti_per_turbine(site, xs, ys, hh_per_turb=hh_per_turb)

    unique_hubs = []
    try:
        if hh_per_turb is not None:
            unique_hubs = sorted({round(float(h), 6) for h in np.asarray(hh_per_turb).reshape(-1).tolist() if h is not None})
    except Exception:
        unique_hubs = []


    # Evaluar el recurso en las direcciones nativas del WRG/WAsP. Si no se pasa
    # wd, PyWake usa 360 direcciones por defecto e interpola linealmente A/k/f
    # entre sectores; en WRG sectorial eso introduce un sesgo apreciable en AEP libre.
    wd_eval = _native_wd_for_site(ds)
    if wd_eval is not None:
        try:
            _log(f"[AEP] Usando direcciones nativas del recurso: n={len(wd_eval)} ({float(wd_eval[0]):.1f}°..{float(wd_eval[-1]):.1f}°).", Qgis.Info)
        except Exception:
            pass

    # ==========================================
    # 7) Ejecutar simulación principal AEP
    # ==========================================
    _progress(35, "Simulación principal con PyWake…")
    # Ejecutar simulación con degradación automática si PyWake no soporta la combinación elegida
    sim_main, used_def_cls, used_turb, used_rotor, used_blk, used_superpos, used_attempt_label = _run_sim_robust(
        site=site,
        windTurbines=wt,
        deficit_cls=bg_def_cls,
        turbulenceModel=turb_model,
        rotorAvgModel=rotor_avg_obj,
        blockageModel=block_model,
        superpositionModel=superpos,
        xs=xs,
        ys=ys,
        type_i=type_i if use_types else None,
        wd=wd_eval,
        engine=engine,
        wake_deficit_kwargs=wake_deficit_kwargs,
        blockage_alternatives=block_model_alternatives,
    )

    # Si hubo degradación, sincronizar los modelos usados para el resto de cálculos
    requested_def_cls = bg_def_cls
    requested_turb_model = turb_model
    requested_rotor_avg_obj = rotor_avg_obj
    requested_block_model = block_model
    requested_superpos = superpos

    bg_def_cls = used_def_cls
    turb_model = used_turb
    rotor_avg_obj = used_rotor
    block_model = used_blk
    superpos = used_superpos

    requested_config = _build_config_snapshot(
        engine=engine,
        wake=_safe_cls_name(requested_def_cls),
        turbulence=_safe_name(requested_turb_model),
        blockage=_safe_name(requested_block_model),
        rotor_avg=_safe_name(requested_rotor_avg_obj),
        superposition=type(requested_superpos).__name__,
    )
    executed_config = _build_config_snapshot(
        engine=engine,
        wake=_safe_cls_name(bg_def_cls),
        turbulence=_safe_name(turb_model),
        blockage=_safe_name(block_model),
        rotor_avg=_safe_name(rotor_avg_obj),
        superposition=type(superpos).__name__,
    )
    simulation_degraded = used_attempt_label != "seleccionado"
    if simulation_degraded:
        if used_attempt_label.startswith("bloqueo alternativo:"):
            # Sustitución de modelo de bloqueo: la simulación conserva todo lo
            # demás de la selección del usuario (wake, rotor-average,
            # turbulencia). Mejor explicar qué ha pasado en vez de hablar de
            # "degradación", que suena a algo se ha perdido.
            _alt_name = used_attempt_label.split(":", 1)[1].strip() or "alternativo"
            _user_blk = str(blockage_deficit_model or "SS2020")
            config_notes.append(
                f"Sustitución del modelo de bloqueo: la combinación seleccionada con {_user_blk} "
                f"no convergió en PyWake (la iteración entre wake TI-driven y bloqueo SS2020 "
                f"no siempre alcanza un punto fijo estable). Se ha mantenido el bloqueo usando "
                f"{_alt_name} como modelo alternativo de acoplamiento más débil con la TI efectiva. "
                f"Esto preserva la partida de pérdidas por bloqueo manteniendo intactos wake, "
                f"rotor-average y modelo de turbulencia."
            )
        else:
            config_notes.append(f"La simulación principal no pudo ejecutarse con la combinación pedida y PyWake requirió la degradación automática: {used_attempt_label}.")

    # Detectar si hemos caído al fallback TI=10% en WRG sin raster TI
    ti_fallback_10pct = bool(use_wrg_resource and not (ti_paths_used and any(ti_paths_used)))

    config_notes.extend(_guidance_notes_for_config(
        wake_cls=bg_def_cls,
        turbulence_obj=turb_model,
        use_wrg=use_wrg_resource,
        wrg_ti_paths=ti_paths_used,
        unique_hubs=unique_hubs,
    ))

    _log("[REPORT] Configuración pedida por el usuario: " + str(user_selected_config), Qgis.Info)
    _log("[REPORT] Configuración solicitada al solver: " + str(requested_config), Qgis.Info)
    _log("[REPORT] Configuración finalmente ejecutada: " + str(executed_config), Qgis.Info)

    # AEP con estelas (operativa)
    aep_wake_wt = _aep_per_turb(sim_main)
    aep_wake = float(aep_wake_wt.sum().item())

    # AEP free-stream (sin efecto wake)
    free_result = _simulation_runner.run_free_stream(
        site=site,
        windTurbines=wt,
        no_wake_deficit_cls=NoWakeDeficit,
        linear_sum_cls=LinearSum,
        fallback_superposition=superpos,
        rotorAvgModel=rotor_avg_obj,
        xs=xs,
        ys=ys,
        type_i=type_i if use_types else None,
        wd=wd_eval,
        engine=engine,
        build_deficit_model=_build_deficit_model,
        build_wfm=_build_wfm,
        aep_per_turb=_aep_per_turb,
        log=_log,
        warning_level=Qgis.Warning,
    )
    sim_free = free_result["sim_free"]
    aep_free_wt = free_result["aep_free_wt"]
    aep_free = float(free_result["aep_free"])

    # --- Desglose por dirección (rosa de pérdidas por sector) ---
    # Útil en la UI para ver qué direcciones del viento limitan más el AEP.
    aep_per_wd_wake_mwh, aep_per_wd_free_mwh, sector_directions_deg = _result_arrays.extract_directional_breakdown(
        sim_main,
        sim_free,
        log=lambda msg: _log(msg, Qgis.Info),
    )

    # ==========================================
    # 8) Simulaciones variantes (wake-only, TI, bloqueo)
    # ==========================================
    if compute_variants:
        _progress(55, "Variantes: wake-only / wake+TI / wake+bloqueo…")

    variants = _simulation_runner.run_simulation_variants(
        compute_variants=compute_variants,
        site=site,
        windTurbines=wt,
        deficit_cls=bg_def_cls,
        turbulenceModel=turb_model,
        rotorAvgModel=rotor_avg_obj,
        blockageModel=block_model,
        superpositionModel=superpos,
        xs=xs,
        ys=ys,
        type_i=type_i if use_types else None,
        wd=wd_eval,
        engine=engine,
        ti_coupled_classes=(NIA_DEF, ZG_DEF, TG_DEF, TNOJ_DEF, GCL_DEF),
        wake_deficit_kwargs=wake_deficit_kwargs,
        build_deficit_model=_build_deficit_model,
        build_wfm=_build_wfm,
        aep_per_turb=_aep_per_turb,
        log=_log,
        info_level=Qgis.Info,
        warning_level=Qgis.Warning,
    )

    ti_breakdown_disabled_for_ti_coupled = bool(variants["ti_breakdown_disabled_for_ti_coupled"])
    if variants.get("ti_coupled_note"):
        config_notes.append(str(variants["ti_coupled_note"]))

    aep_wake_only = variants["aep_wake_only"]
    aep_wake_ti = variants["aep_wake_ti"]
    aep_wake_blk_only = variants["aep_wake_blk_only"]
    aep_wake_ti_blk = variants["aep_wake_ti_blk"]

    aep_wake_only_wt = variants["aep_wake_only_wt"]
    aep_wake_ti_wt = variants["aep_wake_ti_wt"]
    aep_wake_blk_only_wt = variants["aep_wake_blk_only_wt"]
    aep_wake_ti_blk_wt = variants["aep_wake_ti_blk_wt"]

    # ==========================================
    # 9) Construcción del resultado final para la UI
    # ==========================================
    _progress(80, "Calculando desglose por modelo / cluster…")
    _progress(92, "Generando tabla por aerogenerador…")

    return _orchestration.build_energy_result_payload(
        models=models,
        xs=xs,
        ys=ys,
        skipped=skipped,
        use_types=use_types,
        type_i=type_i,
        compute_variants=compute_variants,
        aep_free=aep_free,
        aep_wake=aep_wake,
        aep_free_wt=aep_free_wt,
        aep_wake_wt=aep_wake_wt,
        aep_wake_only=aep_wake_only,
        aep_wake_ti=aep_wake_ti,
        aep_wake_blk_only=aep_wake_blk_only,
        aep_wake_ti_blk=aep_wake_ti_blk,
        aep_wake_only_wt=aep_wake_only_wt,
        aep_wake_ti_wt=aep_wake_ti_wt,
        aep_wake_blk_only_wt=aep_wake_blk_only_wt,
        aep_wake_ti_blk_wt=aep_wake_ti_blk_wt,
        ti_breakdown_disabled_for_ti_coupled=ti_breakdown_disabled_for_ti_coupled,
        ti_per_turb=ti_per_turb,
        block_model=block_model,
        turb_model=turb_model,
        rotor_avg_obj=rotor_avg_obj,
        superpos=superpos,
        bg_def_cls=bg_def_cls,
        engine=engine,
        aep_per_wd_wake_mwh=aep_per_wd_wake_mwh,
        aep_per_wd_free_mwh=aep_per_wd_free_mwh,
        sector_directions_deg=sector_directions_deg,
        user_selected_config=user_selected_config,
        requested_config=requested_config,
        executed_config=executed_config,
        simulation_degraded=simulation_degraded,
        used_attempt_label=used_attempt_label,
        config_notes=config_notes,
        ti_fallback_10pct=ti_fallback_10pct,
        log=lambda msg: _log(msg),
    )


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
    compute_variants: bool = True,
    include_turbulence: bool = True,
    include_blockage: bool = True,
    include_rotor_avg: bool = True,
    fixed_ti: Optional[float] = None,
    wrg_ti_paths: Optional[List[str]] = None,
    wrg_ti_path: Optional[str] = None,
    wrg_ti_heights_m: Optional[List[Optional[float]]] = None,
    project_crs_authid: Optional[str] = None,
    wfm_engine: str = "auto",
    wake_deficit_model: str = "BG",
    wake_deficit_kwargs: Optional[Dict[str, Any]] = None,
    blockage_deficit_model: Optional[str] = None,
    turbulence_model: Optional[str] = None,
    rotor_avg_model: Optional[str] = None,
    superposition_model: Optional[str] = "AUTO",
    tol_m: float = 30.0,
    progress_callback: Optional[Callable[[int, str], None]] = None,
) -> Dict[str, Any]:
    """
    Calcula y actualiza las capas del proyecto en un paso.
    """
    res = compute_aep_from_ui(
        wasp_dir=wasp_dir,
        models=models,
        wrg_paths=wrg_paths,
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
        progress_callback=progress_callback,
    )
    if progress_callback is not None:
        try:
            progress_callback(96, "Volcando resultados a las capas QGIS…")
        except Exception:
            pass
    update_layers_from_results(res["per_turbine_table"], models, tol_m=tol_m)
    if progress_callback is not None:
        try:
            progress_callback(100, "Cálculo completado.")
        except Exception:
            pass
    return res

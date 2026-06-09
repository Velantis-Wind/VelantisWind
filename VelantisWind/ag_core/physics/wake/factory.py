# -*- coding: utf-8 -*-
"""Factorías de wake deficit, engine WFM y superposición PyWake.

El objetivo es que `ag_core.aep_compute` deje de ser el lugar donde viven todos
los imports/version-fallbacks de PyWake. Este módulo no depende de QGIS.
"""
from __future__ import annotations

import inspect
from inspect import signature
from typing import Any, Dict, Optional

from ..common.compat import emit, force_ws_eff_if_needed, instantiate_with_optional_kw, kw_supported
from ..rotor_average import is_node_rotor_avg_instance
from ..turbulence import ConstantTurbulenceModel, make_turbulence_fallback, make_turbulence_model

PDW = A2A = PUD = None
try:
    from py_wake.wind_farm_models import PropagateDownwind as _PDW1  # type: ignore
    PDW = _PDW1
except Exception:
    pass
try:
    from py_wake.wind_farm_models import All2AllIterative as _A2A  # type: ignore
    A2A = _A2A
except Exception:
    pass
try:
    from py_wake.wind_farm_models import PropagateUpDownIterative as _PUD  # type: ignore
    PUD = _PUD
except Exception:
    pass
if PDW is None:
    try:
        import py_wake.wind_farm_models.engineering_models as eng_models
        PDW = getattr(eng_models, "PropagateDownwind", PDW)
        A2A = getattr(eng_models, "All2AllIterative", A2A)
        PUD = getattr(eng_models, "PropagateUpDownIterative", PUD)
    except Exception:
        pass

BG_DEF = NOJ_DEF = TNOJ_DEF = TG_DEF = ZG_DEF = GCL_DEF = NIA_DEF = None
try:
    from py_wake.deficit_models import BastankhahGaussianDeficit as _BGD1  # type: ignore
    BG_DEF = _BGD1
except Exception:
    pass
if BG_DEF is None:
    try:
        from py_wake.deficit_models.gaussian import BastankhahGaussian as _BGD2  # type: ignore
        BG_DEF = _BGD2
    except Exception:
        BG_DEF = None

try:
    from py_wake.deficit_models import NOJDeficit as _NOJ
    NOJ_DEF = _NOJ
except Exception:
    try:
        from py_wake.deficit_models.noj import NOJDeficit as _NOJ
        NOJ_DEF = _NOJ
    except Exception:
        NOJ_DEF = None

try:
    from py_wake.deficit_models import TurboNOJDeficit as _TNOJ
    TNOJ_DEF = _TNOJ
except Exception:
    try:
        from py_wake.deficit_models.noj import TurboNOJDeficit as _TNOJ
        TNOJ_DEF = _TNOJ
    except Exception:
        TNOJ_DEF = None

try:
    from py_wake.deficit_models import NiayifarGaussianDeficit as _NIA
    NIA_DEF = _NIA
except Exception:
    try:
        from py_wake.deficit_models.gaussian import NiayifarGaussianDeficit as _NIA
        NIA_DEF = _NIA
    except Exception:
        NIA_DEF = None

try:
    from py_wake.deficit_models import GCLDeficit as _GCL
    GCL_DEF = _GCL
except Exception:
    try:
        from py_wake.deficit_models.gcl import GCLDeficit as _GCL
        GCL_DEF = _GCL
    except Exception:
        GCL_DEF = None

try:
    from py_wake.deficit_models import TurboGaussianDeficit as _TG
    TG_DEF = _TG
except Exception:
    try:
        from py_wake.deficit_models.gaussian import TurboGaussianDeficit as _TG
        TG_DEF = _TG
    except Exception:
        TG_DEF = None

try:
    from py_wake.deficit_models import ZongGaussianDeficit as _ZG
    ZG_DEF = _ZG
except Exception:
    try:
        from py_wake.deficit_models.gaussian import ZongGaussianDeficit as _ZG
        ZG_DEF = _ZG
    except Exception:
        ZG_DEF = None

try:
    from py_wake.superposition_models import WeightedSum
except Exception:
    WeightedSum = None  # type: ignore
try:
    from py_wake.superposition_models import LinearSum
except Exception:
    LinearSum = None  # type: ignore
try:
    from py_wake.superposition_models import SquaredSum
except Exception:
    SquaredSum = None  # type: ignore
try:
    from py_wake.superposition_models import MaxSum
except Exception:
    MaxSum = None  # type: ignore
try:
    from py_wake.deficit_models.no_wake import NoWakeDeficit
except Exception:
    NoWakeDeficit = None  # type: ignore

_FORCE_EFFECTIVE_WS = False


def set_force_effective_ws(enabled: bool) -> None:
    global _FORCE_EFFECTIVE_WS
    _FORCE_EFFECTIVE_WS = bool(enabled)


def resolve_engine_choice(wfm_engine: str) -> str:
    """Resuelve el motor WFM final (PDW/A2A/PUD) según disponibilidad."""
    eng_u = (wfm_engine or "auto").strip().upper()
    mapping = {
        "AUTO": "AUTO",
        "PDW": "PDW",
        "PROPAGATEDOWNWIND": "PDW",
        "A2A": "A2A",
        "ALL2ALLITERATIVE": "A2A",
        "PUD": "PUD",
        "PROPAGATEUPDOWNITERATIVE": "PUD",
        "PROPAGATEUPDOWNITEARTIVE": "PUD",
    }
    eng_norm = mapping.get(eng_u, eng_u)
    if eng_norm == "AUTO":
        if PDW is not None:
            return "PDW"
        if A2A is not None:
            return "A2A"
        return "PUD"
    engine = eng_norm
    if engine == "PDW" and PDW is None and A2A is not None:
        engine = "A2A"
    if engine == "A2A" and A2A is None and PDW is not None:
        engine = "PDW"
    if engine == "PUD" and PUD is None:
        engine = "PDW" if PDW is not None else "A2A"
    return engine


def wake_deficit_mapping() -> Dict[str, Any]:
    return {
        "AUTO": BG_DEF,
        "GAUSS": BG_DEF,
        "GAUSSIAN": BG_DEF,
        "BG": BG_DEF,
        "BASTANKHAHGAUSSIANDEFICIT": BG_DEF,
        "BASTANKHAHGAUSSIAN": BG_DEF,
        "NIA": NIA_DEF,
        "NIAYIFAR": NIA_DEF,
        "NIAYIFARGAUSSIANDEFICIT": NIA_DEF,
        "NOJ": NOJ_DEF,
        "NOJDEFICIT": NOJ_DEF,
        "TNOJ": TNOJ_DEF,
        "TURBONOJ": TNOJ_DEF,
        "TURBONOJDEFICIT": TNOJ_DEF,
        "GCLDEFICIT": GCL_DEF,
        "GCL": GCL_DEF,
        "TG": TG_DEF,
        "TURBOGAUSSIANDEFICIT": TG_DEF,
        "ZG": ZG_DEF,
        "ZONGGAUSSIANDEFICIT": ZG_DEF,
        "NOWAKE": NoWakeDeficit,
        "NO_WAKE": NoWakeDeficit,
        "NONE": NoWakeDeficit,
        "NINGUNO": NoWakeDeficit,
    }


def resolve_wake_deficit_class(key_raw: Optional[str]) -> tuple[Any, str, str]:
    """Devuelve (clase, key_original_upper, key_norm_sin_espacios)."""
    key = str(key_raw or "gauss").strip().upper()
    key_norm = key.replace(" ", "")
    mapping = wake_deficit_mapping()
    cls = mapping.get(key, mapping.get(key_norm, None))
    if cls is None:
        cls = BG_DEF or NoWakeDeficit
    if cls is None:
        raise RuntimeError("No hay wake deficit model disponible: ni BG ni NoWakeDeficit.")
    return cls, key, key_norm


def apply_pud_wake_compat(deficit_cls: Any, engine: str, *, log=None) -> tuple[Any, Optional[str]]:
    """Compatibilidad PUD sin capar modelos en la UI.

    PropagateUpDownIterative exige que el wake deficit escale con WS_eff. Para la
    mayoría de modelos de PyWake esto se consigue instanciando el deficit con
    use_effective_ws=True (lo hace build_deficit_model cuando engine==PUD). Por
    tanto no sustituimos NOJ/TurboNOJ/TurboGaussian por BG antes de tiempo.
    Si una versión concreta de PyWake rechaza la combinación, el runner robusto
    caerá a un fallback y lo registrará en el resumen.
    """
    return deficit_cls, None


def build_deficit_model(
    deficit_cls: Any,
    turb_model: Any = None,
    rotor_avg_model: Any = None,
    block_model: Any = None,
    user_kwargs: Optional[Dict[str, Any]] = None,
    *,
    force_effective_ws: Optional[bool] = None,
    log=None,
):
    """Instancia el wake deficit model de forma conservadora."""
    if deficit_cls is None:
        raise RuntimeError("deficit_cls es None (no se pudo importar un deficit model válido).")

    force_ws = _FORCE_EFFECTIVE_WS if force_effective_ws is None else bool(force_effective_ws)

    try:
        if not inspect.isclass(deficit_cls):
            return force_ws_eff_if_needed(deficit_cls, enabled=force_ws, log=log, context="wake")
    except Exception:
        pass

    def _try_init(cls_):
        if cls_ is None:
            return None
        kwargs = {}
        if force_ws and kw_supported(cls_, "use_effective_ws"):
            kwargs["use_effective_ws"] = True
        if user_kwargs:
            applied = []
            for key, value in user_kwargs.items():
                if value is None:
                    continue
                try:
                    if kw_supported(cls_, key):
                        kwargs[key] = value
                        applied.append(f"{key}={value}")
                except Exception:
                    pass
            if applied:
                emit(log, f"[AEP] Wake deficit overrides aplicados: {', '.join(applied)}")
        try:
            obj = instantiate_with_optional_kw(cls_, **kwargs)
            return force_ws_eff_if_needed(obj, enabled=force_ws, log=log, context="wake")
        except Exception:
            return None

    name = getattr(deficit_cls, "__name__", str(deficit_cls))
    obj = _try_init(deficit_cls)
    if obj is not None:
        return obj

    emit(log, f"[AEP] No se pudo instanciar wake deficit '{name}'. Intentando fallback...")
    for fallback_cls in (BG_DEF, NoWakeDeficit):
        if fallback_cls is None or fallback_cls is deficit_cls:
            continue
        try:
            kwargs = {}
            if force_ws and kw_supported(fallback_cls, "use_effective_ws"):
                kwargs["use_effective_ws"] = True
            obj = instantiate_with_optional_kw(fallback_cls, **kwargs)
            obj = force_ws_eff_if_needed(obj, enabled=force_ws, log=log, context="wake")
            if obj is not None:
                return obj
        except Exception:
            continue
    raise RuntimeError(f"No se pudo instanciar deficit model '{name}'.")


def build_wfm(
    engine: str,
    site: Any,
    windTurbines: Any,
    wake_deficitModel: Any,
    superpositionModel: Any,
    *,
    turbulenceModel: Any = None,
    rotorAvgModel: Any = None,
    blockageModel: Any = None,
    force_effective_ws: Optional[bool] = None,
    log=None,
):
    """Crea WindFarmModel (PDW/A2A/PUD) pasando solo kwargs soportados."""
    engine_u = (engine or "auto").upper()
    if engine_u in ("AUTO", "PDW", "PROPAGATEDOWNWIND"):
        cls = PDW
    elif engine_u in ("A2A", "ALL2ALLITERATIVE"):
        cls = A2A
    elif engine_u in ("PUD", "PROPAGATEUPDOWNITERATIVE", "PROPAGATEUPDOWNITEARTIVE"):
        cls = PUD
    else:
        cls = PDW if PDW is not None else A2A

    if cls is None:
        raise RuntimeError(f"No hay motor WFM disponible para engine='{engine}' (PDW/A2A/PUD son None).")

    try:
        params = set(signature(cls.__init__).parameters.keys())
    except Exception:
        params = set()

    try:
        req = getattr(wake_deficitModel, "args4deficit", []) or []
        if turbulenceModel is None and any(arg in req for arg in ("TI_eff_ilk", "TI_eff")):
            emit(log, "[AEP] [Compat] El wake deficit requiere TI_eff: forzando turbulenceModel fallback (STF2017).")
            turbulenceModel = make_turbulence_model("STF2017", include_turbulence=True, log=log) \
                or make_turbulence_model("STF2005", include_turbulence=True, log=log) \
                or make_turbulence_model("GCL", include_turbulence=True, log=log)
            if turbulenceModel is None:
                emit(log, "[AEP] [Compat] turbulenceModel=None pero el wake deficit requiere TI_eff -> uso TI constante 0.10 (sin añadida).")
                turbulenceModel = ConstantTurbulenceModel(0.10)
    except Exception:
        pass

    candidates = [
        ("turbulenceModel", turbulenceModel),
        ("turbulence_model", turbulenceModel),
        ("turbulenceModel", turbulenceModel),
        ("rotorAvgModel", rotorAvgModel),
        ("rotor_avg_model", rotorAvgModel),
        ("rotorAvgModel", rotorAvgModel),
        ("blockage_deficitModel", blockageModel),
        ("blockage_deficit_model", blockageModel),
        ("blockageModel", blockageModel),
        ("blockage_model", blockageModel),
    ]
    kwargs = {}
    has_kwargs = any(p.kind == inspect.Parameter.VAR_KEYWORD for p in signature(cls.__init__).parameters.values()) if params else False
    for key, value in candidates:
        if value is None:
            continue
        if key in params or has_kwargs:
            kwargs[key] = value

    if blockageModel is not None:
        blockage_keys = {"blockage_deficitModel", "blockage_deficit_model", "blockageModel", "blockage_model"}
        if not any(key in kwargs for key in blockage_keys):
            emit(log, "[AEP] [Compat] Blockage seleccionado pero el WFM no acepta ningún parámetro de bloqueo (blockage_deficitModel/blockageModel). Se ignorará el bloqueo.")

    force_ws = _FORCE_EFFECTIVE_WS if force_effective_ws is None else bool(force_effective_ws)
    if cls is PUD and force_ws:
        if ("use_effective_ws" in params or has_kwargs) and "use_effective_ws" not in kwargs:
            kwargs["use_effective_ws"] = True

    try:
        return cls(site, windTurbines, wake_deficitModel, superpositionModel, **kwargs)
    except TypeError:
        return cls(
            site=site,
            windTurbines=windTurbines,
            wake_deficitModel=wake_deficitModel,
            superpositionModel=superpositionModel,
            **kwargs,
        )


def deficit_cls_name(deficit_cls: Any) -> str:
    if deficit_cls is None:
        return ""
    try:
        cls = deficit_cls if inspect.isclass(deficit_cls) else deficit_cls.__class__
    except Exception:
        cls = deficit_cls
    return getattr(cls, "__name__", str(cls))


def is_gaussian_deficit(deficit_cls: Any) -> bool:
    if deficit_cls in (BG_DEF, TG_DEF, ZG_DEF):
        return True
    name = deficit_cls_name(deficit_cls).lower()
    return ("gaussian" in name) and (not any(k in name for k in ("noj", "gcl")))


def is_weightedsum_safe_gaussian(deficit_cls: Any) -> bool:
    """True solo para deficits gaussianos donde WeightedSum está derivado de
    forma consistente.

    WeightedSum se derivó matemáticamente para BastankhahGaussianDeficit (k fijo).
    Las variantes TI-driven (TurboGaussianDeficit, ZongGaussianDeficit,
    NiayifarGaussianDeficit, BlondelSuperGaussianDeficit) ajustan k internamente
    con la TI efectiva y la combinación con WeightedSum produce errores
    numéricos o asserts en PyWake. Importante: TG/ZG/NIA HEREDAN de BG en
    PyWake, así que NO podemos usar `issubclass`/MRO ni identidad por clase
    base: hay que mirar el nombre exacto de la clase del deficit, no su
    jerarquía.
    """
    if deficit_cls is None:
        return False
    name = deficit_cls_name(deficit_cls).lower()
    # Excluir explícitamente las variantes TI-driven y super-gaussianas
    if any(k in name for k in (
        "turbo", "zong", "niayifar", "blondel", "supergaussian", "super_gaussian",
    )):
        return False
    # Solo aceptar Bastankhah clásico
    return "bastankhah" in name


def is_weightedsum_incompatible_deficit(deficit_cls: Any) -> bool:
    if deficit_cls in (NOJ_DEF, TNOJ_DEF, GCL_DEF):
        return True
    name = deficit_cls_name(deficit_cls).lower()
    return any(k in name for k in ("noj", "gcl")) and ("gaussian" not in name)


def _superposition_key(value: Optional[str]) -> str:
    u = str(value or "AUTO").strip().upper().replace(" ", "")
    mapping = {
        "AUTO": "AUTO",
        "RECOMMENDED": "AUTO",
        "LIN": "LIN",
        "LINEAR": "LIN",
        "LINEARSUM": "LIN",
        "SQR": "SQR",
        "SQUARE": "SQR",
        "SQUAREDSUM": "SQR",
        "RSS": "SQR",
        "MAX": "MAX",
        "MAXSUM": "MAX",
        "WGT": "WGT",
        "WEIGHTED": "WGT",
        "WEIGHTEDSUM": "WGT",
    }
    return mapping.get(u, "AUTO")


def make_superposition_model(
    key: Optional[str],
    rotor_mdl: Any = None,
    deficit_cls: Any = None,
    engine: Optional[str] = None,
    *,
    include_blockage: bool = False,
    log=None,
):
    """Crea el superpositionModel pedido, con degradación segura si no es compatible.

    Si ``include_blockage`` es True, se fuerza LinearSum: PyWake aplica la MISMA
    superposición al ``blockage_deficitModel``, y el bloqueo modela la zona de
    inducción, que produce *speedups* (valores < 0). ``SquaredSum`` y ``MaxSum``
    llevan asserts que prohíben valores negativos
    ("SquaredSum only works for deficit - not speedups") y ``WeightedSum`` solo
    está derivada para déficits gaussianos. La única superposición que admite
    speedups con signo es ``LinearSum``.
    """
    key_norm = _superposition_key(key)

    if include_blockage:
        if LinearSum is not None:
            if key_norm in ("AUTO", "LIN"):
                emit(log, "[Superposition] Bloqueo activo: se usa LinearSum (única superposición compatible con los speedups de la zona de inducción).")
            else:
                emit(log, f"[Superposition] Bloqueo activo: '{key_norm}' no admite los speedups de la zona de inducción (SquaredSum/MaxSum asertan valores >= 0, WeightedSum es solo gaussiana) -> se usa LinearSum.")
            return LinearSum()
        emit(log, "[Superposition] Bloqueo activo pero LinearSum no está disponible en esta instalación de PyWake; se continúa con la selección estándar (la simulación con bloqueo puede fallar).")

    if key_norm == "AUTO":
        return choose_superposition(rotor_mdl, deficit_cls, engine, selected="AUTO", include_blockage=include_blockage, log=log)

    dname = deficit_cls_name(deficit_cls)
    eng_u = (engine or "").strip().upper()

    def _fallback(reason: str):
        emit(log, f"[Superposition] {eng_u or 'WFM'}: {reason} -> usando selección automática segura.")
        return choose_superposition(rotor_mdl, deficit_cls, engine, selected="AUTO", include_blockage=include_blockage, log=log)

    try:
        if key_norm == "LIN":
            if LinearSum is not None:
                emit(log, f"[Superposition] {eng_u or 'WFM'}: usando LinearSum (selección usuario).")
                return LinearSum()
            return _fallback("LinearSum no disponible")

        if key_norm == "SQR":
            if SquaredSum is not None:
                emit(log, f"[Superposition] {eng_u or 'WFM'}: usando SquaredSum (selección usuario).")
                return SquaredSum()
            return _fallback("SquaredSum no disponible")

        if key_norm == "MAX":
            if MaxSum is not None:
                emit(log, f"[Superposition] {eng_u or 'WFM'}: usando MaxSum (selección usuario).")
                return MaxSum()
            return _fallback("MaxSum no disponible")

        if key_norm == "WGT":
            if WeightedSum is None:
                return _fallback("WeightedSum no disponible")
            if is_weightedsum_incompatible_deficit(deficit_cls) or not is_weightedsum_safe_gaussian(deficit_cls):
                return _fallback(f"WeightedSum no se aplica de forma segura al deficit '{dname or 'desconocido'}'")
            emit(log, f"[Superposition] {eng_u or 'WFM'}: usando WeightedSum (selección usuario, deficit={dname or 'gauss'}).")
            return WeightedSum()

        return _fallback(f"Clave de superposición no reconocida: {key_norm}")
    except Exception as exc:
        return _fallback(f"error creando superposición '{key_norm}': {exc}")


def choose_superposition(rotor_mdl: Any, deficit_cls: Any = None, engine: Optional[str] = None, *, selected: Optional[str] = "AUTO", include_blockage: bool = False, log=None):
    """Selecciona superpositionModel evitando combinaciones no soportadas.

    selected='AUTO' conserva la heurística histórica del plugin. Para elecciones
    explícitas usa make_superposition_model(...).

    Si ``include_blockage`` es True se fuerza LinearSum (ver
    make_superposition_model): es la única superposición que tolera los speedups
    de la zona de inducción del bloqueo.
    """
    if include_blockage and LinearSum is not None:
        emit(log, "[Superposition] Bloqueo activo: se usa LinearSum (compatible con los speedups de la zona de inducción).")
        return LinearSum()
    if _superposition_key(selected) != "AUTO":
        return make_superposition_model(selected, rotor_mdl, deficit_cls, engine, include_blockage=include_blockage, log=log)
    try:
        eng_u = (engine or "").strip().upper()
        dname = deficit_cls_name(deficit_cls)
        if LinearSum is None and WeightedSum is None and SquaredSum is None:
            raise RuntimeError("No se pudo importar ningún superposition model (LinearSum/SquaredSum/WeightedSum).")
        if is_weightedsum_incompatible_deficit(deficit_cls):
            if LinearSum is not None:
                emit(log, f"[Superposition] {eng_u or 'WFM'}: deficit '{dname or 'no-gaussian'}' no-Gaussian -> usando LinearSum (WeightedSum desactivado).")
                return LinearSum()
            if SquaredSum is not None:
                return SquaredSum()
            return WeightedSum()
        if dname and (not is_gaussian_deficit(deficit_cls)):
            if LinearSum is not None:
                emit(log, f"[Superposition] {eng_u or 'WFM'}: deficit '{dname}' no confirmado gaussiano -> usando LinearSum.")
                return LinearSum()
            if SquaredSum is not None:
                return SquaredSum()
            return WeightedSum()
        if WeightedSum is not None and is_node_rotor_avg_instance(rotor_mdl) and is_weightedsum_safe_gaussian(deficit_cls):
            emit(log, f"[Superposition] {eng_u or 'WFM'}: usando WeightedSum (auto, rotor-average NodeRotorAvgModel, deficit={dname or 'gauss'}).")
            return WeightedSum()
        if SquaredSum is not None:
            emit(log, f"[Superposition] {eng_u or 'WFM'}: usando SquaredSum (auto, opción robusta por defecto).")
            return SquaredSum()
        return LinearSum() if LinearSum is not None else WeightedSum()
    except Exception as exc:
        emit(log, f"[Superposition] Fallback por error: {exc}")
        if LinearSum is not None:
            return LinearSum()
        if SquaredSum is not None:
            return SquaredSum()
        return WeightedSum()

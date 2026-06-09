# -*- coding: utf-8 -*-
"""Ejecución de simulaciones PyWake y variantes AEP.

Este módulo no depende de QGIS. `aep_compute.py` le inyecta las factorías
concretas de PyWake, el logger y los extractores de AEP para mantener la
compatibilidad con instalaciones distintas de PyWake.
"""
from __future__ import annotations

import traceback
from typing import Any, Callable, Dict, Iterable, Optional, Tuple

import numpy as np


def _emit(log: Optional[Callable[..., None]], msg: str, level: Any = None) -> None:
    if log is None:
        return
    try:
        if level is None:
            log(msg)
        else:
            log(msg, level)
    except TypeError:
        try:
            log(msg)
        except Exception:
            pass
    except Exception:
        pass


def _sum_mwh(values: Any) -> float:
    try:
        return float(np.asarray(values, dtype=float).sum().item())
    except Exception:
        return float(values.sum().item())


def call_wfm_with_type_fallback(
    wfm: Callable[..., Any],
    xs: np.ndarray,
    ys: np.ndarray,
    type_i: Optional[np.ndarray] = None,
    *,
    wd: Optional[np.ndarray] = None,
    need_types: bool = False,
    log: Optional[Callable[..., None]] = None,
    warning_level: Any = None,
) -> Tuple[Any, str]:
    """Ejecuta un WindFarmModel evitando errores comunes con `type_i`.

    PyWake necesita `type_i` cuando existe más de un modelo de turbina, pero
    algunas configuraciones de un solo modelo fallan si se le pasa. Esta función
    conserva la lógica histórica de fallback.
    """
    xs = np.asarray(xs)
    ys = np.asarray(ys)
    call_kwargs = {"x": xs, "y": ys}
    if wd is not None:
        call_kwargs["wd"] = np.asarray(wd, dtype=float)

    if need_types:
        sim = wfm(**call_kwargs, type_i=np.asarray(type_i, dtype=int))
        _ = sim.aep().sum().item()
        _emit(log, "[sim] OK usando clave 'type_i'")
        return sim, "type_i"

    try:
        sim = wfm(**call_kwargs)
        _ = sim.aep().sum().item()
        return sim, "none"
    except Exception as exc:
        msg = str(exc).lower()
        if "type_i" in msg or "type i" in msg or "required to calculate power and ct" in msg:
            ti0 = np.zeros(xs.shape[0], dtype=int)
            sim = wfm(**call_kwargs, type_i=ti0)
            _ = sim.aep().sum().item()
            _emit(log, "[sim] Reintento con type_i=0 (fallback automático).", warning_level)
            return sim, "type_i(fallback)"
        raise


def run_simulation(
    *,
    site: Any,
    windTurbines: Any,
    wake_deficitModel: Any,
    superpositionModel: Any,
    xs: np.ndarray,
    ys: np.ndarray,
    engine: str,
    type_i: Optional[np.ndarray] = None,
    wd: Optional[np.ndarray] = None,
    turbulenceModel: Any = None,
    rotorAvgModel: Any = None,
    blockageModel: Any = None,
    build_wfm: Callable[..., Any],
    log: Optional[Callable[..., None]] = None,
    warning_level: Any = None,
) -> Any:
    """Construye el WFM y ejecuta la simulación con fallback de `type_i`."""
    wfm = build_wfm(
        engine,
        site,
        windTurbines,
        wake_deficitModel,
        superpositionModel,
        turbulenceModel=turbulenceModel,
        rotorAvgModel=rotorAvgModel,
        blockageModel=blockageModel,
    )
    need_types = type_i is not None
    sim, _ = call_wfm_with_type_fallback(
        wfm,
        xs,
        ys,
        type_i=type_i,
        wd=wd,
        need_types=need_types,
        log=log,
        warning_level=warning_level,
    )
    return sim


def run_robust_simulation(
    *,
    site: Any,
    windTurbines: Any,
    deficit_cls: Any,
    turbulenceModel: Any,
    rotorAvgModel: Any,
    blockageModel: Any,
    engine: str,
    xs: np.ndarray,
    ys: np.ndarray,
    type_i: Optional[np.ndarray] = None,
    wd: Optional[np.ndarray] = None,
    superpositionModel: Any = None,
    wake_deficit_kwargs: Optional[Dict[str, Any]] = None,
    fallback_deficit_cls: Any = None,
    blockage_alternatives: Optional[Iterable[Tuple[str, Any]]] = None,
    build_deficit_model: Callable[..., Any],
    build_wfm: Callable[..., Any],
    choose_superposition: Callable[..., Any],
    log: Optional[Callable[..., None]] = None,
    warning_level: Any = None,
) -> Tuple[Any, Any, Any, Any, Any, Any, str]:
    """Ejecuta la simulación principal aplicando degradaciones automáticas.

    Orden de degradación:
      1) Configuración seleccionada
      2) Bloqueo alternativo (VortexDipole/Rathmann) si se han proporcionado y
         el wake es TI-driven — antes de quitar el bloqueo, intentamos
         sustituir SS2020 por un modelo con acoplamiento más débil a TI_eff.
      3) Sin bloqueo
      4) Sin turbulencia
      5) Sin bloqueo y sin turbulencia
      6) Sin rotor-average
      7) Fallback de wake deficit

    Devuelve: `(sim, used_deficit_cls, used_turbulence, used_rotor,
    used_blockage, used_superposition, label)`.
    """
    attempts = []
    attempts.append(("seleccionado", deficit_cls, turbulenceModel, rotorAvgModel, blockageModel))

    # Antes de quitar el bloqueo, probamos sustituirlo por alternativas más
    # estables (típicamente VortexDipole/Rathmann frente a SelfSimilarity2020
    # cuando el wake es TI-driven). Solo se inyectan si vienen pobladas desde
    # aep_compute, que ya filtra por wake TI-driven.
    if blockageModel is not None and blockage_alternatives:
        for alt_label, alt_model in blockage_alternatives:
            if alt_model is None or alt_model is blockageModel:
                continue
            attempts.append(
                (f"bloqueo alternativo: {alt_label}", deficit_cls, turbulenceModel, rotorAvgModel, alt_model)
            )

    if blockageModel is not None:
        attempts.append(("sin bloqueo", deficit_cls, turbulenceModel, rotorAvgModel, None))
    if turbulenceModel is not None:
        attempts.append(("sin turbulencia", deficit_cls, None, rotorAvgModel, blockageModel))
    if (blockageModel is not None) and (turbulenceModel is not None):
        attempts.append(("sin bloqueo + sin turbulencia", deficit_cls, None, rotorAvgModel, None))
    if rotorAvgModel is not None:
        attempts.append(("sin rotor-average", deficit_cls, turbulenceModel, None, blockageModel))
        if blockageModel is not None:
            attempts.append(("sin rotor-average + sin bloqueo", deficit_cls, turbulenceModel, None, None))
        if turbulenceModel is not None:
            attempts.append(("sin rotor-average + sin turbulencia", deficit_cls, None, None, blockageModel))
        if (blockageModel is not None) and (turbulenceModel is not None):
            attempts.append(("sin rotor-average + sin bloqueo + sin turbulencia", deficit_cls, None, None, None))

    if fallback_deficit_cls is not None and fallback_deficit_cls is not deficit_cls:
        attempts.append(("fallback deficit -> BastankhahGaussianDeficit", fallback_deficit_cls, turbulenceModel, rotorAvgModel, blockageModel))
        attempts.append(("fallback deficit -> Bastankhah (sin extras)", fallback_deficit_cls, None, None, None))

    last_exc: Optional[BaseException] = None
    for label, dcls, tmdl, rmdl, bmdl in attempts:
        try:
            kwargs_for_deficit = wake_deficit_kwargs if dcls is deficit_cls else None
            deficit_obj = build_deficit_model(dcls, user_kwargs=kwargs_for_deficit)
            # Bug-fix: si el intento ha degradado el rotor-average o el wake
            # deficit respecto al original, la superposición externa puede
            # haber dejado de ser válida (p.ej. WeightedSum solo es seguro con
            # NodeRotorAvgModel + Bastankhah clásico). En esos casos recalculamos
            # con choose_superposition para evitar arrastrar la combinación
            # rota a través de todos los intentos y terminar cayendo al
            # fallback deficit -> Bastankhah por la razón equivocada.
            rotor_avg_changed = rmdl is not rotorAvgModel
            deficit_changed = dcls is not deficit_cls
            # El bloqueo de este intento determina si la superposición debe poder
            # admitir speedups (LinearSum). Si recalculamos, pasamos el estado de
            # bloqueo del intento actual para no recaer en SquaredSum/MaxSum cuando
            # el intento conserva el bloqueo.
            blockage_active = bmdl is not None
            if superpositionModel is not None and not (rotor_avg_changed or deficit_changed):
                sp = superpositionModel
            else:
                sp = choose_superposition(rmdl, dcls, engine, include_blockage=blockage_active)
            sim = run_simulation(
                site=site,
                windTurbines=windTurbines,
                wake_deficitModel=deficit_obj,
                turbulenceModel=tmdl,
                rotorAvgModel=rmdl,
                blockageModel=bmdl,
                superpositionModel=sp,
                xs=xs,
                ys=ys,
                type_i=type_i,
                wd=wd,
                engine=engine,
                build_wfm=build_wfm,
                log=log,
                warning_level=warning_level,
            )
            _ = sim.aep().sum().item()
            if label != "seleccionado":
                _emit(log, f"[SIM] La simulación requirió degradación: {label}", warning_level)
            return sim, dcls, tmdl, rmdl, bmdl, sp, label
        except Exception as exc:
            last_exc = exc
            _emit(log, f"[SIM] Falló intento '{label}': {repr(exc)}", warning_level)
            try:
                _emit(log, traceback.format_exc(), warning_level)
            except Exception:
                pass
            continue

    raise RuntimeError(
        "No se pudo ejecutar la simulación con los modelos seleccionados. "
        f"Último error: {repr(last_exc)}"
    )


def run_free_stream(
    *,
    site: Any,
    windTurbines: Any,
    no_wake_deficit_cls: Any,
    linear_sum_cls: Any,
    fallback_superposition: Any,
    rotorAvgModel: Any,
    xs: np.ndarray,
    ys: np.ndarray,
    type_i: Optional[np.ndarray],
    wd: Optional[np.ndarray],
    engine: str,
    build_deficit_model: Callable[..., Any],
    build_wfm: Callable[..., Any],
    aep_per_turb: Callable[[Any], Any],
    log: Optional[Callable[..., None]] = None,
    warning_level: Any = None,
) -> Dict[str, Any]:
    """Ejecuta el caso free-stream sin wake/bloqueo/TI añadida."""
    linear_sum = linear_sum_cls() if linear_sum_cls is not None else fallback_superposition
    sim_free = run_simulation(
        site=site,
        windTurbines=windTurbines,
        wake_deficitModel=build_deficit_model(no_wake_deficit_cls),
        turbulenceModel=None,
        rotorAvgModel=rotorAvgModel,
        blockageModel=None,
        superpositionModel=linear_sum,
        xs=xs,
        ys=ys,
        type_i=type_i,
        wd=wd,
        engine=engine,
        build_wfm=build_wfm,
        log=log,
        warning_level=warning_level,
    )
    aep_free_wt = aep_per_turb(sim_free)
    return {
        "sim_free": sim_free,
        "aep_free_wt": aep_free_wt,
        "aep_free": _sum_mwh(aep_free_wt),
    }


def is_ti_coupled_deficit(deficit_cls: Any, ti_coupled_classes: Iterable[Any]) -> bool:
    """True para wake deficits donde la TI forma parte del propio wake."""
    return bool(deficit_cls in tuple(c for c in ti_coupled_classes if c is not None))


def run_simulation_variants(
    *,
    compute_variants: bool,
    site: Any,
    windTurbines: Any,
    deficit_cls: Any,
    turbulenceModel: Any,
    rotorAvgModel: Any,
    blockageModel: Any,
    superpositionModel: Any,
    xs: np.ndarray,
    ys: np.ndarray,
    type_i: Optional[np.ndarray],
    wd: Optional[np.ndarray],
    engine: str,
    ti_coupled_classes: Iterable[Any],
    wake_deficit_kwargs: Optional[Dict[str, Any]],
    build_deficit_model: Callable[..., Any],
    build_wfm: Callable[..., Any],
    aep_per_turb: Callable[[Any], Any],
    log: Optional[Callable[..., None]] = None,
    info_level: Any = None,
    warning_level: Any = None,
) -> Dict[str, Any]:
    """Ejecuta variantes auxiliares para desglosar wake/TI/bloqueo.

    Devuelve siempre las mismas claves, con `None` cuando no proceda o cuando
    `compute_variants=False`.
    """
    result: Dict[str, Any] = {
        "ti_breakdown_disabled_for_ti_coupled": False,
        "ti_coupled_note": None,
        "aep_wake_only": None,
        "aep_wake_ti": None,
        "aep_wake_blk_only": None,
        "aep_wake_ti_blk": None,
        "aep_wake_only_wt": None,
        "aep_wake_ti_wt": None,
        "aep_wake_blk_only_wt": None,
        "aep_wake_ti_blk_wt": None,
    }
    if not compute_variants:
        return result

    ti_coupled = is_ti_coupled_deficit(deficit_cls, ti_coupled_classes)
    result["ti_breakdown_disabled_for_ti_coupled"] = False
    if ti_coupled:
        note = (
            f"Para {getattr(deficit_cls, '__name__', str(deficit_cls))}, el desglose de turbulencia se interpreta como "
            "TI ambiente only frente a TI ambiente + turbulencia añadida por estela. "
            "No se ejecuta un caso 'sin TI', porque el Site de PyWake necesita una TI ambiente física."
        )
        result["ti_coupled_note"] = note
        _emit(log, f"[AEP] [REPORT] {note}", info_level)

    def _merged_wake_kwargs(extra: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        merged = dict(wake_deficit_kwargs or {})
        if extra:
            merged.update({k: v for k, v in extra.items() if v is not None})
        return merged

    def _sim_variant(*, tmdl: Any, bmdl: Any, ambient_ti_only: bool = False):
        # En modelos TI-driven, use_effective_ti=False mantiene la TI ambiente
        # del Site, pero evita que la turbulencia añadida por estela modifique
        # internamente el wake deficit. build_deficit_model ignora el kw si la
        # clase PyWake de la instalación no lo soporta.
        extra = {"use_effective_ti": False} if ambient_ti_only else None
        return run_simulation(
            site=site,
            windTurbines=windTurbines,
            wake_deficitModel=build_deficit_model(
                deficit_cls,
                turb_model=turbulenceModel,
                rotor_avg_model=rotorAvgModel,
                block_model=blockageModel,
                user_kwargs=_merged_wake_kwargs(extra),
            ),
            turbulenceModel=tmdl,
            rotorAvgModel=rotorAvgModel,
            blockageModel=bmdl,
            superpositionModel=superpositionModel,
            xs=xs,
            ys=ys,
            type_i=type_i,
            wd=wd,
            engine=engine,
            build_wfm=build_wfm,
            log=log,
            warning_level=warning_level,
        )

    try:
        sim_wake_only = _sim_variant(tmdl=None, bmdl=None, ambient_ti_only=ti_coupled)
        result["aep_wake_only_wt"] = aep_per_turb(sim_wake_only)
        result["aep_wake_only"] = _sum_mwh(result["aep_wake_only_wt"])
    except Exception as exc:
        result["ti_breakdown_disabled_for_ti_coupled"] = bool(ti_coupled)
        note = (
            "No se pudo calcular la variante TI ambiente only para el modelo TI-driven; "
            f"se mantiene el AEP principal. Error: {repr(exc)}"
        )
        result["ti_coupled_note"] = note
        _emit(log, f"[AEP] [REPORT] {note}", warning_level)

    if turbulenceModel is not None:
        sim_wake_ti = _sim_variant(tmdl=turbulenceModel, bmdl=None, ambient_ti_only=False)
        result["aep_wake_ti_wt"] = aep_per_turb(sim_wake_ti)
        result["aep_wake_ti"] = _sum_mwh(result["aep_wake_ti_wt"])

    if blockageModel is not None:
        sim_wake_blk = _sim_variant(tmdl=None, bmdl=blockageModel, ambient_ti_only=ti_coupled)
        result["aep_wake_blk_only_wt"] = aep_per_turb(sim_wake_blk)
        result["aep_wake_blk_only"] = _sum_mwh(result["aep_wake_blk_only_wt"])

    if (turbulenceModel is not None) and (blockageModel is not None):
        sim_wake_ti_blk = _sim_variant(tmdl=turbulenceModel, bmdl=blockageModel, ambient_ti_only=False)
        result["aep_wake_ti_blk_wt"] = aep_per_turb(sim_wake_ti_blk)
        result["aep_wake_ti_blk"] = _sum_mwh(result["aep_wake_ti_blk_wt"])

    return result

# -*- coding: utf-8 -*-
"""Physical model configuration helpers for the Energy/AEP module.

This module centralises the PyWake physical configuration selected in the UI:
engine, wake deficit, added-turbulence model, blockage/induction model,
rotor-average model and superposition model.

It intentionally avoids importing QGIS. The caller injects the logger and level
objects so the behaviour stays identical inside QGIS while the logic remains
unit-testable outside the GUI.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

try:  # package import
    from ..physics import wake as _physics_wake
    from ..physics import blockage as _physics_blockage
except Exception:  # pragma: no cover - standalone fallback
    from ag_core.physics import wake as _physics_wake  # type: ignore
    from ag_core.physics import blockage as _physics_blockage  # type: ignore


BG_DEF = _physics_wake.BG_DEF
NOJ_DEF = _physics_wake.NOJ_DEF
TNOJ_DEF = _physics_wake.TNOJ_DEF
TG_DEF = _physics_wake.TG_DEF
ZG_DEF = _physics_wake.ZG_DEF
NIA_DEF = _physics_wake.NIA_DEF
GCL_DEF = _physics_wake.GCL_DEF


def _norm_key(value: Optional[str]) -> str:
    return str(value or "").strip().upper().replace(" ", "")


def build_physical_model_config(
    *,
    wake_model: str,
    wake_deficit_model: Optional[str],
    blockage_deficit_model: Optional[str],
    turbulence_model: Optional[str],
    include_turbulence: bool,
    include_blockage: bool,
    include_rotor_avg: bool,
    rotor_avg_model: Optional[str],
    superposition_model: Optional[str],
    wfm_engine: str,
    resolve_engine_choice,
    set_force_effective_ws,
    make_turbulence_model,
    make_rotor_avg_model,
    choose_superposition,
    log,
    info_level: Any,
    warning_level: Any,
) -> Dict[str, Any]:
    """Build the selected PyWake physical configuration.

    The returned dictionary mirrors the local variables previously created
    inline inside ``compute_aep_from_ui``. The goal is architectural cleanup, not
    a numerical change.
    """
    config_notes: List[str] = []

    # 1) Resolve WFM engine first: PUD requires wake/blockage models evaluated
    # against effective wind speed.
    engine = resolve_engine_choice(wfm_engine)
    force_effective_ws = str(engine).upper() == "PUD"
    set_force_effective_ws(force_effective_ws)
    if force_effective_ws:
        log(
            "[AEP] [Compat] PropagateUpDownIterative: se fuerza use_effective_ws=True "
            "(wake/bloqueo) si el modelo lo soporta.",
            info_level,
        )

    # PropagateDownwind does not support blockage. Disable it before creating
    # the blockage model, preserving the old warning and user-facing note.
    if str(engine).upper() == "PDW" and include_blockage:
        include_blockage = False
        blockage_deficit_model = None
        log("[AEP] PropagateDownwind no calcula bloqueo: se desactiva el bloqueo automáticamente.", warning_level)
        config_notes.append(
            "Has seleccionado PropagateDownwind: PyWake no calcula bloqueo con este engine "
            "y el plugin lo ha desactivado automáticamente."
        )

    # 2) Wake deficit model. New UI selector has priority; older wake_model is
    # kept for backwards compatibility.
    key_raw = wake_deficit_model or wake_model or "gauss"
    bg_def_cls, key, wake_key_norm = _physics_wake.resolve_wake_deficit_class(key_raw)

    bg_def_cls, pud_note = _physics_wake.apply_pud_wake_compat(bg_def_cls, engine, log=log)
    if pud_note:
        config_notes.append(pud_note)
        wake_key_norm = "BG"
        key = "BG"

    name = getattr(bg_def_cls, "__name__", str(bg_def_cls))
    log(f"[AEP] Wake deficit model (seleccionado): {name}", info_level)

    if include_turbulence and (bg_def_cls is NOJ_DEF):
        log(
            "[AEP] [Nota] Con NOJDeficit el modelo de turbulencia no afecta al AEP "
            "(TI no se usa en NOJ por defecto). Si necesitas sensibilidad a TI, usa "
            "TurboNOJDeficit o un modelo gaussiano sensible a TI (p.ej., Niayifar/Zong/TurboGaussian).",
            info_level,
        )
    elif bg_def_cls is NIA_DEF:
        log(
            "[AEP] [Nota] NiayifarGaussianDeficit es un modelo gaussiano sensible a TI: "
            "combina mejor con una TI ambiente representativa y, si procede, con un turbulenceModel activo.",
            info_level,
        )
    elif bg_def_cls is TNOJ_DEF:
        log(
            "[AEP] [Nota] TurboNOJDeficit puede aprovechar mejor la TI que NOJDeficit y suele "
            "ser una opción ligera cuando se busca sensibilidad a turbulencia.",
            info_level,
        )

    # ZongGaussianDeficit requires added turbulence.
    if bg_def_cls is ZG_DEF:
        tm_u = _norm_key(turbulence_model)
        if (not include_turbulence) or (tm_u in ("", "NONE", "NINGUNO", "NO", "OFF")):
            log("[AEP] [Compat] ZongGaussianDeficit requiere turbulencia: forzando STF2017.", warning_level)
            config_notes.append("ZongGaussianDeficit requiere un modelo de turbulencia añadida; se ha forzado STF2017.")
            include_turbulence = True
            turbulence_model = "STF2017"

    # 3) Added turbulence model and fallback.
    turb_model = make_turbulence_model(turbulence_model, include_turbulence=include_turbulence)
    if include_turbulence and turb_model is None:
        tm_u = _norm_key(turbulence_model)
        if tm_u not in ("", "NONE", "NINGUNO", "NO", "OFF"):
            log(
                "[AEP] [Compat] No se pudo crear el turbulence model seleccionado; probando fallback STF2017.",
                warning_level,
            )
            config_notes.append(
                "No se pudo instanciar el modelo de turbulencia seleccionado; el plugin ha intentado "
                "un fallback seguro (STF2017/STF2005/GCL)."
            )
            turb_model = (
                make_turbulence_model("STF2017", include_turbulence=True)
                or make_turbulence_model("STF2005", include_turbulence=True)
                or make_turbulence_model("GCL", include_turbulence=True)
                or None
            )

    # 4) Blockage/induction model and robust alternatives for difficult
    # TI-driven combinations.
    block_model = _physics_blockage.make_blockage_model(
        blockage_deficit_model or "SS2020",
        include_blockage=include_blockage,
        force_effective_ws=force_effective_ws,
        log=log,
    )

    block_model_alternatives: List[Any] = []
    ti_driven_classes = (NIA_DEF, ZG_DEF, TG_DEF, TNOJ_DEF, GCL_DEF)
    user_block_key = _norm_key(blockage_deficit_model or "SS2020")
    if include_blockage and block_model is not None and bg_def_cls in tuple(c for c in ti_driven_classes if c is not None):
        alt_keys = []
        if user_block_key not in ("VD", "VORTEXDIPOLE"):
            alt_keys.append(("VortexDipole", "VD"))
        if user_block_key not in ("RATH", "RATHMANN"):
            alt_keys.append(("Rathmann", "RATH"))

        for alt_label, alt_key in alt_keys:
            alt_obj = _physics_blockage.make_blockage_model(
                alt_key,
                include_blockage=True,
                force_effective_ws=force_effective_ws,
                log=log,
            )
            if alt_obj is not None:
                block_model_alternatives.append((alt_label, alt_obj))

        if block_model_alternatives:
            log(
                "[AEP] Bloqueo: preparadas {n} alternativa(s) para degradación robusta ({alts}). "
                "Se intentará el bloqueo seleccionado primero; si PyWake no converge, se probarán "
                "las alternativas antes de quitar el bloqueo por completo.".format(
                    n=len(block_model_alternatives),
                    alts=", ".join(label for label, _ in block_model_alternatives),
                ),
                info_level,
            )

    # 5) Rotor-average model. GaussianOverlapAvgModel stays hidden in this experimental release;
    # old settings are redirected to CGIRotorAvg(7), as before.
    if include_rotor_avg:
        try:
            rotor_k = _norm_key(rotor_avg_model)
            if rotor_k in ("GO", "GAUSSIANOVERLAPAVGMODEL"):
                log(
                    "[AEP] GaussianOverlapAvgModel no se expone en esta versión experimental. Forzando rotor-average=CGIRotorAvg(7).",
                    warning_level,
                )
                config_notes.append("GaussianOverlapAvgModel se ha sustituido por CGIRotorAvg(7) por compatibilidad.")
                rotor_avg_model = "CGI7"
        except Exception:
            pass

    rotor_avg_obj = None
    if include_rotor_avg:
        try:
            rotor_avg_obj = make_rotor_avg_model(rotor_avg_model)
            if rotor_avg_obj is not None:
                log(f"[AEP] Rotor-average model (seleccionado): {rotor_avg_obj.__class__.__name__}", info_level)
            else:
                log("[AEP] Rotor-average model: None (sin rotor-average)", info_level)
        except Exception as exc:
            log(f"[AEP] Error creando rotor-average (seleccionado): {exc}", warning_level)
            rotor_avg_obj = None

    # 6) Superposition model. With blockage active, LinearSum is forced by the
    # lower-level selector because PyWake applies the same superposition to
    # blockage speedups.
    superpos = choose_superposition(
        rotor_avg_obj,
        bg_def_cls,
        engine,
        selected=superposition_model or "AUTO",
        include_blockage=bool(include_blockage and block_model is not None),
    )
    if include_blockage and block_model is not None:
        sel_supe = _norm_key(superposition_model or "AUTO")
        if sel_supe not in ("LIN", "LINEAR", "LINEARSUM", "AUTO", "RECOMMENDED"):
            config_notes.append(
                "Con bloqueo activo se ha usado LinearSum como superposición: PyWake aplica la misma "
                "superposición a la zona de inducción del bloqueo, que produce aceleraciones (speedups, "
                "valores negativos) que SquaredSum/MaxSum rechazan. LinearSum es la única superposición "
                "compatible con bloqueo, por lo que tu selección se ha redirigido para conservar el bloqueo."
            )

    return {
        "engine": engine,
        "force_effective_ws": force_effective_ws,
        "wake_deficit_cls": bg_def_cls,
        "wake_key": key,
        "wake_key_norm": wake_key_norm,
        "turbulence_model": turb_model,
        "blockage_model": block_model,
        "blockage_alternatives": block_model_alternatives,
        "rotor_avg_model": rotor_avg_obj,
        "superposition_model": superpos,
        "include_turbulence": include_turbulence,
        "include_blockage": include_blockage,
        "include_rotor_avg": include_rotor_avg,
        "turbulence_model_key": turbulence_model,
        "blockage_deficit_model_key": blockage_deficit_model,
        "rotor_avg_model_key": rotor_avg_model,
        "notes": config_notes,
    }

# -*- coding: utf-8 -*-
"""Factoría de modelos de bloqueo/inducción PyWake."""
from __future__ import annotations

from typing import Any, Optional

from ..common.compat import emit, force_ws_eff_if_needed, instantiate_with_optional_kw, kw_supported, try_import_cls

SS_BLOCK = SS_OLD_BLOCK = VC_BLOCK = VD_BLOCK = HI_BLOCK = RATH_BLOCK = None

for mod, cls in [
    ("py_wake.blockage_models.selfsimilarity", "SelfSimilarityDeficit2020"),
    ("py_wake.blockage_models", "SelfSimilarityDeficit2020"),
    ("py_wake.blockage_models.selfsimilarity", "SelfSimilarityDeficit"),
    ("py_wake.blockage_models", "SelfSimilarityDeficit"),
    ("py_wake.deficit_models.selfsimilarity", "SelfSimilarityDeficit2020"),
    ("py_wake.deficit_models.selfsimilarity", "SelfSimilarityDeficit"),
]:
    if SS_BLOCK is None:
        SS_BLOCK = try_import_cls(mod, cls)

for mod, cls in [
    ("py_wake.blockage_models.vortexcylinder", "VortexCylinder"),
    ("py_wake.blockage_models.vortex_cylinder", "VortexCylinder"),
    ("py_wake.blockage_models", "VortexCylinder"),
    ("py_wake.deficit_models.vortexcylinder", "VortexCylinder"),
    ("py_wake.deficit_models.vortex_cylinder", "VortexCylinder"),
]:
    if VC_BLOCK is None:
        VC_BLOCK = try_import_cls(mod, cls)

for mod, cls in [
    ("py_wake.blockage_models.vortexdipole", "VortexDipole"),
    ("py_wake.blockage_models.vortex_dipole", "VortexDipole"),
    ("py_wake.blockage_models", "VortexDipole"),
    ("py_wake.deficit_models.vortexdipole", "VortexDipole"),
    ("py_wake.deficit_models.vortex_dipole", "VortexDipole"),
]:
    if VD_BLOCK is None:
        VD_BLOCK = try_import_cls(mod, cls)

for mod, cls in [
    ("py_wake.blockage_models.hybridinduction", "HybridInduction"),
    ("py_wake.blockage_models.hybrid_induction", "HybridInduction"),
    ("py_wake.blockage_models", "HybridInduction"),
    ("py_wake.deficit_models.hybridinduction", "HybridInduction"),
    ("py_wake.deficit_models.hybrid_induction", "HybridInduction"),
]:
    if HI_BLOCK is None:
        HI_BLOCK = try_import_cls(mod, cls)

for mod, cls in [
    ("py_wake.blockage_models.rathmann", "Rathmann"),
    ("py_wake.blockage_models", "Rathmann"),
    ("py_wake.deficit_models.rathmann", "Rathmann"),
]:
    if RATH_BLOCK is None:
        RATH_BLOCK = try_import_cls(mod, cls)

BLOCKAGE_MODEL_CLS = SS_BLOCK


def resolve_blockage_class(key_raw: Optional[str]):
    key = str(key_raw or "SS2020").strip().upper().replace(" ", "")
    mapping = {
        "NONE": None,
        "NINGUNO": None,
        "NO": None,
        "OFF": None,
        "SS2020": SS_BLOCK,
        "SELFSIMILARITYDEFICIT2020": SS_BLOCK,
        "SS": SS_BLOCK,
        "SELFSIMILARITYDEFICIT": SS_BLOCK,
        "SELF": SS_BLOCK,
        "VC": VC_BLOCK,
        "VORTEXCYLINDER": VC_BLOCK,
        "VD": VD_BLOCK,
        "VORTEXDIPOLE": VD_BLOCK,
        "HI": HI_BLOCK,
        "HYBRIDINDUCTION": HI_BLOCK,
        "RATH": RATH_BLOCK,
        "RATHMANN": RATH_BLOCK,
    }
    return key, mapping.get(key, mapping.get(key.replace("_", ""), None))


def make_blockage_model(
    key_raw: Optional[str],
    *,
    include_blockage: bool = True,
    force_effective_ws: bool = False,
    log=None,
) -> Any:
    """Crea el blockage model seleccionado o None."""
    if not include_blockage:
        return None

    key, cls = resolve_blockage_class(key_raw)
    if cls is None and key in ("NONE", "NINGUNO", "NO", "OFF"):
        emit(log, "[AEP] Blockage model: None (sin bloqueo)")
        return None
    if cls is None:
        emit(log, f"[AEP] Blockage model '{key_raw}' no disponible en esta instalación de PyWake. Intentando fallback a SelfSimilarityDeficit2020...")
        cls = SS_BLOCK
    if cls is None:
        return None

    try:
        kwargs = {}
        if force_effective_ws and kw_supported(cls, "use_effective_ws"):
            kwargs["use_effective_ws"] = True
        obj = instantiate_with_optional_kw(cls, **kwargs)
        obj = force_ws_eff_if_needed(obj, enabled=force_effective_ws, log=log, context="blockage")
        emit(log, f"[AEP] Blockage model (seleccionado): {obj.__class__.__name__}")
        return obj
    except Exception as exc:
        emit(log, f"[AEP] Error creando modelo de bloqueo '{getattr(cls, '__name__', str(cls))}': {exc}")
        return None

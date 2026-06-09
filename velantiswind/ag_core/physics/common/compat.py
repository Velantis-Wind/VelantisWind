# -*- coding: utf-8 -*-
"""Compatibilidad compartida para factorías PyWake.

Este módulo no depende de QGIS y se puede importar desde tests unitarios o desde
el motor AEP. Centraliza introspección robusta de clases PyWake, cuyas firmas y
rutas cambian entre versiones.
"""
from __future__ import annotations

import inspect
from typing import Any, Callable, Optional

Logger = Optional[Callable[..., None]]


def emit(log: Logger, msg: str, level: Any = None) -> None:
    """Llama a un logger compatible con `_log(msg, level)` o `_log(msg)`."""
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


def try_import_cls(mod: str, cls: str):
    """Importa una clase por ruta devolviendo None si no existe."""
    try:
        module = __import__(mod, fromlist=[cls])
        return getattr(module, cls, None)
    except Exception:
        return None


def kw_supported(cls: Any, kw: str) -> bool:
    """True si la clase/instancia expone `kw` en la firma de `__init__`."""
    try:
        if cls is None:
            return False
        if not inspect.isclass(cls):
            cls = cls.__class__
        sig = inspect.signature(cls.__init__)
        return kw in sig.parameters
    except Exception:
        return False


def instantiate_with_optional_kw(cls: Any, **preferred_kwargs: Any):
    """Instancia pasando solo kwargs soportados. Si ya es instancia, la devuelve."""
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
        kwargs = {k: v for k, v in preferred_kwargs.items() if k in params}
    except Exception:
        kwargs = {}

    try:
        return cls(**kwargs) if kwargs else cls()
    except Exception:
        try:
            return cls()
        except Exception:
            raise


def force_ws_eff_if_needed(obj: Any, *, enabled: bool, log: Logger = None, context: str = "wake"):
    """Fuerza WS_key='WS_eff_ilk' cuando PUD lo exige y el modelo lo permite."""
    if not enabled or obj is None:
        return obj
    try:
        ws_key = getattr(obj, "WS_key", None)
        if ws_key and ws_key != "WS_eff_ilk":
            try:
                setattr(obj, "WS_key", "WS_eff_ilk")
                emit(log, f"[AEP] [Compat] {context}: se fuerza WS_key='WS_eff_ilk' (modelo no expone use_effective_ws).")
            except Exception:
                pass
    except Exception:
        pass
    return obj

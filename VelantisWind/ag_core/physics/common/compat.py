# -*- coding: utf-8 -*-
"""The logger helper shared by the resource and turbine modules (QGIS-free).

The factories of the previous wake physics, and their introspection of PyWake classes, were retired with #46: the
classes are built by ``ag_core/wake_setup/factory.py``.
"""
from __future__ import annotations

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
        except Exception:  # nosec B110
            pass
    except Exception:  # nosec B110
        pass

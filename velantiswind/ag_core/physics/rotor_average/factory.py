# -*- coding: utf-8 -*-
"""Factoría de rotor-average PyWake."""
from __future__ import annotations

from inspect import signature
from typing import Any, Optional

from ..common.compat import emit

CGI_AVG = EQ_AVG = RC_AVG = GO_AVG = None
try:
    from py_wake.rotor_avg_models import CGIRotorAvg as _CGI
    CGI_AVG = _CGI
except Exception:
    CGI_AVG = None
try:
    from py_wake.rotor_avg_models import EqGridRotorAvg as _EQ
    EQ_AVG = _EQ
except Exception:
    EQ_AVG = None
try:
    from py_wake.rotor_avg_models import RotorCenter as _RC
    RC_AVG = _RC
except Exception:
    RC_AVG = None

try:
    from py_wake.rotor_avg_models.rotor_avg_model import NodeRotorAvgModel as _NodeRotorAvgModel  # type: ignore
except Exception:
    try:
        from py_wake.rotor_avg_models import NodeRotorAvgModel as _NodeRotorAvgModel  # type: ignore
    except Exception:
        _NodeRotorAvgModel = None  # type: ignore


def make_rotor_avg_model(key: Optional[str], *, log=None) -> Any:
    """Crea el rotor-average model seleccionado.

    key puede ser: 'NONE'|'CGI7'|'CGI9'|'CGI21'|'EQ'|'RC'|'AUTO'
    o nombres de clase. Devuelve una instancia o None.
    """
    raw = (key or "AUTO").strip()
    normalized = raw.upper().replace(" ", "").replace("-", "")
    mapping = {
        "NONE": "NONE",
        "NINGUNO": "NONE",
        "NOWAKE": "NONE",
        "NO": "NONE",
        "AUTO": "AUTO",
        "CGI": "CGI7",
        "CGI4": "CGI7",
        "CGI7": "CGI7",
        "CGI9": "CGI9",
        "CGI21": "CGI21",
        "CGIROTORAVG": "CGI7",
        "CGIROTORAVG(7)": "CGI7",
        "CGIROTORAVG(9)": "CGI9",
        "CGIROTORAVG(21)": "CGI21",
        # GaussianOverlapAvgModel is intentionally not exposed in the experimental release UI.
        # If old settings contain it, fall back to CGIRotorAvg(7).
        "GAUSSIANOVERLAPAVGMODEL": "CGI7",
        "GO": "CGI7",
        "EQGRIDROTORAVG": "EQ",
        "EQ": "EQ",
        "ROTORCENTER": "RC",
        "RC": "RC",
    }
    key_norm = mapping.get(normalized, normalized)
    if key_norm == "NONE":
        return None
    if key_norm == "AUTO":
        if CGI_AVG is not None:
            key_norm = "CGI7"
        elif RC_AVG is not None:
            key_norm = "RC"
        elif EQ_AVG is not None:
            key_norm = "EQ"
        else:
            return None

    cgi_points = {"CGI7": 7, "CGI9": 9, "CGI21": 21}
    if key_norm in cgi_points:
        cls = CGI_AVG
        n_points = cgi_points[key_norm]
    else:
        cls = {"EQ": EQ_AVG, "RC": RC_AVG}.get(key_norm)
        n_points = None
    if cls is None:
        return None

    try:
        sig = signature(cls)
        params = list(sig.parameters.values())
        if len(params) <= 0:
            return cls()
        if n_points is not None:
            for try_kwargs in ({"n": n_points}, {"n_points": n_points}, {"n": n_points, "n_points": n_points}):
                try:
                    kwargs = {p: v for p, v in try_kwargs.items() if p in sig.parameters}
                    if kwargs:
                        return cls(**kwargs)
                except Exception:
                    pass
            try:
                return cls(n_points)
            except Exception:
                return cls()
        try:
            return cls()
        except Exception:
            return cls
    except Exception:
        try:
            if n_points is not None:
                return cls(n_points)
            return cls()
        except Exception:
            try:
                return cls()
            except Exception as exc:
                emit(log, f"[AEP] Error creando rotor-average '{getattr(cls, '__name__', str(cls))}': {exc}")
                return None


def is_node_rotor_avg_instance(rotor_mdl: Any) -> bool:
    """True si el rotor-average es NodeRotorAvgModel compatible con WeightedSum."""
    if rotor_mdl is None:
        return False
    if _NodeRotorAvgModel is not None:
        try:
            return isinstance(rotor_mdl, _NodeRotorAvgModel)
        except Exception:
            pass
    name = rotor_mdl.__class__.__name__.lower()
    return any(k in name for k in ("eqgrid", "rotorgrid", "cgi"))

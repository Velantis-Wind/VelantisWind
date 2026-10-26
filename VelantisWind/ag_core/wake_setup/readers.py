# -*- coding: utf-8 -*-
"""What was executed, read from the built PyWake objects (decision 15d; P0, section 7).

For each position, the class of the object in the built model and, for each
argument of its class signature, its value as the object keeps it («observado»)
through a per-class adapter, or, when the object does not keep it, the value
that was passed to its constructor («argumento pasado»); a submodel, by its
class (the deficit's rotor and ground and the blockage superposition are
positions of their own, and so are the components of the engine). An attribute that
cannot be read raises ``ReaderError`` (``factory.ReaderError``), never a guess.
With ``deficit_ws_reference`` (TurbOPark, M4 of the predefined models), the deficit
keeps ``WS_key = 'WS_jlk'`` instead of the key of ``use_effective_ws``: then, and
only then, the state observed is recorded (``WS_key`` of the deficit) and
``use_effective_ws`` as the argument passed.
The result is a plain dictionary for the result, the report, the exports and
the JSON of the wake raster.
"""
from __future__ import annotations

import inspect
from typing import Any, Dict, List, Optional

from .catalog import (BLOCKAGE, BLOCKAGE_SUPERPOSITION, DEFICIT, ENGINE, GROUND, ROTOR, SUPERPOSITION, TURBULENCE,
                      position_label)
from .config import Component, WakeConfig, plain_value, same_value
from .factory import WS_KEYS, ReaderError

__all__ = ["OBSERVED", "PASSED", "executed_config", "executed_lines", "differences_vs_selection",
           "executed_ws_reference", "WS_REFERENCE_TEXT"]

# The reference of the deficit's scaling in the log, the report and the view (with its key, WS_jlk, in the detail).
WS_REFERENCE_TEXT = {"destination_free_stream": "velocidad libre de la turbina de destino"}

OBSERVED = "observed"
PASSED = "passed"

_KEY_BOOL = {"use_effective_ws": ("WS_key", "WS_eff_ilk", "WS_ilk"), "use_effective_ti": ("TI_key", "TI_eff_ilk", "TI_ilk")}
# The arguments PyWake does not keep in an observable form (P0, section 7): registered as «argumento pasado» (the
# n of EqGridRotorAvg, checked against its nodes). Every other argument of the offered classes is observable, and an
# object without it is a reading error.
PASSED_ONLY = {("EqGridRotorAvg", "n")}
# The arguments that are positions of their own, read there, and the deprecated ``rotorAvgModel`` of the engines,
# which the factory never passes (the rotor is the deficit's).
_OWN_POSITIONS = {
    ENGINE: ("wake_deficitModel", "superpositionModel", "blockage_deficitModel", "turbulenceModel", "rotorAvgModel"),
    DEFICIT: ("rotorAvgModel", "groundModel"), BLOCKAGE: ("superpositionModel",),
}


def _signature(cls: type) -> Dict[str, Any]:
    """The arguments of the signature of ``cls`` that have a default, with it."""
    return {k: p.default for k, p in inspect.signature(cls.__init__).parameters.items()
            if p.default is not p.empty and p.kind in (p.POSITIONAL_OR_KEYWORD, p.KEYWORD_ONLY)}


def _plain(value: Any) -> Any:
    """``plain_value``, with a submodel (an object of PyWake) as its class name."""
    if isinstance(value, (list, tuple)):
        return [_plain(v) for v in value]
    if hasattr(value, "__dict__") and not inspect.isfunction(value):
        return type(value).__name__
    return plain_value(value)


def _read_argument(obj: Any, cls_name: str, name: str) -> Any:
    """The value of the argument ``name`` as ``obj`` keeps it; ``KeyError`` if the object does not have it."""
    d = obj.__dict__
    if name in _KEY_BOOL:
        attr, true, false = _KEY_BOOL[name]
        value = d[attr]
        if value == true:
            return True
        if value == false:
            return False
        raise ReaderError(name, f"{cls_name}.{attr} = {value!r}")
    if cls_name == "NOJDeficit" and name == "k":
        a = d["a"]
        if len(a) != 2 or a[0] != 0:
            raise ReaderError(name, f"NOJDeficit.a = {a!r}")
        return plain_value(a[1])
    if cls_name == "CGIRotorAvg" and name == "n":
        return int(len(d["nodes_x"]))
    if name == "weight_function" and cls_name in ("STF2005TurbulenceModel", "STF2017TurbulenceModel"):
        return d["apply_weight"].__self__
    if cls_name == "IECWeight" and name == "distance_limit":
        return _plain(d["dist_limit"])
    if cls_name == "MultiMirror" and name == "mirror_height":
        return _plain(d["h_mirrors"][1])  # the upper mirror (ground_models.py:87)
    for attr in (name, "_" + name):
        if attr in d:
            return d[attr] if _is_object(d[attr]) else _plain(d[attr])
    raise KeyError(name)


def _eqgrid_nodes(n: int) -> int:
    """How many nodes ``EqGridRotorAvg(n)`` keeps (rotor_avg_model.py:83-88: the points of an n × n grid with
    X² + Y² < 1), counted row by row with the same operations, without building the grid (n² values)."""
    import numpy as np
    x = np.linspace(-1, 1, n + 2)[1:-1]
    x2 = x ** 2
    return int(sum(int(((x2 + yi) < 1).sum()) for yi in x2))


def _is_object(value: Any) -> bool:
    """A PyWake object kept as an argument (a nested component), not a value."""
    return hasattr(value, "__dict__") and not inspect.isfunction(value) and not inspect.ismethod(value)


def _component(position: str, obj: Any, comp: Optional[Component], path: str = "",
               passed_only: tuple = ()) -> Optional[Dict[str, Any]]:
    """``{class, params: {name: {value, source}}}`` of one position, or of a nested component (``path``, its route
    from the position), recursively: a nested component is ``{"value": {class, params, …}, "source": "observed"}``;
    ``None`` for an absent component."""
    if obj is None:
        return None
    name = type(obj).__name__
    passed = comp.params if comp is not None and comp.name == name else {}
    params: Dict[str, Dict[str, Any]] = {}
    where = f"{path}{name}"
    for arg, default in _signature(type(obj)).items():
        if not path and arg in _OWN_POSITIONS.get(position, ()):
            continue
        if (name, arg) in PASSED_ONLY or arg in passed_only:
            params[arg] = {"value": _plain(passed.get(arg, default)), "source": PASSED}
            continue
        try:
            value = _read_argument(obj, name, arg)
            if _is_object(value):
                inner = passed.get(arg) if isinstance(passed.get(arg), Component) else None
                value = _component(position, value, inner, f"{where}.{arg} · ")
            params[arg] = {"value": value, "source": OBSERVED}
        except ReaderError as exc:
            if exc.position == position and exc.diagnosis.startswith(where):
                raise
            raise ReaderError(position, f"{where}.{arg}: {exc.diagnosis}") from exc
        except Exception as exc:
            raise ReaderError(position, f"{where}.{arg}: {type(exc).__name__}: {exc}") from exc
    out: Dict[str, Any] = {"class": name, "params": params}
    if name in ("EqGridRotorAvg", "CGIRotorAvg"):
        try:
            out["nodes"] = int(len(obj.__dict__["nodes_x"]))
        except Exception as exc:
            raise ReaderError(position, f"{name}.nodes_x: {type(exc).__name__}: {exc}") from exc
        n = params.get("n", {}).get("value")
        if name == "EqGridRotorAvg" and isinstance(n, int) and not isinstance(n, bool):
            # The n passed is not kept: its nodes are those of the n asked for, or the object is not the one passed.
            expected = _eqgrid_nodes(n)
            if out["nodes"] != expected:
                raise ReaderError(position, f"{where}: {out['nodes']} nodos, no los {expected} de n = {n}")
    return out


def executed_config(wfm: Any, config: WakeConfig) -> Dict[str, Any]:
    """The configuration as executed: each position read from the objects of ``wfm`` (see the module docstring)."""
    try:
        d = wfm.__dict__
        deficit = d["wake_deficitModel"]
        blockage = d["blockage_deficitModel"]
        objects = {
            ENGINE: wfm, DEFICIT: deficit, ROTOR: deficit.__dict__["rotorAvgModel"],
            GROUND: deficit.__dict__["groundModel"], SUPERPOSITION: d["superpositionModel"],
            TURBULENCE: d["turbulenceModel"], BLOCKAGE: blockage,
            BLOCKAGE_SUPERPOSITION: blockage.__dict__["superpositionModel"] if blockage is not None else None,
        }
    except Exception as exc:
        raise ReaderError(ENGINE, f"{type(exc).__name__}: {exc}") from exc
    out: Dict[str, Any] = {}
    for position, obj in objects.items():
        if position == DEFICIT and config.deficit_ws_reference is not None:
            # The key the deficit keeps, observed; use_effective_ws, which it no longer reflects, as passed.
            out[position] = _component(position, obj, config.component(position), passed_only=("use_effective_ws",))
            try:
                out[position]["WS_key"] = obj.__dict__["WS_key"]
            except Exception as exc:
                raise ReaderError(DEFICIT, f"{type(obj).__name__}.WS_key: {type(exc).__name__}: {exc}") from exc
        else:
            out[position] = _component(position, obj, config.component(position))
    return out


def executed_ws_reference(executed: Dict[str, Any]) -> Optional[str]:
    """The reference of the deficit's scaling that was executed (``None``: that of its class)."""
    key = (executed.get(DEFICIT) or {}).get("WS_key")
    return next((r for r, k in WS_KEYS.items() if k == key), None)


def executed_lines(executed: Dict[str, Any]) -> List[str]:
    """What was executed, one line per position with every argument, for the log (in Spanish, as the log is)."""
    out: List[str] = []
    for position, ex in executed.items():
        if ex is None:
            out.append(f"{position_label(position)}: ninguno")
            continue
        out.append(f"{position_label(position)}: {_executed_text(ex)}")
    return out


def _executed_text(ex: Dict[str, Any]) -> str:
    """``Clase (arg=valor, arg=Anidada (…) [argumento pasado]); nodos: n`` of an executed component, recursively."""
    args = []
    for k, v in ex["params"].items():
        value = _executed_text(v["value"]) if isinstance(v["value"], dict) else v["value"]
        args.append(f"{k}={value}" + (" [argumento pasado]" if v["source"] == PASSED else ""))
    text = ex["class"] + (f" ({', '.join(args)})" if args else "")
    if "WS_key" in ex:
        reference = next((r for r, k in WS_KEYS.items() if k == ex["WS_key"]), None)
        text += f"; referencia del escalado: {WS_REFERENCE_TEXT.get(reference, '?')} (WS_key = {ex['WS_key']})"
    return text + (f"; nodos: {ex['nodes']}" if "nodes" in ex else "")


def differences_vs_selection(executed: Dict[str, Any], selected: WakeConfig) -> List[Dict[str, Any]]:
    """Every class or argument of what was executed that is not what the user selected (the report highlights them).

    An accepted adaptation (decision 10) appears here too, as a difference with the selection.
    """
    out: List[Dict[str, Any]] = []
    for position, comp in ((p, selected.component(p)) for p in executed):
        ex = executed[position]
        sel_name = comp.name if comp is not None else None
        ex_name = ex["class"] if ex is not None else None
        if position == ENGINE:
            sel_name = selected.engine.name
        if sel_name != ex_name:
            out.append({"position": position, "param": None, "selected": sel_name, "executed": ex_name})
            continue
        if comp is not None:
            out += _argument_differences(position, comp, ex, "")
    executed_reference = executed_ws_reference(executed)
    if executed_reference != selected.deficit_ws_reference:
        out.append({"position": DEFICIT, "param": "deficit_ws_reference", "selected": selected.deficit_ws_reference,
                    "executed": executed_reference})
    return out


def _picked(arg: str, value: Any) -> Any:
    """The key PyWake picks with a value of ``use_effective_ws``/``use_effective_ti`` (−2 picks the one of False)."""
    _attr, true, false = _KEY_BOOL[arg]
    try:
        return (false, true)[value]
    except (TypeError, IndexError):
        return value


def _argument_differences(position: str, comp: Component, ex: Dict[str, Any], path: str) -> List[Dict[str, Any]]:
    """The arguments of a selected component whose executed value differs, recursively (``param``: their route)."""
    out: List[Dict[str, Any]] = []
    for arg, value in comp.params.items():
        got = ex["params"].get(arg)
        executed = got["value"] if got else None
        if isinstance(value, Component) and isinstance(executed, dict):
            if executed.get("class") != value.name:
                out.append({"position": position, "param": path + arg, "selected": value.name,
                            "executed": executed.get("class")})
            else:
                out += _argument_differences(position, value, executed, f"{path}{arg} · ")
        elif isinstance(value, Component) or isinstance(executed, dict):
            out.append({"position": position, "param": path + arg, "selected": plain_value(value),
                        "executed": executed.get("class") if isinstance(executed, dict) else executed})
        elif got is not None and arg in _KEY_BOOL and _picked(arg, value) == _picked(arg, executed):
            continue  # the key PyWake picks with it, ['WS_ilk', 'WS_eff_ilk'][value] (deficit_model.py:20-21)
        elif got is None or not same_value(executed, plain_value(value)):
            out.append({"position": position, "param": path + arg, "selected": plain_value(value),
                        "executed": executed})
    return out

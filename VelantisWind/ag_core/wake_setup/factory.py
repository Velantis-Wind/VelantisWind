# -*- coding: utf-8 -*-
"""Exact construction of the PyWake wind farm model of a ``WakeConfig``, and the class check before simulating.

Every component is a new object built with exactly the validated class and
arguments: the arguments are never filtered by name, a constructor that fails
raises ``FactoryError`` with its cause and nothing else is tried, there is no
table of equivalences and no global state (decision 15b). The engine receives
the wake deficit (with its rotor average and ground model as arguments of the
deficit, never the deprecated ``rotorAvgModel`` of the engine), the wake
superposition, the turbulence model and, in the engines that have it, the
blockage model with its own superposition.

A configuration with ``deficit_ws_reference`` (TurbOPark) gets its deficit
with ``WS_key = 'WS_jlk'`` before the engine is built (the engine reads the
deficit's arguments when it is built: set later, PyWake fails when simulating),
and ``check_ws_reference`` checks it before the first simulation.

``expected_classes`` fixes, from the catalogue and the configuration only,
the exact class of the seven checked positions (engine, deficit, wake
superposition, turbulence, blockage, rotor and ground of the deficit; ``None``
for an absent component). ``check_classes`` compares them with the objects of
the built model before the first simulation (decision 15c): a different class,
also a component that disappeared or appeared, raises ``ClassMismatch``; a
component that cannot be read raises ``ReaderError``. The expectation is never
derived from what is observed, and subclasses do not pass.
"""
from __future__ import annotations

import copy
import inspect
from typing import Any, Dict, Optional

from . import catalog as _cat
from . import subordinates as _sub
from .catalog import (BLOCKAGE, BLOCKAGE_SUPERPOSITION, DEFICIT, ENGINE, GROUND, ROTOR, SUPERPOSITION, TURBULENCE)
from .config import DESTINATION_FREE_STREAM, Component, WakeConfig
from ..log_text import log_text
from ..turbines.bin_power import BIN_MEAN, simulation_wind_turbines

__all__ = [
    "FactoryError", "ClassMismatch", "ReaderError", "CHECKED_POSITIONS", "catalogue_entry", "component_class",
    "build_component",
    "build_deficit", "build_blockage", "build_wind_farm_model", "expected_classes", "observed_classes",
    "check_classes", "build_free_stream_model", "free_stream_expected_classes", "check_ws_reference", "WS_KEYS",
]

# The ``WS_key`` of the deficit for each reference of its scaling (``config.DEFICIT_WS_REFERENCES``): the free wind
# speed at the turbine the wake reaches (deficit_model.py:66-74; literature/turbopark.py:37).
WS_KEYS = {DESTINATION_FREE_STREAM: "WS_jlk"}

# The seven positions of the class check (decision 15c).
CHECKED_POSITIONS = (ENGINE, DEFICIT, SUPERPOSITION, TURBULENCE, BLOCKAGE, ROTOR, GROUND)


class FactoryError(RuntimeError):
    """A PyWake constructor failed: its position, the class and the cause. No substitute was built."""

    def __init__(self, position: str, name: str, cause: BaseException):
        super().__init__(log_text("PyWake no pudo construir {cls} ({position}): {error}", cls=name,
                                  position=_cat.position_label(position),
                                  error=f"{type(cause).__name__}: {cause}"))
        self.position, self.name, self.cause = position, name, cause


class ClassMismatch(RuntimeError):
    """The built model has, at one position, another class than the expected one. Nothing was simulated."""

    def __init__(self, position: str, expected: Optional[str], observed: Optional[str]):
        super().__init__(log_text(
            "Comprobación de clases: en {position} se esperaba {expected} y el modelo construido tiene {observed}; "
            "no se ha simulado.", position=_cat.position_label(position), expected=expected or log_text("ninguno"),
            observed=observed or log_text("ninguno")))
        self.position, self.expected, self.observed = position, expected, observed


class ReaderError(RuntimeError):
    """A component of the built model could not be read (distinct from a mismatch). Nothing was simulated."""

    def __init__(self, position: str, diagnosis: str):
        super().__init__(log_text(
            "Comprobación de clases: no se pudo leer {position} del modelo construido: {diagnosis}; no se ha simulado.",
            position=_cat.position_label(position), diagnosis=diagnosis))
        self.position, self.diagnosis = position, diagnosis


def catalogue_entry(position: str, comp: Component) -> _cat.ClassEntry:
    """The catalogue option of a configured component; ``KeyError`` if it is not one."""
    return _cat.entry(position, comp.name, _fixed(position, comp))


def component_class(position: str, comp: Component) -> type:
    """The exact class of a configured component (its catalogue option must exist)."""
    return _cat.resolve_class(catalogue_entry(position, comp))


def _fixed(position: str, comp: Component) -> Dict[str, Any]:
    """The arguments of ``comp`` that identify its catalogue option (``n`` of ``CGIRotorAvg``)."""
    names = {k for e in _cat.entries(position) if e.name == comp.name for k in e.fixed}
    return {k: v for k, v in comp.params.items() if k in names}


def _value(name: str, value: Any, position: str = "") -> Any:
    """The argument PyWake receives: the ``ct2a`` function for its name, a new object for a nested component
    (``subordinates``, #64), a copy otherwise."""
    if name == "ct2a" and value is not None:
        return _cat.resolve_ct2a(value)
    if isinstance(value, Component):
        return _nested(position, value)
    return copy.deepcopy(value)


def _nested(position: str, comp: Component) -> Any:
    """A new object of a nested component (a sum of the ground, the weight of STF, a rotor or ground of a turbulence
    or a blockage), with its own arguments, recursively."""
    try:
        cls = _sub.resolve_name(comp.name)
    except Exception as exc:
        raise FactoryError(position, comp.name, exc) from exc
    return _construct(position, cls, {k: _value(k, v, position) for k, v in comp.params.items()})


# The objects a class builds inside itself from PyWake's own signatures when they are not passed (HybridInduction:
# a SelfSimilarityDeficit2020 and a VortexDipole, hybridinduction.py:43-44), which share those signatures' arrays.
_BUILT_INSIDE = {"HybridInduction": ("near_rotor", "far_field")}


def _construct(position: str, cls: type, kwargs: Dict[str, Any]) -> Any:
    """``cls(**kwargs)``, with a copy of each default of the signature that is an object and is not passed.

    Python evaluates those defaults once (the ``rotorAvgModel`` of ``CrespoHernandez``, the ``c`` list of the STF
    models): without the copy two models would share them, and the objects of PyWake's signatures too. The objects
    the class builds inside itself (``_BUILT_INSIDE``) are copied after building, for the same reason.
    """
    kwargs = dict(kwargs)
    for name, p in inspect.signature(cls.__init__).parameters.items():
        if name in kwargs or p.default is p.empty or p.kind not in (p.POSITIONAL_OR_KEYWORD, p.KEYWORD_ONLY):
            continue
        value = copy.deepcopy(p.default)
        if value is not p.default:
            kwargs[name] = value
    try:
        obj = cls(**kwargs)
    except Exception as exc:
        raise FactoryError(position, cls.__name__, exc) from exc
    for name in _BUILT_INSIDE.get(cls.__name__, ()):
        if name not in kwargs:
            setattr(obj, name, copy.deepcopy(getattr(obj, name)))
    return obj


def build_component(position: str, comp: Optional[Component]) -> Any:
    """A new object of a rotor, ground, superposition or turbulence component, or ``None`` for its absence."""
    if comp is None:
        return None
    cls = component_class(position, comp)
    return _construct(position, cls, {k: _value(k, v, position) for k, v in comp.params.items()})


def build_deficit(config: WakeConfig, **overrides: Any) -> Any:
    """The wake deficit with its arguments, its rotor average and its ground model, all new objects.

    ``overrides`` replaces arguments by name (the variants of the loss breakdown declare them, P3); an argument
    the class does not have makes PyWake fail, never ignored.
    """
    kwargs = {k: _value(k, v, DEFICIT) for k, v in config.deficit.params.items()}
    kwargs["rotorAvgModel"] = build_component(ROTOR, config.rotor)
    kwargs["groundModel"] = build_component(GROUND, config.ground)
    kwargs.update(overrides)
    deficit = _construct(DEFICIT, component_class(DEFICIT, config.deficit), kwargs)
    if config.deficit_ws_reference is not None:  # before the engine is built (see the module docstring)
        deficit.WS_key = WS_KEYS[config.deficit_ws_reference]
    return deficit


def build_blockage(config: WakeConfig) -> Any:
    """The blockage model with its arguments and its own superposition, or ``None`` without blockage."""
    if config.blockage is None:
        return None
    kwargs = {k: _value(k, v, BLOCKAGE) for k, v in config.blockage.params.items()}
    kwargs["superpositionModel"] = build_component(BLOCKAGE_SUPERPOSITION, config.blockage_superposition)
    return _construct(BLOCKAGE, component_class(BLOCKAGE, config.blockage), kwargs)


def build_wind_farm_model(config: WakeConfig, site: Any, windTurbines: Any, *, ws_grid: Any = None,
                          power_bin_mode: str = BIN_MEAN, deficit_overrides: Optional[Dict[str, Any]] = None) -> Any:
    """The engine of ``config`` with new objects in every position (see the module docstring).

    The power of each wind-speed bin is the mean of the curve over the bin of ``ws_grid`` (or of the site's grid),
    as in every simulation of the plugin (``turbines/bin_power.py``).
    """
    if ws_grid is None:
        ws_grid = getattr(site, "default_ws", None)
    turbines = simulation_wind_turbines(windTurbines, ws_grid, power_bin_mode)
    kwargs = {k: _value(k, v, ENGINE) for k, v in config.engine.params.items()}  # its own arguments (#64)
    kwargs.update({
        "wake_deficitModel": build_deficit(config, **(deficit_overrides or {})),
        "superpositionModel": build_component(SUPERPOSITION, config.superposition),
        "turbulenceModel": build_component(TURBULENCE, config.turbulence),
    })
    blockage = build_blockage(config)
    if blockage is not None:
        kwargs["blockage_deficitModel"] = blockage
    return _construct(ENGINE, component_class(ENGINE, config.engine), dict(site=site, windTurbines=turbines, **kwargs))


def _no_wake_class() -> type:
    import importlib
    return importlib.import_module("py_wake.deficit_models.no_wake").__dict__["NoWakeDeficit"]


def build_free_stream_model(config: WakeConfig, site: Any, windTurbines: Any, *, ws_grid: Any = None,
                            power_bin_mode: str = BIN_MEAN) -> Any:
    """A_0 of the loss breakdown: the engine of ``config`` with ``NoWakeDeficit``, ``LinearSum`` and no rotor
    average, ground model, turbulence nor blockage, the same arguments of the engine and the same turbines and
    bin-mean power. An internal configuration, outside the catalogue (PropagateUpDownIterative accepts it, ``engineering_models.py:540``)."""
    if ws_grid is None:
        ws_grid = getattr(site, "default_ws", None)
    turbines = simulation_wind_turbines(windTurbines, ws_grid, power_bin_mode)
    deficit = _construct(DEFICIT, _no_wake_class(), {})
    linear = _construct(SUPERPOSITION, component_class(SUPERPOSITION, Component("LinearSum")), {})
    engine = {k: _value(k, v, ENGINE) for k, v in config.engine.params.items()}  # the main one's (#64)
    return _construct(ENGINE, component_class(ENGINE, config.engine),
                      dict(site=site, windTurbines=turbines, wake_deficitModel=deficit, superpositionModel=linear,
                           **engine))


def free_stream_expected_classes(config: WakeConfig) -> Dict[str, Optional[type]]:
    """The expected classes of A_0 (declared for the class check, like any other configuration)."""
    return {ENGINE: component_class(ENGINE, config.engine), DEFICIT: _no_wake_class(),
            SUPERPOSITION: component_class(SUPERPOSITION, Component("LinearSum")), TURBULENCE: None, BLOCKAGE: None,
            ROTOR: None, GROUND: None}


def expected_classes(config: WakeConfig) -> Dict[str, Optional[type]]:
    """The class of each checked position, fixed from the configuration before building (``None``: absent)."""
    return {
        ENGINE: component_class(ENGINE, config.engine),
        DEFICIT: component_class(DEFICIT, config.deficit),
        SUPERPOSITION: component_class(SUPERPOSITION, config.superposition),
        TURBULENCE: component_class(TURBULENCE, config.turbulence) if config.turbulence else None,
        BLOCKAGE: component_class(BLOCKAGE, config.blockage) if config.blockage else None,
        ROTOR: component_class(ROTOR, config.rotor) if config.rotor else None,
        GROUND: component_class(GROUND, config.ground) if config.ground else None,
    }


# Where each position is read in an engineering wind farm model of PyWake 2.6.18 (engineering_models.py:74-113).
_READERS = {
    ENGINE: lambda wfm: wfm,
    DEFICIT: lambda wfm: wfm.__dict__["wake_deficitModel"],
    SUPERPOSITION: lambda wfm: wfm.__dict__["superpositionModel"],
    TURBULENCE: lambda wfm: wfm.__dict__["turbulenceModel"],
    BLOCKAGE: lambda wfm: wfm.__dict__["blockage_deficitModel"],
    ROTOR: lambda wfm: wfm.__dict__["wake_deficitModel"].__dict__["rotorAvgModel"],
    GROUND: lambda wfm: wfm.__dict__["wake_deficitModel"].__dict__["groundModel"],
}


def observed_classes(wfm: Any) -> Dict[str, Optional[type]]:
    """The class of each checked position in the built model, read from known attributes, without fallbacks."""
    out: Dict[str, Optional[type]] = {}
    for position in CHECKED_POSITIONS:
        try:
            obj = _READERS[position](wfm)
        except Exception as exc:
            raise ReaderError(position, f"{type(exc).__name__}: {exc}") from exc
        out[position] = None if obj is None else type(obj)
    return out


def check_ws_reference(config: WakeConfig, wfm: Any) -> None:
    """Raise ``ClassMismatch`` (or ``ReaderError``) unless the deficit of ``wfm`` scales as ``config`` says: with the
    ``WS_key`` of its ``deficit_ws_reference``, or, without it, not with one of them (an adjustment left out or wrong,
    with the same classes)."""
    try:
        observed = wfm.__dict__["wake_deficitModel"].__dict__["WS_key"]
    except Exception as exc:
        raise ReaderError(DEFICIT, f"WS_key: {type(exc).__name__}: {exc}") from exc
    wanted = WS_KEYS.get(config.deficit_ws_reference) if config.deficit_ws_reference is not None else None
    if (observed != wanted) if wanted is not None else (observed in WS_KEYS.values()):
        raise ClassMismatch(DEFICIT, f"WS_key = {wanted or 'WS_ilk o WS_eff_ilk'}", f"WS_key = {observed}")


def check_classes(expected: Dict[str, Optional[type]], wfm: Any) -> None:
    """Raise ``ClassMismatch`` (or ``ReaderError``) unless every checked position has exactly the expected class."""
    observed = observed_classes(wfm)
    for position in CHECKED_POSITIONS:
        exp, obs = expected[position], observed[position]
        if exp is not obs:
            raise ClassMismatch(position, getattr(exp, "__name__", None), getattr(obs, "__name__", None))

# -*- coding: utf-8 -*-
"""The wake configuration contract: what is calculated, serialisable and versioned.

A ``WakeConfig`` names, for each position, the exact catalogue class and its
arguments: the engine, the wake deficit with its edited arguments, the rotor
average and the ground model of the deficit, the wake superposition, the added
turbulence, the blockage model with its own superposition. ``None`` in an
optional position is the absence asked for (no rotor average, no ground model,
no turbulence, no blockage). A configuration is complete: every editable
argument of the deficit and of the blockage has its value, taken from the class
signature when the user did not change it (decision 2). The adaptations the
user accepted (GaussianOverlap without h5py, decision 10) are recorded in it.

The arguments of the subordinate objects (#64: ``subordinates.ARGS``) are part
of each component; one whose value is another PyWake class holds a nested
``Component`` (or ``None`` where its family has it). Every configuration is
completed with the signatures for what it leaves out of them (decision 2):
the omission is the value of the signature, an explicit ``None`` is kept.

The dictionary form (``to_dict``/``from_dict``) carries ``schema`` and
``version`` (2, recursive); version 1 (#46a) is read and completed the same
way, without changing what it said. Version 3 adds ``deficit_ws_reference``
(TurbOPark: the deficit scales with the free wind speed at the turbine it
reaches, ``WS_key = 'WS_jlk'``), written only by a configuration that uses it:
without it, a configuration is written as version 2, as before, and an earlier
version is read as without it. ``ct2a`` is written as the name of its
function. Nothing here validates the combination or builds a PyWake object:
that is the factory's job.
"""
from __future__ import annotations

import copy
import inspect
import math
from dataclasses import dataclass, field, fields
from typing import Any, Dict, List, Mapping, Optional, Tuple

from . import catalog as _cat
from . import subordinates as _sub
from ..log_text import log_text
from .catalog import (BLOCKAGE, BLOCKAGE_SUPERPOSITION, DEFICIT, ENGINE, GROUND, ROTOR, SUPERPOSITION, TURBULENCE)

__all__ = [
    "WAKE_CONFIG_SCHEMA", "WAKE_CONFIG_VERSION", "Component", "WakeConfig", "ConfigFormatError",
    "plain_value", "same_value", "component_from_object", "deficit_signature", "blockage_signature", "engine_signature",
    "default_config", "differences_vs_signature", "identification", "component_signature", "complete",
]

WAKE_CONFIG_SCHEMA = "velantis.wake_config"
WAKE_CONFIG_VERSION = 2
# Version 1 (#46a) is read and completed with the signatures (the conversion of the README, «Diseño de Q2», 2).
READABLE_VERSIONS = (1, 2, 3)
# The reference of the deficit's scaling, a field of its own (plan of the predefined models, M4): the free wind speed at
# the turbine the wake reaches (``WS_key = 'WS_jlk'``, Nygaard_2022, literature/turbopark.py:37); ``None``, that of the
# class (``use_effective_ws``). In the dictionary form, version 3.
DESTINATION_FREE_STREAM = "destination_free_stream"
DEFICIT_WS_REFERENCES = (DESTINATION_FREE_STREAM,)
WS_REFERENCE_VERSION = 3

# The defaults of the dialog (decision 14).
DEFAULT_ENGINE = "PropagateDownwind"
DEFAULT_DEFICIT = "BastankhahGaussianDeficit"
# The blockage superposition by default: an explicit LinearSum (decision 8).
DEFAULT_BLOCKAGE_SUPERPOSITION = "LinearSum"


class ConfigFormatError(ValueError):
    """A configuration dictionary that does not follow the contract (keys, types or version)."""


def _is_plain(value: Any, allow_none: bool = False) -> bool:
    """A value of the dictionary form: a bool, a number (NaN and infinities too: they reach PyWake as given, decision
    5 of #64; Python's json writes them as NaN and Infinity, not strict JSON), a text, or a list of them."""
    if value is None:
        return allow_none
    if isinstance(value, (bool, str, int, float)):
        return True
    if isinstance(value, list):
        return all(_is_plain(v, allow_none) for v in value)
    return False


def plain_value(value: Any) -> Any:
    """A JSON-able copy of an argument value: the name of a ``ct2a`` function, lists for sequences."""
    if isinstance(value, Component):
        return value.to_dict()
    if inspect.isfunction(value):
        return value.__name__
    if hasattr(value, "tolist") and not isinstance(value, (bool, int, float, str)):
        return value.tolist()
    if isinstance(value, (list, tuple)):
        return [plain_value(v) for v in value]
    if isinstance(value, bool) or value is None or isinstance(value, str):
        return value
    if isinstance(value, (int, float)):
        return value
    raise TypeError(f"Valor de argumento no serializable: {value!r}")


def same_value(a: Any, b: Any) -> bool:
    """``a == b``, with two NaN in the same place equal, at any depth (lists, tuples, mappings, components): a value
    is the same as itself, also after a copy or a serialization (decision 5 of #64)."""
    if isinstance(a, float) and isinstance(b, float) and math.isnan(a) and math.isnan(b):
        return True
    if isinstance(a, Component) and isinstance(b, Component):
        return type(a) is type(b) and a.name == b.name and same_value(dict(a.params), dict(b.params))
    if type(a) is type(b) and isinstance(a, (list, tuple)):
        return len(a) == len(b) and all(same_value(x, y) for x, y in zip(a, b))
    if isinstance(a, Mapping) and isinstance(b, Mapping):
        return a.keys() == b.keys() and all(same_value(a[k], b[k]) for k in a)
    return a == b


@dataclass(frozen=True, eq=False)
class Component:
    """A catalogue class at one position, with its arguments (plain values); two are equal with the same class and
    arguments, a NaN equal to a NaN in the same place (``same_value``)."""

    name: str
    params: Mapping[str, Any] = field(default_factory=dict)

    def __eq__(self, other: Any) -> bool:
        if other.__class__ is not self.__class__:  # as the method dataclass generates
            return NotImplemented
        return same_value(self, other)

    def __hash__(self) -> int:  # as the method dataclass generates for a frozen one
        return hash((self.name, self.params))

    def to_dict(self) -> Dict[str, Any]:
        return {"class": self.name, "params": {k: plain_value(v) for k, v in self.params.items()}}

    @classmethod
    def from_dict(cls, data: Any, where: str, position: Optional[str] = None) -> "Component":
        """In two phases: the dictionary, with its nested components, completed with the signatures for what it
        leaves out; then exactly its arguments (those of its catalogue entry and of ``subordinates``), else
        ``ConfigFormatError``. ``position`` is the one of a top component, ``None`` for a nested one."""
        if not isinstance(data, Mapping) or set(data) - {"class", "params"} or not isinstance(data.get("class"), str):
            raise ConfigFormatError(f"{where}: se esperaba {{'class': <nombre>, 'params': {{…}}}}, no {data!r}.")
        params = data.get("params", {})
        if not isinstance(params, Mapping) or not all(isinstance(k, str) for k in params):
            raise ConfigFormatError(f"{where}: 'params' tiene que ser un diccionario, no {params!r}.")
        name, values = data["class"], {}
        for k, v in params.items():
            spec = _sub.arg_spec(name, k)
            if spec is not None and spec.kind == _sub.COMPONENT and isinstance(v, Mapping):
                options = [o.name for o in _sub.options(spec)]
                if v.get("class") not in options:
                    raise ConfigFormatError(f"{where}.{k}: {v.get('class')!r} no es una opción de {k} de {name} "
                                            f"({', '.join(map(str, options))}).")
                values[k] = cls.from_dict(v, f"{where}.{k}")
            elif _is_plain(v, allow_none=True):  # an explicit None is kept: PyWake receives it (P5 a)
                values[k] = copy.deepcopy(v)
            else:
                raise ConfigFormatError(f"{where}: valor no serializable o no finito en {k}.")
        comp = complete(cls(name, _with_catalogue_signature(position, name, values)))
        expected = _expected_params(position, name)
        if expected is not None and set(comp.params) != expected:
            raise ConfigFormatError(
                f"{where}: {name} lleva exactamente los argumentos {sorted(expected)}, no {sorted(comp.params)}.")
        return comp

    @property
    def label(self) -> str:
        """``CGIRotorAvg(n=9)``, ``Mirror``: the class with the arguments fixed by its catalogue option and those of a
        closed set (``subordinates.CHOICE``: the ``n`` of ``CGIRotorAvg``, an option of its own until #64)."""
        named = _label_args(self.name)
        return _cat.option_id(self.name, {k: v for k, v in self.params.items() if k in named})


def _label_args(name: str) -> set:
    """The arguments the label of a class shows: those fixed by its catalogue option and those of a closed set."""
    named = {k for e in _cat.all_entries() if e.name == name for k in e.fixed}
    return named | {a.name for a in _sub.args_of(name) if a.kind == _sub.CHOICE}


_OPTIONAL = (ROTOR, GROUND, TURBULENCE, BLOCKAGE, BLOCKAGE_SUPERPOSITION)


def _expected_params(position: Optional[str], name: str) -> Optional[set]:
    """The arguments a known class carries in the contract: those of its catalogue entry (editable or fixed, at a
    top position) and those of ``subordinates``; ``None`` for an unknown class, which the validation rejects with
    its own error (R14)."""
    options = [e for e in _cat.entries(position) if e.name == name] if position else []
    sub = {a.name for a in _sub.args_of(name)}
    if not options and not sub and not _sub.known_name(name):  # by the table: a class PyWake lacks is R14's
        return None
    catalogue = set(options[0].params) | set(options[0].fixed) if options else set()
    return catalogue | sub


def _with_catalogue_signature(position: Optional[str], name: str, values: Dict[str, Any]) -> Dict[str, Any]:
    """``values`` with the editable arguments of a catalogue entry (a deficit, a blockage) it leaves out taken from
    the signature (the omission, README, «Contrato de la configuración, versión 2»)."""
    if position not in (DEFICIT, BLOCKAGE) or name not in [e.name for e in _cat.entries(position)]:
        return values
    e = _cat.entry(position, name)
    missing = [p for p in e.params if p not in values]
    if not missing:  # the signature only for what is left out: a complete one is read without the class (R14 decides)
        return values
    defaults = _cat.signature_defaults(e)
    return {**{p: plain_value(copy.deepcopy(defaults[p])) for p in missing}, **values}


def _from_object(obj: Any) -> Optional[Component]:
    """The component of a default object of a signature (``AreaOverlapAvgModel()``, ``SqrMaxSum()``), with the
    values of its own signature; ``None`` for ``None``."""
    return None if obj is None else component_signature(type(obj).__name__)


def _signature_value(spec: Any) -> Any:
    """The value of the signature of an argument of ``subordinates``: a nested component, or a plain copy."""
    default = _sub.signature_default(spec)
    if spec.kind == _sub.COMPONENT:
        return _from_object(default)
    return plain_value(copy.deepcopy(default))


def component_signature(name: str) -> Component:
    """A subordinate class with the values of the signature of every argument of ``subordinates`` (recursive)."""
    return Component(name, {a.name: _signature_value(a) for a in _sub.args_of(name)})


def complete(comp: Optional[Component]) -> Optional[Component]:
    """``comp`` with the arguments of ``subordinates`` it leaves out taken from the signature, recursively (decision
    2); what it gives is kept, an explicit ``None`` and an argument the table does not know too (the validation
    refuses the latter, R14). A list given as a tuple is kept as the list it is in the contract, so that it is not a
    difference with the signature nor changes after writing and reading the configuration."""
    if comp is None:
        return None
    # Every list given as a tuple, of the catalogue (``a`` of Niayifar) or of ``subordinates``.
    params = {k: list(v) if isinstance(v, tuple) else v for k, v in comp.params.items()}
    for a in _sub.args_of(comp.name):
        if a.name not in params:
            params[a.name] = _signature_value(a)
        elif a.kind == _sub.COMPONENT and isinstance(params[a.name], Component):
            params[a.name] = complete(params[a.name])
    return comp if params == dict(comp.params) else Component(comp.name, params)


@dataclass(frozen=True, eq=False)
class WakeConfig:
    """A complete wake configuration (see the module docstring); two are equal with the same fields, a NaN equal to a
    NaN in the same place (``same_value``), also in ``adaptations``."""

    engine: Component
    deficit: Component
    rotor: Optional[Component]
    ground: Optional[Component]
    superposition: Component
    turbulence: Optional[Component] = None
    blockage: Optional[Component] = None
    blockage_superposition: Optional[Component] = None
    adaptations: Tuple[Mapping[str, Any], ...] = ()
    deficit_ws_reference: Optional[str] = None

    def __eq__(self, other: Any) -> bool:
        if other.__class__ is not self.__class__:  # as the method dataclass generates
            return NotImplemented
        return all(same_value(getattr(self, f.name), getattr(other, f.name)) for f in fields(self))

    def __hash__(self) -> int:  # as the method dataclass generates for a frozen one
        return hash(tuple(getattr(self, f.name) for f in fields(self)))

    def __post_init__(self) -> None:
        # Every component carries all its arguments: what is left out takes the signature (decision 2), as when a
        # dictionary is read (the editable ones of a deficit or a blockage, and those of ``subordinates``).
        for position in _cat.POSITIONS:
            comp = getattr(self, position)
            if comp is not None:
                filled = _with_catalogue_signature(position, comp.name, dict(comp.params))
                comp = complete(comp if filled == dict(comp.params) else Component(comp.name, filled))
            object.__setattr__(self, position, comp)

    def component(self, position: str) -> Optional[Component]:
        return getattr(self, position)

    def to_dict(self) -> Dict[str, Any]:
        out: Dict[str, Any] = {"schema": WAKE_CONFIG_SCHEMA, "version": WAKE_CONFIG_VERSION}
        for position in _cat.POSITIONS:
            c = self.component(position)
            out[position] = c.to_dict() if c is not None else None
        out["adaptations"] = [copy.deepcopy(dict(a)) for a in self.adaptations]  # never shared with the config
        if self.deficit_ws_reference is not None:  # version 3 only with it: without it, as before
            out["version"] = WS_REFERENCE_VERSION
            out["deficit_ws_reference"] = self.deficit_ws_reference
        return out

    @classmethod
    def from_dict(cls, data: Any) -> "WakeConfig":
        if not isinstance(data, Mapping):
            raise ConfigFormatError(f"La configuración de estela tiene que ser un diccionario, no {type(data).__name__}.")
        version = data.get("version")
        if data.get("schema") != WAKE_CONFIG_SCHEMA or type(version) is not int or version not in READABLE_VERSIONS:
            raise ConfigFormatError(
                f"Configuración de estela de otro esquema o versión: {data.get('schema')!r} {data.get('version')!r} "
                f"(se espera {WAKE_CONFIG_SCHEMA!r} {WAKE_CONFIG_VERSION}, o la 1, que se completa).")
        own = {"deficit_ws_reference"} if version == WS_REFERENCE_VERSION else set()
        unknown = set(data) - set(_cat.POSITIONS) - {"schema", "version", "adaptations"} - own
        if unknown:
            raise ConfigFormatError(
                f"Claves desconocidas en la configuración de estela: {', '.join(sorted(map(repr, unknown)))}.")
        values: Dict[str, Any] = {}
        for position in _cat.POSITIONS:
            if position not in data:
                raise ConfigFormatError(f"Falta la posición {position!r} en la configuración de estela.")
            raw = data[position]
            if raw is None:
                if position not in _OPTIONAL:
                    raise ConfigFormatError(f"La posición {position!r} no puede estar vacía.")
                values[position] = None
            else:
                values[position] = Component.from_dict(raw, position, position)
        adaptations = data.get("adaptations", [])

        def plain_record(value: Any) -> bool:
            # A value of a record: a plain value, or a dictionary of them (the component used, ``{"class", "n"}``).
            return _is_plain(value, allow_none=True) or (isinstance(value, Mapping) and all(
                isinstance(k, str) and _is_plain(v, allow_none=True) for k, v in value.items()))
        if not isinstance(adaptations, list) or not all(
                isinstance(a, Mapping) and all(isinstance(k, str) and plain_record(v) for k, v in a.items())
                for a in adaptations):
            raise ConfigFormatError("'adaptations' tiene que ser una lista de diccionarios con valores serializables.")
        reference = data.get("deficit_ws_reference")
        if reference is not None and reference not in DEFICIT_WS_REFERENCES:
            raise ConfigFormatError(f"deficit_ws_reference: {reference!r} no es una opción "
                                    f"({', '.join(DEFICIT_WS_REFERENCES)}, o None).")
        return cls(**values, adaptations=tuple(copy.deepcopy(dict(a)) for a in adaptations),
                   deficit_ws_reference=reference)


def component_from_object(position: str, obj: Any) -> Optional[Component]:
    """The catalogue component of a default object of a signature (``AreaOverlapAvgModel()``, ``Mirror()``)."""
    if obj is None:
        return None
    for e in _cat.entries(position):
        if e.fixed:
            continue
        try:
            cls = _cat.resolve_class(e)
        except _cat.ClassUnavailable:  # a class this PyWake does not have is not the one of the object (R14)
            continue
        if type(obj) is cls:
            return Component(e.name, {})
    raise TypeError(f"El valor por defecto {obj!r} no es una opción del catálogo en {position}.")


def deficit_signature(name: str) -> Tuple[Component, Optional[Component], Optional[Component]]:
    """The deficit with the signature values of its editable arguments, and its rotor and ground of the signature."""
    e = _cat.entry(DEFICIT, name)
    defaults = _cat.signature_defaults(e)
    params = {p: plain_value(copy.deepcopy(defaults[p])) for p in e.params}
    return (Component(name, params), complete(component_from_object(ROTOR, defaults.get("rotorAvgModel"))),
            complete(component_from_object(GROUND, defaults.get("groundModel"))))


def blockage_signature(name: str) -> Component:
    """The blockage model with the signature values of its editable arguments."""
    e = _cat.entry(BLOCKAGE, name)
    defaults = _cat.signature_defaults(e)
    return complete(Component(name, {p: plain_value(copy.deepcopy(defaults[p])) for p in e.params}))


def engine_signature(name: str) -> Dict[str, Optional[Component]]:
    """The superposition, turbulence and blockage the engine signature declares (decisions 2 and 5; D9)."""
    defaults = _cat.signature_defaults(_cat.entry(ENGINE, name))
    return {
        SUPERPOSITION: complete(component_from_object(SUPERPOSITION, defaults.get("superpositionModel"))),
        TURBULENCE: complete(component_from_object(TURBULENCE, defaults.get("turbulenceModel"))),
        BLOCKAGE: complete(component_from_object(BLOCKAGE, defaults.get("blockage_deficitModel"))),
    }


def default_config(engine: str = DEFAULT_ENGINE, deficit: str = DEFAULT_DEFICIT) -> WakeConfig:
    """The configuration with every value from the signatures: the dialog's default physics (decision 14)."""
    d, rotor, ground = deficit_signature(deficit)
    eng = engine_signature(engine)
    return WakeConfig(engine=Component(engine, {}), deficit=d, rotor=rotor, ground=ground,
                      superposition=eng[SUPERPOSITION], turbulence=eng[TURBULENCE], blockage=eng[BLOCKAGE],
                      blockage_superposition=None)


def differences_vs_signature(config: WakeConfig) -> List[Dict[str, Any]]:
    """Every value of ``config`` that is not the one of its signature: ``{position, param, signature, value}``.

    The deficit's arguments, rotor and ground against the deficit signature; the superposition, turbulence and
    blockage against the engine signature; the blockage's arguments against its own signature and its superposition
    against the explicit default of decision 8. ``param`` is ``None`` for a whole component (its label is compared);
    the arguments of a component (#64) are compared with the signature of its class, recursively, ``param`` being
    their route (``groundModel · superpositionModel``).
    """
    out: List[Dict[str, Any]] = []

    def label(c: Optional[Component]) -> Optional[str]:
        return c.label if c is not None else None

    def name(c: Optional[Component]) -> Optional[str]:
        return c.name if c is not None else None

    def arguments(position: str, comp: Component, sig: Component, path: str = "", shown: frozenset = frozenset()
                  ) -> None:
        # ``shown``: the arguments the label of a change of class already gives (the n of CGIRotorAvg), not repeated.
        for p, v in sig.params.items():
            if p in shown:
                continue
            got = comp.params.get(p)
            if isinstance(v, Component) or isinstance(got, Component):
                changed = name(v) != name(got)
                if changed:
                    out.append({"position": position, "param": path + p, "signature": label(v), "value": label(got)})
                if isinstance(got, Component):  # its own arguments, against the signature of its class
                    arguments(position, got, component_signature(got.name) if changed else v, f"{path}{p} · ",
                              frozenset(_label_args(got.name)) if changed else frozenset())
            elif not same_value(got, v):
                out.append({"position": position, "param": path + p, "signature": v, "value": got})

    def whole(position: str, comp: Optional[Component], sig: Optional[Component], by=label) -> None:
        changed = by(comp) != by(sig)
        if changed:
            out.append({"position": position, "param": None, "signature": by(sig), "value": by(comp)})
        if comp is not None:
            other = sig is None or sig.name != comp.name
            arguments(position, comp, component_signature(comp.name) if other else sig,
                      shown=frozenset(_label_args(comp.name)) if changed and other else frozenset())

    sig_deficit, sig_rotor, sig_ground = deficit_signature(config.deficit.name)
    arguments(DEFICIT, config.deficit, sig_deficit)
    whole(ROTOR, config.rotor, sig_rotor)
    whole(GROUND, config.ground, sig_ground)
    eng = engine_signature(config.engine.name)
    arguments(ENGINE, config.engine, component_signature(config.engine.name))
    whole(SUPERPOSITION, config.superposition, eng[SUPERPOSITION])
    whole(TURBULENCE, config.turbulence, eng[TURBULENCE])
    if name(config.blockage) != name(eng[BLOCKAGE]):
        out.append({"position": BLOCKAGE, "param": None, "signature": name(eng[BLOCKAGE]),
                    "value": name(config.blockage)})
    if config.blockage is not None:
        arguments(BLOCKAGE, config.blockage, blockage_signature(config.blockage.name))
        if label(config.blockage_superposition) != DEFAULT_BLOCKAGE_SUPERPOSITION:
            out.append({"position": BLOCKAGE_SUPERPOSITION, "param": None, "signature": DEFAULT_BLOCKAGE_SUPERPOSITION,
                        "value": label(config.blockage_superposition)})
    if config.deficit_ws_reference is not None:  # not of any signature: that of the class is its use_effective_ws
        out.append({"position": DEFICIT, "param": "deficit_ws_reference", "signature": None,
                    "value": config.deficit_ws_reference})
    return out


def _value_text(v: Any) -> str:
    if isinstance(v, Component):
        return v.label
    if isinstance(v, list):
        return "[" + "; ".join(_value_text(x) for x in v) + "]"
    return str(v)


_IDENTIFICATION = ("{deficit} · motor {engine} · superposición {superposition} · turbulencia {turbulence} · "
                   "bloqueo {blockage} · valores de su firma")


def identification(config: WakeConfig) -> str:
    """«Clase X · motor Y · superposición Z · turbulencia T · bloqueo B · valores de su firma» or «… salvo: …».

    Never «preset» nor «referencia» (decision 1). A translatable template (``log_text``); its data are class names,
    argument names and values only (an absent component, ``None``), so that the whole text is translated.
    """
    data = dict(deficit=config.deficit.name, engine=config.engine.name, superposition=config.superposition.label,
                turbulence=config.turbulence.label if config.turbulence else log_text("ninguna"),
                blockage=config.blockage.name if config.blockage else log_text("ninguno"))
    diffs = differences_vs_signature(config)
    if not diffs:
        return log_text(_IDENTIFICATION, **data)
    # An argument of another position than the deficit's, with its route (the same name can be in two positions).
    shown = [(f"{d['position']} · {d['param']}" if d["param"] and d["position"] != DEFICIT else d["param"] or d["position"])
             + f" = {_value_text(d['value'])}" for d in diffs]
    return log_text(_IDENTIFICATION + " salvo: {differences}", differences=", ".join(shown), **data)

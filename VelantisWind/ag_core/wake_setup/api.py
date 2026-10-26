# -*- coding: utf-8 -*-
"""The contract of the wake physics at the API (#46 P5b; README, P5 a-f; P0, section 9).

A request gives the physics in ``wake_physics``, a versioned dictionary with the exact names of the PyWake classes::

    {"version": 1, "engine": ..., "deficit": ..., "deficit_params": {...}, "rotor": ..., "ground": ...,
     "superposition": ..., "turbulence": ..., "blockage": ..., "blockage_params": {"use_effective_ws": ...},
     "blockage_superposition": ..., "adaptations": [...]}

A component with arguments is ``{"class": "CGIRotorAvg", "n": 9}``; one without, its class name; the engine too
(``{"class": "All2AllIterative", "convergence_tolerance": None}``). An argument whose value is another PyWake class
(#64) takes that class as its name or ``{"class": …, <its arguments>}``, recursively (``{"class": "MultiMirror",
"n_reps": 1, "superpositionModel": {"class": "SquaredSum"}}``), also in ``blockage_params``. A key left out, or
``""``, is the omission: the value of the signature (the deficit's for its parameters, rotor and ground; the
engine's for the superposition, turbulence and blockage; ``LinearSum`` for the blockage superposition, decision 8).
``None`` or ``"NONE"`` is the absence asked for. A string of spaces only is invalid. ``NOT_SET`` is the omission in
Python, told apart from ``None``. ``adaptations`` carries what the user accepted in the dialog (decision 10).
Version 2 adds ``deficit_ws_reference`` (``config.DEFICIT_WS_REFERENCES``; TurbOPark), only for a request that uses
it: without it a request is version 1, as before.

The previous schema (``wfm_engine``, ``wake_deficit_model``, ``superposition_model``, ``rotor_avg_model``,
``turbulence_model``, ``blockage_deficit_model``, ``wake_deficit_kwargs`` and ``include_turbulence``,
``include_blockage``, ``include_rotor_avg``) is translated once, here, with a closed table, before the configuration
is validated; nothing else translates. Every field of it defaults to «not indicated» (``NOT_SET``): a request that
indicates none is not translated. The explicit arguments are all kept (``False`` and ``None`` too); the signature
only completes what was left out. Rejected, with their error and without translating: ``AUTO`` in any field, a key
outside the table, a request that mixes the two schemas, a position given twice with different values and a boolean
that contradicts its class. The result says that the request used the previous schema and how it was translated (``legacy_request``).

This module only turns a request into a ``WakeConfig``; ``validation.validate`` decides if it can be calculated.
"""
from __future__ import annotations

import copy
from typing import Any, Dict, List, Mapping, Optional, Tuple

from . import catalog as _cat
from . import config as _cfg
from . import subordinates as _sub
from .catalog import BLOCKAGE, BLOCKAGE_SUPERPOSITION, DEFICIT, ENGINE, GROUND, ROTOR, SUPERPOSITION, TURBULENCE
from .config import Component, WakeConfig
from ..log_text import log_text

__all__ = ["NOT_SET", "LEGACY_FIELDS", "WAKE_PHYSICS_VERSION", "RequestError", "ConfigRejected", "resolve_request",
           "legacy_note", "to_wake_physics", "check_calculable", "check_layout", "user_selection", "gaussian_overlap_adaptation"]

WAKE_PHYSICS_VERSION = 1
# Version 2: version 1 with ``deficit_ws_reference`` (plan of the predefined models, M4).
WS_REFERENCE_PHYSICS_VERSION = 2


class _NotSet:
    """The omission: a value of its own, never ``None`` (the absence asked for) nor ``False``."""

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __repr__(self) -> str:
        return "NOT_SET"

    def __bool__(self) -> bool:
        raise TypeError("NOT_SET no es un booleano: compáralo con «is NOT_SET».")

    def __copy__(self):
        return self

    def __deepcopy__(self, memo):
        return self


NOT_SET = _NotSet()

LEGACY_FIELDS = ("wfm_engine", "wake_deficit_model", "superposition_model", "rotor_avg_model", "turbulence_model",
                 "blockage_deficit_model", "wake_deficit_kwargs", "include_turbulence", "include_blockage",
                 "include_rotor_avg", "wake_model")
_KEYS = ("version", "engine", "deficit", "deficit_params", "rotor", "ground", "superposition", "turbulence",
         "blockage", "blockage_params", "blockage_superposition", "adaptations")
_WS_REFERENCE_KEY = "deficit_ws_reference"


class RequestError(ValueError):
    """A request that cannot be read; ``args[0]`` is a translatable template (``log_text``)."""


class ConfigRejected(ValueError):
    """A configuration that cannot be calculated (``validation.validate``); ``issues`` are the reasons."""

    def __init__(self, issues):
        self.issues = list(issues)
        from .validation import issues_log_text
        super().__init__(log_text("No se puede calcular con esta configuración: {reasons}",
                                  reasons=issues_log_text(self.issues)))


def _error(template: str, **data: Any) -> RequestError:
    return RequestError(log_text(template, **data))


# --- the closed table of the previous schema (the keys the dialog emitted, aep_setup_dialog.py:2312-2546) --------
_CGI = {n: {"class": "CGIRotorAvg", "n": n} for n in (7, 9, 21)}
_TABLE: Dict[str, Dict[str, Any]] = {
    "wfm_engine": {"PDW": "PropagateDownwind", "A2A": "All2AllIterative", "PUD": "PropagateUpDownIterative"},
    "wake_deficit_model": {"NOJ": "NOJDeficit", "TNOJ": "TurboNOJDeficit", "BG": "BastankhahGaussianDeficit",
                           "NIA": "NiayifarGaussianDeficit", "TG": "TurboGaussianDeficit", "ZG": "ZongGaussianDeficit"},
    "rotor_avg_model": {"NONE": None, "RC": "RotorCenter", "CGI7": _CGI[7], "CGI9": _CGI[9], "CGI21": _CGI[21],
                        "EQ": "EqGridRotorAvg", "GO": "GaussianOverlapAvgModel"},
    "superposition_model": {"LIN": "LinearSum", "SQR": "SquaredSum", "MAX": "MaxSum", "WGT": "WeightedSum"},
    "turbulence_model": {"NONE": None, "STF2005": "STF2005TurbulenceModel", "STF2017": "STF2017TurbulenceModel",
                         "GCL": "GCLTurbulence", "CH": "CrespoHernandez"},
    "blockage_deficit_model": {"NONE": None, "SS2020": "SelfSimilarityDeficit2020", "SS": "SelfSimilarityDeficit",
                               "VC": "VortexCylinder", "VD": "VortexDipole", "HI": "HybridInduction"},
}
_POSITION_OF = {"wfm_engine": ENGINE, "wake_deficit_model": DEFICIT, "rotor_avg_model": ROTOR,
                "superposition_model": SUPERPOSITION, "turbulence_model": TURBULENCE,
                "blockage_deficit_model": BLOCKAGE}
# The field of each component and its boolean (rule c).
_SWITCHED = {ROTOR: ("rotor_avg_model", "include_rotor_avg"), TURBULENCE: ("turbulence_model", "include_turbulence"),
             BLOCKAGE: ("blockage_deficit_model", "include_blockage")}


def _text(value: Any, where: str) -> Any:
    """``""`` is the omission and ``"NONE"`` the absence; a string of spaces only is invalid."""
    if isinstance(value, str):
        if value == "":
            return NOT_SET
        if not value.strip():
            raise _error("{field}: una cadena solo de espacios no es un valor.", field=where)
        if value.strip().upper() == "AUTO":
            raise _error("{field}: «AUTO» ya no es una opción; indica la clase (o déjalo sin indicar para usar el "
                         "valor de la firma).", field=where)
        if value == "NONE":
            return None
    return value


def _legacy_value(field: str, value: Any) -> Any:
    """The value of a field of the previous schema, by its key or by the exact name of a class (``None`` = absence)."""
    value = _text(value, field)
    if value is NOT_SET or value is None:
        return value
    if not isinstance(value, str):
        raise _error("{field}: se esperaba una clave o el nombre de una clase, no {value!r}.", field=field, value=value)
    table = _TABLE[field]
    key = value.strip()
    if key.upper() in table:
        return copy.deepcopy(table[key.upper()])
    position = _POSITION_OF[field]
    names = [e for e in _cat.entries(position) if e.name == key]
    if names and not names[0].fixed:
        return key
    raise _error("{field}: «{value}» no es una clave del esquema anterior ni una clase de {position}.", field=field,
                 value=value, position=_cat.position_label(position))


def _component(position: str, value: Any, where: str) -> Optional[Component]:
    """A component of the new schema: a class name, or ``{"class": ..., <its fixed arguments>}``."""
    if value is None:
        return None
    if isinstance(value, str):
        options = [e for e in _cat.entries(position) if e.name == value]
        if options and options[0].fixed:
            raise _error("{field}: {cls} necesita sus argumentos ({args}): indícalo como {{'class': '{cls}', …}}.",
                         field=where, cls=value, args=", ".join(sorted(options[0].fixed)))
        return Component(value, {})
    if isinstance(value, Mapping) and isinstance(value.get("class"), str):
        name = value["class"]
        if not all(isinstance(k, str) for k in value):
            raise _error("{field}: los nombres de los argumentos tienen que ser textos.", field=where)
        return Component(name, {k: _argument(name, k, v, f"{where}.{k}") for k, v in value.items() if k != "class"})
    raise _error("{field}: se esperaba el nombre de una clase o {{'class': …}}, no {value!r}.", field=where, value=value)


def _argument(owner: str, name: str, value: Any, where: str) -> Any:
    """An argument of a component: a nested component (#64), as its class name or ``{"class": …, <args>}``, where
    ``subordinates`` says the argument takes another class; a copy of the value otherwise."""
    spec = _sub.arg_spec(owner, name)
    if spec is not None and spec.kind == _sub.COMPONENT and value is not None:
        if isinstance(value, str) and value.strip():  # an empty name is neither a class nor an omission here
            return Component(value, {})
        if isinstance(value, Mapping) and isinstance(value.get("class"), str):
            return _component("", value, where)
        raise _error("{field}: se esperaba el nombre de una clase o {{'class': …}}, no {value!r}.", field=where,
                     value=value)
    return _plain_numpy(value)


def _plain_numpy(value: Any) -> Any:
    """A copy with the arrays and scalars of NumPy as the plain values of the contract (their lists and numbers),
    at any depth, so that a record of a request is written as it was given, not as text."""
    if type(value).__module__ == "numpy" and hasattr(value, "tolist") and not isinstance(value, float):
        return value.tolist()  # a numpy.float64 is a float: kept, as cf249cf passed it (its arithmetic is NumPy's)
    if isinstance(value, Mapping):
        return {k: _plain_numpy(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):  # a subclass (a namedtuple) as its plain form: its constructor differs
        return (list if isinstance(value, list) else tuple)(_plain_numpy(v) for v in value)
    return copy.deepcopy(value)


def _params(value: Any, where: str, owner: str = "") -> Dict[str, Any]:
    if value is NOT_SET:
        return {}
    if not isinstance(value, Mapping) or not all(isinstance(k, str) for k in value):
        raise _error("{field}: se esperaba un diccionario de argumentos, no {value!r}.", field=where, value=value)
    return {k: _argument(owner, k, v, f"{where}.{k}") for k, v in value.items()}


def _resolve_new(physics: Any) -> WakeConfig:
    if not isinstance(physics, Mapping):
        raise _error("wake_physics: se esperaba un diccionario, no {value!r}.", value=physics)
    version = physics.get("version", NOT_SET)
    if type(version) is not int or version not in (WAKE_PHYSICS_VERSION, WS_REFERENCE_PHYSICS_VERSION):
        raise _error("wake_physics: versión {value!r}; se espera {version}.", value=version,
                     version=WAKE_PHYSICS_VERSION)
    own = {_WS_REFERENCE_KEY} if version == WS_REFERENCE_PHYSICS_VERSION else set()
    unknown = sorted(set(physics) - set(_KEYS) - own)
    if unknown:
        raise _error("wake_physics: claves desconocidas: {keys}.", keys=", ".join(map(repr, unknown)))
    reference = physics.get(_WS_REFERENCE_KEY)
    if reference is not None and reference not in _cfg.DEFICIT_WS_REFERENCES:
        raise _error("wake_physics.deficit_ws_reference: {value!r} no es una opción ({options}, o None).",
                     value=reference, options=", ".join(_cfg.DEFICIT_WS_REFERENCES))

    def get(key: str) -> Any:
        return _text(physics.get(key, NOT_SET), f"wake_physics.{key}")

    engine, deficit = get("engine"), get("deficit")
    engine_params: Dict[str, Any] = {}
    if isinstance(engine, Mapping) and isinstance(engine.get("class"), str):  # the engine with its arguments (#64)
        engine_comp = _component(ENGINE, engine, "wake_physics.engine")
        engine, engine_params = engine_comp.name, dict(engine_comp.params)
    for key, value in (("engine", engine), ("deficit", deficit)):
        if value is None:
            raise _error("wake_physics.{key}: no puede faltar; déjalo sin indicar para usar el valor por defecto.",
                         key=key)
        if value is not NOT_SET and not isinstance(value, str):
            raise _error("wake_physics.{key}: se esperaba el nombre de una clase, no {value!r}.", key=key, value=value)
    engine = _cfg.DEFAULT_ENGINE if engine is NOT_SET else engine
    deficit = _cfg.DEFAULT_DEFICIT if deficit is NOT_SET else deficit
    for position, name in ((ENGINE, engine), (DEFICIT, deficit)):
        if name not in [e.name for e in _cat.entries(position)]:
            raise _error("{name} no es una opción de {position}.", name=name, position=_cat.position_label(position))
    try:
        sig_deficit, sig_rotor, sig_ground = _cfg.deficit_signature(deficit)
        sig_engine = _cfg.engine_signature(engine)
    except _cat.ClassUnavailable as exc:
        # A class the installed PyWake does not have (R14, environment): refused with its message, never another.
        from .validation import ENVIRONMENT, Issue
        raise ConfigRejected([Issue("R14", ENGINE, ENVIRONMENT, "{error}", "", {"error": exc.args[0]})]) from exc

    def component(key: str, position: str, default: Optional[Component]) -> Optional[Component]:
        value = get(key)
        return default if value is NOT_SET else _component(position, value, f"wake_physics.{key}")

    superposition = component("superposition", SUPERPOSITION, sig_engine[SUPERPOSITION])
    if superposition is None:
        raise _error("wake_physics.superposition: no puede faltar; déjalo sin indicar para usar la de la firma.")
    blockage = component("blockage", BLOCKAGE, sig_engine[BLOCKAGE])
    blockage_params = _params(physics.get("blockage_params", NOT_SET), "wake_physics.blockage_params",
                              blockage.name if blockage is not None else "")
    if blockage is None and blockage_params:
        raise _error("wake_physics.blockage_params: hay argumentos del bloqueo, pero no hay bloqueo.")
    if blockage is not None:
        if blockage.params:
            raise _error("wake_physics.blockage: sus argumentos van en blockage_params.")
        if blockage.name in [e.name for e in _cat.entries(BLOCKAGE)]:
            try:
                signature = _cfg.blockage_signature(blockage.name).params
            except _cat.ClassUnavailable as exc:
                from .validation import ENVIRONMENT, Issue
                raise ConfigRejected([Issue("R14", BLOCKAGE, ENVIRONMENT, "{error}", "", {"error": exc.args[0]})]) from exc
            blockage = Component(blockage.name, dict(signature, **blockage_params))
        else:
            blockage = Component(blockage.name, blockage_params)
    bsup_default = Component(_cfg.DEFAULT_BLOCKAGE_SUPERPOSITION, {}) if blockage is not None else None
    adaptations = physics.get("adaptations", NOT_SET)
    adaptations = () if adaptations is NOT_SET else adaptations
    if not isinstance(adaptations, (list, tuple)) or not all(isinstance(a, Mapping) for a in adaptations):
        raise _error("wake_physics.adaptations: se esperaba una lista de diccionarios.")
    return WakeConfig(
        engine=Component(engine, engine_params),
        deficit=Component(deficit, dict(sig_deficit.params, **_params(physics.get("deficit_params", NOT_SET),
                                                                        "wake_physics.deficit_params"))),
        rotor=component("rotor", ROTOR, sig_rotor), ground=component("ground", GROUND, sig_ground),
        superposition=superposition, turbulence=component("turbulence", TURBULENCE, sig_engine[TURBULENCE]),
        blockage=blockage, blockage_superposition=component("blockage_superposition", BLOCKAGE_SUPERPOSITION,
                                                            bsup_default),
        adaptations=tuple(copy.deepcopy(dict(a)) for a in adaptations), deficit_ws_reference=reference)


def _switched(position: str, cls: Any, flag: Any) -> Any:
    """Rule (c): the boolean ``include_*`` with its class (``NOT_SET`` both: the signature)."""
    field, flag_name = _SWITCHED[position]
    if flag is NOT_SET:
        return cls
    if not isinstance(flag, bool):
        raise _error("{flag}: se esperaba True o False, no {value!r}.", flag=flag_name, value=flag)
    if flag is False:
        if cls is NOT_SET or cls is None:
            return None
        raise _error("{flag} = False contradice {field} = {value!r}: quita uno de los dos.", flag=flag_name,
                     field=field, value=cls)
    if cls is NOT_SET:
        raise _error("{flag} = True sin {field}: elige la clase.", flag=flag_name, field=field)
    if cls is None:
        raise _error("{flag} = True contradice {field} = NONE: quita uno de los dos.", flag=flag_name, field=field)
    return cls


def _same_rotor(a: Any, b: Any) -> bool:
    """The same rotor average, however it is written (``CGIRotorAvg`` and ``CGI7`` are the same, #64)."""
    if a is None or b is None:
        return a is b
    try:
        return _cfg.complete(_component(ROTOR, a, "rotor")) == _cfg.complete(_component(ROTOR, b, "rotor"))
    except RequestError:
        return a == b


def _translate_legacy(legacy: Mapping[str, Any]) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """The previous schema as a ``wake_physics`` request, and the record of the translation (``legacy_request``)."""
    if legacy.get("wake_model", NOT_SET) is not NOT_SET:
        raise _error("wake_model ya no se usa: indica la física con wake_physics (o con los campos del esquema "
                     "anterior).")
    values = {f: _legacy_value(f, legacy.get(f, NOT_SET)) for f in _TABLE}
    kwargs = legacy.get("wake_deficit_kwargs", NOT_SET)
    kwargs = {} if kwargs is NOT_SET or kwargs is None else _params(kwargs, "wake_deficit_kwargs")
    # (c2) A position given two ways is gathered before completing what was left out.
    rotor = values["rotor_avg_model"]
    in_kwargs = NOT_SET
    if "rotorAvgModel" in kwargs:
        raw = kwargs.pop("rotorAvgModel")
        # None is the absence asked for, "" the omission; anything else is a key or a class name (never False).
        in_kwargs = None if raw is None else _legacy_value("rotor_avg_model", raw)
    if in_kwargs is not NOT_SET:
        if rotor is not NOT_SET and not _same_rotor(rotor, in_kwargs):
            raise _error("rotor_avg_model = {a!r} y wake_deficit_kwargs['rotorAvgModel'] = {b!r} se contradicen: "
                         "indica el rotor una sola vez.", a=legacy.get("rotor_avg_model"), b=in_kwargs)
        rotor = in_kwargs
    ground = NOT_SET
    if "groundModel" in kwargs:
        g = kwargs.pop("groundModel")
        ground = None if g is None or g == "NONE" else g
    physics: Dict[str, Any] = {"version": WAKE_PHYSICS_VERSION}
    for key, field in (("engine", "wfm_engine"), ("deficit", "wake_deficit_model"),
                       ("superposition", "superposition_model")):
        if values[field] is NOT_SET:
            continue
        if values[field] is None:
            raise _error("{field}: «NONE» no es una opción.", field=field)
        physics[key] = values[field]
    for key, position, cls in (("rotor", ROTOR, rotor), ("turbulence", TURBULENCE, values["turbulence_model"]),
                               ("blockage", BLOCKAGE, values["blockage_deficit_model"])):
        resolved = _switched(position, cls, legacy.get(_SWITCHED[position][1], NOT_SET))
        if resolved is not NOT_SET:
            physics[key] = resolved
    if ground is not NOT_SET:
        physics["ground"] = ground
    if kwargs:
        physics["deficit_params"] = kwargs
    given = {f: _plain_numpy(legacy[f]) for f in LEGACY_FIELDS
             if legacy.get(f, NOT_SET) is not NOT_SET and legacy.get(f) != ""}
    return physics, {"given": given, "translated": copy.deepcopy(physics)}


def legacy_note(record: Mapping[str, Any]) -> Any:
    """The note of a translation of the previous schema (``legacy_request``), for the log and the report."""
    given = ", ".join(f"{f} = {v!r}" for f, v in record["given"].items())
    translated = ", ".join(f"{k} = {v!r}" for k, v in record["translated"].items() if k != "version")
    return log_text("La petición usaba el esquema anterior de la física ({given}); se ha traducido como "
                    "{translated}. La traducción no reproduce el comportamiento anterior: lo que se calcula "
                    "es exactamente esa configuración.", given=given, translated=translated or "—")


def resolve_request(wake_physics: Any = NOT_SET, **legacy: Any) -> Tuple[WakeConfig, Optional[Dict[str, Any]]]:
    """The ``WakeConfig`` of a request, and the record of the translation of the previous schema (``None`` without it):
    ``{"given": the fields indicated, "translated": the wake_physics they became}`` (``legacy_note`` says it).

    ``legacy`` takes only the fields of the previous schema (``LEGACY_FIELDS``), each ``NOT_SET`` when not indicated.
    Raises ``RequestError`` for what cannot be read; the configuration is validated by the caller.
    """
    unknown = sorted(set(legacy) - set(LEGACY_FIELDS))
    if unknown:
        raise TypeError(f"Argumentos desconocidos: {', '.join(unknown)}")
    # A field is indicated unless it is NOT_SET or "" (an empty key is the omission, decision 15a).
    indicated = [f for f in LEGACY_FIELDS if legacy.get(f, NOT_SET) is not NOT_SET and legacy.get(f) != ""]
    if wake_physics is not NOT_SET and wake_physics is not None:
        if indicated:
            raise _error("La petición mezcla wake_physics con campos del esquema anterior ({fields}): usa solo "
                         "wake_physics.", fields=", ".join(indicated))
        return _resolve_new(wake_physics), None
    if not indicated:
        return _resolve_new({"version": WAKE_PHYSICS_VERSION}), None
    physics, record = _translate_legacy(legacy)
    return _resolve_new(physics), record


def _spec(comp: Optional[Component], nested: bool = False) -> Any:
    """A component of a request: its class name, or ``{"class": …, <args>}``; a nested one, always the latter."""
    if comp is None:
        return None
    if not comp.params and not nested:
        return comp.name
    return dict({"class": comp.name}, **{k: _plain_argument(v) for k, v in comp.params.items()})


def _plain_argument(value: Any) -> Any:
    return _spec(value, nested=True) if isinstance(value, Component) else copy.deepcopy(value)


def to_wake_physics(config: WakeConfig) -> Dict[str, Any]:
    """The request of a configuration (the dialog's): ``resolve_request(to_wake_physics(c))[0] == c``."""
    out: Dict[str, Any] = {
        "version": WAKE_PHYSICS_VERSION, "engine": _spec(config.engine), "deficit": config.deficit.name,
        "deficit_params": copy.deepcopy(dict(config.deficit.params)), "rotor": _spec(config.rotor),
        "ground": _spec(config.ground), "superposition": _spec(config.superposition),
        "turbulence": _spec(config.turbulence), "blockage": config.blockage.name if config.blockage else None,
        "blockage_superposition": _spec(config.blockage_superposition),
        "adaptations": [copy.deepcopy(dict(a)) for a in config.adaptations],
    }
    if config.blockage is not None:
        out["blockage_params"] = {k: _plain_argument(v) for k, v in config.blockage.params.items()}
    if config.deficit_ws_reference is not None:  # version 2 only with it: without it, as before
        out["version"] = WS_REFERENCE_PHYSICS_VERSION
        out[_WS_REFERENCE_KEY] = config.deficit_ws_reference
    return out


def check_calculable(config: WakeConfig) -> None:
    """``ConfigRejected`` with every reason if ``config`` cannot be calculated (with the environment: R13)."""
    from .validation import validate
    issues = validate(config)
    if issues:
        raise ConfigRejected(issues)


def check_layout(config: WakeConfig, n_turbines: int) -> None:
    """``ConfigRejected`` with what PyWake refuses only with the layout (``validation.layout_issues``: R9f), checked
    once the turbines are loaded and before simulating."""
    from .validation import layout_issues
    issues = layout_issues(config, n_turbines)
    if issues:
        raise ConfigRejected(issues)


# Decision 10: GaussianOverlapAvgModel without h5py or h5netcdf, accepted by the user in the dialog.
GO_REPLACEMENT = {"class": "CGIRotorAvg", "n": 7}


# How a predefined model's adaptation was accepted (decision 21 of the predefined models): with «Continuar» in its
# launch, or by the decision the user saved for that model. The manual mode records none, as before.
ACCEPTED_NOW, ACCEPTED_SAVED = "continue", "saved_preference"


def gaussian_overlap_adaptation(config: WakeConfig, missing: List[str],
                                acceptance: Optional[str] = None) -> WakeConfig:
    """The configuration the user accepted with «Continuar» (decision 10): ``CGIRotorAvg(7)`` instead of
    ``GaussianOverlapAvgModel``, recorded in ``adaptations`` with what was missing (and, for a predefined model, how
    it was accepted)."""
    record = {"position": ROTOR, "selected": "GaussianOverlapAvgModel", "used": dict(GO_REPLACEMENT),
              "reason": "missing_modules", "missing": ", ".join(missing)}
    if acceptance is not None:
        record["acceptance"] = acceptance
    return WakeConfig(**{**config.__dict__, "rotor": Component("CGIRotorAvg", {"n": 7}),
                         "adaptations": tuple(config.adaptations) + (record,)})


def user_selection(config: WakeConfig) -> WakeConfig:
    """What the user selected: ``config`` with its accepted adaptations undone (the report compares with it)."""
    changes: Dict[str, Any] = {}
    for a in config.adaptations:
        if a.get("position") in _cat.POSITIONS and "selected" in a:
            changes[a["position"]] = _component(a["position"], a["selected"], "adaptations")
    return WakeConfig(**{**config.__dict__, **changes}) if changes else config

# -*- coding: utf-8 -*-
"""What is rejected before calculating, and why (decision 1; P0, section 6).

Only what PyWake rejects (when building, or in its calculation path) and what
the plugin cannot support is refused; nothing here judges the physics, and a
warning is never a barrier. Each issue says its rule (R1-R14 of the P0 cards),
the position of the selector it belongs to, its origin (PyWake when building,
PyWake when calculating, the plugin or the environment), the reason and the
known resolution. Validation never changes the configuration.

The PyWake conditions are evaluated on the objects PyWake itself would build
(``WS_key``, ``args4deficit``, the class hierarchy), so the rules follow the
installed version; the tests check every rule against PyWake 2.6.18.
"""
from __future__ import annotations

import importlib
import sys
from dataclasses import dataclass, field, replace
from typing import Any, Callable, Dict, List, Mapping, Optional

from . import catalog as _cat
from . import factory as _f
from . import subordinates as _sub
from .catalog import (BLOCKAGE, BLOCKAGE_SUPERPOSITION, DEFICIT, ENGINE, GROUND, ROTOR, SUPERPOSITION, TURBULENCE)
from . import config as _cfg
from .config import Component, WakeConfig
from ..log_text import LogText, log_text, shown

__all__ = ["Issue", "PYWAKE_BUILD", "PYWAKE_CALC", "PLUGIN", "ENVIRONMENT", "validate", "map_issues", "layout_issues",
           "issues_log_text",
           "missing_gaussian_overlap_modules", "install_hint"]

PYWAKE_BUILD = "pywake_build"
PYWAKE_CALC = "pywake_calc"
PLUGIN = "plugin"
ENVIRONMENT = "environment"

_PDW, _A2A, _PUD = "PropagateDownwind", "All2AllIterative", "PropagateUpDownIterative"
_ITERATIVE_SUMS = ("WeightedSum", "CumulativeWakeSum")
def _is_false(value) -> bool:
    """``False``, or the integer 0, which PyWake takes as the same index (deficit_model.py:20)."""
    return value is False or (type(value) is int and value == 0)


WS_REFERENCE_REFUSED = ("El complemento solo admite la referencia del escalado «{reference}» con PropagateDownwind, "
                        "TurboGaussianDeficit con use_effective_ws = False y SquaredSum, sin bloqueo (la composición de "
                        "TurbOPark).")
# The resolutions name only options that take the cause away without another rule (decision 6.4 of #64); SquaredSum,
# never in a blockage (it stops with a speed-up, 6.3).
_NODE_ROTORS = "Elige rotor «Ninguno», RotorCenter, CGIRotorAvg o EqGridRotorAvg."


_OTHER_SUM = {(False, False): "Elige Suelo «Ninguno», o LinearSum, SquaredSum o MaxSum.",
              (False, True): "Elige Suelo «Ninguno», o LinearSum, SquaredSum o MaxSum y una superposición propia para "
                             "MultiMirror.",
              (True, False): "Para el ráster, elige Suelo «Ninguno», o LinearSum, SquaredSum o MaxSum.",
              (True, True): "Para el ráster, elige Suelo «Ninguno», o LinearSum, SquaredSum o MaxSum y una "
                            "superposición propia para MultiMirror."}


_PLAIN_SUM = {False: "Elige LinearSum, SquaredSum o MaxSum.",
              True: "Elige LinearSum, SquaredSum o MaxSum y una superposición propia para MultiMirror."}


# The resolution of R8 with a ground (another rotor alone would be R9, R9d or, in the map, R9e): no ground and another
# rotor, or another sum (with R12 after it, and a sum of its own for MultiMirror).
_R8_GROUND = {False: "Elige Suelo «Ninguno» con rotor Ninguno, CGIRotorAvg o EqGridRotorAvg, o LinearSum, SquaredSum o "
                     "MaxSum.",
              True: "Elige Suelo «Ninguno» con rotor Ninguno, CGIRotorAvg o EqGridRotorAvg, o LinearSum, SquaredSum o "
                    "MaxSum y una superposición propia para MultiMirror."}


# The resolution of R9f: All2AllIterative as it is where it calculates ("a2a"); with a ground it stops with (R9 from the
# first turbine, R9d), All2AllIterative without the ground (a sum of its own for the ground would keep R9e in the map,
# as in R9d), and another sum (with R12 after it, and a sum of its own for MultiMirror). Either change makes PyWake
# evaluate what CumulativeWakeSum leaves out with PUD: a cause in the ground (a sum of its own it cannot call, R18; a
# None, R19), both without the ground ("no_ground"); one in the deficit (ct2a or deltawD None), neither ("blockage").
_R9F = {"a2a": "Elige LinearSum para el bloqueo, cambia a All2AllIterative o a LinearSum, SquaredSum o MaxSum como "
               "superposición de estelas, o quita el bloqueo.",
        "blockage": "Elige LinearSum para el bloqueo, o quita el bloqueo.",
        "no_ground": "Elige LinearSum para el bloqueo, cambia a All2AllIterative o a LinearSum, SquaredSum o MaxSum como "
                     "superposición de estelas con Suelo «Ninguno», o quita el bloqueo.",
        False: "Elige LinearSum para el bloqueo, cambia a All2AllIterative con Suelo «Ninguno» o a LinearSum, SquaredSum "
               "o MaxSum como superposición de estelas, o quita el bloqueo.",
        True: "Elige LinearSum para el bloqueo, cambia a All2AllIterative con Suelo «Ninguno» o a LinearSum, SquaredSum "
              "o MaxSum como superposición de estelas con una superposición propia para MultiMirror, o quita el "
              "bloqueo."}


def _r12_after(config: WakeConfig) -> bool:
    """Whether LinearSum, SquaredSum or MaxSum would fall into R12: MultiMirror inheriting it under a rotor average."""
    ground = config.ground
    return (ground is not None and ground.name == "MultiMirror" and ground.params.get("superpositionModel") is None
            and config.rotor is not None)


def _other_sum(config: WakeConfig, raster: bool = False) -> str:
    """The resolution of R9, R9d and R9e: no ground, or a sum PyWake calls with one array (with R12, and a sum of its
    own for MultiMirror)."""
    return _OTHER_SUM[raster, _r12_after(config)]
_NOJ = ("NOJDeficit", "NOJLocalDeficit", "TurboNOJDeficit")


@dataclass(frozen=True)
class Frontier:
    """Where PyWake stops with a configuration that fails only when it evaluates a model between turbines or at the
    points of the map (decision 6.1 of #64; evidencias/consistencia/fronteras.md): the number of turbines from which
    it stops with All2AllIterative (``a2a``) and with PropagateDownwind and PropagateUpDownIterative (``others``), 1
    being any layout and ``None`` never; and the one from which the map of the raster stops (``map_from``; ``None``:
    only where the AEP does)."""

    a2a: Optional[int] = 1
    others: Optional[int] = 2
    map_from: Optional[int] = 1

    def from_turbines(self, engine: str) -> Optional[int]:
        return self.a2a if engine == _A2A else self.others


# The failures of interaction: All2AllIterative evaluates every turbine, itself too, so it fails with one; the other
# engines from the second turbine; the map at its points.
INTERACTION = Frontier()


@dataclass(frozen=True)
class Issue:
    """One reason not to calculate. ``message`` and ``resolution`` are Spanish templates filled with ``data``;
    ``frontier``, where PyWake stops with it when that depends on the layout (``None``: with any); ``scope``, the
    sentence that says it, added by ``layout_issues`` and ``map_issues``."""

    code: str
    position: str
    origin: str
    message: str
    resolution: str = ""
    data: Mapping[str, Any] = field(default_factory=dict)
    frontier: Optional[Frontier] = None
    scope: Optional[LogText] = None

    @property
    def text(self) -> str:
        """The message and its resolution, in Spanish (the source language)."""
        return self.translated(lambda t: t)

    def log_text(self) -> LogText:
        """The message and its resolution as a translatable template (translated when shown)."""
        parts = [log_text(t, **self.data) for t in (self.message, self.resolution) if t]
        parts += [self.scope] if self.scope is not None else []
        return log_text(" ".join(f"{{p{k}}}" for k in range(len(parts))), **{f"p{k}": p for k, p in enumerate(parts)})

    def translated(self, tr: Callable[[str], str]) -> str:
        """The message and its resolution translated with ``tr``; the data that are templates are translated too."""
        parts = [shown(log_text(t, **self.data), tr) for t in (self.message, self.resolution) if t]
        parts += [shown(self.scope, tr)] if self.scope is not None else []
        return " ".join(parts).strip()


# The frontier of the cause (another one may stop the configuration before).
_LAYOUT_SCOPES = {2: "Por esta causa, con {engine}, PyWake {version} se detiene desde la segunda turbina.",
                  3: "Por esta causa, con {engine}, PyWake {version} se detiene desde la tercera turbina."}
_MAP_SCOPES = {1: "Por esta causa, el mapa del ráster no se calcula, ni con una sola turbina.",
               2: "Por esta causa, el mapa del ráster no se calcula desde la segunda turbina."}


def _always(issue: Issue, engine: str) -> bool:
    return issue.frontier is None or issue.frontier.from_turbines(engine) == 1


def map_issues(config: WakeConfig, n_turbines: Optional[int] = None) -> List[Issue]:
    """What keeps the flow map of the wake raster from being calculated with a configuration the AEP calculates: the
    failures of interaction whose map fails with any layout or, with ``n_turbines`` (the turbines the raster
    simulates), from that number (decision 6.1 of #64), and R9e.

    R9e: with PropagateDownwind or PropagateUpDownIterative, CumulativeWakeSum and a ground model simulate, but the
    flow map fails (``NotImplementedError: calc_deficit_convection (WeightedSum) cannot be used in combination with
    GroundModels``; with All2AllIterative the AEP refuses it, R9d; evidencias/rama_r1/barrido_mapa.py).
    """
    engine = config.engine.name
    rules = _rules(config)
    if any(_always(i, engine) for i in rules):
        return []  # refused by validate
    out = [replace(i, scope=log_text(_MAP_SCOPES[i.frontier.map_from])) for i in rules
           if i.frontier is not None and i.frontier.map_from is not None and i.frontier.map_from <= (n_turbines or 1)]
    if config.superposition.name == "CumulativeWakeSum" and config.ground is not None:
        out.append(Issue("R9e", GROUND, PYWAKE_CALC,
                         "PyWake no calcula el mapa de flujo con CumulativeWakeSum y un modelo de suelo (el AEP sí).",
                         _other_sum(config, raster=True), {}))
    return out


def layout_issues(config: WakeConfig, n_turbines: Optional[int] = None) -> List[Issue]:
    """What PyWake refuses only from the second turbine or later (decision 6.1 of #64: the failures of interaction
    with PropagateDownwind and PropagateUpDownIterative, some with All2AllIterative too, and R9f), checked where the
    number of turbines is known, before simulating (``None``: not known yet, for the notes of the dialog)."""
    if n_turbines is not None and n_turbines < 2:
        return []
    import py_wake
    engine = config.engine.name
    rules = _rules(config)
    if any(_always(i, engine) for i in rules):
        return []  # refused by validate
    out = []
    for i in rules:
        start = i.frontier.from_turbines(engine) if i.frontier is not None else None
        if start is not None and start > 1 and (n_turbines is None or n_turbines >= start):
            out.append(replace(i, scope=log_text(_LAYOUT_SCOPES[start], engine=engine, version=py_wake.__version__)))
    return out


def issues_log_text(issues: List[Issue]) -> LogText:
    """The reasons of a refusal, joined with «; », as a template whose data are the reasons (translated when
    shown)."""
    return log_text("; ".join(f"{{r{k}}}" for k in range(len(issues))),
                    **{f"r{k}": i.log_text() for k, i in enumerate(issues)})


def missing_gaussian_overlap_modules() -> List[str]:
    """The modules GaussianOverlapAvgModel needs to read its table and that are not installed (decision 10, D8)."""
    missing = []
    for name in ("h5py", "h5netcdf"):
        try:
            importlib.import_module(name)
        except Exception:
            missing.append(name)
    return missing


INSTALL_PIP = ("Si falta, puedes instalarlo con «python -m pip install {packages}» y reiniciar QGIS; si ya está "
               "instalado y no carga, consulta las instrucciones de instalación.")
INSTALL_PIP_PLURAL = ("Si faltan, puedes instalarlos con «python -m pip install {packages}» y reiniciar QGIS; si ya "
                      "están instalados y no cargan, consulta las instrucciones de instalación.")
INSTALL_WINDOWS_H5PY = ("En QGIS para Windows, h5py no se instala con pip, porque su HDF5 puede chocar con la que ya "
                        "carga QGIS: consulta las instrucciones de instalación.")
INSTALL_WINDOWS_H5PY_AND_PIP = ("Puedes instalar el resto con «python -m pip install {packages}» y reiniciar QGIS; "
                                "en QGIS para Windows, h5py no se instala con pip, porque su HDF5 puede chocar con la "
                                "que ya carga QGIS: consulta las instrucciones de instalación.")


def install_hint(missing: List[str]) -> LogText:
    """How to install the ``missing`` libraries of GaussianOverlapAvgModel, as the installation instructions say: in
    QGIS for Windows, h5py is not installed with pip, and h5netcdf from 1.8, which no longer depends on h5py."""
    pip = ['"h5netcdf>=1.8"' if m == "h5netcdf" else m for m in missing
           if not (m == "h5py" and sys.platform == "win32")]
    if len(pip) == len(missing):
        return log_text(INSTALL_PIP if len(pip) == 1 else INSTALL_PIP_PLURAL, packages=" ".join(pip))
    if pip:
        return log_text(INSTALL_WINDOWS_H5PY_AND_PIP, packages=" ".join(pip))
    return log_text(INSTALL_WINDOWS_H5PY)


# Lists PyWake unpacks (``c1, c2 = self.cTI``, when calculating): another length is a failure of interaction (R20).
_UNPACKED = {("TurboGaussianDeficit", "cTI"), ("TurboNOJDeficit", "cTI")}


def _not_an_argument(position: str, cls: str, arg: str, route: str = "") -> Issue:
    """R14 for a name that is not an argument the plugin offers: one it leaves out, with its reason (``subordinates.
    EXCLUDED``), or one the class does not have."""
    reason = next((e.reason for e in _sub.excluded_of(cls) if e.name == arg), None)
    if reason is not None:
        return Issue("R14", position, PLUGIN, "El complemento no ofrece «{arg}» de {cls}: {reason}", "",
                     {"cls": cls, "arg": route + arg, "reason": log_text(reason)})
    return Issue("R14", position, PLUGIN, "{cls} no admite el argumento «{arg}».", "", {"cls": cls, "arg": route + arg})


def _check_arguments(position: str, comp: Component, entry: _cat.ClassEntry, issues: List[Issue]) -> None:
    """Every editable argument present, nothing else, each value one the contract carries (decision 6.2 of #64: whether
    PyWake takes it, its construction decides)."""
    defaults = _cat.signature_defaults(entry)
    allowed = set(entry.params) | set(entry.fixed) | {a.name for a in _sub.args_of(comp.name)}
    unknown = sorted(set(comp.params) - allowed)
    missing = sorted(set(entry.params) - set(comp.params))
    for name in unknown:
        issues.append(_not_an_argument(position, comp.name, name))
    for name in missing:
        issues.append(Issue("R14", position, PLUGIN, "Falta el argumento «{arg}» de {cls}.", "",
                            {"cls": comp.name, "arg": name}))
    for name in entry.params:
        if name not in comp.params:
            continue
        kind, value = _cat.param_kind(defaults[name]), comp.params[name]
        if value is None:
            continue  # an explicit None reaches PyWake, which decides (API contract, P5 a)
        ok = {
            "bool": _number,
            "ct2a": lambda v: v in _cat.CT2A_FUNCTIONS,
            "list": _numbers,
            "number": _number,
        }[kind](value)
        if not ok:
            issues.append(Issue("R14", position, PLUGIN, "Valor no válido para «{arg}» de {cls}: {value!r}.", "",
                                {"cls": comp.name, "arg": name, "value": _Shown(value)}))
    _check_subordinates(position, comp, issues, skip=set(entry.params) | set(entry.fixed))


def _check_subordinates(position: str, comp: Component, issues: List[Issue], path: str = "",
                        skip: Optional[set] = None) -> None:
    """The arguments of ``subordinates`` (#64) of a component, recursively: each value of the type of its control, a
    nested component an option of its family for this owner (and installed); ``None`` where PyWake decides (R19, or
    its error when building); an argument the table does not know, refused (R14). ``path``: the route
    of a nested component, for the messages; ``skip``: the arguments of the catalogue entry, checked apart."""
    for name, value in comp.params.items():
        if skip and name in skip:
            continue
        spec, arg = _sub.arg_spec(comp.name, name), path + name
        if spec is None:
            issues.append(_not_an_argument(position, comp.name, name, path))
            continue
        if value is None:
            # None is a value of the contract; PyWake decides (R19, or its error when building). The integers of
            # EqGridRotorAvg and MultiMirror are not built by the validation with their value (one point, no
            # repetition): None there, which PyWake refuses when building, is refused here.
            if spec.kind == _sub.INT:
                issues.append(Issue("R14", position, PLUGIN, "Valor no válido para «{arg}» de {cls}: {value!r}.", "",
                                    {"cls": comp.name, "arg": arg, "value": _Shown(value)}))
            continue
        if spec.kind == _sub.COMPONENT:
            if not isinstance(value, Component) or value.name not in [o.name for o in _sub.options(spec)]:
                issues.append(Issue("R14", position, PLUGIN, "{option} no es una opción de «{arg}» de {cls}.", "",
                                    {"option": getattr(value, "name", value), "arg": arg, "cls": comp.name}))
                continue
            try:
                _sub.resolve_name(value.name)
            except Exception:
                issues.append(Issue("R14", position, ENVIRONMENT, "La instalación de PyWake no tiene la clase {cls}.",
                                    "", {"cls": value.name}))
                continue
            _check_subordinates(position, value, issues, f"{arg} · ")
            continue
        ok = {
            _sub.NUMBER: _number, _sub.NUMBER_OR_NONE: _number,
            # np.linspace and range need an integer; a bool is one (EqGridRotorAvg(True) calculates).
            _sub.INT: lambda v: isinstance(v, int) and _number(v),
            _sub.BOOL: _number,
            _sub.CT2A: lambda v: v in _cat.CT2A_FUNCTIONS,
            _sub.LIST: _numbers,
            # A number: PyWake looks it up in a dictionary (CGIRotorAvg(7.0) is CGIRotorAvg(7), rotor_avg_model.py:
            # 135-150; s_b_entradas, cgi_float); another, PyWake refuses it when building (KeyError), at its position.
            _sub.CHOICE: _number,
        }[spec.kind](value)
        if not ok:
            issues.append(Issue("R14", position, PLUGIN, "Valor no válido para «{arg}» de {cls}: {value!r}.", "",
                                {"cls": comp.name, "arg": arg, "value": _Shown(value)}))


def _one_point(comp: Optional[Component]) -> Optional[Component]:
    """``comp`` with every EqGridRotorAvg in it (itself or nested) at n = 1 and every MultiMirror at one repetition at
    most (its list of mirrors has one element per repetition, and the first already uses mirror_height,
    ground_models.py:89-94)."""
    if comp is None:
        return None
    params = {k: _one_point(v) if isinstance(v, Component) else v for k, v in comp.params.items()}
    if comp.name == "EqGridRotorAvg":
        params["n"] = 1
    if comp.name == "MultiMirror":
        params["n_reps"] = min(params.get("n_reps", 1), 1)
    return Component(comp.name, params)


class _Shown:
    """A refused value in its message: its ``repr``, or, for an integer Python cannot write as text, its size."""

    def __init__(self, value: Any) -> None:
        self.value = value

    def __repr__(self) -> str:
        return _shown(self.value)


def _shown(v: Any) -> str:
    """``repr(v)``, with each integer Python cannot write as text given by its size, at any depth."""
    try:
        return repr(v)
    except ValueError:
        pass
    if isinstance(v, int):
        return f"<int de {v.bit_length()} bits>"
    if isinstance(v, Mapping):
        return "{" + ", ".join(f"{_shown(k)}: {_shown(x)}" for k, x in v.items()) + "}"
    if isinstance(v, (list, tuple)):
        inner = ", ".join(_shown(x) for x in v)
        return f"[{inner}]" if isinstance(v, list) else f"({inner})"
    return f"<{type(v).__name__}>"


def _number(v: Any) -> bool:
    """A number of the contract: a bool, an int of any size or a float, NaN and infinities included. What PyWake does
    with it is its own: an error when building is refused (the construction of the validation), one when calculating
    with a given value is an error of the calculation (decision 1 of #46a; decisions 5 and 6.2 of #64). An integer
    Python cannot write as text (over 4300 digits by default) is not one: the contract could not record it."""
    if isinstance(v, (bool, float)):
        return True
    if not isinstance(v, int):
        return False
    try:
        str(v)
    except ValueError:
        return False
    return True


def _numbers(v: Any) -> bool:
    """A list of numbers, of any length: the extra elements PyWake does not read are kept and warned; with fewer, or
    another length where PyWake unpacks it, PyWake fails where it reads them (R20, decision 6.1 of #64)."""
    return isinstance(v, (list, tuple)) and all(_number(x) for x in v)


def _known(position: str, comp: Optional[Component], issues: List[Issue]) -> bool:
    """The component is an option of the catalogue at its position and the installed PyWake has its class (R14)."""
    if comp is None:
        return True
    try:
        e = _f.catalogue_entry(position, comp)
    except KeyError:
        issues.append(Issue("R14", position, PLUGIN, "{option} no es una opción de {position}.", "",
                            {"option": comp.label, "position": _cat.position_label(position)}))
        return False
    try:
        _cat.resolve_class(e)
    except _cat.ClassUnavailable as exc:
        issues.append(Issue("R14", position, ENVIRONMENT, "{error}", "", {"error": exc.args[0]}))
        return False
    n_issues = len(issues)
    if position in (DEFICIT, BLOCKAGE):
        _check_arguments(position, comp, e, issues)
    else:
        _check_subordinates(position, comp, issues, skip=set(e.fixed))
    return len(issues) == n_issues


def validate(config: WakeConfig, *, check_environment: bool = True) -> List[Issue]:
    """The issues that keep ``config`` from being calculated with any layout, in the order of the dialog; empty if
    none. What PyWake refuses only from the second turbine is ``layout_issues``; only in the map, ``map_issues``.

    ``check_environment=False`` leaves out R13 (GaussianOverlap without h5py/h5netcdf), which the dialog handles
    with its own warning and the user's choice (decision 10).
    """
    engine = config.engine.name
    return [i for i in _rules(config, check_environment=check_environment) if _always(i, engine)]


def _rules(config: WakeConfig, *, check_environment: bool = True) -> List[Issue]:
    """Every rule that applies to ``config``, each with its frontier (``None``: with any layout). The reasons of a
    refusal at a stage (building and what fails with any layout, ``validate``; the simulation with the turbines,
    ``layout_issues``; the map, ``map_issues``) are every cause that stops PyWake there on its own, whichever it meets
    first; an earlier stage hides the later ones; a cause PyWake can never reach (the arguments of an object it
    cannot call, the table of GaussianOverlap where it is never read) is not one."""
    issues: List[Issue] = []
    positions = (ENGINE, DEFICIT, ROTOR, GROUND, SUPERPOSITION, TURBULENCE, BLOCKAGE, BLOCKAGE_SUPERPOSITION)
    if not all([_known(p, config.component(p), issues) for p in positions]):
        return issues
    if (config.blockage is None) != (config.blockage_superposition is None):
        issues.append(Issue("R14", BLOCKAGE_SUPERPOSITION, PLUGIN,
                            "La superposición del bloqueo se indica si y solo si hay bloqueo.", "", {}))
        return issues
    # R21 (plan of the predefined models, M4): the reference of the deficit's scaling, only in the composition of
    # TurbOPark, the one measured (Nygaard_2022); any other, a refusal of the plugin, not of PyWake.
    if config.deficit_ws_reference is not None and not (
            config.deficit_ws_reference in _cfg.DEFICIT_WS_REFERENCES and config.engine.name == _PDW
            and config.deficit.name == "TurboGaussianDeficit" and _is_false(config.deficit.params.get("use_effective_ws"))
            and config.superposition.name == "SquaredSum" and config.blockage is None):
        issues.append(Issue("R21", DEFICIT, PLUGIN, WS_REFERENCE_REFUSED, "",
                            {"reference": config.deficit_ws_reference}))
        return issues

    # R15 before building: some technical limits make PyWake fail when building (EqGridRotorAvg with n ≤ −3).
    limits = _limit_issues(config)
    if limits:
        return issues + limits
    engine, sup = config.engine.name, config.superposition.name
    rotor = config.rotor.name if config.rotor else None
    ground = config.ground.name if config.ground else None
    position = DEFICIT
    # The rules below look at the classes of the built objects, never at the nodes of a rotor average nor at the
    # mirrors of a ground: built with one point per EqGridRotorAvg and no repetition of MultiMirror, whose n and n_reps
    # have no maximum (building them would cost, at each check, what the calculation costs).
    cheap = replace(config, rotor=_one_point(config.rotor), ground=_one_point(config.ground),
                    blockage=_one_point(config.blockage), turbulence=_one_point(config.turbulence))
    try:
        deficit = _f.build_deficit(cheap)
        position = BLOCKAGE
        blockage = _f.build_blockage(cheap)
        position = TURBULENCE
        _f.build_component(TURBULENCE, cheap.turbulence)  # an error when building it, refused at its position
    except _f.FactoryError as exc:
        return [Issue("build", exc.position, PYWAKE_BUILD, "{error}", "", {"error": exc.args[0]})]
    except _cat.ClassUnavailable as exc:
        # A function the installed PyWake does not have (a ct2a): the environment, with its translatable reason.
        return [Issue("R14", position, ENVIRONMENT, "{error}", "", {"error": exc.args[0]})]
    except Exception as exc:
        return [Issue("build", DEFICIT, PLUGIN, "{error}", "", {"error": f"{type(exc).__name__}: {exc}"})]
    d = {"deficit": config.deficit.name, "engine": engine, "sup": sup, "rotor": rotor, "ground": ground,
         "blockage": config.blockage.name if config.blockage else None,
         "bsup": config.blockage_superposition.name if config.blockage_superposition else None}

    # R1: PropagateDownwind has no blockage argument. PropagateUpDownIterative, only where its blockage superposition
    # takes it (not R5, SquaredSum with up- and downstream effects; not R9f, MaxSum with an iterative sum).
    if engine == _PDW and config.blockage is not None:
        pud_ok = ("use_effective_ws" in config.deficit.params
                  and not (d["bsup"] == "SquaredSum" and not blockage.upstream_only)
                  and not (d["bsup"] == "MaxSum" and sup in _ITERATIVE_SUMS))
        issues.append(Issue("R1", BLOCKAGE, PYWAKE_BUILD, "PropagateDownwind no admite bloqueo.",
                            "Elige All2AllIterative (o PropagateUpDownIterative, con use_effective_ws en el déficit y en el "
                            "bloqueo), o quita el bloqueo." if pud_ok else
                            "Elige All2AllIterative, o quita el bloqueo.", d))
    # R2: a deficit that uses the effective TI needs a turbulence model (engineering_models.py:98).
    if "TI_eff_ilk" in deficit.args4deficit and config.turbulence is None:
        turb = _cat.entry(DEFICIT, config.deficit.name).predefined_turbulence
        issues.append(Issue("R2", TURBULENCE, PYWAKE_BUILD,
                            "{deficit} usa la TI efectiva (use_effective_ti = True) y PyWake exige un modelo de "
                            "turbulencia.",
                            ("Elige una turbulencia (el modelo predefinido de PyWake usa {turb}) o desmarca "
                             "use_effective_ti." if turb else "Elige una turbulencia o desmarca use_effective_ti."),
                            dict(d, turb=log_text(turb) if turb else "")))
    if engine == _PUD:
        # R3: PUD needs a deficit that scales with the effective wind speed (engineering_models.py:539-540).
        if deficit.WS_key != "WS_eff_ilk":
            has_param = "use_effective_ws" in config.deficit.params
            issues.append(Issue(
                "R3", DEFICIT, PYWAKE_BUILD,
                "PropagateUpDownIterative exige un déficit que escale con la velocidad efectiva.",
                "Marca use_effective_ws en los parámetros del déficit." if has_param else
                "{deficit} no tiene use_effective_ws: elige otro motor u otra clase.", d))
        # R4: and a blockage model that scales with it (engineering_models.py:541-542).
        if blockage is not None and blockage.WS_key != "WS_eff_ilk":
            issues.append(Issue("R4", BLOCKAGE, PYWAKE_BUILD,
                                "PropagateUpDownIterative exige un bloqueo que escale con la velocidad efectiva.",
                                "Marca use_effective_ws en los parámetros del bloqueo.", d))
        # R5: SquaredSum in a blockage with up- and downstream effects (engineering_models.py:553-557). With the
        # iterative sums MaxSum is not a way out (R9f).
        if blockage is not None and d["bsup"] == "SquaredSum" and not blockage.upstream_only:
            issues.append(Issue("R5", BLOCKAGE_SUPERPOSITION, PYWAKE_CALC,
                                "PropagateUpDownIterative no admite SquaredSum en un bloqueo con efecto aguas arriba y "
                                "abajo.", "Elige LinearSum para el bloqueo." if sup in _ITERATIVE_SUMS else
                                "Elige LinearSum o MaxSum para el bloqueo.", d))
    # R6: the engines call the blockage superposition with a single array (engineering_models.py:408, 697, 1113). Its
    # resolution leaves out what R5 or R9f would refuse with the same choices.
    if d["bsup"] in _ITERATIVE_SUMS:
        max_ok = not (engine == _PUD and sup in _ITERATIVE_SUMS)
        # SquaredSum is not proposed: it stops with a speed-up of the blockage (decision 8 of #46a, 6.3 of #64).
        resolution = "Elige LinearSum o MaxSum." if max_ok else "Elige LinearSum."
        issues.append(Issue("R6", BLOCKAGE_SUPERPOSITION, PYWAKE_CALC,
                            "{bsup} no se puede usar como superposición del bloqueo: los motores de PyWake la llaman con "
                            "un único array y {bsup} necesita más datos.", resolution, d, INTERACTION))
    if sup in _ITERATIVE_SUMS:
        from py_wake.deficit_models.deficit_model import ConvectionDeficitModel
        from py_wake.rotor_avg_models.rotor_avg_model import NodeRotorAvgModel, WSPowerRotorAvg
        rotor_obj = deficit.rotorAvgModel
        # R7 (engineering_models.py:88-89).
        if not isinstance(deficit, ConvectionDeficitModel):
            issues.append(Issue("R7", SUPERPOSITION, PYWAKE_BUILD,
                                "{sup} exige un déficit de convección (ConvectionDeficitModel); {deficit} no lo es.",
                                _PLAIN_SUM[_r12_after(config)], d))
        # R8 (engineering_models.py:90-94).
        elif rotor_obj is not None and (not isinstance(rotor_obj, NodeRotorAvgModel) or isinstance(rotor_obj, WSPowerRotorAvg)):
            issues.append(Issue("R8", ROTOR, PYWAKE_BUILD,
                                "WeightedSum y CumulativeWakeSum solo funcionan en PyWake con promedios de rotor por "
                                "nodos que no sean WSPowerRotorAvg; {rotor} no lo es.",
                                # NOJ does not take these sums with any rotor (R9b, R9c): another sum.
                                _PLAIN_SUM[_r12_after(config)] if config.deficit.name in _NOJ else
                                _R8_GROUND[_r12_after(config)] if ground is not None else
                                "Elige rotor Ninguno, CGIRotorAvg o EqGridRotorAvg.", d))
        elif sup == "WeightedSum" and config.deficit.name in _NOJ:
            # R9b (deficit_models/noj.py:53).
            issues.append(Issue("R9b", SUPERPOSITION, PYWAKE_CALC,
                                "WeightedSum no está implementado en PyWake para los déficits NOJ.",
                                _PLAIN_SUM[_r12_after(config)], d, INTERACTION))
        elif sup == "WeightedSum" and ground is not None:
            # R9 (deficit_models/gaussian.py:79-81).
            issues.append(Issue("R9", GROUND, PYWAKE_CALC, "WeightedSum no admite modelo de suelo.",
                                _other_sum(config), d, INTERACTION))
        elif sup == "CumulativeWakeSum" and config.deficit.name in _NOJ:
            # R9c.
            issues.append(Issue("R9c", SUPERPOSITION, PYWAKE_CALC,
                                "CumulativeWakeSum no funciona en PyWake con los déficits NOJ.",
                                _PLAIN_SUM[_r12_after(config)], d, INTERACTION))
        elif (sup == "CumulativeWakeSum" and engine == _A2A and ground is not None
              and config.ground.params.get("superpositionModel") is None):
            # R9d: the ground inherits CumulativeWakeSum, which PyWake calls with one array; with a sum of its own the
            # ground calculates (and has no effect, decision 23a).
            issues.append(Issue("R9d", GROUND, PYWAKE_CALC,
                                "CumulativeWakeSum con All2AllIterative no admite un suelo que herede su superposición.",
                                _other_sum(config), d))  # an own sum would leave R9e
    if rotor == "AreaOverlapAvgModel":
        from py_wake.deficit_models.deficit_model import WakeRadiusTopHat
        # R10 (rotor_avg_models/area_overlap_model.py:15-18).
        if not isinstance(deficit, WakeRadiusTopHat):
            issues.append(Issue("R10", ROTOR, PYWAKE_CALC,
                                "AreaOverlapAvgModel solo tiene sentido con déficits de sombrero de copa (NOJ).",
                                _NODE_ROTORS, d, INTERACTION))
    if rotor == "GaussianOverlapAvgModel":
        # R11 (rotor_avg_models/gaussian_overlap_model.py:36-38; AttributeError with the NOJ deficits).
        if not hasattr(deficit, "sigma_ijlk") or config.deficit.name in _NOJ:
            issues.append(Issue("R11", ROTOR, PYWAKE_CALC, "GaussianOverlapAvgModel necesita una estela gaussiana.",
                                _NODE_ROTORS, d, INTERACTION))
        # R13 (decision 10): the table is read when the rotor is evaluated (gaussian_overlap_model.py:14-20, 42), unless
        # an earlier stage stops (a rule with any layout: building, R5). As the rotor of a blockage or of a turbulence
        # it is never read (R16, R17: :36-38).
        elif check_environment and not any(i.frontier is None for i in issues):
            issues += _missing_modules_issue(ROTOR, d, INTERACTION)
    # R12 (ground_models/ground_models.py:141): MultiMirror without a sum of its own looks for the one of the deficit
    # it wraps, which a rotor average hides; with its own sum it calculates. In the deficit and in the blockage.
    if (ground == "MultiMirror" and config.ground.params.get("superpositionModel") is None
            and deficit.rotorAvgModel is not None and sup in ("LinearSum", "SquaredSum", "MaxSum")):
        issues.append(Issue("R12", GROUND, PYWAKE_CALC, "MultiMirror sin superposición propia no funciona en PyWake con "
                            "un promedio de rotor.",
                            "Elige rotor «Ninguno», Mirror, o dale a MultiMirror una superposición propia (LinearSum, "
                            "SquaredSum o MaxSum).", d,
                            INTERACTION))
    if config.blockage is not None:
        b_ground = config.blockage.params.get("groundModel")
        if (isinstance(b_ground, Component) and b_ground.name == "MultiMirror"
                and b_ground.params.get("superpositionModel") is None
                and config.blockage.params.get("rotorAvgModel") is not None):
            issues.append(Issue("R12", BLOCKAGE, PYWAKE_CALC,
                                "En el bloqueo, MultiMirror sin superposición propia no funciona en PyWake con un "
                                "promedio de rotor.", "Quita el promedio de rotor del bloqueo, usa Mirror, o dale a "
                                "MultiMirror una superposición propia (LinearSum o MaxSum).", d, INTERACTION))
    # R9f: with PropagateUpDownIterative and WeightedSum or CumulativeWakeSum the downwind pass keeps no blockage of
    # its turbines (engineering_models.py:798-824), and from the second turbine on MaxSum as the blockage superposition
    # looks for the maximum of that empty list (engineering_models.py:663, 697; superposition_models.py:66).
    interaction = _interaction_issues(config, check_environment)
    if engine == _PUD and d["bsup"] == "MaxSum" and sup in _ITERATIVE_SUMS:
        import py_wake
        own = config.ground.params.get("superpositionModel") if ground is not None else None
        # The causes CumulativeWakeSum leaves out of the AEP with PUD (frontier ``others`` None), by position.
        hidden = {i.position for i in interaction if i.frontier is not None and i.frontier.others is None}
        key = ("blockage" if hidden - {GROUND} else
               "no_ground" if hidden or (isinstance(own, Component) and own.name in _SUMS_OF_ONE_ARRAY_NOT) else
               "a2a" if ground is None or (sup == "CumulativeWakeSum" and own is not None) else _r12_after(config))
        issues.append(Issue("R9f", BLOCKAGE_SUPERPOSITION, PYWAKE_CALC,
                            "PyWake {version} falla al calcular con PropagateUpDownIterative, {sup} y MaxSum como "
                            "superposición del bloqueo: desde la segunda turbina busca el máximo de una lista vacía de "
                            "contribuciones del bloqueo.", _R9F[key],
                            dict(d, version=py_wake.__version__), Frontier(a2a=None, others=2, map_from=None)))
    issues += interaction
    return issues


_OVERLAPS = ("AreaOverlapAvgModel", "GaussianOverlapAvgModel")
_SUMS_OF_ONE_ARRAY_NOT = ("WeightedSum", "CumulativeWakeSum", "SqrMaxSum")  # what a ground cannot call with one array
# None where PyWake fails, measured (evidencias/consistencia/frontera_q5d.salida.txt, frontera_r2.salida.txt): the
# failure of interaction unless said here; ``None`` as frontier: with any layout.
_NONE_FRONTIERS: Dict[tuple, Optional[Frontier]] = {
    ("PropagateUpDownIterative", "convergence_tolerance"): None,
    # alpha weighs the second contribution and later ones (superposition_models.py:238-243): a turbine of PDW and PUD
    # gets one from each turbine before it, the map one from each turbine (evidencias/consistencia/q5d_r1_extra).
    ("CumulativeWakeSum", "alpha"): Frontier(a2a=2, others=3, map_from=2),
}
_NONE_CALCULATES = {("ZongGaussianDeficit", "ctlim")}  # PyWake keeps it and never uses it
# None where PyWake stops depending on the values of the calculation: an error of the calculation (decision 1 of #46a).
# PUD compares max_iter only when its first pass does not meet the tolerance (engineering_models.py:589): with one
# turbine, or without blockage, it meets it (tests.test_wake_interaction). WeightedSum reads max_err, max_iter and
# weight_limit only when a contribution passes its delta (superposition_models.py:111-154).
_NONE_DEPENDS_ON_VALUES = {("PropagateUpDownIterative", "max_iter"), ("WeightedSum", "max_err"),
                           ("WeightedSum", "max_iter"), ("WeightedSum", "weight_limit")}
# With CumulativeWakeSum, PropagateDownwind and PropagateUpDownIterative take from the deficit only its width: the
# arguments it leaves without effect (decision 23a) are not evaluated in the AEP (the map does evaluate them), nor is
# its ground (engineering_models.py:809-814).
_NO_EFFECT_WITH_CUMULATIVE = ("ct2a", "deltawD")
# Rathmann and RathmannScaled use limiter only to take the wake out (rathmann.py:95-96, 146; deficit_model.py:115).
_UNUSED_WITHOUT = {("Rathmann", "limiter"): "exclude_wake", ("RathmannScaled", "limiter"): "exclude_wake"}
_NONE_MESSAGE = "En «{where} · {arg}», con None, PyWake {version} se detiene al usar ese argumento."
_SHORT_MESSAGE = ("En «{where} · {arg}», la lista tiene {count} elementos y PyWake {version} usa {length}: se detiene al "
                  "leerla.")
_OVERLAP_MESSAGE = ("{rotor} como promedio de rotor de {owner} no funciona en PyWake {version}: se detiene al evaluarlo "
                    "entre turbinas.")
_GROUND_SUM_MESSAGE = ("{sum} como superposición propia del suelo de «{where}» no funciona en PyWake {version}: el suelo "
                       "la llama con un único array.")


def _missing_modules_issue(position: str, d: Mapping[str, Any], frontier: Frontier) -> List[Issue]:
    missing = missing_gaussian_overlap_modules()
    return [Issue("R13", position, ENVIRONMENT,
                  "GaussianOverlapAvgModel necesita estas librerías, que no están disponibles: {modules}.",
                  "{install}", dict(d, modules=" ".join(missing), install=install_hint(missing)),
                  frontier)] if missing else []


def _interaction_issues(config: WakeConfig, check_environment: bool) -> List[Issue]:
    """The failures of interaction of the nested objects and of the values (decision 6.1 of #64): R16 and R17, an
    overlap as the rotor average of a blockage or of an added turbulence; R18, a sum of its own a ground cannot call;
    R19, None where PyWake uses the argument; R20, a list shorter than what PyWake reads (or, where it unpacks it,
    of another length). Each with its measured frontier."""
    import py_wake
    version = py_wake.__version__
    engine, sup = config.engine.name, config.superposition.name
    out: List[Issue] = []

    def visit(position: str, comp: Component, path: str) -> None:
        where = {"where": _cat.position_label(position), "version": version}
        entry = None
        if not path and position in (DEFICIT, BLOCKAGE):
            entry = _cat.entry(position, comp.name)
        defaults = _cat.signature_defaults(entry) if entry is not None else {}
        for name, value in comp.params.items():
            spec = _sub.arg_spec(comp.name, name)
            arg = path + name
            data = dict(where, arg=arg)
            if value is None:
                frontier: Optional[Frontier] = INTERACTION
                if entry is not None and name in entry.params:
                    if defaults.get(name) is None or (comp.name, name) in _NONE_CALCULATES:
                        continue
                    if position == DEFICIT and sup == "CumulativeWakeSum" and name in _NO_EFFECT_WITH_CUMULATIVE:
                        frontier = Frontier(others=None)
                elif spec is None or spec.none or spec.kind in (_sub.NUMBER_OR_NONE, _sub.BOOL):
                    continue  # a value, or one PyWake reads as False
                elif (comp.name, name) in _NONE_DEPENDS_ON_VALUES:
                    continue
                elif (comp.name, name) in _UNUSED_WITHOUT and not comp.params.get(
                        _UNUSED_WITHOUT[comp.name, name], defaults.get(_UNUSED_WITHOUT[comp.name, name])):
                    continue
                elif (comp.name, name) in _NONE_FRONTIERS:
                    frontier = _NONE_FRONTIERS[(comp.name, name)]
                elif spec.family == "weight":
                    continue  # an error when building
                out.append(Issue("R19", position, PYWAKE_CALC, _NONE_MESSAGE, "Indica un valor.", data, frontier))
                continue
            length = (len(defaults[name]) if entry is not None and isinstance(defaults.get(name), (list, tuple))
                      else spec.length if spec is not None and spec.kind == _sub.LIST else None)
            if length is not None and isinstance(value, (list, tuple)) and (
                    len(value) < length or ((comp.name, name) in _UNPACKED and len(value) != length)):
                out.append(Issue("R20", position, PYWAKE_CALC, _SHORT_MESSAGE, "Da a la lista sus {length} elementos.",
                                 dict(data, count=len(value), length=length), INTERACTION))
            if isinstance(value, Component):
                if name == "rotorAvgModel" and value.name in _OVERLAPS and position in (BLOCKAGE, TURBULENCE) and not path:
                    in_turbulence = position == TURBULENCE
                    if in_turbulence and value.name == "AreaOverlapAvgModel" and comp.name not in (
                            "STF2005TurbulenceModel", "STF2017TurbulenceModel"):
                        pass  # GCLTurbulence and CrespoHernandez are top-hat models: it calculates (its signature)
                    else:
                        frontier = Frontier(map_from=None) if in_turbulence else INTERACTION
                        out.append(Issue("R17" if in_turbulence else "R16", position, PYWAKE_CALC, _OVERLAP_MESSAGE,
                                         "Elige Ninguno, CGIRotorAvg o EqGridRotorAvg.",
                                         dict(where, rotor=value.name, owner=comp.name), frontier))
                if not (comp.name in ("Mirror", "MultiMirror") and name == "superpositionModel"
                        and value.name in _SUMS_OF_ONE_ARRAY_NOT):  # called with one array, it stops before its arguments
                    visit(position, value, f"{arg} · ")
        if comp.name in ("Mirror", "MultiMirror"):
            own = comp.params.get("superpositionModel")
            if isinstance(own, Component) and own.name in _SUMS_OF_ONE_ARRAY_NOT:
                label = _cat.position_label(position)
                out.append(Issue("R18", position, PYWAKE_CALC, _GROUND_SUM_MESSAGE,
                                 "Elige LinearSum, SquaredSum o MaxSum." if position == GROUND else
                                 "Elige LinearSum o MaxSum.",
                                 dict(where, sum=own.name, where=log_text("{label} · {path}", label=label,
                                                                          path=path.rstrip(" · ")) if path else label),
                                 INTERACTION))

    for position in _cat.POSITIONS:
        comp = config.component(position)
        if position == BLOCKAGE_SUPERPOSITION and comp is not None and comp.name in _ITERATIVE_SUMS:
            continue  # called with one array (R6), it stops before its arguments
        if comp is not None:
            start = len(out)
            visit(position, comp, "")
            if position == GROUND and sup == "CumulativeWakeSum":
                # PDW and PUD do not evaluate the ground of the deficit in the AEP (_NO_EFFECT_WITH_CUMULATIVE); the
                # map does (where R9e stops too).
                out[start:] = [replace(i, frontier=replace(i.frontier, others=None)) if i.frontier else i
                               for i in out[start:]]
    return out


# The technical limits of ``subordinates.LIMITS`` (R15): what PyWake refuses when building, refused before calculating
# (decision 22; decision 5 of #64: with what PyWake calculates, a warning instead), with the route of the argument.
_LIMIT_TEXTS = {
    "eqgrid_n": ("EqGridRotorAvg con n = {value} en «{where} · {arg}»: PyWake no lo construye (np.linspace con n + 2 < 0); "
                 "el mínimo es −2.",
                 lambda c, v, config: v is not None and not isinstance(v, bool) and isinstance(v, int) and v <= -3),
}


def _limit_issues(config: WakeConfig) -> List[Issue]:
    out: List[Issue] = []

    def walk(position: str, comp: Optional[Component], path: str) -> None:
        if comp is None:
            return
        for name, value in comp.params.items():
            spec = _sub.arg_spec(comp.name, name)
            if spec is None:
                continue
            if spec.limit and spec.limit in _LIMIT_TEXTS:
                text, broken = _LIMIT_TEXTS[spec.limit]
                if broken(comp, value, config):
                    out.append(Issue("R15", position, PYWAKE_BUILD, text, "Usa n ≥ −2.",
                                     {"where": _cat.position_label(position), "arg": path + name, "value": value}))
            if isinstance(value, Component):
                walk(position, value, f"{path}{name} · ")

    for position in _cat.POSITIONS:
        walk(position, config.component(position), "")
    return out

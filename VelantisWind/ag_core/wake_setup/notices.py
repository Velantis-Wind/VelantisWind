# -*- coding: utf-8 -*-
"""The notices of a calculation that never keep it from calculating: the persistent warnings of decision 19 and the
warnings of the iterative loops that did not converge (decision 9). Shared by the AEP and the wake raster."""
from __future__ import annotations

import logging

from typing import Any, Dict, List, Mapping, Optional, Tuple

import numpy as np

from . import catalog as _cat
from . import subordinates as _sub
from .config import Component, WakeConfig
from ..edge_cases import may_not_terminate, weighted_sum_argument, weighting_discarded
from ..log_text import log_text
from .validation import install_hint

__all__ = ["persistent_warnings", "superposition_warnings", "cumulative_without_effect", "convergence_warnings",
           "adaptation_notes", "result_warnings", "GO_ADAPTATION_NOTE", "GO_ADAPTATION_NOTE_PLURAL",
           "CUMULATIVE_WITHOUT_EFFECT_NOTE", "CUMULATIVE_FIELD_NOTE", "blockage_warnings", "PUD_DOWNSTREAM_BLOCKAGE_NOTE",
           "PUD_DOWNSTREAM_FIELD_NOTE", "argument_warnings", "ground_window_warnings", "ARGUMENT_TEXTS"]

CUMULATIVE_WITHOUT_EFFECT_NOTE = (
    "Configuración principal · PyWake {version} · {engine}: con CumulativeWakeSum, PyWake toma del déficit solo su "
    "anchura y el promedio de rotor de su distancia transversal, y calcula la intensidad del déficit en la "
    "superposición; por eso estos argumentos del déficit no afectan al resultado numérico por esta ruta: {args}. "
    "CumulativeWakeSum sigue usando la velocidad efectiva. Esto no elimina los requisitos de construcción ni los "
    "errores que PyWake pueda dar al evaluar. Este aviso no describe las variantes del desglose.")
PUD_DOWNSTREAM_BLOCKAGE_NOTE = ("PyWake {version}: con PropagateUpDownIterative y {sup}, la simulación de las turbinas "
                                "omite el bloqueo aguas abajo durante la pasada «down»; la pasada «up» conserva el "
                                "bloqueo aguas arriba.")
# Decision 16 (#75, row 3.15), persistent also without the breakdown (decision 6.6 of #64): the dialog says it too.
TURBULENCE_WITHOUT_EFFECT = ("{cls} no usa la TI efectiva (use_effective_ti = False, o no lo tiene): la turbulencia "
                             "elegida se calcula (la TI efectiva del resultado), pero no cambia el déficit.")
# Decision 6.3 of #64 (decision 8 of #46a): it depends on the values, so it is not refused before calculating.
SQUARED_BLOCKAGE_NOTE = ("PyWake {version}: con SquaredSum en «{where}», el cálculo se detiene si alguna contribución del "
                         "bloqueo es una aceleración, lo habitual en un bloqueo (superposition_models.py:55); depende de "
                         "los valores: es un error del cálculo.")
PUD_DOWNSTREAM_FIELD_NOTE = ("La evaluación del campo sí calcula el bloqueo en sus puntos, con el estado de las turbinas "
                             "de esa simulación.")
CUMULATIVE_FIELD_NOTE = ("En los puntos del campo, PyWake no aplica el promedio de rotor a la distancia transversal; el "
                         "estado de las turbinas sale de la simulación anterior.")


def cumulative_without_effect(config: WakeConfig) -> List[str]:
    """The arguments of the deficit of ``config`` that CumulativeWakeSum leaves without numerical effect (decision 23a):
    those of the table of the catalogue, and the ground with PropagateDownwind and PropagateUpDownIterative."""
    if config.superposition.name != "CumulativeWakeSum":
        return []
    engine = config.engine.name
    out = [a for a in _cat.CUMULATIVE_WITHOUT_EFFECT.get(config.deficit.name, ())
           if not (a == "use_effective_ws" and engine == "PropagateUpDownIterative")]
    if _ground_without_effect(config):
        # Its arguments are left without effect with it (#64), in the order of its signature.
        args = ", ".join(a.name for a in _sub.args_of(config.ground.name) if a.name in config.ground.params)
        out.append(f"groundModel ({config.ground.name}{': ' + args if args else ''})")
    return out


def _ground_without_effect(config: WakeConfig) -> bool:
    """CumulativeWakeSum leaves the ground of the deficit without effect (decision 23a): with PDW and PUD; with A2A
    only with a sum of its own (inheriting it is R9d). With PDW and PUD PyWake never calls it; with A2A it calls it
    (it costs) though it has no effect."""
    return (config.superposition.name == "CumulativeWakeSum" and config.ground is not None
            and (config.engine.name != "All2AllIterative" or config.ground.params.get("superpositionModel") is not None))


def superposition_warnings(config: WakeConfig, *, flow_map: bool = False) -> List[Any]:
    """The persistent warnings of the wake superposition of ``config``: the order of the turbines (decision 19) and
    what CumulativeWakeSum leaves without effect (decision 23a); ``flow_map`` adds what the field of the raster does."""
    if config.superposition.name != "CumulativeWakeSum":
        return []
    import py_wake
    out = [log_text(_cat.entry(_cat.SUPERPOSITION, "CumulativeWakeSum").warning)]
    args = cumulative_without_effect(config)
    if args:
        out.append(log_text(CUMULATIVE_WITHOUT_EFFECT_NOTE, version=py_wake.__version__, engine=config.engine.name,
                            args=", ".join(args)))
    if flow_map and config.rotor is not None:
        out.append(log_text(CUMULATIVE_FIELD_NOTE))
    return out


def blockage_warnings(config: WakeConfig, *, flow_map: bool = False) -> List[Any]:
    """The persistent warnings of the blockage of ``config``: with PropagateUpDownIterative, the models that compute
    with the free wind speed (decision 19) and, with WeightedSum or CumulativeWakeSum, the blockage its downwind pass
    leaves out (decision 23c): only with LinearSum, the one it calculates (MaxSum is R9f, SquaredSum R5 and the
    iterative sums R6; with upstream_only nothing downstream was asked for); with any engine, SquaredSum as the
    superposition of the blockage or of its ground (decision 6.3 of #64)."""
    if config.blockage is None:
        return []
    return _pud_blockage_warnings(config, flow_map) + _squared_blockage_warnings(config)


def _squared_blockage_warnings(config: WakeConfig) -> List[Any]:
    import py_wake
    out = []
    if config.blockage_superposition.name == "SquaredSum":
        out.append(log_text(SQUARED_BLOCKAGE_NOTE, version=py_wake.__version__,
                            where=_cat.position_label(_cat.BLOCKAGE_SUPERPOSITION)))
    return out + _squared_blockage_ground_warnings(config)


def _squared_blockage_ground_warnings(config: WakeConfig) -> List[Any]:
    """SquaredSum as the sum of its own of the ground of the blockage (decision 6.3 of #64)."""
    import py_wake
    ground = config.blockage.params.get("groundModel")
    own = ground.params.get("superpositionModel") if isinstance(ground, Component) else None
    if isinstance(own, Component) and own.name == "SquaredSum":
        return [log_text(SQUARED_BLOCKAGE_NOTE, version=py_wake.__version__,
                         where=log_text("{label} · {path}", label=_cat.position_label(_cat.BLOCKAGE),
                                        path="groundModel · superpositionModel"))]
    return []


def _pud_blockage_warnings(config: WakeConfig, flow_map: bool) -> List[Any]:
    if config.engine.name != "PropagateUpDownIterative":
        return []
    entry = _cat.entry(_cat.BLOCKAGE, config.blockage.name)
    out = [log_text(entry.warning)] if entry.warning else []
    upstream_only = config.blockage.params.get("upstream_only", _cat.signature_defaults(entry)["upstream_only"])
    sup = config.superposition.name
    if (sup in ("WeightedSum", "CumulativeWakeSum") and config.blockage_superposition.name == "LinearSum"
            and not upstream_only):
        import py_wake
        out.append(log_text(PUD_DOWNSTREAM_BLOCKAGE_NOTE, version=py_wake.__version__, sup=sup))
        if flow_map:
            out.append(log_text(PUD_DOWNSTREAM_FIELD_NOTE))
    return out


# The warnings of the edited arguments (#64; ``subordinates.WARNINGS``): what PyWake does with a value, never a barrier.
_A2A_NONE = ("En «{where}{path}», con convergence_tolerance = None, All2AllIterative hace una sola iteración y no "
             "comprueba la convergencia.")
_A2A_NONPOS = ("En «{where}{path}», con convergence_tolerance = {value} (≤ 0), All2AllIterative nunca cumple su criterio "
               "y agota sus iteraciones (como mucho, max(número de turbinas, 20)).")
_PUD_NONPOS = ("En «{where}{path}», con convergence_tolerance = {value} (≤ 0), PropagateUpDownIterative nunca cumple su "
               "criterio y agota sus pasadas.")
_MM_COST = ("En «{where}{path}», MultiMirror representa cada turbina {count} veces (2^(2 + max(0, n_reps))): el coste "
            "del cálculo crece en esa proporción.")
_MM_REPEAT = "En «{where}{path}», con n_reps = {value}, PyWake {version} repite imágenes de las turbinas."
_MM_REAL = ("En «{where}{path}», con n_reps = {value}, PyWake {version} añade también {copies} imagen(es) a la altura de "
            "la turbina real (a menos de 1 µm): aparece {times} veces en la suma del suelo.")
_MM_REAL_NOTE = ("En «{where}{path}», con n_reps = {value}, PyWake {version} añade también {copies} imagen(es) a la "
                 "altura de la turbina real (a menos de 1 µm): aparece {times} veces en la suma del suelo (con un buje "
                 "que no esté a la altura de un espejo; con las turbinas, al calcular, se cuenta exactamente).")
_MM_NEGATIVE = "En «{where}{path}», n_reps = {value} es negativo: PyWake no añade repeticiones, como con 0."
_MM_REAL_MANY = ("En «{where}{path}», con n_reps = {value}, PyWake {version} añade también imágenes a la altura de la "
                 "turbina real (a menos de 1 µm): aparece al menos {times} veces en la suma del suelo.")
_VD_CENTER = ("En «{where}{path}», con limiter = {value}, VortexDipole no regulariza el centro del rotor: PyWake "
              "{version} da NaN en cualquier punto que caiga en el centro de una turbina (en el ráster, una celda sobre "
              "una turbina).")
_VD_EXCLUDED = ("En «{where}{path}», con limiter = 0, VortexDipole solo excluye el centro del rotor dentro de la estela "
                "del déficit (exclude_wake): donde su radio de estela no es positivo, PyWake {version} da NaN en la "
                "propia turbina.")
_MM_ZERO = ("En «{where}{path}», con mirror_height = 0 el espejo superior coincide con el suelo: cada imagen de PyWake "
            "cae sobre la turbina real o sobre su imagen en el suelo.")
_MM_HUB = ("En «{where}{path}», el espejo superior de MultiMirror (mirror_height = {value} m) está a la altura de un buje "
           "o por debajo ({hub} m): sus imágenes no son las de un espejo por encima de las turbinas.")
_MM_HUB_NOTE = ("En «{where}{path}», si el espejo superior de MultiMirror queda a la altura de un buje o por debajo, sus "
                "imágenes no son las de un espejo por encima de las turbinas (se comprueba con las turbinas al calcular).")
# The weighting discarded by the arguments, and the iteration that may not end (decision 9 of #63: one predicate,
# ``edge_cases.weighting_discarded``, for these warnings, the raster and the exception of the 0 m/s node).
_WS_NOT_WEIGHING = "En «{where}{path}», con {arg} = {value}, WeightedSum no pondera: suma las estelas linealmente."
_WS_MAY_NOT_END = ("En «{where}{path}», WeightedSum iterará hasta max_iter si el residuo no baja de max_err (max_err = "
                   "{max_err}, max_iter = {max_iter}): con un valor alto, el cálculo puede tardar mucho o no terminar.")
_WS_INF_ZERO_NODE = ("En «{where}{path}», con max_iter = +inf, si la malla de velocidades incluye 0 m/s su nodo no se "
                     "calcula aparte: sin él, WeightedSum podría no terminar.")
_WS_DELTA = "En «{where}{path}», con delta = {value} (≤ 0), PyWake limita internamente el umbral a 1e-30."
_WS_LIMIT = ("En «{where}{path}», weight_limit = {value} (≤ 0) es el máximo del peso de cada contribución que WeightedSum "
             "pondera cuando itera (las que superan delta; el menor entre el cociente de velocidades de convección y "
             "weight_limit, superposition_models.py:148): con un cociente positivo pesan {value} (con 0 se anulan; con un "
             "negativo se invierten); con uno menor conservan el suyo. Si no itera (según max_err, max_iter y los "
             "valores), suma linealmente.")
_SS_DOMAIN = ("En «{where}{path}», con ss_lambda = {lam} y ss_eta = {eta}, ss_lambda·(ss_eta + x²) es negativo o nulo en "
              "parte del dominio: según las distancias, el promedio de rotor, la exclusión de la estela y ss_alpha, "
              "PyWake {version} puede dar NaN en las velocidades y en el AEP, o un error de cálculo.")
_VD_SELF = ("En «{where}{path}», con All2AllIterative y un promedio de rotor del bloqueo con un nodo en el centro, ese "
            "centro es el de la propia turbina: PyWake {version} da NaN en las velocidades y en el AEP.")
_EQ_EMPTY_WS = ("En «{where}{path}», con n = {value}, EqGridRotorAvg no tiene nodos: NumPy promedia una lista vacía (con su "
                "propio aviso) y PyWake {version} puede dar NaN en las velocidades y en el AEP.")
_EQ_EMPTY_TI = ("En «{where}{path}», con n = {value}, EqGridRotorAvg no tiene nodos: NumPy promedia una lista vacía (con su "
                "propio aviso) y PyWake {version} puede dar NaN en la TI efectiva.")
_STF_C00 = ("En «{where}{path}», con c = [0, 0], la turbulencia añadida de STF2017 es infinita a cualquier distancia: "
            "PyWake {version} puede dar una TI efectiva, unas velocidades o un AEP no finitos, según el motor, el número "
            "de turbinas y el déficit.")
_STF_C0 = ("En «{where}{path}», con c[0] = 0, la turbulencia añadida de STF2017 es infinita a distancia 0: con "
           "All2AllIterative y un promedio de rotor de la turbulencia con un nodo en el centro, PyWake {version} puede dar "
           "una TI efectiva o un AEP no finitos; en el mapa, TI NaN en los puntos que caen sobre un buje.")
_FGP3 = ("En «{where}{path}», con fgp[3] = 0, SelfSimilarityDeficit2020 divide por cero: PyWake {version} puede dar NaN en "
         "las velocidades y en el AEP.")
_LIST_EXTRA = ("En «{where}{path}», {arg} tiene {count} elementos: PyWake {version} solo lee los {length} primeros; los "
               "demás se conservan sin efecto.")
_HIGH_CT = ("En «{where}{path}», con high_ct_mod = True, PyWake {version} modifica en su sitio las distancias aguas abajo "
            "cuando se calcula con una sola velocidad, y con a ≥ 0,5 anula el bloqueo sin error.")
# The warnings that announce non-finite results PyWake gives without an error (decisions 9 and 19; decision 5 of #64).
NON_FINITE_TEXTS = (_SS_DOMAIN, _VD_CENTER, _VD_EXCLUDED, _VD_SELF, _EQ_EMPTY_WS, _EQ_EMPTY_TI, _STF_C00, _STF_C0, _FGP3)
ARGUMENT_TEXTS = (_A2A_NONE, _A2A_NONPOS, _PUD_NONPOS, _MM_COST, _MM_REPEAT, _MM_REAL, _MM_REAL_NOTE, _MM_REAL_MANY,
                  _MM_NEGATIVE, _VD_CENTER, _VD_EXCLUDED,
                  _MM_ZERO, _MM_HUB,
                  _MM_HUB_NOTE, _WS_NOT_WEIGHING, _WS_MAY_NOT_END, _WS_INF_ZERO_NODE, _WS_DELTA, _WS_LIMIT, _SS_DOMAIN,
                  _HIGH_CT, _VD_SELF, _EQ_EMPTY_WS,
                  _EQ_EMPTY_TI, _STF_C00, _STF_C0, _FGP3, _LIST_EXTRA)
# Where the dialog shows the warnings of each position: the rotor and the ground under the deficit.
_SHOWN_AT = {_cat.ROTOR: _cat.DEFICIT, _cat.GROUND: _cat.DEFICIT}


def _walk(config: WakeConfig):
    """``(position, path, component)`` of every component of ``config``, nested ones included."""
    def inner(position, comp, path):
        if comp is None:
            return
        yield position, path, comp
        for name, value in comp.params.items():
            if isinstance(value, Component):
                yield from inner(position, value, f"{path} · {name}")
    for position in _cat.POSITIONS:
        yield from inner(position, config.component(position), "")


# The repetitions of MultiMirror whose images are counted in its warnings (2^14 per hub); above, a lower bound (the
# list of images only grows); and the exponent above which its cost is written as a power.
_COUNTED_REPS = 12
_POWER_LIMIT = 66


def _real_appearances(n_reps: int, mirror_height: Any, hub_heights: Any = None) -> int:
    """How many times MultiMirror of PyWake has a turbine at its own height: the images whose vertical offset, as
    PyWake computes it (``MultiMirror._update_kwargs``, ground_models.py:98-128, the geometry of the calculation),
    is under a micrometre (its copies of the real turbine are 1e-13 m away after its successive reflections; whether
    such an image acts as the real turbine depends on the rotor, so the warning says where they are, not what they
    do: revisiones/sol/q2f_r4-r5_salida.md), for each hub height of the calculation (the most), or, without them, for
    a hub height that is not on a mirror. Called with at most ``_COUNTED_REPS`` repetitions (2^(2 + n_reps) images
    per hub)."""
    if not _number(mirror_height):
        return 1
    import numpy as np
    from py_wake.ground_models import MultiMirror
    try:
        big_h = float(mirror_height)
    except OverflowError:  # an integer too large for a float: PyWake fails with it when calculating, not here
        return 1
    hubs = sorted({float(h) for h in hub_heights}) if hub_heights is not None and len(hub_heights) else \
        [0.3713 * abs(big_h) or 1.0]
    h_ilk = np.array(hubs, dtype=float).reshape(-1, 1, 1)
    kwargs = {"IJLK": (len(hubs), 1, 1, 1), "h_ilk": h_ilk, "dh_ijlk": np.zeros((len(hubs), 1, 1, 1))}
    dh = MultiMirror(mirror_height=big_h, n_reps=n_reps)._update_kwargs(**kwargs)["dh_ijlk"]
    # The images are appended in blocks in the order of the hubs: entry j belongs to hub j % len(hubs).
    return int((np.abs(dh.reshape(-1, len(hubs))) < 1e-6).sum(axis=0).max())


def _number(v: Any) -> bool:
    """A number as PyWake uses it: a bool is one (False is 0), as the contract takes it (decision 6.2 of #64)."""
    return isinstance(v, (bool, int, float))


def _power_text(exponent: int) -> str:
    """«2^exponent», or, for an exponent Python cannot write as text (over 4300 digits), «2^(2 + n_reps)»."""
    try:
        return f"2^{exponent}"
    except ValueError:
        return "2^(2 + n_reps)"


def _product_is_zero(a: Any, b: Any) -> bool:
    """``a·b == 0`` as a float, also with an integer too large for one (it overflows: then it is not zero)."""
    try:
        return a * b == 0
    except OverflowError:
        return False


def _centre_node(rotor: Optional[Component]) -> bool:
    """Whether a rotor average evaluates the centre of the rotor exactly: without one, the centre itself;
    EqGridRotorAvg, the middle node of its np.linspace(-1, 1, n + 2), computed as numpy does without building the
    grid (an odd n, and not every one: with 97 it is 2e-16, rotor_avg_model.py:83-88); CGIRotorAvg, read from its
    nodes (7, 9 and 21 have one)."""
    if rotor is None:
        return True
    n = rotor.params.get("n")
    if rotor.name == "EqGridRotorAvg":
        if not (isinstance(n, int) and n > 0 and n % 2 == 1):  # from −2 to 0, no nodes at all
            return False
        k = (n + 1) // 2
        try:
            return k * (2.0 / (n + 1)) + -1.0 == 0.0
        except OverflowError:  # an n too large for a float: np.linspace does not build it, PyWake fails calculating
            return False
    try:
        obj = _sub.resolve(rotor.name)(**rotor.params)
    except Exception:
        return False  # a rotor PyWake does not build is refused by its own rule
    if not hasattr(obj, "nodes_x"):
        return False  # GaussianOverlapAvgModel has no nodes (in a blockage it is refused, R16)
    return bool(np.any((np.abs(obj.nodes_x) < 1e-12) & (np.abs(obj.nodes_y) < 1e-12)))


def _extra_elements(position: str, comp: Component, data: Dict[str, Any]) -> List[Any]:
    """The lists longer than what PyWake reads (decision 6.2 of #64): kept, and said. The coefficients of the
    subordinate objects (``subordinates``) and those of a deficit or a blockage of the catalogue."""
    lengths = {a.name: a.length for a in _sub.args_of(comp.name) if a.kind == _sub.LIST}
    if position in (_cat.DEFICIT, _cat.BLOCKAGE) and data["path"] == f" · {comp.name}":
        try:
            defaults = _cat.signature_defaults(_cat.entry(position, comp.name))
            lengths.update({k: len(v) for k, v in defaults.items() if isinstance(v, (list, tuple))})
        except Exception as _ignored_exc:  # noqa: BLE001 - not an entry of the catalogue at this position
            logging.getLogger(__name__).debug("Ignored optional operation at %s:%d: %s", __name__, 305, _ignored_exc)
    from .validation import _UNPACKED  # unpacked, another length stops PyWake where it reads it (R20)
    out = []
    for name, length in lengths.items():
        v = comp.params.get(name)
        if isinstance(v, (list, tuple)) and len(v) > length and (comp.name, name) not in _UNPACKED:
            out.append(log_text(_LIST_EXTRA, arg=name, count=len(v), length=length, **data))
    return out


def argument_warnings(config: WakeConfig, *, hub_heights: Any = None) -> Dict[str, List[Any]]:
    """The warnings of the values of the edited arguments, by the position the dialog shows them at. With
    ``hub_heights`` (the turbines are known: the AEP and the raster), the height of the mirror of MultiMirror against
    them; without it, the general note of the dialog."""
    out: Dict[str, List[Any]] = {}
    for position, _path, texts in _routed_argument_warnings(config, hub_heights):
        out.setdefault(_SHOWN_AT.get(position, position), []).extend(texts)
    return out


def ground_window_warnings(config: WakeConfig) -> Dict[str, List[Any]]:
    """The warnings whose cause is in the window of a ground model, by its window: of the deficit (``GROUND``) or of
    the blockage (``BLOCKAGE``); those of its arguments, and SquaredSum as its own sum in the blockage."""
    out: Dict[str, List[Any]] = {_cat.GROUND: [], _cat.BLOCKAGE: []}
    for position, path, texts in _routed_argument_warnings(config):
        if position == _cat.GROUND or (position == _cat.BLOCKAGE and path.startswith(" · groundModel")):
            out[position].extend(texts)
    if config.blockage is not None:
        out[_cat.BLOCKAGE] += _squared_blockage_ground_warnings(config)
    return out


def _routed_argument_warnings(config: WakeConfig, hub_heights: Any = None) -> List[Tuple[str, str, List[Any]]]:
    """``(position, path, warnings)`` of each component of ``config`` with warnings of its arguments."""
    import py_wake
    out: List[Tuple[str, str, List[Any]]] = []
    for position, path, comp in _walk(config):
        p, data = comp.params, {"where": _cat.position_label(position), "path": path or f" · {comp.name}",
                                "version": py_wake.__version__}
        texts: List[Any] = []
        if comp.name == "All2AllIterative" and "convergence_tolerance" in p:
            tol = p["convergence_tolerance"]
            if tol is None:
                texts.append(log_text(_A2A_NONE, **data))
            elif _number(tol) and tol <= 0:
                texts.append(log_text(_A2A_NONPOS, value=tol, **data))
        if comp.name == "PropagateUpDownIterative" and _number(p.get("convergence_tolerance")) \
                and p["convergence_tolerance"] <= 0:
            texts.append(log_text(_PUD_NONPOS, value=p["convergence_tolerance"], **data))
        # A ground PyWake never calls (CumulativeWakeSum with PDW or PUD) has neither cost nor images; with A2A and a
        # sum of its own it is called (and costs) though it has no effect (the note of decision 23a says so).
        if comp.name == "MultiMirror" and not (position == _cat.GROUND and not path and _ground_without_effect(config)
                                               and config.engine.name != "All2AllIterative"):
            n = p.get("n_reps")
            if isinstance(n, int):
                exponent = 2 + max(0, n)
                count = 2 ** exponent if exponent <= _POWER_LIMIT else _power_text(exponent)
                texts.append(log_text(_MM_COST, count=count, **data))
                if n >= 2:
                    texts.append(log_text(_MM_REPEAT, value=n, **data))
                times = _real_appearances(min(n, _COUNTED_REPS), p.get("mirror_height"), hub_heights)
                if times > 1 and n > _COUNTED_REPS:  # counted up to _COUNTED_REPS: a lower bound (it only grows)
                    texts.append(log_text(_MM_REAL_MANY, value=n, times=times, **data))
                elif times > 1:  # copies at the height of the real turbine (evidencias/q1/estructura, S§9)
                    texts.append(log_text(_MM_REAL if hub_heights is not None else _MM_REAL_NOTE, value=n,
                                          copies=times - 1, times=times, **data))
                if n < 0:
                    texts.append(log_text(_MM_NEGATIVE, value=n, **data))
            h = p.get("mirror_height")
            if _number(h) and h == 0:
                texts.append(log_text(_MM_ZERO, **data))
            elif _number(h) and hub_heights is not None and len(hub_heights):
                top = float(max(hub_heights))
                if h <= top:
                    texts.append(log_text(_MM_HUB, value=h, hub=top, **data))
            elif _number(h) and hub_heights is None:
                texts.append(log_text(_MM_HUB_NOTE, **data))
        # Only as the wake superposition: as the sum of a ground PyWake calls it with one array (R18) or never
        # (CumulativeWakeSum with PDW or PUD), and as the blockage's it is refused (R6).
        if comp.name == "WeightedSum" and position == _cat.SUPERPOSITION and not path:
            discarded = weighting_discarded(p)
            if discarded:  # it adds linearly: no other warning of its weights nor of its iteration (precedence)
                texts.append(log_text(_WS_NOT_WEIGHING, arg=discarded, value=p.get(discarded), **data))
            for name, text in (("delta", _WS_DELTA), ("weight_limit", _WS_LIMIT)):
                if _number(p.get(name)) and p[name] <= 0 and (name != "weight_limit" or not discarded):
                    texts.append(log_text(text, value=p[name], **data))
            ending = may_not_terminate(p)
            if ending:
                texts.append(log_text(_WS_MAY_NOT_END, max_err=weighted_sum_argument(p, "max_err"),
                                      max_iter=weighted_sum_argument(p, "max_iter"), **data))
            if "max_iter" in ending:
                texts.append(log_text(_WS_INF_ZERO_NODE, **data))
        if comp.name == "SelfSimilarityDeficit":
            lam, eta = p.get("ss_lambda"), p.get("ss_eta")
            # Also a product that rounds to zero with both positive (1e-200·1e-200): the root at the centre is 0.
            if _number(lam) and _number(eta) and (not (lam > 0 and eta > 0) or _product_is_zero(lam, eta)):
                texts.append(log_text(_SS_DOMAIN, lam=lam, eta=eta, **data))
        if comp.name == "VortexDipole" and _sub.singular_limiter(p):
            texts.append(log_text(_VD_CENTER, value=p["limiter"], **data))
            if config.engine.name == "All2AllIterative" and _centre_node(p.get("rotorAvgModel")):
                texts.append(log_text(_VD_SELF, **data))
        elif comp.name == "VortexDipole" and p.get("limiter") == 0:  # with exclude_wake (deficit_model.py:115)
            texts.append(log_text(_VD_EXCLUDED, **data))
        texts += _extra_elements(position, comp, data)
        if comp.name == "EqGridRotorAvg":
            n = p.get("n")
            if isinstance(n, int) and -2 <= n <= 0:
                texts.append(log_text(_EQ_EMPTY_TI if position == _cat.TURBULENCE else _EQ_EMPTY_WS, value=n, **data))
        if comp.name == "STF2017TurbulenceModel":
            c = p.get("c")
            if isinstance(c, (list, tuple)) and len(c) >= 2 and all(_number(x) for x in c[:2]) and c[0] == 0:
                texts.append(log_text(_STF_C00 if c[1] == 0 else _STF_C0, **data))
        if comp.name == "SelfSimilarityDeficit2020":
            fgp = p.get("fgp")
            if isinstance(fgp, (list, tuple)) and len(fgp) >= 4 and _number(fgp[3]) and fgp[3] == 0:
                texts.append(log_text(_FGP3, **data))
        if comp.name == "RankineHalfBody" and p.get("high_ct_mod"):  # as PyWake reads it: ``if self.high_ct_mod``
            texts.append(log_text(_HIGH_CT, **data))
        if texts:
            out.append((position, path, texts))
    return out


def turbulence_without_effect(config: WakeConfig) -> bool:
    """Decision 16: a turbulence chosen with a deficit that does not read the effective TI, as PyWake picks its key,
    ``['TI_ilk', 'TI_eff_ilk'][use_effective_ti]`` (deficit_model.py:21: −1 reads it, −2 does not; without the
    argument, never)."""
    if config.turbulence is None:
        return False
    try:
        return ("TI_ilk", "TI_eff_ilk")[config.deficit.params.get("use_effective_ti", False)] == "TI_ilk"
    except (TypeError, IndexError):
        return False  # PyWake does not build it: refused before calculating


def persistent_warnings(config: WakeConfig, *, flow_map: bool = False, hub_heights: Any = None) -> List[Any]:
    """The persistent warnings of decisions 16, 19 and 23 and of the edited arguments (#64) that apply to ``config`` (the
    AEP's and, with ``flow_map``, the raster's; ``hub_heights``, the turbines of the calculation)."""
    by_position = argument_warnings(config, hub_heights=hub_heights)
    turbulence = ([log_text(TURBULENCE_WITHOUT_EFFECT, cls=config.deficit.name)]
                  if turbulence_without_effect(config) else [])
    return (turbulence + superposition_warnings(config, flow_map=flow_map) + blockage_warnings(config, flow_map=flow_map)
            + [w for position in _cat.POSITIONS for w in by_position.get(position, [])])


def convergence_warnings(summary: Dict[str, Any]) -> List[Any]:
    """The warnings of the iterative loops that did not converge (decision 9): visible, never a barrier. A state that
    could not be read is «not available», with its reason, never «not converged»; non-finite residuals are said
    (decision 6.5 of #64)."""
    from .instrumentation import UNAVAILABLE
    out = []
    for loop, entry in summary.items():
        if entry.get("converged"):
            continue
        states = {s: c for s, c in entry["states"].items() if s != UNAVAILABLE}
        if UNAVAILABLE in entry["states"]:
            out.append(log_text("Convergencia de {loop}: no disponible en {count} de {calls} ({reasons}).", loop=loop,
                                count=entry["states"][UNAVAILABLE], calls=entry["calls"],
                                reasons="; ".join(entry.get("unavailable_reasons") or [])
                                or log_text("causa no registrada")))  # a result saved before 6.5
        if entry.get("non_finite_residuals"):
            out.append(log_text("Convergencia de {loop}: {count} residuo(s) no finito(s).", loop=loop,
                                count=entry["non_finite_residuals"]))
        if set(states) <= {"converged"}:
            continue
        if set(states) == {"no_check"}:  # All2AllIterative with convergence_tolerance = None: never «converged»
            out.append(log_text("Convergencia de {loop}: una iteración; convergencia no comprobada.", loop=loop))
            continue
        states_text = ", ".join(f"{state} × {count}" for state, count in sorted(states.items()))
        out.append(log_text("Convergencia de {loop}: {states}. El resultado se conserva, pero no es un cálculo "
                            "convergido.", loop=loop, states=states_text))
    return out


GO_ADAPTATION_NOTE = ("Se ha usado CGIRotorAvg(7) en vez de GaussianOverlapAvgModel porque no está disponible "
                      "{missing} (elegido con «Continuar»). {install}")
GO_ADAPTATION_NOTE_PLURAL = ("Se ha usado CGIRotorAvg(7) en vez de GaussianOverlapAvgModel porque no están "
                             "disponibles {missing} (elegido con «Continuar»). {install}")


# Applied by the decision the user saved for a predefined model (decision 21 of the predefined models).
GO_SAVED_NOTE = ("Se ha usado CGIRotorAvg(7) en vez de GaussianOverlapAvgModel porque no está disponible {missing} "
                 "(aplicado por la decisión guardada para este modelo). {install}")
GO_SAVED_NOTE_PLURAL = ("Se ha usado CGIRotorAvg(7) en vez de GaussianOverlapAvgModel porque no están disponibles "
                        "{missing} (aplicado por la decisión guardada para este modelo). {install}")

def adaptation_notes(config: WakeConfig) -> List[Any]:
    """The note of each adaptation the user accepted (decision 10), with how to install what was missing."""
    out = []
    for a in config.adaptations:
        if a.get("reason") == "missing_modules":
            missing = str(a.get("missing") or "")
            packages = [m.strip() for m in missing.split(",") if m.strip()]
            if a.get("acceptance") == "saved_preference":
                note = GO_SAVED_NOTE if len(packages) == 1 else GO_SAVED_NOTE_PLURAL
            else:
                note = GO_ADAPTATION_NOTE if len(packages) == 1 else GO_ADAPTATION_NOTE_PLURAL
            out.append(log_text(note, missing=missing, install=install_hint(packages)))
    return out


def result_warnings(result: Mapping[str, Any]) -> List[Any]:
    """Every warning of a result of schema 2, for the results window and the exports: the persistent ones with the
    accepted adaptations (``persistent_warnings`` of the result), those of convergence of the main calculation, of the
    variants of the breakdown and of the auxiliary simulation of 0 m/s, each saying which one, and those of the edge
    cases (#63; ``edge_cases``, only when there are some)."""
    convergence = result.get("convergence") or {}
    out = list(result.get("persistent_warnings") or [])
    out += [log_text("Cálculo principal: {warning}", warning=w)
            for w in convergence_warnings(convergence.get("main") or {})]
    out += [log_text("Variantes del desglose: {warning}", warning=w)
            for w in convergence_warnings(convergence.get("variants") or {})]
    out += [log_text("Simulación auxiliar de 0 m/s: {warning}", warning=w)
            for w in convergence_warnings(convergence.get("auxiliary_zero") or {})]
    out += list((result.get("edge_cases") or {}).get("warnings") or [])
    return out

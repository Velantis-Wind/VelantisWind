# -*- coding: utf-8 -*-
"""The arguments of the subordinate objects of the wake physics (#64, Q1): what is offered, its kind, its technical
limit, what PyWake says about it, and what is left out and why.

Data only: nothing here is offered yet (Q3 activates it) and nothing reads it to build or validate a configuration
(Q2). Every value comes from PyWake 2.6.18 (``planes/plan_modelos_estela/evidencias/q1/fuentes_pywake.md``): the
default of each argument is the one of its signature, read with ``inspect`` (``signature_defaults``), never written
here. ``tests.test_wake_subordinates`` checks that each argument offered changes the calculation in its position and
that each exclusion «without effect» has none.
"""
from __future__ import annotations

import inspect
import math
from dataclasses import dataclass
from typing import Any, Dict, Mapping, Optional, Tuple

__all__ = ["NUMBER", "INT", "BOOL", "CT2A", "LIST", "CHOICE", "COMPONENT", "NUMBER_OR_NONE", "Arg", "Excluded",
           "Option", "FAMILIES", "LIMITS", "WARNINGS", "ARGS", "EXCLUDED", "args_of", "excluded_of", "options", "resolve",
           "resolve_option", "resolve_name", "known_name", "arg_spec", "signature_default"]

# Kinds of control (Q3): a number, an integer, a boolean, a ct2a function, a list of fixed length, a closed set of
# values, another PyWake class (a «family» of options, with their own arguments), and a number or None.
NUMBER, INT, BOOL, CT2A, LIST, CHOICE, COMPONENT, NUMBER_OR_NONE = (
    "number", "int", "bool", "ct2a", "list", "choice", "component", "number_or_none")

_RA = "py_wake.rotor_avg_models.rotor_avg_model"
_AO = "py_wake.rotor_avg_models.area_overlap_model"
_GO = "py_wake.rotor_avg_models.gaussian_overlap_model"
_GR = "py_wake.ground_models.ground_models"
_SP = "py_wake.superposition_models"
_STF = "py_wake.turbulence_models.stf"
_EM = "py_wake.wind_farm_models.engineering_models"


@dataclass(frozen=True)
class Option:
    """One class an argument of the kind COMPONENT can take; ``None`` as ``name`` is PyWake's ``None`` (no model, or
    inherit, as ``label`` says)."""

    name: Optional[str]
    module: str = ""
    label: str = ""


# The options of each family, in the order of the selector. Who takes which family: ``Arg.family``; a family can be
# narrowed for one owner with ``Arg.only`` (AreaOverlapAvgModel only in the turbulence of GCL and Crespo).
FAMILIES: Dict[str, Tuple[Option, ...]] = {
    # The sum of the ground (Mirror, MultiMirror): None inherits the superposition of the object it wraps
    # (ground_models.py:55-56). WeightedSum, CumulativeWakeSum and SqrMaxSum fail where the ground calls them with one
    # array: offered with their rule (R18, decision 6.1 of #64).
    "ground_sum": (Option(None, label="Heredar"), Option("LinearSum", _SP), Option("SquaredSum", _SP),
                   Option("MaxSum", _SP), Option("WeightedSum", _SP), Option("CumulativeWakeSum", _SP),
                   Option("SqrMaxSum", _SP)),
    # The sum of the added turbulence (turbulence_model.py:47; superposition_models.py:34-71): WeightedSum and
    # CumulativeWakeSum fail when building; None fails where the turbulence is summed (R19).
    "ti_sum": (Option("LinearSum", _SP), Option("SquaredSum", _SP), Option("MaxSum", _SP), Option("SqrMaxSum", _SP)),
    # The weight of the STF models (stf.py:11-57): None fails when building.
    "weight": (Option("FrandsenWeight", _STF), Option("IECWeight", _STF)),
    # A rotor average in a new position (turbulence, blockage): RotorCenter is left out, it is the same as None
    # (rotor_avg_model.py:18-19; E). The overlaps fail where PyWake evaluates them between turbines, except
    # AreaOverlapAvgModel in GCLTurbulence and CrespoHernandez: offered with their rule (R16, R17).
    "rotor": (Option(None, label="Ninguno"), Option("CGIRotorAvg", _RA), Option("EqGridRotorAvg", _RA),
              Option("AreaOverlapAvgModel", _AO), Option("GaussianOverlapAvgModel", _GO)),
    # The ground of a blockage (deficit_model.py:109-110): the same classes as the ground of the deficit.
    "ground": (Option(None, label="Ninguno"), Option("Mirror", _GR), Option("MultiMirror", _GR)),
}


@dataclass(frozen=True)
class Arg:
    """One argument offered of one class (``owner``): its control (``kind``), the length of a list, the values of a
    CHOICE, the family of a COMPONENT (narrowed with ``only``), whether ``None`` is a value, the technical limit
    (what PyWake refuses or what breaks the calculation, validated by Q2), the warning of a behaviour that does not
    keep it from calculating, and what PyWake says about it, with its source."""

    owner: str
    name: str
    kind: str
    length: int = 0
    choices: Tuple[Any, ...] = ()
    family: str = ""
    only: Tuple[Optional[str], ...] = ()
    none: bool = False
    limit: str = ""
    warning: str = ""
    doc: str = ""


@dataclass(frozen=True)
class Excluded:
    """An argument of a class that is not offered, with its reason."""

    owner: str
    name: str
    reason: str


# The technical limits (``Arg.limit``): what PyWake refuses when building, refused before calculating (decision 22;
# decision 5 of #64: only where PyWake stops with an error); and the warnings (``Arg.warning``) of a behaviour that
# never keeps it from calculating (decisions 9 and 19). Each with its evidence (evidencias/q1/fuentes_pywake.md,
# evidencias/tensiones_stf).
LIMITS = {
    "eqgrid_n": "n entero ≥ −2: con −3 o menos np.linspace no lo construye (ValueError, rotor_avg_model.py:83-88); "
                "no entero, TypeError.",
}
WARNINGS = {
    "eqgrid_empty": "de −2 a 0, sin nodos: NumPy promedia una lista vacía (con su propio RuntimeWarning) y PyWake da NaN "
                    "en lo que promedia ese rotor (rotor_avg_model.py:83-88).",
    "stf2017_c0": "c[0] = 0: la turbulencia añadida 1/(c[0] + c[1]·d/√Ct) es infinita a distancia 0 (con c = [0, 0], a "
                  "cualquier distancia); PyWake silencia la división (stf.py:74-79) y puede dar TI efectiva, velocidades "
                  "o AEP no finitos según el motor, el número de turbinas y el rotor de la turbulencia.",
    "fgp3_zero": "fgp[3] = 0 divide por cero con cualquier Ct (selfsimilarity.py:158): velocidades y AEP NaN.",
    "a2a_tolerance": "≤ 0: nunca se cumple y agota max(número de turbinas, 20) iteraciones; None: una iteración, sin "
                     "comprobar la convergencia (engineering_models.py:1020, 1131-1133).",
    "pud_tolerance": "≤ 0: nunca se cumple y agota las pasadas (engineering_models.py:589).",
    "multimirror_height": "0: duplica la turbina real y su imagen en el suelo; un espejo a la altura de las turbinas o "
                          "por debajo da imágenes sin sentido físico (ground_models.py:87-128).",
    "multimirror_reps": "desde 2, imágenes repetidas; desde 3, otra copia de la turbina real (ground_models.py:115-128); "
                        "un negativo no añade repeticiones, como 0 (líneas 89-94); el coste crece como "
                        "2^(2 + max(0, n_reps)) representaciones de cada turbina.",
    "weighted_internal": "PyWake puede omitir la iteración (max_iter ≤ 0), limitar internamente el umbral (delta ≤ 0, "
                         "a 1e-30) o limitar el peso de cada contribución a weight_limit (≤ 0: anula o invierte las de cociente "
                         "positivo, no las demás) (superposition_models.py:"
                         "111-154).",
    "ss_domain": "con ss_lambda·(ss_eta + x²) ≤ 0 en parte del dominio (ss_lambda o ss_eta ≤ 0, o un producto que se "
                 "redondea a cero) la anchura no es real o es nula: NaN intermedios que, según las distancias, el "
                 "rotor, la exclusión de la estela y ss_alpha, se propagan o no; con All2AllIterative, también en la "
                 "propia turbina (selfsimilarity.py:38; deficit_model.py:112).",
    "vortexdipole_center": "limiter < 0, o 0 sin exclude_wake, deja sin regularizar el centro del rotor: NaN en cualquier "
                           "punto que caiga en él (vortexdipole.py:53-59; en el ráster, una celda sobre una turbina); con "
                           "All2AllIterative y un promedio de rotor del bloqueo con un nodo en el centro, el de la propia "
                           "turbina: velocidades y AEP NaN.",
    "high_ct_mod": "True: modifica in situ dw_ijlk con una sola velocidad (rankinehalfbody.py:60-62) y con "
                   "a ≥ 0,5 anula el bloqueo sin error.",
}

_BLOCKAGES = ("SelfSimilarityDeficit", "SelfSimilarityDeficit2020", "VortexCylinder", "VortexDipole", "RankineHalfBody",
              "Rathmann", "RathmannScaled")
# Where each blockage uses its limiter (PyWake: «limiter for singularities» / «limiter to avoid singularities»); with
# exclude_wake, every one also uses it to remove the wake region (deficit_model.py:112-124). PyWake gives no range.
_LIMITER_DOC = {
    "SelfSimilarityDeficit": "PyWake: «limiter for singularities»; anula el bloqueo a menos de limiter·R del plano "
                             "del rotor, aguas arriba y aguas abajo (la distancia va en valor absoluto, "
                             "selfsimilarity.py:52, 84) y, con exclude_wake, delimita la zona de la estela "
                             "(deficit_model.py:115). PyWake no da rango.",
    "VortexCylinder": "PyWake: «limiter to avoid singularities»; regulariza el borde del cilindro (|ρ − 1| < limiter, "
                      "vortexcylinder.py:47) y el plano del rotor (línea 56), también lejos del rotor, y delimita la "
                      "zona excluida (línea 88). PyWake no da rango.",
    "VortexDipole": "PyWake: «limiter to avoid singularities»; actúa con r/R < limiter (vortexdipole.py:53, 57) y, con "
                    "exclude_wake, delimita la zona de la estela (deficit_model.py:115). PyWake no da rango.",
    "RankineHalfBody": "PyWake: «limiter to avoid singularities»; anula el bloqueo con 2r/D < limiter "
                       "(rankinehalfbody.py:70) y, con exclude_wake, delimita la zona de la estela (deficit_model.py:"
                       "115). PyWake no da rango.",
    "Rathmann": "PyWake: «limiter to avoid singularities»; solo se usa con exclude_wake, para delimitar la zona de la "
                "estela (deficit_model.py:115). PyWake no da rango.",
}
_LIMITER_DOC.update({"SelfSimilarityDeficit2020": _LIMITER_DOC["SelfSimilarityDeficit"],
                     "RathmannScaled": _LIMITER_DOC["Rathmann"]})

ARGS: Tuple[Arg, ...] = (
    # --- Engines (decision 1 of #64, «Correcciones del inventario») ---
    Arg("All2AllIterative", "convergence_tolerance", NUMBER_OR_NONE, warning="a2a_tolerance",
        doc="PyWake (engineering_models.py:926-929): «if float: maximum accepted change in WS_eff_ilk [m/s]; if None: "
            "return after first iteration». Como mucho max(número de turbinas, 20) iteraciones. PyWake no da rango."),
    Arg("PropagateUpDownIterative", "convergence_tolerance", NUMBER, warning="pud_tolerance",
        doc="PyWake no la documenta (engineering_models.py:515-535); corta si el cambio máximo es menor que ella. "
            "PyWake no da rango."),
    Arg("PropagateUpDownIterative", "max_iter", NUMBER,
        doc="PyWake no lo documenta; se compara con un contador entero (engineering_models.py:589) y el bucle tiene "
            "como mucho tantas pasadas como turbinas (línea 559); ≤ 0 hace una pasada. PyWake no da rango."),
    # --- Rotor averages ---
    Arg("CGIRotorAvg", "n", CHOICE, choices=(4, 7, 9, 21),
        doc="PyWake (rotor_avg_model.py:127-133): «Circular Gauss Integration … n : {4, 7, 9, 21} Number of points»."),
    Arg("EqGridRotorAvg", "n", INT, limit="eqgrid_n", warning="eqgrid_empty",
        doc="PyWake no lo documenta: malla de n × n puntos, con los que caen dentro del rotor (rotor_avg_model.py:"
            "83-88); de −2 a 0 no hay nodos, y con −3 o menos no se construye. PyWake no da rango."),
    # --- Grounds ---
    Arg("Mirror", "superpositionModel", COMPONENT, family="ground_sum", none=True,
        doc="PyWake (ground_models.py:24-30): «Superposition model used to sum wakes from the above and below-ground "
            "turbine. If None, default, the superposition model used for the deficit model is applied»."),
    Arg("MultiMirror", "mirror_height", NUMBER, warning="multimirror_height",
        doc="PyWake (ground_models.py:64-75): «Considers the ground and a mirror aloft as a mirror by default … "
            "mirror_heigth : int or float, optional». PyWake no da rango."),
    Arg("MultiMirror", "n_reps", INT, warning="multimirror_reps",
        doc="PyWake (ground_models.py:64-76): «the user can set how many mirrors should be enforced (n_mirrors = 2 + "
            "n_reps). Be aware that the number of turbines grows quickly n_turbines = 2^(n_mirrors)». PyWake no da "
            "rango: un negativo no añade repeticiones, como 0 (ground_models.py:89-94); el control llega a "
            "−2147483647, el mínimo de su campo."),
    Arg("MultiMirror", "superpositionModel", COMPONENT, family="ground_sum", none=True,
        doc="PyWake (ground_models.py:77-81): el mismo texto que en Mirror."),
    # --- Wake superpositions ---
    Arg("WeightedSum", "delta", NUMBER, warning="weighted_internal",
        doc="PyWake (superposition_models.py:83): «minimum deficit (as fraction of free-stream) to invoke weighted "
            "summation»; Zong y Porté-Agel, J. Fluid Mech. (2020) 889 A8. PyWake no da rango."),
    Arg("WeightedSum", "max_err", NUMBER,
        doc="PyWake (superposition_models.py:85): «convergence limit for computing global convection velocity». "
            "PyWake no da rango."),
    Arg("WeightedSum", "max_iter", NUMBER, warning="weighted_internal",
        doc="PyWake (superposition_models.py:87): «maximum number of iterations used in computing weights». PyWake "
            "no da rango."),
    Arg("WeightedSum", "weight_limit", NUMBER, warning="weighted_internal",
        doc="PyWake (superposition_models.py:89): «Limit weights to this value. A limit of 1.0 means not exceeding "
            "linear superposition». PyWake no da rango."),
    Arg("CumulativeWakeSum", "alpha", NUMBER,
        doc="PyWake (superposition_models.py:216-217): «somewhat empirical factor to scale results to fit LES "
            "predictions … alpha in 8.3 (1 in eq 6.4 and 2 in eq 4.9)»; Bastankhah et al., J. Fluid Mech. (2021) 911 "
            "A53. PyWake no da rango."),
    # --- Added turbulence ---
    Arg("STF2017TurbulenceModel", "c", LIST, length=2, warning="stf2017_c0",
        doc="PyWake (stf.py:72-73): «the maximal added TI is calculated as TI_add = 1/(1.5 + 0.8*d/sqrt(Ct))», según "
            "la IEC 61400-1 de 2017. PyWake no da rango."),
    Arg("STF2017TurbulenceModel", "addedTurbulenceSuperpositionModel", COMPONENT, family="ti_sum",
        doc="Cómo se suma la turbulencia añadida a la ambiente (turbulence_model.py:47). PyWake no lo documenta."),
    Arg("STF2017TurbulenceModel", "weight_function", COMPONENT, family="weight",
        doc="PyWake (stf.py:12-17, 43-51): FrandsenWeight, el peso de la tesis de Frandsen (Eq. 3.16); IECWeight, el "
            "sector de 21,6° de la IEC 61400-1 (anexos D de 2005 y E de 2017)."),
    Arg("STF2017TurbulenceModel", "rotorAvgModel", COMPONENT, family="rotor", none=True),
    Arg("STF2005TurbulenceModel", "addedTurbulenceSuperpositionModel", COMPONENT, family="ti_sum",
        doc="Cómo se suma la turbulencia añadida a la ambiente (turbulence_model.py:47). PyWake no lo documenta."),
    Arg("STF2005TurbulenceModel", "weight_function", COMPONENT, family="weight",
        doc="Como en STF2017TurbulenceModel."),
    Arg("STF2005TurbulenceModel", "rotorAvgModel", COMPONENT, family="rotor", none=True),
    Arg("GCLTurbulence", "addedTurbulenceSuperpositionModel", COMPONENT, family="ti_sum",
        doc="Cómo se suma la turbulencia añadida a la ambiente (turbulence_model.py:47). PyWake no lo documenta."),
    Arg("GCLTurbulence", "rotorAvgModel", COMPONENT, family="rotor", none=True),
    Arg("CrespoHernandez", "ct2a", CT2A,
        doc="Relación entre el Ct y la inducción axial: ct2a_madsen (Madsen et al., Wind Energ. Sci. 5, 2020) o "
            "ct2a_mom1d (momento 1-D, Ct = 4a(1 − a), con Ct menor que 1) (deficit_models/utils.py:6-18)."),
    Arg("CrespoHernandez", "c", LIST, length=4,
        doc="PyWake (crespo.py:42-44): «added turbulence (Eq. 21)», c[0]·a^c[1]·TI^c[2]·(dw/D)^c[3]; Crespo y "
            "Hernández, J. Wind Eng. Ind. Aerodyn. 61 (1996) 71-85. PyWake no da rango."),
    Arg("CrespoHernandez", "addedTurbulenceSuperpositionModel", COMPONENT, family="ti_sum",
        doc="Cómo se suma la turbulencia añadida a la ambiente (turbulence_model.py:47). PyWake no lo documenta."),
    Arg("CrespoHernandez", "rotorAvgModel", COMPONENT, family="rotor", none=True),
    Arg("IECWeight", "distance_limit", NUMBER,
        doc="PyWake no lo documenta: distancia, en diámetros, hasta la que se aplica el peso (stf.py:56). PyWake no "
            "da rango."),
    # --- Blockage: the arguments the seven share (HybridInduction has its own list) ---
    *[a for b in _BLOCKAGES for a in (
        Arg(b, "ct2a", CT2A, doc="Relación entre el Ct y la inducción axial (deficit_models/utils.py:6-18)."),
        Arg(b, "limiter", NUMBER, warning="vortexdipole_center" if b == "VortexDipole" else "", doc=_LIMITER_DOC[b]),
        Arg(b, "exclude_wake", BOOL,
            doc="PyWake: «if used in a wind farm simulation, set deficit in wake region to zero, as here the wake "
                "model is active» (VortexCylinder excluye por el radio del rotor, vortexcylinder.py:85-90)."),
        Arg(b, "upstream_only", BOOL,
            doc="PyWake (deficit_model.py:92-93): «if true, downstream deficit from this model is set to zero»."),
        Arg(b, "rotorAvgModel", COMPONENT, family="rotor", none=True),
        Arg(b, "groundModel", COMPONENT, family="ground", none=True),
    )],
    Arg("HybridInduction", "switch_radius", NUMBER,
        doc="PyWake (hybridinduction.py:15-20): «Location at which to switch from near-rotor to far-field can be "
            "altered though by setting switch_radius»; campo lejano si r > R·switch_radius o aguas abajo. PyWake no "
            "da rango."),
    Arg("HybridInduction", "upstream_only", BOOL,
        doc="PyWake (deficit_model.py:92-93): «if true, downstream deficit from this model is set to zero»."),
    Arg("HybridInduction", "rotorAvgModel", COMPONENT, family="rotor", none=True),
    Arg("HybridInduction", "groundModel", COMPONENT, family="ground", none=True),
    # --- Blockage: their own arguments ---
    Arg("SelfSimilarityDeficit", "ss_gamma", NUMBER,
        doc="PyWake (selfsimilarity.py:21, 64-65): el Ct efectivo es gamma·Ct, Eq. (8) de Troldborg y Meyer Forsting "
            "(2016). PyWake no da rango."),
    Arg("SelfSimilarityDeficit", "ss_lambda", NUMBER, warning="ss_domain",
        doc="PyWake (selfsimilarity.py:36-38): r12 = √(ss_lambda·(ss_eta + x²)), Eq. (13) de [1]. PyWake no da rango."),
    Arg("SelfSimilarityDeficit", "ss_eta", NUMBER, warning="ss_domain",
        doc="PyWake (selfsimilarity.py:36-38): r12 = √(ss_lambda·(ss_eta + x²)), Eq. (13) de [1]. PyWake no da rango."),
    *[a for b in ("SelfSimilarityDeficit", "SelfSimilarityDeficit2020") for a in (
        Arg(b, "ss_alpha", NUMBER, doc="PyWake (selfsimilarity.py:43-45, 132): forma radial, Eq. (6) de [1]."),
        Arg(b, "ss_beta", NUMBER, doc="PyWake (selfsimilarity.py:43-45, 132): forma radial, Eq. (6) de [1]."),
    )],
    Arg("SelfSimilarityDeficit2020", "r12p", LIST, length=2,
        doc="PyWake (selfsimilarity.py:135, 147-151): «coefficients for the half width approximation», Eq. (13) de "
            "Meyer Forsting et al. (2023). PyWake no da rango."),
    Arg("SelfSimilarityDeficit2020", "ngp", LIST, length=4,
        doc="PyWake (selfsimilarity.py:137, 162-166): γ(Ct) en x/R = −1, Eq. (16) de [2]. PyWake no da rango."),
    Arg("SelfSimilarityDeficit2020", "fgp", LIST, length=4, warning="fgp3_zero",
        doc="PyWake (selfsimilarity.py:155-158): γ(Ct) en x/R = −6, Eq. (17) de [2], fgp[0]·sin((Ct − fgp[1])/fgp[3]) "
            "+ fgp[2]. PyWake no da rango."),
    *[Arg(b, "sct", NUMBER, doc="PyWake (vortexdipole.py:33, rathmann.py:34, 122): «coefficient for scaling the "
                                "effective forcing». PyWake no da rango.")
      for b in ("VortexDipole", "Rathmann", "RathmannScaled")],
    Arg("RankineHalfBody", "high_ct_mod", BOOL, warning="high_ct_mod",
        doc="PyWake no lo documenta: cambia la intensidad y la posición de la fuente con a (rankinehalfbody.py:54-62); "
            "Gribben y Hawkes (2019)."),
)

EXCLUDED: Tuple[Excluded, ...] = (
    Excluded("STF2005TurbulenceModel", "c", "PyWake 2.6.18 no lo lee: STF2005 usa las constantes de la norma "
                                            "(stf.py:107-110)."),
    *[Excluded(t, "groundModel", "El motor no lo invoca: la turbulencia solo se envuelve con su promedio de rotor "
                                 "(turbulence_model.py:26-30).")
      for t in ("STF2017TurbulenceModel", "STF2005TurbulenceModel", "GCLTurbulence", "CrespoHernandez")],
    Excluded("GaussianOverlapAvgModel", "filename", "Es la tabla de PyWake; el complemento no aporta otras."),
    Excluded("HybridInduction", "near_rotor", "Todavía no se ofrece: PyWake calcula con él, aunque lo llama sin algunos "
                                              "de sus envoltorios (hybridinduction.py:49-54); su clase y sus "
                                              "coeficientes cambian el cálculo."),
    Excluded("HybridInduction", "far_field", "Todavía no se ofrece: como near_rotor."),
    *[Excluded(e, a, r) for e in ("PropagateDownwind", "All2AllIterative", "PropagateUpDownIterative") for a, r in (
        ("deflectionModel", "La deflexión no se ofrece: el complemento no calcula el AEP con yaw."),
        ("rotorAvgModel", "En desuso en PyWake (engineering_models.py:100-107); el promedio de rotor va en el déficit."),
        ("inputModifierModels", "Solo admite turbinas multirrotor, que el complemento no tiene."),
    )],
    *[Excluded(e, "externalWindFarms", "Pide otro parque con su modelo, que el complemento no aporta.")
      for e in ("PropagateDownwind", "All2AllIterative")],
)


def args_of(owner: str) -> Tuple[Arg, ...]:
    """The arguments offered of a class, in the order of the table."""
    return tuple(a for a in ARGS if a.owner == owner)


def excluded_of(owner: str) -> Tuple[Excluded, ...]:
    return tuple(e for e in EXCLUDED if e.owner == owner)


def options(arg: Arg) -> Tuple[Option, ...]:
    """The options of a COMPONENT argument, narrowed for its owner."""
    family = FAMILIES[arg.family]
    return tuple(o for o in family if not arg.only or o.name in arg.only)


_MODULES = {"All2AllIterative": _EM, "PropagateUpDownIterative": _EM, "PropagateDownwind": _EM,
            "CGIRotorAvg": _RA, "EqGridRotorAvg": _RA, "Mirror": _GR, "MultiMirror": _GR,
            "WeightedSum": _SP, "CumulativeWakeSum": _SP, "IECWeight": _STF,
            "STF2017TurbulenceModel": _STF, "STF2005TurbulenceModel": _STF,
            "GCLTurbulence": "py_wake.turbulence_models.gcl_turb", "CrespoHernandez": "py_wake.turbulence_models.crespo",
            "SelfSimilarityDeficit": "py_wake.deficit_models.selfsimilarity",
            "SelfSimilarityDeficit2020": "py_wake.deficit_models.selfsimilarity",
            "VortexCylinder": "py_wake.deficit_models.vortexcylinder", "VortexDipole": "py_wake.deficit_models.vortexdipole",
            "RankineHalfBody": "py_wake.deficit_models.rankinehalfbody", "Rathmann": "py_wake.deficit_models.rathmann",
            "RathmannScaled": "py_wake.deficit_models.rathmann", "HybridInduction": "py_wake.deficit_models.hybridinduction",
            "GaussianOverlapAvgModel": "py_wake.rotor_avg_models.gaussian_overlap_model"}


def resolve(owner: str):
    """The PyWake class of an owner of the table."""
    import importlib
    return getattr(importlib.import_module(_MODULES[owner]), owner)


def known_name(name: str) -> bool:
    """Whether ``name`` is an owner of the table or an option of a family, by the table alone (without importing
    its class: whether the installed PyWake has it, the validation says, R14)."""
    return name is not None and (name in _MODULES or any(o.name == name for options_ in FAMILIES.values()
                                                          for o in options_))


def resolve_name(name: str):
    """The PyWake class of a nested component by its name: an owner of the table or an option of a family."""
    if name in _MODULES:
        return resolve(name)
    for options_ in FAMILIES.values():
        for o in options_:
            if o.name == name:
                return resolve_option(o)
    raise KeyError(name)


def arg_spec(owner: str, name: str) -> Optional[Arg]:
    """The entry of the table of an argument, or ``None`` if it is not one offered."""
    for a in ARGS:
        if a.owner == owner and a.name == name:
            return a
    return None


def resolve_option(option: Option):
    """The PyWake class of an option of a family (not ``None``)."""
    import importlib
    return getattr(importlib.import_module(option.module), option.name)


def singular_limiter(params: Mapping[str, Any]) -> bool:
    """The arguments of a VortexDipole leave the centre of the rotor without regularising: limiter < 0, or 0 without
    exclude_wake (vortexdipole.py:53-59; WARNINGS["vortexdipole_center"])."""
    v = params.get("limiter")
    if not isinstance(v, (int, float)):  # a bool is a number, as PyWake reads it
        return False
    if isinstance(v, float) and math.isnan(v):
        return True  # r/R < NaN is false: the centre keeps r = 0 (evidencias/consistencia/q5c_adv_comprobaciones)
    return v < 0 or (v == 0 and not params.get("exclude_wake"))  # −inf too; +inf regularises everything


def signature_default(arg: Arg) -> Any:
    """The default of ``arg`` in its class signature (decision 2): PyWake's own object, to be copied before use."""
    return inspect.signature(resolve(arg.owner).__init__).parameters[arg.name].default

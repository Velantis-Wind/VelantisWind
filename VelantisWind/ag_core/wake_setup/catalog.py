# -*- coding: utf-8 -*-
"""Catalogue of the PyWake classes the Energy module offers for the wake physics.

Each entry names one exact PyWake class (``module`` and ``name``), the position
it takes in a wind farm model and, for the wake deficits and the blockage
models, the arguments of its signature that are edited. The default value of
every argument is never written here: it is read from the class signature of
the installed PyWake (``signature_defaults``), so the plugin follows PyWake.
The fixed arguments of an option (``CGIRotorAvg`` with ``n = 9``) are the only
values the catalogue gives.

The data come from the P0 cards of the plan (fichas de P0): positions, the
order of the editable arguments, the help texts (Spanish source; translated
in ``catalog_translations.py``) and the persistent warnings of the PyWake
defects that are offered anyway. Nothing here builds or simulates anything.
"""
from __future__ import annotations

import importlib
import inspect
from dataclasses import dataclass, field
from typing import Any, Dict, Mapping, Optional, Tuple

from ..log_text import log_text

__all__ = [
    "ENGINE", "DEFICIT", "ROTOR", "GROUND", "SUPERPOSITION", "TURBULENCE", "BLOCKAGE", "BLOCKAGE_SUPERPOSITION",
    "POSITIONS", "CT2A_FUNCTIONS", "ClassEntry", "ClassUnavailable", "entries", "all_entries", "entry", "option_id",
    "resolve_class", "resolve_ct2a", "signature_defaults", "param_kind", "OUT_OF_CATALOGUE", "PARAM_HELP",
    "CLASS_PARAM_HELP", "CUMULATIVE_WITHOUT_EFFECT",
    "PARAM_HELP_TEMPLATE", "texts", "POSITION_LABELS", "position_label",
]

ENGINE = "engine"
DEFICIT = "deficit"
ROTOR = "rotor"
GROUND = "ground"
SUPERPOSITION = "superposition"
TURBULENCE = "turbulence"
BLOCKAGE = "blockage"
BLOCKAGE_SUPERPOSITION = "blockage_superposition"
POSITIONS = (ENGINE, DEFICIT, ROTOR, GROUND, SUPERPOSITION, TURBULENCE, BLOCKAGE, BLOCKAGE_SUPERPOSITION)

# The two functions PyWake offers for the Ct to axial induction relation (decision 4).
CT2A_MODULE = "py_wake.deficit_models.utils"
CT2A_FUNCTIONS = ("ct2a_madsen", "ct2a_mom1d")


class ClassUnavailable(RuntimeError):
    """A catalogue class (or ``ct2a`` function) that the installed PyWake does not have."""


@dataclass(frozen=True)
class ClassEntry:
    """One option of one position: an exact PyWake class, with the arguments fixed by the option."""

    position: str
    name: str
    module: str
    help: str
    params: Tuple[str, ...] = ()
    fixed: Mapping[str, Any] = field(default_factory=dict)
    predefined: str = ""
    predefined_turbulence: str = ""
    warning: str = ""

    @property
    def option(self) -> str:
        return option_id(self.name, self.fixed)


def option_id(name: str, fixed: Optional[Mapping[str, Any]] = None) -> str:
    """``CGIRotorAvg(n=9)`` for an option with fixed arguments, the class name otherwise."""
    if not fixed:
        return name
    return f"{name}({', '.join(f'{k}={fixed[k]!r}' for k in sorted(fixed))})"


_E = "py_wake.wind_farm_models.engineering_models"
_G = "py_wake.deficit_models.gaussian"
_N = "py_wake.deficit_models.noj"
_R = "py_wake.rotor_avg_models.rotor_avg_model"
_S = "py_wake.superposition_models"

_ENTRIES = (
    # --- Engines (decision 6) ---
    ClassEntry(ENGINE, "PropagateDownwind", _E,
               "Propaga las estelas aguas abajo, turbina a turbina. No admite bloqueo."),
    ClassEntry(ENGINE, "All2AllIterative", _E,
               "Calcula la influencia de todas las turbinas sobre todas e itera hasta cumplir su tolerancia o agotar "
               "sus iteraciones. Admite bloqueo si se elige un modelo de bloqueo."),
    ClassEntry(ENGINE, "PropagateUpDownIterative", _E,
               "Propaga las estelas aguas abajo y el bloqueo aguas arriba, e itera. Admite bloqueo y exige que el "
               "déficit y el bloqueo usen la velocidad efectiva (use_effective_ws)."),
    # --- Wake deficits (decision 3; P0, section 2) ---
    ClassEntry(DEFICIT, "BastankhahGaussianDeficit", _G,
               "Déficit gaussiano de Bastankhah y Porté-Agel (2014), con expansión k constante.",
               ("ct2a", "k", "ceps", "ctlim", "use_effective_ws"),
               predefined="Modelo predefinido de PyWake: Bastankhah_PorteAgel_2014, que exige dar k y usa ct2a_mom1d y "
                          "la velocidad efectiva."),
    ClassEntry(DEFICIT, "NiayifarGaussianDeficit", _G,
               "Déficit gaussiano con expansión que depende de la TI local, k = a₁·TI + a₂ (Niayifar y Porté-Agel, "
               "2016).",
               ("ct2a", "a", "ceps", "ctlim", "use_effective_ws", "use_effective_ti"),
               predefined="Modelo predefinido de PyWake: Niayifar_PorteAgel_2016, con a = [0,3837; 0,003678], ct2a_mom1d, "
                          "velocidad efectiva, GaussianOverlapAvgModel y CrespoHernandez.",
               predefined_turbulence="CrespoHernandez"),
    ClassEntry(DEFICIT, "ZongGaussianDeficit", _G,
               "Extensión de Niayifar con el crecimiento gradual del empuje y la anchura de estela de Shapiro (Zong y "
               "Porté-Agel, 2020).",
               ("ct2a", "a", "ctlim", "deltawD", "eps_coeff", "lam", "B", "use_effective_ws", "use_effective_ti"),
               predefined="Modelo predefinido de PyWake: Zong_PorteAgel_2020, con eps_coeff = 0,35, velocidad efectiva, "
                          "WeightedSum y un CrespoHernandez propio (ct2a_mom1d, c = [0,73; 0,83; 0,03; −0,32]).",
               predefined_turbulence="CrespoHernandez (con sus propios ct2a y c)"),
    ClassEntry(DEFICIT, "CarbajofuertesGaussianDeficit", _G,
               "Versión con constantes medidas con lidar: ε empírico y nuevas constantes de expansión (Carbajo Fuertes "
               "et al., 2018).",
               ("ct2a", "a", "ceps", "use_effective_ws", "use_effective_ti"),
               predefined="Modelo predefinido de PyWake: CarbajoFuertes_etal_2018, con ct2a_mom1d, velocidad efectiva, "
                          "GaussianOverlapAvgModel y CrespoHernandez.",
               predefined_turbulence="CrespoHernandez"),
    ClassEntry(DEFICIT, "TurboGaussianDeficit", _G,
               "Déficit gaussiano TurbOPark (Nygaard, 2022): la expansión combina la TI ambiente y la generada por la propia estela.",
               ("ct2a", "A", "cTI", "ceps", "ctlim", "use_effective_ws", "use_effective_ti"),
               predefined="Modelo predefinido de PyWake: Nygaard_2022 (TurbOPark), con ct2a_mom1d, ctlim = 0,96, "
                          "GaussianOverlapAvgModel, Mirror(SquaredSum()), SquaredSum y la velocidad libre de la turbina "
                          "afectada (WS_jlk), que no está en la firma de la clase y no se puede elegir."),
    ClassEntry(DEFICIT, "BlondelSuperGaussianDeficit2020", _G,
               "Super-gaussiano: perfil de sombrero de copa cerca y gaussiano lejos (Blondel y Cathelain, 2020).",
               ("a_s", "b_s", "c_s", "b_f", "c_f", "ctlim", "use_effective_ws", "use_effective_ti"),
               predefined="Modelo predefinido de PyWake: Blondel_Cathelain_2020, con velocidad efectiva; en PyWake "
                          "2.6.18 no trae turbulencia y PyWake lo rechaza por eso; su propio ejemplo usa CrespoHernandez.",
               predefined_turbulence="CrespoHernandez (en el ejemplo de PyWake; el modelo predefinido no trae ninguna)"),
    ClassEntry(DEFICIT, "BlondelSuperGaussianDeficit2023", _G,
               "Super-gaussiano con los parámetros calibrados de Blondel (2023).",
               ("a_s", "b_s", "c_s", "b_f", "c_f", "ctlim", "use_effective_ws", "use_effective_ti")),
    ClassEntry(DEFICIT, "IEA37SimpleBastankhahGaussianDeficit", _G,
               "Bastankhah simplificado del caso de estudio IEA37 (equivale a Bastankhah con β = 1/√8).",
               predefined="Modelo predefinido de PyWake: IEA37CaseStudy1, con All2All (sin comprobar la convergencia) y "
                          "SquaredSum, en el sitio y las turbinas de ese caso."),
    ClassEntry(DEFICIT, "GCLDeficit", "py_wake.deficit_models.gcl",
               "Modelo semianalítico de G. C. Larsen (2009), con estela de simetría rotacional.",
               ("use_effective_ws", "use_effective_ti"),
               predefined="Modelos predefinidos de PyWake: GCL (LinearSum, sin rotor ni turbulencia) y GCLLocal (velocidad "
                          "y TI efectivas)."),
    ClassEntry(DEFICIT, "NOJDeficit", _N,
               "Jensen (NOJ): déficit de sombrero de copa con expansión lineal k.",
               ("ct2a", "k"),
               predefined="Modelo predefinido de PyWake: Jensen_1983, con SquaredSum."),
    ClassEntry(DEFICIT, "NOJLocalDeficit", _N,
               "Como NOJ, pero con la velocidad y la TI locales; k depende de la TI como en Niayifar.",
               ("ct2a", "a", "use_effective_ws", "use_effective_ti"),
               predefined="Modelo predefinido de PyWake: NOJLocal, con LinearSum y STF2017TurbulenceModel.",
               predefined_turbulence="STF2017TurbulenceModel"),
    ClassEntry(DEFICIT, "TurboNOJDeficit", _N,
               "NOJ con la expansión de Nygaard (2020), proporcional a la TI local en la estela.",
               ("ct2a", "A", "cTI", "use_effective_ws", "use_effective_ti")),
    # --- Rotor average of the deficit (decision 4) ---
    ClassEntry(ROTOR, "RotorCenter", _R,
               "Un único punto en el centro del rotor, como modelo explícito."),
    ClassEntry(ROTOR, "CGIRotorAvg", _R, "Integración gaussiana circular con n puntos (4, 7, 9 o 21; 7 en su firma)."),
    ClassEntry(ROTOR, "EqGridRotorAvg", _R, "Rejilla regular de n × n puntos dentro del rotor (n = 4)."),
    ClassEntry(ROTOR, "GaussianOverlapAvgModel", "py_wake.rotor_avg_models.gaussian_overlap_model",
               "Solape exacto de la estela gaussiana con el rotor, leído de una tabla de PyWake (necesita h5py y "
               "h5netcdf)."),
    ClassEntry(ROTOR, "AreaOverlapAvgModel", "py_wake.rotor_avg_models.area_overlap_model",
               "Fracción del área del rotor dentro de una estela de sombrero de copa."),
    # --- Ground model of the deficit ---
    ClassEntry(GROUND, "Mirror", "py_wake.ground_models.ground_models",
               "El suelo como espejo: añade turbinas imagen bajo el terreno."),
    ClassEntry(GROUND, "MultiMirror", "py_wake.ground_models.ground_models",
               "El suelo y un espejo en altura (por defecto a 1000 m); el número de turbinas imagen crece como "
               "2^(2 + max(0, n_reps))."),
    # --- Wake superposition (the «Automático» option is gone) ---
    ClassEntry(SUPERPOSITION, "LinearSum", _S, "Suma de los déficits."),
    ClassEntry(SUPERPOSITION, "SquaredSum", _S, "Raíz de la suma de los cuadrados (Katic et al., 1986)."),
    ClassEntry(SUPERPOSITION, "MaxSum", _S, "El mayor de los déficits."),
    ClassEntry(SUPERPOSITION, "WeightedSum", _S,
               "Suma ponderada que conserva el momento (Zong y Porté-Agel, 2020); iterativa."),
    ClassEntry(SUPERPOSITION, "CumulativeWakeSum", _S, "Estela acumulada (Bastankhah et al., 2021).",
               warning="Con CumulativeWakeSum, PyWake 2.6.18 da resultados que dependen del orden de las turbinas "
                       "(comprobado con tres turbinas iguales); no está verificado."),
    # --- Added turbulence ---
    ClassEntry(TURBULENCE, "STF2005TurbulenceModel", "py_wake.turbulence_models.stf",
               "Frandsen, según la IEC 61400-1 de 2005."),
    ClassEntry(TURBULENCE, "STF2017TurbulenceModel", "py_wake.turbulence_models.stf",
               "Frandsen, según la IEC 61400-1 de 2017."),
    ClassEntry(TURBULENCE, "GCLTurbulence", "py_wake.turbulence_models.gcl_turb", "G. C. Larsen, según Pierik et al."),
    ClassEntry(TURBULENCE, "CrespoHernandez", "py_wake.turbulence_models.crespo", "Crespo y Hernández (1996)."),
)

_WS_ILK_WARNING = ("Con PropagateUpDownIterative, este bloqueo de PyWake 2.6.18 calcula con la velocidad libre aunque "
                   "use_effective_ws esté marcado: no escala con la velocidad efectiva que PropagateUpDownIterative "
                   "exige; no está verificado.")
_BLOCKAGES = (
    ("SelfSimilarityDeficit2020", "py_wake.deficit_models.selfsimilarity",
     "Autosemejanza de Troldborg y Meyer Forsting, versión revisada (2020).", ""),
    ("SelfSimilarityDeficit", "py_wake.deficit_models.selfsimilarity",
     "Autosemejanza de Troldborg y Meyer Forsting (2016).", ""),
    ("VortexCylinder", "py_wake.deficit_models.vortexcylinder",
     "Cilindro semiinfinito de vorticidad tangencial (Branlard).", _WS_ILK_WARNING),
    ("VortexDipole", "py_wake.deficit_models.vortexdipole",
     "Dipolo de vórtice: más simple que el cilindro de vórtice y, según PyWake, muy parecido a él solo en campo "
     "lejano (r/R > 6).", _WS_ILK_WARNING),
    ("HybridInduction", "py_wake.deficit_models.hybridinduction",
     "Combina una aproximación cerca del rotor y otra lejana, con un radio de cambio.", _WS_ILK_WARNING),
    ("RankineHalfBody", "py_wake.deficit_models.rankinehalfbody",
     "Semicuerpo de Rankine con la fuente fijada por el momento 1-D.", _WS_ILK_WARNING),
    ("Rathmann", "py_wake.deficit_models.rathmann",
     "Aproximación de Rathmann (DTU, 2020) al cilindro de vórtice.", _WS_ILK_WARNING),
    ("RathmannScaled", "py_wake.deficit_models.rathmann",
     "Rathmann escalado con el Ct para compensar la expansión de la estela.", _WS_ILK_WARNING),
)
# The warning of decision 19 applies to these blockage models only under PropagateUpDownIterative (D3).
_ENTRIES += tuple(ClassEntry(BLOCKAGE, n, m, h, ("use_effective_ws",), warning=w) for n, m, h, w in _BLOCKAGES)
_ENTRIES += (
    ClassEntry(BLOCKAGE_SUPERPOSITION, "LinearSum", _S, "Suma de los bloqueos."),
    ClassEntry(BLOCKAGE_SUPERPOSITION, "MaxSum", _S, "El mayor de los bloqueos."),
    ClassEntry(BLOCKAGE_SUPERPOSITION, "SquaredSum", _S,
               "Raíz de la suma de los cuadrados; PyWake no la admite con aceleraciones (valores negativos)."),
    ClassEntry(BLOCKAGE_SUPERPOSITION, "WeightedSum", _S,
               'Los motores de PyWake llaman a la superposición del bloqueo con una única matriz y WeightedSum necesita más datos: PyWake se detiene al evaluar el bloqueo entre turbinas (con All2AllIterative, siempre; con PropagateUpDownIterative, desde la segunda turbina).'),
    ClassEntry(BLOCKAGE_SUPERPOSITION, "CumulativeWakeSum", _S,
               'Los motores de PyWake llaman a la superposición del bloqueo con una única matriz y CumulativeWakeSum necesita más datos: PyWake se detiene al evaluar el bloqueo entre turbinas (con All2AllIterative, siempre; con PropagateUpDownIterative, desde la segunda turbina).'),
)

# Help of the arguments that change what the deficit (or the blockage) uses (README, «Ayudas», c); every other
# argument shows its PyWake name and its signature value (e).
PARAM_HELP = {
    "use_effective_ws": "True: el déficit escala con la velocidad efectiva que llega a la turbina; False: con la "
                        "velocidad libre. PropagateUpDownIterative exige True.",
    "use_effective_ti": "True: el déficit usa la TI efectiva (ambiente más la añadida por las estelas) y exige un modelo "
                        "de turbulencia; False: usa la TI ambiente.",
    "ct2a": "Relación entre el Ct y el factor de inducción axial: ct2a_madsen, ajuste para Ct altos (Madsen et al., "
            "2020); ct2a_mom1d, teoría de momento 1-D (Ct = 4a(1 − a), con min(1, Ct)).",
}
PARAM_HELP_TEMPLATE = "{name} (PyWake). Valor de la firma: {value}."
# The help of an argument that one class keeps but never uses in PyWake 2.6.18 (decision 23a).
CLASS_PARAM_HELP = {
    ("ZongGaussianDeficit", "ctlim"): "ctlim (PyWake). Valor de la firma: {value}. ZongGaussianDeficit lo guarda, pero "
                                      "PyWake 2.6.18 no lo usa en el cálculo: su ε es constante (eps_coeff).",
}

# Decision 23(a): with CumulativeWakeSum, PyWake takes from the deficit only its width (sigma_ijlk) and the rotor
# average of its crosswind distance, and computes the amplitude in the superposition (engineering_models.py:798-814,
# 1071-1074; superposition_models.py:219-259). The arguments of each deficit that only enter the amplitude, so they
# have no numerical effect along that path (gaussian.py:43-46, 364-375, 427-440; tests.test_wake_cumulative).
# use_effective_ws is left out with PropagateUpDownIterative, which requires True; the ground of the deficit is added
# with PropagateDownwind and PropagateUpDownIterative (with All2AllIterative it is R9d).
CUMULATIVE_WITHOUT_EFFECT = {
    "BastankhahGaussianDeficit": ("ct2a", "use_effective_ws"),
    "NiayifarGaussianDeficit": ("ct2a", "use_effective_ws"),
    "ZongGaussianDeficit": ("ct2a", "deltawD", "use_effective_ws"),
    "CarbajofuertesGaussianDeficit": ("ct2a", "use_effective_ws"),
    "TurboGaussianDeficit": ("ct2a", "use_effective_ws"),
    "IEA37SimpleBastankhahGaussianDeficit": (),
}

# Out of the catalogue, with the reason the help gives (decisions 3 and 13).
OUT_OF_CATALOGUE = (
    "Fuera del menú: las clases que necesitan tablas que el complemento no aporta (FugaDeficit, FugaMultiLUTDeficit, "
    "FugaYawDeficit, RANSLUTDemoDeficit, RANSLUTDeficit, RANSLUTConvDeficit, XRLUTDeficitModel); NoWakeDeficit, porque "
    "el caso sin estelas ni bloqueo ya lo da el AEP bruto (el escenario de solo bloqueo queda fuera por alcance); y la "
    "deflexión de estela, porque el complemento no calcula el AEP con yaw."
)


# The names of the positions in the messages (translated in ``messages_translations.py``).
POSITION_LABELS = {ENGINE: "motor", DEFICIT: "déficit de estela", ROTOR: "promedio de rotor", GROUND: "suelo",
                   SUPERPOSITION: "superposición de estelas", TURBULENCE: "turbulencia añadida", BLOCKAGE: "bloqueo",
                   BLOCKAGE_SUPERPOSITION: "superposición del bloqueo"}


def position_label(position: str):
    """The name of a position for a message (a translatable template); other keys are returned as they are."""
    return log_text(POSITION_LABELS[position]) if position in POSITION_LABELS else position


def entries(position: str) -> Tuple[ClassEntry, ...]:
    """The options of a position, in the order the dialog shows them."""
    if position not in POSITIONS:
        raise KeyError(position)
    return tuple(e for e in _ENTRIES if e.position == position)


def all_entries() -> Tuple[ClassEntry, ...]:
    """Every option of every position."""
    return _ENTRIES


def entry(position: str, name: str, fixed: Optional[Mapping[str, Any]] = None) -> ClassEntry:
    """The option of ``position`` for the class ``name`` and its fixed arguments; ``KeyError`` if it is not offered."""
    wanted = option_id(name, fixed)
    for e in entries(position):
        if e.option == wanted:
            return e
    raise KeyError(f"{position}: {wanted}")


def resolve_class(e: ClassEntry) -> type:
    """The exact class of the installed PyWake; ``ClassUnavailable`` if it does not have it. No fallback."""
    try:
        module = importlib.import_module(e.module)
    except Exception as exc:
        raise ClassUnavailable(log_text("PyWake no tiene el módulo {module} de {cls}: {error}", module=e.module,
                                         cls=e.name, error=str(exc))) from exc
    cls = module.__dict__.get(e.name)
    if not inspect.isclass(cls) or cls.__name__ != e.name:
        raise ClassUnavailable(log_text("La instalación de PyWake no tiene la clase {cls} en {module}.", cls=e.name,
                                         module=e.module))
    return cls


def resolve_ct2a(name: str):
    """One of the two ``ct2a`` functions of PyWake, by name."""
    if name not in CT2A_FUNCTIONS:
        raise KeyError(f"ct2a: {name}")
    module = importlib.import_module(CT2A_MODULE)
    fn = module.__dict__.get(name)
    if not inspect.isfunction(fn):
        raise ClassUnavailable(log_text("La instalación de PyWake no tiene la función {cls} en {module}.", cls=name,
                                         module=CT2A_MODULE))
    return fn


def signature_defaults(e: ClassEntry) -> Dict[str, Any]:
    """Every argument of the class signature with its default value, in signature order (decision 2).

    Arguments without a default (``site``, ``windTurbines`` of the engines) and ``*args``/``**kwargs`` are left out.
    The values are PyWake's own objects: callers copy them before use.
    """
    out: Dict[str, Any] = {}
    for name, p in inspect.signature(resolve_class(e).__init__).parameters.items():
        if name == "self" or p.kind in (p.VAR_POSITIONAL, p.VAR_KEYWORD) or p.default is inspect.Parameter.empty:
            continue
        out[name] = p.default
    return out


def param_kind(default: Any) -> str:
    """The control of an editable argument from its default (decision 4): bool, ct2a, list or number."""
    if isinstance(default, bool):
        return "bool"
    if inspect.isfunction(default) and default.__name__ in CT2A_FUNCTIONS:
        return "ct2a"
    if isinstance(default, (list, tuple)):
        return "list"
    if isinstance(default, (int, float)):
        return "number"
    raise TypeError(f"Argumento editable de un tipo no previsto: {default!r}")


def texts() -> Tuple[str, ...]:
    """Every Spanish source text of the catalogue, once (for the translation tables and their tests)."""
    seen: list = []
    for e in _ENTRIES:
        for t in (e.help, e.predefined, e.predefined_turbulence, e.warning):
            if t and t not in seen:
                seen.append(t)
    for t in tuple(PARAM_HELP.values()) + tuple(CLASS_PARAM_HELP.values()) + (PARAM_HELP_TEMPLATE, OUT_OF_CATALOGUE):
        if t not in seen:
            seen.append(t)
    return tuple(seen)

# -*- coding: utf-8 -*-
"""The «Modelo de estela» group of the Energy dialog (#46 P5a), and its mirror in the interactive map.

``WakeModelGroup`` shows, one line each, the engine, the wake deficit, the wake superposition, the blockage (with
All2AllIterative and PropagateUpDownIterative only) and the added turbulence; everything subordinate goes in folded
sections: the deficit's parameters with its rotor average and ground model, the parameters of the superposition and
of the turbulence, the blockage's options (its superposition, ``use_effective_ws`` and its parameters) and the
engine's numerical settings. Below a section, no more folds (#64, decision 1): the arguments of a subordinate object
go in the line of its selector (the ``n`` of a rotor average) or, for a ground model, in a small window opened with a
button, summarised next to it. The arguments PyWake has and the plugin does not offer are listed with their reason.

It never changes a choice by itself. What PyWake (or the plugin) refuses is shown as a conflict next to the visible
selector it belongs to, with its reason and its resolution; a conflict inside a folded section unfolds it, without
changing any value. An option that no other choice can make calculable is disabled with its reason, but stays
selected if it already was. Each deficit class and each blockage model keeps its draft during the dialog's session,
and so do the arguments of each engine, superposition, turbulence, rotor average and ground model; changing the
engine does not touch them. «Restablecer» in each section takes what it shows back to its signature (see
``reset_section``).
Between sessions the engine, the class, the superposition, the turbulence and the blockage are remembered, if they
are still options, and open with the values of their signatures; a remembered choice that is no longer an option is
said, not replaced in silence.

Two modes (plan of the predefined models), chosen with two joined buttons under the title: «Modelos predefinidos»,
the predefined wind farm models of PyWake (``presets``), one chosen in «Modelo» and its whole configuration shown with
the hierarchy of the manual mode, read-only (the sections unfold, the helps are read and the windows open to be read
and closed); and «Modo manual», everything above. Each mode keeps its own choices, in its own keys: nothing is copied
from one to the other. A new installation opens with the predefined NOJ; one with choices of the manual mode saved,
with the manual mode.

``config()`` gives the ``WakeConfig`` of the selection (``None`` while a field cannot be read), ``issues()`` its
conflicts and ``provenance()`` that of a predefined model. Nothing here calculates; the dialog connects it (P5b).
"""
from __future__ import annotations

import inspect
import json
import re
from dataclasses import replace
from html import escape
from typing import Any, Callable, Dict, List, Optional, Tuple

from qgis.PyQt import QtCore, QtGui, QtWidgets

from ..ag_core.log_text import log_text, shown
from ..ag_core.wake_setup import catalog as _cat
from ..ag_core.wake_setup import config as _cfg
from ..ag_core.wake_setup import factory as _f
from ..ag_core.wake_setup import notices as _notices
from ..ag_core.wake_setup import presets as _presets
from ..ag_core.wake_setup import readers as _readers
from ..ag_core.wake_setup import subordinates as _sub
from ..ag_core.wake_setup import validation as _val
from ..ag_core.wake_setup.catalog import (BLOCKAGE, BLOCKAGE_SUPERPOSITION, DEFICIT, ENGINE, GROUND, ROTOR,
                                          SUPERPOSITION, TURBULENCE)
from ..ag_core.wake_setup.catalog_translations import register_catalog_translations
from ..ag_core.wake_setup.config import Component, WakeConfig
from ..ag_core.wake_setup.messages_translations import register_messages_translations
from ..ag_core.wake_setup.subordinates_translations import register_subordinates_translations
from ..i18n import mark_translated
from .wake_controls import CollapsibleSection, ComponentWindow, INHERIT_WAKES, ParamEditor, READ_ONLY_STYLE, \
    SubordinateEditor, coloured_lines, fill_option_combo, window_mark
from .wake_group_translations import register_wake_group_translations

__all__ = ["WakeModelGroup", "WakeGroupMirror", "NONE", "SETTINGS_PREFIX", "SHOWN_POSITIONS", "PREDEFINED", "MANUAL",
           "MODE_KEY", "PRESET_KEY"]

# The texts of the group are translated wherever it is built.
register_catalog_translations()
register_messages_translations()
register_wake_group_translations()
register_subordinates_translations()

NONE = ""  # the data of the «Ninguno» options: an absence asked for, never ``None``
SETTINGS_PREFIX = "wake_physics/"
SHOWN_POSITIONS = (ENGINE, DEFICIT, SUPERPOSITION, BLOCKAGE, TURBULENCE)  # the visible selectors, remembered
# The two modes and their keys, apart from those of the manual mode (decisions 9 and 14 of the predefined models).
PREDEFINED, MANUAL = "predefined", "manual"
MODE_KEY, PRESET_KEY = "wake_presets/mode", "wake_presets/preset"
MODE_LABELS = {PREDEFINED: "Modelos predefinidos", MANUAL: "Modo manual"}
DEFAULT_PRESET = "NOJ"
# The information points (help of the modes, of a predefined model and of each selector), Spanish source texts
# translated when shown. A paragraph is separated by a blank line; its first line, if it has more, is its heading.
GENERAL_HELP = (
    "¿Qué define este grupo?\n"
    "Cómo se calculan las pérdidas por estela entre turbinas y, si se elige, el bloqueo. Hay dos modos:\n"
    "• Modelos predefinidos: configuraciones de referencia completas, basadas en PyWake 2.6.18, que se seleccionan "
    "de una vez.\n"
    "• Modo manual: cada componente se elige por separado, incluido el bloqueo.\n\n"
    "Cada pestaña de esta ventana explica un modo. Además, cada selector tiene su propio icono de información con lo "
    "que controla y la opción elegida.")
PREDEFINED_HELP = (
    "¿Qué hace este modo?\n"
    "Selecciona una configuración de referencia completa: una combinación de componentes (motor, déficit, "
    "superposición, turbulencia, promedio de rotor y suelo) y de sus parámetros, basada en las clases predefinidas de "
    "PyWake 2.6.18, con las adaptaciones que el plugin documenta en cada modelo. Los ajustes aparecen debajo, solo "
    "para consulta; el icono junto a «Modelo» explica la formulación y las referencias del modelo elegido.\n\n"
    "¿Cuándo utilizarlo?\n"
    "Para calcular con una configuración conocida o compararla con otras. Los modelos predefinidos que ofrece este "
    "plugin no incluyen bloqueo; PyWake tiene otros que sí, como FugaBlockage, que aquí no se ofrece. Para construir "
    "otras combinaciones compatibles, con o sin bloqueo, usa el «Modo manual».\n\n"
    "Versiones y alcance\n"
    "Las configuraciones se definieron con PyWake 2.6.18; el cálculo usa la versión de PyWake instalada y el "
    "resultado registra las dos. Reproducir una configuración de referencia no garantiza su precisión para un parque "
    "concreto.")
MANUAL_HELP = (
    "¿Qué permite este modo?\nElegir por separado el motor, el déficit de estela, la superposición de estelas, la "
    "turbulencia añadida, el promedio de rotor, el suelo y el bloqueo, con sus parámetros. El programa señala las "
    "combinaciones que PyWake no puede calcular. Que una combinación se pueda calcular no la valida para un "
    "emplazamiento, y que difiera de un modelo predefinido no la hace incorrecta. El icono de cada selector explica "
    "qué controla y la opción elegida.\n\nConfiguración de estelas\nEl motor determina cómo se propagan y resuelven "
    "las interacciones entre turbinas, no la precisión física del modelo. El déficit describe la reducción de "
    "velocidad detrás de cada turbina y cómo se ensancha la estela; la superposición, cómo se combinan los déficits "
    "de velocidad de varias estelas; la turbulencia añadida estima el aumento de la intensidad de turbulencia (TI) en "
    "las estelas, que solo influye si el déficit la utiliza.")
EXAMPLES_HELP = (
    "Ejemplos de configuración\nVelantis propone dos ejemplos para explorar el comportamiento de los modelos; cada "
    "uno indica las hipótesis y los datos que requiere.\n• Expansión constante: BastankhahGaussianDeficit, sin "
    "turbulencia añadida. k controla cuánto se ensancha la estela con la distancia; su valor debe justificarse con "
    "datos, referencias aplicables o un análisis de sensibilidad, no ajustarse hasta obtener el resultado deseado. "
    "Añadir un modelo de turbulencia no cambia este déficit: con k fijo no responde a la TI calculada, y estudiar esa "
    "dependencia exige otra formulación o un tratamiento justificado de k.\n• Expansión dependiente de la TI: "
    "NiayifarGaussianDeficit (k = a₁·TI + a₂), con use_effective_ti = True y CrespoHernandez como turbulencia "
    "añadida. Requiere una TI ambiente representativa en el recurso. Con use_effective_ti = True la expansión usa la "
    "TI efectiva, la ambiente más la añadida por las estelas que estima CrespoHernandez; con False usa solo la "
    "ambiente y la turbulencia añadida no cambia el déficit.\n\nEmplazamientos marinos y terrestres\nEn emplazamientos "
    "marinos, normalmente asociados con una menor turbulencia, la «Expansión constante» es un buen punto de partida. "
    "En los terrestres, donde el relieve influye en la turbulencia, una selección como la «Expansión dependiente de la "
    "TI» suele ajustarse mejor.\n\nEstudiar el bloqueo\nEl bloqueo es el efecto de inducción de las turbinas sobre el "
    "flujo: lo frenan sobre todo aguas arriba del rotor. No son las estelas aguas abajo ni los efectos del relieve. "
    "Para estudiarlo, cambia el motor a All2AllIterative o PropagateUpDownIterative y elige un modelo de bloqueo; con "
    "«Ninguno» no se calcula. Su superposición es independiente de la de las estelas y puede usar la misma "
    "regla.\n\nPara una primera prueba recomendamos All2AllIterative con SelfSimilarityDeficit2020; con ellos, el "
    "resto de recomendaciones de los ejemplos anteriores se puede mantener.")
VALIDATION_HELP = (
    "Comparar con y sin bloqueo\n"
    "Es un análisis de sensibilidad del modelo. Mantén la disposición del parque, las turbinas, el recurso y su discretización, las "
    "curvas de Ct y de potencia, el motor (el mismo, compatible con bloqueo, en los dos cálculos) y los ajustes de "
    "estela, turbulencia y rotor; cambia solo el bloqueo y sus componentes: modelo, superposición y suelo del "
    "bloqueo. La diferencia cuantifica el efecto de ese cambio dentro de la simulación; no mide el bloqueo real ni "
    "valida el resultado.\n\n"
    "Comprobar los resultados\n"
    "Terminar sin error no garantiza la convergencia ni la exactitud. Los avisos del resultado indican si un bucle "
    "iterativo (All2AllIterative, PropagateUpDownIterative o WeightedSum) no convergió o no pudo comprobarse. Revisa "
    "además que las velocidades y la producción sean plausibles y cómo cambian con otras elecciones de modelo; "
    "validarlas exige contrastarlas con observaciones o referencias independientes apropiadas.")
# The help of a predefined model: its class, its formulation, where it comes from and what is particular to it.
PRESET_MODEL_HELP = "{model}\nClase de referencia de PyWake 2.6.18: {reference}"
PRESET_SCOPE = ("Los ajustes aparecen debajo. Las referencias describen la formulación del déficit; el resto de la "
                "combinación es la de la clase de PyWake y no siempre procede de ellas. Reproducir esta configuración "
                "no garantiza su precisión para un parque concreto.")
PRESET_REFERENCES = "Referencias"
PRESET_DOCUMENTATION = "Documentación de PyWake: {url}"
PRESET_PARTICULARS = "Particularidades de esta configuración"
PRESET_ADAPTATION = ("Si faltan h5py o h5netcdf y aceptas sustituir GaussianOverlapAvgModel por CGIRotorAvg(7), el "
                     "cálculo deja de corresponder a esta configuración de referencia y el resultado lo registra como "
                     "configuración adaptada.")
_PAPER, _REPORT, _BENCHMARK, _CODE = ("Artículo", "Informe técnico", "Definición de caso de referencia",
                                      "Documentación técnica y código")
# Per model: its translated formulation and references (kind, citation, verified link).
# Scientific citations and links stay as published; descriptive code captions are translated.
PRESET_HELP: Dict[str, Tuple[str, Tuple[Tuple[str, str, str], ...]]] = {
    "NOJ": (
        "Déficit de sombrero de copa (velocidad uniforme dentro de la estela) cuyo radio crece linealmente con la "
        "distancia según k (0,1 en esta clase). La clase de PyWake lo combina con AreaOverlapAvgModel, adecuado a ese "
        "perfil, y SquaredSum.",
        ((_REPORT, "Jensen, N. O. (1983). A note on wind generator interaction. Risø-M-2411, Risø National "
                   "Laboratory.", "https://orbit.dtu.dk/en/publications/a-note-on-wind-generator-interaction"),)),
    "BastankhahGaussian": (
        "Déficit gaussiano deducido de la conservación de masa y de cantidad de movimiento; la anchura de la estela "
        "crece linealmente según k, que es constante e independiente de la intensidad de turbulencia (TI). La clase de "
        "PyWake usa LinearSum y la velocidad efectiva (use_effective_ws = True).",
        ((_PAPER, "Bastankhah, M. & Porté-Agel, F. (2014). A new analytical model for wind-turbine wakes. Renewable "
                  "Energy, 70, 116–123.", "https://doi.org/10.1016/j.renene.2014.01.002"),)),
    "IEA37SimpleBastankhahGaussian": (
        "Variante simplificada de Bastankhah definida para los casos de estudio 1 y 2 de optimización de la disposición del parque de "
        "IEA Wind Task 37: k = 0,0324555 fijo y anchura inicial D/√8. La clase de PyWake usa SquaredSum.",
        ((_BENCHMARK, "IEA Wind Task 37, case studies 1–2: wake model (iea37-wakemodel.pdf).",
          "https://github.com/IEAWindSystems/iea37-wflo-casestudies/blob/master/cs1-2/iea37-wakemodel.pdf"),
         (_PAPER, "Baker, N. F. et al. (2019). Best practices for wake model and optimization algorithm selection in "
                  "wind farm layout optimization. AIAA SciTech 2019 Forum.", "https://doi.org/10.2514/6.2019-0540"))),
    "NiayifarGaussian": (
        "Extiende el déficit gaussiano de Bastankhah a parques: la expansión depende linealmente de la intensidad de "
        "turbulencia (TI) local, k = a₁·TI + a₂, con a = [0,3837; 0,003678]. Con use_effective_ti = True, la TI local "
        "incluye la turbulencia añadida que estima CrespoHernandez. La publicación lo validó con medidas de "
        "producción y LES del parque marino Horns Rev. La clase de PyWake añade GaussianOverlapAvgModel.",
        ((_PAPER, "Niayifar, A. & Porté-Agel, F. (2016). Analytical modeling of wind farms: a new approach for power "
                  "prediction. Energies, 9(9), 741.", "https://doi.org/10.3390/en9090741"),)),
    "ZongGaussian": (
        "Extiende Niayifar con un crecimiento gradual del empuje y una anchura de estela inspirada en Shapiro et al.; "
        "la expansión depende de la intensidad de turbulencia (TI) local. Se combina con WeightedSum, la "
        "superposición que conserva la cantidad de movimiento propuesta en la misma publicación, y con un "
        "CrespoHernandez con los coeficientes de la clase de PyWake.",
        ((_PAPER, "Zong, H. & Porté-Agel, F. (2020). A momentum-conserving wake superposition method for wind farm "
                  "power prediction. Journal of Fluid Mechanics, 889, A8.", "https://doi.org/10.1017/jfm.2020.77"),)),
    "SuperGaussian": (
        "Perfil supergaussiano: casi de sombrero de copa en la estela cercana y gaussiano en la lejana. La anchura "
        "depende de la intensidad de turbulencia (TI) y del Ct; en la implementación de PyWake 2.6.18, el orden del "
        "perfil depende solo de la distancia. PyWake toma los parámetros calibrados de la publicación y usa "
        "LinearSum.",
        ((_PAPER, "Blondel, F. & Cathelain, M. (2020). An alternative form of the super-Gaussian wind turbine wake "
                  "model. Wind Energy Science, 5, 1225–1236.", "https://doi.org/10.5194/wes-5-1225-2020"),)),
    "TurbOPark": (
        "TurboGaussianDeficit es el déficit: gaussiano, con una expansión que combina la intensidad de turbulencia (TI) ambiente y la generada por la propia estela (expresión de Frandsen), con A = 0,04 calibrado con datos. Nygaard_2022 es la composición completa: además, GaussianOverlapAvgModel, Mirror(SquaredSum()) en la estela, SquaredSum, ninguna turbulencia añadida y el déficit escalado con la velocidad libre de la turbina que recibe la estela (WS_jlk), como en la implementación de referencia.\n\nEn este plugin esa referencia de velocidad solo existe dentro de este modelo predefinido, que usa PropagateDownwind: el modo manual no permite elegirla, así que TurboGaussianDeficit con otro motor o con bloqueo no reproduce Nygaard_2022. Es una restricción actual del plugin, no del modelo.",
        ((_PAPER, "Pedersen, J. G. et al. (2022). Turbulence Optimized Park model with Gaussian wake profile. "
                  "Journal of Physics: Conference Series, 2265, 022063.",
          "https://doi.org/10.1088/1742-6596/2265/2/022063"),)),
}
ROW_EXPLANATIONS = {
    ENGINE: "El motor determina cómo se propagan y resuelven las interacciones entre turbinas; no determina por sí "
            "solo la precisión física. PropagateDownwind propaga las estelas aguas abajo y no admite bloqueo. "
            "All2AllIterative y PropagateUpDownIterative iteran y admiten bloqueo, pero solo lo calculan si además "
            "se elige un modelo de bloqueo.",
    DEFICIT: "El déficit describe cuánto se reduce la velocidad detrás de una turbina y cómo se ensancha la estela "
             "con la distancia: con una expansión constante (k) o dependiente de la intensidad de turbulencia (TI). "
             "use_effective_ws hace que escale con la velocidad efectiva que recibe la turbina en vez de con la "
             "libre; use_effective_ti, que use la TI efectiva (la ambiente más la añadida por las estelas) en vez de "
             "la ambiente. Son ajustes independientes.",
    ROTOR: "Evalúa un déficit representativo sobre el área barrida por el rotor que recibe la estela. «Ninguno» y "
           "RotorCenter usan el centro; CGIRotorAvg (4, 7, 9 o 21 puntos) y EqGridRotorAvg muestrean puntos del "
           "rotor; GaussianOverlapAvgModel integra el solape con una estela gaussiana y AreaOverlapAvgModel calcula "
           "la fracción cubierta por una estela de sombrero de copa. Más puntos suelen mejorar la estimación del "
           "promedio, con más coste y según su distribución, pero no corrigen las hipótesis del modelo; ningún "
           "número de puntos es suficiente en general.",
    GROUND: "Mirror refleja las turbinas en el plano del suelo para imponer una superficie ideal, sin velocidad "
            "normal a ella; no representa rugosidad, oleaje, orografía ni estabilidad atmosférica. Según la "
            "documentación de PyWake, muchos modelos de estela se calibraron con el efecto del suelo incluido y "
            "añadirlo puede contarlo dos veces; otros lo usan expresamente, como el modelo predefinido TurbOPark. "
            "MultiMirror añade un segundo plano de reflexión en altura (mirror_height) para representar el bloqueo "
            "adicional de una inversión térmica baja e intensa; su altura debe justificarse con datos del perfil "
            "atmosférico.",
    SUPERPOSITION: "Indica cómo se combinan los déficits de velocidad de varias estelas que alcanzan una turbina; no "
                   "suma pérdidas de energía. Las reglas parten de hipótesis distintas y no son intercambiables. La "
                   "documentación de PyWake recomienda en general LinearSum con use_effective_ws = True, para evitar "
                   "velocidades negativas, y suele usar SquaredSum con déficits escalados con la velocidad libre. La "
                   "regla de un modelo predefinido no es la única admisible; que el programa acepte una combinación "
                   "indica que se puede calcular, no que sus hipótesis sean coherentes ni que esté validada.",
    BLOCKAGE: "El bloqueo es el efecto de inducción de las turbinas sobre el flujo, sobre todo aguas arriba del "
              "rotor; es distinto de las estelas aguas abajo y del relieve. «Ninguno»: no se calcula. "
              "SelfSimilarityDeficit2020 representa la inducción cerca de cada turbina; no basta por sí solo para la "
              "respuesta atmosférica de un gran parque ni para los efectos del terreno. Comparar con VortexCylinder "
              "u otros modelos sirve para estudiar la sensibilidad; VortexDipole se aproxima al cilindro solo en "
              "campo lejano (r/R > 6, según PyWake). Fuga depende de tablas LUT adecuadas, calculadas previamente "
              "con un modelo RANS linealizado, y no está en el catálogo del plugin.",
    BLOCKAGE_SUPERPOSITION: "Indica cómo se combinan los déficits de bloqueo de varias turbinas. Es independiente de "
                            "la superposición de estelas y puede usar la misma regla. Algunas reglas no se pueden "
                            "calcular para el bloqueo: lo indica la ayuda de cada opción.",
    TURBULENCE: "Estima la turbulencia añadida por las estelas; la intensidad de turbulencia (TI) efectiva combina la "
                "ambiente y la añadida. Solo cambia el déficit si este la utiliza: un déficit cuya expansión depende "
                "de la TI, con use_effective_ti = True. Con una expansión constante (k fijo), la turbulencia se "
                "calcula pero no modifica las pérdidas.",
}
SELECTED_HELP = "Opción seleccionada: {name}\nDetalle del modelo:"
INFO_TOOLTIP = "Ver explicación"
PRESETS_PAGE = "Modelos de parque con la configuración de PyWake: {link}"
PRESETS_FOOTER = "Para cambiar valores, usa el «Modo manual»."
# The resolution of a refusal of a predefined model: the actions it has (decision 13).
PRESET_RESOLUTION = "Elige otro modelo predefinido o usa el «Modo manual»."
STALE_PRESET = "El modelo predefinido guardado «{value}» ya no es una opción: se abre con {default}."
# Decision 21 of the predefined models: CGIRotorAvg(7) instead of the GaussianOverlapAvgModel of a model, without
# asking again, as the user decided for that model; in a key of its own, read and written by the dialog.
CONSENT_PREFIX = "wake_adaptation_consent/"
CONSENT_KEY = CONSENT_PREFIX + "gaussian_overlap_cgi7/v1/{preset}"
_MODULES = {"h5py", "h5netcdf"}


def _consent_keys(settings: Any, preset: str) -> List[str]:
    """Every decision saved for ``preset``, of this version of the plugin or of another one."""
    if settings is None:
        return []
    return [k for k in settings.allKeys() if k.startswith(CONSENT_PREFIX) and k.rsplit("/", 1)[-1] == preset]


def saved_consent(settings: Any, preset: str) -> Optional[Dict[str, Any]]:
    """The decision saved for ``preset`` (its revision and the libraries it was taken for), or ``None``: none, one
    this version cannot read exactly, or one next to another key it does not know; none of these authorizes anything."""
    key = CONSENT_KEY.format(preset=preset)
    if settings is None or any(k != key for k in _consent_keys(settings, preset)):
        return None
    raw = settings.value(key, None)
    try:
        record = json.loads(raw) if isinstance(raw, str) else None
    except ValueError:
        return None
    if not isinstance(record, dict) or set(record) != {"version", "revision", "modules"}:
        return None
    version, revision, modules = record["version"], record["revision"], record["modules"]
    if type(version) is not int or version != 1 or type(revision) is not int or not isinstance(modules, list) or \
            not modules or not all(isinstance(m, str) and m in _MODULES for m in modules) or \
            len(set(modules)) != len(modules):
        return None
    return {"revision": revision, "modules": sorted(modules)}


def consent_applies(record: Optional[Dict[str, Any]], preset: str, missing: List[str]) -> bool:
    """Whether the decision saved authorizes this calculation: the same revision of the model and the same
    libraries missing, in any order."""
    return record is not None and record["revision"] == _presets.preset(preset).revision and \
        record["modules"] == sorted(missing)


def save_consent(settings: Any, preset: str, missing: List[str]) -> None:
    """The decision for ``preset``, instead of any earlier one."""
    if settings is not None:
        clear_consent(settings, preset)
        settings.setValue(CONSENT_KEY.format(preset=preset), json.dumps(
            {"version": 1, "revision": _presets.preset(preset).revision, "modules": sorted(missing)}))


def clear_consent(settings: Any, preset: str) -> None:
    for key in _consent_keys(settings, preset):
        settings.remove(key)


WS_REFERENCE_LINE = "Referencia del escalado: {reference} ({key})"
_PDW = "PropagateDownwind"
_PUD = "PropagateUpDownIterative"

NONE_HELP = {
    ROTOR: "Ninguno: la velocidad en el centro del rotor, sin promediar.",
    GROUND: "Ninguno: sin modelo de suelo.",
    TURBULENCE: "Ninguna: sin turbulencia añadida por las estelas; la TI es la ambiente.",
    BLOCKAGE: "Ninguno: sin bloqueo.",
}
NONE_LABEL = {ROTOR: "Ninguno", GROUND: "Ninguno", TURBULENCE: "Ninguna", BLOCKAGE: "Ninguno"}
NOTES_WITHOUT_BLOCKAGE = {
    "All2AllIterative": "Sin bloqueo, normalmente obtendrás resultados equivalentes con PropagateDownwind y menor coste "
                        "de cálculo. Pueden existir diferencias numéricas según la configuración.",
    _PUD: "Sin bloqueo, PUD mantiene el requisito de usar velocidad efectiva y realiza una propagación adicional. "
          "PropagateDownwind permite calcular este escenario con menor coste.",
}
PUD_REFUSED = ("PropagateUpDownIterative exige un déficit que escale con la velocidad efectiva, y {cls} no tiene "
               "use_effective_ws.")
STALE_PREFERENCE = ("La preferencia guardada «{value}» de {position} ya no es una opción: se abre con la de la firma "
                    "({default}).")
BLOCKAGE_PARAM_HELP = {
    "use_effective_ws": "True: el bloqueo escala con la velocidad efectiva que llega a la turbina; False: con la "
                        "velocidad libre. PropagateUpDownIterative exige True.",
}
UNREADABLE = "No se puede leer el valor de «{arg}» de {cls}: escribe un número."
EXCLUDED_ARG = "No se ofrece {name} = {value}: {reason}"
SIGNATURE_VALUE = "Valor de la firma: {value}."
# The integers with a minimum of the control: what PyWake does not build is corrected in view to the minimum, and
# through the API refused (R15); from −2 to 0 it builds and is warned (decision 5 of #64, option (a) of the user).
SPIN_MINIMUM = {("EqGridRotorAvg", "n"): -2}
SPIN_MINIMUM_HELP = {("EqGridRotorAvg", "n"): "Mínimo −2: de −2 a 0 no hay nodos y PyWake puede dar NaN; con −3 o menos "
                                              "no lo construye."}
# The help of a nested argument whose PyWake class has no text of its own, by its family.
FAMILY_HELP = {
    "rotor": "El promedio de rotor de este modelo, aparte del del déficit; ninguno: la velocidad en el centro del rotor.",
    "ground": "El modelo de suelo de este bloqueo, aparte del del déficit; ninguno: sin suelo.",
}
# The help of the options of a nested argument that are not options of a selector of the group.
OPTION_HELP = {
    ("ground_sum", None): "Hereda la superposición del objeto que envuelve: la de las estelas en el suelo del déficit, "
                          "la del bloqueo en el del bloqueo.",
    ("ti_sum", "LinearSum"): "TI efectiva = TI ambiente + la suma de las TI añadidas.",
    ("ti_sum", "SquaredSum"): "TI efectiva = TI ambiente + √(suma de los cuadrados de las TI añadidas).",
    ("ti_sum", "MaxSum"): "TI efectiva = TI ambiente + la mayor de las TI añadidas.",
    ("ti_sum", "SqrMaxSum"): "TI efectiva = √(TI ambiente² + (la mayor de las TI añadidas)²).",
    ("ground_sum", "WeightedSum"): "El suelo la llama con un único array y WeightedSum necesita más datos: PyWake se "
                                   "detiene donde evalúa el suelo.",
    ("ground_sum", "CumulativeWakeSum"): "El suelo la llama con un único array y CumulativeWakeSum necesita más datos: "
                                         "PyWake se detiene donde evalúa el suelo.",
    ("ground_sum", "SqrMaxSum"): "SqrMaxSum no se puede llamar con un único array: PyWake se detiene donde evalúa el "
                                 "suelo.",
    ("weight", "FrandsenWeight"): "Peso en campana de la tesis de Frandsen (Eq. 3.16), según el desplazamiento "
                                  "lateral de la turbina respecto de la estela.",
    ("weight", "IECWeight"): "La TI añadida entera dentro de un sector de 21,6° aguas abajo y hasta distance_limit "
                             "diámetros (IEC 61400-1).",
}
_FAMILY_POSITION = {"rotor": ROTOR, "ground": GROUND, "ground_sum": SUPERPOSITION}
WINDOW_CONFLICT = "La causa está en «Parámetros del modelo de suelo…» ({where})."
# Decision 16 (#75, row 3.15): a turbulence chosen with a deficit that does not use the effective TI.
TURBULENCE_WITHOUT_EFFECT = ("{cls} no usa la TI efectiva (use_effective_ti = False, o no lo tiene): la turbulencia "
                             "elegida se calcula (la TI efectiva del resultado), pero no cambia el déficit.")

# The positions whose conflicts are shown at the visible selector of another one, and the section that holds them.
_SHOWN_AT = {ROTOR: DEFICIT, GROUND: DEFICIT, BLOCKAGE_SUPERPOSITION: BLOCKAGE}
# The arguments of an engine that are positions of the group (or out of it: the deflection, the rotor average of the
# engine and the multirotor modifiers, decisions 13 and 5 of #46a), not listed among the arguments not offered.
_ENGINE_COMPONENTS = ("wake_deficitModel", "superpositionModel", "blockage_deficitModel", "deflectionModel",
                      "turbulenceModel", "rotorAvgModel", "inputModifierModels")


def _identity(text: str) -> str:
    return text


def _value_text(value: Any) -> str:
    if value is None:
        return "None"
    if inspect.isfunction(value):
        return value.__name__
    if isinstance(value, (bool, int, float, str)):
        return repr(value) if isinstance(value, str) else str(value)
    if isinstance(value, (list, tuple)):
        return "[" + ", ".join(_value_text(v) for v in value) + "]"
    if hasattr(value, "tolist"):  # an array of the signature (r12p, ngp, fgp of SelfSimilarityDeficit2020): its values
        return _value_text(value.tolist())
    return type(value).__name__ + "()"


def _excluded(e: _cat.ClassEntry, skip: Tuple[str, ...] = ()) -> List[Tuple[str, str, str]]:
    """``(name, value, reason)`` of the arguments of the signature that the plugin does not offer (#64, decision 1)."""
    try:
        defaults = _cat.signature_defaults(e)
    except _cat.ClassUnavailable:
        return []
    return [(x.name, _value_text(defaults.get(x.name)), x.reason) for x in _sub.excluded_of(e.name)
            if x.name not in skip and x.name in defaults]


def _component(position: str, option: str) -> Optional[Component]:
    """The component of an option id of ``position`` (``NONE`` is the absence)."""
    if option == NONE:
        return None
    for e in _cat.entries(position):
        if e.option == option:
            return Component(e.name, dict(e.fixed))
    raise KeyError(f"{position}: {option}")


def _option(position: str, comp: Optional[Component]) -> str:
    """The option id of a component of ``position`` (``NONE`` for the absence)."""
    return NONE if comp is None else _f.catalogue_entry(position, comp).option


_URL = re.compile(r"https?://\S+")


def help_html(text: str) -> str:
    """A help text as rich text: its paragraphs, the first line of one with more in bold, its lines starting with «• »
    as an indented list, and its links clickable."""
    def line(s: str) -> str:
        out, end = [], 0
        for m in _URL.finditer(s):
            out += [escape(s[end:m.start()]), f'<a href="{escape(m.group())}">{escape(m.group())}</a>']
            end = m.end()
        return "".join(out + [escape(s[end:])])

    paragraphs = []
    for block in text.split("\n\n"):
        raw = block.split("\n")
        lines = [line(s) for s in raw if not s.startswith("• ")]
        if len(raw) > 1:
            lines[0] = f"<b>{lines[0]}</b>"
        items = "".join(f"<li>{line(s[2:])}</li>" for s in raw if s.startswith("• "))
        paragraphs.append("<p>" + "<br>".join(lines) + "</p>" + (f"<ul>{items}</ul>" if items else ""))
    return "".join(paragraphs)


class WakeModelGroup(QtWidgets.QGroupBox):
    """The group (see the module docstring). ``settings`` is a ``QSettings`` (or anything with ``value`` and
    ``setValue``) where the visible choices are remembered; ``tr`` translates a Spanish source text."""

    changed = QtCore.pyqtSignal()

    def __init__(self, parent: Optional[QtWidgets.QWidget] = None, settings: Any = None,
                 tr: Callable[[str], str] = _identity):
        super().__init__(parent)
        self._tr = tr
        self._settings = settings
        self._preference_notes: List[str] = []
        self._deficit_drafts: Dict[str, Tuple[Component, Optional[Component], Optional[Component]]] = {}
        self._blockage_drafts: Dict[str, Tuple[Component, Optional[Component]]] = {}
        self._deficit_raw: Dict[str, Dict[str, List[str]]] = {}  # the unreadable texts of each class's fields
        # The arguments of each class of a subordinate object (#64): the rotor and ground last given to each class
        # under each deficit class, and an editor kept for each engine, superposition, turbulence and blockage class
        # (with what it holds).
        self._memory: Dict[Tuple[str, str, str], Component] = {}
        self._sub_editors: Dict[Tuple[str, str], SubordinateEditor] = {}
        self.rotor_editor: Optional[SubordinateEditor] = None
        self._shown_deficit: Optional[str] = None  # the deficit class whose draft the controls show
        self._ground: Optional[Component] = None
        self._ground_conflicts: List[str] = []
        self._ground_notes: List[str] = []
        self._updating = False
        self._last_codes: set = set()
        self._issues: List[_val.Issue] = []
        self._preset_issues: List[_val.Issue] = []
        self._mode = self._initial_mode()  # before anything is written
        self.setTitle(tr("Modelo de estela"))
        mark_translated(self)  # every text of the group is set translated (the dialog's apply_i18n leaves it)
        self._build()
        self._restore()
        self._restore_preset()
        self._apply_mode()
        self._refresh()
        self._show_preset()

    def retranslate(self) -> None:
        """Translate in place: manual editors (including hidden drafts) keep their controls."""
        tr = self._tr
        self.setTitle(tr("Modelo de estela"))
        for mode, button in self.btn_mode.items():
            button.setText(tr(MODE_LABELS[mode]))
        for position, source in ((ENGINE, "Motor"), (DEFICIT, "Déficit de estela"), (ROTOR, "Promedio de rotor"),
                                 (GROUND, "Suelo"), (SUPERPOSITION, "Superposición de estelas"),
                                 (BLOCKAGE, "Bloqueo"), (BLOCKAGE_SUPERPOSITION, "Superposición"),
                                 (TURBULENCE, "Turbulencia añadida")):
            self._row_label[position].setText(tr(source))
        for section, source in ((self.sec_deficit, "Parámetros del déficit"),
                                (self.sec_superposition, "Parámetros de la superposición"),
                                (self.sec_blockage, "Parámetros del bloqueo"),
                                (self.sec_turbulence, "Parámetros de la turbulencia")):
            section.header.setText(tr(source))
        for button in self.btn_reset_section.values():
            button.setText(tr("Restablecer"))
        self.btn_engine.setToolTip(tr("Ajustes numéricos del motor"))
        for button in self.findChildren(QtWidgets.QToolButton):
            title = button.property("wake_info_title")
            if title:
                button.setToolTip(tr(INFO_TOOLTIP))
                button.setAccessibleName(tr("Información") + ": " + tr(title))
        link = f'<a href="{_presets.PAGE}">Predefined Engineering Wind Farm Models</a>'
        self.lbl_presets_page.setText(escape(tr(PRESETS_PAGE)).replace("{link}", link))
        self.lbl_preset.setText(tr("Modelo"))
        self.lbl_presets_footer.setText(tr(PRESETS_FOOTER))
        self._refresh_preferences()
        if self._stale_preset_value is not None:
            self._preset_stale = self._tr_template(STALE_PRESET, value=self._stale_preset_value, default=DEFAULT_PRESET)
        self._fill_static_options()
        for editor in self.findChildren(ParamEditor):
            editor.retranslate(self._param_helps(editor._wake_entry))
        for editor in self.findChildren(SubordinateEditor):
            editor.retranslate()
        expanded = {key: sec.isExpanded() for key, sec in self.preset_sections.items()}
        self._refresh()
        self._show_preset()
        for key, state in expanded.items():
            if key in self.preset_sections:
                self.preset_sections[key].setExpanded(state)

    def add_preference_note(self, source: str) -> None:
        """Keep an owner's additional fixed note in Spanish, alongside the stale preferences."""
        self._preference_notes.append(source)
        self._refresh_preferences()

    def _refresh_preferences(self) -> None:
        texts = [self._tr_template(STALE_PREFERENCE, value=value, position=_cat.position_label(position),
                                   default=default or self._tr(NONE_LABEL.get(position, "")))
                 for position, value, default in self._stale_preferences]
        texts.extend(self._tr(source) for source in self._preference_notes)
        self.lbl_preferences.setText("\n".join(texts))
        self.lbl_preferences.setVisible(bool(texts))

    # --- construction ---------------------------------------------------------------------------------------
    def _row(self, layout: QtWidgets.QVBoxLayout, position: str, label: str) -> None:
        """A selector with its label, a place for the arguments of its option in the same line, and its note."""
        box = QtWidgets.QWidget(self)
        v = QtWidgets.QVBoxLayout(box)
        v.setContentsMargins(0, 0, 0, 0)
        h = QtWidgets.QHBoxLayout()
        lbl = QtWidgets.QLabel(self._tr(label))  # no colon (decision 7 of #64)
        combo = QtWidgets.QComboBox(box)
        combo.setSizeAdjustPolicy(QtWidgets.QComboBox.AdjustToMinimumContentsLengthWithIcon)
        h.addWidget(lbl)
        h.addWidget(combo, 1)
        holder = QtWidgets.QWidget(box)
        QtWidgets.QHBoxLayout(holder).setContentsMargins(0, 0, 0, 0)
        h.addWidget(holder)
        info = self._info_button(box, label, lambda p=position: self._row_help(p))  # last: the points in a column
        h.addWidget(info)
        self.btn_row_info[position] = info
        v.addLayout(h)
        note = QtWidgets.QLabel(box)
        note.setWordWrap(True)
        note.setVisible(False)
        v.addWidget(note)
        layout.addWidget(box)
        self.combo[position], self.conflict[position], self.row[position], self._inline[position] = \
            combo, note, box, holder
        self._row_label[position] = lbl

    def _holder(self, section: CollapsibleSection) -> QtWidgets.QVBoxLayout:
        holder = QtWidgets.QWidget(section.body)
        layout = QtWidgets.QVBoxLayout(holder)
        layout.setContentsMargins(0, 0, 0, 0)
        section.body_layout.addWidget(holder)
        return layout

    def _build(self) -> None:
        tr = self._tr
        outer = QtWidgets.QVBoxLayout(self)
        # The two modes: two joined buttons, one checked (decision 1 of the predefined models), and right after them
        # the help of both, in tabs: a widget of its own, so it opens the help without choosing a mode.
        modes = QtWidgets.QHBoxLayout()
        modes.setSpacing(0)
        self._mode_buttons = QtWidgets.QButtonGroup(self)
        self.btn_mode: Dict[str, QtWidgets.QPushButton] = {}
        for mode in (PREDEFINED, MANUAL):
            button = QtWidgets.QPushButton(tr(MODE_LABELS[mode]), self)
            button.setCheckable(True)
            # The mode chosen, highlighted (QGIS tests: with the native style both looked alike).
            button.setStyleSheet("QPushButton:checked { background-color: palette(highlight); "
                                 "color: palette(highlighted-text); }")
            self._mode_buttons.addButton(button)
            button.clicked.connect(lambda _c=False, m=mode: self.set_mode(m))
            modes.addWidget(button)
            self.btn_mode[mode] = button
        self.btn_modes_info = self._info_button(self, "Modelo de estela", self._modes_help)
        modes.addWidget(self.btn_modes_info)
        modes.addStretch(1)
        outer.addLayout(modes)
        self.manual_box = QtWidgets.QWidget(self)
        lay = QtWidgets.QVBoxLayout(self.manual_box)
        lay.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(self.manual_box)
        self.preset_box = self._build_presets()
        outer.addWidget(self.preset_box)
        self.lbl_preferences = QtWidgets.QLabel(self)
        self.lbl_preferences.setWordWrap(True)
        self.lbl_preferences.setStyleSheet("color: #b9770e;")
        self.lbl_preferences.setVisible(False)
        lay.addWidget(self.lbl_preferences)

        self.combo: Dict[str, QtWidgets.QComboBox] = {}
        self.conflict: Dict[str, QtWidgets.QLabel] = {}
        self.row: Dict[str, QtWidgets.QWidget] = {}
        self._inline: Dict[str, QtWidgets.QWidget] = {}
        self._row_label: Dict[str, QtWidgets.QLabel] = {}
        self.btn_row_info: Dict[str, QtWidgets.QToolButton] = {}
        self._row(lay, ENGINE, "Motor")
        self._row(lay, DEFICIT, "Déficit de estela")

        # The deficit's parameters, rotor (its arguments in its line) and ground (its window, with a summary).
        self.sec_deficit = CollapsibleSection(tr("Parámetros del déficit"), self)
        self._deficit_params_layout = self._holder(self.sec_deficit)
        self.deficit_editor: Optional[ParamEditor] = None
        self._row(self.sec_deficit.body_layout, ROTOR, "Promedio de rotor")
        self._row(self.sec_deficit.body_layout, GROUND, "Suelo")
        self.btn_ground = QtWidgets.QPushButton(tr("Parámetros del modelo de suelo…"), self._inline[GROUND])
        self._inline[GROUND].layout().addWidget(self.btn_ground)
        self.btn_ground.clicked.connect(lambda _c=False: self.open_ground_window())
        self.lbl_rotor_info = self._info(self.sec_deficit.body_layout)
        lay.addWidget(self.sec_deficit)

        self._row(lay, SUPERPOSITION, "Superposición de estelas")
        self.sec_superposition = CollapsibleSection(tr("Parámetros de la superposición"), self)
        self._args_layout = {SUPERPOSITION: self._holder(self.sec_superposition)}
        self.lbl_superposition_info = self._info(self.sec_superposition.body_layout)
        lay.addWidget(self.sec_superposition)
        self._row(lay, BLOCKAGE, "Bloqueo")

        # The blockage's options: its superposition, use_effective_ws (decisions 8 and 17) and its parameters (#64).
        self.sec_blockage = CollapsibleSection(tr("Parámetros del bloqueo"), self)
        self._row(self.sec_blockage.body_layout, BLOCKAGE_SUPERPOSITION, "Superposición")  # of the blockage, its section
        self._blockage_params_layout = self._holder(self.sec_blockage)
        self.blockage_editor: Optional[ParamEditor] = None
        self._args_layout[BLOCKAGE] = self._holder(self.sec_blockage)
        self.lbl_blockage_info = self._info(self.sec_blockage.body_layout)
        lay.addWidget(self.sec_blockage)

        self._row(lay, TURBULENCE, "Turbulencia añadida")
        self.sec_turbulence = CollapsibleSection(tr("Parámetros de la turbulencia"), self)
        self._args_layout[TURBULENCE] = self._holder(self.sec_turbulence)
        self.lbl_turbulence_info = self._info(self.sec_turbulence.body_layout)
        lay.addWidget(self.sec_turbulence)

        # The arguments of the engine (decision 7 of #64): a small button at the end of its line opens their window;
        # the editor of each engine class keeps what was accepted (it is not shown).
        self.btn_engine = QtWidgets.QToolButton(self._inline[ENGINE])
        self.btn_engine.setIcon(self.style().standardIcon(QtWidgets.QStyle.SP_FileDialogDetailedView))
        self.btn_engine.setToolTip(tr("Ajustes numéricos del motor"))
        side = self.btn_engine.sizeHint().height()
        self.btn_engine.setFixedSize(side, side)  # square, marked or not
        self._inline[ENGINE].layout().addWidget(self.btn_engine)
        self.btn_engine.clicked.connect(lambda _c=False: self.open_engine_window())
        self._engine_holder = QtWidgets.QWidget(self)
        self._engine_holder.setVisible(False)
        self._args_layout[ENGINE] = QtWidgets.QVBoxLayout(self._engine_holder)
        self._engine_conflicts: List[str] = []
        self._engine_notes: List[str] = []

        # «Restablecer» per section, at its bottom right (decision 7 of #64).
        self.btn_reset_section: Dict[str, QtWidgets.QPushButton] = {}
        for position, section in ((DEFICIT, self.sec_deficit), (SUPERPOSITION, self.sec_superposition),
                                  (BLOCKAGE, self.sec_blockage), (TURBULENCE, self.sec_turbulence)):
            row = QtWidgets.QHBoxLayout()
            row.addStretch(1)
            button = QtWidgets.QPushButton(tr("Restablecer"), section.body)
            button.clicked.connect(lambda _c=False, p=position: self.reset_section(p))
            row.addWidget(button)
            section.body_layout.addLayout(row)
            self.btn_reset_section[position] = button

        self._fill_static_options()
        for position, combo in self.combo.items():
            combo.currentIndexChanged.connect(lambda _i, p=position: self._on_choice(p))

    def _info(self, layout) -> QtWidgets.QLabel:
        lbl = QtWidgets.QLabel(self)
        lbl.setWordWrap(True)
        lbl.setStyleSheet("color: #666;")
        layout.addWidget(lbl)
        return lbl

    def _info_button(self, parent: QtWidgets.QWidget, title: str,
                     text_fn: Callable[[], str]) -> QtWidgets.QToolButton:
        """Non-mutating information point, beside the label like elsewhere in the plugin."""
        button = QtWidgets.QToolButton(parent)
        # Same native information icon, flat appearance and cursor used by Noise and Shadow.
        try:
            button.setIcon(self.style().standardIcon(QtWidgets.QStyle.SP_MessageBoxInformation))
        except Exception:
            button.setText("?")
        button.setAutoRaise(True)
        button.setCursor(QtGui.QCursor(QtCore.Qt.PointingHandCursor))
        button.setProperty("wake_info_title", title)
        button.setToolTip(self._tr(INFO_TOOLTIP))
        button.setAccessibleName(self._tr("Información") + ": " + self._tr(title))
        button.clicked.connect(lambda _checked=False: self._show_info_dialog(self._tr(title), text_fn()))
        return button

    def _show_info_dialog(self, title: str, content: Any) -> None:
        """Display long guidance in a scrollable, resizable window: a text, or one tab per ``(title, text)``.

        The manual-mode explanation includes two full sample configurations;
        a plain QMessageBox can grow beyond the available laptop screen.
        """
        dialog = QtWidgets.QDialog(self)
        dialog.setObjectName("wakeInfoDialog")
        dialog.setWindowTitle(title)
        layout = QtWidgets.QVBoxLayout(dialog)

        def browser(text: str) -> QtWidgets.QTextBrowser:
            editor = QtWidgets.QTextBrowser(dialog)  # read-only, selectable; its links open in the system browser
            editor.setObjectName("wakeInfoText")
            editor.setOpenExternalLinks(True)
            editor.setHtml(help_html(text))
            editor.moveCursor(QtGui.QTextCursor.Start)
            return editor

        if isinstance(content, str):
            layout.addWidget(browser(content), 1)
        else:
            tabs = QtWidgets.QTabWidget(dialog)
            tabs.setObjectName("wakeInfoTabs")
            for tab, text in content:
                tabs.addTab(browser(text), tab)
            layout.addWidget(tabs, 1)
        bottom = QtWidgets.QHBoxLayout()
        bottom.addStretch(1)
        close = QtWidgets.QPushButton(self._tr("Cerrar"), dialog)
        close.setObjectName("wakeInfoClose")
        close.clicked.connect(dialog.accept)
        bottom.addWidget(close)
        layout.addLayout(bottom)
        screen = QtWidgets.QApplication.primaryScreen()
        if screen is not None:
            available = screen.availableGeometry()
            dialog.resize(min(700, max(340, available.width() - 90)),
                          min(520, max(240, available.height() - 100)))
        else:
            dialog.resize(700, 500)
        dialog.exec_()

    def _modes_help(self) -> List[Tuple[str, str]]:
        """The help of the selector of modes: a general tab, then that of each mode."""
        return [(self._tr("General"), self._tr(GENERAL_HELP))] + [
            (self._tr(MODE_LABELS[m]), self._mode_help(m)) for m in (PREDEFINED, MANUAL)]

    def _mode_help(self, mode: str) -> str:
        texts = (PREDEFINED_HELP,) if mode == PREDEFINED else (MANUAL_HELP, EXAMPLES_HELP, VALIDATION_HELP)
        return "\n\n".join(self._tr(t) for t in texts)

    def _selector_help(self, position: str, combo: QtWidgets.QComboBox) -> str:
        """Explain the purpose first, then the option currently chosen in the UI.

        The same helper works for editable options and read-only presets.
        Resolving the option at click time prevents stale help after selection.
        """
        introduction = self._tr(ROW_EXPLANATIONS[position])
        selected = self._tr(SELECTED_HELP).format(name=combo.currentText())
        detail = combo.currentData(QtCore.Qt.ToolTipRole)
        return introduction + "\n\n" + selected + "\n" + (
            str(detail) if detail else self._tr("Sin información adicional para esta opción."))

    def _row_help(self, position: str) -> str:
        return self._selector_help(position, self.combo[position])

    def _preset_model_help(self) -> str:
        """The model chosen: its class, formulation, references and the adaptations of the plugin, not the mode's."""
        model = _presets.preset(self.combo_preset.currentData())
        formulation, references = PRESET_HELP[model.id]
        particulars = [self._tr(n) for n in model.notes]
        if (model.definition.get("rotor") or {}).get("class") == "GaussianOverlapAvgModel":
            particulars.append(self._tr(PRESET_ADAPTATION))
        parts = [self._tr(PRESET_MODEL_HELP).format(model=model.id, reference=model.reference_class) + "\n"
                 + self._tr(formulation), self._tr(PRESET_SCOPE),
                 "\n".join([self._tr(PRESET_REFERENCES)] + [f"{self._tr(kind)}: {self._tr(citation) if kind == _CODE else citation} {url}"
                                                             for kind, citation, url in references]
                           + [self._tr(PRESET_DOCUMENTATION).format(url=model.url)])]
        if particulars:
            parts.append("\n".join([self._tr(PRESET_PARTICULARS)] + particulars))
        return "\n\n".join(parts)

    def _help(self, e: _cat.ClassEntry, with_warning: bool = True) -> str:
        parts = [self._tr(t) for t in (e.help, e.predefined, e.warning if with_warning else "") if t]
        return "\n".join(parts)

    def _arg_help(self, owner: str, name: str) -> str:
        """The help of an argument of a subordinate object (#64): what PyWake says, the minimum of its control and
        the value of its signature."""
        spec = _sub.arg_spec(owner, name)
        lines = [self._tr(spec.doc) if spec.doc else self._tr(FAMILY_HELP.get(spec.family, ""))]
        if (owner, name) in SPIN_MINIMUM_HELP:
            lines.append(self._tr(SPIN_MINIMUM_HELP[(owner, name)]))
        lines.append(self._tr_template(SIGNATURE_VALUE, value=_value_text(_sub.signature_default(spec))))
        return "\n".join(t for t in lines if t)

    def _option_help(self, arg: Any, option: Any) -> str:
        """The help of an option of a nested argument: its own, or that of the same class in a selector."""
        if (arg.family, option.name) in OPTION_HELP:
            return self._tr(OPTION_HELP[(arg.family, option.name)])
        position = _FAMILY_POSITION[arg.family]
        if option.name is None:
            return self._tr(NONE_HELP[position])
        return self._help(next(e for e in _cat.entries(position) if e.name == option.name))

    def _editor_kw(self) -> Dict[str, Any]:
        return dict(tr=self._tr, helps=self._arg_help, option_help=self._option_help, minimum=SPIN_MINIMUM)

    def _options(self, position: str, reasons: Optional[Dict[str, str]] = None) -> List[Tuple[str, str, str, Any]]:
        out: List[Tuple[str, str, str, Any]] = []
        if position in NONE_LABEL:
            out.append((NONE, self._tr(NONE_LABEL[position]), self._tr(NONE_HELP[position]), None))
        for e in _cat.entries(position):
            out.append((e.option, e.option, self._help(e), (reasons or {}).get(e.option)))
        return out

    def _fill_static_options(self) -> None:
        for position in (ENGINE, ROTOR, GROUND, SUPERPOSITION, TURBULENCE, BLOCKAGE):
            fill_option_combo(self.combo[position], self._options(position))
        fill_option_combo(self.combo[BLOCKAGE_SUPERPOSITION], self._options(BLOCKAGE_SUPERPOSITION))
        self._fill_deficits()

    def _fill_deficits(self) -> None:
        # With PUD, a class without use_effective_ws can never be calculated (R3): disabled, with the reason.
        reasons = {}
        if self.combo[ENGINE].currentData() == _PUD:
            reasons = {e.option: self._tr_template(PUD_REFUSED, cls=e.name)
                       for e in _cat.entries(DEFICIT) if "use_effective_ws" not in e.params}
        fill_option_combo(self.combo[DEFICIT], self._options(DEFICIT, reasons))
        self.combo[DEFICIT].setToolTip(self._tr(_cat.OUT_OF_CATALOGUE))  # what is not offered, and why

    def _tr_template(self, template: str, **data: Any) -> str:
        return shown(log_text(template, **data), self._tr)

    # --- state ----------------------------------------------------------------------------------------------
    def _select(self, position: str, option: str) -> bool:
        i = self.combo[position].findData(option)
        if i >= 0:
            self.combo[position].setCurrentIndex(i)
        return i >= 0

    def _restore(self) -> None:
        """The choices remembered between sessions, if still options; otherwise the signature's, and a note."""
        base = _cfg.default_config()
        defaults = {ENGINE: base.engine.name, DEFICIT: base.deficit.name, SUPERPOSITION: base.superposition.label,
                    TURBULENCE: _option(TURBULENCE, base.turbulence), BLOCKAGE: _option(BLOCKAGE, base.blockage)}
        self._stale_preferences = []
        self._updating = True
        try:
            for position in SHOWN_POSITIONS:
                saved = self._settings.value(SETTINGS_PREFIX + position, None) if self._settings is not None else None
                value = defaults[position] if saved is None else str(saved)
                if position == ENGINE:
                    self._select(ENGINE, defaults[ENGINE])
                if not self._select(position, value):
                    self._stale_preferences.append((position, value, defaults[position]))
                    self._select(position, defaults[position])
                if position == ENGINE:
                    self._fill_deficits()
        finally:
            self._updating = False
        self._refresh_preferences()
        self._show_deficit()
        self._show_blockage()
        for position in (ENGINE, SUPERPOSITION, TURBULENCE):
            self._show_args(position)

    def _save(self, position: str) -> None:
        if self._settings is not None and position in SHOWN_POSITIONS:
            self._settings.setValue(SETTINGS_PREFIX + position, self.combo[position].currentData())

    def _deficit_draft(self, name: str) -> Tuple[Component, Optional[Component], Optional[Component]]:
        if name not in self._deficit_drafts:
            self._deficit_drafts[name] = _cfg.deficit_signature(name)
        return self._deficit_drafts[name]

    def _blockage_draft(self, name: str) -> Tuple[Component, Optional[Component]]:
        if name not in self._blockage_drafts:
            self._blockage_drafts[name] = (_cfg.blockage_signature(name),
                                           Component(_cfg.DEFAULT_BLOCKAGE_SUPERPOSITION, {}))
        return self._blockage_drafts[name]

    def _remembered(self, position: str, option: str) -> Optional[Component]:
        """The component of an option of the rotor or the ground, with the arguments it was last given."""
        comp = _component(position, option)
        key = (self.combo[DEFICIT].currentData(), position, comp.name) if comp is not None else None
        return None if comp is None else self._memory.get(key) or _cfg.complete(comp)

    def _unavailable(self, position: str, name: str) -> Optional[_val.Issue]:
        """The class the installed PyWake does not have (R14, environment): no controls, a conflict, no exception."""
        if not name:
            return None
        try:
            _cat.resolve_class(_cat.entry(position, name))
        except _cat.ClassUnavailable as exc:
            return _val.Issue("R14", position, _val.ENVIRONMENT, "{error}", "", {"error": exc.args[0]})
        return None

    def _unavailable_issues(self) -> List[_val.Issue]:
        found = [self._unavailable(ENGINE, self.combo[ENGINE].currentData()),
                 self._unavailable(DEFICIT, self.combo[DEFICIT].currentData())]
        if self._blockage_shown():
            found.append(self._unavailable(BLOCKAGE, self.combo[BLOCKAGE].currentData()))
        return [i for i in found if i is not None]

    @staticmethod
    def _clear(layout) -> None:
        while layout.count():
            w = layout.takeAt(0).widget()
            if w is not None:
                w.setParent(None)
                w.deleteLater()

    @staticmethod
    def _edits(editor: ParamEditor, name: str) -> List[QtWidgets.QLineEdit]:
        c = editor.control(name)
        if isinstance(c, tuple):
            return list(c[1])
        return [c] if isinstance(c, QtWidgets.QLineEdit) else []

    def _param_helps(self, e: _cat.ClassEntry) -> Dict[str, str]:
        defaults = _cat.signature_defaults(e)
        # (c) of «Ayudas»: what ct2a and the effective speed and TI mean, and the value the predefined model of PyWake
        # that uses the class takes; (e): every other argument, its PyWake name and its signature value. The
        # blockage's use_effective_ws has its own help: it is the blockage that scales, not the deficit.
        predefined = "\n" + self._tr(e.predefined) if e.predefined else ""
        own = BLOCKAGE_PARAM_HELP if e.position == BLOCKAGE else _cat.PARAM_HELP
        helps = {p: self._tr(own[p]) + predefined if p in own else
                 self._tr_template(_cat.CLASS_PARAM_HELP.get((e.name, p), _cat.PARAM_HELP_TEMPLATE), name=p,
                                   value=_value_text(defaults[p])) for p in e.params}
        return helps

    def _param_editor(self, e: _cat.ClassEntry, values: Dict[str, Any]) -> ParamEditor:
        """The controls and their help, retaining the entry to retranslate without replacing drafts."""
        defaults = _cat.signature_defaults(e)
        editor = ParamEditor([(p, defaults[p]) for p in e.params], self._param_helps(e), self, tr=self._tr)
        editor._wake_entry = e
        editor.set_values(values)
        return editor

    def _editor(self, layout, e: _cat.ClassEntry, values: Dict[str, Any]) -> ParamEditor:
        self._clear(layout)
        editor = self._param_editor(e, values)
        editor.changed.connect(self._on_params)
        layout.addWidget(editor)
        return editor

    def _sub_editor(self, position: str, comp: Optional[Component], skip: Tuple[str, ...] = ()
                    ) -> Optional[SubordinateEditor]:
        """The editor of the arguments of ``comp`` in the section of ``position``, kept for its class (hidden while
        another class is chosen); ``None`` without arguments to offer."""
        for (p, _n), ed in self._sub_editors.items():
            if p == position:
                ed.setVisible(False)
        if comp is None or not [a for a in _sub.args_of(comp.name) if a.name not in skip]:
            return None
        key = (position, comp.name)
        if key not in self._sub_editors:
            ed = SubordinateEditor(comp, self, skip=skip, **self._editor_kw())
            ed.changed.connect(self._on_params)
            self._args_layout[position].addWidget(ed)
            self._sub_editors[key] = ed
        self._sub_editors[key].setVisible(True)
        return self._sub_editors[key]

    def args_editor(self, position: str) -> Optional[SubordinateEditor]:
        """The editor of the arguments of the engine, superposition, turbulence or blockage chosen, if it has one."""
        data = self.combo[position].currentData()
        name = _component(position, data).name if data else None
        if position == BLOCKAGE and not self._blockage_shown():
            return None
        return self._sub_editors.get((position, name)) if name else None

    def _show_args(self, position: str) -> None:
        """The editor of the arguments of the engine, the superposition or the turbulence chosen."""
        self._sub_editor(position, self._remembered_top(position))

    def _remembered_top(self, position: str) -> Optional[Component]:
        comp = _component(position, self.combo[position].currentData())
        return None if comp is None else _cfg.complete(comp)

    def _show_rotor(self, rotor: Optional[Component]) -> None:
        """The arguments of the rotor average in its line (the ``n`` of CGIRotorAvg and EqGridRotorAvg)."""
        self._clear(self._inline[ROTOR].layout())
        self.rotor_editor = None
        if rotor is not None and _sub.args_of(rotor.name):
            self.rotor_editor = SubordinateEditor(rotor, self._inline[ROTOR], path="", inline=True,
                                                  **self._editor_kw())
            self.rotor_editor.changed.connect(self._on_params)
            self._inline[ROTOR].layout().addWidget(self.rotor_editor)

    def _show_ground(self, ground: Optional[Component]) -> None:
        """The ground of the deficit: its button (decision 7 of #64: without a summary; its window says what it
        inherits)."""
        self._ground = ground
        self.btn_ground.setVisible(ground is not None and bool(_sub.args_of(ground.name)))
        self._mark_ground()

    def _mark_ground(self) -> None:
        text = self._tr("Parámetros del modelo de suelo…")
        self.btn_ground.setText(("⚠ " + text) if self._ground_conflicts or self._ground_notes else text)
        self.btn_ground.setStyleSheet(window_mark(self._ground_conflicts, self._ground_notes))

    def open_ground_window(self, exec_: bool = True) -> ComponentWindow:
        """The window of the arguments of the ground of the deficit; «Aceptar» keeps them in the draft of the class,
        «Cancelar» changes nothing. With ``exec_`` false (tests), it is returned without running it."""
        window = ComponentWindow(self._ground, self, path="", inherited=self.combo[SUPERPOSITION].currentData(),
                                 conflicts=self._ground_conflicts, notes=self._ground_notes, inherit_note=INHERIT_WAKES,
                                 messages=lambda comp: self._provisional(GROUND, comp), **self._editor_kw())
        if exec_ and window.exec_() == QtWidgets.QDialog.Accepted:
            self.accept_ground_window(window)
        return window

    def open_engine_window(self, exec_: bool = True) -> ComponentWindow:
        """The window of the numerical settings of the engine chosen (decision 7 of #64), with what it does not
        offer; «Aceptar» keeps them for its class, «Cancelar» changes nothing. With ``exec_`` false (tests), it is
        returned without running it."""
        editor = self.args_editor(ENGINE)
        comp = editor.value() if editor is not None else self._remembered_top(ENGINE)
        info = self._excluded_text([(ENGINE, self.combo[ENGINE].currentData())], _ENGINE_COMPONENTS)
        window = ComponentWindow(comp, self, path="", conflicts=self._engine_conflicts, notes=self._engine_notes,
                                 title="Ajustes numéricos del motor", info=info,
                                 messages=lambda c: self._provisional(ENGINE, c), **self._editor_kw())
        if exec_ and window.exec_() == QtWidgets.QDialog.Accepted:
            self.accept_engine_window(window)
        return window

    def _provisional(self, window: str, comp: Component) -> Optional[Tuple[List[str], List[str]]]:
        """What the window of the ground of the deficit (``GROUND``), of the ground of the blockage (``BLOCKAGE``) or of
        the engine (``ENGINE``) says with ``comp`` edited in it and the rest of the group as it is (``None``: a field
        of the group cannot be read)."""
        config = self._manual_config()
        if config is None or (window == BLOCKAGE and config.blockage is None):
            return None
        if window == BLOCKAGE:
            change = {"blockage": Component(config.blockage.name, {**config.blockage.params, "groundModel": comp})}
        else:
            change = {"ground" if window == GROUND else "engine": comp}
        return self._window_messages(WakeConfig(**{**config.__dict__, **change}))[window]

    def accept_engine_window(self, window: ComponentWindow) -> None:
        comp = window.value()
        key = (ENGINE, comp.name)
        if key not in self._sub_editors:
            return  # an engine without arguments to offer
        old = self._sub_editors.pop(key)
        old.setParent(None)
        old.deleteLater()
        self._sub_editor(ENGINE, comp)
        self._on_params()

    def _mark_engine(self) -> None:
        """The button of the engine marked by a border: red with conflicts, orange with warnings or notes only."""
        conflicts, notes = self._engine_conflicts, self._engine_notes
        colour = "#c0392b" if conflicts else "#b9770e" if notes else ""
        self.btn_engine.setStyleSheet(f"QToolButton {{ border: 2px solid {colour}; border-radius: 3px; }}" if colour
                                      else "")

    def accept_ground_window(self, window: ComponentWindow) -> None:
        self._ground = window.value()
        self._on_params()

    def _show_deficit(self) -> None:
        """The draft of the selected class in its controls."""
        name = self.combo[DEFICIT].currentData()
        self._keep_rotor_being_typed(name)
        if self._unavailable(DEFICIT, name) is not None:
            self._clear(self._deficit_params_layout)
            self.deficit_editor = None
            self._shown_deficit = None
            return
        deficit, rotor, ground = self._deficit_draft(name)
        self._shown_deficit = name
        self._updating = True
        try:
            self.deficit_editor = self._editor(self._deficit_params_layout, _cat.entry(DEFICIT, name),
                                               dict(deficit.params))
            # The text the user left in a field that could not be read comes back as it was.
            for arg, texts in self._deficit_raw.get(name, {}).items():
                for edit, text in zip(self._edits(self.deficit_editor, arg), texts):
                    edit.setText(text)
            self._select(ROTOR, _option(ROTOR, rotor))
            self._select(GROUND, _option(GROUND, ground))
            self._show_rotor(rotor)
            self._show_ground(ground)
        finally:
            self._updating = False

    def _keep_rotor_being_typed(self, name: str) -> None:
        """Before the controls show another class, an integer being typed in the rotor of the class they showed
        (committed only when leaving the field) goes into that class's draft, not lost (final adversarial round 3)."""
        previous = self._shown_deficit
        if not previous or previous == name or self.rotor_editor is None:
            return
        self._updating = True
        try:
            for spin in self.rotor_editor.findChildren(QtWidgets.QAbstractSpinBox):
                spin.interpretText()
        finally:
            self._updating = False
        if self.rotor_editor.errors():
            return
        rotor = self.rotor_editor.value()
        deficit, _rotor, ground = self._deficit_draft(previous)
        self._deficit_drafts[previous] = (deficit, rotor, ground)
        self._memory[(previous, ROTOR, rotor.name)] = rotor

    def _show_blockage(self) -> None:
        name = self.combo[BLOCKAGE].currentData()
        self._updating = True
        try:
            if name == NONE or self._unavailable(BLOCKAGE, name) is not None:
                self._clear(self._blockage_params_layout)
                self.blockage_editor = None
                self._sub_editor(BLOCKAGE, None)
                return
            params, bsup = self._blockage_draft(name)
            entry = _cat.entry(BLOCKAGE, name)
            self.blockage_editor = self._editor(self._blockage_params_layout, entry,
                                                {p: params.params[p] for p in entry.params})
            self._sub_editor(BLOCKAGE, params, skip=entry.params)
            self._select(BLOCKAGE_SUPERPOSITION, _option(BLOCKAGE_SUPERPOSITION, bsup))
        finally:
            self._updating = False

    def _store_drafts(self) -> None:
        name = self.combo[DEFICIT].currentData()
        if self.deficit_editor is not None and name:
            old, _r, _g = self._deficit_draft(name)
            rotor = self.rotor_editor.value() if self.rotor_editor is not None else \
                _component(ROTOR, self.combo[ROTOR].currentData())
            ground = self._ground
            self._deficit_drafts[name] = (Component(name, dict(old.params, **self.deficit_editor.values())),
                                          rotor if rotor is None else _cfg.complete(rotor), ground)
            for position, comp in ((ROTOR, rotor), (GROUND, ground)):
                if comp is not None:
                    self._memory[(name, position, comp.name)] = _cfg.complete(comp)
            self._deficit_raw[name] = {arg: [e.text() for e in self._edits(self.deficit_editor, arg)]
                                       for arg in self.deficit_editor.errors()}
        b = self.combo[BLOCKAGE].currentData()
        if self.blockage_editor is not None and b:
            old_b, _s = self._blockage_draft(b)
            sub_editor = self._sub_editors.get((BLOCKAGE, b))
            offered = {a.name for a in _sub.args_of(b)}
            nested = {k: v for k, v in sub_editor.value().params.items() if k in offered} if sub_editor else {}
            self._blockage_drafts[b] = (Component(b, dict(old_b.params, **nested, **self.blockage_editor.values())),
                                        _component(BLOCKAGE_SUPERPOSITION, self.combo[BLOCKAGE_SUPERPOSITION].currentData()))

    # --- reactions ------------------------------------------------------------------------------------------
    def _on_choice(self, position: str) -> None:
        if self._updating:
            return
        if position == DEFICIT:
            self._show_deficit()
        elif position == BLOCKAGE:
            self._show_blockage()
        elif position == ROTOR:
            self._show_rotor(self._remembered(ROTOR, self.combo[ROTOR].currentData()))
        elif position == GROUND:
            self._show_ground(self._remembered(GROUND, self.combo[GROUND].currentData()))
        elif position in (SUPERPOSITION, TURBULENCE):
            self._show_args(position)
        elif position == ENGINE:
            self._updating = True
            try:
                self._fill_deficits()  # keeps the class chosen, even when it is now disabled
            finally:
                self._updating = False
            self._show_args(ENGINE)
        self._store_drafts()
        self._save(position)
        self._refresh()

    def _on_params(self) -> None:
        if self._updating:
            return
        self._store_drafts()
        self._refresh()

    def reset_section(self, position: str) -> None:
        """«Restablecer» of a section (decision 7 of #64): what it shows (the class, and the rotor, the ground and the
        nested options it has chosen) and its selectors back to their signatures; the drafts of the alternatives not
        chosen (another rotor, another option of a nested argument), of the other classes and of the other sections
        stay. The selector above the section does not change."""
        if position == DEFICIT:
            name = self.combo[DEFICIT].currentData()
            if self._unavailable(DEFICIT, name) is not None:
                return
            _deficit, rotor, ground = self._deficit_draft(name)
            signature = _cfg.deficit_signature(name)
            for pos, chosen, sig in ((ROTOR, rotor, signature[1]), (GROUND, ground, signature[2])):
                for comp in (chosen, sig):
                    if comp is not None:
                        self._memory.pop((name, pos, comp.name), None)
            self._deficit_drafts[name] = signature
            self._deficit_raw.pop(name, None)
            self._show_deficit()
        elif position == BLOCKAGE:
            name = self.combo[BLOCKAGE].currentData()
            if not name or name == NONE or self._unavailable(BLOCKAGE, name) is not None:
                return
            self._blockage_drafts.pop(name, None)
            drafts = self._drop_editor(BLOCKAGE, name)
            self._show_blockage()
            self._keep_drafts(BLOCKAGE, name, drafts)
        else:  # the superposition, the added turbulence
            comp = _component(position, self.combo[position].currentData())
            if comp is None:
                return
            drafts = self._drop_editor(position, comp.name)
            self._show_args(position)
            self._keep_drafts(position, comp.name, drafts)
        self._store_drafts()
        self._refresh()

    def _drop_editor(self, position: str, name: str) -> Dict[str, Dict[str, Any]]:
        editor = self._sub_editors.pop((position, name), None)
        if editor is None:
            return {}
        drafts = editor.take_drafts()
        editor.setParent(None)
        editor.deleteLater()
        return drafts

    def _keep_drafts(self, position: str, name: str, drafts: Dict[str, Dict[str, Any]]) -> None:
        editor = self._sub_editors.get((position, name))
        if editor is not None and drafts:
            editor.keep_drafts(drafts)

    # --- the two modes and the predefined models --------------------------------------------------------------
    def _initial_mode(self) -> str:
        """The mode saved; without one, the manual mode if it has choices saved, else the predefined models (decision 9:
        checked before anything is written)."""
        if self._settings is None:
            return PREDEFINED
        saved = self._settings.value(MODE_KEY, None)
        if saved in (PREDEFINED, MANUAL):
            return str(saved)
        manual = any(self._settings.value(SETTINGS_PREFIX + p, None) is not None for p in SHOWN_POSITIONS)
        return MANUAL if manual else PREDEFINED

    def mode(self) -> str:
        return self._mode

    def set_mode(self, mode: str) -> None:
        """Show the other mode (each keeps its own choices) and remember it."""
        if mode == self._mode:
            self._apply_mode()
            return
        self._mode = mode
        if self._settings is not None:
            self._settings.setValue(MODE_KEY, mode)
        self._apply_mode()
        self.changed.emit()

    def _apply_mode(self) -> None:
        self.btn_mode[self._mode].setChecked(True)
        self.manual_box.setVisible(self._mode == MANUAL)
        self.preset_box.setVisible(self._mode == PREDEFINED)

    def _build_presets(self) -> QtWidgets.QWidget:
        """The predefined models (decision 10): a grey line with the page of PyWake, «Modelo» with its notes, the
        configuration of the model read-only, and how to change values."""
        tr = self._tr
        box = QtWidgets.QWidget(self)
        lay = QtWidgets.QVBoxLayout(box)
        lay.setContentsMargins(0, 0, 0, 0)
        self.lbl_presets_page = QtWidgets.QLabel(box)
        self.lbl_presets_page.setWordWrap(True)
        self.lbl_presets_page.setStyleSheet("color: #666;")
        self.lbl_presets_page.setTextFormat(QtCore.Qt.RichText)
        self.lbl_presets_page.setOpenExternalLinks(True)
        link = f'<a href="{_presets.PAGE}">Predefined Engineering Wind Farm Models</a>'
        self.lbl_presets_page.setText(escape(tr(PRESETS_PAGE)).replace("{link}", link))
        lay.addWidget(self.lbl_presets_page)
        row = QtWidgets.QHBoxLayout()
        self.lbl_preset = QtWidgets.QLabel(tr("Modelo"), box)
        self.combo_preset = QtWidgets.QComboBox(box)
        self.combo_preset.setSizeAdjustPolicy(QtWidgets.QComboBox.AdjustToMinimumContentsLengthWithIcon)
        for id_ in _presets.ids():
            self.combo_preset.addItem(id_, id_)
        row.addWidget(self.lbl_preset)
        row.addWidget(self.combo_preset, 1)
        self.btn_preset_model_info = self._info_button(box, "Modelo", self._preset_model_help)
        row.addWidget(self.btn_preset_model_info)
        lay.addLayout(row)
        self.preset_note = QtWidgets.QLabel(box)
        self.preset_note.setWordWrap(True)
        self.preset_note.setOpenExternalLinks(True)
        self.preset_note.setVisible(False)
        lay.addWidget(self.preset_note)
        # The rows of the model, inside a widget replaced whole with each model (nothing of the previous one is left).
        self.preset_details = QtWidgets.QWidget(box)
        self._preset_holder = QtWidgets.QVBoxLayout(self.preset_details)
        self._preset_holder.setContentsMargins(0, 0, 0, 0)
        self._preset_content: Optional[QtWidgets.QWidget] = None
        lay.addWidget(self.preset_details)
        self.lbl_presets_footer = QtWidgets.QLabel(tr(PRESETS_FOOTER), box)
        self.lbl_presets_footer.setWordWrap(True)
        self.lbl_presets_footer.setStyleSheet("color: #666;")
        lay.addWidget(self.lbl_presets_footer)
        self.preset_combo: Dict[str, QtWidgets.QComboBox] = {}
        self.preset_conflict: Dict[str, QtWidgets.QLabel] = {}
        self.preset_sections: Dict[str, CollapsibleSection] = {}
        self.preset_editors: Dict[str, Any] = {}
        self._preset_stale = ""
        self._stale_preset_value = None
        self.combo_preset.currentIndexChanged.connect(lambda _i: self._on_preset())
        return box

    def _restore_preset(self) -> None:
        saved = self._settings.value(PRESET_KEY, None) if self._settings is not None else None
        value = DEFAULT_PRESET if saved is None else str(saved)
        self.combo_preset.blockSignals(True)
        try:
            if value not in _presets.ids():
                self._stale_preset_value = value
                self._preset_stale = self._tr_template(STALE_PRESET, value=value, default=DEFAULT_PRESET)
                value = DEFAULT_PRESET
            self.combo_preset.setCurrentIndex(self.combo_preset.findData(value))
        finally:
            self.combo_preset.blockSignals(False)

    def _on_preset(self) -> None:
        if self._settings is not None:
            self._settings.setValue(PRESET_KEY, self.combo_preset.currentData())
        self._preset_stale = ""
        self._stale_preset_value = None
        self._show_preset()

    def _preset_issue(self, issue: _val.Issue) -> _val.Issue:
        """A refusal of a predefined model, with the actions it has: another model or the manual mode (decision 13)."""
        return replace(issue, resolution=PRESET_RESOLUTION)

    def _show_preset(self) -> None:
        """The configuration of the predefined model chosen, read-only, with the hierarchy of the manual mode (decision
        10), and its notes and messages under each selector; then ``changed``."""
        config = _presets.config(self.combo_preset.currentData())
        issues = _val.validate(config, check_environment=False)
        self._preset_issues = [self._preset_issue(i) for i in issues]
        if self._preset_content is not None:
            self._preset_content.setParent(None)
            self._preset_content.deleteLater()
        self._preset_content = QtWidgets.QWidget(self.preset_details)
        self._preset_content.setStyleSheet(READ_ONLY_STYLE)
        self._preset_layout = QtWidgets.QVBoxLayout(self._preset_content)
        self._preset_layout.setContentsMargins(0, 0, 0, 0)
        self._preset_holder.addWidget(self._preset_content)
        self.preset_combo, self.preset_conflict, self.preset_sections, self.preset_editors = {}, {}, {}, {}
        self.btn_preset_info: Dict[str, QtWidgets.QToolButton] = {}
        self._preset_labels: Dict[str, QtWidgets.QLabel] = {}
        unavailable = [i for i in issues if i.origin == _val.ENVIRONMENT]
        preset = _presets.preset(self.combo_preset.currentData())
        notes = [self._tr(n) for n in preset.notes]
        conflicts = [i.translated(self._tr) for i in self._preset_issues] if unavailable else []
        self._note(self.preset_note, conflicts, ([self._preset_stale] if self._preset_stale else []) + notes)
        if _presets.SUPERGAUSSIAN_NOTE in preset.notes:  # with the link to its documentation (decision 6)
            self.preset_note.setText(self.preset_note.text() + f'<br><a href="{preset.url}">{preset.url}</a>')
        if not unavailable:  # a class this PyWake does not have: no controls, its conflict under «Modelo»
            self._preset_rows(config, self._preset_messages(config))
        self.changed.emit()

    def _preset_messages(self, config: WakeConfig) -> Dict[str, Tuple[List[str], List[str]]]:
        """What the manual mode says under each selector for this configuration: its refusals (with the resolution of a
        predefined model) and, as notes, what PyWake refuses from a number of turbines and the warnings."""
        out: Dict[str, Tuple[List[str], List[str]]] = {p: ([], []) for p in (ENGINE, DEFICIT, SUPERPOSITION, TURBULENCE)}
        # Without the libraries of GaussianOverlapAvgModel (R13) nothing is said here: the dialog asks when calculating.
        layout = [self._preset_issue(i) for i in _val.layout_issues(config) if i.code != "R13"]
        for issues, kind in ((self._preset_issues, 0), (layout, 1)):
            for issue in issues:
                out[_SHOWN_AT.get(issue.position, issue.position)][kind].append(issue.translated(self._tr))
        for position, warnings in _notices.argument_warnings(config).items():
            out[_SHOWN_AT.get(position, position)][1].extend(str(shown(w, self._tr)) for w in warnings)
        out[SUPERPOSITION][1].extend(str(shown(w, self._tr)) for w in _notices.superposition_warnings(config))
        if _notices.turbulence_without_effect(config):
            out[TURBULENCE][1].append(self._tr_template(TURBULENCE_WITHOUT_EFFECT, cls=config.deficit.name))
        return out

    def _preset_selector(self, layout, position: str, label: str, comp: Optional[Component]) -> QtWidgets.QHBoxLayout:
        """A selector of the manual mode that shows the component of the model, disabled, with its help."""
        line = QtWidgets.QHBoxLayout()
        lbl = QtWidgets.QLabel(self._tr(label))
        combo = QtWidgets.QComboBox()
        combo.setSizeAdjustPolicy(QtWidgets.QComboBox.AdjustToMinimumContentsLengthWithIcon)
        if comp is None:
            text, tip = self._tr(NONE_LABEL[position]), self._tr(NONE_HELP[position])
        else:
            e = _f.catalogue_entry(position, comp)
            text, tip = e.option, self._help(e)
        combo.addItem(text, NONE if comp is None else _option(position, comp))
        combo.setItemData(0, tip, QtCore.Qt.ToolTipRole)
        combo.setToolTip(tip)
        combo.setEnabled(False)
        line.addWidget(lbl)
        line.addWidget(combo, 1)
        help_button = self._info_button(self._preset_content, label,
                                        lambda p=position, c=combo: self._selector_help(p, c))
        line.addWidget(help_button)
        self.btn_preset_info[position] = help_button
        layout.addLayout(line)
        self.preset_combo[position] = combo
        self._preset_labels[position] = lbl
        return line

    def _preset_note(self, layout, position: str, messages: Dict[str, Tuple[List[str], List[str]]]) -> None:
        note = QtWidgets.QLabel()
        note.setWordWrap(True)
        layout.addWidget(note)
        self._note(note, *messages[position])
        self.preset_conflict[position] = note

    def _preset_section(self, position: str, title: str) -> CollapsibleSection:
        section = CollapsibleSection(self._tr(title), self._preset_content)
        self._preset_layout.addWidget(section)
        self.preset_sections[position] = section
        return section

    def _read_only_editor(self, comp: Component, parent: QtWidgets.QWidget, **kwargs: Any) -> SubordinateEditor:
        editor = SubordinateEditor(comp, parent, **self._editor_kw(), **kwargs)
        editor.set_read_only(True)
        return editor

    def _preset_rows(self, config: WakeConfig, messages: Dict[str, Tuple[List[str], List[str]]]) -> None:
        lay = self._preset_layout
        line = self._preset_selector(lay, ENGINE, "Motor", config.engine)
        button = QtWidgets.QToolButton()
        button.setIcon(self.style().standardIcon(QtWidgets.QStyle.SP_FileDialogDetailedView))
        button.setToolTip(self._tr("Ajustes numéricos del motor"))
        button.clicked.connect(lambda _c=False: self.open_preset_window(ENGINE))
        line.insertWidget(line.count() - 1, button)  # before the information point, which stays last
        self.btn_preset_engine = button
        self._preset_note(lay, ENGINE, messages)
        self._preset_selector(lay, DEFICIT, "Déficit de estela", config.deficit)
        self._preset_note(lay, DEFICIT, messages)
        section = self._preset_section(DEFICIT, "Parámetros del déficit")
        editor = self._param_editor(_cat.entry(DEFICIT, config.deficit.name), dict(config.deficit.params))
        editor.set_read_only(True)
        section.body_layout.addWidget(editor)
        self.preset_editors[DEFICIT] = editor
        line = self._preset_selector(section.body_layout, ROTOR, "Promedio de rotor", config.rotor)
        if config.rotor is not None and _sub.args_of(config.rotor.name):
            self.preset_editors[ROTOR] = self._read_only_editor(config.rotor, section.body, path="", inline=True)
            line.insertWidget(line.count() - 1, self.preset_editors[ROTOR])
        line = self._preset_selector(section.body_layout, GROUND, "Suelo", config.ground)
        if config.ground is not None and _sub.args_of(config.ground.name):
            self.btn_preset_ground = QtWidgets.QPushButton(self._tr("Parámetros del modelo de suelo…"))
            self.btn_preset_ground.clicked.connect(lambda _c=False: self.open_preset_window(GROUND))
            line.insertWidget(line.count() - 1, self.btn_preset_ground)
        if config.deficit_ws_reference is not None:  # TurbOPark: not an argument of the deficit (M4)
            self.lbl_preset_reference = QtWidgets.QLabel(self._tr_template(
                WS_REFERENCE_LINE, reference=log_text(_readers.WS_REFERENCE_TEXT[config.deficit_ws_reference]),
                key=_f.WS_KEYS[config.deficit_ws_reference]), section.body)
            self.lbl_preset_reference.setWordWrap(True)
            section.body_layout.addWidget(self.lbl_preset_reference)
        self._preset_info(section, [(ROTOR, _option(ROTOR, config.rotor)), (GROUND, _option(GROUND, config.ground))])
        for position, label, title in ((SUPERPOSITION, "Superposición de estelas", "Parámetros de la superposición"),
                                       (TURBULENCE, "Turbulencia añadida", "Parámetros de la turbulencia")):
            comp = config.component(position)
            self._preset_selector(lay, position, label, comp)
            self._preset_note(lay, position, messages)
            section = self._preset_section(position, title)
            if comp is not None and _sub.args_of(comp.name):
                self.preset_editors[position] = self._read_only_editor(comp, section.body)
                section.body_layout.addWidget(self.preset_editors[position])
            info = self._preset_info(section, [(position, _option(position, comp))])
            section.setVisible(position in self.preset_editors or bool(info))
        # As in the manual mode: the selectors of the first level start at the same x, and in the deficit's section
        # the rotor and the ground at that of its arguments.
        form = self.preset_editors[DEFICIT].layout()
        arguments = [form.itemAt(i, QtWidgets.QFormLayout.LabelRole).widget() for i in range(form.rowCount())]
        for labels in ([self.lbl_preset] + [self._preset_labels[p] for p in (ENGINE, DEFICIT, SUPERPOSITION, TURBULENCE)],
                       arguments + [self._preset_labels[ROTOR], self._preset_labels[GROUND]]):
            for label in labels:
                label.setMinimumWidth(0)
            width = max(label.sizeHint().width() for label in labels)
            for label in labels:
                label.setMinimumWidth(width)

    def _preset_info(self, section: CollapsibleSection, items: List[Tuple[str, str]]) -> str:
        """What the classes have and the plugin does not offer, as in the manual mode."""
        text = self._excluded_text(items)
        if text:
            lbl = QtWidgets.QLabel(text, section.body)
            lbl.setWordWrap(True)
            lbl.setStyleSheet("color: #666;")
            section.body_layout.addWidget(lbl)
        return text

    def open_preset_window(self, position: str, exec_: bool = True) -> ComponentWindow:
        """The window of the engine's settings or of the ground of the model, to be read and closed. With ``exec_``
        false (tests), it is returned without running it."""
        config = _presets.config(self.combo_preset.currentData())
        if position == ENGINE:
            info = self._excluded_text([(ENGINE, _option(ENGINE, config.engine))], _ENGINE_COMPONENTS)
            window = ComponentWindow(config.engine, self, path="", title="Ajustes numéricos del motor", info=info,
                                     read_only=True, **self._editor_kw())
        else:
            window = ComponentWindow(config.ground, self, path="", inherited=config.superposition.name,
                                     inherit_note=INHERIT_WAKES, read_only=True, **self._editor_kw())
        if exec_:
            window.exec_()
        return window

    # --- reading --------------------------------------------------------------------------------------------
    def _field_issues(self) -> List[_val.Issue]:
        out = []
        for position, editor, combo in ((DEFICIT, self.deficit_editor, self.combo[DEFICIT]),
                                        (BLOCKAGE, self.blockage_editor, self.combo[BLOCKAGE])):
            if editor is None or (position == BLOCKAGE and not self._blockage_shown()):
                continue
            for arg in editor.errors():
                out.append(_val.Issue("field", position, _val.PLUGIN, UNREADABLE, "",
                                      {"arg": arg, "cls": combo.currentData()}))
        editors = [(ROTOR, self.rotor_editor)] + [(p, self.args_editor(p))
                                                  for p in (ENGINE, SUPERPOSITION, TURBULENCE, BLOCKAGE)]
        for position, editor in editors:
            for arg in (editor.errors() if editor is not None else []):
                out.append(_val.Issue("field", position, _val.PLUGIN, UNREADABLE, "", {"arg": arg, "cls": editor.name}))
        return out

    def _blockage_shown(self) -> bool:
        """The blockage row, with A2A and PUD (decision 7 of #64): with PDW, which has no blockage argument, it is not
        shown and the configuration has no blockage; its choice and its draft are kept for when the engine takes one
        (the API still refuses a blockage asked for with PDW, R1)."""
        return self.combo[ENGINE].currentData() != _PDW

    def _chosen(self, position: str) -> Optional[Component]:
        """The engine, superposition or turbulence chosen, with the arguments of its editor."""
        editor = self.args_editor(position)
        return editor.value() if editor is not None else self._remembered_top(position)

    def config(self) -> Optional[WakeConfig]:
        """The configuration of the selection; ``None`` while a field cannot be read or a class is not installed. A
        predefined model gives a new configuration each time (``presets.config``)."""
        if self._mode == PREDEFINED:
            return _presets.config(self.combo_preset.currentData())
        return self._manual_config()

    def _manual_config(self) -> Optional[WakeConfig]:
        """The configuration of the manual mode, whichever mode is shown: its conflicts and notes are always its own,
        also when the group opens with the predefined models."""
        if self._field_issues() or self._unavailable_issues():
            return None
        name = self.combo[DEFICIT].currentData()
        deficit, rotor, ground = self._deficit_draft(name)
        blockage = bsup = None
        b = self.combo[BLOCKAGE].currentData()
        if self._blockage_shown() and b:
            blockage, bsup = self._blockage_draft(b)
        return WakeConfig(engine=self._chosen(ENGINE), deficit=deficit, rotor=rotor, ground=ground,
                          superposition=self._chosen(SUPERPOSITION), turbulence=self._chosen(TURBULENCE),
                          blockage=blockage, blockage_superposition=bsup)

    def issues(self) -> List[_val.Issue]:
        """What keeps the selection from being calculated (the dialog's GaussianOverlap warning is apart, R13)."""
        return list(self._preset_issues if self._mode == PREDEFINED else self._issues)

    def provenance(self) -> Optional[Dict[str, Any]]:
        """The provenance of the predefined model chosen (``presets.provenance``); ``None`` in the manual mode."""
        return _presets.provenance(self.combo_preset.currentData()) if self._mode == PREDEFINED else None

    # --- showing --------------------------------------------------------------------------------------------
    @staticmethod
    def _in_ground_window(issue: _val.Issue) -> Optional[str]:
        """``GROUND`` or ``BLOCKAGE`` when the cause of ``issue`` is in the window of a ground model (of the deficit,
        of the blockage): the sum it inherits (R9d, R12) or one of its arguments (R15)."""
        arg = str(issue.data.get("arg", ""))
        if issue.position == GROUND and (issue.code in ("R9d", "R12", "R15", "R18")
                                         or (issue.code in ("R19", "R20") and arg)):
            return GROUND
        if issue.position == BLOCKAGE and (issue.code in ("R12", "R18") or (
                issue.code in ("R15", "R19", "R20") and arg.startswith("groundModel · "))):
            return BLOCKAGE
        return None

    def _window_messages(self, config: Optional[WakeConfig], issues: Optional[List[_val.Issue]] = None,
                         layout: Optional[List[_val.Issue]] = None) -> Dict[str, Tuple[List[str], List[str]]]:
        """What a window shows and marks its button with (decision 7 of #64): the conflicts and the notes whose cause is
        in the window of the ground of the deficit (``GROUND``), of the ground of the blockage (``BLOCKAGE``) or of the
        engine (``ENGINE``): what PyWake refuses with any layout or from a number of turbines, and the warnings of its
        arguments. ``issues`` and ``layout``: those of ``config``, if known (without ``config``, the fields that cannot
        be read)."""
        out: Dict[str, Tuple[List[str], List[str]]] = {GROUND: ([], []), BLOCKAGE: ([], []), ENGINE: ([], [])}
        if issues is None:
            issues = _val.validate(config, check_environment=False) if config is not None else []
        if layout is None:
            layout = _val.layout_issues(config) if config is not None else []
        for found, kind in ((issues, 0), (layout, 1)):
            for issue in found:
                window = self._in_ground_window(issue)
                if window is None and issue.position == ENGINE and (kind == 1 or issue.data.get("arg")):
                    window = ENGINE
                if window is not None:
                    out[window][kind].append(issue.translated(self._tr))
        if config is not None:
            for window, warnings in _notices.ground_window_warnings(config).items():
                out[window][1].extend(str(shown(w, self._tr)) for w in warnings)
            out[ENGINE][1].extend(str(shown(w, self._tr)) for w in _notices.argument_warnings(config).get(ENGINE, []))
        return out

    def _refresh(self) -> None:
        config = self._manual_config()
        self._issues = (self._unavailable_issues() + self._field_issues() if config is None
                        else _val.validate(config, check_environment=False))
        engine = self.combo[ENGINE].currentData()
        blockage_shown = self._blockage_shown()
        self.row[BLOCKAGE].setVisible(blockage_shown)
        self.sec_blockage.setVisible(blockage_shown and bool(self.combo[BLOCKAGE].currentData()))

        # Conflicts, at the visible selector; the section that holds the cause unfolds (values unchanged). A cause
        # inside the window of a ground model names the window and marks its button; the window does not open.
        # What PyWake refuses only from the second turbine or later (decision 6.1 of #64): checked with the turbines
        # when calculating; here, a note at the selector of its cause, and at its window (never a barrier).
        texts: Dict[str, List[str]] = {}
        layout_notes: Dict[str, List[str]] = {}
        layout = _val.layout_issues(config) if config is not None else []
        for issues, out in ((self._issues, texts), (layout, layout_notes)):
            for issue in issues:
                text = issue.translated(self._tr)
                window = self._in_ground_window(issue)
                if window is not None:
                    text += " " + self._tr_template(WINDOW_CONFLICT, where=_cat.position_label(window))
                out.setdefault(_SHOWN_AT.get(issue.position, issue.position), []).append(text)
        windows = self._window_messages(config, self._issues, layout)
        self._ground_conflicts, self._ground_notes = windows[GROUND]
        self._mark_ground()
        b_editor = self.args_editor(BLOCKAGE)
        if b_editor is not None:
            b_editor.mark_window("groundModel", *windows[BLOCKAGE])
            b_editor.window_messages = lambda _arg, comp: self._provisional(BLOCKAGE, comp)
            b_editor.set_inherited(self.combo[BLOCKAGE_SUPERPOSITION].currentData())
        for position, lbl in self.conflict.items():
            if position in (ROTOR, GROUND, BLOCKAGE_SUPERPOSITION):
                continue
            self._note(lbl, texts.get(position, []), [])
        codes = {(i.code, i.position, str(dict(i.data))) for i in self._issues}
        new = codes - self._last_codes
        self._last_codes = codes
        sections = {DEFICIT: self.sec_deficit, ROTOR: self.sec_deficit, GROUND: self.sec_deficit,
                    BLOCKAGE: self.sec_blockage, BLOCKAGE_SUPERPOSITION: self.sec_blockage,
                    SUPERPOSITION: self.sec_superposition, TURBULENCE: self.sec_turbulence}  # the engine: its button
        for code, position, _d in new:
            if (position in (ROTOR, GROUND, BLOCKAGE_SUPERPOSITION) or code in ("field", "R15", "R16", "R17", "R18",
                                                                                 "R19", "R20")
                    or (position, code) in ((DEFICIT, "R3"), (BLOCKAGE, "R4"), (BLOCKAGE, "R12"))) and position in sections:
                sections[position].setExpanded(True)

        # Notes (they do not keep from calculating): without blockage, and the persistent warnings (decision 19).
        # The warnings of the edited arguments (#64), at the selector of their position.
        by_position = ({p: [str(shown(w, self._tr)) for w in ws] for p, ws in _notices.argument_warnings(config).items()}
                       if config is not None else {})
        for position, notes in layout_notes.items():
            by_position[position] = notes + by_position.get(position, [])
        notes_engine = []
        if engine in NOTES_WITHOUT_BLOCKAGE and not self.combo[BLOCKAGE].currentData():
            notes_engine.append(self._tr(NOTES_WITHOUT_BLOCKAGE[engine]))
        self._note(self.conflict[ENGINE], texts.get(ENGINE, []), notes_engine + by_position.get(ENGINE, []))
        # The causes in the arguments of the engine mark its button (its window shows them, it never opens itself).
        self._engine_conflicts, self._engine_notes = windows[ENGINE]
        self._mark_engine()
        if by_position.get(DEFICIT):
            self._note(self.conflict[DEFICIT], texts.get(DEFICIT, []), by_position[DEFICIT])
        sup = _cat.entry(SUPERPOSITION, self.combo[SUPERPOSITION].currentData())
        notes_sup = ([str(shown(w, self._tr)) for w in _notices.superposition_warnings(config)] if config is not None
                     else [self._tr(sup.warning)] if sup.warning else [])
        self._note(self.conflict[SUPERPOSITION], texts.get(SUPERPOSITION, []),
                   notes_sup + by_position.get(SUPERPOSITION, []))
        notes_t = []
        if config is not None and _notices.turbulence_without_effect(config):
            notes_t.append(self._tr_template(TURBULENCE_WITHOUT_EFFECT, cls=config.deficit.name))
        self._note(self.conflict[TURBULENCE], texts.get(TURBULENCE, []), notes_t + by_position.get(TURBULENCE, []))
        b = self.combo[BLOCKAGE].currentData()
        if config is not None:
            warn_b = [str(shown(w, self._tr)) for w in _notices.blockage_warnings(config)]
        else:
            warning = _cat.entry(BLOCKAGE, b).warning if b and engine == _PUD else ""
            warn_b = [self._tr(warning)] if warning else []
        self._note(self.conflict[BLOCKAGE], texts.get(BLOCKAGE, []), warn_b + by_position.get(BLOCKAGE, []))

        # The arguments PyWake has and the plugin does not offer, with their reason; a section shows only with
        # something in it.
        self.lbl_rotor_info.setText(self._excluded_text(
            [(ROTOR, self.combo[ROTOR].currentData()), (GROUND, self.combo[GROUND].currentData())]))
        self.lbl_blockage_info.setText(self._excluded_text([(BLOCKAGE, b)] if b else []))
        for position, sec, lbl in ((SUPERPOSITION, self.sec_superposition, self.lbl_superposition_info),
                                   (TURBULENCE, self.sec_turbulence, self.lbl_turbulence_info)):
            lbl.setText(self._excluded_text([(position, self.combo[position].currentData())]))
            sec.setVisible(self.args_editor(position) is not None or bool(lbl.text()))
        for lbl in (self.lbl_rotor_info, self.lbl_blockage_info, self.lbl_superposition_info,
                    self.lbl_turbulence_info):
            lbl.setVisible(bool(lbl.text()))

        # Decision 7 of #64: no summary nor «Diferencias» in the dialog (what was executed, with its differences and
        # their routes, is in the result).
        self._align_sections()
        self._align_first_level()
        self.changed.emit()

    def _align_sections(self) -> None:
        """One left margin per section (decision 7 of #64): the labels of its rows and of the forms of its editors, as
        wide as the widest, so that their controls start at the same x; and the n of the rotor of the deficit, and the
        nested ones of the blockage and of the turbulence with the button of the ground of the blockage, as wide as the
        button of the ground of the deficit (marked or not)."""
        for rows, editors in (((ROTOR, GROUND), (self.deficit_editor,)),
                              ((BLOCKAGE_SUPERPOSITION,), (self.blockage_editor, self.args_editor(BLOCKAGE)))):
            labels = [self._row_label[p] for p in rows]
            for editor in editors:
                form = editor.layout() if editor is not None else None
                if isinstance(form, QtWidgets.QFormLayout):
                    items = (form.itemAt(i, QtWidgets.QFormLayout.LabelRole) for i in range(form.rowCount()))
                    labels += [item.widget() for item in items if item is not None and item.widget() is not None]
            for label in labels:
                label.setMinimumWidth(0)
            width = max(label.sizeHint().width() for label in labels)
            for label in labels:
                label.setMinimumWidth(width)
        text = self.btn_ground.text()
        self.btn_ground.setText("⚠ " + self._tr("Parámetros del modelo de suelo…"))
        self.btn_ground.setMinimumWidth(0)
        self.btn_ground.setMaximumWidth(16777215)
        width = self.btn_ground.sizeHint().width()
        self.btn_ground.setText(text)
        self.btn_ground.setFixedWidth(width)
        try:
            n = self.rotor_editor.control("n") if self.rotor_editor is not None else None
        except KeyError:  # a rotor without n
            n = None
        if isinstance(n, QtWidgets.QWidget):
            n.setFixedWidth(width)
        for position in (BLOCKAGE, TURBULENCE):  # their nested rotor and ground, as wide (QGIS tests of #64, QG1)
            editor = self.args_editor(position)
            if editor is not None:
                editor.align_nested(width)

    def _align_first_level(self) -> None:
        """The five selectors of the first level start at the same x (decision 7 of #64, point 11: a piece of its own,
        to be undone alone if the user does not like it)."""
        labels = [self._row_label[p] for p in (ENGINE, DEFICIT, SUPERPOSITION, BLOCKAGE, TURBULENCE)]
        for label in labels:
            label.setMinimumWidth(0)
        width = max(label.sizeHint().width() for label in labels)
        for label in labels:
            label.setMinimumWidth(width)

    def _note(self, lbl: QtWidgets.QLabel, conflicts: List[str], notes: List[str]) -> None:
        """A note under a selector: the conflicts in red and the warnings and notes in orange (decision 7 of #64)."""
        lbl.setTextFormat(QtCore.Qt.RichText)
        lbl.setText(coloured_lines(conflicts, notes))
        lbl.setVisible(bool(conflicts or notes))

    def _excluded_text(self, items: List[Tuple[str, str]], skip: Tuple[str, ...] = ()) -> str:
        lines = []
        for position, option in items:
            if not option:
                continue
            e = next(x for x in _cat.entries(position) if x.option == option)
            lines += [self._tr_template(EXCLUDED_ARG, name=n, value=v, reason=self._tr(r))
                      for n, v, r in _excluded(e, skip)]
        return "\n".join(lines)


class WakeGroupMirror(QtCore.QObject):
    """The visible selectors of a ``WakeModelGroup`` in another form (the interactive map's dock, #75 row 1.6):
    the same options, enabled and disabled as in the group, with the same help, and under each one the note the group
    shows under it (its conflicts, warnings and notes, each line in its colour); the note of the old preferences
    first, as in the group. A change here is a change of the group's selector; the group's changes are shown here.
    Nothing else is decided here.

    With the predefined models it reflects what the group lets change, no more: «Modelo» (a change here changes the
    model of the group) with the notes of the model, and the selectors with the components of the model, disabled,
    which forward nothing. The mode is changed in the dialog only; the mirror follows it."""

    def __init__(self, group: WakeModelGroup, form: QtWidgets.QFormLayout, tr: Callable[[str], str] = _identity):
        super().__init__(form.parentWidget())
        self.group = group
        self.combo: Dict[str, QtWidgets.QComboBox] = {}
        self._syncing = False
        labels = {ENGINE: "Motor", DEFICIT: "Déficit de estela", SUPERPOSITION: "Superposición de estelas",
                  BLOCKAGE: "Bloqueo", TURBULENCE: "Turbulencia añadida"}
        self.labels: Dict[str, QtWidgets.QLabel] = {}
        self.notes: Dict[str, QtWidgets.QLabel] = {}
        self.lbl_preferences = self._note_label()
        form.addRow(self.lbl_preferences)
        self.lbl_preset = QtWidgets.QLabel(tr("Modelo"))
        self.combo_preset = QtWidgets.QComboBox()
        self.combo_preset.setSizeAdjustPolicy(QtWidgets.QComboBox.AdjustToMinimumContentsLengthWithIcon)
        form.addRow(self.lbl_preset, self.combo_preset)
        mark_translated(self.lbl_preset)
        mark_translated(self.combo_preset)
        self.combo_preset.currentIndexChanged.connect(lambda _i: self._forward_preset())
        self.preset_note = self._note_label()
        self.preset_note.setOpenExternalLinks(True)
        form.addRow(self.preset_note)
        for position in SHOWN_POSITIONS:
            combo = QtWidgets.QComboBox()
            combo.setSizeAdjustPolicy(QtWidgets.QComboBox.AdjustToMinimumContentsLengthWithIcon)
            self.labels[position] = QtWidgets.QLabel(tr(labels[position]))
            form.addRow(self.labels[position], combo)
            mark_translated(self.labels[position])  # set translated: the dock's apply_i18n leaves them
            mark_translated(combo)
            combo.currentIndexChanged.connect(lambda _i, p=position: self._forward(p))
            self.combo[position] = combo
            self.notes[position] = self._note_label()
            form.addRow(self.notes[position])
        group.changed.connect(self.sync)
        self.sync()

    @staticmethod
    def _note_label() -> QtWidgets.QLabel:
        lbl = QtWidgets.QLabel()
        lbl.setWordWrap(True)
        lbl.setTextFormat(QtCore.Qt.RichText)
        lbl.setVisible(False)
        mark_translated(lbl)
        return lbl

    def sync(self) -> None:
        """Copy the group's options (text, data, help, enabled) and choices, and its notes; with the predefined models,
        those of its view of the model."""
        self.lbl_preset.setText(self.group._tr("Modelo"))
        for position, label in self.labels.items():
            label.setText(self.group._row_label[position].text())
        self._syncing = True
        predefined = self.group.mode() == PREDEFINED
        try:
            self._copy(self.group.combo_preset, self.combo_preset)
            for w in (self.lbl_preset, self.combo_preset):
                w.setVisible(predefined)
            self._copy_note(self.group.preset_note if predefined else None, self.preset_note)
            for position, mine in self.combo.items():
                theirs = self.group.preset_combo.get(position) if predefined else self.group.combo[position]
                mine.setEnabled(not predefined)
                mine.setStyleSheet(READ_ONLY_STYLE if predefined else "")  # read like the view of the dialog
                if theirs is None:  # the blockage, which no predefined model has
                    mine.clear()
                    continue
                self._copy(theirs, mine)
            visible = not predefined and self.group.row[BLOCKAGE].isVisibleTo(self.group)
            self.combo[BLOCKAGE].setVisible(visible)
            self.labels[BLOCKAGE].setVisible(visible)
            # What the group says under each visible selector, there (decision 7 of #64, D6: each line in its colour
            # and in its place; the notes of the group are rich text already; the note of the old preferences, orange).
            pref = self.group.lbl_preferences.text() if not predefined else ""
            self.lbl_preferences.setText(coloured_lines([], [pref]) if pref else "")
            self.lbl_preferences.setVisible(bool(pref))
            for position, note in self.notes.items():
                self._copy_note(self.group.preset_conflict.get(position) if predefined else self.group.conflict[position],
                                note)
        finally:
            self._syncing = False

    def _copy_note(self, theirs: Optional[QtWidgets.QLabel], note: QtWidgets.QLabel) -> None:
        text = theirs.text() if theirs is not None and theirs.isVisibleTo(self.group) else ""
        note.setText(text)
        note.setVisible(bool(text))

    @staticmethod
    def _copy(theirs: QtWidgets.QComboBox, mine: QtWidgets.QComboBox) -> None:
        """The options of a selector of the group (text, data, help, enabled), its choice and its help."""
        mine.clear()
        for i in range(theirs.count()):
            mine.addItem(theirs.itemText(i), theirs.itemData(i))
            mine.setItemData(i, theirs.itemData(i, QtCore.Qt.ToolTipRole), QtCore.Qt.ToolTipRole)
            item = theirs.model().item(i) if hasattr(theirs.model(), "item") else None
            if item is not None and not item.isEnabled():
                mine.model().item(i).setEnabled(False)
        mine.setCurrentIndex(theirs.currentIndex())
        mine.setToolTip(theirs.toolTip())  # the help of the selector itself (what is not offered, and why)

    def _forward_preset(self) -> None:
        if self._syncing:
            return
        i = self.group.combo_preset.findData(self.combo_preset.currentData())
        if i >= 0 and i != self.group.combo_preset.currentIndex():
            self.group.combo_preset.setCurrentIndex(i)

    def _forward(self, position: str) -> None:
        if self._syncing or self.group.mode() == PREDEFINED:  # the components of a model are not changed here
            return
        data = self.combo[position].currentData()
        i = self.group.combo[position].findData(data)
        if i >= 0 and i != self.group.combo[position].currentIndex():
            self.group.combo[position].setCurrentIndex(i)

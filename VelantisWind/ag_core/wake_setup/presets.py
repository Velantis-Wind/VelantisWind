# -*- coding: utf-8 -*-
"""The predefined wind farm models of PyWake, as fixed configurations of the manual mode (plan of the predefined models).

Each preset is the one documented under its bold title on PyWake's page «Predefined Engineering Wind Farm Models»
(``PAGE``), except Fuga and FugaBlockage, with the configuration of the class documented there in PyWake 2.6.18
(``REFERENCE_VERSION``): engine, deficit with its arguments, rotor, ground, superposition and turbulence, nested
arguments included. Every argument of the contract (those of the catalogue and of ``subordinates``) is written here,
so nothing of it is left to the signatures of the installed PyWake (decision 4); two exceptions of the definition:
``k`` of BastankhahGaussian, which its class does not give (decision 5), and the turbulence of SuperGaussian, which
its class in 2.6.18 does not have (decision 6). The arguments the plugin offers in no mode (``subordinates.EXCLUDED``:
the deflection and the other engine arguments, the table of GaussianOverlapAvgModel, the ground of a turbulence) are
outside the contract, as in the manual mode; the PyWake class of each preset leaves them to their signatures too.
TurbOPark (Nygaard_2022) also scales its deficit with the free wind speed at the turbine the wake reaches, which its
class sets after building the deficit: the field ``deficit_ws_reference`` of the contract (version 3).

``config(id)`` gives a new and independent ``WakeConfig`` built from the dictionary form, the same contract and the
same factory as the manual mode; ``provenance(id)`` what the result records of where it comes from. Nothing else of
the plugin knows the name of a preset: the factory, the validation and the API receive the expanded configuration.
"""
from __future__ import annotations

import copy
from dataclasses import dataclass
from typing import Any, Dict, Mapping, Optional, Tuple

from .config import DESTINATION_FREE_STREAM, WAKE_CONFIG_SCHEMA, WS_REFERENCE_VERSION, WakeConfig
from ..log_text import log_text

__all__ = ["PAGE", "REFERENCE_VERSION", "Preset", "PRESETS", "ids", "preset", "config", "provenance",
           "adapted", "checked_provenance", "identification", "notes"]

PAGE = "https://topfarm.pages.windenergy.dtu.dk/PyWake/api/PredefinedEngineeringWindFarmModels.html"
REFERENCE_VERSION = "2.6.18"
# The version of the contract the definitions are written in (``config.WakeConfig.to_dict``).
_CONFIG_VERSION = 2

# The notes of a preset (decisions 5-7), Spanish source texts translated when shown.
K_NOTE = ("k = 0,0324555, fijo: PyWake no da a este modelo un valor de k. Se toma el valor de k por defecto de "
          "BastankhahGaussianDeficit en PyWake 2.6.18.")
SUPERGAUSSIAN_NOTE = ("Usa CrespoHernandez, como la documentación de PyWake y el ejemplo de PyWake 2.6.18. En 2.6.18 su "
                      "firma no trae turbulencia y no se puede construir con sus valores por defecto; este preset la "
                      "incorpora explícitamente.")
DEPRECATED_NOTE = "Modelo de parque de referencia marcado como obsoleto por PyWake."
NOTES = (K_NOTE, SUPERGAUSSIAN_NOTE, DEPRECATED_NOTE)


def _c(name: str, **params: Any) -> Dict[str, Any]:
    return {"class": name, "params": params}


def _crespo(ct2a: str, c: list) -> Dict[str, Any]:
    return _c("CrespoHernandez", ct2a=ct2a, c=c, addedTurbulenceSuperpositionModel=_c("SqrMaxSum"),
              rotorAvgModel=_c("AreaOverlapAvgModel"))


def _definition(deficit: Dict[str, Any], rotor: Optional[Dict[str, Any]], superposition: Dict[str, Any],
                turbulence: Optional[Dict[str, Any]], ground: Optional[Dict[str, Any]] = None,
                **fields: Any) -> Dict[str, Any]:
    """A configuration with ``PropagateDownwind`` and no blockage (every preset), and its other fields."""
    return {"engine": _c("PropagateDownwind"), "deficit": deficit, "rotor": rotor, "ground": ground,
            "superposition": superposition, "turbulence": turbulence, "blockage": None,
            "blockage_superposition": None, **fields}


@dataclass(frozen=True)
class Preset:
    """One predefined model: its title (also its identifier), the PyWake class it reproduces, the revision of its
    definition (changed with any change of it), the configuration (the dictionary form without ``schema`` nor
    ``version``), the anchor of its section in ``PAGE`` and its notes."""

    id: str
    reference_class: str
    revision: int
    definition: Mapping[str, Any]
    anchor: str
    notes: Tuple[str, ...] = ()

    @property
    def url(self) -> str:
        return f"{PAGE}#{self.anchor}"


_LIT = "py_wake.literature."
PRESETS: Tuple[Preset, ...] = (
    # Jensen_1983 (literature/noj.py:20-22).
    Preset("NOJ", _LIT + "noj.Jensen_1983", 1, _definition(
        _c("NOJDeficit", ct2a="ct2a_madsen", k=0.1), _c("AreaOverlapAvgModel"), _c("SquaredSum"), None), "noj"),
    # Bastankhah_PorteAgel_2014 (literature/gaussian_models.py:29-35); ctlim, of BastankhahGaussianDeficit
    # (deficit_models/gaussian.py); k of decision 5.
    Preset("BastankhahGaussian", _LIT + "gaussian_models.Bastankhah_PorteAgel_2014", 1, _definition(
        _c("BastankhahGaussianDeficit", ct2a="ct2a_mom1d", k=0.0324555, ceps=0.2, ctlim=0.899,
           use_effective_ws=True), None, _c("LinearSum"), None), "bastankhahgaussian", (K_NOTE,)),
    # IEA37SimpleBastankhahGaussian (deficit_models/gaussian.py:251-256), deprecated as a wind farm model (decision 7).
    Preset("IEA37SimpleBastankhahGaussian", "py_wake.deficit_models.gaussian.IEA37SimpleBastankhahGaussian", 1,
           _definition(_c("IEA37SimpleBastankhahGaussianDeficit"), None, _c("SquaredSum"), None),
           "iea37simplebastankhahgaussian", (DEPRECATED_NOTE,)),
    # Niayifar_PorteAgel_2016 (literature/gaussian_models.py:85-91); ctlim of NiayifarGaussianDeficit; the
    # rotorAvgModel of its CrespoHernandez, of the signature of CrespoHernandez (turbulence_models/crespo.py:20-22).
    Preset("NiayifarGaussian", _LIT + "gaussian_models.Niayifar_PorteAgel_2016", 1, _definition(
        _c("NiayifarGaussianDeficit", ct2a="ct2a_mom1d", a=[0.3837, 0.003678], ceps=0.2, ctlim=0.899,
           use_effective_ws=True, use_effective_ti=True), _c("GaussianOverlapAvgModel"), _c("LinearSum"),
        _crespo("ct2a_mom1d", [0.73, 0.8325, 0.0325, -0.32])), "niayifargaussian"),
    # Zong_PorteAgel_2020 (literature/gaussian_models.py:196-203); ct2a and ctlim of ZongGaussianDeficit, the
    # arguments of WeightedSum of its signature (superposition_models.py); deltawD = 1/√2.
    Preset("ZongGaussian", _LIT + "gaussian_models.Zong_PorteAgel_2020", 1, _definition(
        _c("ZongGaussianDeficit", ct2a="ct2a_madsen", a=[0.38, 0.004], ctlim=0.899, deltawD=0.7071067811865475,
           eps_coeff=0.35, lam=7.5, B=3, use_effective_ws=True, use_effective_ti=True), None,
        _c("WeightedSum", delta=0.01, max_err=0.001, max_iter=5, weight_limit=10000000000),
        _crespo("ct2a_mom1d", [0.73, 0.83, 0.03, -0.32])), "zonggaussian"),
    # Blondel_Cathelain_2020 (literature/gaussian_models.py:251-257); the arguments of
    # BlondelSuperGaussianDeficit2020 of its signature; CrespoHernandez() of 2.6.18 (decision 6).
    Preset("SuperGaussian", _LIT + "gaussian_models.Blondel_Cathelain_2020", 1, _definition(
        _c("BlondelSuperGaussianDeficit2020", a_s=0.17, b_s=0.005, c_s=0.2, b_f=-0.68, c_f=2.41, ctlim=0.999,
           use_effective_ws=True, use_effective_ti=True), None, _c("LinearSum"),
        _crespo("ct2a_madsen", [0.73, 0.8325, -0.0325, -0.32])), "supergaussian", (SUPERGAUSSIAN_NOTE,)),
    # Nygaard_2022 (literature/turbopark.py:25-41): TurboGaussianDeficit(ct2a=ct2a_mom1d, ctlim=0.96,
    # groundModel=Mirror(superpositionModel=SquaredSum()), rotorAvgModel=GaussianOverlapAvgModel()) with the rest of
    # its signature, WS_key = 'WS_jlk' (the field deficit_ws_reference, M4), SquaredSum and no turbulence.
    Preset("TurbOPark", _LIT + "turbopark.Nygaard_2022", 1, _definition(
        _c("TurboGaussianDeficit", ct2a="ct2a_mom1d", A=0.04, cTI=[1.5, 0.8], ceps=0.25, ctlim=0.96,
           use_effective_ws=False, use_effective_ti=False), _c("GaussianOverlapAvgModel"), _c("SquaredSum"), None,
        ground=_c("Mirror", superpositionModel=_c("SquaredSum")), deficit_ws_reference=DESTINATION_FREE_STREAM),
        "turbopark"),
)


def ids() -> Tuple[str, ...]:
    """The presets, in the order of the page (decision 2)."""
    return tuple(p.id for p in PRESETS)


def preset(id_: str) -> Preset:
    for p in PRESETS:
        if p.id == id_:
            return p
    raise KeyError(id_)


def config(id_: str) -> WakeConfig:
    """A new configuration of the preset, independent of any other (its lists and nested components are new)."""
    data = copy.deepcopy(dict(preset(id_).definition))
    version = WS_REFERENCE_VERSION if "deficit_ws_reference" in data else _CONFIG_VERSION
    return WakeConfig.from_dict(dict(data, schema=WAKE_CONFIG_SCHEMA, version=version))


def provenance(id_: str) -> Dict[str, Any]:
    """Where a configuration of the preset comes from, for the result (decision 14): its identifier, the revision of its
    definition, the PyWake class and version of reference, the version executed, and its notes."""
    import py_wake
    p = preset(id_)
    return {"preset": p.id, "revision": p.revision, "reference_class": p.reference_class,
            "reference_version": REFERENCE_VERSION, "executed_version": py_wake.__version__, "url": p.url,
            "notes": list(p.notes)}


# The libraries GaussianOverlapAvgModel may miss, as ``validation.missing_gaussian_overlap_modules`` lists them.
_MISSING_MODULES = (("h5py",), ("h5netcdf",), ("h5py", "h5netcdf"))


def adapted(id_: str, wake_config: WakeConfig) -> bool:
    """Whether ``wake_config`` is the preset with exactly the adaptation the user may accept without the libraries of
    its GaussianOverlapAvgModel (decisions 17 and 18): ``CGIRotorAvg(7)`` instead, recorded, and nothing else."""
    from .api import ACCEPTED_NOW, ACCEPTED_SAVED, gaussian_overlap_adaptation
    own = config(id_)
    return own.rotor is not None and own.rotor.name == "GaussianOverlapAvgModel" and any(
        wake_config == gaussian_overlap_adaptation(own, list(m), a)
        for m in _MISSING_MODULES for a in (None, ACCEPTED_NOW, ACCEPTED_SAVED))


def checked_provenance(wake_config: WakeConfig, given: Optional[Mapping[str, Any]]) -> Optional[Dict[str, Any]]:
    """The provenance a calculation records: ``None`` without one; with one, it must be the current provenance of its
    preset and ``wake_config`` that preset's configuration, or the preset ``adapted``, else ``ValueError`` (a result
    never claims a preset it does not calculate)."""
    if given is None:
        return None
    try:
        own = provenance(given.get("preset"))
    except (KeyError, AttributeError) as exc:
        raise ValueError(log_text("Procedencia de modelo predefinido no reconocida: {value!r}.", value=given)) from exc
    if dict(given) != own or (wake_config != config(own["preset"]) and not adapted(own["preset"], wake_config)):
        raise ValueError(log_text("La configuración no es la del modelo predefinido {preset} (revisión {revision}) que "
                                  "dice su procedencia.", preset=own["preset"], revision=given.get("revision")))
    return own


def identification(record: Mapping[str, Any], wake_config: Optional[WakeConfig] = None) -> Any:
    """«Modelo predefinido: <título>», the identification of a result of a preset (instead of its differences with the
    signatures, which are not the user's); for the preset ``adapted`` (``wake_config``, already checked), what it is
    instead (decision 19)."""
    if wake_config is not None and wake_config.adaptations:
        return log_text("Configuración adaptada a partir de {preset}: CGIRotorAvg(7)", preset=record["preset"])
    return log_text("Modelo predefinido: {preset}", preset=record["preset"])


def notes(record: Mapping[str, Any]) -> list:
    """The notes of a preset, for the warnings of its result (translated when shown); that of SuperGaussian with the
    link to its documentation (decision 6), as under the selector."""
    return [log_text("{note} {url}", note=log_text(n), url=record["url"]) if n == SUPERGAUSSIAN_NOTE and record.get("url")
            else log_text(n) for n in record.get("notes") or ()]

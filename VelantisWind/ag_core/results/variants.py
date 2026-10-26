# -*- coding: utf-8 -*-
"""The auxiliary configurations of the loss breakdown, built from the main one (README, «Resultado»; #75 rows 4.3-4.4).

Each variant is the effective configuration of the main calculation with only its declared intervention:

- turbulence intervention (A_W and A_WB): no turbulence model and, only in the classes whose signature has
  ``use_effective_ti``, that argument set to ``False`` (Bastankhah, NOJ and IEA37 do not have it and are not
  given it);
- blockage intervention (A_W and A_WT): no blockage model (and no blockage superposition), with the same engine.

A_0 is an internal configuration outside the catalogue: the engine of the main one with ``NoWakeDeficit``,
``LinearSum`` and no rotor average, ground model, turbulence nor blockage (PropagateUpDownIterative accepts it,
``engineering_models.py:540``). Each variant is calculated with ``run`` (a callable that builds, checks the classes
and simulates one configuration, and returns the AEP per turbine), on its own; one that fails is ``failed`` with
its error, never zero, and the others go on.
"""
from __future__ import annotations

from typing import Any, Callable, Dict, Optional, Tuple

import numpy as np

from . import breakdown as bd
from ..log_text import log_text
from ..wake_setup.config import Component, WakeConfig

__all__ = ["FREE_STREAM", "variant_configs", "turbulence_changes_deficit", "run_breakdown"]

# The marker of the A_0 configuration (built by the factory's free-stream path, not from the catalogue).
FREE_STREAM = "free_stream"


def _without_turbulence(config: WakeConfig) -> WakeConfig:
    params = dict(config.deficit.params)
    if "use_effective_ti" in params:
        params["use_effective_ti"] = False
    return WakeConfig(**{**config.__dict__, "turbulence": None, "deficit": Component(config.deficit.name, params)})


def _without_blockage(config: WakeConfig) -> WakeConfig:
    return WakeConfig(**{**config.__dict__, "blockage": None, "blockage_superposition": None})


def variant_configs(config: WakeConfig) -> Dict[str, Optional[WakeConfig]]:
    """The configuration of A_W, A_WT and A_WB (``None`` when the term is the main one or is not modelled)."""
    turbulence, blockage = config.turbulence is not None, config.blockage is not None
    out: Dict[str, Optional[WakeConfig]] = {"A_W": None, "A_WT": None, "A_WB": None}
    if turbulence or blockage:
        out["A_W"] = _without_blockage(_without_turbulence(config))
    if turbulence and blockage:
        out["A_WT"] = _without_blockage(config)
        out["A_WB"] = _without_turbulence(config)
    return out


def turbulence_changes_deficit(deficit: Any) -> bool:
    """Whether the added turbulence reaches the deficit: it reads the effective TI (``args4deficit``)."""
    return "TI_eff_ilk" in getattr(deficit, "args4deficit", ())


def run_breakdown(config: WakeConfig, principal: np.ndarray, run: Callable[[Any], np.ndarray], *,
                  compute_variants: bool, turbulence_reaches_deficit: bool) -> Tuple[Dict[str, Optional[np.ndarray]],
                                                                                   Dict[str, str], Dict[str, str],
                                                                                   Dict[str, str]]:
    """Calculate the terms of the breakdown of ``config``, whose AEP per turbine is ``principal``.

    Returns ``(aep, aep_states, states, errors)``: the AEP per turbine of A_0, A_W, A_WT, A_WB and A_WTB, their
    states, the states of the derived terms (``breakdown.term_states``) and the error of each failed term.
    ``run`` receives a ``WakeConfig`` or ``FREE_STREAM``. A_0 is always calculated; the other variants only with
    ``compute_variants``.
    """
    turbulence, blockage = config.turbulence is not None, config.blockage is not None
    aep: Dict[str, Optional[np.ndarray]] = {"A_WTB": np.asarray(principal, float)}
    states: Dict[str, str] = {"A_WTB": bd.OK}
    errors: Dict[str, str] = {}

    def attempt(term: str, target: Any) -> None:
        try:
            aep[term] = np.asarray(run(target), float)
            states[term] = bd.OK
        except Exception as exc:
            aep[term] = None
            states[term] = bd.FAILED
            # The message of an error of the physics stays a template (translated when shown).
            message = exc.args[0] if exc.args and getattr(exc.args[0], "template_item", None) else str(exc)
            errors[term] = log_text("{kind}: {message}", kind=type(exc).__name__, message=message)

    attempt("A_0", FREE_STREAM)
    configs = variant_configs(config)
    # The terms that are the main configuration itself.
    if not turbulence and not blockage:
        aep["A_W"], states["A_W"] = aep["A_WTB"], bd.OK
    if turbulence and not blockage:
        aep["A_WT"], states["A_WT"] = aep["A_WTB"], bd.OK
    if blockage and not turbulence:
        aep["A_WB"], states["A_WB"] = aep["A_WTB"], bd.OK
    for term in ("A_W", "A_WT", "A_WB"):
        if term in states:
            continue
        if configs[term] is None:
            aep[term], states[term] = None, bd.NOT_MODELLED
        elif not compute_variants:
            aep[term], states[term] = None, bd.NOT_REQUESTED
        else:
            attempt(term, configs[term])
    derived = bd.term_states(aep_states=states, turbulence=turbulence, blockage=blockage,
                             turbulence_changes_deficit=turbulence_reaches_deficit)
    return aep, states, derived, errors

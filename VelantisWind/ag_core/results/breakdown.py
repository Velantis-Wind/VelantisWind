# -*- coding: utf-8 -*-
"""The signed loss breakdown of an AEP result (schema 2; P0, section 8; README, «Resultado»).

From the AEP per turbine of the main configuration and of its variants,

    A_0   no wakes and no blockage (``aep_free``)
    A_W   wakes, without added turbulence nor blockage
    A_WT  wakes with the added turbulence, without blockage
    A_WB  wakes with blockage, without added turbulence (only for the interaction diagnostic)
    A_WTB the main configuration (``aep``)

it gives L_W = A_0 − A_W, Δ_T = A_WT − A_W, Δ_B = A_WTB − A_WT and L_total = A_0 − A_WTB = L_W − Δ_T − Δ_B,
with I_TB = A_WTB − A_WT − A_WB + A_W as a diagnostic outside the balance, per turbine, per model and for the
farm, each with its state: ``ok``, ``zero_by_construction`` (Δ_T when the deficit does not use the effective TI),
``not_modelled`` (no turbulence, no blockage), ``not_requested`` (variants not computed) or ``failed`` (its
variant failed, with the error). A term that is not available is ``None``: never a zero, and the total is never
presented as the wake loss. Percentages are over A_0 of the same scope, ``None`` when A_0 is not available or not
positive. Sums are of the signed values, never clipped.
"""
from __future__ import annotations

from typing import Any, Dict, List, Mapping, Optional, Sequence

import numpy as np

__all__ = ["OK", "ZERO_BY_CONSTRUCTION", "NOT_MODELLED", "NOT_REQUESTED", "FAILED", "TERMS", "AEP_TERMS",
           "term_states", "per_turbine", "aggregate", "states_text", "TURBINE_FIELDS"]

OK = "ok"
ZERO_BY_CONSTRUCTION = "zero_by_construction"
NOT_MODELLED = "not_modelled"
NOT_REQUESTED = "not_requested"
FAILED = "failed"

AEP_TERMS = ("A_0", "A_W", "A_WT", "A_WB", "A_WTB")
TERMS = ("L_W", "D_T", "D_B", "L_total", "I_TB")
# The per-turbine fields of schema 2 (P0, section 8) for each term; I_TB stays in the global and per-model summary.
TURBINE_FIELDS = {"A_0": "aep_free_mwh", "A_W": "aep_w_mwh", "A_WT": "aep_wt_mwh", "A_WB": "aep_wb_mwh",
                  "A_WTB": "aep_mwh", "L_W": "l_wake_mwh", "D_T": "d_turb_mwh", "D_B": "d_blk_mwh",
                  "L_total": "l_total_mwh"}


def term_states(*, aep_states: Mapping[str, str], turbulence: bool, blockage: bool,
                turbulence_changes_deficit: bool) -> Dict[str, str]:
    """The state of each derived term from the states of the AEP terms and the main configuration.

    ``aep_states`` gives the state of A_0, A_W, A_WT, A_WB and A_WTB (A_WTB, the main one, is always ``ok``).
    Without added turbulence A_WT is ``not_modelled`` and stands for A_W in Δ_B; without blockage A_WB is
    ``not_modelled``; without either, A_W is the main configuration itself.
    """
    s = dict(aep_states)
    wt = "A_WT" if turbulence else "A_W"

    def combine(*names: str) -> str:
        for state in (FAILED, NOT_REQUESTED, NOT_MODELLED):
            if any(s[n] == state for n in names):
                return state
        return OK

    out = {"L_W": combine("A_0", "A_W"), "L_total": combine("A_0", "A_WTB")}
    if not turbulence:
        out["D_T"] = NOT_MODELLED
    else:
        out["D_T"] = combine("A_WT", "A_W")
        if out["D_T"] == OK and not turbulence_changes_deficit:
            out["D_T"] = ZERO_BY_CONSTRUCTION
    out["D_B"] = NOT_MODELLED if not blockage else combine("A_WTB", wt)
    out["I_TB"] = NOT_MODELLED if not (turbulence and blockage) else combine("A_WTB", "A_WT", "A_WB", "A_W")
    return out


def _derive(a: Mapping[str, Optional[np.ndarray]], states: Mapping[str, str]) -> Dict[str, Optional[np.ndarray]]:
    def diff(x: Optional[np.ndarray], y: Optional[np.ndarray]):
        return None if x is None or y is None else x - y

    # Without added turbulence, A_WT is A_W (D_T not modelled): Δ_B is measured from A_W.
    wt = a.get("A_WT") if states.get("D_T") != NOT_MODELLED else a.get("A_W")
    out: Dict[str, Optional[np.ndarray]] = {
        "L_W": diff(a.get("A_0"), a.get("A_W")), "D_T": diff(a.get("A_WT"), a.get("A_W")),
        "D_B": diff(a.get("A_WTB"), wt), "L_total": diff(a.get("A_0"), a.get("A_WTB")), "I_TB": None,
    }
    if all(a.get(n) is not None for n in ("A_WTB", "A_WT", "A_WB", "A_W")):
        out["I_TB"] = a["A_WTB"] - a["A_WT"] - a["A_WB"] + a["A_W"]
    for term in out:
        if states.get(term) not in (OK, ZERO_BY_CONSTRUCTION):
            out[term] = None
    return out


def _pct(value: Optional[float], base: Optional[float]) -> Optional[float]:
    if value is None or base is None or not base > 0:
        return None
    return 100.0 * float(value) / float(base)


def states_text(aep_states: Mapping[str, str], states: Mapping[str, str]) -> str:
    """The ``wake_states`` field of a turbine: ``A_0=ok;A_W=ok;…;L_total=ok``."""
    names = list(AEP_TERMS[:4]) + ["L_W", "D_T", "D_B", "L_total"]
    merged = dict(aep_states, **states)
    return ";".join(f"{n}={merged[n]}" for n in names)


def per_turbine(aep: Mapping[str, Optional[np.ndarray]], aep_states: Mapping[str, str],
                states: Mapping[str, str]) -> List[Dict[str, Any]]:
    """The schema-2 breakdown fields of each turbine (``TURBINE_FIELDS`` and their ``_pct``), plus ``wake_states``."""
    a = {k: (None if aep.get(k) is None or aep_states.get(k) != OK else np.asarray(aep[k], float)) for k in AEP_TERMS}
    derived = _derive(a, states)
    n = len(np.asarray(aep["A_WTB"]))
    text = states_text(aep_states, states)
    rows = []
    for i in range(n):
        base = float(a["A_0"][i]) if a["A_0"] is not None else None
        row: Dict[str, Any] = {}
        for term, field in TURBINE_FIELDS.items():
            source = a.get(term) if term in AEP_TERMS else derived.get(term)
            value = float(source[i]) if source is not None else None
            row[field] = value
            if term in TERMS:
                row[field.replace("_mwh", "_pct")] = _pct(value, base)
        row["wake_states"] = text
        rows.append(row)
    return rows


def aggregate(aep: Mapping[str, Optional[np.ndarray]], aep_states: Mapping[str, str], states: Mapping[str, str],
              groups: Optional[Sequence[Any]] = None) -> Dict[Any, Dict[str, Any]]:
    """The breakdown of the farm (``groups`` ``None``: one key, ``None``) or of each group (the model of each turbine).

    Each value: ``{term: {"mwh": value or None, "pct": value or None, "state": state}}`` for the five AEP terms and
    the five derived ones; the sums are of the signed per-turbine values.
    """
    a = {k: (None if aep.get(k) is None or aep_states.get(k) != OK else np.asarray(aep[k], float)) for k in AEP_TERMS}
    derived = _derive(a, states)
    n = len(np.asarray(aep["A_WTB"]))
    keys = [None] * n if groups is None else list(groups)
    out: Dict[Any, Dict[str, Any]] = {}
    for key in dict.fromkeys(keys):
        mask = np.array([k == key for k in keys], dtype=bool)
        base = float(a["A_0"][mask].sum()) if a["A_0"] is not None else None
        entry: Dict[str, Any] = {}
        for term in AEP_TERMS + TERMS:
            source = a.get(term) if term in AEP_TERMS else derived.get(term)
            value = float(source[mask].sum()) if source is not None else None
            state = aep_states[term] if term in AEP_TERMS else states[term]
            entry[term] = {"mwh": value, "pct": _pct(value, base), "state": state}
        out[key] = entry
    return out
